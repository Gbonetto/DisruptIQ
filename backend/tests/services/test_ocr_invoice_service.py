"""
Tests for OCR Invoice Extraction Service

Tests extraction, parsing, validation
"""

import pytest
from pathlib import Path
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, AsyncMock, patch

from app.services.ocr_invoice_service import (
    OCRInvoiceService,
    OCRBackend,
    ExtractedInvoice,
    InvoiceLineItem
)


class TestOCRInvoiceService:
    """Test OCR invoice extraction service"""

    def test_service_initialization(self):
        """Test service init"""
        service = OCRInvoiceService(default_backend=OCRBackend.TESSERACT)

        assert service.default_backend == OCRBackend.TESSERACT
        assert service.tesseract_cmd is None

    def test_extract_invoice_number(self):
        """Test extraction du numéro de facture"""
        service = OCRInvoiceService()

        # Test patterns courants
        tests = [
            ("Facture N° FAC20240001", "FAC20240001"),
            ("INVOICE NUMBER: INV-2024-123", "INV-2024-123"),
            ("Facture: 123456", "123456"),
            ("No facture 2024/001", "2024"),  # Premier match
        ]

        for text, expected in tests:
            result = service._extract_invoice_number(text)
            assert result is not None, f"Failed for: {text}"
            assert expected in result or result == expected

    def test_extract_date(self):
        """Test extraction de dates"""
        service = OCRInvoiceService()

        # Test formats variés
        tests = [
            ("Date: 15/01/2024", date(2024, 1, 15)),
            ("Date facture: 01-02-2024", date(2024, 2, 1)),
            ("Date: 31.12.2023", date(2023, 12, 31)),
        ]

        for text, expected in tests:
            result = service._extract_date(text, "date")
            assert result == expected, f"Failed for: {text}"

    def test_extract_amounts(self):
        """Test extraction des montants"""
        service = OCRInvoiceService()

        # Test extraction
        text = """
        Montant HT : 1 234,56 €
        TVA (20%) : 246,91 €
        Total TTC : 1 481,47 €
        """

        montants = service._extract_amounts(text)

        assert montants is not None
        assert montants["montant_ht"] == Decimal("1234.56")
        assert montants["montant_tva"] == Decimal("246.91")
        assert montants["montant_ttc"] == Decimal("1481.47")

    def test_extract_amounts_with_calculation(self):
        """Test calcul automatique si montant manquant"""
        service = OCRInvoiceService()

        # Seulement HT et TVA
        text = """
        Total HT: 100.00
        TVA: 20.00
        """

        montants = service._extract_amounts(text)

        assert montants["montant_ht"] == Decimal("100.00")
        assert montants["montant_tva"] == Decimal("20.00")
        assert montants["montant_ttc"] == Decimal("120.00")  # Calculé

    def test_extract_supplier(self):
        """Test extraction fournisseur"""
        service = OCRInvoiceService()

        text = """
        PLOMBERIE DUPONT
        123 Rue de la Paix
        SIRET: 12345678901234

        FACTURE N° 001
        """

        supplier = service._extract_supplier(text)

        assert supplier.get("fournisseur_siret") == "12345678901234"
        # Nom peut varier selon parsing

    def test_infer_category(self):
        """Test inférence de catégorie"""
        service = OCRInvoiceService()

        tests = [
            ("Réparation tuyau fuite plombier", "Plomberie"),
            ("Installation électrique disjoncteur", "Électricité"),
            ("Entretien jardinage nettoyage", "Entretien"),
            ("Chaudière chauffage réparation", "Chauffage"),
        ]

        for text, expected_category in tests:
            result = service._infer_category(text)
            assert result == expected_category, f"Failed for: {text}"

    def test_parse_invoice_complete(self):
        """Test parsing complet d'une facture"""
        service = OCRInvoiceService()

        raw_text = """
        PLOMBERIE EXPERT
        SIRET: 98765432101234

        FACTURE N° FAC-2024-0042
        Date: 15/03/2024
        Date échéance: 15/04/2024

        Réparation fuite robinet cuisine

        Total HT: 450.00 EUR
        TVA 20%: 90.00 EUR
        Total TTC: 540.00 EUR
        """

        invoice = service._parse_invoice(raw_text, "tesseract", Decimal("0.92"))

        assert invoice.numero == "FAC-2024-0042"
        assert invoice.date_facture == date(2024, 3, 15)
        assert invoice.date_echeance == date(2024, 4, 15)
        assert invoice.montant_ht == Decimal("450.00")
        assert invoice.montant_tva == Decimal("90.00")
        assert invoice.montant_ttc == Decimal("540.00")
        assert invoice.fournisseur_siret == "98765432101234"
        assert invoice.ocr_backend == "tesseract"
        assert invoice.ocr_confidence == Decimal("0.92")

    def test_validate_invoice_success(self):
        """Test validation d'une facture valide"""
        service = OCRInvoiceService()

        invoice = ExtractedInvoice(
            numero="TEST001",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),  # Correct
            ocr_backend="tesseract",
            ocr_confidence=Decimal("0.95")
        )

        service._validate_invoice(invoice)

        # Pas d'erreurs
        assert len(invoice.extraction_notes) == 0
        assert invoice.needs_review == False

    def test_validate_invoice_montant_mismatch(self):
        """Test validation détecte incohérence montants"""
        service = OCRInvoiceService()

        invoice = ExtractedInvoice(
            numero="TEST002",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("999.00"),  # INCORRECT
            ocr_backend="tesseract",
            ocr_confidence=Decimal("0.95")
        )

        service._validate_invoice(invoice)

        # Erreur détectée
        assert len(invoice.extraction_notes) > 0
        assert invoice.needs_review == True
        assert "Incohérence montants" in invoice.extraction_notes[0]

    def test_validate_invoice_future_date(self):
        """Test validation détecte date future"""
        from datetime import timedelta

        service = OCRInvoiceService()

        invoice = ExtractedInvoice(
            numero="TEST003",
            date_facture=date.today() + timedelta(days=30),  # Futur
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),
            ocr_backend="tesseract",
            ocr_confidence=Decimal("0.95")
        )

        service._validate_invoice(invoice)

        # Erreur détectée
        assert len(invoice.extraction_notes) > 0
        assert invoice.needs_review == True

    def test_validate_invoice_zero_amount(self):
        """Test validation détecte montant nul"""
        service = OCRInvoiceService()

        invoice = ExtractedInvoice(
            numero="TEST004",
            date_facture=date.today(),
            montant_ht=Decimal("0.00"),
            montant_tva=Decimal("0.00"),
            montant_ttc=Decimal("0.00"),  # Nul
            ocr_backend="tesseract",
            ocr_confidence=Decimal("0.95")
        )

        service._validate_invoice(invoice)

        # Erreur détectée
        assert len(invoice.extraction_notes) > 0
        assert invoice.needs_review == True

    @pytest.mark.asyncio
    async def test_save_to_database(self):
        """Test enregistrement en base"""
        service = OCRInvoiceService()

        # Mock DB
        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one.return_value = 42  # facture_id
        mock_db.execute.return_value = mock_result

        invoice = ExtractedInvoice(
            numero="TEST-DB-001",
            date_facture=date(2024, 1, 15),
            montant_ht=Decimal("200.00"),
            montant_tva=Decimal("40.00"),
            montant_ttc=Decimal("240.00"),
            ocr_backend="tesseract",
            ocr_confidence=Decimal("0.88"),
            needs_review=False
        )

        facture_id = await service.save_to_database(
            db=mock_db,
            invoice=invoice,
            doc_id=10,
            copropriete_id=5,
            fournisseur_id=3
        )

        assert facture_id == 42
        assert mock_db.execute.called
        assert mock_db.commit.called

    def test_low_confidence_triggers_review(self):
        """Test que faible confiance déclenche needs_review"""
        service = OCRInvoiceService()

        raw_text = """
        FACTURE 001
        Date: 01/01/2024
        Total TTC: 100.00
        """

        invoice = service._parse_invoice(raw_text, "tesseract", Decimal("0.70"))  # Faible confiance

        # needs_review automatique
        assert invoice.needs_review == True
        assert invoice.ocr_confidence < Decimal("0.85")

    def test_missing_numero_triggers_review(self):
        """Test que numéro manquant déclenche needs_review"""
        service = OCRInvoiceService()

        raw_text = """
        Date: 01/01/2024
        Total TTC: 100.00
        """  # Pas de numéro

        invoice = service._parse_invoice(raw_text, "tesseract", Decimal("0.95"))

        assert invoice.needs_review == True
        assert "Numéro de facture non détecté" in invoice.extraction_notes


class TestInvoiceLineItem:
    """Test modèle ligne de détail"""

    def test_line_item_validation_success(self):
        """Test validation ligne correcte"""
        ligne = InvoiceLineItem(
            ligne_numero=1,
            article="Robinet",
            quantite=Decimal("2.0"),
            prix_unitaire_ht=Decimal("50.00"),
            taux_tva=Decimal("20.0"),
            montant_ht=Decimal("100.00"),  # 2 * 50 = 100
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00")
        )

        assert ligne.montant_ht == Decimal("100.00")

    def test_line_item_validation_warning(self):
        """Test validation détecte incohérence"""
        # Pydantic validator va loguer un warning mais pas raise
        ligne = InvoiceLineItem(
            ligne_numero=1,
            article="Robinet",
            quantite=Decimal("2.0"),
            prix_unitaire_ht=Decimal("50.00"),
            taux_tva=Decimal("20.0"),
            montant_ht=Decimal("999.00"),  # INCORRECT (devrait être 100)
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("1019.00")
        )

        # Ligne créée mais avec warning loggué
        assert ligne.ligne_numero == 1


class TestExtractedInvoice:
    """Test modèle facture extraite"""

    def test_invoice_validation_montant_ttc(self):
        """Test validation TTC = HT + TVA"""
        # Valid invoice
        invoice = ExtractedInvoice(
            numero="V001",
            date_facture=date.today(),
            montant_ht=Decimal("100.00"),
            montant_tva=Decimal("20.00"),
            montant_ttc=Decimal("120.00"),  # Correct
            ocr_backend="tesseract",
            ocr_confidence=Decimal("0.90")
        )

        assert invoice.montant_ttc == Decimal("120.00")

    def test_invoice_defaults(self):
        """Test valeurs par défaut"""
        invoice = ExtractedInvoice(
            numero="D001",
            date_facture=date.today(),
            montant_ht=Decimal("50.00"),
            montant_tva=Decimal("10.00"),
            montant_ttc=Decimal("60.00"),
            ocr_backend="azure",
            ocr_confidence=Decimal("0.98")
        )

        assert invoice.devise == "EUR"
        assert invoice.needs_review == False
        assert invoice.lignes == []
        assert invoice.extraction_notes == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
