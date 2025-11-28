"""
Unified Context Manager - Single Source of Truth for Multi-Agent System
Phase 3 - World-Class SMA Architecture

This module consolidates all context sources into a single, coherent model:
- StateManager (conversation state)
- ContextStore (agent-to-agent context)
- EntityGraph (entity resolution)
- ConversationHistory (from frontend)

Key Principles:
1. Single Source of Truth (SSOT) - One place for all context
2. Conflict Resolution - Newer data wins, with explicit priority rules
3. TTL Management - Automatic cleanup of stale data
4. Persistence Ready - Interface for Redis backend

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from enum import Enum

logger = structlog.get_logger()


class ContextPriority(str, Enum):
    """Priority levels for context conflict resolution"""
    REALTIME = "realtime"      # Current request data (highest)
    SESSION = "session"        # Session state (medium)
    HISTORICAL = "historical"  # Past data (lowest)


class UnifiedContext(BaseModel):
    """
    Single Source of Truth for all conversation context

    Consolidates:
    - Topic/subtopic tracking
    - Recipients (identified emails)
    - Pending actions (email drafts, etc.)
    - Entity graph data
    - Recent facts (budgets, dates, etc.)
    - Conversation summary
    """

    # Session identification
    session_id: str
    last_updated: datetime = Field(default_factory=datetime.now)

    # Topic tracking
    topic: Optional[str] = None
    sub_topic: Optional[str] = None

    # Recipients tracking
    recipients_identified: List[str] = Field(default_factory=list)
    recipients_context: Optional[str] = None

    # Pending actions
    pending_action: Optional[str] = None  # "awaiting_email_confirmation", etc.
    pending_data: Dict[str, Any] = Field(default_factory=dict)
    email_draft: Optional[Dict[str, Any]] = None

    # Entity resolution
    resolved_entities: Dict[str, Any] = Field(default_factory=dict)
    # Format: {"copropriete": {"id": 5, "nom": "Les Jardins", "resolved_from": "jardins"}}

    # Business context (incident type, property info)
    business_context: Dict[str, Any] = Field(default_factory=dict)

    # Recent facts (structured data extracted from conversation)
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    # Format: [{"type": "budget", "data": {"amount": 50000}, "timestamp": ...}]

    # Recent SQL results (for reference)
    last_sql_results: Optional[Dict[str, Any]] = None
    last_query_entities: List[Dict[str, Any]] = Field(default_factory=list)

    # Documents
    last_uploaded_documents: List[Dict[str, Any]] = Field(default_factory=list)
    active_document_ids: Optional[List[int]] = None

    # Conversation summary (for LLM context)
    conversation_summary: Optional[str] = None
    message_count: int = 0


class UnifiedContextManager:
    """
    Unified Context Manager - Consolidates all context sources

    Usage:
        ctx_manager = UnifiedContextManager(session_id)

        # Get unified context
        context = ctx_manager.get_context()

        # Update from various sources
        ctx_manager.update_from_state_manager(state_manager)
        ctx_manager.update_from_context_store(context_store, session_id)
        ctx_manager.update_topic("odeurs de gaz", "alerte sécurité")

        # Resolve conflicts
        ctx_manager.merge_with_priority(new_data, priority=ContextPriority.REALTIME)
    """

    def __init__(self, session_id: str, ttl_minutes: int = 60):
        self.session_id = session_id
        self.ttl_minutes = ttl_minutes
        self._context = UnifiedContext(session_id=session_id)
        self._timestamps: Dict[str, datetime] = {}

        logger.info("unified_context_manager_initialized",
                   session_id=session_id,
                   ttl_minutes=ttl_minutes)

    def get_context(self) -> UnifiedContext:
        """Get the current unified context"""
        return self._context

    def update_topic(self, topic: str, sub_topic: Optional[str] = None):
        """Update conversation topic with timestamp tracking"""
        self._context.topic = topic
        if sub_topic:
            self._context.sub_topic = sub_topic

        self._timestamps["topic"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_topic_updated",
                   session_id=self.session_id,
                   topic=topic,
                   sub_topic=sub_topic)

    def add_recipients(self, emails: List[str], context: Optional[str] = None):
        """Add recipients with deduplication"""
        new_emails = [e for e in emails if e not in self._context.recipients_identified]
        self._context.recipients_identified.extend(new_emails)

        if context:
            self._context.recipients_context = context

        self._timestamps["recipients"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_recipients_added",
                   session_id=self.session_id,
                   new_count=len(new_emails),
                   total=len(self._context.recipients_identified))

    def set_pending_action(self, action: str, data: Dict[str, Any] = None):
        """Set pending action (email confirmation, etc.)"""
        self._context.pending_action = action
        self._context.pending_data = data or {}

        self._timestamps["pending_action"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_pending_action_set",
                   session_id=self.session_id,
                   action=action)

    def clear_pending_action(self):
        """Clear pending action"""
        self._context.pending_action = None
        self._context.pending_data = {}
        self._context.email_draft = None

        self._timestamps["pending_action"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_pending_action_cleared",
                   session_id=self.session_id)

    def set_email_draft(self, draft: Dict[str, Any]):
        """Store email draft"""
        self._context.email_draft = draft
        self._context.pending_action = "awaiting_email_confirmation"
        self._context.pending_data = {"draft": draft}

        self._timestamps["email_draft"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_email_draft_set",
                   session_id=self.session_id,
                   has_recipients=bool(draft.get("recipients")))

    def resolve_entity(self, entity_type: str, resolved_id: int,
                       resolved_name: str, original_query: str):
        """Store entity resolution result"""
        self._context.resolved_entities[entity_type] = {
            "id": resolved_id,
            "nom": resolved_name,
            "resolved_from": original_query,
            "timestamp": datetime.now().isoformat()
        }

        self._timestamps["entities"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_entity_resolved",
                   session_id=self.session_id,
                   entity_type=entity_type,
                   resolved_name=resolved_name)

    def add_fact(self, fact_type: str, fact_data: Dict[str, Any]):
        """Add a structured fact (budget, date, contact, etc.)"""
        fact_entry = {
            "type": fact_type,
            "data": fact_data,
            "timestamp": datetime.now().isoformat()
        }
        self._context.facts.append(fact_entry)

        # Keep only last 20 facts to prevent bloat
        if len(self._context.facts) > 20:
            self._context.facts = self._context.facts[-20:]

        self._timestamps["facts"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_fact_added",
                   session_id=self.session_id,
                   fact_type=fact_type,
                   total_facts=len(self._context.facts))

    def query_facts(self, fact_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query facts by type"""
        if fact_type:
            return [f for f in self._context.facts if f["type"] == fact_type]
        return self._context.facts

    def update_business_context(self, context: Dict[str, Any]):
        """Update business context (incident type, property info, etc.)"""
        self._context.business_context.update(context)

        self._timestamps["business_context"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_business_updated",
                   session_id=self.session_id,
                   keys=list(context.keys()))

    def set_sql_results(self, results: Dict[str, Any],
                        entities: Optional[List[Dict[str, Any]]] = None):
        """Store SQL query results"""
        self._context.last_sql_results = results
        if entities:
            self._context.last_query_entities = entities

        self._timestamps["sql_results"] = datetime.now()
        self._context.last_updated = datetime.now()

    def add_uploaded_document(self, filename: str, document_id: int, mime_type: str):
        """Track uploaded document"""
        doc_info = {
            "filename": filename,
            "document_id": document_id,
            "mime_type": mime_type,
            "timestamp": datetime.now().isoformat()
        }

        # Add to beginning (most recent first)
        self._context.last_uploaded_documents.insert(0, doc_info)

        # Keep only last 10 documents
        if len(self._context.last_uploaded_documents) > 10:
            self._context.last_uploaded_documents = self._context.last_uploaded_documents[:10]

        self._timestamps["documents"] = datetime.now()
        self._context.last_updated = datetime.now()

        logger.info("unified_context_document_added",
                   session_id=self.session_id,
                   filename=filename,
                   total_docs=len(self._context.last_uploaded_documents))

    def set_active_document_ids(self, document_ids: List[int]):
        """Set active document IDs for RAG filtering"""
        self._context.active_document_ids = document_ids

        self._timestamps["active_docs"] = datetime.now()
        self._context.last_updated = datetime.now()

    def update_conversation_summary(self, summary: str, message_count: int):
        """Update conversation summary for LLM context"""
        self._context.conversation_summary = summary
        self._context.message_count = message_count

        self._timestamps["summary"] = datetime.now()
        self._context.last_updated = datetime.now()

    # ================================================================
    # SYNCHRONIZATION METHODS
    # ================================================================

    def sync_from_state_manager(self, state_manager) -> None:
        """
        Sync context from StateManager (conversation_state.py)

        Priority: StateManager data is SESSION priority (medium)
        """
        state = state_manager.state

        # Sync topic
        if state.topic:
            self._merge_field("topic", state.topic, ContextPriority.SESSION)
        if state.sub_topic:
            self._merge_field("sub_topic", state.sub_topic, ContextPriority.SESSION)

        # Sync recipients
        if state.recipients_identified:
            for email in state.recipients_identified:
                if email not in self._context.recipients_identified:
                    self._context.recipients_identified.append(email)

        if state.recipients_context:
            self._merge_field("recipients_context", state.recipients_context, ContextPriority.SESSION)

        # Sync pending action
        if state.pending_action and state.pending_action.value != "none":
            self._merge_field("pending_action", state.pending_action.value, ContextPriority.SESSION)
            self._context.pending_data = state.pending_data

        # Sync email draft
        if state.email_draft:
            self._merge_field("email_draft", state.email_draft, ContextPriority.SESSION)

        # Sync business context
        if state.business_context:
            self._context.business_context.update(state.business_context)

        # Sync SQL results
        if state.last_sql_results:
            self._context.last_sql_results = state.last_sql_results

        if state.last_query_entities:
            self._context.last_query_entities = state.last_query_entities

        # Sync documents
        if state.last_uploaded_documents:
            self._context.last_uploaded_documents = state.last_uploaded_documents

        if state.active_document_ids is not None:
            self._context.active_document_ids = state.active_document_ids

        self._context.last_updated = datetime.now()

        logger.info("unified_context_synced_from_state_manager",
                   session_id=self.session_id)

    def sync_from_context_store(self, context_store, conversation_id: str) -> None:
        """
        Sync context from SimpleContextStore (context_store.py)

        Priority: ContextStore data is HISTORICAL priority (low)
        """
        # Get all context
        stored = context_store.get_all(conversation_id)

        if not stored:
            return

        # Sync workflow data
        if "last_workflow" in stored:
            self._context.business_context["last_workflow"] = stored["last_workflow"]

        # Sync SQL results (if not already set)
        if "last_sql_results" in stored and not self._context.last_sql_results:
            self._context.last_sql_results = stored["last_sql_results"]

        # Sync recipients
        if "last_recipients" in stored:
            for email in stored["last_recipients"]:
                if email not in self._context.recipients_identified:
                    self._context.recipients_identified.append(email)

        # Sync facts
        if "facts" in stored:
            for fact in stored["facts"]:
                # Only add if not already present (by type + data hash)
                fact_key = f"{fact['type']}:{hash(str(fact['data']))}"
                existing_keys = [f"{f['type']}:{hash(str(f['data']))}" for f in self._context.facts]
                if fact_key not in existing_keys:
                    self._context.facts.append(fact)

        self._context.last_updated = datetime.now()

        logger.info("unified_context_synced_from_context_store",
                   session_id=self.session_id,
                   conversation_id=conversation_id)

    def sync_from_entity_graph(self, entity_graph) -> None:
        """
        Sync resolved entities from EntityGraph

        Priority: EntityGraph data is SESSION priority (medium)
        """
        # Get recently resolved entities
        for entity in entity_graph.entities:
            if hasattr(entity, 'entity_type') and hasattr(entity, 'entity_id'):
                self._context.resolved_entities[entity.entity_type] = {
                    "id": entity.entity_id,
                    "nom": getattr(entity, 'name', str(entity.entity_id)),
                    "timestamp": datetime.now().isoformat()
                }

        self._context.last_updated = datetime.now()

        logger.info("unified_context_synced_from_entity_graph",
                   session_id=self.session_id,
                   entities_count=len(self._context.resolved_entities))

    def _merge_field(self, field: str, value: Any, priority: ContextPriority):
        """
        Merge a field value with conflict resolution

        Rules:
        - REALTIME always wins
        - SESSION wins over HISTORICAL
        - If same priority, newer timestamp wins
        """
        current_value = getattr(self._context, field, None)
        field_timestamp = self._timestamps.get(field)

        # If no current value, just set it
        if current_value is None:
            setattr(self._context, field, value)
            self._timestamps[field] = datetime.now()
            return

        # REALTIME always wins
        if priority == ContextPriority.REALTIME:
            setattr(self._context, field, value)
            self._timestamps[field] = datetime.now()
            return

        # For SESSION and HISTORICAL, check if current is older
        if field_timestamp:
            time_diff = datetime.now() - field_timestamp
            # If current data is older than 5 minutes, replace it
            if time_diff > timedelta(minutes=5):
                setattr(self._context, field, value)
                self._timestamps[field] = datetime.now()

    # ================================================================
    # EXPORT METHODS
    # ================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Export context as dictionary (for API responses)"""
        return self._context.model_dump()

    def get_llm_context_string(self) -> str:
        """
        Generate a context string for LLM prompts

        This provides a concise summary of current context for
        better LLM decision-making.
        """
        parts = []

        if self._context.topic:
            parts.append(f"Sujet actuel: {self._context.topic}")
            if self._context.sub_topic:
                parts.append(f"Sous-sujet: {self._context.sub_topic}")

        if self._context.recipients_context:
            parts.append(f"Destinataires ciblés: {self._context.recipients_context}")
            if self._context.recipients_identified:
                parts.append(f"Emails trouvés: {len(self._context.recipients_identified)}")

        if self._context.pending_action:
            parts.append(f"Action en attente: {self._context.pending_action}")

        if self._context.resolved_entities:
            entities = [f"{k}: {v['nom']}" for k, v in self._context.resolved_entities.items()]
            parts.append(f"Entités résolues: {', '.join(entities)}")

        if self._context.business_context:
            biz = self._context.business_context
            if "incident_type" in biz:
                parts.append(f"Type d'incident: {biz['incident_type']}")

        if self._context.facts:
            recent_facts = self._context.facts[-3:]
            for fact in recent_facts:
                parts.append(f"Fait ({fact['type']}): {fact['data']}")

        if self._context.message_count > 0:
            parts.append(f"Messages dans la conversation: {self._context.message_count}")

        return " | ".join(parts) if parts else "Aucun contexte"

    def is_stale(self) -> bool:
        """Check if context has expired"""
        if not self._context.last_updated:
            return True

        age = datetime.now() - self._context.last_updated
        return age > timedelta(minutes=self.ttl_minutes)

    def reset(self):
        """Reset context to initial state"""
        self._context = UnifiedContext(session_id=self.session_id)
        self._timestamps = {}

        logger.info("unified_context_reset", session_id=self.session_id)


# ================================================================
# REDIS PERSISTENCE LAYER
# ================================================================

class RedisContextStore:
    """
    Redis-backed persistence for UnifiedContext

    Provides:
    - Persistent context across app restarts
    - Shared context across multiple instances
    - Automatic TTL management
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._redis = None
        self._initialized = False

    async def _get_redis(self):
        """Lazy-load Redis client"""
        if not self._initialized:
            try:
                from app.core.redis_client import get_redis_client
                self._redis = get_redis_client()
                self._initialized = True
            except Exception as e:
                logger.warning("redis_context_store_init_failed", error=str(e))
                self._redis = None
                self._initialized = True
        return self._redis

    def _get_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"unified_context:{session_id}"

    async def save(self, session_id: str, context: UnifiedContext) -> bool:
        """Save context to Redis"""
        import json

        redis = await self._get_redis()
        if not redis:
            return False

        try:
            key = self._get_key(session_id)
            data = context.model_dump_json()
            redis.setex(key, self.ttl_seconds, data)
            logger.debug("redis_context_saved", session_id=session_id)
            return True
        except Exception as e:
            logger.error("redis_context_save_failed", error=str(e), session_id=session_id)
            return False

    async def load(self, session_id: str) -> Optional[UnifiedContext]:
        """Load context from Redis"""
        import json

        redis = await self._get_redis()
        if not redis:
            return None

        try:
            key = self._get_key(session_id)
            data = redis.get(key)
            if data:
                context = UnifiedContext.model_validate_json(data)
                logger.debug("redis_context_loaded", session_id=session_id)
                return context
            return None
        except Exception as e:
            logger.error("redis_context_load_failed", error=str(e), session_id=session_id)
            return None

    async def delete(self, session_id: str) -> bool:
        """Delete context from Redis"""
        redis = await self._get_redis()
        if not redis:
            return False

        try:
            key = self._get_key(session_id)
            redis.delete(key)
            logger.debug("redis_context_deleted", session_id=session_id)
            return True
        except Exception as e:
            logger.error("redis_context_delete_failed", error=str(e), session_id=session_id)
            return False

    async def exists(self, session_id: str) -> bool:
        """Check if context exists in Redis"""
        redis = await self._get_redis()
        if not redis:
            return False

        try:
            key = self._get_key(session_id)
            return redis.exists(key) > 0
        except Exception as e:
            return False


# Global Redis store singleton
_redis_store = RedisContextStore()


# ================================================================
# GLOBAL REGISTRY (Singleton per session)
# ================================================================

_unified_contexts: Dict[str, UnifiedContextManager] = {}


def get_unified_context_manager(session_id: str, use_redis: bool = True) -> UnifiedContextManager:
    """
    Get or create UnifiedContextManager for session

    Thread-safe singleton pattern per session_id
    With optional Redis persistence

    Args:
        session_id: Session identifier
        use_redis: Whether to try loading from Redis (default: True)
    """
    global _unified_contexts

    if session_id not in _unified_contexts:
        # Create new manager
        ctx_manager = UnifiedContextManager(session_id)

        # Try to load from Redis if enabled
        if use_redis:
            import asyncio
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, schedule loading
                    # The context will be synced on first access
                    pass
                else:
                    # Sync context, try to load from Redis
                    cached_context = loop.run_until_complete(_redis_store.load(session_id))
                    if cached_context:
                        ctx_manager._context = cached_context
                        logger.info("unified_context_loaded_from_redis", session_id=session_id)
            except RuntimeError:
                # No event loop available, skip Redis loading
                pass

        _unified_contexts[session_id] = ctx_manager
        logger.info("unified_context_manager_created", session_id=session_id)

    # Check if stale and reset if needed
    ctx_manager = _unified_contexts[session_id]
    if ctx_manager.is_stale():
        logger.info("unified_context_stale_reset", session_id=session_id)
        ctx_manager.reset()

    return ctx_manager


async def get_unified_context_manager_async(session_id: str) -> UnifiedContextManager:
    """
    Async version that properly loads from Redis

    Use this in async contexts for proper Redis loading
    """
    global _unified_contexts

    if session_id not in _unified_contexts:
        # Create new manager
        ctx_manager = UnifiedContextManager(session_id)

        # Try to load from Redis
        cached_context = await _redis_store.load(session_id)
        if cached_context:
            ctx_manager._context = cached_context
            logger.info("unified_context_loaded_from_redis_async", session_id=session_id)

        _unified_contexts[session_id] = ctx_manager
        logger.info("unified_context_manager_created_async", session_id=session_id)

    # Check if stale and reset if needed
    ctx_manager = _unified_contexts[session_id]
    if ctx_manager.is_stale():
        logger.info("unified_context_stale_reset", session_id=session_id)
        ctx_manager.reset()

    return ctx_manager


async def save_context_to_redis(session_id: str) -> bool:
    """
    Explicitly save context to Redis

    Call this after significant context updates to persist
    """
    if session_id in _unified_contexts:
        ctx_manager = _unified_contexts[session_id]
        return await _redis_store.save(session_id, ctx_manager._context)
    return False


def cleanup_stale_contexts():
    """
    Cleanup stale contexts (call periodically)

    Should be called by a background task every ~15 minutes
    """
    global _unified_contexts

    stale_sessions = [
        sid for sid, ctx in _unified_contexts.items()
        if ctx.is_stale()
    ]

    for sid in stale_sessions:
        del _unified_contexts[sid]
        logger.info("unified_context_cleaned", session_id=sid)

    logger.info("unified_context_cleanup_complete",
               cleaned=len(stale_sessions),
               remaining=len(_unified_contexts))
