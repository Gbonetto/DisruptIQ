"""
Query Planning Agent - Agentic RAG Enhancement

Décompose queries complexes en sous-queries simples pour améliorer retrieval.

Use Cases:
- Multi-hop: "Les fenêtres et volets ont-ils la même couleur ?" → 2 queries
- Comparison: "Quel est le plus long document ?" → metadata query + ranking
- Ambiguous: "Quelle est la durée du contrat ?" → detect + clarify

Architecture:
- Input: Single complex query
- Output: QueryPlan with sub-queries + aggregation strategy
- Integration: Plugs into RAGService.search() with use_query_planning flag

IMPORTANT: This is a NON-BREAKING enhancement
- Default: DISABLED (use_query_planning=False)
- When enabled: Returns same format as normal search
- Compatible with existing ResponseFusionAgent
"""

import structlog
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

from app.services.llm_service import LLMService

logger = structlog.get_logger()


class QueryType(str, Enum):
    """Type de query détecté"""
    SIMPLE = "simple"  # Single fact lookup
    MULTI_HOP = "multi_hop"  # Requires multiple documents/chunks
    COMPARISON = "comparison"  # Compares 2+ entities
    AMBIGUOUS = "ambiguous"  # Missing context, multiple interpretations
    TEMPORAL = "temporal"  # Time-based reasoning
    NEGATION = "negation"  # Contains negation (what is NOT allowed)


class AggregationStrategy(str, Enum):
    """Comment combiner les résultats des sous-queries"""
    CONCAT = "concat"  # Concatenate results (multi-hop)
    COMPARE = "compare"  # Compare results side-by-side (comparison)
    MERGE = "merge"  # Merge and deduplicate (ambiguous)
    FILTER = "filter"  # Filter results by criteria (negation)
    SEQUENCE = "sequence"  # Execute in sequence, each depends on previous


class SubQuery(BaseModel):
    """Sous-query à exécuter"""
    query: str
    order: int  # Ordre d'exécution (pour SEQUENCE)
    description: str  # Pourquoi cette sub-query
    expected_doc_count: int = 3  # Nombre de docs attendus


class QueryPlan(BaseModel):
    """Plan d'exécution pour une query complexe"""
    original_query: str
    query_type: QueryType
    is_complex: bool  # True if needs decomposition
    sub_queries: List[SubQuery]
    aggregation_strategy: AggregationStrategy
    reasoning: str  # Explication du plan
    confidence: float  # Confidence dans le plan (0-1)


class QueryPlanningAgent:
    """
    Query Planning Agent - Décompose queries complexes

    Features:
    - Pattern detection (multi-hop, comparison, negation)
    - LLM-based decomposition for complex cases
    - Fast heuristics for simple queries (no LLM call)
    - Returns execution plan for RAGService

    Usage:
        planner = QueryPlanningAgent()
        plan = await planner.plan_query("Les fenêtres et volets ont même couleur ?")

        if plan.is_complex:
            # Execute sub-queries
            for sub_q in plan.sub_queries:
                chunks = await rag.search(sub_q.query)
        else:
            # Simple query - direct search
            chunks = await rag.search(query)
    """

    def __init__(self):
        self.llm_service = LLMService()

        # Pattern-based detection (fast, no LLM)
        self.multi_hop_patterns = [
            r'\bet\b.*\?',  # "X et Y ?"
            r'ont.*même|même.*que',  # "ont-ils la même"
            r'différence entre',  # "différence entre X et Y"
            r'comparer|comparaison',
        ]

        self.comparison_patterns = [
            r'plus (grand|long|cher|petit)',
            r'moins (grand|long|cher|petit)',
            r'meilleur|pire',
            r'qui est.*que',  # "qui est plus grand que"
        ]

        self.negation_patterns = [
            r"(ne|n').*pas",
            r'interdit|interdiction',
            r'sans|sauf',
            r'aucun|jamais',
        ]

        logger.info("query_planning_agent_initialized")

    async def plan_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QueryPlan:
        """
        Analyse query et génère plan d'exécution

        Args:
            query: User query
            context: Optional context (conversation history, etc.)

        Returns:
            QueryPlan with execution strategy
        """

        # PHASE 1: Fast heuristic detection (no LLM)
        query_type = self._detect_query_type(query)

        # PHASE 2: Simple queries → skip decomposition
        if query_type == QueryType.SIMPLE:
            return QueryPlan(
                original_query=query,
                query_type=QueryType.SIMPLE,
                is_complex=False,
                sub_queries=[SubQuery(
                    query=query,
                    order=0,
                    description="Simple query - no decomposition needed",
                    expected_doc_count=5
                )],
                aggregation_strategy=AggregationStrategy.CONCAT,
                reasoning="Simple fact lookup - direct search",
                confidence=1.0
            )

        # PHASE 2.5: Explicit comparisons → rule-based decomposition (NO LLM)
        # This is MUCH faster and more reliable than LLM for obvious cases
        if query_type == QueryType.COMPARISON:
            rule_based_plan = self._decompose_comparison_rule_based(query)
            if rule_based_plan:
                logger.info("comparison_decomposed_rule_based",
                           query=query[:60],
                           sub_queries=len(rule_based_plan.sub_queries))
                return rule_based_plan

        # PHASE 3: Complex queries → LLM decomposition
        logger.info("complex_query_detected",
                   query_type=query_type.value,
                   query=query[:60])

        plan = await self._decompose_with_llm(query, query_type, context)

        logger.info("query_plan_generated",
                   query_type=plan.query_type.value,
                   sub_queries_count=len(plan.sub_queries),
                   strategy=plan.aggregation_strategy.value,
                   confidence=plan.confidence)

        return plan

    def _detect_query_type(self, query: str) -> QueryType:
        """
        Fast pattern-based detection with structural analysis

        Returns:
            QueryType enum
        """
        import re

        query_lower = query.lower()

        # PRIORITY 1: Explicit comparisons with "et" (AND) between two entities
        # Pattern: "X et Y [comparison verb]" → MUST decompose
        # Examples: "fenêtres et volets même couleur?", "X et Y identiques?"
        # NOTE: Use [\w\s]+ to capture multi-word entities like "les fenêtres"
        explicit_comparison_patterns = [
            r'([\w\s]+?)\s+et\s+([\w\s]+?)\s+(ont.*même|même|identique|similaire|différent)',
            r'différence\s+entre\s+([\w\s]+?)\s+et\s+([\w\s]+?)[\s\?]',
            r'comparer?\s+([\w\s]+?)\s+(et|avec)\s+([\w\s]+)',  # comparer/compare (imperative/infinitive)
            r'^compare[rz]?\s+',  # Line starts with Compare/Comparer/Comparez
        ]

        for pattern in explicit_comparison_patterns:
            match = re.search(pattern, query_lower)
            if match:
                # Extract entities being compared
                # This is a TRUE multi-hop that requires decomposition
                logger.info("explicit_comparison_detected",
                           query=query[:60],
                           pattern=pattern[:40])
                return QueryType.COMPARISON

        # PRIORITY 2: Check standard comparison patterns
        for pattern in self.comparison_patterns:
            if re.search(pattern, query_lower):
                return QueryType.COMPARISON

        # PRIORITY 3: Multi-hop patterns (but NOT if it's a simple "et" conjunction)
        # Filter out: "règles concernant X et Y" (just listing, not comparing)
        # Keep: "Si X, alors Y" (sequential logic)
        multi_hop_sequential = [
            r'si.*alors',
            r'si.*qui',
            r'si.*ne.*pas',
        ]

        for pattern in multi_hop_sequential:
            if re.search(pattern, query_lower):
                return QueryType.MULTI_HOP

        # PRIORITY 4: Check negation patterns
        for pattern in self.negation_patterns:
            if re.search(pattern, query_lower):
                return QueryType.NEGATION

        # PRIORITY 5: Check temporal keywords
        temporal_keywords = ['combien de temps', 'délai', 'durée', 'avant', 'après', 'date']
        if any(kw in query_lower for kw in temporal_keywords):
            return QueryType.TEMPORAL

        # PRIORITY 6: Check ambiguous (multiple possible meanings)
        ambiguous_keywords = ['le contrat', 'la copropriété', 'le document']
        if any(kw in query_lower for kw in ambiguous_keywords):
            # Only ambiguous if no specific context
            if len(query.split()) < 8:  # Short query = likely ambiguous
                return QueryType.AMBIGUOUS

        # Default: simple
        return QueryType.SIMPLE

    async def _decompose_with_llm(
        self,
        query: str,
        query_type: QueryType,
        context: Optional[Dict[str, Any]] = None
    ) -> QueryPlan:
        """
        Use LLM to decompose complex query

        Args:
            query: Complex query
            query_type: Detected type
            context: Optional context

        Returns:
            QueryPlan with sub-queries
        """

        # Build prompt based on query type
        prompt = self._build_decomposition_prompt(query, query_type, context)

        try:
            # Call LLM using ainvoke
            from langchain.schema import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="You are a query decomposition expert. Break complex queries into simple sub-queries. Always respond in JSON format."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm_service.chat_model.ainvoke(messages)
            llm_output = response.content

            # Parse LLM response
            plan = self._parse_llm_response(query, query_type, llm_output)

            return plan

        except Exception as e:
            logger.error("llm_decomposition_failed",
                        error=str(e),
                        query=query[:60])

            # Fallback: treat as simple query
            return QueryPlan(
                original_query=query,
                query_type=query_type,
                is_complex=False,
                sub_queries=[SubQuery(
                    query=query,
                    order=0,
                    description="LLM decomposition failed - using original query",
                    expected_doc_count=5
                )],
                aggregation_strategy=AggregationStrategy.CONCAT,
                reasoning="Fallback to simple search due to decomposition error",
                confidence=0.5
            )

    def _build_decomposition_prompt(
        self,
        query: str,
        query_type: QueryType,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build LLM prompt for decomposition"""

        examples = {
            QueryType.MULTI_HOP: """
Example:
Query: "Les fenêtres et les volets ont-ils la même couleur ?"
Sub-queries:
1. "Quelle est la couleur des fenêtres ?"
2. "Quelle est la couleur des volets ?"
Aggregation: COMPARE (compare results to answer yes/no)
""",
            QueryType.COMPARISON: """
Example:
Query: "Quel est le document le plus long ?"
Sub-queries:
1. "Liste tous les documents avec leur taille"
Aggregation: FILTER (extract longest from metadata)
""",
            QueryType.NEGATION: """
Example:
Query: "Qu'est-ce qui est interdit sur les balcons ?"
Sub-queries:
1. "Quelles sont les règles concernant les balcons ?"
Aggregation: FILTER (extract prohibited items)
""",
            QueryType.TEMPORAL: """
Example:
Query: "Combien de temps à l'avance faut-il réserver ?"
Sub-queries:
1. "Quel est le délai de réservation ?"
Aggregation: CONCAT (extract duration/deadline)
""",
            QueryType.AMBIGUOUS: """
Example:
Query: "Quelle est la durée du contrat ?"
Sub-queries:
1. "Quelle est la durée du contrat de syndic ?"
2. "Quelle est la durée du contrat de nettoyage ?"
Aggregation: MERGE (return all relevant contracts)
"""
        }

        example = examples.get(query_type, "")

        prompt = f"""
You are a query decomposition expert for RAG systems.

Task: Analyze if this query NEEDS decomposition. Only decompose if absolutely necessary.

Query Type: {query_type.value}
Query: "{query}"

{example}

CRITICAL RULES:
1. **DEFAULT**: Keep as 1 query if possible
2. **ONLY decompose** if the query requires comparing 2+ distinct facts
3. **AVOID over-decomposition**: "rules about balconies" stays as 1 query
4. **For comparisons**: Split into exactly 2 sub-queries (one per entity)
5. **Keep queries broad**: Prefer "rules about X" over "what is forbidden on X"

Aggregation strategy:
   - CONCAT: Combine all results (default)
   - COMPARE: Compare results side-by-side (only for explicit comparisons)

Return ONLY valid JSON (no markdown, no explanation):
{{
  "sub_queries": [
    {{"query": "...", "order": 0, "description": "why"}},
    {{"query": "...", "order": 1, "description": "why"}}
  ],
  "aggregation_strategy": "concat",
  "reasoning": "why this decomposition",
  "confidence": 0.9
}}

CRITICAL RULES:
- Respond ONLY with the JSON object (no ```json```, no extra text)
- Keep sub-queries in French
- Use "concat" as default aggregation_strategy
- Each sub-query must be simple and factual
"""

        return prompt

    def _parse_llm_response(
        self,
        query: str,
        query_type: QueryType,
        llm_response: str
    ) -> QueryPlan:
        """Parse LLM JSON response into QueryPlan"""

        import json
        import re

        try:
            # Clean response - remove markdown blocks if present
            cleaned = llm_response.strip()

            # Remove ```json ``` blocks
            if '```json' in cleaned:
                cleaned = re.sub(r'```json\s*', '', cleaned)
                cleaned = re.sub(r'```\s*$', '', cleaned)
            elif '```' in cleaned:
                cleaned = re.sub(r'```\s*', '', cleaned, count=1)
                cleaned = re.sub(r'```\s*$', '', cleaned)

            cleaned = cleaned.strip()

            # Try to extract JSON object if embedded in text
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            data = json.loads(cleaned)

            # Build sub-queries
            sub_queries = []
            for i, sq_data in enumerate(data.get("sub_queries", [])):
                sub_queries.append(SubQuery(
                    query=sq_data["query"],
                    order=sq_data.get("order", i),
                    description=sq_data.get("description", ""),
                    expected_doc_count=3
                ))

            # Determine if complex (more than 1 sub-query)
            is_complex = len(sub_queries) > 1

            return QueryPlan(
                original_query=query,
                query_type=query_type,
                is_complex=is_complex,
                sub_queries=sub_queries,
                aggregation_strategy=AggregationStrategy(
                    data.get("aggregation_strategy", "concat")
                ),
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.8))
            )

        except Exception as e:
            logger.error("llm_response_parse_failed", error=str(e))

            # Fallback
            return QueryPlan(
                original_query=query,
                query_type=query_type,
                is_complex=False,
                sub_queries=[SubQuery(
                    query=query,
                    order=0,
                    description="Parse failed - using original",
                    expected_doc_count=5
                )],
                aggregation_strategy=AggregationStrategy.CONCAT,
                reasoning="Failed to parse LLM response",
                confidence=0.5
            )

    def _decompose_comparison_rule_based(self, query: str) -> Optional[QueryPlan]:
        """
        Rule-based decomposition for explicit comparisons (NO LLM needed)

        Examples:
        - "fenêtres et volets même couleur?" → 2 queries
        - "différence entre X et Y?" → 2 queries

        Returns:
            QueryPlan if successfully decomposed, None otherwise
        """
        import re

        query_lower = query.lower()

        # Pattern 1: "X et Y [comparison]"
        match = re.search(r'(.+?)\s+et\s+(.+?)\s+(ont.*même|même|identique|similaire|différent)', query_lower)
        if match:
            entity1 = match.group(1).strip()
            entity2 = match.group(2).strip()
            comparison_verb = match.group(3).strip()

            # Extract the attribute being compared (after comparison verb)
            # Example: "ont-ils la même couleur" → "couleur"
            attribute_match = re.search(r'(même|identique|similaire)\s+(\w+)', query_lower)
            attribute = attribute_match.group(2) if attribute_match else "propriétés"

            return QueryPlan(
                original_query=query,
                query_type=QueryType.COMPARISON,
                is_complex=True,
                sub_queries=[
                    SubQuery(
                        query=f"Quel(le) est {attribute} de {entity1} ?",
                        order=0,
                        description=f"Get {attribute} of {entity1}",
                        expected_doc_count=3
                    ),
                    SubQuery(
                        query=f"Quel(le) est {attribute} de {entity2} ?",
                        order=1,
                        description=f"Get {attribute} of {entity2}",
                        expected_doc_count=3
                    )
                ],
                aggregation_strategy=AggregationStrategy.COMPARE,
                reasoning=f"Explicit comparison: {entity1} vs {entity2} on {attribute}",
                confidence=0.95
            )

        # Pattern 2: "différence entre X et Y"
        match = re.search(r'différence\s+entre\s+(.+?)\s+et\s+(.+?)[\s\?]', query_lower)
        if match:
            entity1 = match.group(1).strip()
            entity2 = match.group(2).strip()

            return QueryPlan(
                original_query=query,
                query_type=QueryType.COMPARISON,
                is_complex=True,
                sub_queries=[
                    SubQuery(
                        query=f"Quelles sont les caractéristiques de {entity1} ?",
                        order=0,
                        description=f"Get properties of {entity1}",
                        expected_doc_count=3
                    ),
                    SubQuery(
                        query=f"Quelles sont les caractéristiques de {entity2} ?",
                        order=1,
                        description=f"Get properties of {entity2}",
                        expected_doc_count=3
                    )
                ],
                aggregation_strategy=AggregationStrategy.COMPARE,
                reasoning=f"Explicit difference: {entity1} vs {entity2}",
                confidence=0.95
            )

        # Pattern 3: "Compare X et Y" or "Comparer X et Y" (imperative/infinitive)
        match = re.search(r'compare[rz]?\s+(.+?)\s+(et|avec)\s+(.+?)(?:\s*[\?\.]|$)', query_lower)
        if match:
            entity1 = match.group(1).strip()
            entity2 = match.group(3).strip()

            return QueryPlan(
                original_query=query,
                query_type=QueryType.COMPARISON,
                is_complex=True,
                sub_queries=[
                    SubQuery(
                        query=f"Informations sur {entity1}",
                        order=0,
                        description=f"Get information about {entity1}",
                        expected_doc_count=3
                    ),
                    SubQuery(
                        query=f"Informations sur {entity2}",
                        order=1,
                        description=f"Get information about {entity2}",
                        expected_doc_count=3
                    )
                ],
                aggregation_strategy=AggregationStrategy.COMPARE,
                reasoning=f"Explicit comparison command: {entity1} vs {entity2}",
                confidence=0.95
            )

        # Could not decompose with rules
        return None

    def should_use_planning(self, query: str) -> bool:
        """
        Quick check: Does this query benefit from planning?

        Use this for fast bypass of simple queries.

        Returns:
            True if query is complex enough to benefit from planning
        """
        query_type = self._detect_query_type(query)
        return query_type != QueryType.SIMPLE
