"""
Tests for Copropriétés and Copropriétaires Endpoints
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.copropriete import Copropriete
from app.models.coproprietaire import Coproprietaire


@pytest.mark.asyncio
@pytest.mark.coproprietes
class TestCoproprietes:
    """Test copropriétés CRUD operations"""

    async def test_create_copropriete(self, client: AsyncClient):
        """Test creating a new copropriété"""
        data = {
            "nom": "Résidence Test",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001",
            "nombre_lots": 10,
            "nombre_batiments": 1,
            "annee_construction": 2000,
            "type_copropriete": "résidentiel"
        }

        response = await client.post("/api/coproprietes/", json=data)
        assert response.status_code == 201

        result = response.json()
        assert result["nom"] == "Résidence Test"
        assert result["ville"] == "Paris"
        assert result["is_indexed"] is False
        assert "id" in result

    async def test_list_coproprietes(self, client: AsyncClient):
        """Test listing copropriétés"""
        # Create test data
        data1 = {
            "nom": "Résidence A",
            "adresse": "1 rue A",
            "ville": "Paris",
            "code_postal": "75001"
        }
        data2 = {
            "nom": "Résidence B",
            "adresse": "2 rue B",
            "ville": "Lyon",
            "code_postal": "69001"
        }

        await client.post("/api/coproprietes/", json=data1)
        await client.post("/api/coproprietes/", json=data2)

        # List all
        response = await client.get("/api/coproprietes/")
        assert response.status_code == 200

        result = response.json()
        assert len(result) == 2
        assert result[0]["coproprietaires_count"] is not None

    async def test_get_copropriete_by_id(self, client: AsyncClient):
        """Test getting specific copropriété"""
        # Create
        data = {
            "nom": "Résidence Test",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        create_response = await client.post("/api/coproprietes/", json=data)
        copro_id = create_response.json()["id"]

        # Get by ID
        response = await client.get(f"/api/coproprietes/{copro_id}")
        assert response.status_code == 200

        result = response.json()
        assert result["id"] == copro_id
        assert result["nom"] == "Résidence Test"

    async def test_update_copropriete(self, client: AsyncClient):
        """Test updating copropriété"""
        # Create
        data = {
            "nom": "Résidence Original",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        create_response = await client.post("/api/coproprietes/", json=data)
        copro_id = create_response.json()["id"]

        # Update
        update_data = {"nom": "Résidence Updated"}
        response = await client.put(f"/api/coproprietes/{copro_id}", json=update_data)
        assert response.status_code == 200

        result = response.json()
        assert result["nom"] == "Résidence Updated"

    async def test_delete_copropriete(self, client: AsyncClient):
        """Test deleting copropriété"""
        # Create
        data = {
            "nom": "Résidence to Delete",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        create_response = await client.post("/api/coproprietes/", json=data)
        copro_id = create_response.json()["id"]

        # Delete
        response = await client.delete(f"/api/coproprietes/{copro_id}")
        assert response.status_code == 200
        assert response.json()["id"] == copro_id

        # Verify deleted
        get_response = await client.get(f"/api/coproprietes/{copro_id}")
        assert get_response.status_code == 404

    async def test_get_copropriete_stats(self, client: AsyncClient):
        """Test copropriété statistics"""
        # Create copropriété
        copro_data = {
            "nom": "Résidence Stats",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        copro_response = await client.post("/api/coproprietes/", json=copro_data)
        copro_id = copro_response.json()["id"]

        # Get stats
        response = await client.get(f"/api/coproprietes/{copro_id}/stats")
        assert response.status_code == 200

        stats = response.json()
        assert "total_coproprietaires" in stats
        assert "by_statut" in stats
        assert "special_roles" in stats


@pytest.mark.asyncio
@pytest.mark.coproprietaires
class TestCoproprietaires:
    """Test copropriétaires CRUD operations"""

    async def test_create_coproprietaire(self, client: AsyncClient):
        """Test creating a new copropriétaire"""
        # First create a copropriété
        copro_data = {
            "nom": "Résidence Test",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        copro_response = await client.post("/api/coproprietes/", json=copro_data)
        copro_id = copro_response.json()["id"]

        # Create copropriétaire
        data = {
            "nom": "Dupont",
            "prenom": "Jean",
            "email": "jean.dupont@test.com",
            "telephone": "0612345678",
            "copropriete_id": copro_id,
            "numero_lot": "A101",
            "type_lot": "appartement",
            "etage": 3,
            "surface": 65.5,
            "statut": "proprietaire",
            "est_resident": True
        }

        response = await client.post("/api/coproprietaires/", json=data)
        assert response.status_code == 201

        result = response.json()
        assert result["nom"] == "Dupont"
        assert result["prenom"] == "Jean"
        assert result["copropriete_id"] == copro_id
        assert "copropriete_nom" in result

    async def test_list_coproprietaires(self, client: AsyncClient):
        """Test listing copropriétaires"""
        # Create copropriété
        copro_data = {
            "nom": "Résidence Test",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        copro_response = await client.post("/api/coproprietes/", json=copro_data)
        copro_id = copro_response.json()["id"]

        # Create copropriétaires
        data1 = {
            "nom": "Dupont",
            "prenom": "Jean",
            "email": "jean@test.com",
            "copropriete_id": copro_id,
            "numero_lot": "A101"
        }
        data2 = {
            "nom": "Martin",
            "prenom": "Marie",
            "email": "marie@test.com",
            "copropriete_id": copro_id,
            "numero_lot": "A102"
        }

        await client.post("/api/coproprietaires/", json=data1)
        await client.post("/api/coproprietaires/", json=data2)

        # List all
        response = await client.get("/api/coproprietaires/")
        assert response.status_code == 200

        result = response.json()
        assert len(result) == 2

    async def test_get_special_roles(self, client: AsyncClient):
        """Test getting copropriétaires with special roles"""
        # Create copropriété
        copro_data = {
            "nom": "Résidence Test",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        copro_response = await client.post("/api/coproprietes/", json=copro_data)
        copro_id = copro_response.json()["id"]

        # Create président
        data = {
            "nom": "Président",
            "prenom": "Jean",
            "email": "president@test.com",
            "copropriete_id": copro_id,
            "numero_lot": "A101",
            "statut_special": "président"
        }
        await client.post("/api/coproprietaires/", json=data)

        # Get special roles
        response = await client.get("/api/coproprietaires/special-roles/list")
        assert response.status_code == 200

        result = response.json()
        assert "special_roles" in result
        assert result["total"] >= 1

    async def test_search_coproprietaires(self, client: AsyncClient):
        """Test searching copropriétaires"""
        # Create copropriété
        copro_data = {
            "nom": "Résidence Test",
            "adresse": "123 rue de Test",
            "ville": "Paris",
            "code_postal": "75001"
        }
        copro_response = await client.post("/api/coproprietes/", json=copro_data)
        copro_id = copro_response.json()["id"]

        # Create copropriétaire
        data = {
            "nom": "SearchTest",
            "prenom": "John",
            "email": "searchtest@test.com",
            "copropriete_id": copro_id,
            "numero_lot": "SEARCH101"
        }
        await client.post("/api/coproprietaires/", json=data)

        # Search
        response = await client.get("/api/coproprietaires/?search=SearchTest")
        assert response.status_code == 200

        result = response.json()
        assert len(result) >= 1
        assert result[0]["nom"] == "SearchTest"
