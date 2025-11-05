"""
Advanced Enrichment API Endpoints

API endpoints pour l'enrichissement avancé et le machine learning:
- Re-enrichissement de factures
- Enrichissement en lot (batch)
- Statistiques d'enrichissement
- Métriques ML
- Re-entraînement du modèle
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.invoice import FactureGlobal, FactureStatut
from app.models.enrichment import (
    EnrichmentConfig,
    EnrichmentResult,
    BatchEnrichmentRequest,
    BatchEnrichmentResult
)
from app.services.enrichment_pipeline import EnrichmentPipeline
import structlog

router = APIRouter()
logger = structlog.get_logger()


# ==================== Request/Response Models ====================

class ReEnrichRequest(BaseModel):
    """Requête de re-enrichissement"""
    config: Optional[EnrichmentConfig] = Field(
        None,
        description="Configuration personnalisée (utilise défaut si omis)"
    )
    force: bool = Field(
        False,
        description="Forcer le re-enrichissement même si déjà enrichi"
    )


class EnrichmentStatsResponse(BaseModel):
    """Statistiques d'enrichissement"""
    total_invoices: int
    enriched_invoices: int
    enrichment_rate: float

    # Supplier matching
    supplier_matched_count: int
    supplier_match_rate: float

    # Duplicates
    duplicates_detected_count: int
    duplicate_rate: float

    # Category classification
    category_auto_set_count: int
    category_auto_set_rate: float
    ml_used_count: int
    ml_usage_rate: float
    keyword_used_count: int

    # Anomalies
    anomalies_detected_count: int
    anomaly_rate: float

    # Needs review
    needs_review_count: int
    needs_review_rate: float

    # Performance
    avg_processing_time_ms: Optional[float]


class MLMetricsResponse(BaseModel):
    """Métriques du modèle ML"""
    model_loaded: bool
    model_path: Optional[str]

    # Training metrics (from training_metrics.json)
    training_metrics: Optional[Dict] = None

    # Live usage stats
    predictions_count: int
    avg_confidence: Optional[float]
    categories: List[str]


class RetrainRequest(BaseModel):
    """Requête de re-entraînement"""
    min_samples: int = Field(
        5,
        ge=1,
        le=50,
        description="Minimum samples par catégorie"
    )
    test_split: float = Field(
        0.2,
        ge=0.1,
        le=0.5,
        description="Fraction pour test set"
    )


class RetrainResponse(BaseModel):
    """Réponse de re-entraînement"""
    status: str  # "started", "completed", "failed"
    message: str
    task_id: Optional[str] = None
    metrics: Optional[Dict] = None


# ==================== Endpoints ====================

@router.post("/{facture_id}/re-enrich", response_model=EnrichmentResult)
async def re_enrich_invoice(
    facture_id: int,
    request: ReEnrichRequest = ReEnrichRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Re-enrichir une facture existante

    Utile pour :
    - Appliquer une configuration d'enrichissement différente
    - Re-enrichir après mise à jour du modèle ML
    - Corriger un enrichissement erroné

    Args:
        facture_id: ID de la facture à re-enrichir
        request: Configuration de re-enrichissement

    Returns:
        EnrichmentResult avec nouveaux résultats

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/enrichment/123/re-enrich" \\
          -H "Content-Type: application/json" \\
          -d '{
            "config": {
              "enable_supplier_matching": true,
              "category_confidence_threshold": 0.90
            },
            "force": true
          }'
        ```
    """
    logger.info(
        "re_enrich_invoice_request",
        facture_id=facture_id,
        force=request.force
    )

    # Vérifier que la facture existe
    query = select(FactureGlobal).where(FactureGlobal.id == facture_id)
    result = await db.execute(query)
    facture = result.scalars().first()

    if not facture:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {facture_id} not found"
        )

    # Vérifier si déjà enrichi (si force=False)
    if not request.force:
        metadata = facture.metadata_json or {}
        if "enrichment" in metadata:
            raise HTTPException(
                status_code=400,
                detail="Invoice already enriched. Use force=true to re-enrich"
            )

    # Configuration
    config = request.config or EnrichmentConfig()

    # Enrichir
    pipeline = EnrichmentPipeline(db=db, config=config)
    enrichment_result = await pipeline.enrich_invoice(facture_id)

    logger.info(
        "re_enrich_invoice_complete",
        facture_id=facture_id,
        success=enrichment_result.success,
        actions_taken=len(enrichment_result.actions_taken)
    )

    return enrichment_result


@router.post("/batch-enrich", response_model=BatchEnrichmentResult)
async def batch_enrich_invoices(
    request: BatchEnrichmentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Enrichir plusieurs factures en lot

    Utile pour :
    - Enrichir des factures existantes non enrichies
    - Traitement en masse après import
    - Re-enrichissement après mise à jour ML

    Note: Si > 20 factures, traitement en background

    Args:
        request: Liste de facture IDs et config

    Returns:
        BatchEnrichmentResult avec résultats pour chaque facture

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/enrichment/batch-enrich" \\
          -H "Content-Type: application/json" \\
          -d '{
            "facture_ids": [1, 2, 3, 4, 5],
            "config": {
              "enable_supplier_matching": true
            },
            "max_concurrent": 3
          }'
        ```
    """
    import time
    import asyncio

    logger.info(
        "batch_enrich_request",
        count=len(request.facture_ids),
        max_concurrent=request.max_concurrent
    )

    if len(request.facture_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="No invoice IDs provided"
        )

    if len(request.facture_ids) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Maximum 1000 invoices per batch"
        )

    start_time = time.time()

    # Initialize pipeline
    pipeline = EnrichmentPipeline(db=db, config=request.config)

    # Results
    results = []
    errors = {}
    successful = 0
    failed = 0

    # Process with concurrency control
    semaphore = asyncio.Semaphore(request.max_concurrent)

    async def enrich_one(facture_id: int):
        nonlocal successful, failed

        async with semaphore:
            try:
                logger.info("batch_enrich_processing", facture_id=facture_id)
                result = await pipeline.enrich_invoice(facture_id)

                if result.success:
                    successful += 1
                else:
                    failed += 1
                    errors[facture_id] = result.error_message or "Unknown error"

                return result

            except Exception as e:
                logger.error(
                    "batch_enrich_error",
                    facture_id=facture_id,
                    error=str(e)
                )
                failed += 1
                errors[facture_id] = str(e)
                return None

    # Process all invoices concurrently
    tasks = [enrich_one(fid) for fid in request.facture_ids]
    results = await asyncio.gather(*tasks)

    # Filter out None results
    results = [r for r in results if r is not None]

    # Calculate stats
    total_time_ms = (time.time() - start_time) * 1000
    avg_time_ms = total_time_ms / len(request.facture_ids) if request.facture_ids else 0

    batch_result = BatchEnrichmentResult(
        total_invoices=len(request.facture_ids),
        successful=successful,
        failed=failed,
        results=results,
        errors=errors,
        total_processing_time_ms=total_time_ms,
        average_processing_time_ms=avg_time_ms
    )

    logger.info(
        "batch_enrich_complete",
        total=len(request.facture_ids),
        successful=successful,
        failed=failed,
        total_time_ms=total_time_ms
    )

    return batch_result


@router.get("/stats", response_model=EnrichmentStatsResponse)
async def get_enrichment_stats(
    copropriete_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Statistiques d'enrichissement

    Retourne des métriques sur :
    - Taux d'enrichissement
    - Taux de matching fournisseurs
    - Détection de doublons
    - Classification automatique
    - Utilisation ML vs keywords
    - Anomalies détectées

    Args:
        copropriete_id: Filtrer par copropriété (optionnel)

    Returns:
        EnrichmentStatsResponse avec toutes les statistiques

    Example:
        ```bash
        curl "http://localhost:8000/api/enrichment/stats"
        curl "http://localhost:8000/api/enrichment/stats?copropriete_id=1"
        ```
    """
    logger.info("get_enrichment_stats", copropriete_id=copropriete_id)

    # Build where clause
    where_clause = ""
    params = {}
    if copropriete_id:
        where_clause = "WHERE copropriete_id = :copropriete_id"
        params["copropriete_id"] = copropriete_id

    # Query stats
    query = text(f"""
        SELECT
            -- Total invoices
            COUNT(*) as total_invoices,

            -- Enriched invoices
            COUNT(CASE WHEN metadata_json ? 'enrichment' THEN 1 END) as enriched_invoices,

            -- Supplier matching
            COUNT(CASE
                WHEN metadata_json->'enrichment'->'supplier_matching'->>'matched' = 'true'
                THEN 1
            END) as supplier_matched_count,

            -- Duplicates
            COUNT(CASE
                WHEN metadata_json->'enrichment'->'duplicate_detection'->>'is_duplicate' = 'true'
                THEN 1
            END) as duplicates_detected_count,

            -- Category auto-set
            COUNT(CASE
                WHEN categorie IS NOT NULL
                AND metadata_json->'enrichment'->'category_classification' IS NOT NULL
                THEN 1
            END) as category_auto_set_count,

            -- ML usage
            COUNT(CASE
                WHEN metadata_json->'enrichment'->'category_classification'->>'method' = 'ml'
                THEN 1
            END) as ml_used_count,

            -- Keyword usage
            COUNT(CASE
                WHEN metadata_json->'enrichment'->'category_classification'->>'method' = 'keyword'
                THEN 1
            END) as keyword_used_count,

            -- Anomalies
            COUNT(CASE
                WHEN metadata_json->'enrichment'->'anomaly_detection'->>'is_anomaly' = 'true'
                THEN 1
            END) as anomalies_detected_count,

            -- Needs review
            COUNT(CASE WHEN needs_review = true THEN 1 END) as needs_review_count,

            -- Avg processing time
            AVG(
                CAST(
                    metadata_json->'enrichment'->>'processing_time_ms' AS FLOAT
                )
            ) as avg_processing_time_ms

        FROM factures_global
        {where_clause}
    """)

    result = await db.execute(query, params)
    stats = result.one()

    # Calculate rates
    total = stats.total_invoices or 1  # Avoid division by zero
    enriched = stats.enriched_invoices or 0

    return EnrichmentStatsResponse(
        total_invoices=total,
        enriched_invoices=enriched,
        enrichment_rate=enriched / total,

        supplier_matched_count=stats.supplier_matched_count or 0,
        supplier_match_rate=(stats.supplier_matched_count or 0) / total,

        duplicates_detected_count=stats.duplicates_detected_count or 0,
        duplicate_rate=(stats.duplicates_detected_count or 0) / total,

        category_auto_set_count=stats.category_auto_set_count or 0,
        category_auto_set_rate=(stats.category_auto_set_count or 0) / total,

        ml_used_count=stats.ml_used_count or 0,
        ml_usage_rate=(stats.ml_used_count or 0) / total,

        keyword_used_count=stats.keyword_used_count or 0,

        anomalies_detected_count=stats.anomalies_detected_count or 0,
        anomaly_rate=(stats.anomalies_detected_count or 0) / total,

        needs_review_count=stats.needs_review_count or 0,
        needs_review_rate=(stats.needs_review_count or 0) / total,

        avg_processing_time_ms=stats.avg_processing_time_ms
    )


@router.get("/ml/metrics", response_model=MLMetricsResponse)
async def get_ml_metrics(
    db: AsyncSession = Depends(get_db)
):
    """
    Métriques du modèle ML de classification

    Retourne :
    - Statut du modèle (chargé ou non)
    - Métriques d'entraînement (accuracy, F1, etc.)
    - Statistiques d'utilisation en production

    Returns:
        MLMetricsResponse avec métriques complètes

    Example:
        ```bash
        curl "http://localhost:8000/api/enrichment/ml/metrics"
        ```
    """
    import json
    from pathlib import Path
    from app.services.enrichment.category_classifier import CategoryClassifier

    logger.info("get_ml_metrics")

    # Check if model is loaded
    classifier = CategoryClassifier.get_default_instance()
    model_loaded = classifier.model is not None

    # Try to load training metrics
    training_metrics = None
    metrics_path = Path("models/training_metrics.json")

    if metrics_path.exists():
        try:
            with open(metrics_path, 'r') as f:
                training_metrics = json.load(f)
        except Exception as e:
            logger.warning("failed_to_load_training_metrics", error=str(e))

    # Get live usage stats
    query = text("""
        SELECT
            COUNT(*) as predictions_count,
            AVG(
                CAST(
                    metadata_json->'enrichment'->'category_classification'->>'confidence' AS FLOAT
                )
            ) as avg_confidence
        FROM factures_global
        WHERE metadata_json->'enrichment'->'category_classification'->>'method' = 'ml'
    """)

    result = await db.execute(query)
    stats = result.one()

    # Get categories
    categories = []
    if training_metrics:
        categories = training_metrics.get("categories", [])

    return MLMetricsResponse(
        model_loaded=model_loaded,
        model_path="models/category_classifier.pkl" if model_loaded else None,
        training_metrics=training_metrics,
        predictions_count=stats.predictions_count or 0,
        avg_confidence=stats.avg_confidence,
        categories=categories
    )


@router.post("/ml/retrain", response_model=RetrainResponse)
async def retrain_ml_model(
    request: RetrainRequest = RetrainRequest(),
    background_tasks: BackgroundTasks = None
):
    """
    Re-entraîner le modèle ML de classification

    Déclenche un re-entraînement du modèle avec les factures
    validées les plus récentes.

    ⚠️ Attention : Opération longue (peut prendre 10-60 secondes)

    Args:
        request: Paramètres d'entraînement

    Returns:
        RetrainResponse avec statut et métriques

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/enrichment/ml/retrain" \\
          -H "Content-Type: application/json" \\
          -d '{
            "min_samples": 10,
            "test_split": 0.2
          }'
        ```
    """
    import subprocess
    import sys
    from pathlib import Path

    logger.info(
        "retrain_ml_model_request",
        min_samples=request.min_samples,
        test_split=request.test_split
    )

    try:
        # Path to training script
        script_path = Path("scripts/train_category_classifier.py")

        if not script_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Training script not found"
            )

        # Run training script
        logger.info("starting_ml_training")

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--min-samples", str(request.min_samples),
                "--test-split", str(request.test_split)
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max
        )

        if result.returncode == 0:
            logger.info("ml_training_complete")

            # Try to load new metrics
            import json
            metrics = None
            metrics_path = Path("models/training_metrics.json")

            if metrics_path.exists():
                try:
                    with open(metrics_path, 'r') as f:
                        metrics = json.load(f)
                except Exception as e:
                    logger.warning("failed_to_load_new_metrics", error=str(e))

            return RetrainResponse(
                status="completed",
                message="Model retrained successfully",
                metrics=metrics
            )
        else:
            logger.error(
                "ml_training_failed",
                returncode=result.returncode,
                stderr=result.stderr
            )

            return RetrainResponse(
                status="failed",
                message=f"Training failed: {result.stderr}"
            )

    except subprocess.TimeoutExpired:
        logger.error("ml_training_timeout")

        return RetrainResponse(
            status="failed",
            message="Training timeout (>5 minutes)"
        )

    except Exception as e:
        logger.error("ml_training_error", error=str(e))

        return RetrainResponse(
            status="failed",
            message=f"Training error: {str(e)}"
        )
