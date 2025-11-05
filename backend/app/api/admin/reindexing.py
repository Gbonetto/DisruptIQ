"""
Admin API - RAG Reindexing Management
Endpoints pour gérer la réindexation RAG après changements de schéma
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.services.rag_reindexing_service import get_reindexing_service
from app.services.schema_introspection_service import get_schema_service


router = APIRouter(prefix="/reindexing", tags=["Admin - RAG Reindexing"])


# ============================================================================
# Response Models
# ============================================================================

class ReindexingCheckResponse(BaseModel):
    """Résultat de la vérification de schéma"""
    table: str
    needs_reindexing: bool
    reason: str
    affected_fields: list = []
    schema_changes: dict = {}


class ReindexingTriggerResponse(BaseModel):
    """Résultat du déclenchement de réindexation"""
    status: str
    table: str
    message: str
    job_id: Optional[str] = None  # Pour future async job tracking


class ReindexingResultResponse(BaseModel):
    """Résultat de la réindexation"""
    success: bool
    table: str
    total_reindexed: int
    batches_processed: int
    errors: list = []
    duration_ms: int
    message: Optional[str] = None


class IndexedTablesResponse(BaseModel):
    """Liste des tables indexées"""
    tables: list
    count: int


class TableConfigResponse(BaseModel):
    """Configuration d'indexation d'une table"""
    table: str
    text_fields: list
    metadata_fields: list
    id_field: str
    is_indexed_field: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/tables", response_model=IndexedTablesResponse)
async def list_indexed_tables():
    """
    Liste toutes les tables indexées dans RAG

    Returns:
        Liste des tables avec leur configuration
    """
    service = get_reindexing_service()
    tables = service.get_indexed_tables_list()

    return {
        "tables": tables,
        "count": len(tables)
    }


@router.get("/tables/{table_name}/config", response_model=TableConfigResponse)
async def get_table_config(table_name: str):
    """
    Récupère la configuration d'indexation d'une table

    Args:
        table_name: Nom de la table

    Returns:
        Configuration (text_fields, metadata_fields, etc.)
    """
    service = get_reindexing_service()
    config = service.get_table_config(table_name)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not configured for indexing"
        )

    return {
        "table": table_name,
        **config
    }


@router.get("/check/{table_name}", response_model=ReindexingCheckResponse)
async def check_reindexing_needed(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Vérifie si une réindexation est nécessaire après changement de schéma

    Args:
        table_name: Table à vérifier (ex: "professionnels")

    Returns:
        Résultat de la vérification avec détails des changements

    Example:
        GET /api/admin/reindexing/check/professionnels

        Response:
        {
            "table": "professionnels",
            "needs_reindexing": true,
            "reason": "1 indexed field(s) changed",
            "affected_fields": [["added", "certification_iso"]],
            "schema_changes": {
                "added_columns": ["certification_iso"],
                "removed_columns": []
            }
        }
    """
    service = get_reindexing_service()
    result = await service.detect_indexed_field_changes(db, table_name)

    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    return result


@router.post("/trigger/{table_name}", response_model=ReindexingTriggerResponse)
async def trigger_reindexing(
    table_name: str,
    batch_size: int = Query(100, ge=10, le=1000, description="Taille des batchs"),
    max_records: Optional[int] = Query(None, ge=1, description="Limite max de records (None = tous)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Déclenche une réindexation complète d'une table

    Args:
        table_name: Table à réindexer
        batch_size: Taille des batchs (10-1000, défaut: 100)
        max_records: Limite max de records à réindexer (défaut: tous)

    Returns:
        Statut du déclenchement

    Example:
        POST /api/admin/reindexing/trigger/professionnels?batch_size=50&max_records=500

        Response:
        {
            "status": "reindexing_started",
            "table": "professionnels",
            "message": "Reindexing 500 records in batches of 50"
        }

    Note:
        - Cette opération peut être longue (plusieurs minutes)
        - Utiliser batch_size petit pour grosse DB (éviter surcharge)
        - Utiliser max_records pour tester sur subset avant full reindex
    """
    service = get_reindexing_service()

    # Vérifier que table existe dans config
    if table_name not in service.get_indexed_tables_list():
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not configured for indexing"
        )

    # SYNCHRONOUS reindexing (pour simplicité - Phase 1)
    # Phase 2: Implémenter background job avec Celery/ARQ
    try:
        result = await service.reindex_table(
            db=db,
            table_name=table_name,
            batch_size=batch_size,
            max_records=max_records
        )

        if not result["success"]:
            return {
                "status": "reindexing_completed_with_errors",
                "table": table_name,
                "message": f"Reindexed {result['total_reindexed']} records with {len(result['errors'])} errors",
                "result": result
            }

        return {
            "status": "reindexing_completed",
            "table": table_name,
            "message": f"Successfully reindexed {result['total_reindexed']} records in {result['duration_ms']}ms"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reindexing failed: {str(e)}"
        )


@router.get("/schema/drift", response_model=dict)
async def detect_schema_drift_all_tables(
    db: AsyncSession = Depends(get_db)
):
    """
    Détecte les dérives de schéma sur TOUTES les tables indexées

    Returns:
        Dict avec résultats pour chaque table

    Example:
        GET /api/admin/reindexing/schema/drift

        Response:
        {
            "tables_checked": 3,
            "tables_with_drift": 1,
            "results": {
                "professionnels": {
                    "needs_reindexing": true,
                    "affected_fields": [["added", "certification_iso"]]
                },
                "documents": {
                    "needs_reindexing": false
                },
                "coproprietes": {
                    "needs_reindexing": false
                }
            }
        }
    """
    service = get_reindexing_service()
    tables = service.get_indexed_tables_list()

    results = {}
    tables_with_drift = 0

    for table_name in tables:
        check_result = await service.detect_indexed_field_changes(db, table_name)
        results[table_name] = check_result

        if check_result.get("needs_reindexing"):
            tables_with_drift += 1

    return {
        "tables_checked": len(tables),
        "tables_with_drift": tables_with_drift,
        "results": results,
        "summary": f"{tables_with_drift}/{len(tables)} tables need reindexing"
    }


@router.get("/schema/columns/{table_name}", response_model=dict)
async def get_table_columns(table_name: str):
    """
    Récupère les colonnes d'une table depuis SQLAlchemy

    Args:
        table_name: Nom de la table

    Returns:
        Liste des colonnes avec types et flags

    Example:
        GET /api/admin/reindexing/schema/columns/professionnels

        Response:
        {
            "table": "professionnels",
            "columns": [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "nullable": false,
                    "primary_key": true
                },
                ...
            ]
        }
    """
    schema_service = get_schema_service()
    columns = schema_service.get_table_columns(table_name)

    if not columns:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found in registered models"
        )

    return {
        "table": table_name,
        "columns": columns,
        "count": len(columns)
    }


@router.post("/schema/invalidate-cache")
async def invalidate_schema_cache():
    """
    Invalide le cache de schéma (force régénération)

    Utiliser après une migration Alembic pour rafraîchir le schéma.

    Returns:
        Confirmation

    Example:
        POST /api/admin/reindexing/schema/invalidate-cache

        Response:
        {
            "status": "cache_invalidated",
            "message": "Schema cache cleared, will regenerate on next access"
        }
    """
    schema_service = get_schema_service()
    schema_service.invalidate_cache()

    return {
        "status": "cache_invalidated",
        "message": "Schema cache cleared, will regenerate on next access"
    }
