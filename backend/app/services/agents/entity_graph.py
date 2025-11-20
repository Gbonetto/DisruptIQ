"""
EntityGraph - Graph-based entity tracking and resolution

Inspired by Notion AI and modern knowledge graph systems.
Tracks entities (copropriétés, people, professionals) and their relationships
across conversation turns for robust reference resolution.

Example Usage:
    graph = EntityGraph()

    # After query: "liste des copropriétés avec copropriétaires"
    graph.add_entity(Entity(
        id="copropriete_1",
        type=EntityType.COPROPRIETE,
        canonical_name="Residence Les Jardins",
        aliases=["les jardins", "jardins", "residence jardins"],
        attributes={"lots": 45, "db_id": 1}
    ))

    # Next query: "copropriétaires de la Residence Les Jardins"
    resolved = graph.resolve("Residence Les Jardins")  # → Entity(id="copropriete_1")

Key Features:
- Fuzzy matching with multiple algorithms (Levenshtein, Jaro-Winkler, embeddings)
- Alias tracking (multiple ways to refer to same entity)
- Relationship graph (Person → lives_in → Copropriete)
- Temporal decay (older entities get lower relevance scores)
- Multi-turn context window
"""

import structlog
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import difflib
from rapidfuzz import fuzz
import re
import unicodedata
import numpy as np
from functools import lru_cache

logger = structlog.get_logger()

# Lazy import for sentence transformers (heavy dependency)
_embedder = None

def get_embedder():
    """Lazy load sentence transformer model"""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Use multilingual model optimized for French
            _embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("sentence_transformer_loaded", model="paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            logger.warning("sentence_transformer_load_failed", error=str(e))
            _embedder = None
    return _embedder


def normalize_text(text: str) -> str:
    """
    Normalize text for matching: lowercase + remove accents

    Example:
        normalize_text("Résidence Les Jardins") → "residence les jardins"
    """
    # Remove accents using unicode normalization
    nfd = unicodedata.normalize('NFD', text)
    text_without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    return text_without_accents.lower()


def strip_titles(text: str) -> str:
    """
    Remove common French honorific titles from text

    Supports: M., Mme, Mme., Mlle, Mlle., Mr, Mr., Monsieur, Madame, Mademoiselle

    Examples:
        strip_titles("M. Dupont") → "Dupont"
        strip_titles("Mme Marie Dubois") → "Marie Dubois"
        strip_titles("Mlle. Sophie") → "Sophie"
        strip_titles("Mr Moussu") → "Moussu"
        strip_titles("Monsieur Jean") → "Jean"
    """
    import re
    # Pattern: Match titles at the beginning, optionally followed by period and space
    title_pattern = r'^(M\.|Mme\.?|Mlle\.?|Mr\.?|Monsieur|Madame|Mademoiselle)\s+'
    cleaned = re.sub(title_pattern, '', text, flags=re.IGNORECASE)
    return cleaned.strip()


class EntityType(str, Enum):
    """Types of entities we track"""
    COPROPRIETE = "copropriete"
    PERSON = "person"
    PROFESSIONAL = "professional"
    PROPERTY = "property"
    DOCUMENT = "document"
    ORGANIZATION = "organization"
    LOCATION = "location"


class RelationType(str, Enum):
    """Types of relationships between entities"""
    LIVES_IN = "lives_in"
    WORKS_FOR = "works_for"
    MANAGES = "manages"
    OWNS = "owns"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"


@dataclass
class Entity:
    """
    Represents a tracked entity in the graph

    Attributes:
        id: Unique identifier (e.g., "copropriete_1")
        type: EntityType enum
        canonical_name: Official name (e.g., "Residence Les Jardins")
        aliases: Alternative names (e.g., ["les jardins", "jardins"])
        attributes: Additional properties (e.g., {"lots": 45, "db_id": 1})
        db_id: Database ID if entity is from DB
        confidence: Confidence score (0.0-1.0)
        first_mentioned: Timestamp of first mention
        last_mentioned: Timestamp of last mention
        mention_count: Number of times mentioned
        embedding: Semantic embedding vector (lazy computed)
    """
    id: str
    type: EntityType
    canonical_name: str
    aliases: Set[str] = field(default_factory=set)
    attributes: Dict[str, any] = field(default_factory=dict)
    db_id: Optional[int] = None
    confidence: float = 1.0
    first_mentioned: datetime = field(default_factory=datetime.now)
    last_mentioned: datetime = field(default_factory=datetime.now)
    mention_count: int = 0
    embedding: Optional[np.ndarray] = field(default=None, repr=False)

    def update_mention(self):
        """Update mention timestamp and count"""
        self.last_mentioned = datetime.now()
        self.mention_count += 1

    def get_recency_score(self) -> float:
        """
        Calculate recency score (temporal decay)

        Returns:
            Score between 0.0-1.0 (1.0 = just mentioned, decays over time)
        """
        time_since_mention = datetime.now() - self.last_mentioned

        # Decay function: score = e^(-t/tau)
        # tau = 10 minutes (half-life)
        tau_minutes = 10.0
        decay = max(0.0, 1.0 - (time_since_mention.total_seconds() / 60.0) / tau_minutes)

        return decay

    def get_embedding(self) -> Optional[np.ndarray]:
        """
        Get or compute semantic embedding for canonical name

        Returns:
            Embedding vector or None if embedder unavailable
        """
        if self.embedding is not None:
            return self.embedding

        embedder = get_embedder()
        if embedder is None:
            return None

        try:
            # Compute embedding for canonical name
            self.embedding = embedder.encode(self.canonical_name, convert_to_numpy=True)
            return self.embedding
        except Exception as e:
            logger.warning("embedding_computation_failed", entity=self.canonical_name, error=str(e))
            return None


@dataclass
class Relation:
    """Represents a relationship between two entities"""
    source_id: str
    relation_type: RelationType
    target_id: str
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ResolutionResult:
    """Result of entity resolution"""
    entity: Optional[Entity]
    confidence: float
    method: str  # "exact", "alias", "fuzzy", "embedding"
    alternatives: List[Tuple[Entity, float]] = field(default_factory=list)


class EntityGraph:
    """
    Graph-based entity tracker with fuzzy resolution

    Maintains a knowledge graph of entities and their relationships
    across conversation turns.

    Features:
    - LRU cache for frequent resolutions (performance optimization)
    - Multi-level matching (exact, alias, fuzzy, semantic)
    - Temporal decay for recency scoring
    """

    def __init__(self, context_window_minutes: int = 30, cache_size: int = 100):
        """
        Initialize EntityGraph

        Args:
            context_window_minutes: How long to keep entities active (default 30 min)
            cache_size: Size of LRU cache for resolution results (default 100)
        """
        self.entities: Dict[str, Entity] = {}  # {id: Entity}
        self.relations: List[Relation] = []
        self.canonical_index: Dict[str, str] = {}  # {canonical_name_lower: id}
        self.alias_index: Dict[str, Set[str]] = {}  # {alias_lower: {id1, id2}}
        self.context_window = timedelta(minutes=context_window_minutes)

        # LRU cache for resolution results (key: query + entity_type)
        self._resolution_cache_size = cache_size
        self._resolution_cache: Dict[str, ResolutionResult] = {}
        self._cache_access_order: List[str] = []

        logger.info("entity_graph_initialized",
                   context_window_minutes=context_window_minutes,
                   cache_size=cache_size)

    def _cache_key(self, query: str, entity_type: Optional[EntityType]) -> str:
        """Generate cache key for resolution"""
        type_str = entity_type.value if entity_type else "any"
        return f"{normalize_text(query)}:{type_str}"

    def _get_from_cache(self, cache_key: str) -> Optional[ResolutionResult]:
        """Get resolution result from LRU cache"""
        if cache_key in self._resolution_cache:
            # Move to end (most recently used)
            self._cache_access_order.remove(cache_key)
            self._cache_access_order.append(cache_key)
            logger.debug("resolution_cache_hit", key=cache_key[:50])
            return self._resolution_cache[cache_key]
        return None

    def _put_in_cache(self, cache_key: str, result: ResolutionResult):
        """Put resolution result in LRU cache"""
        if cache_key in self._resolution_cache:
            # Update existing + move to end
            self._cache_access_order.remove(cache_key)
        elif len(self._resolution_cache) >= self._resolution_cache_size:
            # Evict least recently used
            lru_key = self._cache_access_order.pop(0)
            del self._resolution_cache[lru_key]
            logger.debug("resolution_cache_evict", key=lru_key[:50])

        self._resolution_cache[cache_key] = result
        self._cache_access_order.append(cache_key)
        logger.debug("resolution_cache_put", key=cache_key[:50])

    def _invalidate_cache(self):
        """Invalidate entire resolution cache (called when entities change)"""
        self._resolution_cache.clear()
        self._cache_access_order.clear()
        logger.debug("resolution_cache_invalidated")

    def add_entity(self, entity: Entity) -> str:
        """
        Add or update entity in graph

        Args:
            entity: Entity to add

        Returns:
            Entity ID
        """
        # Check if entity already exists (by canonical name)
        existing_id = self._find_existing_entity(entity.canonical_name, entity.type)

        if existing_id:
            # Update existing entity
            existing = self.entities[existing_id]
            existing.update_mention()
            existing.aliases.update(entity.aliases)
            existing.attributes.update(entity.attributes)
            existing.confidence = max(existing.confidence, entity.confidence)

            logger.info("entity_updated", id=existing_id, name=entity.canonical_name)

            # Invalidate cache when entities change
            self._invalidate_cache()

            return existing_id

        else:
            # Add new entity
            self.entities[entity.id] = entity

            # Index canonical name
            canonical_key = normalize_text(entity.canonical_name)
            self.canonical_index[canonical_key] = entity.id

            # Index aliases
            for alias in entity.aliases:
                alias_key = normalize_text(alias)
                if alias_key not in self.alias_index:
                    self.alias_index[alias_key] = set()
                self.alias_index[alias_key].add(entity.id)

            logger.info("entity_added", id=entity.id, name=entity.canonical_name, type=entity.type.value)

            # Invalidate cache when entities change
            self._invalidate_cache()

            return entity.id

    def add_relation(self, relation: Relation):
        """Add relationship between entities"""
        self.relations.append(relation)
        logger.info("relation_added",
                   source=relation.source_id,
                   type=relation.relation_type.value,
                   target=relation.target_id)

    def resolve(
        self,
        query: str,
        entity_type: Optional[EntityType] = None,
        min_confidence: float = 0.75
    ) -> ResolutionResult:
        """
        Resolve entity reference to canonical entity with LRU caching

        Uses multi-level matching strategy:
        1. LRU Cache lookup (performance optimization)
        2. Exact match on canonical name
        3. Exact match on alias
        4. Fuzzy match with multiple algorithms
        5. Semantic embedding similarity (bonus)

        Args:
            query: User's reference (e.g., "les jardins")
            entity_type: Optional type filter
            min_confidence: Minimum confidence threshold

        Returns:
            ResolutionResult with best match
        """
        # Check cache first
        cache_key = self._cache_key(query, entity_type)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        # Strip titles before normalization (handles "M. Dupont" → "Dupont")
        query_cleaned = strip_titles(query.strip())
        query_lower = normalize_text(query_cleaned)

        # Filter active entities (within context window)
        active_entities = self._get_active_entities(entity_type)

        if not active_entities:
            logger.info("no_active_entities", query=query[:30])
            result = ResolutionResult(entity=None, confidence=0.0, method="none")
            self._put_in_cache(cache_key, result)
            return result

        # Level 1: Exact match on canonical name
        if query_lower in self.canonical_index:
            entity_id = self.canonical_index[query_lower]
            entity = self.entities[entity_id]
            entity.update_mention()

            logger.info("resolution_exact", query=query[:30], entity=entity.canonical_name)
            result = ResolutionResult(entity=entity, confidence=1.0, method="exact")
            self._put_in_cache(cache_key, result)
            return result

        # Level 2: Exact match on alias
        if query_lower in self.alias_index:
            matching_ids = self.alias_index[query_lower]

            # If multiple matches, use recency + type filter
            best_entity = self._select_best_from_ids(matching_ids, entity_type)

            if best_entity:
                best_entity.update_mention()
                logger.info("resolution_alias", query=query[:30], entity=best_entity.canonical_name)
                result = ResolutionResult(entity=best_entity, confidence=0.95, method="alias")
                self._put_in_cache(cache_key, result)
                return result

        # Level 3: Fuzzy matching
        fuzzy_results = self._fuzzy_match(query, active_entities, entity_type)

        if fuzzy_results and fuzzy_results[0][1] >= min_confidence:
            best_entity, confidence = fuzzy_results[0]
            best_entity.update_mention()

            alternatives = [(e, conf) for e, conf in fuzzy_results[1:3]]

            logger.info("resolution_fuzzy",
                       query=query[:30],
                       entity=best_entity.canonical_name,
                       confidence=confidence)

            result = ResolutionResult(
                entity=best_entity,
                confidence=confidence,
                method="fuzzy",
                alternatives=alternatives
            )
            self._put_in_cache(cache_key, result)
            return result

        # No match found
        logger.warning("resolution_failed", query=query[:30], entity_type=entity_type)
        result = ResolutionResult(entity=None, confidence=0.0, method="none")
        self._put_in_cache(cache_key, result)
        return result

    def get_related_entities(
        self,
        entity_id: str,
        relation_type: Optional[RelationType] = None
    ) -> List[Entity]:
        """
        Get entities related to given entity

        Args:
            entity_id: Source entity ID
            relation_type: Optional relation type filter

        Returns:
            List of related entities
        """
        related_ids = []

        for relation in self.relations:
            if relation.source_id == entity_id:
                if relation_type is None or relation.relation_type == relation_type:
                    related_ids.append(relation.target_id)

        return [self.entities[rid] for rid in related_ids if rid in self.entities]

    def get_entity_by_db_id(self, db_id: int, entity_type: EntityType) -> Optional[Entity]:
        """Get entity by database ID"""
        for entity in self.entities.values():
            if entity.db_id == db_id and entity.type == entity_type:
                return entity
        return None

    def get_active_entities(self, entity_type: Optional[EntityType] = None) -> List[Entity]:
        """Get all active entities (within context window)"""
        return self._get_active_entities(entity_type)

    def cleanup_stale_entities(self):
        """Remove entities outside context window"""
        now = datetime.now()
        stale_ids = []

        for entity_id, entity in self.entities.items():
            time_since_mention = now - entity.last_mentioned
            if time_since_mention > self.context_window:
                stale_ids.append(entity_id)

        for entity_id in stale_ids:
            entity = self.entities[entity_id]

            # Remove from canonical index
            canonical_key = normalize_text(entity.canonical_name)
            self.canonical_index.pop(canonical_key, None)

            # Remove from alias index
            for alias in entity.aliases:
                alias_key = normalize_text(alias)
                if alias_key in self.alias_index:
                    self.alias_index[alias_key].discard(entity_id)
                    if not self.alias_index[alias_key]:
                        del self.alias_index[alias_key]

            # Remove entity
            del self.entities[entity_id]

        if stale_ids:
            logger.info("entities_cleaned_up", count=len(stale_ids))

    # ==================== PRIVATE METHODS ====================

    def _find_existing_entity(self, canonical_name: str, entity_type: EntityType) -> Optional[str]:
        """Find existing entity by canonical name and type"""
        canonical_key = normalize_text(canonical_name)

        if canonical_key in self.canonical_index:
            entity_id = self.canonical_index[canonical_key]
            entity = self.entities[entity_id]

            if entity.type == entity_type:
                return entity_id

        return None

    def _get_active_entities(self, entity_type: Optional[EntityType] = None) -> List[Entity]:
        """Get active entities within context window"""
        now = datetime.now()
        active = []

        for entity in self.entities.values():
            time_since_mention = now - entity.last_mentioned

            if time_since_mention <= self.context_window:
                if entity_type is None or entity.type == entity_type:
                    active.append(entity)

        return active

    def _select_best_from_ids(
        self,
        entity_ids: Set[str],
        entity_type: Optional[EntityType] = None
    ) -> Optional[Entity]:
        """Select best entity from multiple IDs based on recency and type"""
        candidates = [self.entities[eid] for eid in entity_ids if eid in self.entities]

        # Filter by type
        if entity_type:
            candidates = [e for e in candidates if e.type == entity_type]

        if not candidates:
            return None

        # Sort by recency score
        candidates.sort(key=lambda e: e.get_recency_score(), reverse=True)

        return candidates[0]

    def _fuzzy_match(
        self,
        query: str,
        entities: List[Entity],
        entity_type: Optional[EntityType] = None
    ) -> List[Tuple[Entity, float]]:
        """
        Fuzzy match using multiple algorithms with strict type filtering

        Combines:
        - Levenshtein distance (difflib)
        - Jaro-Winkler similarity (rapidfuzz)
        - Partial ratio (substring matching)
        - Token set ratio (word order invariant)

        Strictly filters by entity_type when provided to prevent cross-type matches
        (e.g., prevent "des jardins" from matching person names)
        """
        query_lower = normalize_text(query.strip())
        results = []

        for entity in entities:
            # STRICT type filtering: reject immediately if types don't match
            if entity_type and entity.type != entity_type:
                continue

            # Score against canonical name (with semantic embedding)
            canonical_score = self._compute_similarity(
                query_lower,
                normalize_text(entity.canonical_name),
                entity=entity  # Pass entity for semantic matching
            )

            # Score against aliases (string-based only, no semantic for aliases)
            alias_scores = [
                self._compute_similarity(query_lower, normalize_text(alias), entity=None)
                for alias in entity.aliases
            ]

            # Take max score
            max_alias_score = max(alias_scores) if alias_scores else 0.0
            final_score = max(canonical_score, max_alias_score)

            # Boost by recency
            recency_boost = entity.get_recency_score() * 0.1
            final_score = min(1.0, final_score + recency_boost)

            results.append((entity, final_score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def _compute_similarity(self, query: str, target: str, entity: Optional[Entity] = None) -> float:
        """
        Compute similarity between query and target using multiple metrics + semantic embeddings

        Returns weighted average of:
        - SequenceMatcher ratio (Levenshtein-based)
        - Jaro-Winkler (good for names)
        - Partial ratio (substring matching)
        - Token set ratio (word order invariant)
        - Semantic similarity (cosine similarity of embeddings) - BONUS

        Args:
            query: Query string
            target: Target string
            entity: Optional entity for semantic embedding
        """
        # 1. SequenceMatcher (difflib)
        seq_score = difflib.SequenceMatcher(None, query, target).ratio()

        # 2. Jaro-Winkler (rapidfuzz)
        jaro_score = fuzz.ratio(query, target) / 100.0

        # 3. Partial ratio (substring)
        partial_score = fuzz.partial_ratio(query, target) / 100.0

        # 4. Token set ratio (word order invariant)
        token_score = fuzz.token_set_ratio(query, target) / 100.0

        # Base weighted average (string-based matching)
        string_weights = [0.25, 0.25, 0.30, 0.20]
        string_score = (
            seq_score * string_weights[0] +
            jaro_score * string_weights[1] +
            partial_score * string_weights[2] +
            token_score * string_weights[3]
        )

        # 5. Semantic similarity (if embedder available and entity provided)
        semantic_score = 0.0
        if entity is not None:
            embedder = get_embedder()
            if embedder is not None:
                try:
                    # Get entity embedding (cached)
                    entity_emb = entity.get_embedding()

                    if entity_emb is not None:
                        # Compute query embedding
                        query_emb = embedder.encode(query, convert_to_numpy=True)

                        # Cosine similarity
                        cosine_sim = np.dot(query_emb, entity_emb) / (
                            np.linalg.norm(query_emb) * np.linalg.norm(entity_emb)
                        )
                        semantic_score = float(cosine_sim)

                        logger.debug("semantic_similarity_computed",
                                   query=query[:30],
                                   target=target[:30],
                                   semantic_score=semantic_score,
                                   string_score=string_score)
                except Exception as e:
                    logger.warning("semantic_similarity_failed", error=str(e))

        # Combine string and semantic scores
        # If semantic is available, give it 20% weight, string 80%
        if semantic_score > 0.0:
            final_score = string_score * 0.80 + semantic_score * 0.20
        else:
            final_score = string_score

        return final_score


# ==================== UTILITY FUNCTIONS ====================

def extract_copropriete_aliases(name: str) -> Set[str]:
    """
    Extract common aliases for copropriété names with comprehensive preposition variations

    Example:
        "Résidence Les Jardins" → {
            "les jardins", "jardins", "residence jardins",
            "des jardins", "du jardin", "de la jardin",
            "residence les jardins", "residence des jardins"
        }

    This handles French preposition variations that users commonly make:
    - "Les Jardins" vs "Des Jardins" vs "Du Jardin"
    - "Le Parc" vs "Du Parc" vs "Au Parc"
    """
    aliases = set()
    name_lower = normalize_text(name)

    # Add the full normalized name
    aliases.add(name_lower)

    # Common property prefixes
    prefixes = ["residence", "immeuble", "villa", "ensemble", "cite", "domaine"]

    # French prepositions and articles
    prepositions = ["les", "des", "le", "du", "la", "de la", "de", "au", "aux"]

    # Step 1: Remove prefixes to get core name
    core_name = name_lower
    for prefix in prefixes:
        if core_name.startswith(prefix + " "):
            core_name = core_name.replace(prefix + " ", "", 1).strip()
            # Add version without prefix
            aliases.add(core_name)
            break

    # Step 2: Extract base name (after preposition)
    base_name = core_name
    for prep in prepositions:
        if core_name.startswith(prep + " "):
            base_name = core_name.replace(prep + " ", "", 1).strip()
            # Add just the base name
            if base_name:
                aliases.add(base_name)
            break

    # Step 3: Generate all preposition variations
    if base_name != core_name:  # We found a preposition
        for prep in prepositions:
            # Create variant with different preposition
            variant = f"{prep} {base_name}"
            aliases.add(variant)

            # Also add with prefix
            for prefix in prefixes:
                if prefix in name_lower:
                    full_variant = f"{prefix} {prep} {base_name}"
                    aliases.add(full_variant)

    # Step 4: Singular/plural variations for common endings
    singular_plural_map = {
        "jardins": "jardin",
        "terrasses": "terrasse",
        "parcs": "parc",
        "chenes": "chene",
        "roses": "rose",
        "oliviers": "olivier"
    }

    for plural, singular in singular_plural_map.items():
        if plural in name_lower:
            # Add singular version
            singular_variant = name_lower.replace(plural, singular)
            aliases.add(singular_variant)

            # Add singular version with all preposition variations
            for prep in prepositions:
                if f"{prep} {plural}" in name_lower:
                    sing_prep_variant = name_lower.replace(f"{prep} {plural}", f"{prep} {singular}")
                    aliases.add(sing_prep_variant)

    # Clean up: remove empty strings and very short aliases
    aliases = {a.strip() for a in aliases if a and len(a.strip()) >= 3}

    return aliases
