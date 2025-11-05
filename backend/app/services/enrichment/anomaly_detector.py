"""
Anomaly Detector Service

Detects abnormal invoice amounts using:
1. Z-score statistical analysis (outliers)
2. Historical comparison with same supplier
3. Business rule thresholds
"""

import math
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import FactureGlobal
from app.models.enrichment import (
    AnomalyResult,
    AnomalyType,
    AnomalySeverity
)
import structlog

logger = structlog.get_logger(__name__)


class AnomalyDetector:
    """
    Service for detecting anomalous invoice amounts.

    Uses multiple detection methods:
    1. Statistical Z-score analysis by category
    2. Historical comparison with same supplier
    3. Business rule thresholds
    """

    def __init__(
        self,
        db: AsyncSession,
        zscore_threshold: float = 3.0,
        threshold_high: float = 10000.0,
        threshold_critical: float = 50000.0
    ):
        """
        Initialize anomaly detector.

        Args:
            db: Database session
            zscore_threshold: Z-score threshold for outliers (default: 3.0 = 99.7% CI)
            threshold_high: Amount threshold for high-value review (EUR)
            threshold_critical: Amount threshold for critical review (EUR)
        """
        self.db = db
        self.zscore_threshold = zscore_threshold
        self.threshold_high = Decimal(str(threshold_high))
        self.threshold_critical = Decimal(str(threshold_critical))
        self.logger = logger.bind(service="anomaly_detector")

    async def detect_anomaly(
        self,
        facture_id: int,
        montant_ttc: Decimal,
        categorie: Optional[str] = None,
        fournisseur_id: Optional[int] = None
    ) -> AnomalyResult:
        """
        Detect if an invoice amount is anomalous.

        Args:
            facture_id: ID of the invoice being checked
            montant_ttc: Total amount including VAT
            categorie: Invoice category (for statistical comparison)
            fournisseur_id: Supplier ID (for historical comparison)

        Returns:
            AnomalyResult with detection details
        """
        self.logger.info(
            "detecting_anomaly",
            facture_id=facture_id,
            montant_ttc=float(montant_ttc),
            categorie=categorie,
            fournisseur_id=fournisseur_id
        )

        # Check 1: Business rule thresholds (highest priority)
        threshold_result = self._check_thresholds(montant_ttc)
        if threshold_result:
            return threshold_result

        # Check 2: Z-score analysis (if category available)
        if categorie:
            zscore_result = await self._check_zscore(
                facture_id=facture_id,
                montant_ttc=montant_ttc,
                categorie=categorie
            )
            if zscore_result:
                return zscore_result

        # Check 3: Historical comparison (if supplier known)
        if fournisseur_id:
            historical_result = await self._check_historical(
                facture_id=facture_id,
                montant_ttc=montant_ttc,
                fournisseur_id=fournisseur_id
            )
            if historical_result:
                return historical_result

        # No anomaly detected
        self.logger.info(
            "no_anomaly_detected",
            facture_id=facture_id,
            montant_ttc=float(montant_ttc)
        )
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type=AnomalyType.NONE,
            severity=AnomalySeverity.LOW,
            message="Amount within normal range"
        )

    def _check_thresholds(
        self,
        montant_ttc: Decimal
    ) -> Optional[AnomalyResult]:
        """
        Check if amount exceeds business rule thresholds.

        Args:
            montant_ttc: Total amount

        Returns:
            AnomalyResult if threshold exceeded, None otherwise
        """
        if montant_ttc >= self.threshold_critical:
            self.logger.warning(
                "critical_threshold_exceeded",
                montant_ttc=float(montant_ttc),
                threshold=float(self.threshold_critical)
            )
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.THRESHOLD,
                severity=AnomalySeverity.CRITICAL,
                threshold_value=float(self.threshold_critical),
                message=f"CRITICAL: Amount {montant_ttc:,.2f}€ exceeds critical threshold {self.threshold_critical:,.2f}€",
                metadata={
                    "threshold_type": "critical",
                    "threshold_value": float(self.threshold_critical)
                }
            )

        if montant_ttc >= self.threshold_high:
            self.logger.warning(
                "high_threshold_exceeded",
                montant_ttc=float(montant_ttc),
                threshold=float(self.threshold_high)
            )
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.THRESHOLD,
                severity=AnomalySeverity.HIGH,
                threshold_value=float(self.threshold_high),
                message=f"HIGH: Amount {montant_ttc:,.2f}€ exceeds high-value threshold {self.threshold_high:,.2f}€",
                metadata={
                    "threshold_type": "high",
                    "threshold_value": float(self.threshold_high)
                }
            )

        return None

    async def _check_zscore(
        self,
        facture_id: int,
        montant_ttc: Decimal,
        categorie: str
    ) -> Optional[AnomalyResult]:
        """
        Check if amount is a statistical outlier using Z-score.

        Z-score = (value - mean) / std_dev
        Threshold of 3.0 means 99.7% of normal values are within range.

        Args:
            facture_id: Current invoice ID (exclude from calculation)
            montant_ttc: Total amount
            categorie: Invoice category

        Returns:
            AnomalyResult if outlier detected, None otherwise
        """
        # Query statistics for this category (excluding current invoice)
        query = select(
            func.avg(FactureGlobal.montant_ttc).label('mean'),
            func.stddev(FactureGlobal.montant_ttc).label('stddev'),
            func.count(FactureGlobal.id).label('count')
        ).where(
            and_(
                FactureGlobal.categorie == categorie,
                FactureGlobal.id != facture_id
            )
        )

        result = await self.db.execute(query)
        stats = result.one()

        mean = stats.mean
        stddev = stats.stddev
        count = stats.count

        # Need at least 10 samples for reliable statistics
        if count < 10:
            self.logger.info(
                "insufficient_samples_for_zscore",
                categorie=categorie,
                count=count
            )
            return None

        # Need non-zero standard deviation
        if not stddev or stddev == 0:
            self.logger.info(
                "zero_stddev_cannot_calculate_zscore",
                categorie=categorie
            )
            return None

        # Calculate Z-score
        zscore = float((montant_ttc - mean) / stddev)
        abs_zscore = abs(zscore)

        self.logger.info(
            "zscore_calculated",
            zscore=zscore,
            mean=float(mean),
            stddev=float(stddev),
            count=count
        )

        # Check if outlier
        if abs_zscore > self.zscore_threshold:
            # Determine severity based on Z-score magnitude
            if abs_zscore > 5.0:
                severity = AnomalySeverity.CRITICAL
            elif abs_zscore > 4.0:
                severity = AnomalySeverity.HIGH
            else:
                severity = AnomalySeverity.MEDIUM

            self.logger.warning(
                "zscore_anomaly_detected",
                zscore=zscore,
                severity=severity.value,
                categorie=categorie
            )

            direction = "higher" if zscore > 0 else "lower"
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.ZSCORE,
                severity=severity,
                zscore=zscore,
                message=f"Statistical outlier: Amount is {abs_zscore:.1f} std deviations {direction} than average for category '{categorie}'",
                metadata={
                    "category": categorie,
                    "mean": float(mean),
                    "stddev": float(stddev),
                    "sample_count": count,
                    "zscore_threshold": self.zscore_threshold
                }
            )

        return None

    async def _check_historical(
        self,
        facture_id: int,
        montant_ttc: Decimal,
        fournisseur_id: int
    ) -> Optional[AnomalyResult]:
        """
        Check if amount deviates significantly from historical average
        for this supplier.

        Args:
            facture_id: Current invoice ID (exclude from calculation)
            montant_ttc: Total amount
            fournisseur_id: Supplier ID

        Returns:
            AnomalyResult if historical deviation detected, None otherwise
        """
        # Query historical average for this supplier
        query = select(
            func.avg(FactureGlobal.montant_ttc).label('avg'),
            func.count(FactureGlobal.id).label('count')
        ).where(
            and_(
                FactureGlobal.fournisseur_id == fournisseur_id,
                FactureGlobal.id != facture_id
            )
        )

        result = await self.db.execute(query)
        stats = result.one()

        avg = stats.avg
        count = stats.count

        # Need at least 3 historical invoices
        if count < 3:
            self.logger.info(
                "insufficient_historical_invoices",
                fournisseur_id=fournisseur_id,
                count=count
            )
            return None

        # Check if current amount is > 2x historical average
        if montant_ttc > (avg * 2):
            ratio = float(montant_ttc / avg)

            # Determine severity based on ratio
            if ratio > 5.0:
                severity = AnomalySeverity.CRITICAL
            elif ratio > 3.0:
                severity = AnomalySeverity.HIGH
            else:
                severity = AnomalySeverity.MEDIUM

            self.logger.warning(
                "historical_anomaly_detected",
                ratio=ratio,
                severity=severity.value,
                fournisseur_id=fournisseur_id
            )

            return AnomalyResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.HISTORICAL,
                severity=severity,
                historical_avg=float(avg),
                message=f"Historical deviation: Amount is {ratio:.1f}x higher than average for this supplier (avg: {avg:.2f}€)",
                metadata={
                    "fournisseur_id": fournisseur_id,
                    "historical_avg": float(avg),
                    "historical_count": count,
                    "ratio": ratio
                }
            )

        return None
