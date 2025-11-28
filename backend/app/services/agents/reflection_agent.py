"""
Reflection Agent - Meta-level RAG optimization

This agent analyzes WHY retrieval failed and applies corrective strategies.

Use Cases:
- Vocabulary mismatch → Query expansion with synonyms
- Fragmented information → Expand context window
- Wrong granularity → Aggregate adjacent chunks
- Out of scope → Signal low confidence

Architecture:
- Input: query + low-quality results + failure history
- Output: improved results OR confidence signal
- Integration: Last resort after Verification fails

Key Features:
1. Failure diagnosis (vocabulary, fragmentation, scope)
2. Strategy selection (expansion, aggregation, entity-based)
3. Quality assessment (confidence scoring)
4. Learning feedback (for future improvements)
"""

import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

from app.services.llm_service import LLMService

logger = structlog.get_logger()


class FailureType(str, Enum):
    """Types of retrieval failures"""
    VOCABULARY_MISMATCH = "vocabulary_mismatch"  # User words != document words
    FRAGMENTED_INFO = "fragmented_info"           # Answer split across chunks
    WRONG_GRANULARITY = "wrong_granularity"       # Chunks too small/large
    OUT_OF_SCOPE = "out_of_scope"                 # Information not in corpus
    AMBIGUOUS_QUERY = "ambiguous_query"           # Query needs clarification


class ReflectionStrategy(str, Enum):
    """Corrective strategies"""
    QUERY_EXPANSION = "query_expansion"         # Add synonyms/related terms
    CONTEXT_EXPANSION = "context_expansion"     # Fetch adjacent chunks
    ENTITY_SEARCH = "entity_search"             # Search by named entities
    METADATA_FILTER = "metadata_filter"         # Try metadata-based search
    SIGNAL_UNKNOWN = "signal_unknown"           # Admit "don't know"


class ReflectionResult(BaseModel):
    """Result of reflection analysis"""
    failure_type: FailureType
    strategy_used: ReflectionStrategy
    improved_results: Optional[List[Dict[str, Any]]] = None
    confidence: float  # 0-1
    reasoning: str
    should_return: bool  # True if we have acceptable results
    fallback_message: Optional[str] = None  # If should_return=False


class ReflectionAgent:
    """
    Reflection Agent - Diagnoses and fixes RAG failures

    Features:
    - Failure type detection (LLM-based)
    - Strategy selection and application
    - Quality-based decision making
    - Graceful degradation (admit "don't know")

    Usage:
        reflector = ReflectionAgent()
        result = await reflector.reflect_and_improve(
            query="...",
            low_quality_chunks=[...],
            search_func=rag.search,
            verification_attempts=2
        )
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.min_acceptable_confidence = 0.25  # Below this, signal "unknown"
        logger.info("reflection_agent_initialized",
                   min_confidence=self.min_acceptable_confidence)

    async def reflect_and_improve(
        self,
        query: str,
        low_quality_chunks: List[Dict[str, Any]],
        search_func,  # Async function for re-search
        verification_attempts: int = 0
    ) -> ReflectionResult:
        """
        Analyze failure and attempt correction

        Args:
            query: Original user query
            low_quality_chunks: Current results (low quality)
            search_func: Function to call for new searches
            verification_attempts: How many times verification tried

        Returns:
            ReflectionResult with improved chunks or fallback
        """

        logger.info("reflection_agent_activated",
                   query=query[:60],
                   current_chunks=len(low_quality_chunks),
                   verification_attempts=verification_attempts)

        # PHASE 1: Diagnose failure type
        diagnosis = await self._diagnose_failure(query, low_quality_chunks)

        logger.info("failure_diagnosed",
                   failure_type=diagnosis['failure_type'],
                   reasoning=diagnosis['reasoning'][:80])

        failure_type = FailureType(diagnosis['failure_type'])

        # PHASE 2: Select and apply strategy
        strategy = self._select_strategy(failure_type, verification_attempts)

        logger.info("strategy_selected",
                   strategy=strategy.value,
                   failure_type=failure_type.value)

        # PHASE 3: Execute strategy
        improved_chunks = await self._execute_strategy(
            strategy=strategy,
            query=query,
            current_chunks=low_quality_chunks,
            search_func=search_func,
            diagnosis=diagnosis
        )

        # PHASE 4: Evaluate results
        if improved_chunks:
            top_score = improved_chunks[0].get('reranked_score', improved_chunks[0].get('score', 0))

            if top_score >= self.min_acceptable_confidence:
                logger.info("reflection_succeeded",
                           strategy=strategy.value,
                           improved_score=f"{top_score:.1%}",
                           improved_chunks=len(improved_chunks))

                return ReflectionResult(
                    failure_type=failure_type,
                    strategy_used=strategy,
                    improved_results=improved_chunks,
                    confidence=top_score,
                    reasoning=f"Reflection strategy '{strategy.value}' improved results",
                    should_return=True
                )

        # PHASE 5: If all strategies fail, signal "unknown"
        logger.warning("reflection_failed_all_strategies",
                      query=query[:60],
                      strategy_attempted=strategy.value)

        return ReflectionResult(
            failure_type=failure_type,
            strategy_used=ReflectionStrategy.SIGNAL_UNKNOWN,
            improved_results=low_quality_chunks,  # Return original
            confidence=0.10,  # Very low
            reasoning=f"Unable to find reliable answer after reflection. Failure type: {failure_type.value}",
            should_return=True,
            fallback_message="Je n'ai pas trouvé de réponse fiable dans les documents disponibles. Pouvez-vous reformuler votre question ?"
        )

    async def _diagnose_failure(
        self,
        query: str,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Use LLM to diagnose WHY retrieval failed

        Returns:
            {
                "failure_type": str,
                "reasoning": str,
                "suggested_action": str
            }
        """

        chunks_text = "\n\n---\n\n".join([
            f"[Chunk {i+1}, Score: {c.get('reranked_score', c.get('score', 0)):.1%}]\n{c.get('text', '')[:300]}"
            for i, c in enumerate(chunks[:3])
        ])

        prompt = f"""
You are a RAG failure analyst. Your job is to diagnose WHY retrieval failed.

User Query: "{query}"

Retrieved Chunks (low quality):
{chunks_text}

Task: Diagnose the failure type and suggest corrective action.

Respond ONLY with valid JSON:
{{
  "failure_type": "vocabulary_mismatch" | "fragmented_info" | "wrong_granularity" | "out_of_scope" | "ambiguous_query",
  "reasoning": "why retrieval failed (1-2 sentences)",
  "suggested_action": "what to try next"
}}

Failure Types:
- **vocabulary_mismatch**: User uses different words than documents (e.g., "société" vs "entreprise")
- **fragmented_info**: Answer exists but split across multiple chunks
- **wrong_granularity**: Chunks are too small/large for this query
- **out_of_scope**: Information simply not in the corpus
- **ambiguous_query**: Query is too vague or has multiple interpretations

Rules:
1. Look for vocabulary differences between query and chunks
2. Check if chunks contain PARTIAL information (fragmentation sign)
3. If chunks are completely unrelated → likely out_of_scope
4. If score > 5% but < 25% → likely vocabulary or fragmentation issue
5. If score < 5% → likely out_of_scope

Be analytical and precise.
"""

        try:
            from langchain.schema import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="You are a RAG diagnostic expert. Respond only in JSON."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm_service.chat_model.ainvoke(messages)
            llm_output = response.content

            # Parse JSON
            import json
            import re

            cleaned = llm_output.strip()
            if '```json' in cleaned:
                cleaned = re.sub(r'```json\s*', '', cleaned)
                cleaned = re.sub(r'```\s*$', '', cleaned)
            elif '```' in cleaned:
                cleaned = re.sub(r'```\s*', '', cleaned, count=1)
                cleaned = re.sub(r'```\s*$', '', cleaned)

            cleaned = cleaned.strip()
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            diagnosis = json.loads(cleaned)
            return diagnosis

        except Exception as e:
            logger.error("diagnosis_failed", error=str(e))

            # Fallback: heuristic diagnosis
            top_score = chunks[0].get('reranked_score', chunks[0].get('score', 0)) if chunks else 0

            if top_score < 0.05:
                failure_type = "out_of_scope"
            elif top_score < 0.15:
                failure_type = "vocabulary_mismatch"
            else:
                failure_type = "fragmented_info"

            return {
                "failure_type": failure_type,
                "reasoning": f"Heuristic diagnosis based on score {top_score:.1%}",
                "suggested_action": "Try alternative search strategy"
            }

    def _select_strategy(
        self,
        failure_type: FailureType,
        verification_attempts: int
    ) -> ReflectionStrategy:
        """
        Select corrective strategy based on failure type
        """

        strategy_map = {
            FailureType.VOCABULARY_MISMATCH: ReflectionStrategy.QUERY_EXPANSION,
            FailureType.FRAGMENTED_INFO: ReflectionStrategy.CONTEXT_EXPANSION,
            FailureType.WRONG_GRANULARITY: ReflectionStrategy.CONTEXT_EXPANSION,
            FailureType.AMBIGUOUS_QUERY: ReflectionStrategy.ENTITY_SEARCH,
            FailureType.OUT_OF_SCOPE: ReflectionStrategy.SIGNAL_UNKNOWN,
        }

        return strategy_map.get(failure_type, ReflectionStrategy.QUERY_EXPANSION)

    async def _execute_strategy(
        self,
        strategy: ReflectionStrategy,
        query: str,
        current_chunks: List[Dict[str, Any]],
        search_func,
        diagnosis: Dict[str, str]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute the selected strategy
        """

        if strategy == ReflectionStrategy.QUERY_EXPANSION:
            return await self._query_expansion(query, search_func)

        elif strategy == ReflectionStrategy.CONTEXT_EXPANSION:
            return await self._context_expansion(current_chunks, search_func)

        elif strategy == ReflectionStrategy.ENTITY_SEARCH:
            return await self._entity_search(query, search_func)

        elif strategy == ReflectionStrategy.SIGNAL_UNKNOWN:
            return None  # No improved results

        else:
            logger.warning("unknown_strategy", strategy=strategy.value)
            return None

    async def _query_expansion(
        self,
        query: str,
        search_func
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Expand query with synonyms and related terms
        """

        logger.info("executing_query_expansion", query=query[:60])

        # Generate expanded queries with synonyms
        expansion_prompt = f"""
Given this query: "{query}"

Generate 2 alternative queries using synonyms and related terms.
Keep the SAME intent but use DIFFERENT vocabulary.

Examples:
- "société" → "entreprise", "compagnie", "organisme"
- "contrat" → "accord", "convention", "engagement"
- "nettoyage" → "propreté", "entretien", "ménage"

Respond with JSON array:
["alternative query 1", "alternative query 2"]

Keep queries concise and in French.
"""

        try:
            from langchain.schema import HumanMessage, SystemMessage
            import json
            import re

            messages = [
                SystemMessage(content="You are a query expansion expert."),
                HumanMessage(content=expansion_prompt)
            ]

            response = await self.llm_service.chat_model.ainvoke(messages)
            expanded_text = response.content.strip()

            # Clean and parse
            if '```json' in expanded_text:
                expanded_text = re.sub(r'```json\s*', '', expanded_text)
                expanded_text = re.sub(r'```\s*$', '', expanded_text)

            json_match = re.search(r'\[.*\]', expanded_text, re.DOTALL)
            if json_match:
                expanded_text = json_match.group(0)

            expanded_queries = json.loads(expanded_text)

            # Search with expanded queries
            all_chunks = []
            for exp_query in expanded_queries[:2]:  # Max 2 expansions
                logger.info("searching_expanded_query", query=exp_query[:60])
                new_chunks = await search_func(query=exp_query, limit=3)
                all_chunks.extend(new_chunks)

            # Deduplicate and sort by score
            seen = set()
            unique_chunks = []
            for chunk in all_chunks:
                text_key = chunk.get('text', '')[:200]
                if text_key not in seen:
                    seen.add(text_key)
                    unique_chunks.append(chunk)

            unique_chunks.sort(
                key=lambda c: c.get('reranked_score', c.get('score', 0)),
                reverse=True
            )

            logger.info("query_expansion_completed",
                       expanded_queries=len(expanded_queries),
                       chunks_found=len(unique_chunks))

            return unique_chunks[:5]

        except Exception as e:
            logger.error("query_expansion_failed", error=str(e))
            return None

    async def _context_expansion(
        self,
        current_chunks: List[Dict[str, Any]],
        search_func
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch adjacent chunks to expand context

        Strategy: Get chunks AROUND the current ones (before/after)
        """

        logger.info("executing_context_expansion",
                   current_chunks=len(current_chunks))

        # For now, return current chunks (context expansion requires chunk IDs)
        # Full implementation would fetch adjacent chunks from vector DB
        logger.warning("context_expansion_not_fully_implemented",
                      reason="requires chunk adjacency metadata")

        return current_chunks

    async def _entity_search(
        self,
        query: str,
        search_func
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Extract entities and search by them
        """

        logger.info("executing_entity_search", query=query[:60])

        # Extract key entities (proper nouns, dates, numbers)
        import re

        # Simple entity extraction (proper nouns capitalized)
        words = query.split()
        entities = [w for w in words if w and w[0].isupper()]

        if not entities:
            logger.warning("no_entities_found", query=query[:60])
            return None

        # Search with entities only
        entity_query = " ".join(entities)
        logger.info("searching_entities", entities=entity_query)

        try:
            entity_chunks = await search_func(query=entity_query, limit=5)
            return entity_chunks
        except Exception as e:
            logger.error("entity_search_failed", error=str(e))
            return None
