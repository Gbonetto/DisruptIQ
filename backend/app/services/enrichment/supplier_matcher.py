"""
Supplier Matcher Service

Automatically matches invoices to suppliers using:
1. SIRET exact matching (priority 1)
2. Fuzzy name matching with Levenshtein distance (priority 2)
"""

import re
import unicodedata
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.professionnel import Professionnel
from app.models.enrichment import (
    SupplierMatchResult,
    SupplierMatchMethod,
    SupplierCandidate
)
import structlog

logger = structlog.get_logger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for fuzzy matching:
    - Lowercase
    - Remove accents
    - Remove extra whitespace
    - Remove special characters
    """
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Remove accents
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

    # Remove special characters except spaces and alphanumeric
    text = re.sub(r'[^a-z0-9\s]', '', text)

    # Remove extra whitespace
    text = ' '.join(text.split())

    return text


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.

    The Levenshtein distance is the minimum number of single-character
    edits (insertions, deletions, substitutions) required to change
    one string into another.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_score(s1: str, s2: str) -> float:
    """
    Calculate similarity score (0.0 to 1.0) between two strings.

    Based on normalized Levenshtein distance:
    similarity = 1 - (distance / max_length)

    Returns:
        float: 1.0 = identical, 0.0 = completely different
    """
    if not s1 or not s2:
        return 0.0

    # Normalize both strings
    s1_norm = normalize_text(s1)
    s2_norm = normalize_text(s2)

    if s1_norm == s2_norm:
        return 1.0

    # Calculate distance
    distance = levenshtein_distance(s1_norm, s2_norm)
    max_len = max(len(s1_norm), len(s2_norm))

    if max_len == 0:
        return 0.0

    # Convert to similarity score
    similarity = 1.0 - (distance / max_len)
    return max(0.0, min(1.0, similarity))


def normalize_siret(siret: Optional[str]) -> Optional[str]:
    """
    Normalize SIRET number:
    - Remove spaces, dashes, and special characters
    - Keep only digits
    - Must be exactly 14 digits

    Returns None if invalid.
    """
    if not siret:
        return None

    # Remove all non-digit characters
    siret_clean = re.sub(r'\D', '', siret)

    # SIRET must be exactly 14 digits
    if len(siret_clean) != 14:
        return None

    return siret_clean


class SupplierMatcher:
    """
    Service for matching invoices to suppliers automatically.

    Strategies (in priority order):
    1. SIRET exact match (confidence = 1.0)
    2. Fuzzy name match (confidence = similarity score)
    """

    def __init__(
        self,
        db: AsyncSession,
        fuzzy_threshold: float = 0.85
    ):
        """
        Initialize supplier matcher.

        Args:
            db: Database session
            fuzzy_threshold: Minimum similarity score for fuzzy matching (0.0-1.0)
        """
        self.db = db
        self.fuzzy_threshold = fuzzy_threshold
        self.logger = logger.bind(service="supplier_matcher")

    async def match_supplier(
        self,
        extracted_siret: Optional[str] = None,
        extracted_name: Optional[str] = None,
        copropriete_id: Optional[int] = None
    ) -> SupplierMatchResult:
        """
        Match a supplier based on extracted invoice data.

        Args:
            extracted_siret: SIRET extracted from invoice
            extracted_name: Supplier name extracted from invoice
            copropriete_id: Optional copropriete ID to filter suppliers

        Returns:
            SupplierMatchResult with match details and candidates
        """
        self.logger.info(
            "matching_supplier",
            siret=extracted_siret,
            name=extracted_name,
            copropriete_id=copropriete_id
        )

        # Strategy 1: SIRET exact match
        if extracted_siret:
            siret_match = await self._match_by_siret(extracted_siret)
            if siret_match:
                self.logger.info(
                    "supplier_matched_siret",
                    fournisseur_id=siret_match.id,
                    siret=extracted_siret
                )
                return SupplierMatchResult(
                    matched=True,
                    fournisseur_id=siret_match.id,
                    confidence=1.0,
                    method=SupplierMatchMethod.SIRET_EXACT,
                    candidates=[
                        SupplierCandidate(
                            fournisseur_id=siret_match.id,
                            name=siret_match.name,
                            company_name=siret_match.company_name,
                            siret=siret_match.siret,
                            similarity_score=1.0,
                            match_reason="SIRET exact match"
                        )
                    ],
                    metadata={"siret": extracted_siret}
                )

        # Strategy 2: Fuzzy name match
        if extracted_name:
            name_matches = await self._match_by_name(
                extracted_name,
                copropriete_id=copropriete_id
            )

            if name_matches:
                best_match = name_matches[0]

                if best_match.similarity_score >= self.fuzzy_threshold:
                    self.logger.info(
                        "supplier_matched_fuzzy",
                        fournisseur_id=best_match.fournisseur_id,
                        name=extracted_name,
                        score=best_match.similarity_score
                    )
                    return SupplierMatchResult(
                        matched=True,
                        fournisseur_id=best_match.fournisseur_id,
                        confidence=best_match.similarity_score,
                        method=SupplierMatchMethod.NAME_FUZZY,
                        candidates=name_matches[:5],  # Top 5 candidates
                        metadata={
                            "extracted_name": extracted_name,
                            "threshold": self.fuzzy_threshold
                        }
                    )
                else:
                    # Below threshold, but return candidates for manual review
                    self.logger.info(
                        "supplier_no_match_below_threshold",
                        name=extracted_name,
                        best_score=best_match.similarity_score,
                        threshold=self.fuzzy_threshold
                    )
                    return SupplierMatchResult(
                        matched=False,
                        confidence=0.0,
                        method=SupplierMatchMethod.NONE,
                        candidates=name_matches[:5],
                        metadata={
                            "extracted_name": extracted_name,
                            "best_score": best_match.similarity_score,
                            "threshold": self.fuzzy_threshold
                        }
                    )

        # No match
        self.logger.info(
            "supplier_no_match",
            siret=extracted_siret,
            name=extracted_name
        )
        return SupplierMatchResult(
            matched=False,
            confidence=0.0,
            method=SupplierMatchMethod.NONE,
            candidates=[],
            metadata={
                "siret": extracted_siret,
                "name": extracted_name
            }
        )

    async def _match_by_siret(
        self,
        siret: str
    ) -> Optional[Professionnel]:
        """
        Find supplier by exact SIRET match.

        Args:
            siret: SIRET number (will be normalized)

        Returns:
            Professionnel if found, None otherwise
        """
        siret_normalized = normalize_siret(siret)
        if not siret_normalized:
            return None

        query = select(Professionnel).where(
            Professionnel.siret == siret_normalized,
            Professionnel.statut == 'active'
        )

        result = await self.db.execute(query)
        return result.scalars().first()

    async def _match_by_name(
        self,
        name: str,
        copropriete_id: Optional[int] = None,
        limit: int = 10
    ) -> List[SupplierCandidate]:
        """
        Find suppliers by fuzzy name matching.

        Args:
            name: Supplier name to match
            copropriete_id: Optional filter by copropriete
            limit: Maximum number of candidates to return

        Returns:
            List of SupplierCandidate, sorted by similarity score (descending)
        """
        # Query all active suppliers
        # TODO: Add copropriete filtering when many-to-many relation is set up
        query = select(Professionnel).where(
            Professionnel.statut == 'active'
        ).limit(500)  # Limit to avoid processing too many

        result = await self.db.execute(query)
        suppliers = result.scalars().all()

        # Calculate similarity scores
        candidates = []
        for supplier in suppliers:
            # Try matching against both name and company_name
            scores = []

            if supplier.name:
                scores.append(similarity_score(name, supplier.name))

            if supplier.company_name:
                scores.append(similarity_score(name, supplier.company_name))

            if not scores:
                continue

            # Use best score
            best_score = max(scores)

            # Only include if score > 0.3 (very loose filter)
            if best_score > 0.3:
                match_field = "name" if supplier.name and similarity_score(name, supplier.name) == best_score else "company_name"
                candidates.append(
                    SupplierCandidate(
                        fournisseur_id=supplier.id,
                        name=supplier.name,
                        company_name=supplier.company_name,
                        siret=supplier.siret,
                        similarity_score=best_score,
                        match_reason=f"Fuzzy match on {match_field} ({best_score:.2f})"
                    )
                )

        # Sort by score descending
        candidates.sort(key=lambda c: c.similarity_score, reverse=True)

        return candidates[:limit]
