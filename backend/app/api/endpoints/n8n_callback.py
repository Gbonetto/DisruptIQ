"""
N8N Callback Endpoints

These endpoints receive updates from N8N workflows and inject them into the ThoughtStream
for real-time display in the UI.

IMPORTANT: These endpoints are called BY N8N, not by DisruptIQ.
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
import structlog
from datetime import datetime

from app.core.config import settings
from app.services.agents.thought_stream import ThoughtStream, ThoughtType, get_thought_stream

router = APIRouter()
logger = structlog.get_logger()


class N8NThoughtUpdate(BaseModel):
    """
    Thought update from N8N workflow

    This payload is sent by N8N workflows to provide real-time progress updates
    that will be displayed in the DisruptIQ UI.
    """
    thought_stream_id: str = Field(..., description="ID of the ThoughtStream to update")
    thought_type: Literal["SEARCHING", "PROCESSING", "EXECUTING", "VALIDATING", "COMPLETED", "WARNING", "ERROR"]
    title: str = Field(..., min_length=1, max_length=200, description="Short title (e.g., 'Envoi email à M. Dupont')")
    content: str = Field(default="", description="Detailed content (optional)")
    agent: str = Field(..., description="Agent name (e.g., 'N8N_WaterLeak')")
    progress: float = Field(..., ge=0.0, le=1.0, description="Progress from 0.0 to 1.0")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class N8NWorkflowResult(BaseModel):
    """
    Final result from N8N workflow execution

    Sent when the workflow completes (success or failure).
    """
    thought_stream_id: str
    workflow_name: str
    status: Literal["success", "error", "warning"]
    execution_time: float = Field(..., description="Execution time in seconds")
    result: Dict[str, Any] = Field(default_factory=dict, description="Workflow output")
    error: Optional[str] = None


# Dependency: Verify N8N authentication
async def verify_n8n_token(authorization: str = Header(...)):
    """Verify that the request comes from N8N with valid token"""
    expected_token = f"Bearer {settings.N8N_WEBHOOK_AUTH_TOKEN}"

    if authorization != expected_token:
        logger.warning("n8n_callback_unauthorized", provided_token=authorization[:20])
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid N8N webhook token"
        )

    return True


@router.post("/thought-update", status_code=200)
async def receive_thought_update(
    update: N8NThoughtUpdate,
    authenticated: bool = Depends(verify_n8n_token)
):
    """
    Receive a thought update from N8N workflow

    Example N8N HTTP Request node configuration:

    URL: http://backend:8000/api/n8n/callback/thought-update
    Method: POST
    Headers:
      - Authorization: Bearer {{$env.DISRUPTIQ_WEBHOOK_TOKEN}}
      - Content-Type: application/json
    Body:
    {
      "thought_stream_id": "{{$json.trace.thought_stream_id}}",
      "thought_type": "EXECUTING",
      "title": "Envoi email à M. Dupont",
      "content": "Email envoyé avec succès",
      "agent": "N8N_WaterLeak",
      "progress": 0.5,
      "metadata": {
        "email_sent": true,
        "recipient": "dupont@example.com"
      }
    }
    """
    try:
        logger.info(
            "n8n_thought_update_received",
            stream_id=update.thought_stream_id,
            type=update.thought_type,
            agent=update.agent,
            progress=update.progress
        )

        # Get ThoughtStream instance
        thought_stream = get_thought_stream(update.thought_stream_id)

        if not thought_stream:
            logger.warning(
                "thought_stream_not_found",
                stream_id=update.thought_stream_id
            )
            return {
                "status": "warning",
                "message": f"ThoughtStream {update.thought_stream_id} not found (may have closed)"
            }

        # Add thought to stream
        await thought_stream.add_thought(
            thought_type=ThoughtType[update.thought_type],
            title=update.title,
            content=update.content,
            agent=update.agent,
            progress=update.progress,
            data=update.metadata
        )

        logger.info(
            "n8n_thought_injected",
            stream_id=update.thought_stream_id,
            title=update.title
        )

        return {
            "status": "success",
            "message": "Thought added to stream",
            "stream_id": update.thought_stream_id
        }

    except KeyError as e:
        logger.error("invalid_thought_type", type=update.thought_type, error=str(e))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid thought_type: {update.thought_type}. Must be one of: SEARCHING, PROCESSING, EXECUTING, VALIDATING, COMPLETED, WARNING, ERROR"
        )

    except Exception as e:
        logger.error(
            "n8n_thought_update_failed",
            stream_id=update.thought_stream_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process thought update: {str(e)}"
        )


@router.post("/workflow-result", status_code=200)
async def receive_workflow_result(
    result: N8NWorkflowResult,
    authenticated: bool = Depends(verify_n8n_token)
):
    """
    Receive final workflow execution result from N8N

    This is called when the workflow completes (success or error).

    Example N8N HTTP Request node configuration:

    URL: http://backend:8000/api/n8n/callback/workflow-result
    Method: POST
    Headers:
      - Authorization: Bearer {{$env.DISRUPTIQ_WEBHOOK_TOKEN}}
      - Content-Type: application/json
    Body:
    {
      "thought_stream_id": "{{$json.trace.thought_stream_id}}",
      "workflow_name": "water_leak_emergency",
      "status": "success",
      "execution_time": 5.2,
      "result": {
        "emails_sent": 3,
        "sms_sent": 1,
        "professional_contacted": true
      }
    }
    """
    try:
        logger.info(
            "n8n_workflow_result_received",
            stream_id=result.thought_stream_id,
            workflow=result.workflow_name,
            status=result.status,
            execution_time=result.execution_time
        )

        # Get ThoughtStream instance
        thought_stream = get_thought_stream(result.thought_stream_id)

        if not thought_stream:
            logger.warning(
                "thought_stream_not_found_for_result",
                stream_id=result.thought_stream_id
            )
            return {
                "status": "warning",
                "message": f"ThoughtStream {result.thought_stream_id} not found"
            }

        # Add completion thought
        if result.status == "success":
            thought_type = ThoughtType.COMPLETED
            title = f"✅ Workflow {result.workflow_name} terminé"
            content = f"Exécution réussie en {result.execution_time:.1f}s"
        elif result.status == "error":
            thought_type = ThoughtType.ERROR
            title = f"❌ Workflow {result.workflow_name} échoué"
            content = result.error or "Erreur inconnue"
        else:  # warning
            thought_type = ThoughtType.WARNING
            title = f"⚠️  Workflow {result.workflow_name} complété avec avertissements"
            content = result.error or ""

        await thought_stream.add_thought(
            thought_type=thought_type,
            title=title,
            content=content,
            agent=f"N8N_{result.workflow_name}",
            progress=1.0,
            data={
                **result.result,
                "execution_time": result.execution_time
            }
        )

        logger.info(
            "n8n_workflow_result_processed",
            stream_id=result.thought_stream_id,
            status=result.status
        )

        return {
            "status": "success",
            "message": "Workflow result recorded",
            "stream_id": result.thought_stream_id
        }

    except Exception as e:
        logger.error(
            "n8n_workflow_result_failed",
            stream_id=result.thought_stream_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process workflow result: {str(e)}"
        )


@router.get("/ping", status_code=200)
async def ping(authenticated: bool = Depends(verify_n8n_token)):
    """
    Health check endpoint for N8N to verify connectivity

    N8N workflows can call this to verify the callback endpoint is accessible.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "DisruptIQ N8N Callback",
        "version": "1.0.0"
    }


@router.get("/health", status_code=200)
async def health():
    """
    Public health check (no authentication required)

    Used for monitoring and debugging.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/", status_code=200)
async def generic_callback(
    payload: Dict[str, Any],
    authenticated: bool = Depends(verify_n8n_token)
):
    """
    Generic callback endpoint for N8N workflows

    URL: http://backend:8000/api/n8n/callback

    This endpoint receives any callback from N8N (email results, workflow updates, etc.)
    and processes them accordingly.

    Used by the email workflow to send back results.
    """
    try:
        logger.info(
            "n8n_generic_callback_received",
            payload_keys=list(payload.keys()),
            success=payload.get("success"),
            message=payload.get("message")
        )

        # Check if this is an email workflow result
        if "emails_sent" in payload:
            return await _handle_email_callback(payload)

        # Check if this is a thought update
        if "thought_stream_id" in payload and "thought_type" in payload:
            update = N8NThoughtUpdate(**payload)
            return await receive_thought_update(update, authenticated)

        # Generic success response
        return {
            "status": "success",
            "message": "Callback received",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(
            "n8n_generic_callback_failed",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process callback: {str(e)}"
        )


async def _handle_email_callback(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle email workflow callback"""
    try:
        thought_stream_id = payload.get("thought_stream_id")
        success = payload.get("success", False)
        emails_sent = payload.get("emails_sent", [])

        if not thought_stream_id:
            logger.warning("email_callback_no_stream_id", payload=payload)
            return {
                "status": "warning",
                "message": "No thought_stream_id provided"
            }

        # Get ThoughtStream
        thought_stream = get_thought_stream(thought_stream_id)

        if not thought_stream:
            logger.warning(
                "thought_stream_not_found_for_email",
                stream_id=thought_stream_id
            )
            return {
                "status": "warning",
                "message": f"ThoughtStream {thought_stream_id} not found"
            }

        # Add completion thought
        if success:
            recipients_count = len(emails_sent)
            recipients_list = ", ".join([e.get("recipient", "unknown") for e in emails_sent[:3]])
            if recipients_count > 3:
                recipients_list += f" (+{recipients_count - 3} autres)"

            await thought_stream.add_thought(
                thought_type=ThoughtType.COMPLETED,
                title=f"✅ Email envoyé avec succès",
                content=f"Email envoyé à {recipients_count} destinataire(s): {recipients_list}",
                agent="N8N_Email",
                progress=1.0,
                data={
                    "emails_sent": emails_sent,
                    "subject": payload.get("subject", "")
                }
            )
        else:
            error_msg = payload.get("error", payload.get("message", "Erreur inconnue"))
            await thought_stream.add_thought(
                thought_type=ThoughtType.ERROR,
                title="❌ Échec de l'envoi d'email",
                content=error_msg,
                agent="N8N_Email",
                progress=1.0,
                data={"error": error_msg}
            )

        logger.info(
            "email_callback_processed",
            stream_id=thought_stream_id,
            success=success,
            recipients_count=len(emails_sent)
        )

        return {
            "status": "success",
            "message": "Email callback processed",
            "stream_id": thought_stream_id
        }

    except Exception as e:
        logger.error("email_callback_processing_failed", error=str(e), exc_info=True)
        raise
