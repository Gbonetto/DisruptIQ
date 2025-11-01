"""
Assistant Interface Endpoints
Intelligent database querying with natural language
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog

from app.services.sql_agent_service import SQLAgentService
from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)


class SQLQueryRequest(BaseModel):
    """Request for natural language SQL query"""
    query: str = Field(..., description="Natural language query", min_length=3, max_length=500)
    operation_type: str = Field(default="SELECT", description="Type of operation: SELECT, INSERT, UPDATE, DELETE")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Trouve tous les plombiers dans le 13ème arrondissement",
                "operation_type": "SELECT"
            }
        }


class SQLQueryResponse(BaseModel):
    """Response for SQL query"""
    success: bool
    query: str
    sql: Optional[str] = None
    explanation: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = None
    columns: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    error: Optional[str] = None
    validation_errors: Optional[List[str]] = None


class TableStatsResponse(BaseModel):
    """Database table statistics"""
    table_name: str
    total_rows: int
    indexed_rows: Optional[int] = None
    sample_data: Optional[List[Dict[str, Any]]] = None


@router.post("/sql-query", response_model=SQLQueryResponse)
@limiter.limit("10/minute")  # Strict limit for SQL queries
async def execute_sql_query(
    request_body: SQLQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a natural language query as SQL

    ## Features:
    - Converts natural language to PostgreSQL
    - Validates SQL for security (blocks DROP, ALTER, etc.)
    - Executes queries safely with automatic LIMIT
    - Returns formatted results with explanations

    ## Examples:

    **Search queries:**
    ```json
    {
        "query": "Trouve tous les électriciens actifs à Paris",
        "operation_type": "SELECT"
    }
    ```

    **Complex joins:**
    ```json
    {
        "query": "Qui habite au 3ème étage de la résidence Les Mimosas?",
        "operation_type": "SELECT"
    }
    ```

    **Aggregations:**
    ```json
    {
        "query": "Combien de copropriétaires sont présidents de conseil syndical?",
        "operation_type": "SELECT"
    }
    ```

    ## Security:
    - Only allowed operations: SELECT, INSERT, UPDATE, DELETE
    - Blocked operations: DROP, TRUNCATE, ALTER, CREATE
    - UPDATE/DELETE require WHERE clause
    - Automatic LIMIT of 1000 rows for SELECT
    - Only allowed tables: professionnels, coproprietes, coproprietaires, documents, emails
    """
    try:
        logger.info(
            "sql_query_received",
            query=request_body.query[:100],
            operation_type=request_body.operation_type
        )

        # Validate operation type
        allowed_operations = {"SELECT", "INSERT", "UPDATE", "DELETE"}
        if request_body.operation_type.upper() not in allowed_operations:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operation type. Allowed: {', '.join(allowed_operations)}"
            )

        # Initialize SQL Agent
        sql_agent = SQLAgentService()

        # Execute natural query
        result = await sql_agent.execute_natural_query(
            query=request_body.query,
            db=db,
            operation_type=request_body.operation_type.upper()
        )

        logger.info(
            "sql_query_completed",
            query=request_body.query[:50],
            success=result.get("success"),
            row_count=result.get("row_count", 0)
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("sql_query_failed", query=request_body.query, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )


@router.get("/tables", response_model=List[str])
async def get_allowed_tables():
    """
    Get list of allowed tables for SQL queries

    Returns a list of table names that can be queried through the SQL agent.
    """
    sql_agent = SQLAgentService()
    return sorted(list(sql_agent.ALLOWED_TABLES))


@router.get("/tables/{table_name}/stats", response_model=TableStatsResponse)
async def get_table_stats(
    table_name: str,
    db: AsyncSession = Depends(get_db),
    include_sample: bool = False
):
    """
    Get statistics for a specific table

    Args:
        table_name: Name of the table
        include_sample: Include 5 sample rows (default: False)

    Returns:
        Table statistics including row count, indexed count, and optional sample data
    """
    try:
        sql_agent = SQLAgentService()

        # Validate table name
        if table_name not in sql_agent.ALLOWED_TABLES:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found or not allowed"
            )

        # Get total row count
        count_result = await sql_agent.execute_sql(
            sql=f"SELECT COUNT(*) as total FROM {table_name}",
            db=db,
            validate=True
        )

        total_rows = 0
        if count_result["success"] and count_result["results"]:
            total_rows = count_result["results"][0]["total"]

        # Get indexed row count if is_indexed column exists
        indexed_rows = None
        indexed_result = await sql_agent.execute_sql(
            sql=f"SELECT COUNT(*) as indexed FROM {table_name} WHERE is_indexed = TRUE",
            db=db,
            validate=True
        )
        if indexed_result["success"] and indexed_result["results"]:
            indexed_rows = indexed_result["results"][0]["indexed"]

        # Get sample data if requested
        sample_data = None
        if include_sample:
            sample_result = await sql_agent.execute_sql(
                sql=f"SELECT * FROM {table_name} LIMIT 5",
                db=db,
                validate=True
            )
            if sample_result["success"]:
                sample_data = sample_result["results"]

        return {
            "table_name": table_name,
            "total_rows": total_rows,
            "indexed_rows": indexed_rows,
            "sample_data": sample_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("table_stats_failed", table=table_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table stats: {str(e)}"
        )


@router.get("/schema")
async def get_database_schema():
    """
    Get the complete database schema description

    Returns a comprehensive description of all tables, columns, relationships,
    and example queries. Useful for understanding what data is available.
    """
    sql_agent = SQLAgentService()
    schema_description = sql_agent._build_schema_description()

    return {
        "schema": schema_description,
        "allowed_tables": sorted(list(sql_agent.ALLOWED_TABLES)),
        "allowed_operations": ["SELECT", "INSERT", "UPDATE", "DELETE"],
        "dangerous_operations": sorted(list(sql_agent.DANGEROUS_OPERATIONS)),
        "max_results": sql_agent.MAX_RESULTS
    }


@router.post("/validate-sql")
async def validate_sql_query(sql: str):
    """
    Validate a SQL query without executing it

    Useful for testing SQL queries before execution.
    Checks for dangerous operations and unauthorized tables.
    """
    try:
        sql_agent = SQLAgentService()
        validation_result = sql_agent._validate_sql(sql)

        return {
            "sql": sql,
            "is_valid": validation_result["is_valid"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"]
        }

    except Exception as e:
        logger.error("sql_validation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )
