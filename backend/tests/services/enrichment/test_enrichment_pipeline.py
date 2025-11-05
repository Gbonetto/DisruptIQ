"""
Tests for EnrichmentPipeline integration
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta

from app.services.enrichment_pipeline import EnrichmentPipeline
from app.models.enrichment import EnrichmentConfig
from app.models.invoice import FactureGlobal, FactureStatut, ExtractionMethod
from app.models.professionnel import Professionnel


@pytest.mark.asyncio
class TestEnrichmentPipeline:
    """Integration tests for enrichment pipeline"""

    async def test_full_enrichment_with_supplier_match(
        self,
        async_db_session,
        sample_invoice_data
    ):
        """Should enrich invoice with supplier matching"""
        # Create supplier with known SIRET
        supplier = Professionnel(
            name="Plomberie Martin",
            email="martin@plomberie.fr",
            siret="98765432101234",
            category="Plomberie",
            statut="active"
        )
        async_db_session.add(supplier)
        await async_db_session.commit()

        # Create invoice with SIRET in metadata
        invoice = FactureGlobal(
            numero="FAC-2024-001",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={
                "siret": "98765432101234",  # Matches supplier
                "raw_text": "Facture plomberie robinet fuite"
            }
        )
        async_db_session.add(invoice)
        await async_db_session.commit()
        await async_db_session.refresh(invoice)

        # Run enrichment
        pipeline = EnrichmentPipeline(
            db=async_db_session,
            config=EnrichmentConfig()
        )
        result = await pipeline.enrich_invoice(invoice.id)

        # Verify
        assert result.success is True
        assert result.supplier_matching is not None
        assert result.supplier_matching.matched is True
        assert result.supplier_matching.fournisseur_id == supplier.id

        # Reload invoice to check updates
        await async_db_session.refresh(invoice)
        assert invoice.fournisseur_id == supplier.id
        assert "enrichment" in invoice.metadata_json

    async def test_duplicate_detection_strict(
        self,
        async_db_session
    ):
        """Should detect strict duplicate (same numero + fournisseur)"""
        # Create supplier
        supplier = Professionnel(
            name="Électricité Pro",
            email="pro@electricite.fr",
            category="Électricité",
            statut="active"
        )
        async_db_session.add(supplier)
        await async_db_session.commit()

        # Create first invoice
        invoice1 = FactureGlobal(
            numero="ELEC-2024-100",
            date_facture=date.today(),
            fournisseur_id=supplier.id,
            montant_ht=Decimal("200.00"),
            montant_tva=Decimal("40.00"),
            montant_ttc=Decimal("240.00"),
            extraction_method=ExtractionMethod.OCR.value
        )
        async_db_session.add(invoice1)
        await async_db_session.commit()

        # Create duplicate invoice (same numero + fournisseur)
        invoice2 = FactureGlobal(
            numero="ELEC-2024-100",  # SAME numero
            date_facture=date.today() + timedelta(days=1),
            fournisseur_id=supplier.id,  # SAME fournisseur
            montant_ht=Decimal("200.00"),
            montant_tva=Decimal("40.00"),
            montant_ttc=Decimal("240.00"),
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={"raw_text": "test"}
        )
        async_db_session.add(invoice2)
        await async_db_session.commit()
        await async_db_session.refresh(invoice2)

        # Run enrichment on second invoice
        pipeline = EnrichmentPipeline(db=async_db_session)
        result = await pipeline.enrich_invoice(invoice2.id)

        # Verify duplicate detected
        assert result.duplicate_detection is not None
        assert result.duplicate_detection.is_duplicate is True
        assert invoice1.id in result.duplicate_detection.existing_facture_ids

        # Should flag for review
        await async_db_session.refresh(invoice2)
        assert invoice2.needs_review is True

    async def test_category_classification_keyword(
        self,
        async_db_session
    ):
        """Should classify category using keywords"""
        invoice = FactureGlobal(
            numero="FAC-2024-001",
            date_facture=date.today(),
            montant_ht=Decimal("150.00"),
            montant_tva=Decimal("30.00"),
            montant_ttc=Decimal("180.00"),
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={
                "raw_text": "Réparation plomberie fuite robinet évier"
            }
        )
        async_db_session.add(invoice)
        await async_db_session.commit()
        await async_db_session.refresh(invoice)

        # Run enrichment
        pipeline = EnrichmentPipeline(db=async_db_session)
        result = await pipeline.enrich_invoice(invoice.id)

        # Verify classification
        assert result.category_classification is not None
        assert result.category_classification.predicted_category == "Plomberie"

        # Should auto-set category if confidence high enough
        await async_db_session.refresh(invoice)
        assert invoice.categorie == "Plomberie"

    async def test_anomaly_detection_high_threshold(
        self,
        async_db_session
    ):
        """Should detect anomaly for high-value invoice"""
        invoice = FactureGlobal(
            numero="FAC-2024-BIG",
            date_facture=date.today(),
            montant_ht=Decimal("12000.00"),
            montant_tva=Decimal("2400.00"),
            montant_ttc=Decimal("14400.00"),  # > 10,000€ threshold
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={"raw_text": "test"}
        )
        async_db_session.add(invoice)
        await async_db_session.commit()
        await async_db_session.refresh(invoice)

        # Run enrichment
        pipeline = EnrichmentPipeline(db=async_db_session)
        result = await pipeline.enrich_invoice(invoice.id)

        # Verify anomaly detected
        assert result.anomaly_detection is not None
        assert result.anomaly_detection.is_anomaly is True
        assert result.anomaly_detection.severity in ["high", "critical"]

        # Should flag for review
        await async_db_session.refresh(invoice)
        assert invoice.needs_review is True

    async def test_anomaly_detection_zscore(
        self,
        async_db_session
    ):
        """Should detect anomaly using Z-score analysis"""
        # Create multiple invoices in same category for statistics
        for i in range(10):
            invoice = FactureGlobal(
                numero=f"FAC-2024-{i:03d}",
                date_facture=date.today() - timedelta(days=i),
                montant_ht=Decimal("100.00"),
                montant_tva=Decimal("20.00"),
                montant_ttc=Decimal("120.00"),  # Normal range
                categorie="Plomberie",
                extraction_method=ExtractionMethod.OCR.value
            )
            async_db_session.add(invoice)

        await async_db_session.commit()

        # Create outlier invoice (much higher amount)
        outlier = FactureGlobal(
            numero="FAC-2024-OUTLIER",
            date_facture=date.today(),
            montant_ht=Decimal("5000.00"),
            montant_tva=Decimal("1000.00"),
            montant_ttc=Decimal("6000.00"),  # WAY above average
            categorie="Plomberie",
            extraction_method=ExtractionMethod.OCR.value,
            metadata_json={"raw_text": "test"}
        )
        async_db_session.add(outlier)
        await async_db_session.commit()
        await async_db_session.refresh(outlier)

        # Run enrichment
        pipeline = EnrichmentPipeline(db=async_db_session)
        result = await pipeline.enrich_invoice(outlier.id)

        # Verify Z-score anomaly detected
        assert result.anomaly_detection is not None
        assert result.anomaly_detection.is_anomaly is True
        assert result.anomaly_detection.zscore is not None
        assert abs(result.anomaly_detection.zscore) > 3.0

    async def test_enrichment_config_customization(
        self,
        async_db_session
    ):
        """Should respect custom config settings"""
        invoice = FactureGlobal(
            numero="FAC-2024-001",
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

        # Custom config: disable category classification
        config = EnrichmentConfig(
            enable_category_classification=False,
            enable_anomaly_detection=True
        )

        pipeline = EnrichmentPipeline(db=async_db_session, config=config)
        result = await pipeline.enrich_invoice(invoice.id)

        # Category classification should be skipped
        assert result.category_classification is None
        # But anomaly detection should run
        assert result.anomaly_detection is not None

    async def test_enrichment_failure_handling(
        self,
        async_db_session
    ):
        """Should handle enrichment failures gracefully"""
        # Run enrichment on non-existent invoice
        pipeline = EnrichmentPipeline(db=async_db_session)
        result = await pipeline.enrich_invoice(facture_id=99999)

        # Should return error result, not crash
        assert result.success is False
        assert result.error_message is not None


# Pytest fixtures

@pytest.fixture
def sample_invoice_data():
    """Sample invoice data for testing"""
    return {
        "numero": "FAC-2024-001",
        "date_facture": date.today(),
        "montant_ht": Decimal("100.00"),
        "montant_tva": Decimal("20.00"),
        "montant_ttc": Decimal("120.00"),
        "categorie": None,
        "needs_review": False
    }
