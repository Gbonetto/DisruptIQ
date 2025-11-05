"""
Schema Introspection Service
Génère automatiquement des descriptions de schéma pour le LLM depuis SQLAlchemy metadata

Architecture:
- Single Source of Truth: SQLAlchemy models
- Cache pour performance
- Détection de schema drift (optionnel)
- Support pour tous les types SQLAlchemy
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import class_mapper
from sqlalchemy.exc import NoInspectionAvailable
import structlog

logger = structlog.get_logger(__name__)


class SchemaIntrospectionService:
    """
    Service d'introspection de schéma

    Capacités:
    - Génère description texte depuis SQLAlchemy models
    - Détecte colonnes, types, contraintes, relations
    - Maintient cache auto-rafraîchi
    - Single source of truth: SQLAlchemy models uniquement

    Usage:
        service = get_schema_service()
        schema_desc = service.build_full_schema_description()
        # → Description Markdown complète pour LLM
    """

    def __init__(self):
        self._schema_cache: Dict[str, str] = {}
        self._cache_built = False
        self._documented_models = []

    def register_models(self, models: List[Any]):
        """
        Enregistre les modèles à documenter

        Args:
            models: Liste de classes SQLAlchemy (ex: [Professionnel, Copropriete])
        """
        self._documented_models = models
        logger.info("models_registered", count=len(models))

    def _get_sqlalchemy_type_description(self, column) -> str:
        """
        Convertit type SQLAlchemy en description lisible

        Args:
            column: Objet Column SQLAlchemy

        Returns:
            Description humaine du type
        """
        col_type_str = str(column.type).upper()

        # Mapping des types communs
        type_mapping = {
            "INTEGER": "Entier",
            "BIGINT": "Grand entier",
            "SMALLINT": "Petit entier",
            "VARCHAR": "Texte",
            "TEXT": "Texte long",
            "STRING": "Texte",
            "BOOLEAN": "Booléen (true/false)",
            "DATE": "Date (YYYY-MM-DD)",
            "DATETIME": "Date et heure",
            "TIMESTAMP": "Timestamp",
            "DECIMAL": "Nombre décimal",
            "NUMERIC": "Nombre",
            "FLOAT": "Nombre flottant",
            "REAL": "Nombre réel",
            "JSONB": "Données JSON flexibles",
            "JSON": "Données JSON",
            "ENUM": "Énumération",
        }

        for sql_type, description in type_mapping.items():
            if sql_type in col_type_str:
                return description

        return col_type_str

    def _extract_column_comment(self, column) -> str:
        """
        Extrait le commentaire d'une colonne

        Args:
            column: Objet Column SQLAlchemy

        Returns:
            Commentaire ou chaîne vide
        """
        # SQLAlchemy stocke les commentaires dans column.comment
        if hasattr(column, 'comment') and column.comment:
            return column.comment

        # Ou dans column.doc si utilisé via comment=
        if hasattr(column, 'doc') and column.doc:
            return column.doc

        return ""

    def _build_model_description(self, model_class) -> str:
        """
        Génère description d'un model SQLAlchemy

        Args:
            model_class: Classe SQLAlchemy (ex: Professionnel)

        Returns:
            Description formatée Markdown pour LLM
        """
        try:
            mapper = class_mapper(model_class)
        except NoInspectionAvailable:
            logger.warning("model_not_inspectable", model=model_class.__name__)
            return f"## {model_class.__name__}\n**Erreur**: Model non inspectable\n"

        table_name = mapper.mapped_table.name
        model_doc = model_class.__doc__ or ""

        # Nettoyer la docstring (enlever indentation excessive)
        if model_doc:
            lines = [line.strip() for line in model_doc.split('\n') if line.strip()]
            model_doc = ' '.join(lines)

        lines = [
            f"## Table: {table_name}",
            f"**Description**: {model_doc}" if model_doc else "",
            "",
            "### Colonnes:",
        ]

        # Parcourir toutes les colonnes
        for column in mapper.mapped_table.columns:
            col_name = column.name
            col_type = self._get_sqlalchemy_type_description(column)

            # Flags importants
            flags = []
            if column.primary_key:
                flags.append("PK")
            if column.foreign_keys:
                # Extraire table référencée
                fk_targets = [f"{fk.column.table.name}.{fk.column.name}" for fk in column.foreign_keys]
                flags.append(f"FK → {', '.join(fk_targets)}")
            if column.nullable is False:
                flags.append("NOT NULL")
            if column.unique:
                flags.append("UNIQUE")
            if column.index:
                flags.append("INDEXED")

            flags_str = f" [{', '.join(flags)}]" if flags else ""

            # Comment
            comment = self._extract_column_comment(column)
            comment_str = f" - {comment}" if comment else ""

            # Default value (si simple)
            default_str = ""
            if column.default is not None and hasattr(column.default, 'arg'):
                default_val = column.default.arg
                if isinstance(default_val, (str, int, float, bool)):
                    default_str = f" (défaut: {default_val})"

            lines.append(f"- **{col_name}**: {col_type}{flags_str}{default_str}{comment_str}")

        # Relations (One-to-Many, Many-to-One)
        if mapper.relationships:
            lines.append("")
            lines.append("### Relations:")
            for rel_name, relationship in mapper.relationships.items():
                target_class = relationship.mapper.class_.__name__
                target_table = relationship.mapper.mapped_table.name

                # Déterminer type de relation
                if relationship.uselist:
                    rel_type = "One-to-Many"
                else:
                    rel_type = "Many-to-One"

                lines.append(f"- **{rel_name}** ({rel_type}) → {target_class} (table: {target_table})")

        lines.append("")
        return "\n".join(lines)

    def build_full_schema_description(self) -> str:
        """
        Génère description complète de TOUS les models enregistrés

        Returns:
            Description Markdown complète pour le LLM

        Note:
            - Résultat mis en cache après première génération
            - Utilisez invalidate_cache() après migration pour rafraîchir
        """
        if self._cache_built and self._schema_cache.get("full_schema"):
            logger.debug("schema_cache_hit")
            return self._schema_cache["full_schema"]

        if not self._documented_models:
            logger.warning("no_models_registered")
            return "# SCHÉMA DE BASE DE DONNÉES\n\n**Aucun modèle enregistré**"

        logger.info("building_schema_description_from_models", count=len(self._documented_models))

        parts = [
            "# SCHÉMA DE LA BASE DE DONNÉES DisruptIQ",
            "",
            "**Note**: Ce schéma est généré automatiquement depuis les modèles SQLAlchemy.",
            "Il reflète TOUJOURS l'état actuel de la base de données.",
            "",
            "---",
            "",
        ]

        # Générer description pour chaque model
        for model_class in self._documented_models:
            try:
                model_desc = self._build_model_description(model_class)
                parts.append(model_desc)
                parts.append("---")
                parts.append("")
            except Exception as e:
                logger.error(
                    "model_description_failed",
                    model=model_class.__name__,
                    error=str(e)
                )
                parts.append(f"## {model_class.__name__}")
                parts.append(f"**Erreur lors de la génération**: {str(e)}")
                parts.append("")

        # Ajouter exemples de requêtes (génériques, pas liés au schéma)
        parts.extend([
            "# EXEMPLES DE REQUÊTES GÉNÉRIQUES",
            "",
            "## 1. Recherche insensible à la casse (ILIKE)",
            "```sql",
            "SELECT * FROM professionnels WHERE LOWER(name) LIKE '%dupont%'",
            "```",
            "",
            "## 2. Jointure avec filtres",
            "```sql",
            "SELECT p.*, c.nom as copropriete_nom",
            "FROM professionnels p",
            "JOIN professionnels_coproprietes pc ON p.id = pc.professionnel_id",
            "JOIN coproprietes c ON pc.copropriete_id = c.id",
            "WHERE c.nom ILIKE '%mimosas%'",
            "```",
            "",
            "## 3. Agrégation avec GROUP BY",
            "```sql",
            "SELECT category, COUNT(*) as count, AVG(rating) as avg_rating",
            "FROM professionnels",
            "WHERE statut = 'active'",
            "GROUP BY category",
            "ORDER BY count DESC",
            "```",
            "",
            "## 4. Recherche de dates (CURRENT_DATE, INTERVAL)",
            "```sql",
            "SELECT * FROM factures_global",
            "WHERE date_facture >= CURRENT_DATE - INTERVAL '30 days'",
            "```",
            "",
            "## 5. Filtres JSONB (métadonnées flexibles)",
            "```sql",
            "SELECT * FROM professionnels",
            "WHERE specialties @> '[\"plomberie\"]'::jsonb",
            "```",
            "",
        ])

        full_schema = "\n".join(parts)

        # Cache
        self._schema_cache["full_schema"] = full_schema
        self._cache_built = True

        logger.info(
            "schema_description_built",
            models_count=len(self._documented_models),
            total_length=len(full_schema),
            cached=True
        )

        return full_schema

    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Récupère les colonnes d'une table spécifique

        Args:
            table_name: Nom de la table

        Returns:
            Liste de dicts avec infos colonnes
            Format: [{"name": str, "type": str, "nullable": bool, ...}]
        """
        for model_class in self._documented_models:
            try:
                mapper = class_mapper(model_class)
                if mapper.mapped_table.name == table_name:
                    columns = []
                    for column in mapper.mapped_table.columns:
                        columns.append({
                            "name": column.name,
                            "type": str(column.type),
                            "nullable": column.nullable,
                            "primary_key": column.primary_key,
                            "unique": column.unique,
                            "indexed": column.index,
                            "comment": self._extract_column_comment(column),
                        })
                    return columns
            except NoInspectionAvailable:
                continue

        logger.warning("table_not_found", table_name=table_name)
        return []

    def invalidate_cache(self):
        """
        Force la régénération du schéma (après migration)

        Usage:
            # Après une migration Alembic
            schema_service.invalidate_cache()
            new_schema = schema_service.build_full_schema_description()
        """
        self._cache_built = False
        self._schema_cache.clear()
        logger.info("schema_cache_invalidated")

    async def detect_schema_changes(
        self,
        db: AsyncSession,
        table_name: str
    ) -> Dict[str, Any]:
        """
        Détecte les changements de schéma entre SQLAlchemy models et DB réelle

        Args:
            db: Session database
            table_name: Table à vérifier

        Returns:
            Dict avec:
                - table: str
                - added_columns: List[str] (dans model, pas dans DB)
                - removed_columns: List[str] (dans DB, pas dans model)
                - has_changes: bool

        Note:
            - "added_columns" signifie que le model a des colonnes que la DB n'a pas encore
            - "removed_columns" signifie que la DB a des colonnes que le model n'a plus
        """
        # Récupérer colonnes depuis SQLAlchemy model
        model_columns_list = self.get_table_columns(table_name)
        if not model_columns_list:
            logger.warning("table_not_in_models", table=table_name)
            return {
                "table": table_name,
                "added_columns": [],
                "removed_columns": [],
                "has_changes": False,
                "error": "Table not found in registered models"
            }

        model_col_names = {col["name"] for col in model_columns_list}

        # Récupérer colonnes depuis DB réelle (via information_schema)
        query = text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = :table_name
            AND table_schema = 'public'
        """)

        try:
            result = await db.execute(query, {"table_name": table_name})
            db_rows = result.fetchall()
            db_col_names = {row.column_name for row in db_rows}
        except Exception as e:
            logger.error("db_introspection_failed", table=table_name, error=str(e))
            return {
                "table": table_name,
                "added_columns": [],
                "removed_columns": [],
                "has_changes": False,
                "error": str(e)
            }

        # Comparer
        added = model_col_names - db_col_names
        removed = db_col_names - model_col_names

        changes = {
            "table": table_name,
            "added_columns": sorted(list(added)),
            "removed_columns": sorted(list(removed)),
            "has_changes": len(added) > 0 or len(removed) > 0,
        }

        if changes["has_changes"]:
            logger.warning(
                "schema_drift_detected",
                table=table_name,
                added=changes["added_columns"],
                removed=changes["removed_columns"]
            )

        return changes

    def get_registered_tables(self) -> List[str]:
        """
        Retourne la liste des tables enregistrées

        Returns:
            Liste des noms de tables
        """
        tables = []
        for model_class in self._documented_models:
            try:
                mapper = class_mapper(model_class)
                tables.append(mapper.mapped_table.name)
            except NoInspectionAvailable:
                continue
        return tables


# ============================================================================
# Singleton Pattern
# ============================================================================

_schema_service_instance: Optional[SchemaIntrospectionService] = None


def get_schema_service() -> SchemaIntrospectionService:
    """
    Récupère l'instance singleton du SchemaIntrospectionService

    Returns:
        Instance singleton

    Note:
        - Le service doit être initialisé au démarrage de l'application
        - Appelez initialize_schema_service() dans app/main.py
    """
    global _schema_service_instance
    if _schema_service_instance is None:
        logger.warning("schema_service_not_initialized", hint="Call initialize_schema_service() in main.py")
        _schema_service_instance = SchemaIntrospectionService()
    return _schema_service_instance


def initialize_schema_service() -> SchemaIntrospectionService:
    """
    Initialise le SchemaIntrospectionService avec tous les modèles

    Returns:
        Instance initialisée

    Usage:
        # Dans app/main.py, au startup
        from app.services.schema_introspection_service import initialize_schema_service
        initialize_schema_service()
    """
    global _schema_service_instance

    # Import des modèles (tous les models SQLAlchemy)
    from app.models.professionnel import Professionnel
    from app.models.copropriete import Copropriete
    from app.models.coproprietaire import Coproprietaire
    from app.models.invoice import FactureGlobal, FactureDetail
    from app.models.email import Email
    from app.models.document import Document
    from app.models.user import User
    from app.models.conversation import ConversationSession, ConversationTurn
    from app.models.agent_run import AgentRun
    from app.models.agent_step import AgentStep

    # Liste complète des modèles à documenter
    documented_models = [
        Professionnel,
        Copropriete,
        Coproprietaire,
        FactureGlobal,
        FactureDetail,
        Email,
        Document,
        User,
        ConversationSession,
        ConversationTurn,
        AgentRun,
        AgentStep,
    ]

    _schema_service_instance = SchemaIntrospectionService()
    _schema_service_instance.register_models(documented_models)

    logger.info(
        "schema_service_initialized",
        models_count=len(documented_models),
        tables=_schema_service_instance.get_registered_tables()
    )

    return _schema_service_instance
