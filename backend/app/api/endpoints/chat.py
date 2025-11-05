"""
Chat Interface Endpoints
Intelligent orchestration between RAG and SQL modes with Conversational Intelligence
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import structlog
import uuid

from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.services.orchestrator_service import OrchestratorService
from app.core.dependencies import get_llm_service, get_rag_service
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

# Conversational Intelligence imports
from app.services.conversation.session_manager import SessionManager
from app.services.conversation.intent_classifier import IntentClassifier
from app.services.conversation.llm_intent_classifier import LLMIntentClassifier
from app.services.conversation.entity_extractor import EntityExtractor
from app.services.conversation.query_rewriter import QueryRewriter
from app.services.conversation.response_adapter import ResponseAdapter
from app.services.conversation.suggestion_engine import SuggestionEngine

router = APIRouter()
logger = structlog.get_logger()


class ChatMessage(BaseModel):
    """Chat message schema"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat request"""
    message: str
    conversation_history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response"""
    message: str
    sources: List[Dict]
    session_id: str


class ObservabilityData(BaseModel):
    """Observability metadata"""
    run_id: Optional[int]
    plan_steps: int
    total_latency_ms: int
    estimated_tokens: int


class EvaluationData(BaseModel):
    """Evaluation results"""
    passed: bool
    rules_checked: int
    rules_passed: int
    critical_failures: int
    warnings: int
    failed_rules: List[str]


class ChatResponseWithPlan(BaseModel):
    """Enhanced chat response with observability, evaluation, and intelligence"""
    message: str
    sources: List[Dict]
    session_id: str
    observability: ObservabilityData
    evaluation: EvaluationData
    agents_used: List[str]
    confidence: float
    # New intelligence fields
    suggestions: Optional[List[Dict]] = []
    entities: Optional[Dict] = {}
    rewritten_query: Optional[str] = None
    primary_intent: Optional[str] = None


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask a question with intelligent routing (RAG or SQL)

    The orchestrator automatically determines if your question needs:
    - RAG: Document search and knowledge retrieval
    - SQL: Database queries and statistics

    Example:
    {
        "message": "Combien d'emails urgents avons-nous?",  # -> SQL
        "conversation_history": []
    }
    {
        "message": "Comment procéder pour un dégât des eaux?",  # -> RAG
        "conversation_history": []
    }

    Performance optimizations:
    - Intelligent routing reduces unnecessary service calls
    - Reuses singleton services (no re-initialization)
    """
    try:
        # Use orchestrator for intelligent routing
        orchestrator = OrchestratorService()

        logger.info("orchestrator_processing", question=request.message[:50])

        result = await orchestrator.process_query(
            query=request.message,
            db=db,
            conversation_history=[msg.dict() for msg in request.conversation_history]
        )

        logger.info(
            "orchestrator_completed",
            question=request.message[:50],
            mode=result.get("mode"),
            success=result.get("success")
        )

        # Format response based on mode
        if result["mode"] == "sql":
            # SQL mode: include query and results
            return {
                "message": result["response"],
                "sources": [{
                    "text": f"Mode: SQL Database Query",
                    "metadata": {
                        "title": "SQL Query Result",
                        "sql": result.get("sql_query", ""),
                        "row_count": result.get("row_count", 0)
                    }
                }],
                "session_id": request.session_id or "default"
            }
        else:
            # RAG mode: include document sources
            return {
                "message": result["response"],
                "sources": result.get("sources", []),
                "session_id": request.session_id or "default"
            }

    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(e)}"
        )


@router.post("/with-plan", response_model=ChatResponseWithPlan)
async def ask_question_with_plan(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask a question with FULL OBSERVABILITY, EVALUATION, and CONVERSATIONAL INTELLIGENCE

    This endpoint uses the enhanced orchestrator with:
    - ✅ Execution plan generation (Planner DAG)
    - ✅ Rule-based validation (Evaluator)
    - ✅ Complete observability tracking (AgentRun, AgentSteps)
    - ✅ SQL canonical views for security
    - ✅ Citation validation for RAG responses
    - ✅ Conflict detection for HYBRID queries
    - ✅ Conversational memory and context retention
    - ✅ Intent classification with context awareness
    - ✅ User profiling and personalization
    - ✅ Automatic learning from interactions

    Returns enhanced response with:
    - message: The response text
    - sources: Citations and sources used
    - observability: Run ID, latency, tokens, plan steps
    - evaluation: Rules checked, passed/failed, warnings
    - agents_used: List of agents involved
    - confidence: Overall confidence score

    Example request:
    {
        "message": "Liste des plombiers actifs",
        "conversation_history": [],
        "session_id": "user-123"
    }

    Example response:
    {
        "message": "Trouvé 5 plombiers actifs...",
        "sources": [...],
        "session_id": "user-123",
        "observability": {
            "run_id": 456,
            "plan_steps": 3,
            "total_latency_ms": 1234,
            "estimated_tokens": 500
        },
        "evaluation": {
            "passed": true,
            "rules_checked": 3,
            "rules_passed": 3,
            "critical_failures": 0,
            "warnings": 0,
            "failed_rules": []
        },
        "agents_used": ["sql_agent"],
        "confidence": 0.95
    }

    ⚠️ IMPORTANT: If evaluation.passed is false, the response may not meet
    quality standards (e.g., missing citations, SQL errors, conflicts).
    """
    try:
        # Import orchestrator agent with Phase 1 integration
        from app.services.agents.orchestrator_agent import OrchestratorAgent

        # Initialize conversational intelligence services
        session_manager = SessionManager(db)
        llm_service = get_llm_service()

        # Initialize all 5 intelligence services
        entity_extractor = EntityExtractor()
        llm_intent_classifier = LLMIntentClassifier(llm_service)
        query_rewriter = QueryRewriter(llm_service)
        response_adapter = ResponseAdapter()
        suggestion_engine = SuggestionEngine()

        # Generate conversation ID (use session_id or generate new)
        conversation_id = request.session_id or f"session-{uuid.uuid4().hex[:12]}"

        # Step 1: Create or load conversation session
        session = await session_manager.get_session(
            session_id=conversation_id,
            create_if_not_exists=True
        )

        # Set user_id if available (TODO: Extract from auth context)
        # if session and not session.user_id:
        #     session.user_id = current_user.id
        #     await session_manager.db.commit()

        # Step 2: Load conversation history from database (last 10 turns)
        conversation_history = await session_manager.get_session_history(
            session_id=session.session_id,
            last_n_turns=10
        )

        logger.info(
            "conversational_context_loaded",
            session_id=session.session_id,
            history_turns=len(conversation_history),
            current_topics=session.topics
        )

        # Step 3: Extract entities from message (Phase 1)
        extracted_entities = entity_extractor.extract_entities(request.message)

        logger.info(
            "entities_extracted",
            entities_summary=entity_extractor.format_entities_summary(extracted_entities),
            amounts=len(extracted_entities.get('amounts', [])),
            dates=len(extracted_entities.get('dates', [])),
            categories=len(extracted_entities.get('categories', []))
        )

        # Step 4: Rewrite query with context (Phase 3)
        rewritten_message = await query_rewriter.rewrite(
            message=request.message,
            context=conversation_history,
            extracted_entities=extracted_entities
        )

        if rewritten_message != request.message:
            logger.info(
                "query_rewritten",
                original=request.message[:50],
                rewritten=rewritten_message[:50]
            )

        # Step 5: Classify intent with LLM fallback (Phase 2)
        intent_scores = await llm_intent_classifier.classify_async(
            message=rewritten_message,
            conversation_context=conversation_history,
            use_llm=True  # Enable LLM for better accuracy
        )

        primary_intent = max(intent_scores.items(), key=lambda x: x[1])[0]
        intent_confidence = intent_scores[primary_intent]

        logger.info(
            "intent_classified_with_llm",
            primary_intent=primary_intent,
            confidence=intent_confidence,
            all_intents=intent_scores
        )

        # Step 6: Check if clarification is needed
        should_clarify, clarification_message = llm_intent_classifier.should_ask_clarification(
            intent_scores
        )

        if should_clarify:
            # Save clarification turn
            await session_manager.add_turn(
                session_id=session.session_id,
                user_message=request.message,
                assistant_message=clarification_message,
                detected_intent=primary_intent,
                intent_confidence=intent_confidence,
                all_intents=intent_scores,
                extracted_entities=extracted_entities,
                response_type="clarification"
            )

            logger.info("clarification_required", message=clarification_message)

            # Return clarification response
            return ChatResponseWithPlan(
                message=clarification_message,
                sources=[],
                session_id=session.session_id,
                observability=ObservabilityData(
                    run_id=None,
                    plan_steps=0,
                    total_latency_ms=0,
                    estimated_tokens=0
                ),
                evaluation=EvaluationData(
                    passed=True,
                    rules_checked=0,
                    rules_passed=0,
                    critical_failures=0,
                    warnings=0,
                    failed_rules=[]
                ),
                agents_used=["clarification"],
                confidence=0.5,
                suggestions=[],
                entities=extracted_entities,
                rewritten_query=rewritten_message,
                primary_intent=primary_intent
            )

        # Step 7: Get user profile for personalization (Phase 4)
        user_profile = None
        if session.user_id:
            user_profile = await session_manager.get_user_profile(
                user_id=session.user_id,
                create_if_not_exists=True
            )
            logger.info(
                "user_profile_loaded",
                user_id=session.user_id,
                expertise_level=user_profile.expertise_level if user_profile else None,
                preferred_style=user_profile.preferred_response_style if user_profile else None
            )

        # Step 8: Extract sub-intents for more granular understanding
        sub_intents = llm_intent_classifier.detect_sub_intents(
            message=rewritten_message,
            primary_intent=primary_intent
        )

        logger.info(
            "orchestrator_with_plan_processing",
            question=rewritten_message[:50],
            conversation_id=conversation_id,
            primary_intent=primary_intent,
            sub_intents=sub_intents,
            entities=entity_extractor.format_entities_summary(extracted_entities)
        )

        # Step 9: Process with enhanced orchestrator
        # Use rewritten message and pass entities for filtering
        orchestrator = OrchestratorAgent()

        response = await orchestrator.process_with_plan(
            user_input=rewritten_message,  # Use rewritten query
            db=db,
            conversation_id=conversation_id,
            conversation_history=[msg.dict() for msg in request.conversation_history],
            thought_stream=None,
            state_manager=None
        )

        logger.info(
            "orchestrator_with_plan_completed",
            question=request.message[:50],
            success=response.success,
            run_id=response.data.get("observability", {}).get("run_id"),
            evaluation_passed=response.data.get("evaluation", {}).get("passed")
        )

        # Extract sources from response data
        sources = []
        if response.data and "sources" in response.data:
            sources = response.data["sources"]
        elif response.data and "sql" in response.data:
            # SQL query result
            sources = [{
                "text": "SQL Database Query",
                "metadata": {
                    "title": "SQL Query Result",
                    "sql": response.data.get("sql", ""),
                    "table": "Canonical Views (vw_*)"
                }
            }]

        # Step 10: Adapt response to user profile (Phase 4)
        adapted_message = response_adapter.adapt_response(
            response=response.message,
            user_profile=user_profile,
            intent=primary_intent,
            context={"entities": extracted_entities}
        )

        if adapted_message != response.message:
            logger.info(
                "response_adapted",
                original_length=len(response.message),
                adapted_length=len(adapted_message),
                expertise=user_profile.expertise_level if user_profile else "none"
            )

        # Step 11: Generate smart suggestions (Phase 4)
        suggestions = suggestion_engine.generate_suggestions(
            intent=primary_intent,
            query_result=response.data,
            user_profile=user_profile,
            extracted_entities=extracted_entities,
            max_suggestions=3
        )

        suggestions_dict = [s.to_dict() for s in suggestions]

        logger.info(
            "suggestions_generated",
            count=len(suggestions),
            types=[s.type for s in suggestions]
        )

        # Step 12: Save conversation turn to database
        await session_manager.add_turn(
            session_id=session.session_id,
            user_message=request.message,
            assistant_message=adapted_message,
            detected_intent=primary_intent,
            intent_confidence=intent_confidence,
            all_intents=intent_scores,
            extracted_entities=extracted_entities,
            sub_intents=sub_intents,
            response_type="answer",
            sources_used=sources,
            agents_used=response.agents_used,
            execution_time_ms=response.data.get("observability", {}).get("total_latency_ms", 0),
            orchestrator_mode=response.data.get("mode", "unknown")
        )

        logger.info(
            "conversation_turn_saved",
            session_id=session.session_id,
            turn_number=session.turns_count + 1
        )

        # Step 13: Build enhanced response with all intelligence features
        return ChatResponseWithPlan(
            message=adapted_message,  # Adapted response
            sources=sources,
            session_id=conversation_id,
            observability=ObservabilityData(**response.data["observability"]),
            evaluation=EvaluationData(**response.data["evaluation"]),
            agents_used=response.agents_used,
            confidence=response.confidence,
            # Intelligence enhancements
            suggestions=suggestions_dict,
            entities=extracted_entities,
            rewritten_query=rewritten_message if rewritten_message != request.message else None,
            primary_intent=primary_intent
        )

    except Exception as e:
        logger.error("chat_with_plan_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question with plan: {str(e)}"
        )


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a session

    Returns all conversation turns for the specified session with:
    - User messages
    - Assistant responses
    - Detected intents and confidence
    - Timestamps
    - Feedback ratings
    """
    try:
        session_manager = SessionManager(db)

        # Get session
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )

        # Get full history
        turns = await session_manager.get_session_history(
            session_id=session_id,
            last_n_turns=None  # Get all turns
        )

        # Format turns for response
        messages = []
        for turn in turns:
            messages.append({
                "turn_number": turn.turn_number,
                "timestamp": turn.timestamp.isoformat(),
                "user_message": turn.user_message,
                "assistant_message": turn.assistant_message,
                "detected_intent": turn.detected_intent,
                "intent_confidence": turn.intent_confidence,
                "response_type": turn.response_type,
                "user_satisfied": turn.user_satisfied,
                "feedback_rating": turn.feedback_rating
            })

        return {
            "session_id": session.session_id,
            "started_at": session.started_at.isoformat(),
            "turns_count": session.turns_count,
            "topics": session.topics,
            "messages": messages
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_history_error", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}"
        )


@router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    End a conversation session

    Marks the session as ended but keeps the data for analytics.
    Use this when the user explicitly ends a conversation.
    """
    try:
        session_manager = SessionManager(db)

        # End session
        await session_manager.end_session(session_id)

        logger.info("session_ended", session_id=session_id)

        return {
            "message": "Session ended successfully",
            "session_id": session_id
        }

    except Exception as e:
        logger.error("end_session_error", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to end session: {str(e)}"
        )


# === Feedback Endpoints ===


class FeedbackRequest(BaseModel):
    """Feedback request schema"""
    turn_id: int
    satisfied: Optional[bool] = None
    rating: Optional[int] = None
    feedback_text: Optional[str] = None
    corrected_intent: Optional[str] = None


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit user feedback for a conversation turn

    Feedback types:
    - satisfied: True/False (thumbs up/down)
    - rating: 1-5 stars
    - feedback_text: Optional text feedback
    - corrected_intent: Correction if system misunderstood intent

    This feedback is used to:
    - Improve intent classification accuracy
    - Personalize user experience
    - Train machine learning models
    - Monitor system performance

    Example:
    {
        "turn_id": 123,
        "satisfied": true,
        "rating": 5,
        "feedback_text": "Perfect response!",
        "corrected_intent": null
    }
    """
    try:
        session_manager = SessionManager(db)

        # Validate rating if provided
        if request.rating is not None and (request.rating < 1 or request.rating > 5):
            raise HTTPException(
                status_code=400,
                detail="Rating must be between 1 and 5"
            )

        # Update turn feedback
        await session_manager.update_turn_feedback(
            turn_id=request.turn_id,
            satisfied=request.satisfied,
            rating=request.rating,
            feedback_text=request.feedback_text,
            corrected_intent=request.corrected_intent
        )

        logger.info(
            "feedback_submitted",
            turn_id=request.turn_id,
            satisfied=request.satisfied,
            rating=request.rating,
            has_correction=request.corrected_intent is not None
        )

        return {
            "message": "Feedback submitted successfully",
            "turn_id": request.turn_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("submit_feedback_error", error=str(e), turn_id=request.turn_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@router.get("/profile/{user_id}")
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get user profile with learned preferences

    Returns:
    - Preferred copropriété
    - Most common intents
    - Favorite queries
    - Expertise level
    - Interaction statistics
    - Recent entities used

    This information is used to personalize the user experience.
    """
    try:
        session_manager = SessionManager(db)

        profile = await session_manager.get_user_profile(
            user_id=user_id,
            create_if_not_exists=False
        )

        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Profile for user {user_id} not found"
            )

        return {
            "user_id": profile.user_id,
            "default_copropriete_id": profile.default_copropriete_id,
            "preferred_date_range": profile.preferred_date_range,
            "preferred_response_style": profile.preferred_response_style,
            "preferred_language": profile.preferred_language,
            "most_common_intents": profile.most_common_intents,
            "favorite_queries": profile.favorite_queries,
            "interests": profile.interests,
            "expertise_level": profile.expertise_level,
            "total_sessions": profile.total_sessions,
            "total_turns": profile.total_turns,
            "avg_satisfaction": profile.avg_satisfaction,
            "last_interaction_at": profile.last_interaction_at.isoformat() if profile.last_interaction_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_profile_error", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user profile: {str(e)}"
        )
