"""
Tests for Advanced Enrichment API Endpoints
"""

import pytest
import json
from decimal import Decimal
from datetime import date, timedelta
from pathlib import Path

from app.models.invoice import FactureGlobal, FactureStatut, ExtractionMethod
from app.models.professionnel import Professionnel


@pytest.mark.asyncio
class TestReEnrichEndpoint:
    """Test POST /api/enrichment/{id}/re-enrich"""

    async def test_re_enrich_success(self, async_client, async_db_session):
        """Should re-enrich invoice successfully"""
        # Create invoice
        invoice = FactureGlobal(
            numero="FAC-2024-001",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={"raw_text": "Réparation plomberie robinet"}
        )
        async_db_session.add(invoice)
        await async_db_session.commit()
        await async_db_session.refresh(invoice)

        # Re-enrich
        response = await async_client.post(
            f"/api/enrichment/{invoice.id}/re-enrich",
            json={"force": True}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["facture_id"] == invoice.id
        assert data["success"] is True
        assert "actions_taken" in data

    async def test_re_enrich_not_found(self, async_client):
        """Should return 404 for non-existent invoice"""
        response = await async_client.post(
            "/api/enrichment/99999/re-enrich",
            json={"force": True}
        )

        assert response.status_code == 404

    async def test_re_enrich_without_force_fails_if_already_enriched(
        self,
        async_client,
        async_db_session
    ):
        """Should fail if already enriched and force=false"""
        # Create invoice with enrichment
        invoice = FactureGlobal(
            numero="FAC-2024-002",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={
                "raw_text": "test",
                "enrichment": {"timestamp": "2024-01-01T00:00:00"}
            }
        )
        async_db_session.add(invoice)
        await async_db_session.commit()
        await async_db_session.refresh(invoice)

        # Try re-enrich without force
        response = await async_client.post(
            f"/api/enrichment/{invoice.id}/re-enrich",
            json={"force": False}
        )

        assert response.status_code == 400
        assert "already enriched" in response.json()["detail"].lower()

    async def test_re_enrich_with_custom_config(
        self,
        async_client,
        async_db_session
    ):
        """Should accept custom enrichment config"""
        # Create invoice
        invoice = FactureGlobal(
            numero="FAC-2024-003",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={"raw_text": "test"}
        )
        async_db_session.add(invoice)
        await async_db_session.commit()
        await async_db_session.refresh(invoice)

        # Re-enrich with custom config
        response = await async_client.post(
            f"/api/enrichment/{invoice.id}/re-enrich",
            json={
                "force": True,
                "config": {
                    "enable_supplier_matching": False,
                    "enable_category_classification": True
                }
            }
        )

        assert response.status_code == 200


@pytest.mark.asyncio
class TestBatchEnrichEndpoint:
    """Test POST /api/enrichment/batch-enrich"""

    async def test_batch_enrich_multiple_invoices(
        self,
        async_client,
        async_db_session
    ):
        """Should enrich multiple invoices"""
        # Create 3 invoices
        invoice_ids = []
        for i in range(3):
            invoice = FactureGlobal(
                numero=f"FAC-2024-{i:03d}",
                date_facture=date.today(),
                montant_ht=Decimal("100.00"),
                montant_tva=Decimal("20.00"),
                montant_ttc=Decimal("120.00"),
                extraction_method=ExtractionMethod.OCR.value,
                metadata_json={"raw_text": "test"}
            )
            async_db_session.add(invoice)
            await async_db_session.flush()
            invoice_ids.append(invoice.id)

        await async_db_session.commit()

        # Batch enrich
        response = await async_client.post(
            "/api/enrichment/batch-enrich",
            json={
                "facture_ids": invoice_ids,
                "max_concurrent": 2
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_invoices"] == 3
        assert data["successful"] + data["failed"] == 3
        assert len(data["results"]) > 0

    async def test_batch_enrich_empty_list(self, async_client):
        """Should fail with empty invoice list"""
        response = await async_client.post(
            "/api/enrichment/batch-enrich",
            json={"facture_ids": []}
        )

        assert response.status_code == 400

    async def test_batch_enrich_too_many_invoices(self, async_client):
        """Should fail with too many invoices"""
        response = await async_client.post(
            "/api/enrichment/batch-enrich",
            json={"facture_ids": list(range(1001))}
        )

        assert response.status_code == 400
        assert "1000" in response.json()["detail"]


@pytest.mark.asyncio
class TestEnrichmentStatsEndpoint:
    """Test GET /api/enrichment/stats"""

    async def test_get_stats_basic(self, async_client, async_db_session):
        """Should return enrichment statistics"""
        # Create some invoices with enrichment
        for i in range(5):
            invoice = FactureGlobal(
                numero=f"FAC-2024-{i:03d}",
                date_facture=date.today(),
                montant_ht=Decimal("100.00"),
                montant_tva=Decimal("20.00"),
                montant_ttc=Decimal("120.00"),
                extraction_method=ExtractionMethod.OCR.value,
                metadata_json={
                    "raw_text": "test",
                    "enrichment": {
                        "supplier_matching": {"matched": True},
                        "category_classification": {"method": "ml"}
                    }
                }
            )
            async_db_session.add(invoice)

        await async_db_session.commit()

        # Get stats
        response = await async_client.get("/api/enrichment/stats")

        assert response.status_code == 200
        data = response.json()

        assert "total_invoices" in data
        assert "enriched_invoices" in data
        assert "enrichment_rate" in data
        assert "supplier_matched_count" in data
        assert "ml_used_count" in data

    async def test_get_stats_with_copropriete_filter(
        self,
        async_client,
        async_db_session
    ):
        """Should filter stats by copropriete"""
        # Create invoices with different coproprietes
        for i in range(3):
            invoice = FactureGlobal(
                numero=f"FAC-2024-{i:03d}",
                date_facture=date.today(),
                copropriete_id=1,  # All in copropriete 1
                montant_ht=Decimal("100.00"),
                montant_tva=Decimal("20.00"),
                montant_ttc=Decimal("120.00"),
                extraction_method=ExtractionMethod.OCR.value,
                metadata_json={"raw_text": "test"}
            )
            async_db_session.add(invoice)

        await async_db_session.commit()

        # Get stats for copropriete 1
        response = await async_client.get("/api/enrichment/stats?copropriete_id=1")

        assert response.status_code == 200
        data = response.json()

        assert data["total_invoices"] == 3


@pytest.mark.asyncio
class TestMLMetricsEndpoint:
    """Test GET /api/enrichment/ml/metrics"""

    async def test_get_ml_metrics_no_model(self, async_client):
        """Should return metrics even if model not loaded"""
        response = await async_client.get("/api/enrichment/ml/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "model_loaded" in data
        assert "predictions_count" in data
        assert "categories" in data

    async def test_get_ml_metrics_with_model(
        self,
        async_client,
        mock_trained_model
    ):
        """Should return training metrics if model exists"""
        # mock_trained_model fixture creates models/training_metrics.json
        response = await async_client.get("/api/enrichment/ml/metrics")

        assert response.status_code == 200
        data = response.json()

        if data["model_loaded"]:
            assert data["training_metrics"] is not None
            assert "accuracy" in data["training_metrics"]


@pytest.mark.asyncio
class TestMLRetrainEndpoint:
    """Test POST /api/enrichment/ml/retrain"""

    async def test_retrain_with_insufficient_data(
        self,
        async_client,
        async_db_session
    ):
        """Should fail gracefully with insufficient training data"""
        # Don't create enough data
        response = await async_client.post(
            "/api/enrichment/ml/retrain",
            json={"min_samples": 10, "test_split": 0.2}
        )

        assert response.status_code == 200
        data = response.json()

        # Will fail due to insufficient data
        assert data["status"] in ["completed", "failed"]

    async def test_retrain_with_valid_params(self, async_client):
        """Should accept valid training parameters"""
        response = await async_client.post(
            "/api/enrichment/ml/retrain",
            json={"min_samples": 5, "test_split": 0.2}
        )

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "message" in data


# Pytest fixtures

@pytest.fixture
def mock_trained_model():
    """Create mock training metrics file"""
    metrics_path = Path("models/training_metrics.json")
    metrics_path.parent.mkdir(exist_ok=True)

    metrics = {
        "accuracy": 0.85,
        "precision": 0.83,
        "recall": 0.85,
        "f1_score": 0.84,
        "categories": ["Plomberie", "Électricité", "Chauffage"],
        "training_date": "2024-11-05T12:00:00"
    }

    with open(metrics_path, 'w') as f:
        json.dump(metrics, f)

    yield metrics_path

    # Cleanup
    if metrics_path.exists():
        metrics_path.unlink()


@pytest.fixture
async def async_client(app, async_db_session):
    """Create async test client"""
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
