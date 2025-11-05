"""
Workflows API Endpoints - N8N Automation

Endpoints pour gérer les workflows N8N:
- Liste des workflows disponibles
- Preview avec dry-run
- Trigger avec validation
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel

from app.services.n8n_workflow_service import (
    N8NWorkflowService,
    Workflow,
    WorkflowExecutionRequest,
    WorkflowExecutionResult,
    WorkflowPreview,
    DangerLevel,
    WorkflowCategory
)
from app.core.database import get_db, AsyncSession
import structlog

logger = structlog.get_logger()

router = APIRouter()

# Service singleton
workflow_service = N8NWorkflowService()


# =========================================================================
# Response Models
# =========================================================================

class WorkflowListResponse(BaseModel):
    """Response pour liste workflows"""
    workflows: List[dict]
    total: int


class WorkflowDetailResponse(BaseModel):
    """Response pour détails workflow"""
    workflow: dict


# =========================================================================
# Endpoints
# =========================================================================

@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    category: Optional[str] = None,
    danger_level: Optional[str] = None
):
    """
    Liste tous les workflows disponibles.

    Query params:
    - category: Filtrer par catégorie (emergency, legal, procurement, etc.)
    - danger_level: Filtrer par niveau de danger (low, medium, high, critical)
    """
    try:
        # Convertir filters en enums
        category_filter = WorkflowCategory(category) if category else None
        danger_filter = DangerLevel(danger_level) if danger_level else None

        workflows = workflow_service.list_workflows(
            category=category_filter,
            danger_level=danger_filter
        )

        return WorkflowListResponse(
            workflows=[wf.dict() for wf in workflows],
            total=len(workflows)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filtre invalide: {str(e)}"
        )


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(workflow_id: str):
    """
    Récupère les détails d'un workflow.
    """
    workflow = workflow_service.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} non trouvé"
        )

    return WorkflowDetailResponse(workflow=workflow.dict())


@router.post("/{workflow_id}/preview")
async def preview_workflow(
    workflow_id: str,
    inputs: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Génère un preview du workflow avant exécution.

    Effectue:
    - Validation des inputs
    - Estimation des actions
    - Identification entités affectées
    - Warnings basés sur danger level

    Returns:
    - WorkflowPreview avec preview_text et warnings
    """
    try:
        preview = await workflow_service.generate_preview(
            workflow_id=workflow_id,
            inputs=inputs,
            db=db
        )

        logger.info(
            "workflow_preview_requested",
            workflow_id=workflow_id,
            can_execute=preview.can_execute
        )

        return preview.dict()

    except Exception as e:
        logger.error(
            "workflow_preview_error",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur génération preview: {str(e)}"
        )


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecutionRequest
):
    """
    Exécute un workflow N8N.

    Body:
    - inputs: Paramètres du workflow
    - dry_run: true/false (simuler uniquement)
    - correlation_id: ID de corrélation (optionnel)

    Returns:
    - WorkflowExecutionResult avec outputs
    """
    try:
        # Forcer workflow_id from path
        request.workflow_id = workflow_id

        result = await workflow_service.execute_workflow(request)

        logger.info(
            "workflow_executed",
            workflow_id=workflow_id,
            success=result.success,
            dry_run=result.dry_run
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.error
            )

        return result.dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "workflow_execute_error",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur exécution workflow: {str(e)}"
        )


@router.get("/categories/list")
async def list_categories():
    """
    Liste les catégories de workflows disponibles.
    """
    return {
        "categories": [c.value for c in WorkflowCategory]
    }


@router.get("/danger-levels/list")
async def list_danger_levels():
    """
    Liste les niveaux de danger disponibles.
    """
    return {
        "danger_levels": [d.value for d in DangerLevel]
    }
