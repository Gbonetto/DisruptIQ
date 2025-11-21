"""
Multi-Agent Assistant with Streaming Chain of Thoughts
Real-time reasoning display (DeepSeek-style)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import asyncio

from app.core.database import get_db
from app.services.agents.orchestrator_agent import OrchestratorAgent
from app.services.agents.thought_stream import get_thought_stream, cleanup_stream, ThoughtType
from app.services.agents.state_registry import get_state_manager, cleanup_state_manager

router = APIRouter()
logger = structlog.get_logger()


class StreamChatRequest(BaseModel):
    """Streaming chat request"""
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    context: Optional[Dict[str, Any]] = None


@router.get("/chat/stream")
async def assistant_chat_stream(
    message: str,
    conversation_history: str = "[]",
    session_id: str = "default",  # Session ID for state tracking
    active_document_ids: str = "[]",  # Active document IDs for RAG filtering
    selected_sources: str = "[]",  # User-selected sources ['sql', 'rag', 'web']
    db: AsyncSession = Depends(get_db)
):
    """
    Streaming assistant chat with Chain of Thoughts

    Returns Server-Sent Events (SSE) stream showing:
    - Real-time reasoning steps
    - Agent activations
    - Progress indicators
    - Final response

    Example SSE events:
    ```
    event: thought
    data: {"type": "analyzing", "title": "Analyse...", "content": "..."}

    event: thought
    data: {"type": "executing", "agent": "sql_agent", "title": "Requête SQL", ...}

    event: response
    data: {"success": true, "message": "Voici les résultats...", ...}
    ```

    Usage with JavaScript:
    ```js
    const eventSource = new EventSource('/api/assistant-v2/chat/stream');
    eventSource.addEventListener('thought', (e) => {
        const thought = JSON.parse(e.data);
        console.log(thought.title, thought.content);
    });
    eventSource.addEventListener('response', (e) => {
        const response = JSON.parse(e.data);
        console.log('Final:', response.message);
        eventSource.close();
    });
    ```
    """
    # Use provided session_id or default (for state tracking across upload and chat)

    async def event_generator():
        """Generate Server-Sent Events"""
        try:
            # Parse conversation history, document IDs, and selected sources from JSON strings
            import json
            try:
                parsed_history = json.loads(conversation_history)
            except json.JSONDecodeError:
                parsed_history = []

            try:
                parsed_doc_ids = json.loads(active_document_ids)
            except json.JSONDecodeError:
                parsed_doc_ids = []

            try:
                parsed_selected_sources = json.loads(selected_sources)
            except json.JSONDecodeError:
                parsed_selected_sources = []

            # DEBUG: Log what we received
            logger.info("stream_request_received",
                       message=message[:50],
                       active_document_ids_raw=active_document_ids,
                       parsed_doc_ids=parsed_doc_ids,
                       has_doc_ids=len(parsed_doc_ids) > 0,
                       selected_sources=parsed_selected_sources)

            # Initialize thought stream
            thought_stream = get_thought_stream(session_id)

            # Start streaming thoughts in background
            async def process_and_stream():
                try:
                    # Initialize orchestrator and state manager
                    orchestrator = OrchestratorAgent()
                    state_manager = get_state_manager(session_id)
                    current_state = state_manager.get_state()

                    # Extract context from history AND state
                    context = None
                    if parsed_history:
                        # Look for last message with useful context data
                        for msg in reversed(parsed_history):
                            if msg.get("role") == "assistant" and msg.get("data"):
                                msg_data = msg.get("data", {})

                                # Check for email draft awaiting confirmation
                                if "email_draft" in msg_data and msg_data.get("awaiting_confirmation"):
                                    context = {"email_draft": msg_data["email_draft"]}
                                    logger.info("context_extracted_from_history", has_draft=True)
                                    break

                                # Check for emails from SQL query
                                if "emails_available" in msg_data:
                                    context = context or {}
                                    context["emails_available"] = msg_data["emails_available"]
                                    logger.info("context_extracted_from_history", has_emails=True, count=len(msg_data["emails_available"]))
                                    # Don't break - continue looking for email_draft which has priority

                    # Enrich context with state information
                    if not context:
                        context = {}

                    # Add active document IDs for RAG filtering
                    if parsed_doc_ids:
                        context["active_document_ids"] = parsed_doc_ids
                        logger.info("context_enriched_with_document_ids", count=len(parsed_doc_ids))

                    # Add recipients from state if available
                    if current_state.recipients_identified and not context.get("emails_available"):
                        context["emails_available"] = current_state.recipients_identified
                        logger.info("context_enriched_from_state", emails_count=len(current_state.recipients_identified))

                    # Add business context from state
                    if current_state.business_context:
                        context["business_context"] = current_state.business_context
                        logger.info("context_enriched_with_business", keys=list(current_state.business_context.keys()))

                    # Add topic from state for email modification preservation
                    if current_state.topic:
                        context["topic"] = current_state.topic
                        logger.info("context_enriched_with_topic", topic=current_state.topic)

                    # Process request (this will emit thoughts)
                    result = await orchestrator.process(
                        user_input=message,
                        db=db,
                        context=context,
                        conversation_history=parsed_history,
                        thought_stream=thought_stream,
                        state_manager=state_manager,  # Pass state manager to orchestrator
                        selected_sources=parsed_selected_sources if parsed_selected_sources else None  # User-controlled routing
                    )

                    # Update state from message and response
                    state_manager.extract_and_update_from_message(message, result.data)

                    # Add completion thought
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Terminé",
                        content="J'ai terminé de traiter votre demande.",
                        agent="orchestrator",
                        progress=1.0
                    )

                    # Send final response as separate event
                    import json

                    # Extract sources from data if available
                    sources = []
                    if result.data and isinstance(result.data, dict):
                        sources = result.data.get("sources", [])

                    response_data = {
                        "success": result.success,
                        "message": result.message,
                        "data": result.data,
                        "agents_used": result.agents_used,
                        "suggestions": result.suggestions if result.suggestions else [],
                        "sources": sources  # Extract sources to top level
                    }
                    final_event = f"event: response\ndata: {json.dumps(response_data, default=str)}\n\n"
                    await thought_stream._broadcast(final_event)

                except Exception as e:
                    logger.error("streaming_process_failed", error=str(e), exc_info=True)
                    await thought_stream.add_thought(
                        ThoughtType.ERROR,
                        title="Erreur",
                        content=f"Une erreur s'est produite : {str(e)}",
                        agent="orchestrator"
                    )

            # IMPORTANT: Subscribe FIRST before starting background task
            # This ensures we don't miss any early thoughts
            queue = thought_stream.subscribe()

            # Start processing in background
            task = asyncio.create_task(process_and_stream())

            # Stream thoughts as they come
            try:
                # Send existing thoughts first
                for thought in thought_stream.thoughts:
                    yield thought_stream._format_sse(thought)
                    await asyncio.sleep(0.05)

                # Stream new thoughts as they come
                should_continue = True
                while should_continue:
                    try:
                        # Wait for new thought with timeout
                        event = await asyncio.wait_for(queue.get(), timeout=60.0)

                        # Handle both ThoughtEvent objects and raw SSE strings
                        if isinstance(event, str):
                            # Raw SSE string (e.g., final response event)
                            yield event
                            # If it's a response event, we can stop after sending it
                            if "event: response" in event:
                                should_continue = False
                        else:
                            # Standard thought event
                            yield thought_stream._format_sse(event)

                    except asyncio.TimeoutError:
                        # Send keep-alive ping
                        yield f": keep-alive\n\n"

            finally:
                thought_stream.unsubscribe(queue)

            # Wait for processing to complete
            await task

        except Exception as e:
            logger.error("event_generation_failed", error=str(e), exc_info=True)
            yield f"event: error\ndata: {{'error': '{str(e)}'}}\n\n"

        finally:
            # Cleanup
            cleanup_stream(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/chat/stream/test")
async def test_stream():
    """
    Test endpoint for streaming

    Returns a simple SSE stream to verify streaming works
    """
    async def test_generator():
        import json
        import asyncio

        for i in range(5):
            event_data = {
                "step": i + 1,
                "message": f"Test event {i + 1}",
                "timestamp": str(asyncio.get_event_loop().time())
            }
            yield f"event: test\ndata: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(1)

        yield f"event: done\ndata: {json.dumps({'message': 'Stream completed'})}\n\n"

    return StreamingResponse(
        test_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
