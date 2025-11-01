"""
SQL Agent Service
Agent intelligent capable de traduire des requêtes en langage naturel en SQL
et d'exécuter des opérations sur la base de données de manière sécurisée.
"""

import structlog
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re
import json

from app.services.llm_service import LLMService
from app.core.config import settings

logger = structlog.get_logger()


class SQLAgentService:
    """
    Service intelligent pour convertir langage naturel → SQL

    Fonctionnalités:
    - Traduction NL → SQL avec LLM
    - Validation et sécurisation des requêtes
    - Exécution sécurisée avec limitations
    - Formatage intelligent des résultats
    """

    # Tables autorisées pour les requêtes
    ALLOWED_TABLES = {
        "professionnels", "coproprietes", "coproprietaires",
        "professionnels_coproprietes", "documents", "emails", "users"
    }

    # Opérations dangereuses interdites
    DANGEROUS_OPERATIONS = {
        "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"
    }

    # Limite de résultats
    MAX_RESULTS = 1000

    def __init__(self):
        self.llm_service = LLMService()

    def _build_schema_description(self) -> str:
        """
        Construit une description complète du schéma BDD pour le LLM

        Returns:
            Description texte du schéma
        """
        schema = """
# SCHÉMA DE LA BASE DE DONNÉES DisruptIQ

## Table: professionnels (Prestataires/Fournisseurs)
- id (INTEGER, PK)
- name (VARCHAR) - Nom du professionnel
- company_name (VARCHAR) - Nom de l'entreprise
- email (VARCHAR, UNIQUE) - Email
- phone (VARCHAR) - Téléphone
- siret (VARCHAR) - Numéro SIRET
- description (TEXT) - Description des services
- statut (VARCHAR) - active, inactive, blacklisted
- category (VARCHAR) - plombier, électricien, peintre, etc.
- specialties (JSONB) - Liste des spécialités
- address (TEXT), city (VARCHAR), postal_code (VARCHAR)
- rating (FLOAT) - Note sur 5
- total_jobs (INTEGER) - Nombre d'interventions
- is_indexed (BOOLEAN) - Indexé dans Qdrant
- created_at (TIMESTAMPTZ)

## Table: coproprietes (Immeubles gérés)
- id (INTEGER, PK)
- nom (VARCHAR) - Nom de la copropriété
- adresse (TEXT), ville (VARCHAR), code_postal (VARCHAR)
- nombre_lots (INTEGER) - Nombre d'appartements
- nombre_batiments (INTEGER)
- annee_construction (INTEGER)
- syndic (VARCHAR) - Nom du syndic
- type_copropriete (VARCHAR) - résidentiel, mixte, commercial
- surface_totale (NUMERIC) - Surface en m²
- equipements (JSONB) - ["ascenseur", "parking"]
- is_indexed (BOOLEAN)
- created_at (TIMESTAMPTZ)

## Table: coproprietaires (Résidents/Propriétaires)
- id (INTEGER, PK)
- nom (VARCHAR), prenom (VARCHAR)
- email (VARCHAR), telephone (VARCHAR), telephone_mobile (VARCHAR)
- copropriete_id (INTEGER, FK → coproprietes.id)
- numero_lot (VARCHAR) - "A12", "Bat B - 304"
- type_lot (VARCHAR) - appartement, garage, cave
- etage (INTEGER), surface (NUMERIC)
- statut (VARCHAR) - proprietaire, locataire, usufruitier
- statut_special (VARCHAR) - président, syndic, gardien
- est_resident (BOOLEAN) - Habite-t-il le lot?
- tantiemes (INTEGER) - Millièmes de copropriété
- is_indexed (BOOLEAN)
- created_at (TIMESTAMPTZ)

## Table: professionnels_coproprietes (Liaison Many-to-Many)
- professionnel_id (INTEGER, FK → professionnels.id)
- copropriete_id (INTEGER, FK → coproprietes.id)
- date_debut (DATE), date_fin (DATE)
- est_prestataire_principal (BOOLEAN)
- nombre_interventions (INTEGER)
- note_moyenne (NUMERIC)

## Table: documents
- id (INTEGER, PK)
- filename (VARCHAR), file_size (BIGINT), mime_type (VARCHAR)
- document_type (VARCHAR) - invoice, contract, letter
- extracted_text (TEXT)
- professionnel_id (INTEGER, FK → professionnels.id)
- copropriete_id (INTEGER, FK → coproprietes.id)
- coproprietaire_id (INTEGER, FK → coproprietaires.id)
- created_at (TIMESTAMPTZ)

## Table: emails
- id (INTEGER, PK)
- sender (VARCHAR), subject (VARCHAR), body (TEXT)
- urgency (ENUM) - urgent, important, routine
- professionnel_id, copropriete_id, coproprietaire_id (FK)
- received_at (TIMESTAMPTZ)

# EXEMPLES DE REQUÊTES

1. "Trouve tous les plombiers dans le 13ème arrondissement"
   → SELECT * FROM professionnels WHERE category ILIKE '%plombier%' AND (city ILIKE '%13%' OR postal_code LIKE '13%')

2. "Qui habite au 3ème étage de la résidence Les Mimosas?"
   → SELECT c.* FROM coproprietaires c
      JOIN coproprietes co ON c.copropriete_id = co.id
      WHERE co.nom ILIKE '%Les Mimosas%' AND c.etage = 3

3. "Liste les professionnels qui travaillent sur la copropriété X"
   → SELECT p.* FROM professionnels p
      JOIN professionnels_coproprietes pc ON p.id = pc.professionnel_id
      JOIN coproprietes c ON pc.copropriete_id = c.id
      WHERE c.nom ILIKE '%X%' AND pc.date_fin IS NULL
"""
        return schema

    async def natural_language_to_sql(
        self,
        query: str,
        operation_type: str = "SELECT"
    ) -> Dict[str, Any]:
        """
        Convertit une requête en langage naturel en SQL

        Args:
            query: Requête en langage naturel
            operation_type: Type d'opération (SELECT, INSERT, UPDATE, DELETE)

        Returns:
            Dict avec sql, explanation, estimated_rows
        """
        try:
            # Construire le prompt pour le LLM
            schema = self._build_schema_description()

            system_prompt = f"""Tu es un expert SQL pour PostgreSQL.
Ton rôle est de convertir des requêtes en langage naturel en SQL sécurisé et optimisé.

{schema}

RÈGLES IMPORTANTES:
1. Génère UNIQUEMENT du SQL PostgreSQL valide
2. Utilise TOUJOURS ILIKE pour les recherches texte (insensible à la casse)
3. Ajoute LIMIT {self.MAX_RESULTS} si pas de LIMIT spécifié
4. Pour les dates, utilise CURRENT_DATE, NOW(), INTERVAL
5. Joins: Utilise INNER JOIN par défaut, LEFT JOIN si nécessaire
6. JAMAIS de DROP, TRUNCATE, ALTER dans les requêtes
7. Pour les INSERT/UPDATE/DELETE, ajoute RETURNING * pour voir le résultat

Format de réponse (JSON strict):
{{
    "sql": "SELECT * FROM ...",
    "explanation": "Explication de la requête",
    "estimated_rows": 10,
    "tables_used": ["table1", "table2"]
}}
"""

            user_prompt = f"""Convertis cette requête en SQL:

"{query}"

Type d'opération demandée: {operation_type}

Réponds UNIQUEMENT avec un objet JSON valide (sans markdown, sans ```json)."""

            # Appeler le LLM via LangChain
            from langchain.schema import SystemMessage, HumanMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            llm_response = await self.llm_service.chat_model.ainvoke(messages)
            response = llm_response.content

            # Parser la réponse JSON
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # Essayer d'extraire le JSON si le LLM a ajouté du texte autour
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError("Le LLM n'a pas retourné du JSON valide")

            logger.info(
                "nl_to_sql_success",
                query=query[:100],
                sql=result['sql'][:200]
            )

            return result

        except Exception as e:
            logger.error("nl_to_sql_failed", query=query, error=str(e))
            raise ValueError(f"Conversion NL→SQL échouée: {str(e)}")

    def _validate_sql(self, sql: str) -> Dict[str, Any]:
        """
        Valide et sécurise une requête SQL

        Args:
            sql: Requête SQL à valider

        Returns:
            Dict avec is_valid, errors, warnings
        """
        errors = []
        warnings = []

        sql_upper = sql.upper()

        # Vérifier les opérations dangereuses
        for dangerous_op in self.DANGEROUS_OPERATIONS:
            if dangerous_op in sql_upper:
                errors.append(f"Opération interdite: {dangerous_op}")

        # Vérifier que les tables utilisées sont autorisées
        used_tables = re.findall(r'FROM\s+(\w+)', sql_upper)
        used_tables += re.findall(r'JOIN\s+(\w+)', sql_upper)
        used_tables += re.findall(r'UPDATE\s+(\w+)', sql_upper)
        used_tables += re.findall(r'INTO\s+(\w+)', sql_upper)

        for table in used_tables:
            if table.lower() not in self.ALLOWED_TABLES:
                errors.append(f"Table non autorisée: {table}")

        # Vérifier la limite de résultats pour SELECT
        if 'SELECT' in sql_upper and 'LIMIT' not in sql_upper:
            warnings.append(f"Pas de LIMIT défini, max {self.MAX_RESULTS} résultats")

        # Vérifier les UPDATE/DELETE sans WHERE
        if 'UPDATE' in sql_upper and 'WHERE' not in sql_upper:
            errors.append("UPDATE sans WHERE interdit (risque de modification totale)")

        if 'DELETE' in sql_upper and 'WHERE' not in sql_upper:
            errors.append("DELETE sans WHERE interdit (risque de suppression totale)")

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }

    async def execute_sql(
        self,
        sql: str,
        db: AsyncSession,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Exécute une requête SQL de manière sécurisée

        Args:
            sql: Requête SQL à exécuter
            db: Session database
            validate: Valider avant exécution

        Returns:
            Dict avec results, row_count, columns
        """
        try:
            # Validation
            if validate:
                validation = self._validate_sql(sql)
                if not validation["is_valid"]:
                    return {
                        "success": False,
                        "error": "Requête invalide",
                        "validation_errors": validation["errors"]
                    }

            # Ajouter LIMIT si SELECT sans LIMIT
            if 'SELECT' in sql.upper() and 'LIMIT' not in sql.upper():
                sql = f"{sql.rstrip(';')} LIMIT {self.MAX_RESULTS}"

            # Exécuter la requête
            result = await db.execute(text(sql))

            # Récupérer les résultats
            if 'SELECT' in sql.upper() or 'RETURNING' in sql.upper():
                rows = result.fetchall()
                columns = list(result.keys()) if rows else []

                # Convertir en liste de dicts
                results = [
                    dict(zip(columns, row))
                    for row in rows
                ]

                return {
                    "success": True,
                    "results": results,
                    "row_count": len(results),
                    "columns": columns
                }
            else:
                # INSERT/UPDATE/DELETE
                await db.commit()
                return {
                    "success": True,
                    "message": "Opération réussie",
                    "rows_affected": result.rowcount
                }

        except Exception as e:
            await db.rollback()
            logger.error("sql_execution_failed", sql=sql[:200], error=str(e))
            return {
                "success": False,
                "error": str(e),
                "sql": sql
            }

    async def execute_natural_query(
        self,
        query: str,
        db: AsyncSession,
        operation_type: str = "SELECT"
    ) -> Dict[str, Any]:
        """
        Pipeline complet: NL → SQL → Exécution → Résultats

        Args:
            query: Requête en langage naturel
            db: Session database
            operation_type: Type d'opération

        Returns:
            Dict avec sql, results, explanation
        """
        try:
            # Étape 1: Conversion NL → SQL
            nl_result = await self.natural_language_to_sql(query, operation_type)
            sql = nl_result["sql"]

            # Étape 2: Validation
            validation = self._validate_sql(sql)
            if not validation["is_valid"]:
                return {
                    "success": False,
                    "error": "SQL généré invalide",
                    "validation_errors": validation["errors"],
                    "sql": sql
                }

            # Étape 3: Exécution
            exec_result = await self.execute_sql(sql, db, validate=False)

            # Étape 4: Formater la réponse
            if exec_result["success"]:
                return {
                    "success": True,
                    "query": query,
                    "sql": sql,
                    "explanation": nl_result.get("explanation", ""),
                    "results": exec_result.get("results", []),
                    "row_count": exec_result.get("row_count", exec_result.get("rows_affected", 0)),
                    "columns": exec_result.get("columns", []),
                    "warnings": validation.get("warnings", [])
                }
            else:
                return {
                    "success": False,
                    "error": exec_result["error"],
                    "sql": sql,
                    "query": query
                }

        except Exception as e:
            logger.error("natural_query_failed", query=query, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
