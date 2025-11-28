"""
World-Class RAG Mixin - Shared capabilities for all agents
Provides uniform thought emission and quality enhancement

This mixin enables any agent to:
1. Emit thoughts to the CoT stream for UI transparency
2. Use World-Class RAG components (Verification, Reflection, Synthesis)
3. Track reasoning steps for debugging

Usage:
    class MyAgent(BaseAgent, WorldClassRAGMixin):
        async def process(self, input: AgentInput) -> AgentOutput:
            await self.emit_thought("Analyzing query...", ThoughtType.ANALYZING)
            # ... processing ...
            await self.emit_thought("Done!", ThoughtType.COMPLETED)

Author: Claude Code - World-Class SMA Architecture
Date: November 28, 2025
"""

import structlog
from typing import Dict, Any, Optional, List, Callable, Awaitable
from enum import Enum

logger = structlog.get_logger()


class WorldClassThoughtType(str, Enum):
    """Extended thought types for World-Class RAG pipeline"""
    # Query Planning
    QUERY_PLANNING = "query_planning"
    QUERY_DECOMPOSING = "query_decomposing"
    SUBQUERY_EXECUTING = "subquery_executing"

    # Verification
    VERIFICATION_CHECKING = "verification_checking"
    VERIFICATION_REFINING = "verification_refining"
    VERIFICATION_COMPLETE = "verification_complete"

    # Reflection
    REFLECTION_DIAGNOSING = "reflection_diagnosing"
    REFLECTION_IMPROVING = "reflection_improving"
    REFLECTION_COMPLETE = "reflection_complete"

    # Synthesis
    SYNTHESIS_STARTING = "synthesis_starting"
    SYNTHESIS_CITING = "synthesis_citing"
    SYNTHESIS_COMPLETE = "synthesis_complete"

    # LLM Internal
    LLM_CALLING = "llm_calling"
    LLM_REASONING = "llm_reasoning"
    LLM_RESPONSE = "llm_response"


# French labels for World-Class thought types
WORLD_CLASS_THOUGHT_LABELS_FR = {
    WorldClassThoughtType.QUERY_PLANNING: "🧩 Planification de requête",
    WorldClassThoughtType.QUERY_DECOMPOSING: "🔀 Décomposition en sous-requêtes",
    WorldClassThoughtType.SUBQUERY_EXECUTING: "🔍 Exécution sous-requête",

    WorldClassThoughtType.VERIFICATION_CHECKING: "🔍 Vérification de pertinence",
    WorldClassThoughtType.VERIFICATION_REFINING: "🔄 Raffinement de la recherche",
    WorldClassThoughtType.VERIFICATION_COMPLETE: "✅ Vérification terminée",

    WorldClassThoughtType.REFLECTION_DIAGNOSING: "🤔 Diagnostic du problème",
    WorldClassThoughtType.REFLECTION_IMPROVING: "🔄 Amélioration des résultats",
    WorldClassThoughtType.REFLECTION_COMPLETE: "✅ Réflexion terminée",

    WorldClassThoughtType.SYNTHESIS_STARTING: "📝 Début de synthèse",
    WorldClassThoughtType.SYNTHESIS_CITING: "📚 Citation des sources",
    WorldClassThoughtType.SYNTHESIS_COMPLETE: "✅ Synthèse terminée",

    WorldClassThoughtType.LLM_CALLING: "🤖 Appel au modèle LLM",
    WorldClassThoughtType.LLM_REASONING: "💭 Raisonnement en cours",
    WorldClassThoughtType.LLM_RESPONSE: "💬 Réponse LLM reçue",
}


class WorldClassRAGMixin:
    """
    Mixin providing World-Class RAG capabilities to any agent

    Features:
    - Unified thought emission for CoT transparency
    - Access to Verification, Reflection, Synthesis agents
    - Consistent logging and debugging
    - Performance tracking

    Requirements:
    - Agent must have a `thought_stream` attribute (can be None)
    - Agent must have a `name` property
    """

    # Reference to thought stream (set by process method)
    _thought_stream: Optional[Any] = None
    _agent_name: str = "unknown_agent"

    def set_thought_stream(self, thought_stream: Optional[Any], agent_name: str = None):
        """
        Initialize thought stream for this processing session

        Args:
            thought_stream: ThoughtStream instance (can be None)
            agent_name: Name of the agent for logging
        """
        self._thought_stream = thought_stream
        if agent_name:
            self._agent_name = agent_name

    async def emit_thought(
        self,
        content: str,
        thought_type: str = "analyzing",
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None,
        agent_override: Optional[str] = None
    ):
        """
        Emit a thought to the CoT stream

        This is the primary method for agents to communicate their reasoning
        to the UI for transparency and debugging.

        Args:
            content: Detailed thought content
            thought_type: Type of thought (string or ThoughtType/WorldClassThoughtType)
            title: Short title (auto-generated if not provided)
            data: Additional structured data
            progress: Progress indicator (0-1)
            agent_override: Override agent name for this thought
        """
        if self._thought_stream is None:
            # Log but don't fail - thoughts are optional
            logger.debug("thought_emitted_no_stream",
                        agent=self._agent_name,
                        type=thought_type,
                        content=content[:50])
            return

        try:
            # Import ThoughtType here to avoid circular imports
            from .thought_stream import ThoughtType

            # Convert string to ThoughtType if needed
            if isinstance(thought_type, str):
                try:
                    thought_type_enum = ThoughtType(thought_type)
                except ValueError:
                    # Use ANALYZING as fallback for custom types
                    thought_type_enum = ThoughtType.ANALYZING
            else:
                thought_type_enum = thought_type

            # Generate title if not provided
            if title is None:
                # Use French labels if available
                if isinstance(thought_type, WorldClassThoughtType):
                    title = WORLD_CLASS_THOUGHT_LABELS_FR.get(thought_type, content[:40])
                else:
                    from .thought_stream import THOUGHT_LABELS_FR
                    title = THOUGHT_LABELS_FR.get(thought_type_enum, content[:40])

            agent_name = agent_override or self._agent_name

            await self._thought_stream.add_thought(
                thought_type=thought_type_enum,
                title=title,
                content=content,
                agent=agent_name,
                data=data,
                progress=progress
            )

            logger.debug("thought_emitted",
                        agent=agent_name,
                        type=str(thought_type),
                        title=title)

        except Exception as e:
            logger.warning("thought_emission_failed",
                          agent=self._agent_name,
                          error=str(e))

    async def emit_llm_reasoning(
        self,
        prompt_preview: str,
        reasoning_type: str = "analysis",
        model: str = "mistral"
    ):
        """
        Emit thought showing LLM reasoning (for debugging)

        Args:
            prompt_preview: First N chars of prompt
            reasoning_type: Type of reasoning being done
            model: Model being used
        """
        await self.emit_thought(
            content=f"Modèle: {model}\nType: {reasoning_type}\nPrompt: {prompt_preview[:100]}...",
            thought_type="analyzing",
            title=f"🤖 Appel LLM ({reasoning_type})",
            data={"model": model, "reasoning_type": reasoning_type}
        )

    async def emit_confidence(
        self,
        confidence: float,
        source: str = "retrieval",
        details: Optional[str] = None
    ):
        """
        Emit confidence score thought

        Args:
            confidence: Confidence score (0-1)
            source: What the confidence is for
            details: Additional details
        """
        # Confidence indicator
        if confidence >= 0.7:
            indicator = "🟢"
            level = "haute"
        elif confidence >= 0.4:
            indicator = "🟡"
            level = "moyenne"
        else:
            indicator = "🔴"
            level = "basse"

        content = f"Confiance {level}: {confidence:.0%}"
        if details:
            content += f"\n{details}"

        await self.emit_thought(
            content=content,
            thought_type="processing",
            title=f"{indicator} Confiance {source}: {confidence:.0%}",
            data={"confidence": confidence, "source": source, "level": level}
        )

    # =========================================================================
    # WORLD-CLASS RAG COMPONENTS
    # =========================================================================

    async def use_query_planning(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Use QueryPlanningAgent to decompose complex queries

        Args:
            query: User query
            context: Optional context

        Returns:
            QueryPlan if complex query, None otherwise
        """
        try:
            from .query_planning_agent import QueryPlanningAgent

            await self.emit_thought(
                content=f"Analyse de la complexité: \"{query[:60]}...\"",
                thought_type="analyzing",
                title="🧩 Analyse de requête",
                progress=0.1
            )

            planner = QueryPlanningAgent()
            plan = await planner.plan_query(query, context)

            if plan.is_complex:
                sub_queries = [sq.query[:40] + "..." for sq in plan.sub_queries[:3]]
                await self.emit_thought(
                    content=f"Requête complexe détectée ({plan.query_type.value}).\n"
                           f"Décomposition en {len(plan.sub_queries)} sous-requêtes:\n" +
                           "\n".join([f"• {sq}" for sq in sub_queries]),
                    thought_type="analyzing",
                    title=f"🧩 {len(plan.sub_queries)} sous-requêtes planifiées",
                    data={
                        "query_type": plan.query_type.value,
                        "sub_queries": len(plan.sub_queries),
                        "strategy": plan.aggregation_strategy.value
                    },
                    progress=0.2
                )
                return plan
            else:
                logger.debug("query_simple_no_decomposition", query=query[:50])
                return None

        except Exception as e:
            logger.warning("query_planning_error", error=str(e))
            return None

    async def use_verification(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        search_func: Callable[[str], Awaitable[List[Dict[str, Any]]]],
        confidence: float
    ) -> List[Dict[str, Any]]:
        """
        Use VerificationAgent to validate and refine results

        Args:
            query: Original query
            chunks: Retrieved chunks
            search_func: Function to re-search if needed
            confidence: Current confidence score

        Returns:
            Verified/refined chunks
        """
        try:
            from .verification_agent import VerificationAgent

            await self.emit_thought(
                content=f"Confiance initiale: {confidence:.0%}\n"
                       f"Vérification que les {len(chunks)} passages répondent à la question...",
                thought_type="analyzing",
                title="🔍 Vérification de pertinence",
                data={"initial_confidence": confidence, "chunks_count": len(chunks)},
                progress=0.5
            )

            verifier = VerificationAgent()
            verified = await verifier.verify_and_refine(
                query=query,
                chunks=chunks,
                rag_search_func=search_func,
                max_iterations=1
            )

            if verified and len(verified) > 0:
                await self.emit_thought(
                    content=f"Vérification terminée: {len(verified)} passages validés",
                    thought_type="processing",
                    title="✅ Vérification OK",
                    progress=0.6
                )
                return verified

            return chunks

        except Exception as e:
            logger.warning("verification_error", error=str(e))
            return chunks

    async def use_reflection(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        search_func: Callable[[str], Awaitable[List[Dict[str, Any]]]],
        confidence: float
    ) -> List[Dict[str, Any]]:
        """
        Use ReflectionAgent to diagnose and fix retrieval failures

        Args:
            query: Original query
            chunks: Low-quality chunks
            search_func: Function to re-search
            confidence: Current confidence score

        Returns:
            Improved chunks or original if no improvement
        """
        try:
            from .reflection_agent import ReflectionAgent

            await self.emit_thought(
                content=f"Confiance faible ({confidence:.0%}).\n"
                       f"Diagnostic du problème de récupération...",
                thought_type="analyzing",
                title="🔄 Réflexion et amélioration",
                data={"confidence": confidence},
                progress=0.55
            )

            reflector = ReflectionAgent()
            result = await reflector.reflect_and_improve(
                query=query,
                low_quality_chunks=chunks,
                search_func=search_func,
                verification_attempts=0
            )

            if result.improved_results and len(result.improved_results) > 0:
                strategy = result.strategy_used.value if result.strategy_used else "none"
                await self.emit_thought(
                    content=f"Stratégie appliquée: {strategy}\n"
                           f"Résultats améliorés: {len(result.improved_results)} passages",
                    thought_type="processing",
                    title=f"✅ Amélioration: {strategy}",
                    data={"strategy": strategy, "new_count": len(result.improved_results)},
                    progress=0.65
                )
                return result.improved_results

            return chunks

        except Exception as e:
            logger.warning("reflection_error", error=str(e))
            return chunks

    async def use_synthesis(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        is_procedural: bool = False
    ) -> Any:
        """
        Use SynthesisAgent to generate response with citations

        Args:
            query: Original query
            chunks: Chunks to synthesize
            is_procedural: Whether this is a procedural (how-to) question

        Returns:
            SynthesizedResponse with citations
        """
        try:
            from .synthesis_agent import SynthesisAgent

            await self.emit_thought(
                content=f"Synthèse de {len(chunks)} passages pour répondre à la question...",
                thought_type="synthesizing",
                title="📝 Synthèse en cours",
                progress=0.7
            )

            synthesizer = SynthesisAgent()
            result = await synthesizer.synthesize_with_citations(
                query=query,
                chunks=chunks,
                is_procedural=is_procedural
            )

            await self.emit_thought(
                content=f"Synthèse terminée avec {len(result.sources)} source(s)\n"
                       f"Confiance: {result.overall_confidence:.0%}",
                thought_type="completed",
                title=f"✅ Synthèse ({result.overall_confidence:.0%})",
                data={
                    "sources_count": len(result.sources),
                    "confidence": result.overall_confidence
                },
                progress=0.9
            )

            return result

        except Exception as e:
            logger.error("synthesis_error", error=str(e))
            raise


# =========================================================================
# CONFIGURATION FLAGS
# =========================================================================

class WorldClassConfig:
    """Configuration for World-Class RAG features"""

    # Feature flags
    ENABLE_QUERY_PLANNING: bool = True
    ENABLE_VERIFICATION: bool = True
    ENABLE_REFLECTION: bool = True

    # Thresholds
    VERIFICATION_THRESHOLD: float = 0.40  # Trigger verification below this
    REFLECTION_THRESHOLD: float = 0.30    # Trigger reflection below this

    # Limits
    MAX_VERIFICATION_ITERATIONS: int = 1
    MAX_REFLECTION_ATTEMPTS: int = 1

    @classmethod
    def from_env(cls) -> "WorldClassConfig":
        """Load configuration from environment variables"""
        import os
        config = cls()

        config.ENABLE_QUERY_PLANNING = os.getenv("ENABLE_QUERY_PLANNING", "true").lower() == "true"
        config.ENABLE_VERIFICATION = os.getenv("ENABLE_VERIFICATION_AGENT", "true").lower() == "true"
        config.ENABLE_REFLECTION = os.getenv("ENABLE_REFLECTION_AGENT", "true").lower() == "true"

        config.VERIFICATION_THRESHOLD = float(os.getenv("VERIFICATION_THRESHOLD", "0.40"))
        config.REFLECTION_THRESHOLD = float(os.getenv("REFLECTION_THRESHOLD", "0.30"))

        return config


# Global configuration instance
world_class_config = WorldClassConfig()
