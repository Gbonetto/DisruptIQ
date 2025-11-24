"""
Simple Context Store - Shared context between agents

Permet aux agents de partager du contexte pendant une conversation:
- WorkflowAgent stocke workflow_data
- SQLAgent stocke query_results
- EmailAgent lit tout pour enrichir emails
"""

import structlog
from typing import Dict, Any, Optional
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


# Global singleton
context_store = SimpleContextStore()
