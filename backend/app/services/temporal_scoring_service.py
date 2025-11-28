"""
Temporal Decay Scoring Service
Phase 2.3 - World-Class SMA Optimization

Boosts relevance of recent documents over older ones using time-based decay functions.

Use Cases:
- Recent emails/communications should rank higher
- Latest version of contracts should appear first
- Recent incidents are more relevant than old ones

Decay Functions:
- Exponential: score * exp(-λ * days) - Strong recency bias
- Linear: score * max(0, 1 - days/max_days) - Gentle recency bias
- Logarithmic: score * (1 / (1 + log(1 + days))) - Moderate decay

Author: Claude Code - Phase 2 World-Class SMA
Date: November 27, 2025
"""

import math
import structlog
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

logger = structlog.get_logger()


class DecayFunction(str, Enum):
    """Available decay functions"""
    EXPONENTIAL = "exponential"  # Strong recency bias
    LINEAR = "linear"            # Gentle, predictable decay
    LOGARITHMIC = "logarithmic"  # Moderate decay (default)
    NONE = "none"                # No decay (disabled)


class TemporalScoringService:
    """
    Temporal scoring service for time-based relevance boosting

    Usage:
        service = TemporalScoringService(
            decay_function=DecayFunction.LOGARITHMIC,
            half_life_days=30
        )

        # Apply decay to search results
        boosted_results = service.apply_temporal_boost(results, date_field="created_at")
    """

    def __init__(
        self,
        decay_function: DecayFunction = DecayFunction.LOGARITHMIC,
        half_life_days: float = 30.0,
        max_days: float = 365.0,
        min_score_factor: float = 0.1,
        boost_weight: float = 0.3
    ):
        """
        Initialize temporal scoring service

        Args:
            decay_function: Decay function to use
            half_life_days: Days until score is halved (for exponential)
            max_days: Maximum age in days (for linear)
            min_score_factor: Minimum score multiplier (prevents old docs from being ignored)
            boost_weight: Weight of temporal boost vs semantic score (0-1)
                         0.3 = 70% semantic, 30% temporal
        """
        self.decay_function = decay_function
        self.half_life_days = half_life_days
        self.max_days = max_days
        self.min_score_factor = min_score_factor
        self.boost_weight = boost_weight

        # Pre-calculate lambda for exponential decay
        # half_life: score * exp(-λ * half_life) = 0.5 * score
        # => λ = ln(2) / half_life
        self._lambda = math.log(2) / half_life_days if half_life_days > 0 else 0

        logger.info("temporal_scoring_service_initialized",
                   decay_function=decay_function.value,
                   half_life_days=half_life_days,
                   boost_weight=boost_weight)

    def calculate_decay(self, age_days: float) -> float:
        """
        Calculate decay factor based on document age

        Args:
            age_days: Age of document in days

        Returns:
            Decay factor (0 to 1)
        """
        if age_days < 0:
            age_days = 0

        if self.decay_function == DecayFunction.NONE:
            return 1.0

        elif self.decay_function == DecayFunction.EXPONENTIAL:
            # Strong recency bias: exp(-λ * days)
            decay = math.exp(-self._lambda * age_days)

        elif self.decay_function == DecayFunction.LINEAR:
            # Gentle linear decay: 1 - (days / max_days)
            decay = max(0.0, 1.0 - (age_days / self.max_days))

        elif self.decay_function == DecayFunction.LOGARITHMIC:
            # Moderate decay: 1 / (1 + log(1 + days))
            decay = 1.0 / (1.0 + math.log(1.0 + age_days))

        else:
            decay = 1.0

        # Apply minimum score factor
        return max(self.min_score_factor, decay)

    def apply_temporal_boost(
        self,
        results: List[Dict[str, Any]],
        date_field: str = "created_at",
        reference_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply temporal boost to search results

        Args:
            results: Search results with scores
            date_field: Field containing document date (in metadata or top-level)
            reference_date: Reference date for age calculation (default: now)

        Returns:
            Results with boosted scores, re-sorted by combined score
        """
        if not results:
            return results

        if reference_date is None:
            reference_date = datetime.now()

        boosted_results = []

        for result in results:
            # Get original score
            original_score = result.get("score", 0.0)

            # Extract date from result
            doc_date = self._extract_date(result, date_field)

            if doc_date:
                # Calculate age in days
                age = reference_date - doc_date
                age_days = max(0, age.total_seconds() / 86400)  # Convert to days

                # Calculate decay factor
                decay_factor = self.calculate_decay(age_days)

                # Calculate temporal score (1.0 for recent, decay for old)
                temporal_score = decay_factor

            else:
                # No date available, use neutral decay
                temporal_score = 0.5
                age_days = -1  # Unknown

            # Combine semantic score with temporal score
            # combined = (1 - weight) * semantic + weight * temporal
            combined_score = (
                (1 - self.boost_weight) * original_score +
                self.boost_weight * temporal_score
            )

            # Create boosted result
            boosted_result = {
                **result,
                "original_score": original_score,
                "temporal_score": temporal_score,
                "combined_score": combined_score,
                "age_days": age_days if age_days >= 0 else None,
                "score": combined_score  # Replace original score
            }

            boosted_results.append(boosted_result)

        # Re-sort by combined score
        boosted_results.sort(key=lambda x: x["combined_score"], reverse=True)

        logger.info("temporal_boost_applied",
                   results_count=len(boosted_results),
                   decay_function=self.decay_function.value,
                   boost_weight=self.boost_weight)

        return boosted_results

    def _extract_date(
        self,
        result: Dict[str, Any],
        date_field: str
    ) -> Optional[datetime]:
        """
        Extract date from result (handles various formats and locations)
        """
        # Try top-level
        date_value = result.get(date_field)

        # Try metadata
        if date_value is None and "metadata" in result:
            date_value = result["metadata"].get(date_field)

        # Try common alternatives
        if date_value is None:
            for alt_field in ["date", "timestamp", "created", "indexed_at", "upload_date"]:
                date_value = result.get(alt_field) or result.get("metadata", {}).get(alt_field)
                if date_value:
                    break

        if date_value is None:
            return None

        # Parse date
        return self._parse_date(date_value)

    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """
        Parse date from various formats
        """
        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            # Try common formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds
                "%Y-%m-%dT%H:%M:%SZ",      # ISO format
                "%Y-%m-%dT%H:%M:%S",       # ISO without Z
                "%Y-%m-%d %H:%M:%S",       # Standard datetime
                "%Y-%m-%d",                # Date only
                "%d/%m/%Y",                # French format
                "%d-%m-%Y",                # French with dashes
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue

        # Try timestamp (unix epoch)
        if isinstance(date_value, (int, float)):
            try:
                return datetime.fromtimestamp(date_value)
            except (ValueError, OSError):
                pass

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "decay_function": self.decay_function.value,
            "half_life_days": self.half_life_days,
            "max_days": self.max_days,
            "min_score_factor": self.min_score_factor,
            "boost_weight": self.boost_weight,
            "lambda": self._lambda,
        }


# ================================================================
# PRE-CONFIGURED INSTANCES
# ================================================================

# Default temporal scorer (moderate recency bias)
default_temporal_scorer = TemporalScoringService(
    decay_function=DecayFunction.LOGARITHMIC,
    half_life_days=30.0,
    boost_weight=0.2  # 80% semantic, 20% temporal
)

# Email/communication scorer (strong recency bias)
communication_temporal_scorer = TemporalScoringService(
    decay_function=DecayFunction.EXPONENTIAL,
    half_life_days=7.0,   # Emails older than 1 week are less relevant
    boost_weight=0.4      # 60% semantic, 40% temporal
)

# Legal document scorer (weak recency bias - legal docs stay relevant)
legal_temporal_scorer = TemporalScoringService(
    decay_function=DecayFunction.LINEAR,
    max_days=365 * 3,     # 3 years until full decay
    boost_weight=0.1      # 90% semantic, 10% temporal
)


def get_temporal_scorer(doc_type: Optional[str] = None) -> TemporalScoringService:
    """
    Get appropriate temporal scorer based on document type

    Args:
        doc_type: Document type (email, legal, contract, etc.)

    Returns:
        Configured TemporalScoringService
    """
    if doc_type in ["email", "communication", "message", "notification"]:
        return communication_temporal_scorer
    elif doc_type in ["legal", "contract", "regulation", "law", "jurisprudence"]:
        return legal_temporal_scorer
    else:
        return default_temporal_scorer
