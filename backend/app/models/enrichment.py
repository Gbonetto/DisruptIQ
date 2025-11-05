"""
Enrichment Models - Pydantic schemas for invoice enrichment pipeline

These models represent the results of various enrichment processes
applied to invoices after OCR extraction.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from enum import Enum


class SupplierMatchMethod(str, Enum):
    """Method used for supplier matching"""
    SIRET_EXACT = "siret_exact"
    NAME_FUZZY = "name_fuzzy"
    NONE = "none"


class DuplicateType(str, Enum):
    """Type of duplicate detection"""
    STRICT = "strict"  # Same numero + fournisseur
    FUZZY = "fuzzy"    # Same amount + date range
    NONE = "none"


class AnomalyType(str, Enum):
    """Type of anomaly detected"""
    ZSCORE = "zscore"           # Statistical outlier
    HISTORICAL = "historical"   # Deviation from history
    THRESHOLD = "threshold"     # Business rule threshold
    NONE = "none"


class AnomalySeverity(str, Enum):
    """Severity of detected anomaly"""
    LOW = "low"          # Minor deviation
    MEDIUM = "medium"    # Moderate concern
    HIGH = "high"        # Significant concern
    CRITICAL = "critical"  # Requires immediate review


class ClassificationMethod(str, Enum):
    """Method used for category classification"""
    ML = "ml"              # Machine learning model
    KEYWORD = "keyword"    # Keyword-based rules
    MANUAL = "manual"      # Manually set
    NONE = "none"


# ==================== Supplier Matching ====================

class SupplierCandidate(BaseModel):
    """A candidate supplier match"""
    fournisseur_id: int
    name: str
    company_name: Optional[str] = None
    siret: Optional[str] = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    match_reason: str  # "SIRET exact", "Name fuzzy (0.92)", etc.


class SupplierMatchResult(BaseModel):
    """Result of supplier matching process"""
    matched: bool
    fournisseur_id: Optional[int] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    method: SupplierMatchMethod
    candidates: List[SupplierCandidate] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)

    class Config:
        use_enum_values = True


# ==================== Duplicate Detection ====================

class DuplicateMatch(BaseModel):
    """A detected duplicate invoice"""
    facture_id: int
    numero: str
    date_facture: str
    montant_ttc: float
    match_reason: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class DuplicateResult(BaseModel):
    """Result of duplicate detection process"""
    is_duplicate: bool
    duplicate_type: DuplicateType
    existing_facture_ids: List[int] = Field(default_factory=list)
    matches: List[DuplicateMatch] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    message: Optional[str] = None

    class Config:
        use_enum_values = True


# ==================== Category Classification ====================

class CategoryPrediction(BaseModel):
    """Result of category classification"""
    predicted_category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    method: ClassificationMethod
    top_predictions: List[Tuple[str, float]] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)

    class Config:
        use_enum_values = True


# ==================== Anomaly Detection ====================

class AnomalyResult(BaseModel):
    """Result of anomaly detection process"""
    is_anomaly: bool
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    zscore: Optional[float] = None
    threshold_value: Optional[float] = None
    historical_avg: Optional[float] = None
    message: str
    metadata: Dict = Field(default_factory=dict)

    class Config:
        use_enum_values = True


# ==================== Pipeline Configuration ====================

class EnrichmentConfig(BaseModel):
    """Configuration for enrichment pipeline"""

    # Enable/disable individual enrichments
    enable_supplier_matching: bool = True
    enable_duplicate_detection: bool = True
    enable_category_classification: bool = True
    enable_anomaly_detection: bool = True

    # Supplier matching settings
    supplier_matching_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for fuzzy name matching"
    )

    # Category classification settings
    category_confidence_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to auto-set category"
    )

    # Anomaly detection settings
    anomaly_zscore_threshold: float = Field(
        default=3.0,
        ge=0.0,
        description="Z-score threshold for statistical anomalies (3.0 = 99.7% CI)"
    )
    anomaly_threshold_high: float = Field(
        default=10000.0,
        description="Amount threshold for high-value review (EUR)"
    )
    anomaly_threshold_critical: float = Field(
        default=50000.0,
        description="Amount threshold for critical review (EUR)"
    )

    # Duplicate detection settings
    duplicate_date_tolerance_days: int = Field(
        default=7,
        description="Date range for fuzzy duplicate detection (±days)"
    )
    duplicate_amount_tolerance: float = Field(
        default=0.50,
        description="Amount tolerance for fuzzy duplicate detection (EUR)"
    )


# ==================== Pipeline Result ====================

class EnrichmentResult(BaseModel):
    """Complete result of enrichment pipeline execution"""

    facture_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    config: EnrichmentConfig

    # Individual enrichment results
    supplier_matching: Optional[SupplierMatchResult] = None
    duplicate_detection: Optional[DuplicateResult] = None
    category_classification: Optional[CategoryPrediction] = None
    anomaly_detection: Optional[AnomalyResult] = None

    # Summary
    actions_taken: List[str] = Field(
        default_factory=list,
        description="List of automatic actions performed"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings and flags raised"
    )
    needs_review_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons why invoice needs manual review"
    )

    success: bool = True
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==================== Training Metrics (for ML) ====================

class TrainingMetrics(BaseModel):
    """Metrics from category classifier training"""

    accuracy: float
    precision: float
    recall: float
    f1_score: float

    samples_per_category: Dict[str, int]
    confusion_matrix: List[List[int]]
    categories: List[str]

    training_date: datetime
    model_path: str
    vectorizer_path: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==================== Batch Enrichment ====================

class BatchEnrichmentRequest(BaseModel):
    """Request for batch enrichment of multiple invoices"""

    facture_ids: List[int]
    config: EnrichmentConfig = Field(default_factory=EnrichmentConfig)
    max_concurrent: int = Field(default=5, ge=1, le=20)


class BatchEnrichmentResult(BaseModel):
    """Result of batch enrichment process"""

    total_invoices: int
    successful: int
    failed: int

    results: List[EnrichmentResult]
    errors: Dict[int, str] = Field(
        default_factory=dict,
        description="Map of facture_id to error message"
    )

    total_processing_time_ms: float
    average_processing_time_ms: float
