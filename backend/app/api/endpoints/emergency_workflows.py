"""
Emergency Workflows Execution Endpoint

This endpoint receives confirmed workflows from the frontend and triggers N8N execution.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import structlog
import httpx
from datetime import datetime

from app.core.config import settings
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = structlog.get_logger()


class WorkflowStep(BaseModel):
    """Single workflow step"""
    step_id: int
    step_order: int
    title: str
    enabled: bool
    is_critical: bool
    workflow_action: str
    n8n_node_type: str
    extracted_data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowData(BaseModel):
    """Workflow data to execute"""
    workflow_type: str
    workflow_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    steps: List[WorkflowStep]
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class WorkflowTrace(BaseModel):
    """Trace information"""
    conversation_id: Optional[str] = None
    request_id: str
    thought_stream_id: str
    timestamp: str


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute an emergency workflow"""
    workflow_data: WorkflowData
    trace: WorkflowTrace


@router.post("/execute", status_code=200)
async def execute_emergency_workflow(
    request: ExecuteWorkflowRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute an emergency workflow by sending it to N8N

    This endpoint is called by the frontend after user confirmation.

    Flow:
    1. Frontend receives `requires_confirmation: true` from chat
    2. Frontend shows confirmation modal with workflow preview
    3. User clicks "Execute"
    4. Frontend calls this endpoint
    5. This endpoint forwards to N8N webhook
    6. N8N executes and sends callbacks
    7. ThoughtStream updates in real-time
    """
    try:
        logger.info(
            "emergency_workflow_execution_requested",
            workflow_type=request.workflow_data.workflow_type,
            request_id=request.trace.request_id,
            steps_count=len(request.workflow_data.steps)
        )

        # Prepare N8N payload
        n8n_payload = {
            "request_id": request.trace.request_id,
            "workflow_data": request.workflow_data.dict(),
            "trace": request.trace.dict()
        }

        # Determine N8N webhook URL based on workflow type
        workflow_type = request.workflow_data.workflow_type

        # V1: Hardcoded mapping (V2: dynamic from DB)
        webhook_paths = {
            "water_leak": "emergency-water-leak",
            # Future: "fire", "elevator", etc.
        }

        webhook_path = webhook_paths.get(workflow_type)
        if not webhook_path:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown workflow type: {workflow_type}"
            )

        # Construct full N8N URL
        n8n_url = f"{settings.N8N_WEBHOOK_BASE_URL}/webhook/{webhook_path}"

        logger.info(
            "triggering_n8n_workflow",
            url=n8n_url,
            workflow_type=workflow_type
        )

        # Call N8N webhook
        async with httpx.AsyncClient(timeout=float(settings.N8N_TIMEOUT)) as client:
            response = await client.post(
                n8n_url,
                json=n8n_payload,
                headers={
                    "Authorization": f"Bearer {settings.N8N_WEBHOOK_AUTH_TOKEN}",
                    "Content-Type": "application/json"
                }
            )

        if response.status_code == 200:
            logger.info(
                "n8n_workflow_triggered_successfully",
                request_id=request.trace.request_id,
                status_code=response.status_code
            )

            return {
                "success": True,
                "message": "Workflow execution started",
                "request_id": request.trace.request_id,
                "thought_stream_id": request.trace.thought_stream_id,
                "n8n_response": response.json() if response.text else {}
            }
        else:
            logger.error(
                "n8n_workflow_trigger_failed",
                request_id=request.trace.request_id,
                status_code=response.status_code,
                response=response.text
            )

            raise HTTPException(
                status_code=502,
                detail=f"N8N workflow trigger failed: {response.status_code}"
            )

    except httpx.TimeoutException as e:
        logger.error(
            "n8n_workflow_timeout",
            request_id=request.trace.request_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=504,
            detail="N8N workflow execution timeout"
        )

    except httpx.HTTPError as e:
        logger.error(
            "n8n_workflow_http_error",
            request_id=request.trace.request_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=502,
            detail=f"N8N communication error: {str(e)}"
        )

    except Exception as e:
        logger.error(
            "emergency_workflow_execution_failed",
            request_id=request.trace.request_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute workflow: {str(e)}"
        )


@router.get("/health", status_code=200)
async def health():
    """Health check for emergency workflows endpoint"""
    return {
        "status": "healthy",
        "service": "emergency_workflows",
        "timestamp": datetime.utcnow().isoformat()
    }
