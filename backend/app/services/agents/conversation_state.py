"""
Conversation State Manager - Maintains context across multi-turn conversations

Tracks:
- Current topic and sub-topic
- Identified recipients (emails)
- Pending actions (email draft, SQL query, etc.)
- Business context (incident details, property info, etc.)
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from enum import Enum
import structlog

if TYPE_CHECKING:
    from app.services.agents.entity_graph import EntityGraph

logger = structlog.get_logger()


class ActionType(str, Enum):
    """Types of pending actions"""
    AWAITING_EMAIL_CONFIRMATION = "awaiting_email_confirmation"
    AWAITING_SQL_QUERY = "awaiting_sql_query"
    AWAITING_RECIPIENT_SELECTION = "awaiting_recipient_selection"
    AWAITING_MODIFICATION = "awaiting_modification"
    NONE = "none"


class ConversationState(BaseModel):
    """
    Conversation state tracking

    Example usage:
    User: "envoyer mail aux copropriétaires des mimosas pour odeurs de gaz"
    State:
        topic: "odeurs de gaz"
        sub_topic: "alerte sécurité"
        recipients_context: "copropriétaires des mimosas"
        pending_action: AWAITING_RECIPIENT_SELECTION
        business_context: {"incident_type": "gaz", "property": "les mimosas"}
    """

    # Current conversation topic
    topic: Optional[str] = Field(None, description="Main topic (ex: 'dégât des eaux', 'odeurs de gaz')")
    sub_topic: Optional[str] = Field(None, description="Sub-topic (ex: 'alerte copropriétaires', 'demande devis')")

    # Recipients tracking
    recipients_identified: List[str] = Field(default_factory=list, description="List of email addresses identified")
    recipients_context: Optional[str] = Field(None, description="Description of intended recipients")

    # Pending actions
    pending_action: ActionType = Field(ActionType.NONE, description="Current pending action")
    pending_data: Dict[str, Any] = Field(default_factory=dict, description="Data for pending action")

    # Business context (incident details, property info, etc.)
    business_context: Dict[str, Any] = Field(default_factory=dict, description="Business-related context")

    # Last SQL results for reference
    last_sql_results: Optional[Dict[str, Any]] = Field(None, description="Last SQL query results")

    # Last query results as structured entities (for reference resolution)
    last_query_entities: List[Dict[str, Any]] = Field(default_factory=list, description="Last entities from query (people, professionals)")
    last_query_type: Optional[str] = Field(None, description="Type of last query: 'people', 'professionals', 'properties'")

    # Email draft in progress
    email_draft: Optional[Dict[str, Any]] = Field(None, description="Current email draft")

    # Recently uploaded documents (for "le doc", "ce fichier" references)
    last_uploaded_documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recently uploaded documents (max 5, FIFO)"
    )

    # Active documents for RAG filtering (checkbox selection from frontend)
    active_document_ids: Optional[List[int]] = Field(
        None,
        description="List of document IDs currently selected for RAG search (from checkbox panel)"
    )

    def update_topic(self, topic: str, sub_topic: Optional[str] = None):
        """Update conversation topic"""
        self.topic = topic
        if sub_topic:
            self.sub_topic = sub_topic
        logger.info("state_topic_updated", topic=topic, sub_topic=sub_topic)

    def add_recipients(self, emails: List[str]):
        """Add identified recipients"""
        new_emails = [e for e in emails if e not in self.recipients_identified]
        self.recipients_identified.extend(new_emails)
        logger.info("state_recipients_added", count=len(new_emails), total=len(self.recipients_identified))

    def set_recipients_context(self, context: str):
        """Set recipient context description"""
        self.recipients_context = context
        logger.info("state_recipients_context_set", context=context)

    def set_pending_action(self, action: ActionType, data: Dict[str, Any] = None):
        """Set pending action"""
        self.pending_action = action
        self.pending_data = data or {}
        logger.info("state_pending_action_set", action=action.value)

    def clear_pending_action(self):
        """Clear pending action"""
        self.pending_action = ActionType.NONE
        self.pending_data = {}
        logger.info("state_pending_action_cleared")

    def update_business_context(self, context: Dict[str, Any]):
        """Update business context"""
        self.business_context.update(context)
        logger.info("state_business_context_updated", keys=list(context.keys()))

    def set_email_draft(self, draft: Dict[str, Any]):
        """Store email draft"""
        self.email_draft = draft
        self.set_pending_action(ActionType.AWAITING_EMAIL_CONFIRMATION, {"draft": draft})
        logger.info("state_email_draft_set", has_recipients=bool(draft.get("recipients")))

    def set_last_query_entities(self, entities: List[Dict[str, Any]], query_type: str):
        """
        Store entities from last query for reference resolution

        Args:
            entities: List of entity dicts (with 'nom', 'prenom', 'email', etc.)
            query_type: Type of entities ('people', 'professionals', 'properties')
        """
        self.last_query_entities = entities
        self.last_query_type = query_type
        logger.info("state_last_query_entities_set",
                   count=len(entities),
                   query_type=query_type)

    def add_uploaded_document(self, filename: str, document_id: int, mime_type: str):
        """
        Track recently uploaded document for reference resolution

        Args:
            filename: Original filename
            document_id: Database document ID
            mime_type: MIME type
        """
        doc_info = {
            "filename": filename,
            "document_id": document_id,
            "mime_type": mime_type
        }

        # Add to beginning (most recent first)
        self.last_uploaded_documents.insert(0, doc_info)

        # Keep only last 5 documents (FIFO)
        if len(self.last_uploaded_documents) > 5:
            self.last_uploaded_documents = self.last_uploaded_documents[:5]

        logger.info("state_document_uploaded",
                   filename=filename,
                   document_id=document_id,
                   total_tracked=len(self.last_uploaded_documents))

    def set_active_document_ids(self, document_ids: List[int]):
        """
        Update list of active documents for RAG filtering

        Args:
            document_ids: List of document IDs currently selected (from checkbox panel)
        """
        self.active_document_ids = document_ids
        logger.info("state_active_documents_updated",
                   count=len(document_ids),
                   ids=document_ids)

    def get_context_summary(self) -> str:
        """Get human-readable context summary"""
        parts = []
        if self.topic:
            parts.append(f"Sujet: {self.topic}")
        if self.recipients_context:
            parts.append(f"Destinataires: {self.recipients_context}")
        if self.recipients_identified:
            parts.append(f"Emails trouvés: {len(self.recipients_identified)}")
        if self.business_context:
            parts.append(f"Contexte: {', '.join(f'{k}={v}' for k, v in self.business_context.items())}")
        return " | ".join(parts) if parts else "Aucun contexte"

    def get_relevant_professions(self) -> List[str]:
        """
        Get relevant professions based on incident type

        Returns list of profession categories that should be contacted for the current incident
        """
        if not self.business_context or "incident_type" not in self.business_context:
            return []

        incident_type = self.business_context["incident_type"]

        # Map incident types to relevant professions
        incident_profession_map = {
            "gas": ["chauffagiste", "plombier"],
            "water_damage": ["plombier", "chauffagiste"],
            "electrical": ["électricien"],
            "heating": ["chauffagiste"],
            "plumbing": ["plombier"],
            "locksmith": ["serrurier"],
            "painting": ["peintre"],
            "carpentry": ["menuisier"],
            "masonry": ["maçon"],
            "gardening": ["jardinier"]
        }

        return incident_profession_map.get(incident_type, [])


class StateManager:
    """
    Manages conversation state across turns

    Singleton pattern - one state per session
    Now includes EntityGraph for robust entity tracking
    """

    def __init__(self):
        self.state = ConversationState()

        # Initialize EntityGraph for entity tracking
        from app.services.agents.entity_graph import EntityGraph
        self.entity_graph = EntityGraph(context_window_minutes=30)

        logger.info("state_manager_initialized", has_entity_graph=True)

    def get_state(self) -> ConversationState:
        """Get current state"""
        return self.state

    def get_entity_graph(self) -> 'EntityGraph':
        """Get entity graph"""
        return self.entity_graph

    async def pre_populate_entity_graph(self, db):
        """
        Pre-populate EntityGraph with all coproprietes from database

        This ensures entity resolution works from the first query,
        resolving variations like "residence des jardins" -> "Résidence Les Jardins"

        Args:
            db: Database session
        """
        try:
            from sqlalchemy import text
            from app.services.agents.query_enrichment import EntityPopulator

            # Fetch all coproprietes
            query = text("SELECT id, nom FROM coproprietes")
            result = await db.execute(query)
            rows = result.fetchall()

            # Convert to dict format
            coproprietes_data = [
                {"id": row[0], "nom": row[1]}
                for row in rows
            ]

            # Use EntityPopulator to populate graph
            populator = EntityPopulator()
            await populator.populate_from_sql_results(
                results=coproprietes_data,
                query_type="coproprietes",
                entity_graph=self.entity_graph
            )

            logger.info("entity_graph_pre_populated",
                       coproprietes_count=len(coproprietes_data),
                       total_entities=len(self.entity_graph.entities))

        except Exception as e:
            logger.warning("entity_graph_pre_population_failed", error=str(e))
            # Non-critical - continue without pre-population

    def reset(self):
        """Reset state"""
        self.state = ConversationState()
        logger.info("state_reset")

    def extract_and_update_from_message(self, user_message: str, response_data: Dict[str, Any] = None):
        """
        Extract relevant info from user message and update state

        Args:
            user_message: User's input
            response_data: Response data from agent (SQL results, etc.)
        """
        message_lower = user_message.lower()

        # Extract topic keywords
        if "dégât" in message_lower or "fuite" in message_lower:
            self.state.update_topic("dégât des eaux", "alerte")
            self.state.update_business_context({"incident_type": "water_damage"})

        elif "gaz" in message_lower or "odeur" in message_lower:
            self.state.update_topic("odeurs de gaz", "alerte sécurité")
            self.state.update_business_context({"incident_type": "gas", "urgency": "high"})

        elif "devis" in message_lower or "quote" in message_lower:
            self.state.update_topic("demande de devis", "fournisseurs")

        # Extract recipient context
        if "copropriétaire" in message_lower:
            if "mimosas" in message_lower:
                self.state.set_recipients_context("copropriétaires des mimosas")
            elif "tous" in message_lower or "all" in message_lower:
                self.state.set_recipients_context("tous les copropriétaires")
            else:
                self.state.set_recipients_context("copropriétaires")

        elif "voisin" in message_lower:
            self.state.set_recipients_context("voisins")

        elif "chauffagiste" in message_lower:
            self.state.set_recipients_context("chauffagistes")
            self.state.update_business_context({"profession_requested": "chauffagiste"})

        elif "plombier" in message_lower:
            self.state.set_recipients_context("plombiers")
            self.state.update_business_context({"profession_requested": "plombier"})

        # Update from response data
        if response_data:
            # Extract emails from SQL results
            if "emails_available" in response_data:
                self.state.add_recipients(response_data["emails_available"])

            # Store SQL results
            if "results" in response_data:
                self.state.last_sql_results = response_data

            # Store email draft
            if "email_draft" in response_data:
                self.state.set_email_draft(response_data["email_draft"])

        logger.info("state_updated_from_message",
                    topic=self.state.topic,
                    recipients_count=len(self.state.recipients_identified),
                    context=self.state.recipients_context)
