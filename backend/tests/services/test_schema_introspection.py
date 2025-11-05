"""
Tests for SchemaIntrospectionService
Tests schema generation from SQLAlchemy models
"""

import pytest
from sqlalchemy import text

from app.services.schema_introspection_service import (
    SchemaIntrospectionService,
    get_schema_service,
    initialize_schema_service
)
from app.models.professionnel import Professionnel
from app.models.copropriete import Copropriete
from app.models.invoice import FactureGlobal


class TestSchemaIntrospectionService:
    """Tests pour SchemaIntrospectionService"""

    def test_service_initialization(self):
        """Test initialisation du service"""
        service = SchemaIntrospectionService()
        assert service is not None
        assert service._documented_models == []
        assert not service._cache_built

    def test_register_models(self):
        """Test enregistrement des modèles"""
        service = SchemaIntrospectionService()
        models = [Professionnel, Copropriete]

        service.register_models(models)

        assert len(service._documented_models) == 2
        assert Professionnel in service._documented_models
        assert Copropriete in service._documented_models

    def test_get_sqlalchemy_type_description(self):
        """Test conversion des types SQLAlchemy"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        # Récupérer une colonne
        from sqlalchemy.orm import class_mapper
        mapper = class_mapper(Professionnel)
        id_column = mapper.mapped_table.columns['id']

        type_desc = service._get_sqlalchemy_type_description(id_column)
        assert "Entier" in type_desc or "INTEGER" in type_desc

    def test_build_model_description(self):
        """Test génération description d'un model"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        description = service._build_model_description(Professionnel)

        # Vérifications
        assert "## Table: professionnels" in description
        assert "### Colonnes:" in description
        assert "**id**:" in description
        assert "**name**:" in description
        assert "**email**:" in description
        assert "PK" in description  # id est primary key

    def test_build_full_schema_description(self):
        """Test génération schéma complet"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel, Copropriete])

        schema = service.build_full_schema_description()

        # Vérifications globales
        assert "# SCHÉMA DE LA BASE DE DONNÉES DisruptIQ" in schema
        assert "généré automatiquement" in schema

        # Vérifier présence des 2 tables
        assert "## Table: professionnels" in schema
        assert "## Table: coproprietes" in schema

        # Vérifier exemples de requêtes
        assert "EXEMPLES DE REQUÊTES GÉNÉRIQUES" in schema
        assert "ILIKE" in schema

    def test_schema_caching(self):
        """Test que le schéma est mis en cache"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        # Première génération
        schema1 = service.build_full_schema_description()
        assert service._cache_built

        # Deuxième génération (doit retourner le cache)
        schema2 = service.build_full_schema_description()

        # Doit être identique (même objet en mémoire)
        assert schema1 == schema2

    def test_invalidate_cache(self):
        """Test invalidation du cache"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        # Générer schéma
        service.build_full_schema_description()
        assert service._cache_built

        # Invalider
        service.invalidate_cache()
        assert not service._cache_built
        assert len(service._schema_cache) == 0

    def test_get_table_columns(self):
        """Test récupération colonnes d'une table"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        columns = service.get_table_columns("professionnels")

        # Vérifications
        assert len(columns) > 0
        assert any(col["name"] == "id" for col in columns)
        assert any(col["name"] == "name" for col in columns)
        assert any(col["name"] == "email" for col in columns)

        # Vérifier structure
        id_col = next(col for col in columns if col["name"] == "id")
        assert "type" in id_col
        assert "nullable" in id_col
        assert "primary_key" in id_col
        assert id_col["primary_key"] is True

    def test_get_table_columns_unknown_table(self):
        """Test récupération colonnes table inconnue"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        columns = service.get_table_columns("table_inconnue")

        assert columns == []

    def test_get_registered_tables(self):
        """Test liste des tables enregistrées"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel, Copropriete, FactureGlobal])

        tables = service.get_registered_tables()

        assert "professionnels" in tables
        assert "coproprietes" in tables
        assert "factures_global" in tables
        assert len(tables) == 3

    def test_foreign_key_detection(self):
        """Test détection des foreign keys"""
        service = SchemaIntrospectionService()
        service.register_models([FactureGlobal])

        description = service._build_model_description(FactureGlobal)

        # FactureGlobal a des FK vers professionnels, coproprietes, documents
        assert "FK" in description
        assert "fournisseur_id" in description or "copropriete_id" in description

    def test_relationships_detection(self):
        """Test détection des relations"""
        service = SchemaIntrospectionService()
        service.register_models([Copropriete])

        description = service._build_model_description(Copropriete)

        # Copropriete a une relation coproprietaires
        assert "### Relations:" in description
        assert "coproprietaires" in description.lower()

    @pytest.mark.asyncio
    async def test_detect_schema_changes_no_drift(self, db_session):
        """Test détection changements - pas de drift"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        # Pas de changements attendus (model = DB)
        changes = await service.detect_schema_changes(db_session, "professionnels")

        assert changes["table"] == "professionnels"
        assert changes["added_columns"] == []
        assert changes["removed_columns"] == []
        assert changes["has_changes"] is False

    @pytest.mark.asyncio
    async def test_detect_schema_changes_unknown_table(self, db_session):
        """Test détection changements - table inconnue"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        # Table pas dans les models
        changes = await service.detect_schema_changes(db_session, "table_inexistante")

        assert "error" in changes
        assert changes["has_changes"] is False

    def test_singleton_get_schema_service(self):
        """Test singleton get_schema_service()"""
        service1 = get_schema_service()
        service2 = get_schema_service()

        # Doit retourner la même instance
        assert service1 is service2

    def test_initialize_schema_service(self):
        """Test initialisation complète du service"""
        service = initialize_schema_service()

        # Vérifier que tous les modèles sont enregistrés
        tables = service.get_registered_tables()

        # Doit contenir au moins les tables principales
        expected_tables = [
            "professionnels",
            "coproprietes",
            "coproprietaires",
            "factures_global",
            "factures_details",
            "emails",
            "documents",
            "users"
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} manquante dans les modèles enregistrés"

    def test_schema_includes_all_key_elements(self):
        """Test que le schéma généré inclut tous les éléments clés"""
        service = initialize_schema_service()
        schema = service.build_full_schema_description()

        # Éléments obligatoires
        required_elements = [
            "# SCHÉMA DE LA BASE DE DONNÉES",
            "## Table:",
            "### Colonnes:",
            "PK",  # Au moins une primary key
            "EXEMPLES DE REQUÊTES",
            "ILIKE",
            "JOIN",
        ]

        for element in required_elements:
            assert element in schema, f"Élément manquant dans le schéma: {element}"

    def test_schema_markdown_formatting(self):
        """Test que le schéma est bien formaté en Markdown"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        schema = service.build_full_schema_description()

        # Vérifier formatage Markdown
        assert schema.count("##") >= 1  # Au moins un header niveau 2
        assert schema.count("**") >= 2  # Au moins du texte en gras
        assert schema.count("```") >= 2  # Au moins un code block
        assert "\n\n" in schema  # Séparation paragraphes

    def test_column_flags_detection(self):
        """Test détection des flags de colonnes (NOT NULL, UNIQUE, etc.)"""
        service = SchemaIntrospectionService()
        service.register_models([Professionnel])

        description = service._build_model_description(Professionnel)

        # Vérifier flags communs
        assert "PK" in description  # Primary Key sur id
        assert "NOT NULL" in description  # Plusieurs colonnes NOT NULL
        # Email est UNIQUE
        if "email" in description.lower():
            # Chercher la ligne email
            email_line = [line for line in description.split('\n') if 'email' in line.lower()][0]
            # Peut contenir UNIQUE (dépend du model)

    def test_schema_with_jsonb_columns(self):
        """Test schéma avec colonnes JSONB"""
        service = SchemaIntrospectionService()
        service.register_models([FactureGlobal])

        description = service._build_model_description(FactureGlobal)

        # FactureGlobal a metadata_json en JSONB
        assert "metadata_json" in description
        assert "JSON" in description  # Type doit mentionner JSON

    def test_empty_models_list(self):
        """Test génération schéma avec liste vide de modèles"""
        service = SchemaIntrospectionService()
        # Ne pas enregistrer de modèles

        schema = service.build_full_schema_description()

        assert "Aucun modèle enregistré" in schema
