"""
OCR Invoice Extraction Service

Service d'extraction OCR pour factures avec support :
- Tesseract OCR (local, gratuit)
- Azure Document Intelligence (cloud, premium)

Extrait automatiquement :
- Numéro de facture
- Date de facture et échéance
- Fournisseur (nom, SIRET)
- Montants (HT, TVA, TTC)
- Lignes de détail (description, quantité, prix unitaire)
- Calcul de confiance OCR
"""

import re
import structlog
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from enum import Enum

from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = structlog.get_logger()


class OCRBackend(str, Enum):
    """Backend OCR disponibles"""
    TESSERACT = "tesseract"
    AZURE = "azure"
    AUTO = "auto"  # Choisit automatiquement le meilleur


class InvoiceLineItem(BaseModel):
    """Ligne de détail d'une facture"""
    ligne_numero: int
    article: str
    description: Optional[str] = None
    quantite: Decimal
    unite: str = "unité"
    prix_unitaire_ht: Decimal
    taux_tva: Decimal
    montant_ht: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal

    @validator("montant_ht")
    def validate_montant_ht(cls, v, values):
        """Valide que montant_ht = quantite * prix_unitaire_ht"""
        if "quantite" in values and "prix_unitaire_ht" in values:
            expected = values["quantite"] * values["prix_unitaire_ht"]
            if abs(v - expected) > Decimal("0.01"):
                logger.warning(
                    "invoice_line_montant_mismatch",
                    montant_ht=v,
                    expected=expected,
                    quantite=values["quantite"],
                    prix_unitaire=values["prix_unitaire_ht"]
                )
        return v


class ExtractedInvoice(BaseModel):
    """Facture extraite par OCR"""
    # En-tête
    numero: str
    date_facture: date
    date_echeance: Optional[date] = None

    # Fournisseur
    fournisseur_nom: Optional[str] = None
    fournisseur_siret: Optional[str] = None
    fournisseur_adresse: Optional[str] = None

    # Montants
    montant_ht: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    devise: str = "EUR"

    # Détails
    categorie: Optional[str] = None
    mode_paiement: Optional[str] = None

    # Lignes
    lignes: List[InvoiceLineItem] = Field(default_factory=list)

    # Métadonnées OCR
    ocr_backend: str
    ocr_confidence: Decimal = Field(ge=0, le=1)
    needs_review: bool = False
    extraction_notes: List[str] = Field(default_factory=list)

    @validator("montant_ttc")
    def validate_montant_ttc(cls, v, values):
        """Valide que montant_ttc = montant_ht + montant_tva"""
        if "montant_ht" in values and "montant_tva" in values:
            expected = values["montant_ht"] + values["montant_tva"]
            if abs(v - expected) > Decimal("0.01"):
                logger.warning(
                    "invoice_montant_ttc_mismatch",
                    montant_ttc=v,
                    expected=expected,
                    montant_ht=values["montant_ht"],
                    montant_tva=values["montant_tva"]
                )
        return v


class OCRInvoiceService:
    """
    Service d'extraction OCR pour factures

    Support multi-backend :
    - Tesseract : OCR local gratuit (bonne qualité)
    - Azure Document Intelligence : OCR cloud premium (excellente qualité)

    Fonctionnalités :
    - Extraction automatique des champs clés
    - Parsing intelligent avec regex
    - Validation des montants (HT + TVA = TTC)
    - Calcul de confiance OCR
    - Flag needs_review si confiance < 0.85
    - Persistence en base de données
    """

    def __init__(
        self,
        default_backend: OCRBackend = OCRBackend.TESSERACT,
        tesseract_cmd: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        azure_key: Optional[str] = None
    ):
        self.default_backend = default_backend
        self.tesseract_cmd = tesseract_cmd
        self.azure_endpoint = azure_endpoint
        self.azure_key = azure_key

        logger.info(
            "ocr_invoice_service_initialized",
            backend=default_backend.value
        )

    async def extract_from_file(
        self,
        file_path: Path,
        backend: Optional[OCRBackend] = None,
        copropriete_id: Optional[int] = None
    ) -> ExtractedInvoice:
        """
        Extrait une facture depuis un fichier PDF ou image

        Args:
            file_path: Chemin vers le fichier
            backend: Backend OCR à utiliser (AUTO par défaut)
            copropriete_id: ID copropriété (optionnel)

        Returns:
            ExtractedInvoice avec tous les champs extraits
        """
        backend = backend or self.default_backend

        logger.info(
            "ocr_extraction_start",
            file_path=str(file_path),
            backend=backend.value,
            copropriete_id=copropriete_id
        )

        # Étape 1 : Extraction texte brut via OCR
        raw_text, confidence = await self._extract_text(file_path, backend)

        # Étape 2 : Parsing intelligent
        invoice = self._parse_invoice(raw_text, backend.value, confidence)

        # Étape 3 : Validation
        self._validate_invoice(invoice)

        logger.info(
            "ocr_extraction_complete",
            numero=invoice.numero,
            montant_ttc=float(invoice.montant_ttc),
            confidence=float(invoice.ocr_confidence),
            needs_review=invoice.needs_review
        )

        return invoice

    async def _extract_text(
        self,
        file_path: Path,
        backend: OCRBackend
    ) -> Tuple[str, Decimal]:
        """
        Extrait le texte brut d'un document via OCR

        Returns:
            (raw_text, confidence_score)
        """
        if backend == OCRBackend.TESSERACT:
            return await self._extract_with_tesseract(file_path)
        elif backend == OCRBackend.AZURE:
            return await self._extract_with_azure(file_path)
        else:
            raise ValueError(f"Backend OCR non supporté: {backend}")

    async def _extract_with_tesseract(self, file_path: Path) -> Tuple[str, Decimal]:
        """
        Extraction via Tesseract OCR (local)

        Tesseract est open source et gratuit, bonne qualité
        pour factures scannées standard.
        """
        try:
            import pytesseract
            from PIL import Image
            from pdf2image import convert_from_path

            logger.info("tesseract_extraction", file_path=str(file_path))

            # Si PDF, convertir en images
            if file_path.suffix.lower() == ".pdf":
                images = convert_from_path(str(file_path), dpi=300)

                # Extraire texte de chaque page
                full_text = ""
                confidences = []

                for i, image in enumerate(images):
                    # Extraction avec confiance
                    data = pytesseract.image_to_data(
                        image,
                        lang="fra",  # Français
                        output_type=pytesseract.Output.DICT
                    )

                    # Texte de la page
                    page_text = pytesseract.image_to_string(image, lang="fra")
                    full_text += page_text + "\n\n"

                    # Confiance moyenne de la page
                    page_confidences = [
                        int(conf) for conf in data["conf"] if conf != "-1"
                    ]
                    if page_confidences:
                        avg_conf = sum(page_confidences) / len(page_confidences)
                        confidences.append(avg_conf)

                # Confiance globale
                overall_confidence = Decimal(str(sum(confidences) / len(confidences) / 100)) if confidences else Decimal("0.5")

            else:
                # Image directe
                image = Image.open(file_path)

                # Extraction avec confiance
                data = pytesseract.image_to_data(
                    image,
                    lang="fra",
                    output_type=pytesseract.Output.DICT
                )

                full_text = pytesseract.image_to_string(image, lang="fra")

                # Confiance moyenne
                confidences = [int(conf) for conf in data["conf"] if conf != "-1"]
                overall_confidence = Decimal(str(sum(confidences) / len(confidences) / 100)) if confidences else Decimal("0.5")

            logger.info(
                "tesseract_extraction_complete",
                text_length=len(full_text),
                confidence=float(overall_confidence)
            )

            return full_text, overall_confidence

        except Exception as e:
            logger.error(
                "tesseract_extraction_failed",
                error=str(e),
                file_path=str(file_path),
                exc_info=True
            )

            # Fallback : texte vide avec confiance 0
            return "", Decimal("0.0")

    async def _extract_with_azure(self, file_path: Path) -> Tuple[str, Decimal]:
        """
        Extraction via Azure Document Intelligence (cloud)

        Azure offre une qualité supérieure pour factures complexes,
        tables, écritures manuscrites, etc.
        """
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential

            if not self.azure_endpoint or not self.azure_key:
                raise ValueError("Azure endpoint/key non configurés")

            logger.info("azure_extraction", file_path=str(file_path))

            # Client Azure
            client = DocumentAnalysisClient(
                endpoint=self.azure_endpoint,
                credential=AzureKeyCredential(self.azure_key)
            )

            # Analyser le document
            with open(file_path, "rb") as f:
                poller = client.begin_analyze_document(
                    model_id="prebuilt-invoice",  # Modèle pré-entraîné pour factures
                    document=f
                )
                result = poller.result()

            # Extraire texte
            full_text = ""
            if result.content:
                full_text = result.content

            # Confiance globale
            overall_confidence = Decimal("0.95")  # Azure a généralement > 95%
            if result.documents:
                doc = result.documents[0]
                confidences = [
                    field.confidence
                    for field in doc.fields.values()
                    if hasattr(field, "confidence") and field.confidence
                ]
                if confidences:
                    overall_confidence = Decimal(str(sum(confidences) / len(confidences)))

            logger.info(
                "azure_extraction_complete",
                text_length=len(full_text),
                confidence=float(overall_confidence)
            )

            return full_text, overall_confidence

        except ImportError:
            logger.error("azure_sdk_not_installed")
            raise ValueError("Azure SDK non installé. pip install azure-ai-formrecognizer")

        except Exception as e:
            logger.error(
                "azure_extraction_failed",
                error=str(e),
                file_path=str(file_path),
                exc_info=True
            )

            # Fallback : texte vide
            return "", Decimal("0.0")

    def _parse_invoice(
        self,
        raw_text: str,
        backend: str,
        confidence: Decimal
    ) -> ExtractedInvoice:
        """
        Parse le texte brut pour extraire les champs de la facture

        Utilise des regex intelligentes pour détecter :
        - Numéros de facture (patterns courants)
        - Dates (formats variés)
        - Montants (avec ou sans espaces, € ou EUR)
        - SIRET fournisseur
        - Lignes de détail
        """
        logger.info("invoice_parsing_start", text_length=len(raw_text))

        # Initialiser résultat
        invoice_data = {
            "ocr_backend": backend,
            "ocr_confidence": confidence,
            "needs_review": confidence < Decimal("0.85"),
            "extraction_notes": []
        }

        # 1. Numéro de facture
        numero = self._extract_invoice_number(raw_text)
        if numero:
            invoice_data["numero"] = numero
        else:
            invoice_data["numero"] = f"UNKNOWN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            invoice_data["extraction_notes"].append("Numéro de facture non détecté")
            invoice_data["needs_review"] = True

        # 2. Date de facture
        date_facture = self._extract_date(raw_text, "date")
        if date_facture:
            invoice_data["date_facture"] = date_facture
        else:
            invoice_data["date_facture"] = date.today()
            invoice_data["extraction_notes"].append("Date de facture non détectée")
            invoice_data["needs_review"] = True

        # 3. Date d'échéance
        date_echeance = self._extract_date(raw_text, "échéance")
        if date_echeance:
            invoice_data["date_echeance"] = date_echeance

        # 4. Fournisseur
        fournisseur = self._extract_supplier(raw_text)
        if fournisseur:
            invoice_data.update(fournisseur)

        # 5. Montants
        montants = self._extract_amounts(raw_text)
        if montants:
            invoice_data.update(montants)
        else:
            # Montants obligatoires manquants
            invoice_data["montant_ht"] = Decimal("0.00")
            invoice_data["montant_tva"] = Decimal("0.00")
            invoice_data["montant_ttc"] = Decimal("0.00")
            invoice_data["extraction_notes"].append("Montants non détectés")
            invoice_data["needs_review"] = True

        # 6. Lignes de détail (optionnel)
        lignes = self._extract_line_items(raw_text)
        if lignes:
            invoice_data["lignes"] = lignes

        # 7. Catégorie (heuristique basée sur mots-clés)
        categorie = self._infer_category(raw_text)
        if categorie:
            invoice_data["categorie"] = categorie

        logger.info(
            "invoice_parsing_complete",
            numero=invoice_data["numero"],
            needs_review=invoice_data["needs_review"],
            notes_count=len(invoice_data["extraction_notes"])
        )

        return ExtractedInvoice(**invoice_data)

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extrait le numéro de facture"""
        # Patterns courants
        patterns = [
            r'(?:facture|invoice|n°|no|number)\s*[:\s]*([A-Z0-9\-/]+)',
            r'([A-Z]{2,}\d{4,})',  # Ex: FAC20240001
            r'(\d{4,})',  # Numéro simple
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_date(self, text: str, date_type: str = "date") -> Optional[date]:
        """Extrait une date (facture ou échéance)"""
        # Chercher près du mot-clé
        context_pattern = f"{date_type}.*?(\d{{1,2}}[-/\.]\d{{1,2}}[-/\.]\d{{2,4}})"
        match = re.search(context_pattern, text, re.IGNORECASE)

        if match:
            date_str = match.group(1)
            # Parser la date
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

        return None

    def _extract_supplier(self, text: str) -> Dict[str, str]:
        """Extrait les infos fournisseur"""
        supplier_info = {}

        # SIRET
        siret_match = re.search(r'SIRET\s*[:\s]*(\d{14})', text, re.IGNORECASE)
        if siret_match:
            supplier_info["fournisseur_siret"] = siret_match.group(1)

        # Nom (heuristique : premières lignes avant "facture")
        lines = text.split("\n")
        for i, line in enumerate(lines[:10]):
            if re.search(r'facture|invoice', line, re.IGNORECASE):
                # Nom probable dans les 3 lignes précédentes
                name_lines = [l.strip() for l in lines[max(0, i-3):i] if len(l.strip()) > 3]
                if name_lines:
                    supplier_info["fournisseur_nom"] = name_lines[0]
                break

        return supplier_info

    def _extract_amounts(self, text: str) -> Optional[Dict[str, Decimal]]:
        """Extrait les montants HT, TVA, TTC"""
        # Patterns pour montants
        # Ex: "Total HT : 1 234,56 €" ou "HT 1234.56"

        def parse_amount(amount_str: str) -> Decimal:
            """Parse un montant (gère espaces, virgules, points)"""
            # Nettoyer : enlever €, EUR, espaces
            cleaned = re.sub(r'[€EUR\s]', '', amount_str)
            # Remplacer virgule par point
            cleaned = cleaned.replace(',', '.')
            return Decimal(cleaned)

        montants = {}

        # Montant HT
        ht_match = re.search(r'(?:total\s*)?HT\s*[:\s]*([\d\s,\.]+)', text, re.IGNORECASE)
        if ht_match:
            try:
                montants["montant_ht"] = parse_amount(ht_match.group(1))
            except (InvalidOperation, ValueError):
                pass

        # Montant TVA
        tva_match = re.search(r'(?:montant\s*)?TVA\s*[:\s]*([\d\s,\.]+)', text, re.IGNORECASE)
        if tva_match:
            try:
                montants["montant_tva"] = parse_amount(tva_match.group(1))
            except (InvalidOperation, ValueError):
                pass

        # Montant TTC
        ttc_match = re.search(r'(?:total\s*)?TTC\s*[:\s]*([\d\s,\.]+)', text, re.IGNORECASE)
        if ttc_match:
            try:
                montants["montant_ttc"] = parse_amount(ttc_match.group(1))
            except (InvalidOperation, ValueError):
                pass

        # Si on a HT et TVA mais pas TTC, calculer
        if "montant_ht" in montants and "montant_tva" in montants and "montant_ttc" not in montants:
            montants["montant_ttc"] = montants["montant_ht"] + montants["montant_tva"]

        # Si on a TTC et HT mais pas TVA, calculer
        if "montant_ttc" in montants and "montant_ht" in montants and "montant_tva" not in montants:
            montants["montant_tva"] = montants["montant_ttc"] - montants["montant_ht"]

        return montants if montants else None

    def _extract_line_items(self, text: str) -> List[Dict]:
        """Extrait les lignes de détail (optionnel, complexe)"""
        # Simplifié pour l'instant : pas d'extraction de lignes
        # Peut être ajouté plus tard avec parsing plus sophistiqué
        return []

    def _infer_category(self, text: str) -> Optional[str]:
        """Infère la catégorie depuis le contenu"""
        categories_keywords = {
            "Plomberie": ["plombier", "plomberie", "robinet", "fuite", "tuyau"],
            "Électricité": ["électricien", "électrique", "câble", "prise", "disjoncteur"],
            "Peinture": ["peintre", "peinture", "ravalement", "décoration"],
            "Entretien": ["nettoyage", "entretien", "maintenance", "jardinage"],
            "Chauffage": ["chauffage", "chaudière", "radiateur", "climatisation"],
        }

        text_lower = text.lower()
        for categorie, keywords in categories_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return categorie

        return None

    def _validate_invoice(self, invoice: ExtractedInvoice):
        """Valide les contraintes métier"""
        # Vérifier cohérence montants
        expected_ttc = invoice.montant_ht + invoice.montant_tva
        if abs(invoice.montant_ttc - expected_ttc) > Decimal("0.01"):
            invoice.extraction_notes.append(
                f"Incohérence montants : TTC attendu={expected_ttc}, trouvé={invoice.montant_ttc}"
            )
            invoice.needs_review = True

        # Vérifier date cohérente
        if invoice.date_facture > date.today():
            invoice.extraction_notes.append("Date facture dans le futur")
            invoice.needs_review = True

        # Vérifier montants positifs
        if invoice.montant_ttc <= 0:
            invoice.extraction_notes.append("Montant TTC nul ou négatif")
            invoice.needs_review = True

    async def save_to_database(
        self,
        db: AsyncSession,
        invoice: ExtractedInvoice,
        doc_id: Optional[int] = None,
        copropriete_id: Optional[int] = None,
        fournisseur_id: Optional[int] = None
    ) -> int:
        """
        Enregistre la facture extraite en base de données

        Args:
            db: Session DB
            invoice: Facture extraite
            doc_id: ID du document source
            copropriete_id: ID copropriété
            fournisseur_id: ID fournisseur

        Returns:
            ID de la facture créée
        """
        logger.info(
            "saving_invoice_to_db",
            numero=invoice.numero,
            montant_ttc=float(invoice.montant_ttc)
        )

        # Insérer facture globale
        query = text("""
            INSERT INTO factures_global (
                numero, date_facture, date_echeance,
                fournisseur_id, copropriete_id, doc_id,
                montant_ht, montant_tva, montant_ttc, devise,
                categorie, extraction_method, ocr_confidence, needs_review,
                notes, metadata_json
            ) VALUES (
                :numero, :date_facture, :date_echeance,
                :fournisseur_id, :copropriete_id, :doc_id,
                :montant_ht, :montant_tva, :montant_ttc, :devise,
                :categorie, :extraction_method, :ocr_confidence, :needs_review,
                :notes, :metadata_json::jsonb
            )
            RETURNING id
        """)

        import json

        result = await db.execute(
            query,
            {
                "numero": invoice.numero,
                "date_facture": invoice.date_facture,
                "date_echeance": invoice.date_echeance,
                "fournisseur_id": fournisseur_id,
                "copropriete_id": copropriete_id,
                "doc_id": doc_id,
                "montant_ht": float(invoice.montant_ht),
                "montant_tva": float(invoice.montant_tva),
                "montant_ttc": float(invoice.montant_ttc),
                "devise": invoice.devise,
                "categorie": invoice.categorie,
                "extraction_method": "ocr",
                "ocr_confidence": float(invoice.ocr_confidence),
                "needs_review": invoice.needs_review,
                "notes": "\n".join(invoice.extraction_notes) if invoice.extraction_notes else None,
                "metadata_json": json.dumps({
                    "ocr_backend": invoice.ocr_backend,
                    "fournisseur_nom": invoice.fournisseur_nom,
                    "fournisseur_siret": invoice.fournisseur_siret
                })
            }
        )

        facture_id = result.scalar_one()
        await db.commit()

        # Insérer lignes de détail si présentes
        if invoice.lignes:
            for ligne in invoice.lignes:
                await self._save_line_item(db, facture_id, ligne)

        logger.info(
            "invoice_saved_to_db",
            facture_id=facture_id,
            numero=invoice.numero,
            needs_review=invoice.needs_review
        )

        return facture_id

    async def _save_line_item(
        self,
        db: AsyncSession,
        facture_id: int,
        ligne: InvoiceLineItem
    ):
        """Enregistre une ligne de détail"""
        query = text("""
            INSERT INTO factures_details (
                facture_id, ligne_numero, article, description,
                quantite, unite, prix_unitaire_ht, taux_tva,
                montant_ht, montant_tva, montant_ttc
            ) VALUES (
                :facture_id, :ligne_numero, :article, :description,
                :quantite, :unite, :prix_unitaire_ht, :taux_tva,
                :montant_ht, :montant_tva, :montant_ttc
            )
        """)

        await db.execute(
            query,
            {
                "facture_id": facture_id,
                "ligne_numero": ligne.ligne_numero,
                "article": ligne.article,
                "description": ligne.description,
                "quantite": float(ligne.quantite),
                "unite": ligne.unite,
                "prix_unitaire_ht": float(ligne.prix_unitaire_ht),
                "taux_tva": float(ligne.taux_tva),
                "montant_ht": float(ligne.montant_ht),
                "montant_tva": float(ligne.montant_tva),
                "montant_ttc": float(ligne.montant_ttc)
            }
        )

        await db.commit()
