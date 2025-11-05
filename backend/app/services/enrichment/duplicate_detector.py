"""
Duplicate Detector Service

Detects duplicate invoices using:
1. Strict matching: Same numero + fournisseur
2. Fuzzy matching: Similar montant_ttc + date range + fournisseur
"""

from typing import List, Optional
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import FactureGlobal
from app.models.enrichment import (
    DuplicateResult,
    DuplicateType,
    DuplicateMatch
)
import structlog

logger = structlog.get_logger(__name__)


class DuplicateDetector:
    """
    Service for detecting duplicate invoices.

    Implements two detection strategies:
    1. Strict: Exact match on numero + fournisseur_id
    2. Fuzzy: Similar amount + date range + fournisseur_id
    """

    def __init__(
        self,
        db: AsyncSession,
        date_tolerance_days: int = 7,
        amount_tolerance: float = 0.50
    ):
        """
        Initialize duplicate detector.

        Args:
            db: Database session
            date_tolerance_days: Date range for fuzzy matching (±days)
            amount_tolerance: Amount tolerance for fuzzy matching (EUR)
        """
        self.db = db
        self.date_tolerance_days = date_tolerance_days
        self.amount_tolerance = Decimal(str(amount_tolerance))
        self.logger = logger.bind(service="duplicate_detector")

    async def detect_duplicates(
        self,
        facture_id: int,
        numero: str,
        date_facture: date,
        montant_ttc: Decimal,
        fournisseur_id: Optional[int] = None
    ) -> DuplicateResult:
        """
        Detect if an invoice is a duplicate.

        Args:
            facture_id: ID of the invoice being checked
            numero: Invoice number
            date_facture: Invoice date
            montant_ttc: Total amount including VAT
            fournisseur_id: Supplier ID (optional)

        Returns:
            DuplicateResult with detection details
        """
        self.logger.info(
            "detecting_duplicates",
            facture_id=facture_id,
            numero=numero,
            date_facture=date_facture.isoformat(),
            montant_ttc=float(montant_ttc),
            fournisseur_id=fournisseur_id
        )

        # Strategy 1: Strict matching (numero + fournisseur)
        strict_matches = await self._detect_strict(
            facture_id=facture_id,
            numero=numero,
            fournisseur_id=fournisseur_id
        )

        if strict_matches:
            self.logger.warning(
                "strict_duplicate_detected",
                facture_id=facture_id,
                duplicate_ids=[m.facture_id for m in strict_matches]
            )
            return DuplicateResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.STRICT,
                existing_facture_ids=[m.facture_id for m in strict_matches],
                matches=strict_matches,
                confidence=1.0,
                message=f"Duplicate detected: Same invoice number '{numero}' and supplier"
            )

        # Strategy 2: Fuzzy matching (amount + date range)
        fuzzy_matches = await self._detect_fuzzy(
            facture_id=facture_id,
            date_facture=date_facture,
            montant_ttc=montant_ttc,
            fournisseur_id=fournisseur_id
        )

        if fuzzy_matches:
            self.logger.warning(
                "fuzzy_duplicate_detected",
                facture_id=facture_id,
                duplicate_ids=[m.facture_id for m in fuzzy_matches]
            )
            return DuplicateResult(
                is_duplicate=True,
                duplicate_type=DuplicateType.FUZZY,
                existing_facture_ids=[m.facture_id for m in fuzzy_matches],
                matches=fuzzy_matches,
                confidence=0.8,  # Lower confidence for fuzzy matches
                message=f"Possible duplicate: Similar amount and date"
            )

        # No duplicates
        self.logger.info(
            "no_duplicates_detected",
            facture_id=facture_id
        )
        return DuplicateResult(
            is_duplicate=False,
            duplicate_type=DuplicateType.NONE,
            existing_facture_ids=[],
            matches=[],
            confidence=0.0,
            message=None
        )

    async def _detect_strict(
        self,
        facture_id: int,
        numero: str,
        fournisseur_id: Optional[int]
    ) -> List[DuplicateMatch]:
        """
        Detect strict duplicates: same numero + fournisseur.

        Args:
            facture_id: Current invoice ID (exclude from results)
            numero: Invoice number
            fournisseur_id: Supplier ID

        Returns:
            List of strict duplicate matches
        """
        # Build query
        conditions = [
            FactureGlobal.id != facture_id,  # Exclude self
            FactureGlobal.numero == numero
        ]

        # Add fournisseur condition if available
        if fournisseur_id:
            conditions.append(FactureGlobal.fournisseur_id == fournisseur_id)

        query = select(FactureGlobal).where(and_(*conditions))

        result = await self.db.execute(query)
        duplicates = result.scalars().all()

        # Convert to DuplicateMatch objects
        matches = []
        for dup in duplicates:
            matches.append(
                DuplicateMatch(
                    facture_id=dup.id,
                    numero=dup.numero,
                    date_facture=dup.date_facture.isoformat(),
                    montant_ttc=float(dup.montant_ttc),
                    match_reason=f"Exact match: numero '{numero}'",
                    similarity_score=1.0
                )
            )

        return matches

    async def _detect_fuzzy(
        self,
        facture_id: int,
        date_facture: date,
        montant_ttc: Decimal,
        fournisseur_id: Optional[int]
    ) -> List[DuplicateMatch]:
        """
        Detect fuzzy duplicates: similar amount + date range.

        Args:
            facture_id: Current invoice ID (exclude from results)
            date_facture: Invoice date
            montant_ttc: Total amount
            fournisseur_id: Supplier ID

        Returns:
            List of fuzzy duplicate matches
        """
        # Calculate date range
        date_min = date_facture - timedelta(days=self.date_tolerance_days)
        date_max = date_facture + timedelta(days=self.date_tolerance_days)

        # Calculate amount range
        amount_min = montant_ttc - self.amount_tolerance
        amount_max = montant_ttc + self.amount_tolerance

        # Build query
        conditions = [
            FactureGlobal.id != facture_id,  # Exclude self
            FactureGlobal.date_facture >= date_min,
            FactureGlobal.date_facture <= date_max,
            FactureGlobal.montant_ttc >= amount_min,
            FactureGlobal.montant_ttc <= amount_max
        ]

        # Add fournisseur condition if available (strongly recommended)
        if fournisseur_id:
            conditions.append(FactureGlobal.fournisseur_id == fournisseur_id)

        query = select(FactureGlobal).where(and_(*conditions))

        result = await self.db.execute(query)
        duplicates = result.scalars().all()

        # Convert to DuplicateMatch objects with similarity scores
        matches = []
        for dup in duplicates:
            # Calculate similarity score based on date and amount proximity
            date_diff = abs((dup.date_facture - date_facture).days)
            date_score = 1.0 - (date_diff / self.date_tolerance_days)

            amount_diff = abs(float(dup.montant_ttc - montant_ttc))
            amount_score = 1.0 - (amount_diff / float(self.amount_tolerance))

            # Combined score (average)
            similarity = (date_score + amount_score) / 2.0

            matches.append(
                DuplicateMatch(
                    facture_id=dup.id,
                    numero=dup.numero,
                    date_facture=dup.date_facture.isoformat(),
                    montant_ttc=float(dup.montant_ttc),
                    match_reason=f"Similar amount (±{amount_diff:.2f}€) and date (±{date_diff} days)",
                    similarity_score=max(0.0, min(1.0, similarity))
                )
            )

        # Sort by similarity score descending
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        return matches
