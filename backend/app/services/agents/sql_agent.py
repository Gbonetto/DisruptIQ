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

# SECURITY: Whitelist of allowed tables to prevent SQL injection
ALLOWED_TABLES = [
    'coproprietes',
    'coproprietaires',
    'professionnels',
    'emails',
    'documents',
    'professionnels_coproprietes'  # Junction table
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
   - annee_construction: Integer (année de construction ex: 1985, 1920)
   - syndic: String (nom du syndic)
   - contact_syndic: String
   - reference_syndic: String
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

    async def process(
        self,
        user_input: str,
        db: AsyncSession,
        thought_stream=None,
        conversation_history: list = None,
        last_sql_context: dict = None
    ) -> Dict[str, Any]:
        """
        Process natural language query and execute SQL

        Args:
            user_input: User's question in natural language
            db: Database session
            thought_stream: Optional ThoughtStream for CoT display
            conversation_history: Recent conversation for context resolution
            last_sql_context: Previous SQL results for pronoun resolution (e.g., "leur", "ses")

        Returns:
            Dict with success, message, data, sql_query
        """
        # Import here to avoid circular imports
        from app.services.agents.thought_stream import ThoughtType

        try:
            # Step 0: Resolve contextual references ("leur mail", "ses coordonnées")
            enriched_input = await self._resolve_contextual_references(
                user_input,
                conversation_history,
                last_sql_context
            )

            # Step 1: Generate SQL query
            sql_query = await self._generate_sql(enriched_input)

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

            # Emit thought with SQL query for CoT display
            if thought_stream:
                # Extract tables from query for display
                tables_in_query = [t for t in ALLOWED_TABLES if t.lower() in sql_query.lower()]
                await thought_stream.add_thought(
                    ThoughtType.SQL_EXECUTING,
                    title="Exécution de la requête SQL",
                    content=f"Interrogation des tables : {', '.join(tables_in_query) if tables_in_query else 'base de données'}",
                    agent="sql_agent",
                    data={
                        "query": sql_query,
                        "tables": tables_in_query
                    },
                    progress=0.6
                )

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

            # Step 5: Prepare structured table data for DataTable component
            table_data = None
            if results:
                # Determine which columns to display (max 10 columns for table view)
                first_row = results[0]
                all_columns = list(first_row.keys())

                # Prioritize important columns
                priority_columns = ['id', 'nom', 'prenom', 'name', 'email', 'telephone',
                                   'phone', 'telephone_mobile', 'subject', 'ville', 'city',
                                   'adresse', 'address', 'numero_lot', 'type_lot', 'category',
                                   'urgency', 'statut', 'company_name', 'rating']

                # Select columns: prioritize important ones, then others
                selected_columns = []
                for col in priority_columns:
                    if col in all_columns and col not in selected_columns:
                        selected_columns.append(col)
                        if len(selected_columns) >= 10:
                            break

                # Add remaining columns if we have less than 10
                for col in all_columns:
                    if col not in selected_columns:
                        selected_columns.append(col)
                        if len(selected_columns) >= 10:
                            break

                # Build table data structure
                table_rows = []
                for row in results:
                    table_row = []
                    for col in selected_columns:
                        value = row.get(col, '')
                        # Format value for display
                        if value is None:
                            table_row.append('-')
                        else:
                            # Clean numeric artifacts from phone/postal_code fields
                            formatted_value = str(value)
                            if col in ['phone', 'telephone', 'telephone_mobile', 'postal_code', 'code_postal']:
                                # Remove .0 suffix from numeric strings
                                formatted_value = formatted_value.replace('.0', '')
                            table_row.append(formatted_value)
                    table_rows.append(table_row)

                table_data = {
                    "title": f"Résultats - {len(results)} ligne{'s' if len(results) > 1 else ''}",
                    "headers": selected_columns,
                    "rows": table_rows
                }

            # Extract table names from SQL query for source citations
            tables = self._extract_table_names(sql_query)

            return {
                "success": True,
                "message": formatted_message,
                "data": {
                    "results": results,
                    "row_count": len(results) if isinstance(results, list) else 0,
                    "sql_query": sql_query,
                    "table": table_data,  # Structured table data for DataTable component
                    "tables": tables  # Table names for source citations
                },
                "sql_query": sql_query,
                "tables": tables,  # Also at top level for easy access
                "confidence": 0.9
            }

        except Exception as e:
            logger.error("sql_agent_processing_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"Erreur lors du traitement: {str(e)}"
            }

    async def _generate_sql(self, user_input: str) -> str:
        """Generate SQL query from natural language with few-shot examples"""
        prompt = f"""
Tu es un expert SQL PostgreSQL. Génère une requête SQL SELECT UNIQUEMENT pour répondre à la question.

SCHÉMA DE BASE DE DONNÉES:
{self.schema}

RÈGLES IMPORTANTES:
1. Utilise UNIQUEMENT des SELECT (pas INSERT, UPDATE, DELETE, DROP)
2. ⚠️ CRITIQUE: Pour TOUTES les comparaisons de texte (=, LIKE, IN, etc.), utilise TOUJOURS unaccent(LOWER())
   - Exemple LIKE: WHERE unaccent(LOWER(nom)) LIKE unaccent(LOWER('%dupont%'))
   - Exemple = : WHERE unaccent(LOWER(co.nom)) = unaccent(LOWER('Résidence des Jardins'))
   - Exemple IN : WHERE unaccent(LOWER(category)) IN (unaccent(LOWER('plombier')), unaccent(LOWER('chauffagiste')))
   - Cela permet de chercher sans tenir compte des accents (résidence = residence, José = Jose)
3. ⚠️ CRITIQUE - RECHERCHE DE PERSONNE PAR NOM:
   - TOUJOURS utiliser UNION ALL pour chercher dans TOUTES les tables de personnes
   - Chercher dans 'professionnels' (colonne name) ET 'coproprietaires' (colonnes nom, prenom)
   - Format OBLIGATOIRE pour "qui est X" ou "email de X":
     SELECT 'professionnel' as source_type, id, name, company_name, email, phone, category, city
     FROM professionnels WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%nom%'))
     UNION ALL
     SELECT 'coproprietaire' as source_type, id, CONCAT(prenom, ' ', nom) as name, NULL as company_name, email, telephone as phone, 'copropriétaire' as category, NULL as city
     FROM coproprietaires WHERE unaccent(LOWER(nom)) LIKE unaccent(LOWER('%nom%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%nom%'))
   - Gère les titres: "M. Dupont", "Mme Dupont" → retire "M.", "Mme", "Mr" avant de chercher
4. ⚠️ CRITIQUE - RECHERCHE PAR NOM D'ENTREPRISE:
   - Pour chercher une ENTREPRISE, chercher dans 'professionnels' colonnes 'name' ET 'company_name'
   - Exemple: "email d'électricité plus" → WHERE unaccent(LOWER(company_name)) LIKE unaccent(LOWER('%electricite plus%')) OR unaccent(LOWER(name)) LIKE unaccent(LOWER('%electricite plus%'))
5. Pour chercher un MÉTIER/CATÉGORIE: utilise table 'professionnels' colonne 'category'
6. Pour comparer des DATES/ANNÉES:
   - "avant 2000" → WHERE annee_construction < 2000
   - "après 1990" → WHERE annee_construction > 1990
   - "en 2000" → WHERE annee_construction = 2000
7. Utilise des JOINs appropriés si nécessaire
8. Dans les SUBQUERIES aussi: utilise toujours unaccent(LOWER()) pour les comparaisons de texte
9. Limite les résultats à 100 rows (LIMIT 100), SAUF si demandé explicitement "tous"
10. Retourne UNIQUEMENT le SQL, sans explication, sans markdown

⚠️ INFORMATIONS NON DISPONIBLES EN BASE DE DONNÉES:
Les informations suivantes NE SONT PAS stockées dans la base et ne peuvent PAS être interrogées avec SQL:
- Prix, tarifs, coûts, honoraires des professionnels
- Conditions de paiement, modalités contractuelles
- Devis, factures, montants financiers
- Documents, contrats, conditions générales

Si la question porte sur ces sujets, retourne une requête SQL vide ou indique que ces informations ne sont pas en base.

EXEMPLES CONCRETS:

⚠️ RECHERCHE DE PERSONNE (TOUJOURS utiliser UNION ALL pour chercher dans toutes les tables):
Q: "qui est fafa moussu ?"
A: SELECT 'professionnel' as source_type, id, name, company_name, email, phone, category, city FROM professionnels WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%fafa%')) AND unaccent(LOWER(name)) LIKE unaccent(LOWER('%moussu%')) UNION ALL SELECT 'coproprietaire' as source_type, id, CONCAT(prenom, ' ', nom) as name, NULL as company_name, email, telephone as phone, 'copropriétaire' as category, NULL as city FROM coproprietaires WHERE (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%fafa%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%fafa%'))) AND (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%moussu%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%moussu%'))) LIMIT 100

Q: "qui est nadege moussu ?"
A: SELECT 'professionnel' as source_type, id, name, company_name, email, phone, category, city FROM professionnels WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%nadege%')) AND unaccent(LOWER(name)) LIKE unaccent(LOWER('%moussu%')) UNION ALL SELECT 'coproprietaire' as source_type, id, CONCAT(prenom, ' ', nom) as name, NULL as company_name, email, telephone as phone, 'copropriétaire' as category, NULL as city FROM coproprietaires WHERE (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%nadege%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%nadege%'))) AND (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%moussu%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%moussu%'))) LIMIT 100

Q: "quel est le mail de fafa moussu ?"
A: SELECT 'professionnel' as source_type, name, email, phone FROM professionnels WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%fafa%')) AND unaccent(LOWER(name)) LIKE unaccent(LOWER('%moussu%')) UNION ALL SELECT 'coproprietaire' as source_type, CONCAT(prenom, ' ', nom) as name, email, telephone as phone FROM coproprietaires WHERE (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%fafa%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%fafa%'))) AND (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%moussu%')) OR unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%moussu%'))) LIMIT 100

Q: "coordonnées de Jean Dupont"
A: SELECT 'professionnel' as source_type, name, company_name, email, phone, address, city FROM professionnels WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%jean%')) AND unaccent(LOWER(name)) LIKE unaccent(LOWER('%dupont%')) UNION ALL SELECT 'coproprietaire' as source_type, CONCAT(prenom, ' ', nom) as name, NULL as company_name, email, telephone as phone, NULL as address, NULL as city FROM coproprietaires WHERE (unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%jean%')) AND unaccent(LOWER(nom)) LIKE unaccent(LOWER('%dupont%'))) OR (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%jean%')) AND unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%dupont%'))) LIMIT 100

⚠️ RECHERCHE PAR NOM D'ENTREPRISE (chercher dans name ET company_name):
Q: "donne moi le mail d'electricite plus"
A: SELECT name, company_name, email, phone FROM professionnels WHERE unaccent(LOWER(company_name)) LIKE unaccent(LOWER('%electricite plus%')) OR unaccent(LOWER(name)) LIKE unaccent(LOWER('%electricite plus%')) LIMIT 100

Q: "contact de Plomberie Express"
A: SELECT name, company_name, email, phone, address, city FROM professionnels WHERE unaccent(LOWER(company_name)) LIKE unaccent(LOWER('%plomberie express%')) OR unaccent(LOWER(name)) LIKE unaccent(LOWER('%plomberie express%')) LIMIT 100

Q: "email de jardins sud"
A: SELECT name, company_name, email, phone FROM professionnels WHERE unaccent(LOWER(company_name)) LIKE unaccent(LOWER('%jardins sud%')) OR unaccent(LOWER(name)) LIKE unaccent(LOWER('%jardins sud%')) LIMIT 100

PROFESSIONNELS PAR CATÉGORIE/MÉTIER:
Q: "connaissons nous des consultants ?"
A: SELECT * FROM professionnels WHERE unaccent(LOWER(category)) LIKE unaccent(LOWER('%consultant%')) LIMIT 100

Q: "liste des plombiers"
A: SELECT name, company_name, email, phone, city FROM professionnels WHERE unaccent(LOWER(category)) LIKE unaccent(LOWER('%plombier%')) LIMIT 100

Q: "donne moi le mail d'un jardinier"
A: SELECT name, company_name, email, phone FROM professionnels WHERE unaccent(LOWER(category)) LIKE unaccent(LOWER('%jardinier%')) LIMIT 100

COPROPRIETAIRES (nom et prenom séparés - TRÈS IMPORTANT):
Q: "Qui est Dupont Marie ?"
A: SELECT * FROM coproprietaires WHERE unaccent(LOWER(nom)) LIKE unaccent(LOWER('%dupont%')) AND unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%marie%')) LIMIT 100

Q: "où vit Marie Dupont ?"
A: SELECT nom, prenom, adresse_postale, ville, numero_lot FROM coproprietaires WHERE unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%marie%')) AND unaccent(LOWER(nom)) LIKE unaccent(LOWER('%dupont%')) LIMIT 100

Q: "qui est Michel Bertrand ?"
A: SELECT * FROM coproprietaires WHERE (unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%michel%')) AND unaccent(LOWER(nom)) LIKE unaccent(LOWER('%bertrand%'))) OR (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%michel%')) AND unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%bertrand%'))) LIMIT 100

Q: "quel est l'email de Sophie Durant ?"
A: SELECT nom, prenom, email, telephone FROM coproprietaires WHERE (unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%sophie%')) AND unaccent(LOWER(nom)) LIKE unaccent(LOWER('%durant%'))) OR (unaccent(LOWER(nom)) LIKE unaccent(LOWER('%sophie%')) AND unaccent(LOWER(prenom)) LIKE unaccent(LOWER('%durant%'))) LIMIT 100

COPROPRIETES:
Q: "copropriétaires des Mimosas"
A: SELECT c.nom, c.prenom, c.email, c.telephone, c.numero_lot FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%mimosas%')) LIMIT 100

Q: "liste tous les copropriétaires de Arc-en-Ciel avec leurs emails"
A: SELECT c.nom, c.prenom, c.email, c.telephone, c.numero_lot, c.etage FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc-en-ciel%')) OR unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc en ciel%')) LIMIT 100

Q: "combien de copropriétaires dans la résidence Arc-en-Ciel"
A: SELECT COUNT(*) as nombre_coproprietaires FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc-en-ciel%')) OR unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc en ciel%'))

Q: "copropriétés construites avant 2000"
A: SELECT * FROM coproprietes WHERE annee_construction < 2000 LIMIT 100

Q: "copropriétaires habitant dans des copropriétés construites avant 2000"
A: SELECT c.nom, c.prenom, c.email, co.nom as copropriete_nom, co.annee_construction FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE co.annee_construction < 2000 LIMIT 100

SUBQUERIES COMPLEXES (ATTENTION: utilise unaccent() dans les subqueries aussi):
Q: "copropriétaires ayant le même syndic que la résidence des jardins"
A: SELECT c.nom, c.prenom, c.email, co.nom as copropriete_nom FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.syndic)) = (SELECT unaccent(LOWER(syndic)) FROM coproprietes WHERE unaccent(LOWER(nom)) LIKE unaccent(LOWER('%residence%')) AND unaccent(LOWER(nom)) LIKE unaccent(LOWER('%jardins%')) LIMIT 1) LIMIT 100

Q: "syndic de la copropriété où vit Marie Dubois"
A: SELECT DISTINCT co.syndic, co.contact_syndic FROM coproprietes co JOIN coproprietaires c ON c.copropriete_id = co.id WHERE unaccent(LOWER(c.prenom)) LIKE unaccent(LOWER('%marie%')) AND unaccent(LOWER(c.nom)) LIKE unaccent(LOWER('%dubois%')) LIMIT 100

COLONNES CALCULÉES (tantièmes, pourcentages, totaux):
Q: "liste des copropriétaires Arc-en-Ciel avec leurs tantièmes"
A: SELECT c.nom, c.prenom, c.email, c.numero_lot, c.surface, ROUND(c.surface * 1000.0 / (SELECT SUM(c2.surface) FROM coproprietaires c2 WHERE c2.copropriete_id = c.copropriete_id), 2) as tantiemes FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc-en-ciel%')) ORDER BY tantiemes DESC LIMIT 100

Q: "calcule le quorum pour l'AG de Arc-en-Ciel"
A: SELECT COUNT(*) as nb_coproprietaires, SUM(c.surface) as surface_totale, ROUND(SUM(c.surface) / 2, 2) as quorum_surface_50pct, ROUND(COUNT(*) / 2.0, 0) as quorum_nb_50pct FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc-en-ciel%'))

Q: "surface totale et moyenne par copropriétaire de Arc-en-Ciel"
A: SELECT co.nom as copropriete, COUNT(c.id) as nb_coproprietaires, ROUND(SUM(c.surface), 2) as surface_totale_m2, ROUND(AVG(c.surface), 2) as surface_moyenne_m2 FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%arc-en-ciel%')) GROUP BY co.id, co.nom

VÉRIFICATION DE PRÉSENCE:
Q: "dans la table professionnels, y a t-il Gregori Bonetto ?"
A: SELECT * FROM professionnels WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%gregori%')) AND unaccent(LOWER(name)) LIKE unaccent(LOWER('%bonetto%')) LIMIT 100

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
        Format SQL results as a simple text message
        The table will be displayed using the DataTable component

        Args:
            original_question: User's original question
            results: Query results
            sql_query: SQL query executed

        Returns:
            Simple formatted message (table is in data.table)
        """
        if not results:
            # Check if query was about pricing/tarif
            pricing_keywords = ["prix", "tarif", "coût", "combien", "facture", "honoraire"]
            if any(word in original_question.lower() for word in pricing_keywords):
                return ("Je n'ai trouvé aucun résultat dans la base de données.\n\n"
                       "💡 **Astuce**: Les informations tarifaires sont souvent dans les contrats et documents. "
                       "Essayez de rechercher dans les documents uploadés avec: `Cherche dans les documents: tarif plombier`")
            return "Je n'ai trouvé aucun résultat pour votre question."

        count = len(results)
        question_lower = original_question.lower()

        # ================================================================
        # SPECIAL CASE: COUNT(*) queries - display the count value directly
        # ================================================================
        if count == 1 and len(results[0]) == 1:
            # Single row, single column = likely a COUNT query
            first_col = list(results[0].keys())[0]
            first_val = results[0][first_col]

            # Check if this is a COUNT result (column name contains 'count' or value is integer)
            if 'count' in first_col.lower() or (isinstance(first_val, (int, float)) and first_col in ['count', 'nb', 'total', 'nombre']):
                count_value = int(first_val) if first_val else 0

                # Detect what we're counting from the original question
                entity = "éléments"
                if "copropriétaire" in question_lower:
                    entity = "copropriétaires"
                elif "professionnel" in question_lower or "plombier" in question_lower or "électricien" in question_lower:
                    entity = "professionnels"
                elif "email" in question_lower or "mail" in question_lower:
                    entity = "emails"
                elif "document" in question_lower:
                    entity = "documents"
                elif "lot" in question_lower:
                    entity = "lots"
                elif "copropriété" in question_lower or "immeuble" in question_lower:
                    entity = "copropriétés"

                # Extract copropriété name if present
                copro_name = ""
                import re
                copro_match = re.search(r'(aux?|des?|chez|dans|pour)\s+(les?\s+)?([A-Z][a-zA-Zéèêëàâäîïôöùûüç]+)', original_question)
                if copro_match:
                    copro_name = f" aux {copro_match.group(3)}"

                return f"Il y a **{count_value} {entity}**{copro_name}."

        # ================================================================
        # SPECIAL CASE: Single scalar value (SUM, AVG, etc.)
        # ================================================================
        if count == 1 and len(results[0]) == 1:
            first_col = list(results[0].keys())[0]
            first_val = results[0][first_col]

            if first_val is not None:
                # Format numbers nicely
                if isinstance(first_val, float):
                    return f"Le résultat est **{first_val:,.2f}**."
                elif isinstance(first_val, int):
                    return f"Le résultat est **{first_val:,}**."
                else:
                    return f"Le résultat est : **{first_val}**"

        # ================================================================
        # SPECIAL CASE: Quorum calculation - add explanatory context
        # ================================================================
        if any(kw in question_lower for kw in ["quorum", "assemblée générale", "ag "]):
            return await self._format_quorum_response(original_question, results)

        # ================================================================
        # SPECIAL CASE: Tantièmes calculation - add explanatory context
        # ================================================================
        if any(kw in question_lower for kw in ["tantième", "tantiemes", "millième"]):
            return await self._format_tantiemes_response(original_question, results)

        # Generate human-readable response from SQL results
        response_parts = [f"✅ J'ai trouvé **{count}** résultat{'s' if count > 1 else ''} dans la base de données.\n"]

        # Format top results (max 3 for readability)
        for i, row in enumerate(results[:3], 1):
            # Build a descriptive line based on available columns
            details = []

            # Name handling (different column names possible)
            name = row.get('name') or f"{row.get('prenom', '')} {row.get('nom', '')}".strip()
            if name:
                details.append(f"**{name}**")

            # Company/category
            if row.get('company_name'):
                details.append(f"({row['company_name']})")
            if row.get('category'):
                details.append(f"- {row['category']}")

            # Contact info
            contact_parts = []
            if row.get('email'):
                contact_parts.append(f"📧 {row['email']}")
            if row.get('phone') or row.get('telephone'):
                phone = row.get('phone') or row.get('telephone')
                contact_parts.append(f"📞 {str(phone).replace('.0', '')}")

            # Location
            location_parts = []
            if row.get('city') or row.get('ville'):
                location_parts.append(row.get('city') or row.get('ville'))
            if row.get('address') or row.get('adresse'):
                location_parts.append(row.get('address') or row.get('adresse'))

            # Build the line
            if details:
                line = " ".join(details)
                if contact_parts:
                    line += f"\n   {' | '.join(contact_parts)}"
                if location_parts:
                    line += f"\n   📍 {', '.join(location_parts)}"
                response_parts.append(f"\n{i}. {line}")

        if count > 3:
            response_parts.append(f"\n\n*... et {count - 3} autre(s) résultat(s) dans le tableau ci-dessous.*")

        return "".join(response_parts)

    def _extract_table_names(self, sql: str) -> List[str]:
        """
        Extract table names from SQL query for source citations

        Args:
            sql: SQL query

        Returns:
            List of table names found in query
        """
        import re
        sql_lower = sql.lower()

        table_patterns = [
            r'\bfrom\s+(\w+)',        # FROM clause
            r'\bjoin\s+(\w+)',        # JOIN clause (LEFT/RIGHT/INNER/OUTER JOIN)
        ]

        found_tables = set()
        for pattern in table_patterns:
            matches = re.findall(pattern, sql_lower, re.IGNORECASE)
            found_tables.update(matches)

        # Filter to only allowed tables and return as sorted list
        valid_tables = [t for t in found_tables if t in ALLOWED_TABLES]
        return sorted(valid_tables)

    async def _format_quorum_response(
        self,
        original_question: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Format quorum calculation with explanatory context

        Args:
            original_question: User's original question
            results: Query results with quorum data

        Returns:
            Formatted message with legal context
        """
        if not results:
            return "Je n'ai pas trouvé de données pour calculer le quorum."

        row = results[0]

        # Extract values from results
        nb_copros = row.get('nb_coproprietaires', row.get('count', 0))
        surface_totale = row.get('surface_totale', 0)
        quorum_surface = row.get('quorum_surface_50pct', surface_totale / 2 if surface_totale else 0)
        quorum_nb = row.get('quorum_nb_50pct', nb_copros / 2 if nb_copros else 0)

        response = f"""## 📊 Calcul du Quorum - Assemblée Générale

### Données de la copropriété
- **Nombre de copropriétaires:** {nb_copros}
- **Surface totale:** {surface_totale:.2f} m² (tantièmes totaux: 1000)

### Quorum requis (Article 25 loi du 10 juillet 1965)

**Pour une AG valide en première convocation:**
- ✅ **Minimum {int(quorum_nb)} copropriétaires** présents ou représentés
- ✅ **Minimum {quorum_surface:.2f} m²** de tantièmes représentés (50% de {surface_totale:.2f})

### 📋 Règles de majorité
| Type de décision | Majorité requise |
|-----------------|------------------|
| Décisions courantes (art. 24) | Majorité des voix présentes |
| Travaux importants (art. 25) | Majorité de tous les copropriétaires |
| Modifications règlement (art. 26) | Double majorité (2/3 des voix) |

💡 *Si le quorum n'est pas atteint, une 2ème AG peut être convoquée sans condition de quorum.*
"""
        return response

    async def _format_tantiemes_response(
        self,
        original_question: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Format tantièmes calculation with explanatory context

        Args:
            original_question: User's original question
            results: Query results with tantièmes data

        Returns:
            Formatted message with explanation
        """
        if not results:
            return "Je n'ai pas trouvé de données pour calculer les tantièmes."

        count = len(results)
        total_tantiemes = sum(float(r.get('tantiemes', 0)) for r in results if r.get('tantiemes'))

        response_parts = [
            f"""## 📊 Répartition des Tantièmes

**{count} copropriétaire{'s' if count > 1 else ''}** | Total tantièmes: **{total_tantiemes:.0f}/1000**

### Calcul des tantièmes
Les tantièmes sont calculés selon la formule:
`Tantièmes = (Surface du lot / Surface totale copropriété) × 1000`

### Top 5 des propriétaires par tantièmes
"""
        ]

        # Show top 5 by tantiemes
        sorted_results = sorted(results, key=lambda x: float(x.get('tantiemes', 0)), reverse=True)
        for i, row in enumerate(sorted_results[:5], 1):
            name = f"{row.get('prenom', '')} {row.get('nom', '')}".strip()
            lot = row.get('numero_lot', 'N/A')
            surface = row.get('surface', 0)
            tantiemes = row.get('tantiemes', 0)
            response_parts.append(f"| {i}. **{name}** | Lot {lot} | {surface}m² | **{tantiemes} tantièmes** |")

        if count > 5:
            response_parts.append(f"\n*... et {count - 5} autre(s) dans le tableau ci-dessous.*")

        response_parts.append("""
### 💡 Utilisation des tantièmes
- **Répartition des charges** communes
- **Droit de vote** en AG (1 tantième = 1 voix)
- **Quote-part** dans les parties communes
""")

        return "\n".join(response_parts)

    # ========================================================================
    # LIGHT MODE - NO LLM (for WorldClassRouter optimization)
    # ========================================================================

    # SQL Templates for common queries - NO LLM CALL
    SQL_TEMPLATES = {
        # Counting queries
        "count_coproprietaires": {
            "patterns": [
                r"combien\s+(?:de\s+)?copropri[ée]taires?\s+(?:y\s+a[- ]t[- ]il\s+)?(?:dans|aux?|chez|de|pour)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"nombre\s+(?:de\s+)?copropri[ée]taires?\s+(?:dans|aux?|chez|de|pour)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"copropri[ée]taires?\s+(?:des?|aux?)\s+(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
            ],
            "sql": """SELECT COUNT(*) as count FROM coproprietaires c
                      JOIN coproprietes co ON c.copropriete_id = co.id
                      WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%{entity}%'))""",
            "extract_group": 1
        },
        "count_lots": {
            "patterns": [
                r"combien\s+(?:de\s+)?lots?\s+(?:y\s+a[- ]t[- ]il\s+)?(?:dans|aux?|chez|de|pour)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"nombre\s+(?:de\s+)?lots?\s+(?:dans|aux?|chez|de|pour)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"lots?\s+(?:des?|aux?)\s+(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
            ],
            "sql": """SELECT nombre_lots as count FROM coproprietes
                      WHERE unaccent(LOWER(nom)) LIKE unaccent(LOWER('%{entity}%'))""",
            "extract_group": 1
        },
        "count_professionnels": {
            "patterns": [
                r"combien\s+(?:de\s+)?(plombiers?|[ée]lectriciens?|professionnels?|prestataires?|chauffagistes?|serruriers?|jardiniers?)",
                r"nombre\s+(?:de\s+)?(plombiers?|[ée]lectriciens?|professionnels?|prestataires?|chauffagistes?|serruriers?|jardiniers?)",
            ],
            "sql": """SELECT COUNT(*) as count FROM professionnels
                      WHERE unaccent(LOWER(category)) LIKE unaccent(LOWER('%{entity}%'))""",
            "extract_group": 1
        },
        # List queries
        "list_coproprietaires": {
            "patterns": [
                r"liste\s+(?:des?\s+)?copropri[ée]taires?\s+(?:de|aux?|chez|pour)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"copropri[ée]taires?\s+(?:de|aux?|chez)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"qui\s+(?:habite|vit|est)\s+(?:aux?|dans|chez)\s+(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
            ],
            "sql": """SELECT c.nom, c.prenom, c.email, c.telephone, c.numero_lot
                      FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id
                      WHERE unaccent(LOWER(co.nom)) LIKE unaccent(LOWER('%{entity}%'))
                      LIMIT {limit}""",
            "extract_group": 1
        },
        "list_professionnels": {
            "patterns": [
                r"liste\s+(?:des?\s+)?(plombiers?|[ée]lectriciens?|chauffagistes?|serruriers?|jardiniers?|professionnels?|menuisiers?|ma[çc]ons?|peintres?)",
                r"(plombiers?|[ée]lectriciens?|chauffagistes?|serruriers?|jardiniers?|menuisiers?|ma[çc]ons?|peintres?)\s+disponibles?",
                r"(?:donne|trouve)[- ]moi\s+(?:un|des|les)\s+(plombiers?|[ée]lectriciens?|professionnels?|chauffagistes?|serruriers?)",
                r"nos?\s+(plombiers?|[ée]lectriciens?|chauffagistes?|serruriers?|jardiniers?)",
            ],
            "sql": """SELECT name, company_name, email, phone, city, rating
                      FROM professionnels
                      WHERE unaccent(LOWER(category)) LIKE unaccent(LOWER('%{entity}%'))
                      AND statut = 'active'
                      ORDER BY rating DESC NULLS LAST
                      LIMIT {limit}""",
            "extract_group": 1
        },
        # Who is queries
        "who_is_person": {
            "patterns": [
                r"qui\s+est\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                r"c'est\s+qui\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                r"connais[- ]tu\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                r"contact\s+(?:de|du)\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                r"email\s+(?:de|du)\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                # Patterns coordonnées
                r"(?:donne|donnes|donne[- ]moi)\s+(?:les?\s+)?coordonn[ée]es\s+(?:de|du)\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                r"(?:quelles?\s+)?(?:sont\s+)?les?\s+coordonn[ée]es\s+(?:de|du)\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
                r"coordonn[ée]es\s+(?:de|du)\s+([A-ZÀ-Ÿa-zà-ÿ]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ]+)*)",
            ],
            "sql": """SELECT 'professionnel' as type_personne, name as nom_complet, company_name as entreprise_ou_copro,
                             email, phone as telephone, category as role_ou_statut, city as ville
                      FROM professionnels
                      WHERE unaccent(LOWER(name)) LIKE unaccent(LOWER('%{entity}%'))
                         OR unaccent(LOWER(company_name)) LIKE unaccent(LOWER('%{entity}%'))
                      UNION ALL
                      SELECT 'copropriétaire' as type_personne, CONCAT(c.prenom, ' ', c.nom) as nom_complet,
                             co.nom as entreprise_ou_copro, c.email, c.telephone,
                             COALESCE(c.statut_special, c.statut) as role_ou_statut, co.ville
                      FROM coproprietaires c
                      JOIN coproprietes co ON c.copropriete_id = co.id
                      WHERE unaccent(LOWER(CONCAT(c.prenom, ' ', c.nom))) LIKE unaccent(LOWER('%{entity}%'))
                         OR unaccent(LOWER(c.nom)) LIKE unaccent(LOWER('%{entity}%'))
                         OR unaccent(LOWER(c.prenom)) LIKE unaccent(LOWER('%{entity}%'))
                      LIMIT {limit}""",
            "extract_group": 1
        },
        # Lot queries
        "lot_info": {
            "patterns": [
                r"lot\s+(\d+[A-Za-z]?)",
                r"qui\s+(?:habite|vit|poss[èe]de)\s+(?:le\s+)?lot\s+(\d+[A-Za-z]?)",
                r"propri[ée]taire\s+(?:du\s+)?lot\s+(\d+[A-Za-z]?)",
            ],
            "sql": """SELECT c.nom, c.prenom, c.email, c.telephone, c.numero_lot,
                             c.type_lot, c.etage, c.surface, co.nom as copropriete
                      FROM coproprietaires c
                      JOIN coproprietes co ON c.copropriete_id = co.id
                      WHERE c.numero_lot = '{entity}'
                      LIMIT {limit}""",
            "extract_group": 1
        },
        # Copropriete info
        "copropriete_info": {
            "patterns": [
                r"(?:infos?|informations?)\s+(?:sur|de)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"parle[sz]?[- ]moi\s+(?:de|des?)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)",
                r"(?:la\s+)?copropri[ée]t[ée]?\s+(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿa-zà-ÿ\-]+)*)\s*[\?$]",
                r"o[uù]\s+(?:se\s+trouve|est\s+situ[ée]e?)\s+(?:la\s+)?(?:copropri[ée]t[ée]?\s+)?(?:les?\s+)?([A-ZÀ-Ÿa-zà-ÿ\-]+)",
            ],
            "sql": """SELECT * FROM coproprietes
                      WHERE unaccent(LOWER(nom)) LIKE unaccent(LOWER('%{entity}%'))
                      LIMIT {limit}""",
            "extract_group": 1
        },
        # Simple count of coproprietes
        "count_coproprietes": {
            "patterns": [
                r"combien\s+(?:de\s+)?copropri[ée]t[ée]s?\s*[\?]?$",
                r"nombre\s+(?:de\s+)?copropri[ée]t[ée]s?",
                r"(?:liste|toutes?)\s+(?:les?\s+)?copropri[ée]t[ée]s?",
            ],
            "sql": """SELECT COUNT(*) as count FROM coproprietes""",
            "extract_group": 0
        },
        # Présidents de copropriété
        "list_presidents": {
            "patterns": [
                r"(?:qui\s+sont|liste|quels?\s+sont)\s+(?:les?\s+)?pr[ée]sidents?",
                r"pr[ée]sidents?\s+(?:de\s+)?(?:copropri[ée]t[ée]|conseil)",
            ],
            "sql": """SELECT c.prenom, c.nom, c.email, c.telephone, co.nom as copropriete
                      FROM coproprietaires c
                      JOIN coproprietes co ON c.copropriete_id = co.id
                      WHERE c.statut_special = 'président' OR c.statut_special = 'president'
                      ORDER BY co.nom
                      LIMIT {limit}""",
            "extract_group": 0
        },
        # Locataires
        "list_locataires": {
            "patterns": [
                r"(?:qui\s+sont|liste|quels?\s+sont)\s+(?:les?\s+)?locataires?",
                r"locataires?\s+(?:de|des)\s+",
            ],
            "sql": """SELECT c.prenom, c.nom, c.email, c.telephone, co.nom as copropriete
                      FROM coproprietaires c
                      JOIN coproprietes co ON c.copropriete_id = co.id
                      WHERE c.statut = 'locataire'
                      ORDER BY co.nom
                      LIMIT {limit}""",
            "extract_group": 0
        },
        # Professionnels par nombre d'interventions
        "list_pro_by_jobs": {
            "patterns": [
                r"professionnels?\s+(?:avec\s+)?plus\s+de\s+(\d+)\s+interventions?",
                r"qui\s+(?:a|ont)\s+(?:fait|r[ée]alis[ée])\s+plus\s+de\s+(\d+)\s+interventions?",
            ],
            "sql": """SELECT name, company_name, category, email, phone, total_jobs, rating
                      FROM professionnels
                      WHERE total_jobs > {entity}
                      AND statut = 'active'
                      ORDER BY total_jobs DESC
                      LIMIT {limit}""",
            "extract_group": 1
        },
    }

    async def retrieve_light(
        self,
        query: str,
        db,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        LIGHT MODE retrieval - Uses SQL templates WITHOUT LLM call.

        This method is optimized for WorldClassRouter to reduce latency.
        It uses pattern matching to select the right SQL template.

        Args:
            query: User's question
            db: Database session
            limit: Max results

        Returns:
            List of documents with raw SQL results and metadata.
            Returns empty list if no template matches (fallback to full mode).
        """
        import re

        query_lower = query.lower()

        try:
            # Try each template
            for template_name, template_config in self.SQL_TEMPLATES.items():
                for pattern in template_config["patterns"]:
                    match = re.search(pattern, query_lower, re.IGNORECASE)
                    if match:
                        # Extract entity from the matched group
                        extract_idx = template_config.get("extract_group", -1)
                        groups = match.groups()

                        if groups:
                            if extract_idx == -1:
                                entity = groups[-1] if groups[-1] else ""
                            elif extract_idx < len(groups):
                                entity = groups[extract_idx] if groups[extract_idx] else ""
                            else:
                                entity = groups[-1] if groups[-1] else ""
                        else:
                            entity = ""

                        # Clean entity
                        entity = entity.strip().strip('"\'')

                        # Normalize profession names (remove French plural 's')
                        if template_name in ("list_professionnels", "count_professionnels"):
                            # Remove trailing 's' for plural professions to match singular category in DB
                            profession_roots = {
                                'plombiers': 'plombier',
                                'électriciens': 'électricien',
                                'electriciens': 'electricien',
                                'chauffagistes': 'chauffagiste',
                                'serruriers': 'serrurier',
                                'jardiniers': 'jardinier',
                                'menuisiers': 'menuisier',
                                'peintres': 'peintre',
                                'maçons': 'maçon',
                                'masons': 'macon',
                            }
                            entity_lower = entity.lower()
                            if entity_lower in profession_roots:
                                entity = profession_roots[entity_lower]

                        # Build SQL from template
                        sql = template_config["sql"].format(
                            entity=entity,
                            limit=limit
                        )

                        logger.info("sql_light_template_matched",
                                   template=template_name,
                                   entity=entity[:30],
                                   query=query[:50])

                        # Validate SQL
                        is_valid, error = self._validate_sql(sql)
                        if not is_valid:
                            logger.warning("sql_light_validation_failed",
                                         error=error, sql=sql[:100])
                            continue

                        # Execute SQL
                        results = await self._execute_sql(sql, db)

                        if results is None:
                            continue

                        # Format as document list for WorldClassRouter
                        documents = []

                        # Build content from results
                        if results:
                            # Format results in a clear, LLM-friendly format
                            tables_used = self._extract_table_names(sql)

                            # Build structured content with clear answer
                            content_lines = []
                            content_lines.append(f"✅ DONNÉES TROUVÉES: {len(results)} résultat(s)")
                            content_lines.append("")

                            for i, row in enumerate(results[:limit], 1):
                                # Format each row as a clear entity
                                row_lines = [f"**Résultat {i}:**"]
                                for key, value in row.items():
                                    if value is not None and str(value).strip():
                                        # Make key names more readable
                                        key_label = key.replace("_", " ").title()
                                        row_lines.append(f"  - {key_label}: {value}")
                                content_lines.append("\n".join(row_lines))
                                content_lines.append("")

                            content = "\n".join(content_lines)

                            documents.append({
                                "content": content,
                                "source": "sql",
                                "score": 0.95,  # High score for SQL facts
                                "metadata": {
                                    "template_used": template_name,
                                    "sql_query": sql,
                                    "row_count": len(results),
                                    "tables": tables_used,
                                    "raw_results": results,
                                    "is_factual": True  # Flag for synthesis to prioritize
                                }
                            })
                        else:
                            # No results but query was valid
                            documents.append({
                                "content": f"Aucun résultat trouvé dans la base de données pour: {entity}",
                                "source": "sql",
                                "score": 0.5,
                                "metadata": {
                                    "template_used": template_name,
                                    "sql_query": sql,
                                    "row_count": 0,
                                    "tables": self._extract_table_names(sql),
                                    "raw_results": []
                                }
                            })

                        return documents

            # No template matched - return empty (WorldClassRouter will skip SQL)
            logger.debug("sql_light_no_template_match", query=query[:50])
            return []

        except Exception as e:
            logger.error("sql_light_retrieval_failed", error=str(e), query=query[:50])
            return []

    # ========================================================================
    # CONTEXTUAL REFERENCE RESOLUTION
    # ========================================================================

    async def _resolve_contextual_references(
        self,
        user_input: str,
        conversation_history: list = None,
        last_sql_context: dict = None
    ) -> str:
        """
        Resolve contextual references like "leur mail", "ses coordonnées", etc.

        Examples:
        - "qui habite aux mimosas" → stores context
        - "donne moi leur mail" → resolves to "donne moi le mail des habitants des mimosas"

        Args:
            user_input: Current user query
            conversation_history: Recent conversation messages
            last_sql_context: Previous SQL query context (tables, entities found)

        Returns:
            Enriched query with resolved references
        """
        import re

        query_lower = user_input.lower()

        # Contextual reference patterns
        contextual_patterns = [
            (r'\bleur\b', 'plural possessive'),     # "leur mail", "leur adresse"
            (r'\bleurs\b', 'plural possessive'),    # "leurs coordonnées"
            (r'\bses\b', 'singular possessive'),    # "ses coordonnées"
            (r'\bson\b', 'singular possessive'),    # "son email"
            (r'\bsa\b', 'singular possessive'),     # "sa téléphone"
            (r'\bces\b', 'demonstrative plural'),   # "ces copropriétaires"
        ]

        # Check if query has contextual references
        has_contextual_ref = any(re.search(pattern, query_lower) for pattern, _ in contextual_patterns)

        if not has_contextual_ref:
            return user_input  # No resolution needed

        # Try to extract context from conversation history
        context_entity = None
        context_filter = None

        if conversation_history:
            # Look at recent messages (last 5)
            for msg in reversed(conversation_history[-5:]):
                content = msg.get("content", "").lower()

                # Extract copropriété mentions
                copro_patterns = [
                    r"(?:aux|des|de la|dans les?)\s+(?:copropriété\s+)?(?:les?\s+)?([a-zéèêëàâäîïôöùûüç\-]+(?:\s+[a-zéèêëàâäîïôöùûüç\-]+)*)",
                    r"(?:résidence|copropriété)\s+(?:les?\s+)?([a-zéèêëàâäîïôöùûüç\-]+)",
                    r"(?:habite|vit|réside)\s+(?:aux?|dans)\s+(?:les?\s+)?([a-zéèêëàâäîïôöùûüç\-]+)",
                ]

                for pattern in copro_patterns:
                    match = re.search(pattern, content)
                    if match:
                        context_entity = match.group(1).strip()
                        context_filter = "copropriete"
                        logger.info("context_resolved_from_history",
                                   entity=context_entity,
                                   filter_type=context_filter)
                        break

                if context_entity:
                    break

                # Extract professional category mentions
                prof_patterns = [
                    r"(?:les?|nos?|des?)\s+(plombiers?|électriciens?|jardiniers?|chauffagistes?)",
                    r"(plombiers?|électriciens?|jardiniers?|chauffagistes?)\s+(?:disponibles?|actifs?)",
                ]

                for pattern in prof_patterns:
                    match = re.search(pattern, content)
                    if match:
                        context_entity = match.group(1).strip()
                        context_filter = "professionnel_category"
                        logger.info("context_resolved_from_history",
                                   entity=context_entity,
                                   filter_type=context_filter)
                        break

                if context_entity:
                    break

        # Also check last_sql_context if available
        if not context_entity and last_sql_context:
            if "copropriete" in str(last_sql_context.get("tables", [])):
                # Extract copropriété name from previous results
                context_filter = "copropriete"
                context_entity = last_sql_context.get("entity_name")

        # If we found context, enrich the query
        if context_entity and context_filter:
            enriched_query = user_input

            if context_filter == "copropriete":
                # Replace "leur mail" with "le mail des copropriétaires de X"
                enriched_query = re.sub(
                    r'\bleur\s+(mail|email|adresse|coordonnées?|téléphone)',
                    f'le \\1 des copropriétaires de {context_entity}',
                    enriched_query,
                    flags=re.IGNORECASE
                )
                enriched_query = re.sub(
                    r'\bleurs\s+(mails?|emails?|adresses?|coordonnées?|téléphones?)',
                    f'les \\1 des copropriétaires de {context_entity}',
                    enriched_query,
                    flags=re.IGNORECASE
                )

            elif context_filter == "professionnel_category":
                # Replace "leur mail" with "le mail des {category}"
                enriched_query = re.sub(
                    r'\bleur\s+(mail|email|adresse|coordonnées?|téléphone)',
                    f'le \\1 des {context_entity}',
                    enriched_query,
                    flags=re.IGNORECASE
                )

            logger.info("query_enriched_with_context",
                       original=user_input[:50],
                       enriched=enriched_query[:50],
                       context_entity=context_entity)

            return enriched_query

        # No context found, return original
        logger.debug("no_context_found_for_reference", query=user_input[:50])
        return user_input
