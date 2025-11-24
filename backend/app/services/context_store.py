"""
Simple Context Store - Shared context between agents

Permet aux agents de partager du contexte pendant une conversation:
- WorkflowAgent stocke workflow_data
- SQLAgent stocke query_results
- EmailAgent lit tout pour enrichir emails
"""

import structlog
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = structlog.get_logger()


class SimpleContextStore:
    """
    In-memory context store for agent-to-agent context sharing

    Simple dict-based, will be replaced by Redis when scaling
    """

    def __init__(self, ttl_minutes: int = 30):
        self._store: Dict[str, Dict[str, Any]] = {}
        self.ttl_minutes = ttl_minutes
        logger.info("context_store_initialized", ttl_minutes=ttl_minutes)

    def _cleanup_expired(self):
        """Remove expired contexts"""
        now = datetime.now()
        expired = [
            conv_id for conv_id, ctx in self._store.items()
            if (now - ctx.get("_timestamp", now)) > timedelta(minutes=self.ttl_minutes)
        ]
        for conv_id in expired:
            del self._store[conv_id]
            logger.info("context_expired", conversation_id=conv_id)

    def set_workflow(self, conversation_id: str, workflow_data: Dict[str, Any]):
        """Store workflow context"""
        self._cleanup_expired()

        if conversation_id not in self._store:
            self._store[conversation_id] = {}

        self._store[conversation_id].update({
            "last_workflow": workflow_data,
            "_timestamp": datetime.now()
        })

        logger.info("context_workflow_stored",
                   conversation_id=conversation_id,
                   workflow_type=workflow_data.get("workflow_type"))

    def get_workflow(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve workflow context"""
        self._cleanup_expired()
        return self._store.get(conversation_id, {}).get("last_workflow")

    def set_sql_results(self, conversation_id: str, results: Dict[str, Any]):
        """Store SQL query results (for email recipient resolution)"""
        self._cleanup_expired()

        if conversation_id not in self._store:
            self._store[conversation_id] = {}

        self._store[conversation_id].update({
            "last_sql_results": results,
            "_timestamp": datetime.now()
        })

        logger.info("context_sql_stored",
                   conversation_id=conversation_id,
                   result_count=len(results.get("results", [])))

    def get_sql_results(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve SQL results"""
        self._cleanup_expired()
        return self._store.get(conversation_id, {}).get("last_sql_results")

    def set_recipients(self, conversation_id: str, recipients: list):
        """Store recipient list"""
        self._cleanup_expired()

        if conversation_id not in self._store:
            self._store[conversation_id] = {}

        self._store[conversation_id].update({
            "last_recipients": recipients,
            "_timestamp": datetime.now()
        })

        logger.info("context_recipients_stored",
                   conversation_id=conversation_id,
                   count=len(recipients))

    def get_recipients(self, conversation_id: str) -> Optional[list]:
        """Retrieve recipients"""
        self._cleanup_expired()
        return self._store.get(conversation_id, {}).get("last_recipients")

    def get_all(self, conversation_id: str) -> Dict[str, Any]:
        """Get all context for conversation"""
        self._cleanup_expired()
        return self._store.get(conversation_id, {})

    def clear(self, conversation_id: str):
        """Clear context for conversation"""
        if conversation_id in self._store:
            del self._store[conversation_id]
            logger.info("context_cleared", conversation_id=conversation_id)

    # ================================================================
    # ENHANCED CONTEXT STORE - Solution 2 from MEMORY_ENHANCEMENT_PLAN.md
    # ================================================================

    def add_fact(self, session_id: str, fact_type: str, fact_data: Dict[str, Any]):
        """
        Store a structured fact for later recall

        Examples:
            add_fact(sid, "budget", {"amount": 50000, "for": "travaux toiture"})
            add_fact(sid, "date", {"event": "AG", "date": "20 janvier"})
            add_fact(sid, "contact", {"name": "M. Dupont", "apt": "45"})

        Args:
            session_id: Conversation/session ID
            fact_type: Type of fact (budget, date, contact, workflow, query_result)
            fact_data: Structured data for the fact
        """
        self._cleanup_expired()

        if session_id not in self._store:
            self._store[session_id] = {"_timestamp": datetime.now()}

        if "facts" not in self._store[session_id]:
            self._store[session_id]["facts"] = []

        fact_entry = {
            "type": fact_type,
            "data": fact_data,
            "timestamp": datetime.now()
        }

        self._store[session_id]["facts"].append(fact_entry)

        logger.info("context_fact_added",
                   session_id=session_id,
                   fact_type=fact_type,
                   fact_count=len(self._store[session_id]["facts"]))

    def query_facts(
        self,
        session_id: str,
        fact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query facts by type or get all facts

        Args:
            session_id: Conversation/session ID
            fact_type: Optional type filter (budget, date, contact, etc.)

        Returns:
            List of matching facts
        """
        self._cleanup_expired()

        if session_id not in self._store:
            return []

        facts = self._store[session_id].get("facts", [])

        if fact_type:
            filtered = [f for f in facts if f["type"] == fact_type]
            logger.info("context_facts_queried",
                       session_id=session_id,
                       fact_type=fact_type,
                       count=len(filtered))
            return filtered

        logger.info("context_facts_queried",
                   session_id=session_id,
                   fact_type="all",
                   count=len(facts))
        return facts


# Global singleton
context_store = SimpleContextStore()
