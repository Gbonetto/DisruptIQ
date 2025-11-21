"""
SQL Query Validation Utilities
Validates SQL queries against whitelist before execution
"""

import re
import structlog
from typing import Tuple, List

logger = structlog.get_logger()

# SECURITY: Whitelist of allowed tables (MUST match sql_agent.py)
ALLOWED_TABLES = [
    "coproprietes",
    "coproprietaires",
    "professionnels",
    "emails",
    "documents",
    "users",
    "vendors",  # Alias for professionnels
    "conversations",
    "messages",
]


def extract_table_names(sql_query: str) -> List[str]:
    """
    Extract table names from a SQL query

    Handles:
    - FROM clauses
    - JOIN clauses
    - Quoted table names ("table" or `table`)
    - Schema prefixes (schema.table)

    Args:
        sql_query: SQL query string

    Returns:
        List of table names found in query
    """
    tables = []

    # Normalize query (lowercase, remove extra spaces)
    query_lower = sql_query.lower().strip()

    # Pattern to match table names after FROM, JOIN, UPDATE, INTO, etc.
    # Matches: FROM table, JOIN table, UPDATE table, INTO table
    # Handles quoted names and schema prefixes
    patterns = [
        r'\bfrom\s+(?:`|")?(\w+)(?:`|")?',  # FROM table
        r'\bjoin\s+(?:`|")?(\w+)(?:`|")?',  # JOIN table
        r'\binner\s+join\s+(?:`|")?(\w+)(?:`|")?',  # INNER JOIN table
        r'\bleft\s+join\s+(?:`|")?(\w+)(?:`|")?',  # LEFT JOIN table
        r'\bright\s+join\s+(?:`|")?(\w+)(?:`|")?',  # RIGHT JOIN table
        r'\bupdate\s+(?:`|")?(\w+)(?:`|")?',  # UPDATE table
        r'\binto\s+(?:`|")?(\w+)(?:`|")?',  # INSERT INTO table
        r'\bdelete\s+from\s+(?:`|")?(\w+)(?:`|")?',  # DELETE FROM table
    ]

    for pattern in patterns:
        matches = re.findall(pattern, query_lower, re.IGNORECASE)
        tables.extend(matches)

    # Remove duplicates while preserving order
    seen = set()
    unique_tables = []
    for table in tables:
        # Remove schema prefix if present (e.g., "public.users" -> "users")
        table = table.split('.')[-1]
        if table not in seen:
            seen.add(table)
            unique_tables.append(table)

    return unique_tables


def validate_sql_query(sql_query: str) -> Tuple[bool, str]:
    """
    Validate SQL query against security rules

    Security checks:
    1. All tables are in the whitelist
    2. No dangerous keywords (DROP, TRUNCATE, etc.)
    3. Query is not empty

    Args:
        sql_query: SQL query to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not sql_query or not sql_query.strip():
        return False, "Query SQL vide"

    query_upper = sql_query.upper()

    # Check for dangerous keywords
    dangerous_keywords = [
        "DROP",
        "TRUNCATE",
        "DELETE",  # DELETE is risky, better to use soft deletes
        "ALTER",
        "CREATE DATABASE",
        "DROP DATABASE",
        "GRANT",
        "REVOKE",
        "EXECUTE",
        "EXEC",
        "xp_",  # SQL Server stored procedures
        "--",  # SQL comments (can hide malicious code)
        ";--",  # Comment injection
        "/*",  # Block comments
        "*/",
    ]

    for keyword in dangerous_keywords:
        if keyword in query_upper:
            logger.warning(
                "dangerous_sql_keyword_detected",
                keyword=keyword,
                query=sql_query[:100]
            )
            return False, f"Mot-clé SQL dangereux détecté: {keyword}"

    # Extract table names from query
    tables_in_query = extract_table_names(sql_query)

    if not tables_in_query:
        logger.warning("no_tables_found_in_query", query=sql_query[:100])
        return False, "Aucune table trouvée dans la requête"

    # Check if all tables are in whitelist
    for table in tables_in_query:
        if table not in ALLOWED_TABLES:
            logger.warning(
                "unauthorized_table_access",
                table=table,
                allowed_tables=ALLOWED_TABLES,
                query=sql_query[:100]
            )
            return False, (
                f"Table non autorisée: '{table}'. "
                f"Tables autorisées: {', '.join(ALLOWED_TABLES)}"
            )

    # All checks passed
    logger.info(
        "sql_query_validated",
        tables=tables_in_query,
        query_length=len(sql_query)
    )

    return True, ""


def is_read_only_query(sql_query: str) -> bool:
    """
    Check if query is read-only (SELECT only)

    Args:
        sql_query: SQL query

    Returns:
        True if query is SELECT only
    """
    query_upper = sql_query.upper().strip()

    # Check if starts with SELECT
    if not query_upper.startswith("SELECT"):
        return False

    # Check for write operations hidden in subqueries
    write_keywords = ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE"]

    for keyword in write_keywords:
        if keyword in query_upper:
            return False

    return True
