"""
Query Enrichment Layer - Enrich user queries with context before execution

This layer sits between the user input and the orchestrator, enriching queries
with contextual information from:
- EntityGraph (resolved references)
- ConversationState (previous results)
- Database schema (validation)

Example Flow:
    User: "copropriétaires de la Residence Les Jardins"

    1. Extract entities: ["Residence Les Jardins"]
    2. Resolve reference: Residence Les Jardins → Entity(db_id=1)
    3. Enrich query: "copropriétaires de la Residence Les Jardins (DB ID: 1, confirmed exists)"
    4. Add context: {"copropriete_id": 1, "copropriete_name": "Residence Les Jardins"}

    Result: SQL Agent can now generate accurate query with explicit ID

Inspired by:
- Semantic Machines (Microsoft Research)
- Text-to-SQL SOTA systems
- Notion AI entity resolution
"""

import structlog
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re

from app.services.agents.entity_graph import (
    EntityGraph,
    Entity,
    EntityType,
    extract_copropriete_aliases
)
from app.services.agents.conversation_state import ConversationState

logger = structlog.get_logger()


@dataclass
class ExtractedEntity:
    """Entity extracted from user query"""
    text: str  # Original text from query
    type: EntityType
    span: Tuple[int, int]  # Start, end position in query
    confidence: float = 1.0


@dataclass
class EnrichedQuery:
    """Enriched query with context"""
    original_query: str
    enriched_query: str  # Query with resolved references
    extracted_entities: List[ExtractedEntity]
    resolved_entities: Dict[str, Entity]  # {text: Entity}
    context: Dict[str, Any]
    confidence: float
    needs_validation: bool = False
    validation_message: Optional[str] = None


class QueryEnrichmentLayer:
    """
    Query enrichment pipeline

    Steps:
    1. Entity extraction (detect entity mentions)
    2. Reference resolution (resolve to canonical entities)
    3. Schema validation (check entities exist in DB)
    4. Query expansion (add explicit context)
    """

    def __init__(self):
        """Initialize enrichment layer"""
        # Entity patterns for extraction
        self.entity_patterns = {
            EntityType.COPROPRIETE: [
                r'\b(Residence|Résidence|Immeuble|Villa|Le|Les)\s+[A-Z][a-zéèêàâù]+(?:\s+[A-Z][a-zéèêàâù]+)*',
                r'\b(copropriété|copropriete)\s+([A-Z][a-zéèêàâù\s]+)',
                r'\bde\s+la\s+([A-Z][a-zéèêàâù\s]+)',
                r'\bdes\s+([A-Z][a-zéèêàâù\s]+)',
            ],
            EntityType.PERSON: [
                r'\b([A-ZÉÈÊÀÂ][a-zéèêàâù]+)\s+([A-ZÉÈÊÀÂ][a-zéèêàâù]+)\b',  # Nom Prenom
            ],
            EntityType.PROFESSIONAL: [
                r'\b(chauffagiste|plombier|électricien|menuisier|peintre|jardinier|serrurier|maçon)s?\b',
            ]
        }

        logger.info("query_enrichment_layer_initialized")

    async def enrich(
        self,
        user_query: str,
        entity_graph: EntityGraph,
        conversation_state: ConversationState,
        db: Optional[AsyncSession] = None
    ) -> EnrichedQuery:
        """
        Main enrichment pipeline

        Args:
            user_query: Original user query
            entity_graph: EntityGraph with tracked entities
            conversation_state: Conversation state
            db: Optional database session for validation

        Returns:
            EnrichedQuery with resolved references and context
        """
        logger.info("query_enrichment_started", query=user_query[:50])

        # Step 1: Extract entity mentions
        extracted_entities = self._extract_entities(user_query)

        logger.info("entities_extracted", count=len(extracted_entities))

        # Step 2: Resolve references to canonical entities
        resolved_entities = {}
        for extracted in extracted_entities:
            resolution = entity_graph.resolve(
                extracted.text,
                entity_type=extracted.type,
                min_confidence=0.6
            )

            if resolution.entity:
                resolved_entities[extracted.text] = resolution.entity
                logger.info("entity_resolved",
                           query_text=extracted.text,
                           canonical=resolution.entity.canonical_name,
                           confidence=resolution.confidence,
                           method=resolution.method)

        # Step 3: Build enriched query
        enriched_query = user_query
        context = {}

        for extracted_text, entity in resolved_entities.items():
            # Add DB ID to context if available
            if entity.db_id is not None:
                if entity.type == EntityType.COPROPRIETE:
                    context["copropriete_id"] = entity.db_id
                    context["copropriete_name"] = entity.canonical_name

                    # Enrich query with explicit reference
                    enriched_query = self._inject_reference(
                        enriched_query,
                        extracted_text,
                        entity
                    )

                elif entity.type == EntityType.PERSON:
                    context["person_id"] = entity.db_id
                    context["person_name"] = entity.canonical_name

        # Step 4: Validate entities exist in DB (if db session provided)
        needs_validation = False
        validation_message = None

        if db and resolved_entities:
            validation_result = await self._validate_entities_in_db(
                resolved_entities,
                db
            )

            needs_validation = not validation_result["all_valid"]
            if needs_validation:
                validation_message = validation_result["message"]

        # Step 5: Add conversation context
        if conversation_state.last_query_entities:
            context["previous_results_available"] = True
            context["previous_query_type"] = conversation_state.last_query_type

        # Calculate overall confidence
        if resolved_entities:
            avg_confidence = sum(
                entity_graph.resolve(text, min_confidence=0.0).confidence
                for text in resolved_entities.keys()
            ) / len(resolved_entities)
        else:
            avg_confidence = 1.0  # No entities to resolve

        logger.info("query_enrichment_completed",
                   original=user_query[:50],
                   enriched=enriched_query[:50],
                   entities_resolved=len(resolved_entities),
                   confidence=avg_confidence)

        return EnrichedQuery(
            original_query=user_query,
            enriched_query=enriched_query,
            extracted_entities=extracted_entities,
            resolved_entities=resolved_entities,
            context=context,
            confidence=avg_confidence,
            needs_validation=needs_validation,
            validation_message=validation_message
        )

    def _extract_entities(self, query: str) -> List[ExtractedEntity]:
        """
        Extract entity mentions from query using regex patterns

        Args:
            query: User query

        Returns:
            List of extracted entities with positions
        """
        extracted = []

        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, query, re.IGNORECASE)

                for match in matches:
                    text = match.group(0).strip()

                    # Skip very short matches
                    if len(text) < 3:
                        continue

                    # Skip common false positives
                    if text.lower() in ["de la", "des", "les", "le"]:
                        continue

                    extracted.append(ExtractedEntity(
                        text=text,
                        type=entity_type,
                        span=(match.start(), match.end()),
                        confidence=0.8
                    ))

        return extracted

    def _inject_reference(
        self,
        query: str,
        extracted_text: str,
        entity: Entity
    ) -> str:
        """
        Inject explicit reference into query

        Example:
            Input:  "copropriétaires de la Residence Les Jardins"
            Entity: Entity(db_id=1, canonical_name="Residence Les Jardins")
            Output: "copropriétaires de la Residence Les Jardins (copropriété ID: 1)"

        Args:
            query: Original query
            extracted_text: Text to replace
            entity: Resolved entity

        Returns:
            Query with injected reference
        """
        if entity.type == EntityType.COPROPRIETE and entity.db_id:
            injection = f"{entity.canonical_name} (copropriété ID: {entity.db_id})"
            enriched = query.replace(extracted_text, injection)
            return enriched

        return query

    async def _validate_entities_in_db(
        self,
        entities: Dict[str, Entity],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Validate that entities exist in database

        Args:
            entities: Dict of resolved entities
            db: Database session

        Returns:
            Validation result dict
        """
        all_valid = True
        invalid_entities = []

        for text, entity in entities.items():
            if entity.db_id is None:
                continue

            # Check based on entity type
            if entity.type == EntityType.COPROPRIETE:
                query = text("SELECT COUNT(*) FROM coproprietes WHERE id = :id")
                result = await db.execute(query, {"id": entity.db_id})
                count = result.scalar()

                if count == 0:
                    all_valid = False
                    invalid_entities.append(entity.canonical_name)
                    logger.warning("entity_not_found_in_db",
                                 entity=entity.canonical_name,
                                 db_id=entity.db_id,
                                 type=entity.type.value)

        if not all_valid:
            message = f"Les entités suivantes n'existent plus dans la base : {', '.join(invalid_entities)}"
        else:
            message = "All entities validated"

        return {
            "all_valid": all_valid,
            "invalid_entities": invalid_entities,
            "message": message
        }


class EntityPopulator:
    """
    Populates EntityGraph from SQL query results

    After SQL Agent returns results, this component extracts entities
    and adds them to the graph for future reference resolution.
    """

    async def populate_from_sql_results(
        self,
        results: List[Dict[str, Any]],
        query_type: str,
        entity_graph: EntityGraph
    ):
        """
        Extract entities from SQL results and add to graph

        Args:
            results: SQL query results
            query_type: Type of query ("coproprietes", "people", "professionals")
            entity_graph: EntityGraph to populate
        """
        if not results:
            return

        entity_count = 0

        if query_type == "coproprietes":
            # Extract copropriété entities
            for idx, row in enumerate(results):
                # Support both "nom" and "copropriete_nom" columns
                coprop_name = row.get("nom") or row.get("copropriete_nom")
                coprop_id = row.get("id") or row.get("copropriete_id") or idx

                if coprop_name:
                    # Handle coproprietaires as list or comma-separated string
                    coproprietaires = row.get("coproprietaires_names", [])
                    if not coproprietaires:
                        coproprietaires_str = row.get("coproprietaires_noms", "")
                        if coproprietaires_str:
                            coproprietaires = coproprietaires_str.split(", ")
                        else:
                            coproprietaires = []

                    entity = Entity(
                        id=f"copropriete_{coprop_id}",
                        type=EntityType.COPROPRIETE,
                        canonical_name=coprop_name,
                        aliases=extract_copropriete_aliases(coprop_name),
                        attributes={
                            "lots": row.get("nombre_lots"),
                            "coproprietaires": coproprietaires
                        },
                        db_id=coprop_id if isinstance(coprop_id, int) else None
                    )
                    entity_graph.add_entity(entity)
                    entity_count += 1

        elif query_type == "people":
            # Extract people entities
            for row in results:
                if "nom" in row and "prenom" in row and "id" in row:
                    full_name = f"{row['prenom']} {row['nom']}"
                    entity = Entity(
                        id=f"person_{row['id']}",
                        type=EntityType.PERSON,
                        canonical_name=full_name,
                        aliases={row['nom'], row['prenom'], full_name.lower()},
                        attributes={
                            "email": row.get("email"),
                            "telephone": row.get("telephone"),
                            "copropriete_id": row.get("copropriete_id")
                        },
                        db_id=row["id"]
                    )
                    entity_graph.add_entity(entity)
                    entity_count += 1

        elif query_type == "professionals":
            # Extract professional entities
            for row in results:
                if "name" in row and "id" in row:
                    entity = Entity(
                        id=f"professional_{row['id']}",
                        type=EntityType.PROFESSIONAL,
                        canonical_name=row["name"],
                        aliases={row["name"].lower()},
                        attributes={
                            "category": row.get("category"),
                            "email": row.get("email"),
                            "phone": row.get("phone")
                        },
                        db_id=row["id"]
                    )
                    entity_graph.add_entity(entity)
                    entity_count += 1

        if entity_count > 0:
            logger.info("entities_populated_from_sql",
                       query_type=query_type,
                       count=entity_count)
