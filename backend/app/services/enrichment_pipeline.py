"""
Enrichment Pipeline

Main orchestrator for automatic invoice enrichment.
Coordinates all enrichment services and updates invoices with enriched data.
"""

import time
from typing import Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import FactureGlobal
from app.models.enrichment import (
    EnrichmentConfig,
    EnrichmentResult
)
from app.services.enrichment.supplier_matcher import SupplierMatcher
from app.services.enrichment.duplicate_detector import DuplicateDetector
from app.services.enrichment.category_classifier import CategoryClassifier
from app.services.enrichment.anomaly_detector import AnomalyDetector

import structlog

logger = structlog.get_logger(__name__)


class EnrichmentPipeline:
    """
    Main orchestrator for invoice enrichment pipeline.

    Coordinates:
    1. Supplier matching (SIRET + fuzzy name)
    2. Duplicate detection
    3. Category classification (ML + keywords)
    4. Anomaly detection (statistical + business rules)
    """

    def __init__(
        self,
        db: AsyncSession,
        config: Optional[EnrichmentConfig] = None
    ):
        """
        Initialize enrichment pipeline.

        Args:
            db: Database session
            config: Configuration (uses defaults if not provided)
        """
        self.db = db
        self.config = config or EnrichmentConfig()
        self.logger = logger.bind(service="enrichment_pipeline")

        # Initialize services
        self.supplier_matcher = SupplierMatcher(
            db=db,
            fuzzy_threshold=self.config.supplier_matching_threshold
        )

        self.duplicate_detector = DuplicateDetector(
            db=db,
            date_tolerance_days=self.config.duplicate_date_tolerance_days,
            amount_tolerance=self.config.duplicate_amount_tolerance
        )

        self.category_classifier = CategoryClassifier.get_default_instance()

        self.anomaly_detector = AnomalyDetector(
            db=db,
            zscore_threshold=self.config.anomaly_zscore_threshold,
            threshold_high=self.config.anomaly_threshold_high,
            threshold_critical=self.config.anomaly_threshold_critical
        )

    async def enrich_invoice(
        self,
        facture_id: int
    ) -> EnrichmentResult:
        """
        Enrich an invoice with all enabled enrichment processes.

        Process:
        1. Load invoice from database
        2. Run supplier matching
        3. Run duplicate detection
        4. Run category classification
        5. Run anomaly detection
        6. Update invoice with enriched data
        7. Return enrichment result

        Args:
            facture_id: ID of the invoice to enrich

        Returns:
            EnrichmentResult with all enrichment details
        """
        start_time = time.time()

        self.logger.info(
            "starting_enrichment",
            facture_id=facture_id,
            config=self.config.dict()
        )

        result = EnrichmentResult(
            facture_id=facture_id,
            config=self.config
        )

        try:
            # Load invoice
            facture = await self._load_invoice(facture_id)
            if not facture:
                result.success = False
                result.error_message = f"Invoice {facture_id} not found"
                return result

            # Extract data from invoice for enrichment
            metadata = facture.metadata_json or {}
            raw_text = metadata.get("raw_text", "")

            # 1. Supplier Matching
            if self.config.enable_supplier_matching:
                result.supplier_matching = await self._run_supplier_matching(
                    facture=facture,
                    metadata=metadata
                )

            # 2. Duplicate Detection
            if self.config.enable_duplicate_detection:
                result.duplicate_detection = await self._run_duplicate_detection(
                    facture=facture
                )

            # 3. Category Classification
            if self.config.enable_category_classification:
                result.category_classification = await self._run_category_classification(
                    facture=facture,
                    raw_text=raw_text
                )

            # 4. Anomaly Detection
            if self.config.enable_anomaly_detection:
                result.anomaly_detection = await self._run_anomaly_detection(
                    facture=facture
                )

            # Update invoice with enrichment results
            await self._update_invoice(facture, result)

            # Calculate processing time
            result.processing_time_ms = (time.time() - start_time) * 1000

            self.logger.info(
                "enrichment_completed",
                facture_id=facture_id,
                processing_time_ms=result.processing_time_ms,
                actions_taken=len(result.actions_taken),
                warnings=len(result.warnings)
            )

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            self.logger.error(
                "enrichment_failed",
                facture_id=facture_id,
                error=str(e)
            )

        return result

    async def _load_invoice(self, facture_id: int) -> Optional[FactureGlobal]:
        """Load invoice from database"""
        query = select(FactureGlobal).where(FactureGlobal.id == facture_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def _run_supplier_matching(
        self,
        facture: FactureGlobal,
        metadata: dict
    ) -> Optional:
        """Run supplier matching process"""
        self.logger.info("running_supplier_matching", facture_id=facture.id)

        # Extract SIRET and name from metadata
        extracted_siret = metadata.get("siret")
        extracted_name = metadata.get("fournisseur_nom")

        if not extracted_siret and not extracted_name:
            self.logger.info(
                "no_supplier_data_to_match",
                facture_id=facture.id
            )
            return None

        # Run matching
        match_result = await self.supplier_matcher.match_supplier(
            extracted_siret=extracted_siret,
            extracted_name=extracted_name,
            copropriete_id=facture.copropriete_id
        )

        return match_result

    async def _run_duplicate_detection(
        self,
        facture: FactureGlobal
    ) -> Optional:
        """Run duplicate detection process"""
        self.logger.info("running_duplicate_detection", facture_id=facture.id)

        duplicate_result = await self.duplicate_detector.detect_duplicates(
            facture_id=facture.id,
            numero=facture.numero,
            date_facture=facture.date_facture,
            montant_ttc=facture.montant_ttc,
            fournisseur_id=facture.fournisseur_id
        )

        return duplicate_result

    async def _run_category_classification(
        self,
        facture: FactureGlobal,
        raw_text: str
    ) -> Optional:
        """Run category classification process"""
        self.logger.info("running_category_classification", facture_id=facture.id)

        # Skip if already has category
        if facture.categorie:
            self.logger.info(
                "category_already_set",
                facture_id=facture.id,
                categorie=facture.categorie
            )
            return None

        # Classify
        classification = self.category_classifier.classify(
            text=raw_text,
            existing_category=facture.categorie
        )

        return classification

    async def _run_anomaly_detection(
        self,
        facture: FactureGlobal
    ) -> Optional:
        """Run anomaly detection process"""
        self.logger.info("running_anomaly_detection", facture_id=facture.id)

        anomaly_result = await self.anomaly_detector.detect_anomaly(
            facture_id=facture.id,
            montant_ttc=facture.montant_ttc,
            categorie=facture.categorie,
            fournisseur_id=facture.fournisseur_id
        )

        return anomaly_result

    async def _update_invoice(
        self,
        facture: FactureGlobal,
        result: EnrichmentResult
    ):
        """
        Update invoice with enrichment results.

        Modifies:
        - fournisseur_id (if matched)
        - categorie (if classified with high confidence)
        - needs_review (if duplicates or anomalies detected)
        - metadata_json (store all enrichment data)
        """
        # Initialize metadata if needed
        if not facture.metadata_json:
            facture.metadata_json = {}

        # Store enrichment metadata
        enrichment_metadata = {
            "timestamp": result.timestamp.isoformat(),
            "config": result.config.dict(),
            "actions_taken": [],
            "warnings": []
        }

        # 1. Supplier Matching
        if result.supplier_matching:
            enrichment_metadata["supplier_matching"] = {
                "matched": result.supplier_matching.matched,
                "method": result.supplier_matching.method,
                "confidence": result.supplier_matching.confidence
            }

            if result.supplier_matching.matched:
                # Update fournisseur_id
                old_id = facture.fournisseur_id
                facture.fournisseur_id = result.supplier_matching.fournisseur_id

                action = f"Linked supplier #{result.supplier_matching.fournisseur_id} ({result.supplier_matching.method}, confidence: {result.supplier_matching.confidence:.2f})"
                result.actions_taken.append(action)
                enrichment_metadata["actions_taken"].append(action)

                self.logger.info(
                    "supplier_linked",
                    facture_id=facture.id,
                    old_fournisseur_id=old_id,
                    new_fournisseur_id=facture.fournisseur_id
                )

        # 2. Duplicate Detection
        if result.duplicate_detection:
            enrichment_metadata["duplicate_detection"] = {
                "is_duplicate": result.duplicate_detection.is_duplicate,
                "type": result.duplicate_detection.duplicate_type,
                "confidence": result.duplicate_detection.confidence
            }

            if result.duplicate_detection.is_duplicate:
                # Flag for review
                facture.needs_review = True

                warning = f"Duplicate detected: {result.duplicate_detection.message}"
                result.warnings.append(warning)
                result.needs_review_reasons.append(warning)
                enrichment_metadata["warnings"].append(warning)

                self.logger.warning(
                    "duplicate_flagged",
                    facture_id=facture.id,
                    duplicate_ids=result.duplicate_detection.existing_facture_ids
                )

        # 3. Category Classification
        if result.category_classification:
            enrichment_metadata["category_classification"] = {
                "predicted": result.category_classification.predicted_category,
                "confidence": result.category_classification.confidence,
                "method": result.category_classification.method
            }

            # Auto-set category if confidence is high enough
            if result.category_classification.confidence >= self.config.category_confidence_threshold:
                facture.categorie = result.category_classification.predicted_category

                action = f"Set category to '{facture.categorie}' ({result.category_classification.method}, confidence: {result.category_classification.confidence:.2f})"
                result.actions_taken.append(action)
                enrichment_metadata["actions_taken"].append(action)

                self.logger.info(
                    "category_set",
                    facture_id=facture.id,
                    categorie=facture.categorie
                )
            else:
                warning = f"Low confidence category prediction: {result.category_classification.predicted_category} ({result.category_classification.confidence:.2f})"
                result.warnings.append(warning)
                enrichment_metadata["warnings"].append(warning)

        # 4. Anomaly Detection
        if result.anomaly_detection:
            enrichment_metadata["anomaly_detection"] = {
                "is_anomaly": result.anomaly_detection.is_anomaly,
                "type": result.anomaly_detection.anomaly_type,
                "severity": result.anomaly_detection.severity
            }

            if result.anomaly_detection.is_anomaly:
                # Flag for review
                facture.needs_review = True

                warning = f"Anomaly detected ({result.anomaly_detection.severity}): {result.anomaly_detection.message}"
                result.warnings.append(warning)
                result.needs_review_reasons.append(warning)
                enrichment_metadata["warnings"].append(warning)

                self.logger.warning(
                    "anomaly_flagged",
                    facture_id=facture.id,
                    severity=result.anomaly_detection.severity,
                    anomaly_type=result.anomaly_detection.anomaly_type
                )

        # Update metadata
        facture.metadata_json["enrichment"] = enrichment_metadata

        # Commit changes
        await self.db.commit()
        await self.db.refresh(facture)

        self.logger.info(
            "invoice_updated",
            facture_id=facture.id,
            needs_review=facture.needs_review,
            categorie=facture.categorie,
            fournisseur_id=facture.fournisseur_id
        )
