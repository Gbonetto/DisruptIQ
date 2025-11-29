"""
Thought Stream - Chain of Thoughts tracking for transparent AI reasoning
Inspired by DeepSeek's reasoning display
"""

import structlog
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
import asyncio
import json

logger = structlog.get_logger()


class ThoughtType(str, Enum):
    """Types of thoughts in the reasoning chain"""
    # === Phases générales ===
    ANALYZING = "analyzing"  # Analyse de la requête
    CLASSIFYING = "classifying"  # Classification de l'intention
    PLANNING = "planning"  # Planification des agents à appeler
    EXECUTING = "executing"  # Exécution d'une action (générique)
    WAITING = "waiting"  # En attente de réponse
    PROCESSING = "processing"  # Traitement des résultats
    SYNTHESIZING = "synthesizing"  # Synthèse de la réponse finale
    COMPLETED = "completed"  # Terminé
    ERROR = "error"  # Erreur
    WARNING = "warning"  # Avertissement

    # === Actions spécifiques par agent ===
    # SQL Agent
    SQL_GENERATING = "sql_generating"  # Génération de la requête SQL
    SQL_EXECUTING = "sql_executing"  # Exécution de la requête SQL
    SQL_RESULTS = "sql_results"  # Résultats SQL reçus

    # RAG Agent (Documents)
    RAG_SEARCHING = "rag_searching"  # Recherche dans les documents
    RAG_RETRIEVING = "rag_retrieving"  # Récupération des passages
    RAG_RERANKING = "rag_reranking"  # Reclassement des résultats
    RAG_RESULTS = "rag_results"  # Documents trouvés

    # Web Agent
    WEB_SEARCHING = "web_searching"  # Recherche sur le web
    WEB_FETCHING = "web_fetching"  # Consultation d'un site
    WEB_RESULTS = "web_results"  # Résultats web reçus

    # Legal Agent
    LEGAL_SEARCHING = "legal_searching"  # Recherche juridique
    LEGAL_ANALYZING = "legal_analyzing"  # Analyse juridique

    # Email Agent
    EMAIL_DRAFTING = "email_drafting"  # Rédaction d'email
    EMAIL_SENDING = "email_sending"  # Envoi d'email
    EMAIL_SENT = "email_sent"  # Email envoyé avec succès

    # Workflow Agent (N8N)
    WORKFLOW_TRIGGERING = "workflow_triggering"  # Déclenchement du workflow
    WORKFLOW_SENDING = "workflow_sending"  # Envoi vers N8N
    WORKFLOW_SUCCESS = "workflow_success"  # Workflow exécuté avec succès
    WORKFLOW_ERROR = "workflow_error"  # Erreur workflow

    # Digest Agent
    DIGEST_FETCHING = "digest_fetching"  # Récupération des emails
    DIGEST_CLASSIFYING = "digest_classifying"  # Classification par urgence
    DIGEST_GENERATING = "digest_generating"  # Génération du résumé

    # Table Generation Agent
    TABLE_GENERATING = "table_generating"  # Génération du tableau
    TABLE_EXPORTING = "table_exporting"  # Export du tableau

    # Legal Agent (compléments)
    LEGAL_RESULTS = "legal_results"  # Résultats juridiques trouvés

    # OCR Agent
    OCR_PROCESSING = "ocr_processing"  # Traitement OCR en cours
    OCR_EXTRACTING = "ocr_extracting"  # Extraction du texte

    # Intent Classification
    INTENT_DETECTED = "intent_detected"  # Intention détectée

    # Fusion multi-sources
    FUSION_COMBINING = "fusion_combining"  # Combinaison des sources

    # === World-Class RAG Pipeline ===
    # Query Planning
    QUERY_PLANNING = "query_planning"  # Planification de requête complexe
    QUERY_DECOMPOSING = "query_decomposing"  # Décomposition en sous-requêtes
    SUBQUERY_EXECUTING = "subquery_executing"  # Exécution d'une sous-requête

    # Verification Agent
    VERIFICATION_CHECKING = "verification_checking"  # Vérification de pertinence
    VERIFICATION_REFINING = "verification_refining"  # Raffinement de la recherche
    VERIFICATION_COMPLETE = "verification_complete"  # Vérification terminée

    # Reflection Agent
    REFLECTION_DIAGNOSING = "reflection_diagnosing"  # Diagnostic du problème
    REFLECTION_IMPROVING = "reflection_improving"  # Amélioration des résultats
    REFLECTION_COMPLETE = "reflection_complete"  # Réflexion terminée

    # Synthesis Agent
    SYNTHESIS_STARTING = "synthesis_starting"  # Début de synthèse
    SYNTHESIS_CITING = "synthesis_citing"  # Citation des sources
    SYNTHESIS_COMPLETE = "synthesis_complete"  # Synthèse terminée

    # LLM Internal (for debugging)
    LLM_CALLING = "llm_calling"  # Appel au modèle LLM
    LLM_REASONING = "llm_reasoning"  # Raisonnement en cours
    LLM_RESPONSE = "llm_response"  # Réponse LLM reçue

    # Alias legacy
    SEARCHING = "searching"  # Déprécié: utiliser les types spécifiques

    # === PROGRESS STAGES (Option C - Streaming Optimization) ===
    # Pre-defined progress messages (NO LLM call to generate these)
    PROGRESS_ROUTING = "progress_routing"          # Analyse et sélection des sources
    PROGRESS_RETRIEVAL_SQL = "progress_retrieval_sql"    # Récupération SQL
    PROGRESS_RETRIEVAL_RAG = "progress_retrieval_rag"    # Récupération RAG
    PROGRESS_RETRIEVAL_LEGAL = "progress_retrieval_legal"  # Récupération Legal
    PROGRESS_RETRIEVAL_WEB = "progress_retrieval_web"    # Récupération Web
    PROGRESS_RERANKING = "progress_reranking"        # Reranking des résultats
    PROGRESS_SYNTHESIS = "progress_synthesis"        # Synthèse finale


# === Labels français pour l'affichage frontend ===
THOUGHT_LABELS_FR = {
    # Phases générales
    ThoughtType.ANALYZING: "Analyse de la requête",
    ThoughtType.CLASSIFYING: "Classification de l'intention",
    ThoughtType.PLANNING: "Planification",
    ThoughtType.EXECUTING: "Exécution",
    ThoughtType.WAITING: "En attente",
    ThoughtType.PROCESSING: "Traitement",
    ThoughtType.SYNTHESIZING: "Synthèse",
    ThoughtType.COMPLETED: "Terminé",
    ThoughtType.ERROR: "Erreur",
    ThoughtType.WARNING: "Avertissement",

    # SQL
    ThoughtType.SQL_GENERATING: "Génération de la requête SQL",
    ThoughtType.SQL_EXECUTING: "Exécution de la requête SQL",
    ThoughtType.SQL_RESULTS: "Résultats de la base de données",

    # RAG
    ThoughtType.RAG_SEARCHING: "Recherche dans les documents",
    ThoughtType.RAG_RETRIEVING: "Récupération des passages",
    ThoughtType.RAG_RERANKING: "Reclassement par pertinence",
    ThoughtType.RAG_RESULTS: "Documents consultés",

    # Web
    ThoughtType.WEB_SEARCHING: "Recherche sur internet",
    ThoughtType.WEB_FETCHING: "Consultation du site",
    ThoughtType.WEB_RESULTS: "Résultats web",

    # Legal
    ThoughtType.LEGAL_SEARCHING: "Recherche juridique",
    ThoughtType.LEGAL_ANALYZING: "Analyse juridique",

    # Email
    ThoughtType.EMAIL_DRAFTING: "Rédaction de l'email",
    ThoughtType.EMAIL_SENDING: "Envoi de l'email",
    ThoughtType.EMAIL_SENT: "Email envoyé",

    # Workflow (N8N)
    ThoughtType.WORKFLOW_TRIGGERING: "Déclenchement du workflow",
    ThoughtType.WORKFLOW_SENDING: "Envoi vers N8N",
    ThoughtType.WORKFLOW_SUCCESS: "Workflow exécuté avec succès",
    ThoughtType.WORKFLOW_ERROR: "Erreur workflow",

    # Digest
    ThoughtType.DIGEST_FETCHING: "Récupération des emails",
    ThoughtType.DIGEST_CLASSIFYING: "Classification par urgence",
    ThoughtType.DIGEST_GENERATING: "Génération du résumé",

    # Table Generation
    ThoughtType.TABLE_GENERATING: "Génération du tableau",
    ThoughtType.TABLE_EXPORTING: "Export du tableau",

    # Legal (compléments)
    ThoughtType.LEGAL_RESULTS: "Résultats juridiques",

    # OCR
    ThoughtType.OCR_PROCESSING: "Traitement OCR",
    ThoughtType.OCR_EXTRACTING: "Extraction du texte",

    # Intent
    ThoughtType.INTENT_DETECTED: "Intention détectée",

    # Fusion
    ThoughtType.FUSION_COMBINING: "Combinaison des sources",

    # Legacy
    ThoughtType.SEARCHING: "Recherche",

    # === World-Class RAG Pipeline ===
    # Query Planning
    ThoughtType.QUERY_PLANNING: "🧩 Planification de requête",
    ThoughtType.QUERY_DECOMPOSING: "🔀 Décomposition en sous-requêtes",
    ThoughtType.SUBQUERY_EXECUTING: "🔍 Exécution sous-requête",

    # Verification
    ThoughtType.VERIFICATION_CHECKING: "🔍 Vérification de pertinence",
    ThoughtType.VERIFICATION_REFINING: "🔄 Raffinement de la recherche",
    ThoughtType.VERIFICATION_COMPLETE: "✅ Vérification terminée",

    # Reflection
    ThoughtType.REFLECTION_DIAGNOSING: "🤔 Diagnostic du problème",
    ThoughtType.REFLECTION_IMPROVING: "🔄 Amélioration des résultats",
    ThoughtType.REFLECTION_COMPLETE: "✅ Réflexion terminée",

    # Synthesis
    ThoughtType.SYNTHESIS_STARTING: "📝 Début de synthèse",
    ThoughtType.SYNTHESIS_CITING: "📚 Citation des sources",
    ThoughtType.SYNTHESIS_COMPLETE: "✅ Synthèse terminée",

    # LLM Internal
    ThoughtType.LLM_CALLING: "🤖 Appel au modèle LLM",
    ThoughtType.LLM_REASONING: "💭 Raisonnement en cours",
    ThoughtType.LLM_RESPONSE: "💬 Réponse LLM reçue",

    # === PROGRESS STAGES (Option C - Streaming) ===
    ThoughtType.PROGRESS_ROUTING: "🔀 Analyse de la requête",
    ThoughtType.PROGRESS_RETRIEVAL_SQL: "🗄️ Récupération des données",
    ThoughtType.PROGRESS_RETRIEVAL_RAG: "📚 Recherche dans les documents",
    ThoughtType.PROGRESS_RETRIEVAL_LEGAL: "⚖️ Consultation juridique",
    ThoughtType.PROGRESS_RETRIEVAL_WEB: "🌐 Recherche sur internet",
    ThoughtType.PROGRESS_RERANKING: "📊 Classement des résultats",
    ThoughtType.PROGRESS_SYNTHESIS: "✍️ Rédaction de la réponse",
}


# ========================================================================
# PROGRESS MESSAGES - Pre-defined messages (NO LLM call)
# ========================================================================
# These messages are used by WorldClassRouter to emit progress without LLM
# IMPORTANT: NEVER call an LLM to generate these messages

PROGRESS_MESSAGES = {
    "routing": {
        "type": ThoughtType.PROGRESS_ROUTING,
        "title": "Analyse de la requête",
        "content": "Analyse de la requête et sélection des meilleures sources de données…",
        "progress": 0.1,
    },
    "retrieval_sql": {
        "type": ThoughtType.PROGRESS_RETRIEVAL_SQL,
        "title": "Récupération SQL",
        "content": "Récupération des données structurées (copropriétaires, lots, charges)…",
        "progress": 0.3,
    },
    "retrieval_rag": {
        "type": ThoughtType.PROGRESS_RETRIEVAL_RAG,
        "title": "Recherche documentaire",
        "content": "Recherche dans vos documents (règlement, PV, contrats)…",
        "progress": 0.3,
    },
    "retrieval_legal": {
        "type": ThoughtType.PROGRESS_RETRIEVAL_LEGAL,
        "title": "Consultation juridique",
        "content": "Consultation des textes de loi et jurisprudences (Légifrance)…",
        "progress": 0.3,
    },
    "retrieval_web": {
        "type": ThoughtType.PROGRESS_RETRIEVAL_WEB,
        "title": "Recherche web",
        "content": "Recherche d'informations actualisées sur internet…",
        "progress": 0.3,
    },
    "reranking": {
        "type": ThoughtType.PROGRESS_RERANKING,
        "title": "Classement des résultats",
        "content": "Analyse et classement des résultats par pertinence…",
        "progress": 0.6,
    },
    "synthesis": {
        "type": ThoughtType.PROGRESS_SYNTHESIS,
        "title": "Synthèse",
        "content": "Rédaction de la réponse en cours…",
        "progress": 0.8,
    },
}


class ThoughtEvent(BaseModel):
    """Single thought event in the reasoning chain"""
    id: str
    type: ThoughtType
    timestamp: datetime
    agent: Optional[str] = None  # Which agent is thinking
    title: str  # Short title (e.g., "Analyzing request")
    content: str  # Detailed thought content
    data: Optional[Dict[str, Any]] = None  # Additional structured data
    progress: Optional[float] = None  # Progress 0-1 for this step

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ThoughtStream:
    """
    Manages the chain of thoughts for an assistant session

    This class tracks all reasoning steps and broadcasts them
    in real-time via Server-Sent Events (SSE)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.thoughts: List[ThoughtEvent] = []
        self.subscribers: List[asyncio.Queue] = []
        self._event_counter = 0
        logger.info("thought_stream_initialized", session_id=session_id)

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to thought stream events"""
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        logger.info("subscriber_added", session_id=self.session_id, total=len(self.subscribers))
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from thought stream"""
        if queue in self.subscribers:
            self.subscribers.remove(queue)
            logger.info("subscriber_removed", session_id=self.session_id, total=len(self.subscribers))

    async def add_thought(
        self,
        thought_type: ThoughtType,
        title: str,
        content: str,
        agent: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None
    ) -> ThoughtEvent:
        """
        Add a new thought to the stream and broadcast it

        Args:
            thought_type: Type of thought
            title: Short title
            content: Detailed content
            agent: Agent name (if applicable)
            data: Additional structured data
            progress: Progress indicator (0-1)

        Returns:
            Created ThoughtEvent
        """
        self._event_counter += 1

        event = ThoughtEvent(
            id=f"{self.session_id}-{self._event_counter}",
            type=thought_type,
            timestamp=datetime.now(),
            agent=agent,
            title=title,
            content=content,
            data=data,
            progress=progress
        )

        self.thoughts.append(event)

        # Broadcast to all subscribers
        await self._broadcast(event)

        logger.info(
            "thought_added",
            session_id=self.session_id,
            type=thought_type.value,
            agent=agent,
            title=title,
            subscribers_count=len(self.subscribers)
        )

        return event

    async def _broadcast(self, event):
        """
        Broadcast event to all subscribers

        Args:
            event: ThoughtEvent or raw string (for custom SSE events)
        """
        for queue in self.subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error("broadcast_failed", error=str(e), session_id=self.session_id)

    async def stream_events(self) -> AsyncGenerator[str, None]:
        """
        Stream events as Server-Sent Events (SSE) format

        Yields:
            SSE formatted strings
        """
        queue = self.subscribe()

        try:
            # Send existing thoughts first
            for thought in self.thoughts:
                yield self._format_sse(thought)
                await asyncio.sleep(0.05)  # Small delay for readability

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
                    elif isinstance(event, ThoughtEvent):
                        # Standard thought event
                        yield self._format_sse(event)

                        # If completed or error, continue streaming to get final response
                        if event.type in [ThoughtType.COMPLETED, ThoughtType.ERROR]:
                            # Don't stop yet - wait for the final response event
                            pass

                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield f": keep-alive\n\n"

        except asyncio.CancelledError:
            logger.info("stream_cancelled", session_id=self.session_id)
        finally:
            self.unsubscribe(queue)

    def _format_sse(self, event: ThoughtEvent) -> str:
        """
        Format thought event as Server-Sent Event

        Format:
        event: thought
        data: {"id": "...", "type": "...", ...}

        """
        event_data = event.model_dump()
        sse_str = f"event: thought\ndata: {json.dumps(event_data, default=str)}\n\n"
        logger.debug("sse_event_formatted", event_id=event.id, type=event.type.value, sse_preview=sse_str[:100])
        return sse_str

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all thoughts"""
        return {
            "session_id": self.session_id,
            "total_thoughts": len(self.thoughts),
            "agents_used": list(set(t.agent for t in self.thoughts if t.agent)),
            "duration_seconds": (
                (self.thoughts[-1].timestamp - self.thoughts[0].timestamp).total_seconds()
                if len(self.thoughts) > 1 else 0
            ),
            "thoughts": [t.model_dump() for t in self.thoughts]
        }


# Global registry of active thought streams
_active_streams: Dict[str, ThoughtStream] = {}


def get_thought_stream(session_id: str) -> ThoughtStream:
    """Get or create thought stream for session"""
    if session_id not in _active_streams:
        _active_streams[session_id] = ThoughtStream(session_id)
    return _active_streams[session_id]


def cleanup_stream(session_id: str):
    """Cleanup thought stream after session ends"""
    if session_id in _active_streams:
        del _active_streams[session_id]
        logger.info("thought_stream_cleaned", session_id=session_id)
