"""
Multi-Agent Assistant API Endpoint
Intelligent assistant with orchestrated agents
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import asyncio

from app.core.database import get_db
from app.models.intent import AgentResponse  # Centralized intent system
from app.services.agents.orchestrator_factory import get_orchestrator
from app.services.agents.thought_stream import get_thought_stream, cleanup_stream, ThoughtType

router = APIRouter()
logger = structlog.get_logger()


class AssistantMessage(BaseModel):
    """Chat message"""
    role: str  # "user" or "assistant"
    content: str


class AssistantRequest(BaseModel):
    """Assistant chat request"""
    message: str
    conversation_history: Optional[List[AssistantMessage]] = []
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    selected_sources: Optional[List[str]] = None  # ['sql', 'rag', 'web'] or None for auto


class AssistantResponseModel(BaseModel):
    """Assistant response"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    agents_used: List[str] = []
    suggestions: List[str] = []
    session_id: str


@router.post("/chat", response_model=AssistantResponseModel)
async def assistant_chat(
    request: AssistantRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Main assistant chat endpoint

    This endpoint:
    1. Receives user message
    2. Routes to Orchestrator Agent
    3. Returns intelligent response with agent coordination

    Example requests:
    - "Combien de copropriétaires dans l'Immeuble A?" → SQL Agent
    - "Envoyer email pour dégât des eaux" → Email + Workflow Agents
    - "Demander devis aux jardiniers" → SQL + Template + Workflow Agents
    """
    try:
        logger.info("assistant_request_received", message=request.message[:100])

        # Get singleton orchestrator (eliminates 400ms re-instantiation overhead)
        orchestrator = get_orchestrator()

        # Process request with 30s timeout protection
        try:
            result: AgentResponse = await asyncio.wait_for(
                orchestrator.process(
                    user_input=request.message,
                    db=db,
                    context=request.context,
                    conversation_history=[msg.dict() for msg in request.conversation_history],
                    selected_sources=request.selected_sources  # User-controlled source selection
                ),
                timeout=90.0
            )
        except asyncio.TimeoutError:
            logger.error("request_timeout", message=request.message[:100])
            raise HTTPException(
                status_code=504,
                detail="La requête a pris trop de temps. Veuillez réessayer avec une question plus simple."
            )

        # Build response
        response = AssistantResponseModel(
            success=result.success,
            message=result.message,
            data=result.data,
            agents_used=result.agents_used,
            suggestions=result.suggestions,
            session_id=request.session_id or "default"
        )

        logger.info(
            "assistant_request_completed",
            success=result.success,
            agents=result.agents_used
        )

        return response

    except Exception as e:
        logger.error("assistant_request_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Assistant error: {str(e)}"
        )


@router.post("/chat/upload")
async def assistant_chat_with_file(
    message: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with file upload (for document analysis)

    Example: Upload facture PDF + message "Analyse cette facture"
    → OCR Agent + SQL Agent (persist)
    """
    try:
        logger.info("assistant_file_upload", filename=file.filename, message=message[:50])

        # Read file
        file_content = await file.read()

        # Build context with file
        context = {
            "file": {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(file_content),
                "content": file_content
            }
        }

        # Initialize orchestrator
        orchestrator = OrchestratorAgent()

        # Process with file context
        result: AgentResponse = await orchestrator.process(
            user_input=message,
            db=db,
            context=context
        )

        return AssistantResponseModel(
            success=result.success,
            message=result.message,
            data=result.data,
            agents_used=result.agents_used,
            suggestions=result.suggestions,
            session_id="default"
        )

    except Exception as e:
        logger.error("assistant_file_upload_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"File upload error: {str(e)}"
        )


@router.get("/capabilities")
async def get_capabilities():
    """
    List assistant capabilities

    Returns:
    - Available agent types
    - Supported operations
    - Example queries
    """
    return {
        "agents": [
            {
                "name": "SQL Agent",
                "description": "Requêtes sur données structurées (copropriétaires, copropriétés, fournisseurs)",
                "examples": [
                    "Combien de copropriétaires dans l'Immeuble A?",
                    "Liste des fournisseurs jardiniers actifs",
                    "Statistiques des emails urgents cette semaine"
                ]
            },
            {
                "name": "RAG Agent",
                "description": "Recherche dans documents (contrats, règlements, procédures)",
                "examples": [
                    "Procédure pour un dégât des eaux",
                    "Règlement copropriété article 5",
                    "Contrat avec le jardinier"
                ]
            },
            {
                "name": "Email Agent",
                "description": "Génération d'emails personnalisés",
                "examples": [
                    "Envoyer email aux copropriétaires pour AG",
                    "Alerte urgence dégât des eaux",
                    "Convocation assemblée générale le 15 novembre"
                ]
            },
            {
                "name": "Workflow Agent (N8N)",
                "description": "Déclenchement de workflows automatisés",
                "examples": [
                    "Créer brouillon Gmail pour tous les copropriétaires",
                    "Demander devis aux jardiniers",
                    "Déclencher alerte SMS urgence"
                ]
            },
            {
                "name": "Template Agent",
                "description": "Remplissage de templates (emails, lettres, devis)",
                "examples": [
                    "Générer convocation AG",
                    "Créer relance paiement charges",
                    "Demande de devis standard"
                ]
            }
        ],
        "workflows_available": [
            "Email Draft Creator",
            "Bulk Devis Request",
            "Emergency Alert (SMS + Email)",
            "Document OCR Processor"
        ]
    }


@router.get("/templates")
async def list_templates():
    """List all available templates"""
    from app.services.agents.template_agent import TemplateAgent

    template_agent = TemplateAgent()
    templates = template_agent.list_templates()

    return {
        "templates": templates,
        "count": len(templates)
    }
