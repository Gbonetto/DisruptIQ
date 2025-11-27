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


    # ================================================================
    # ENTITY TRACKING - For reference resolution
    # ================================================================

    def set_entity(
        self,
        session_id: str,
        entity_type: str,
        entity_data: Dict[str, Any]
    ):
        """
        Store a mentioned entity for reference resolution.

        Entity types: copropriete, coproprietaire, professionnel, document, montant

        Args:
            session_id: Conversation/session ID
            entity_type: Type of entity
            entity_data: {"name": "...", "id": ..., "metadata": {...}}
        """
        self._cleanup_expired()

        if session_id not in self._store:
            self._store[session_id] = {"_timestamp": datetime.now()}

        if "entities" not in self._store[session_id]:
            self._store[session_id]["entities"] = {}

        if entity_type not in self._store[session_id]["entities"]:
            self._store[session_id]["entities"][entity_type] = []

        # Add to front of list (most recent first)
        self._store[session_id]["entities"][entity_type].insert(0, {
            "data": entity_data,
            "timestamp": datetime.now()
        })

        # Keep only last 10 per type
        self._store[session_id]["entities"][entity_type] = \
            self._store[session_id]["entities"][entity_type][:10]

        logger.info("context_entity_stored",
                   session_id=session_id,
                   entity_type=entity_type,
                   entity_name=entity_data.get("name"))

    def get_last_entity(
        self,
        session_id: str,
        entity_types: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recently mentioned entity of given types.

        Args:
            session_id: Conversation/session ID
            entity_types: List of types to search (e.g., ["copropriete", "coproprietaire"])

        Returns:
            Most recent entity data or None
        """
        self._cleanup_expired()

        if session_id not in self._store:
            return None

        entities = self._store[session_id].get("entities", {})

        # Find most recent entity across all requested types
        best_entity = None
        best_timestamp = None

        for entity_type in entity_types:
            type_entities = entities.get(entity_type, [])
            if type_entities:
                latest = type_entities[0]  # Already sorted by recency
                ts = latest.get("timestamp")
                if best_timestamp is None or (ts and ts > best_timestamp):
                    best_entity = latest["data"]
                    best_timestamp = ts

        if best_entity:
            logger.info("context_entity_retrieved",
                       session_id=session_id,
                       entity_types=entity_types,
                       found_name=best_entity.get("name"))

        return best_entity

    def get_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get full context including entities for reference resolution.

        Returns dict with:
        - coproprietes: List of mentioned copropriétés
        - professionnels: List of mentioned professionnels
        - coproprietaires: List of mentioned copropriétaires
        - documents: List of mentioned documents
        - montants: List of mentioned amounts
        - last_mentioned: Most recently mentioned entity (any type)
        """
        self._cleanup_expired()

        if session_id not in self._store:
            return {}

        store_data = self._store[session_id]
        entities = store_data.get("entities", {})

        result = {
            "coproprietes": [e["data"] for e in entities.get("copropriete", [])],
            "professionnels": [e["data"] for e in entities.get("professionnel", [])],
            "coproprietaires": [e["data"] for e in entities.get("coproprietaire", [])],
            "documents": [e["data"] for e in entities.get("document", [])],
            "montants": [e["data"] for e in entities.get("montant", [])],
        }

        # Find the most recently mentioned entity overall
        all_entities = []
        for entity_type, entity_list in entities.items():
            for e in entity_list:
                all_entities.append({
                    "type": entity_type,
                    **e["data"],
                    "timestamp": e.get("timestamp")
                })

        if all_entities:
            # Sort by timestamp descending
            all_entities.sort(key=lambda x: x.get("timestamp") or datetime.min, reverse=True)
            result["last_mentioned"] = all_entities[0]

        return result


# Global singleton
context_store = SimpleContextStore()
