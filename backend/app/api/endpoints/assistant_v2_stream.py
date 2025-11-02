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
    session_id = str(uuid.uuid4())

    async def event_generator():
        """Generate Server-Sent Events"""
        try:
            # Parse conversation history from JSON string
            import json
            try:
                parsed_history = json.loads(conversation_history)
            except json.JSONDecodeError:
                parsed_history = []

            # Initialize thought stream
            thought_stream = get_thought_stream(session_id)

            # Start streaming thoughts in background
            async def process_and_stream():
                try:
                    # Initialize orchestrator
                    orchestrator = OrchestratorAgent()

                    # Process request (this will emit thoughts)
                    result = await orchestrator.process(
                        user_input=message,
                        db=db,
                        context=None,
                        conversation_history=parsed_history,
                        thought_stream=thought_stream
                    )

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
                    response_data = {
                        "success": result.success,
                        "message": result.message,
                        "data": result.data,
                        "agents_used": result.agents_used,
                        "suggestions": result.suggestions
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

            # Start processing in background
            task = asyncio.create_task(process_and_stream())

            # Stream thoughts as they come
            async for sse_event in thought_stream.stream_events():
                yield sse_event

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
