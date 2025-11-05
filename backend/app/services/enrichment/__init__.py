"""
Enrichment Services Package

Provides automatic enrichment of invoices post-OCR extraction:
- Supplier matching (SIRET + fuzzy name)
- Duplicate detection (strict + fuzzy)
- Category classification (ML + keywords)
- Anomaly detection (statistical + business rules)
"""

from app.services.enrichment.supplier_matcher import (
    SupplierMatcher,
    normalize_text,
    similarity_score,
    normalize_siret
)
from app.services.enrichment.duplicate_detector import DuplicateDetector
from app.services.enrichment.category_classifier import CategoryClassifier
from app.services.enrichment.anomaly_detector import AnomalyDetector

__all__ = [
    "SupplierMatcher",
    "DuplicateDetector",
    "CategoryClassifier",
    "AnomalyDetector",
    "normalize_text",
    "similarity_score",
    "normalize_siret",
]
