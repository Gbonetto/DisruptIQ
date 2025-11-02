"""
SQL Agent - Intelligent Text-to-SQL for structured data queries
Handles queries about copropriétaires, copropriétés, professionnels, emails, etc.
"""

import structlog
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService
from app.models.coproprietaire import Coproprietaire
from app.models.copropriete import Copropriete
from app.models.professionnel import Professionnel

logger = structlog.get_logger()


class SQLAgent:
    """
    SQL Agent - Converts natural language to SQL queries

    Capabilities:
    - Text-to-SQL generation
    - Query validation and security
    - Result formatting in natural language
    - Support for copropriétaires, copropriétés, professionnels, emails tables
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("sql_agent_initialized")

        # Database schema for context
        self.schema = """
TABLES DISPONIBLES:

1. coproprietes
   - id: Integer (PK)
   - nom: String (ex: "Les Mimosas", "Résidence du Parc")
   - adresse: String
   - ville: String (NOT NULL)
   - code_postal: String (NOT NULL)
   - nombre_lots: Integer
   - nombre_batiments: Integer
   - created_at: DateTime

2. coproprietaires
   - id: Integer (PK)
   - nom: String (NOT NULL)
   - prenom: String (NOT NULL)
   - email: String
   - telephone: String
   - copropriete_id: Integer (FK -> coproprietes.id) (NOT NULL)
   - numero_lot: String (NOT NULL) (ex: "302", "A301", "12")
   - type_lot: String (ex: "Appartement", "Maison")
   - etage: Integer
   - surface: Decimal (en m²)
   - statut: String (default: "proprietaire")
   - created_at: DateTime

3. professionnels
   - id: Integer (PK)
   - name: String (nom du professionnel)
   - company_name: String (nom de l'entreprise)
   - category: String (ex: "plombier", "électricien", "peintre", "jardinier", "serrurier", "chauffagiste", "menuisier", "maçon")
   - email: String
   - phone: String
   - siret: String
   - description: Text
   - statut: String (active, inactive, blacklisted)
   - address: Text
   - city: String
   - postal_code: String
   - rating: Float (note sur 5)
   - is_indexed: Boolean
   - created_at: DateTime

4. emails
   - id: Integer (PK)
   - message_id: String (UNIQUE)
   - sender: String
   - subject: String
   - body: Text
   - urgency: Enum ('URGENT', 'IMPORTANT', 'ROUTINE') -- IMPORTANT: valeurs en MAJUSCULES
   - received_at: DateTime
   - processed: Boolean
"""

    async def process(self, user_input: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Process natural language query and execute SQL

        Args:
            user_input: User's question in natural language
            db: Database session

        Returns:
            Dict with success, message, data, sql_query
        """
        try:
            # Step 1: Generate SQL query
            sql_query = await self._generate_sql(user_input)

            if not sql_query:
                return {
                    "success": False,
                    "message": "Je n'ai pas pu générer une requête SQL pour cette question.",
                    "confidence": 0.0
                }

            logger.info("sql_generated", query=sql_query[:100])

            # Step 2: Validate SQL (security check)
            if not self._validate_sql(sql_query):
                return {
                    "success": False,
                    "message": "La requête générée n'est pas sûre. Veuillez reformuler votre question.",
                    "sql_query": sql_query
                }

            # Step 3: Execute SQL
            results = await self._execute_sql(sql_query, db)

            if results is None:
                return {
                    "success": False,
                    "message": "Erreur lors de l'exécution de la requête SQL.",
                    "sql_query": sql_query
                }

            # Step 4: Format results in natural language
            formatted_message = await self._format_results(user_input, results, sql_query)

            return {
                "success": True,
                "message": formatted_message,
                "data": {
                    "results": results,
                    "row_count": len(results) if isinstance(results, list) else 0,
                    "sql_query": sql_query
                },
                "sql_query": sql_query,
                "confidence": 0.9
            }

        except Exception as e:
            logger.error("sql_agent_processing_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"Erreur lors du traitement: {str(e)}"
            }

    async def _generate_sql(self, user_input: str) -> str:
        """Generate SQL query from natural language"""
        prompt = f"""
Tu es un expert SQL PostgreSQL. Génère une requête SQL SELECT UNIQUEMENT pour répondre à la question.

SCHÉMA DE BASE DE DONNÉES:
{self.schema}

RÈGLES IMPORTANTES:
1. Utilise UNIQUEMENT des SELECT (pas INSERT, UPDATE, DELETE, DROP)
2. Utilise des JOINs appropriés si nécessaire
3. Limite les résultats à 100 rows max (LIMIT 100)
4. Utilise des alias de table pour plus de clarté
5. Retourne UNIQUEMENT le SQL, sans explication

QUESTION:
{user_input}

SQL QUERY:
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=300,
                temperature=0.1
            )

            # Clean SQL response
            sql = response.strip()

            # Remove markdown code blocks if present
            if sql.startswith("```"):
                sql = sql.split("```")[1]
                if sql.startswith("sql"):
                    sql = sql[3:]
                sql = sql.strip()

            # Remove trailing semicolon
            sql = sql.rstrip(";").strip()

            return sql

        except Exception as e:
            logger.error("sql_generation_failed", error=str(e))
            return ""

    def _validate_sql(self, sql: str) -> bool:
        """
        Validate SQL query for security

        Checks:
        - Only SELECT statements allowed
        - No dangerous keywords (DROP, DELETE, UPDATE, INSERT, etc.)
        - No SQL injection patterns
        """
        sql_lower = sql.lower()

        # Must start with SELECT
        if not sql_lower.strip().startswith("select"):
            logger.warning("sql_validation_failed", reason="Not a SELECT query")
            return False

        # Blacklist dangerous keywords
        dangerous_keywords = [
            "drop", "delete", "update", "insert", "alter", "create",
            "truncate", "grant", "revoke", "exec", "execute",
            "sp_", "xp_", "--", "/*", "*/"
        ]

        for keyword in dangerous_keywords:
            if keyword in sql_lower:
                logger.warning("sql_validation_failed", reason=f"Dangerous keyword: {keyword}")
                return False

        return True

    async def _execute_sql(self, sql: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Execute SQL query safely

        Args:
            sql: SQL SELECT query
            db: Database session

        Returns:
            List of results as dictionaries
        """
        try:
            result = await db.execute(text(sql))
            rows = result.fetchall()

            # Convert to list of dicts
            if rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []

            logger.info("sql_executed_successfully", row_count=len(results))
            return results

        except Exception as e:
            logger.error("sql_execution_failed", sql=sql, error=str(e))
            return None

    async def _format_results(
        self,
        original_question: str,
        results: List[Dict[str, Any]],
        sql_query: str
    ) -> str:
        """
        Format SQL results in natural language (simplified, no LLM call for speed)

        Args:
            original_question: User's original question
            results: Query results
            sql_query: SQL query executed

        Returns:
            Formatted message in natural language
        """
        if not results:
            return "Je n'ai trouvé aucun résultat pour votre question."

        # Simple, fast formatting without LLM
        count = len(results)

        # Header
        message_parts = [f"✅ J'ai trouvé **{count}** résultat{'s' if count > 1 else ''}:\n"]

        # Show first 5 results with key information
        for i, row in enumerate(results[:5], 1):
            message_parts.append(f"\n**{i}.** ")

            # Try to find a meaningful identifier (name, title, subject, etc.)
            identifier = None
            for key in ['name', 'nom', 'title', 'subject', 'email']:
                if key in row and row[key]:
                    identifier = str(row[key])
                    break

            if identifier:
                message_parts.append(f"{identifier}")

            # Add other important fields
            important_fields = []
            for key, value in row.items():
                if key in ['name', 'nom', 'title', 'subject']:
                    continue  # Already shown as identifier
                if value is not None and str(value).strip():
                    # Limit field display
                    if len(important_fields) < 4:
                        important_fields.append(f"{key}: {value}")

            if important_fields:
                message_parts.append(f"\n   {', '.join(important_fields)}")

        # Show count if more results
        if count > 5:
            message_parts.append(f"\n\n_... et {count - 5} autre{'s' if count - 5 > 1 else ''} résultat{'s' if count - 5 > 1 else ''}_")

        return "".join(message_parts)

        # Note: Old LLM formatting removed for speed. If needed for complex cases,
        # can be re-enabled as an optional parameter.

        try:
            pass  # Keeping try-except structure for future use

        except Exception as e:
            logger.error("result_formatting_failed", error=str(e))
            # Fallback to simple formatting
            return f"J'ai trouvé {len(results)} résultat(s) pour votre question."
