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

# SECURITY: Whitelist of allowed views/tables - CANONICAL VIEWS for SQL agent isolation
ALLOWED_TABLES = [
    # Phase 1 canonical views (read-only, security hardened)
    'vw_professionnels_min',        # Professionnels (sans infos sensibles)
    'vw_professionnels_full',       # Professionnels (avec détails complets)
    'vw_coproprietaires_contact',   # Copropriétaires (contacts uniquement)
    'vw_emails_urgents',             # Emails urgents
    'vw_coproprietes_stats',         # Copropriétés (avec stats)
    'vw_documents_active',           # Documents actifs

    # Legacy raw tables (kept for backward compatibility, to be deprecated)
    'coproprietes',
    'coproprietaires',
    'professionnels',
    'emails',
    'documents',
    'professionnels_coproprietes'
]


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
        # Import here to avoid circular dependency
        from app.services.schema_introspection_service import get_schema_service
        self._schema_service = get_schema_service()
        logger.info("sql_agent_initialized")

    @property
    def schema(self) -> str:
        """
        Database schema for context - DYNAMICALLY GENERATED

        Note:
            Generated dynamically from SQLAlchemy models via SchemaIntrospectionService.
            Single source of truth: SQLAlchemy models + canonical views in migrations.

        Returns:
            Complete schema description (Markdown)
        """
        return self._schema_service.build_full_schema_description()

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

            logger.info("sql_generated", query=sql_query[:200], user_input=user_input[:100])

            # Step 2: Validate SQL (security check)
            is_valid, validation_error = self._validate_sql(sql_query)
            if not is_valid:
                logger.warning("sql_validation_failed", error=validation_error, sql=sql_query[:200])
                return {
                    "success": False,
                    "message": f"La requête générée n'est pas sûre: {validation_error}. Veuillez reformuler votre question.",
                    "sql_query": sql_query,
                    "debug": {
                        "validation_error": validation_error,
                        "user_input": user_input
                    }
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
        """Generate SQL query from natural language with comprehensive examples"""
        prompt = f"""
Tu es un expert SQL PostgreSQL avancé. Génère une requête SQL SELECT optimisée pour répondre à la question.

SCHÉMA DE BASE DE DONNÉES:
{self.schema}

RÈGLES CRITIQUES:
1. ✅ UNIQUEMENT des SELECT (jamais INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE)
2. ✅ Recherche NOMS/PRÉNOMS: TOUJOURS LOWER() et LIKE avec '%' pour gérer les variations
3. ✅ Recherche PERSONNES:
   - Professionnels → colonne 'name' (nom complet en un seul champ)
   - Copropriétaires → colonnes 'nom' et 'prenom' (séparés)
   - IMPORTANT: Les noms peuvent être dans n'importe quel ordre (Michel Bertrand OU Bertrand Michel)
4. ✅ Recherche MÉTIERS: table 'professionnels', colonne 'category'
5. ✅ JOINs: Utilise INNER JOIN pour données liées (évite les subqueries quand possible)
6. ✅ Limite: LIMIT 100 par défaut, SAUF si "tous" ou "combien" (agrégations)
7. ✅ Agrégations: Pour COUNT, SUM, AVG → pas de LIMIT, utilise GROUP BY si nécessaire
8. ✅ Relations:
   - coproprietaires.copropriete_id → coproprietes.id
   - professionnels_coproprietes: table de liaison pour Many-to-Many
9. ✅ Retourne UNIQUEMENT le SQL brut, sans explication, sans markdown, sans backticks

⚠️ INFORMATIONS NON DISPONIBLES (renvoyer vers RAG):
Ces données NE SONT PAS en base SQL, elles sont dans les documents:
- Prix, tarifs, coûts, honoraires
- Conditions de paiement, modalités contractuelles
- Devis, factures, montants financiers
- Documents, contrats, conditions générales
- Procédures, règlements, articles

Si la question porte sur ces sujets, retourne: ""

EXEMPLES CONCRETS PAR CATÉGORIE:

═══════════════════════════════════════════════════════════════════════
📋 RECHERCHE SIMPLE - PROFESSIONNELS (name en un seul champ)
═══════════════════════════════════════════════════════════════════════

Q: "qui est nadege moussu ?"
A: SELECT * FROM professionnels WHERE LOWER(name) LIKE '%nadege%' AND LOWER(name) LIKE '%moussu%' LIMIT 100

Q: "qui est Gregori Bonetto ?"
A: SELECT * FROM professionnels WHERE LOWER(name) LIKE '%gregori%' AND LOWER(name) LIKE '%bonetto%' LIMIT 100

Q: "connaissons nous des consultants ?"
A: SELECT * FROM professionnels WHERE LOWER(category) LIKE '%consultant%' LIMIT 100

Q: "liste des plombiers"
A: SELECT name, email, phone, city FROM professionnels WHERE LOWER(category) LIKE '%plombier%' LIMIT 100

Q: "email du plombier"
A: SELECT name, email, phone, category FROM professionnels WHERE LOWER(category) LIKE '%plombier%' LIMIT 100

═══════════════════════════════════════════════════════════════════════
👥 RECHERCHE SIMPLE - COPROPRIETAIRES (nom et prenom séparés)
═══════════════════════════════════════════════════════════════════════

Q: "Qui est Dupont Marie ?"
A: SELECT * FROM coproprietaires WHERE (LOWER(nom) LIKE '%dupont%' AND LOWER(prenom) LIKE '%marie%') OR (LOWER(nom) LIKE '%marie%' AND LOWER(prenom) LIKE '%dupont%') LIMIT 100

Q: "où vit Marie Dupont ?"
A: SELECT nom, prenom, adresse_postale, ville, numero_lot FROM coproprietaires WHERE (LOWER(prenom) LIKE '%marie%' AND LOWER(nom) LIKE '%dupont%') OR (LOWER(nom) LIKE '%marie%' AND LOWER(prenom) LIKE '%dupont%') LIMIT 100

Q: "qui est Michel Bertrand ?"
A: SELECT * FROM coproprietaires WHERE (LOWER(prenom) LIKE '%michel%' AND LOWER(nom) LIKE '%bertrand%') OR (LOWER(nom) LIKE '%michel%' AND LOWER(prenom) LIKE '%bertrand%') LIMIT 100

Q: "quel est l'email de Sophie Durant ?"
A: SELECT nom, prenom, email, telephone FROM coproprietaires WHERE (LOWER(prenom) LIKE '%sophie%' AND LOWER(nom) LIKE '%durant%') OR (LOWER(nom) LIKE '%sophie%' AND LOWER(prenom) LIKE '%durant%') LIMIT 100

═══════════════════════════════════════════════════════════════════════
🔗 JOINTURES (Relations entre tables)
═══════════════════════════════════════════════════════════════════════

Q: "copropriétaires des Mimosas"
A: SELECT c.nom, c.prenom, c.email, c.telephone, c.numero_lot, co.nom as copropriete FROM coproprietaires c INNER JOIN coproprietes co ON c.copropriete_id = co.id WHERE LOWER(co.nom) LIKE '%mimosas%' LIMIT 100

Q: "combien de copropriétaires dans Les Mimosas ?"
A: SELECT COUNT(*) as nombre_coproprietaires FROM coproprietaires c INNER JOIN coproprietes co ON c.copropriete_id = co.id WHERE LOWER(co.nom) LIKE '%mimosas%'

Q: "professionnels qui travaillent pour Les Mimosas"
A: SELECT p.name, p.email, p.phone, p.category FROM professionnels p INNER JOIN professionnels_coproprietes pc ON p.id = pc.professionnel_id INNER JOIN coproprietes co ON pc.copropriete_id = co.id WHERE LOWER(co.nom) LIKE '%mimosas%' LIMIT 100

═══════════════════════════════════════════════════════════════════════
🔢 AGRÉGATIONS (COUNT, SUM, AVG, GROUP BY)
═══════════════════════════════════════════════════════════════════════

Q: "combien de copropriétaires ?"
A: SELECT COUNT(*) as total FROM coproprietaires

Q: "combien de plombiers ?"
A: SELECT COUNT(*) as total FROM professionnels WHERE LOWER(category) LIKE '%plombier%'

Q: "nombre de copropriétaires par copropriété"
A: SELECT co.nom as copropriete, COUNT(c.id) as nombre_coproprietaires FROM coproprietes co LEFT JOIN coproprietaires c ON co.id = c.copropriete_id GROUP BY co.nom ORDER BY nombre_coproprietaires DESC

Q: "nombre de professionnels par catégorie"
A: SELECT category, COUNT(*) as nombre FROM professionnels GROUP BY category ORDER BY nombre DESC

Q: "combien de copropriétés ?"
A: SELECT COUNT(*) as total FROM coproprietes

═══════════════════════════════════════════════════════════════════════
🔍 VÉRIFICATION DE PRÉSENCE
═══════════════════════════════════════════════════════════════════════

Q: "dans la table professionnels, y a t-il Gregori Bonetto ?"
A: SELECT * FROM professionnels WHERE LOWER(name) LIKE '%gregori%' AND LOWER(name) LIKE '%bonetto%' LIMIT 100

Q: "est-ce que Michel Bertrand est un copropriétaire ?"
A: SELECT * FROM coproprietaires WHERE (LOWER(prenom) LIKE '%michel%' AND LOWER(nom) LIKE '%bertrand%') OR (LOWER(nom) LIKE '%michel%' AND LOWER(prenom) LIKE '%bertrand%') LIMIT 100

═══════════════════════════════════════════════════════════════════════
❌ QUESTIONS NON-SQL (Renvoyer vers RAG - retourner "")
═══════════════════════════════════════════════════════════════════════

Q: "combien coute le plombier ?"
A:

Q: "quel est le tarif du jardinier ?"
A:

Q: "conditions de paiement du syndic ?"
A:

Q: "que dit le contrat de plomberie ?"
A:

QUESTION DE L'UTILISATEUR:
{user_input}

GÉNÈRE LE SQL (retourne UNIQUEMENT la requête SQL, rien d'autre):
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

    def _validate_sql(self, sql: str) -> tuple[bool, str]:
        """
        Validate SQL query for security

        Checks:
        - Only SELECT statements allowed
        - No dangerous keywords (DROP, DELETE, UPDATE, INSERT, etc.)
        - Only allowed tables can be queried (WHITELIST)
        - No SQL injection patterns

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        import re
        sql_lower = sql.lower()

        # Must start with SELECT
        if not sql_lower.strip().startswith("select"):
            return (False, "Seules les requêtes SELECT sont autorisées")

        # Whitelist: Safe business keywords that might contain dangerous substrings
        # Example: "prix" shouldn't trigger "update" in "prix_updated_at"
        safe_business_keywords = [
            'prix', 'tarif', 'coût', 'montant', 'facture', 'honoraire',  # Business terms
            'updated_at', 'created_at', 'deleted_at', 'date_update',      # Common columns
            'last_update', 'update_time', 'next_update'                   # Timestamp columns
        ]

        # Blacklist dangerous keywords using WORD BOUNDARIES (not substrings!)
        # This prevents false positives like "updated_at" triggering "update"
        dangerous_patterns = [
            r'\bdrop\b', r'\bdelete\b', r'\bupdate\b', r'\binsert\b',
            r'\balter\b', r'\bcreate\b', r'\btruncate\b', r'\bgrant\b',
            r'\brevoke\b', r'\bexec\b', r'\bexecute\b',
            r'\bsp_', r'\bxp_',
            r'--', r'/\*', r'\*/'
        ]

        # Check for dangerous patterns
        for pattern in dangerous_patterns:
            matches = re.finditer(pattern, sql_lower)
            for match in matches:
                # Get the matched keyword
                matched_keyword = match.group(0)

                # Check if this is part of a safe business keyword
                # Look at surrounding context (10 chars before and after)
                start = max(0, match.start() - 10)
                end = min(len(sql_lower), match.end() + 10)
                context = sql_lower[start:end]

                # If any safe keyword is in the context, skip this match
                is_safe = any(safe_word in context for safe_word in safe_business_keywords)

                if not is_safe:
                    return (False, f"Mot-clé dangereux détecté: {matched_keyword.strip()}")

        # SECURITY: Whitelist table validation
        # Extract table names from SQL (improved parsing)
        import re
        table_patterns = [
            r'\bfrom\s+(\w+)',        # FROM clause
            r'\bjoin\s+(\w+)',        # JOIN clause
            r'\binto\s+(\w+)',        # INTO clause
            r'\bupdate\s+(\w+)',      # UPDATE clause
            r'\btable\s+(\w+)',       # TABLE keyword
        ]

        found_tables = set()
        for pattern in table_patterns:
            matches = re.findall(pattern, sql_lower, re.IGNORECASE)
            found_tables.update(matches)

        # Also check for table names directly (case-insensitive)
        for allowed_table in ALLOWED_TABLES:
            if allowed_table.lower() in sql_lower:
                found_tables.add(allowed_table)

        # If no tables found but query looks valid, log warning but don't fail
        if not found_tables and sql_lower.strip().startswith('select'):
            logger.warning("no_tables_detected_in_sql", sql=sql_lower[:100])
            # Don't fail - might be a simple SELECT with no FROM clause
            return (True, "")

        # Check if all found tables are in whitelist
        for table in found_tables:
            if table not in ALLOWED_TABLES:
                return (False, f"Table non autorisée: '{table}'. Tables autorisées: {', '.join(ALLOWED_TABLES)}")

        logger.info("sql_validated", tables_used=list(found_tables))
        return (True, "")

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
        Format SQL results as a Markdown table for better readability with intelligent suggestions

        Args:
            original_question: User's original question
            results: Query results
            sql_query: SQL query executed

        Returns:
            Formatted message with Markdown table
        """
        if not results:
            question_lower = original_question.lower()

            # Check if query was about pricing/financial info
            pricing_keywords = ["prix", "tarif", "coût", "combien coût", "combien coute",
                              "facture", "honoraire", "devis", "montant", "payer", "paiement"]
            if any(word in question_lower for word in pricing_keywords):
                return (
                    "❌ **Aucun résultat trouvé dans la base de données**\n\n"
                    "💡 **Suggestion**: Les informations **tarifaires et financières** ne sont **pas stockées dans la base de données**. "
                    "Elles se trouvent dans les **documents contractuels** (contrats, devis, factures).\n\n"
                    "**Essayez plutôt**: \n"
                    "- _\"Cherche dans les documents: tarif plombier\"_\n"
                    "- _\"Que dit le contrat sur les prix ?\"_\n"
                    "- _\"De quoi parle le devis ?\"_\n\n"
                    "Uploadez vos documents dans le panneau de droite si ce n'est pas déjà fait."
                )

            # Check if query was about person lookup
            person_keywords = ["qui est", "qui", "email", "téléphone", "telephone", "phone", "contact", "adresse"]
            if any(word in question_lower for word in person_keywords):
                return (
                    "❌ **Aucun résultat trouvé**\n\n"
                    "💡 **Suggestions**: \n"
                    "1. Vérifiez l'**orthographe** du nom (les noms peuvent être dans l'ordre inverse)\n"
                    "2. Essayez avec **juste le nom de famille**: _\"qui est Dupont ?\"_\n"
                    "3. Cherchez par **métier**: _\"liste des plombiers\"_\n"
                    "4. Utilisez des **termes partiels**: _\"nom contenant Dupon\"_ (sans 't')\n\n"
                    f"**Requête exécutée**: `{sql_query}`"
                )

            # Check if query was about count/statistics
            count_keywords = ["combien", "nombre", "total", "statistique"]
            if any(word in question_lower for word in count_keywords):
                return (
                    "❌ **Aucun résultat trouvé**\n\n"
                    "💡 **Suggestion**: La table interrogée est peut-être **vide** ou le **filtre est trop restrictif**.\n\n"
                    "**Essayez**: \n"
                    "- _\"combien de copropriétaires ?\"_ (sans filtre)\n"
                    "- _\"combien de professionnels ?\"_\n"
                    "- _\"nombre de copropriétés ?\"_\n\n"
                    f"**Requête exécutée**: `{sql_query}`"
                )

            # Generic no results message
            return (
                "❌ **Aucun résultat trouvé dans la base de données**\n\n"
                "💡 **Suggestions**: \n"
                "1. Vérifiez l'**orthographe** et les **termes de recherche**\n"
                "2. Essayez des **requêtes plus larges** (moins de filtres)\n"
                "3. Les **informations contractuelles** (prix, conditions) sont dans les **documents**, pas en base\n\n"
                f"**Requête exécutée**: `{sql_query}`"
            )

        count = len(results)

        # Determine which columns to display (max 6 columns for readability)
        first_row = results[0]
        all_columns = list(first_row.keys())

        # Prioritize important columns
        priority_columns = ['id', 'nom', 'prenom', 'name', 'email', 'telephone',
                           'phone', 'subject', 'ville', 'city', 'adresse', 'address',
                           'numero_lot', 'type_lot', 'category', 'urgency', 'statut']

        # Select columns: prioritize important ones, then others
        selected_columns = []
        for col in priority_columns:
            if col in all_columns and col not in selected_columns:
                selected_columns.append(col)
                if len(selected_columns) >= 6:
                    break

        # Add remaining columns if we have less than 6
        for col in all_columns:
            if col not in selected_columns:
                selected_columns.append(col)
                if len(selected_columns) >= 6:
                    break

        # Build header
        message_parts = [f"✅ **{count}** résultat{'s' if count > 1 else ''} trouvé{'s' if count > 1 else ''}\n\n"]

        # Build Markdown table
        # Header row
        header = "| " + " | ".join(selected_columns) + " |"
        message_parts.append(header + "\n")

        # Separator row
        separator = "|" + "|".join([" --- " for _ in selected_columns]) + "|"
        message_parts.append(separator + "\n")

        # Data rows (show max 10 rows)
        max_display = min(10, count)
        for row in results[:max_display]:
            row_values = []
            for col in selected_columns:
                value = row.get(col, '')
                # Format value for display
                if value is None:
                    formatted_value = '-'
                elif isinstance(value, str):
                    # Truncate long strings
                    formatted_value = value[:50] + '...' if len(value) > 50 else value
                else:
                    formatted_value = str(value)
                row_values.append(formatted_value)

            message_parts.append("| " + " | ".join(row_values) + " |\n")

        # Add footer if more results exist
        if count > max_display:
            message_parts.append(f"\n_... et {count - max_display} autre{'s' if count - max_display > 1 else ''} résultat{'s' if count - max_display > 1 else ''}_")

        return "".join(message_parts)
