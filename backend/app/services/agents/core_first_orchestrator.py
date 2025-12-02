"""
Core-First Orchestrator - Pipeline simplifié SQL+RAG avec suggestions contextuelles
Phase Core-First - DisruptIQ SMA

Architecture validée:
1. TOUTE requête → Core (SQL + RAG en parallèle) par défaut
2. Short-circuit Legal/Web UNIQUEMENT si:
   - pure_legal/pure_web == True
   - confidence >= 0.85
   - AUCUNE entité métier détectée
3. Suggestions contextuelles (one-shot, non persistantes)
4. Follow-up via process_action() séparé

INVARIANTS:
- Jamais de mode "4 sources automatiques"
- Jamais de persistance de mode (pas de checkbox)
- Jamais de /legal ou /web en UI
- Suggestions = boutons métier ("Consulter la loi", "Prix du marché")

Author: Claude Code - Core-First Architecture
Date: December 2024
"""

import asyncio
import structlog
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass

from app.models.intent import AgentResponse, FollowUpSuggestion, DataSource
from app.services.query_analyzer import get_query_analyzer, QueryAnalysis

logger = structlog.get_logger()


@dataclass
class CoreExecutionResult:
    """Résultat de l'exécution Core (SQL + RAG)"""
    sql_results: Dict[str, Any]
    rag_results: Dict[str, Any]
    has_sql_data: bool
    has_rag_data: bool
    latency_ms: float


class CoreFirstOrchestrator:
    """
    Orchestrateur Core-First pour DisruptIQ.

    Pipeline:
    1. QueryAnalyzer → Analyse + scores
    2. Pre-routing → Short-circuit rare (pure_legal/pure_web)
    3. Core Execution → SQL + RAG en parallèle
    4. Synthesis → Fusion des résultats
    5. Suggestions → Boutons contextuels (Legal/Web)
    """

    def __init__(
        self,
        sql_agent,
        rag_service,
        synthesis_agent,
        legal_agent=None,
        web_agent=None,
        thought_callback: Optional[Callable[[str, str, Dict], Awaitable[None]]] = None
    ):
        """
        Args:
            sql_agent: Agent SQL pour requêtes BDD
            rag_service: Service RAG pour recherche documentaire
            synthesis_agent: Agent de synthèse pour fusion SQL+RAG
            legal_agent: Agent Légifrance (optionnel, pour follow-ups)
            web_agent: Agent Web Search (optionnel, pour follow-ups)
            thought_callback: Callback pour streaming des thoughts
        """
        self._sql_agent = sql_agent
        self._rag_service = rag_service
        self._synthesis_agent = synthesis_agent
        self._legal_agent = legal_agent
        self._web_agent = web_agent
        self._thought_callback = thought_callback
        self._query_analyzer = get_query_analyzer()

    async def _emit_thought(self, thought_type: str, agent: str, data: Dict[str, Any]):
        """Émet un thought pour le streaming UI"""
        if self._thought_callback:
            await self._thought_callback(thought_type, agent, data)

    async def process_query(
        self,
        query: str,
        context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]] = None,
        db = None,
        session_id: str = None
    ) -> AgentResponse:
        """
        Pipeline principal Core-First.

        1. Analyse la requête (QueryAnalyzer avec scores)
        2. Short-circuit si pure_legal/pure_web (rare)
        3. Exécute TOUJOURS SQL + RAG en parallèle (Core)
        4. Synthèse avec SynthesisAgent
        5. Génère suggestions contextuelles (Legal/Web)

        Args:
            query: Requête utilisateur
            context: Contexte de conversation (entities, topic, etc.)
            conversation_history: Historique des messages
            db: Session base de données
            session_id: ID de session pour le contexte

        Returns:
            AgentResponse avec core_answer + structured_suggestions
        """
        import time
        start_time = time.time()

        conversation_history = conversation_history or []

        # ══════════════════════════════════════════════════════════════
        # ÉTAPE 1: ANALYSE DE LA REQUÊTE
        # ══════════════════════════════════════════════════════════════
        await self._emit_thought("analyzing", "core_first", {"query": query[:50]})

        analysis = self._query_analyzer.analyze(query)

        logger.info("core_first_analysis",
                   query=query[:50],
                   legal_conf=f"{analysis.legal_confidence:.0%}",
                   web_conf=f"{analysis.web_confidence:.0%}",
                   pure_legal=analysis.pure_legal_query,
                   pure_web=analysis.pure_web_query,
                   has_biz_entities=analysis.has_business_entities)

        # ══════════════════════════════════════════════════════════════
        # ÉTAPE 2: SHORT-CIRCUIT (RARE - uniquement si pure_legal/pure_web)
        # ══════════════════════════════════════════════════════════════
        if analysis.should_shortcircuit_legal and self._legal_agent:
            await self._emit_thought("shortcircuit", "legal", {
                "reason": "Requête purement légale sans entité métier",
                "confidence": analysis.legal_confidence
            })
            logger.info("core_first_shortcircuit_legal", query=query[:50])
            return await self._execute_legal_only(query, context, db)

        if analysis.should_shortcircuit_web and self._web_agent:
            await self._emit_thought("shortcircuit", "web", {
                "reason": "Requête purement web sans entité métier",
                "confidence": analysis.web_confidence
            })
            logger.info("core_first_shortcircuit_web", query=query[:50])
            return await self._execute_web_only(query, context)

        # ══════════════════════════════════════════════════════════════
        # ÉTAPE 3: CORE EXECUTION (SQL + RAG en parallèle)
        # ══════════════════════════════════════════════════════════════
        await self._emit_thought("core_execution", "core_first", {
            "sources": ["sql", "rag"],
            "parallel": True
        })

        core_result = await self._execute_core(query, context, db, analysis)

        # ══════════════════════════════════════════════════════════════
        # ÉTAPE 4: SYNTHÈSE
        # ══════════════════════════════════════════════════════════════
        await self._emit_thought("synthesis", "synthesis_agent", {
            "has_sql": core_result.has_sql_data,
            "has_rag": core_result.has_rag_data
        })

        core_answer = await self._synthesize_core_answer(
            query=query,
            sql_results=core_result.sql_results,
            rag_results=core_result.rag_results,
            context=context,
            conversation_history=conversation_history
        )

        # ══════════════════════════════════════════════════════════════
        # ÉTAPE 5: SUGGESTIONS CONTEXTUELLES (one-shot, non persistantes)
        # ══════════════════════════════════════════════════════════════
        suggestions = self._generate_followup_suggestions(
            query=query,
            analysis=analysis,
            core_answer=core_answer,
            core_result=core_result
        )

        latency_ms = (time.time() - start_time) * 1000

        # Construire la réponse finale
        sources_used = []
        if core_result.has_sql_data:
            sources_used.append(DataSource.SQL)
        if core_result.has_rag_data:
            sources_used.append(DataSource.RAG)

        response = AgentResponse(
            success=True,
            message=core_answer,
            data={
                "sources_used": [s.value for s in sources_used],
                "sql_data": core_result.sql_results if core_result.has_sql_data else None,
                "rag_data": core_result.rag_results if core_result.has_rag_data else None,
                "analysis": {
                    "legal_confidence": analysis.legal_confidence,
                    "web_confidence": analysis.web_confidence,
                    "pure_legal": analysis.pure_legal_query,
                    "pure_web": analysis.pure_web_query,
                    "complexity": analysis.complexity.value
                },
                "latency_ms": latency_ms
            },
            agents_used=["core_first_orchestrator", "sql_agent", "rag_service", "synthesis_agent"],
            sources_used=sources_used,
            confidence=analysis.confidence,
            structured_suggestions=suggestions
        )

        logger.info("core_first_completed",
                   query=query[:50],
                   sources=[s.value for s in sources_used],
                   suggestions_count=len(suggestions),
                   latency_ms=f"{latency_ms:.0f}")

        return response

    async def _execute_core(
        self,
        query: str,
        context: Dict[str, Any],
        db,
        analysis: QueryAnalysis
    ) -> CoreExecutionResult:
        """
        Exécute SQL + RAG en parallèle (Core).

        C'est le coeur du système - toujours exécuté sauf short-circuit.
        """
        import time
        start = time.time()

        # Exécuter en parallèle
        sql_task = self._execute_sql(query, context, db)
        rag_task = self._execute_rag(query, context, analysis)

        sql_results, rag_results = await asyncio.gather(
            sql_task, rag_task, return_exceptions=True
        )

        # Gérer les erreurs
        if isinstance(sql_results, Exception):
            logger.warning("core_sql_error", error=str(sql_results))
            sql_results = {}
        if isinstance(rag_results, Exception):
            logger.warning("core_rag_error", error=str(rag_results))
            rag_results = {}

        latency = (time.time() - start) * 1000

        return CoreExecutionResult(
            sql_results=sql_results or {},
            rag_results=rag_results or {},
            has_sql_data=bool(sql_results and sql_results.get("results")),
            has_rag_data=bool(rag_results and rag_results.get("chunks")),
            latency_ms=latency
        )

    async def _execute_sql(self, query: str, context: Dict[str, Any], db) -> Dict[str, Any]:
        """Exécute la recherche SQL"""
        try:
            if not self._sql_agent or not db:
                return {}

            await self._emit_thought("executing", "sql_agent", {"query": query[:50]})

            # Appeler l'agent SQL
            result = await self._sql_agent.execute_natural_query(
                query=query,
                db=db,
                context=context
            )

            if result and result.success:
                return {
                    "results": result.data.get("results", []) if result.data else [],
                    "query_used": result.data.get("sql_query", "") if result.data else "",
                    "row_count": result.data.get("row_count", 0) if result.data else 0
                }
            return {}

        except Exception as e:
            logger.warning("sql_execution_error", error=str(e))
            return {}

    async def _execute_rag(self, query: str, context: Dict[str, Any], analysis: QueryAnalysis) -> Dict[str, Any]:
        """Exécute la recherche RAG"""
        try:
            if not self._rag_service:
                return {}

            await self._emit_thought("executing", "rag_service", {"query": query[:50]})

            # Déterminer le nombre de chunks basé sur la complexité
            limit = 30 if analysis.needs_extended_retrieval else 15

            # Appeler le service RAG
            chunks = await self._rag_service.search(
                query=query,
                limit=limit,
                document_ids=context.get("active_document_ids")
            )

            if chunks:
                return {
                    "chunks": chunks,
                    "chunk_count": len(chunks)
                }
            return {}

        except Exception as e:
            logger.warning("rag_execution_error", error=str(e))
            return {}

    async def _synthesize_core_answer(
        self,
        query: str,
        sql_results: Dict[str, Any],
        rag_results: Dict[str, Any],
        context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Synthétise la réponse Core à partir de SQL + RAG"""
        try:
            if not self._synthesis_agent:
                # Fallback simple si pas de synthesis agent
                parts = []
                if sql_results.get("results"):
                    parts.append(f"Données trouvées: {len(sql_results['results'])} résultats")
                if rag_results.get("chunks"):
                    parts.append(f"Documents trouvés: {len(rag_results['chunks'])} extraits")
                return "\n".join(parts) if parts else "Aucune donnée trouvée."

            # Appeler le synthesis agent
            result = await self._synthesis_agent.synthesize(
                query=query,
                sql_data=sql_results,
                rag_data=rag_results,
                context=context,
                conversation_history=conversation_history
            )

            return result.message if result else "Synthèse non disponible."

        except Exception as e:
            logger.warning("synthesis_error", error=str(e))
            return f"Erreur lors de la synthèse: {str(e)}"

    def _generate_followup_suggestions(
        self,
        query: str,
        analysis: QueryAnalysis,
        core_answer: str,
        core_result: CoreExecutionResult
    ) -> List[FollowUpSuggestion]:
        """
        Génère les suggestions de follow-up (Legal/Web).

        Ces suggestions sont:
        - Contextuelles (basées sur l'analyse)
        - One-shot (pas de persistance)
        - Métier (pas de termes techniques)
        """
        suggestions = []

        # ══════════════════════════════════════════════════════════════
        # SUGGESTION LEGAL
        # ══════════════════════════════════════════════════════════════
        if self._should_suggest_legal(analysis, core_answer, core_result):
            priority = "high" if analysis.legal_confidence > 0.7 else "normal"
            reason = self._get_legal_reason(analysis)

            suggestions.append(FollowUpSuggestion(
                id="legal_followup",
                icon="⚖️",
                label="Consulter la loi",
                action="legal_lookup",
                priority=priority,
                reason=reason,
                payload={"original_query": query}
            ))

        # ══════════════════════════════════════════════════════════════
        # SUGGESTION WEB
        # ══════════════════════════════════════════════════════════════
        if self._should_suggest_web(analysis, core_answer, core_result):
            priority = "high" if analysis.web_confidence > 0.7 else "normal"
            reason = self._get_web_reason(analysis)

            suggestions.append(FollowUpSuggestion(
                id="web_followup",
                icon="🌐",
                label="Rechercher les prix actuels",
                action="web_search",
                priority=priority,
                reason=reason,
                payload={"original_query": query}
            ))

        return suggestions

    def _should_suggest_legal(
        self,
        analysis: QueryAnalysis,
        core_answer: str,
        core_result: CoreExecutionResult
    ) -> bool:
        """Détermine si on doit suggérer Legal"""
        # Ne pas suggérer si déjà shortcircuité
        if analysis.should_shortcircuit_legal:
            return False

        # Suggérer si confiance Legal modérée
        if analysis.legal_confidence >= 0.5:
            return True

        # Suggérer si la question est légale mais les docs internes n'ont pas la réponse
        if analysis.is_legal_query and not core_result.has_rag_data:
            return True

        # Suggérer si mention de majorité/article sans réponse légale dans core
        legal_keywords = ["majorité", "article", "loi", "code civil"]
        if any(kw in analysis.original_query.lower() for kw in legal_keywords):
            if not any(kw in core_answer.lower() for kw in ["article", "loi de 1965", "majorité"]):
                return True

        return False

    def _should_suggest_web(
        self,
        analysis: QueryAnalysis,
        core_answer: str,
        core_result: CoreExecutionResult
    ) -> bool:
        """Détermine si on doit suggérer Web"""
        # Ne pas suggérer si déjà shortcircuité
        if analysis.should_shortcircuit_web:
            return False

        # Suggérer si confiance Web modérée
        if analysis.web_confidence >= 0.5:
            return True

        # Suggérer si la question concerne des prix/tarifs et pas de données récentes
        price_keywords = ["prix", "tarif", "coût", "combien", "devis"]
        if any(kw in analysis.original_query.lower() for kw in price_keywords):
            # Si la réponse mentionne des prix anciens ou pas de prix
            if "2024" not in core_answer and "2025" not in core_answer:
                return True

        return False

    def _get_legal_reason(self, analysis: QueryAnalysis) -> str:
        """Génère une explication pour la suggestion Legal"""
        if analysis.legal_confidence > 0.7:
            return "Votre question semble concerner la loi de copropriété"
        elif analysis.is_legal_query:
            return "Je peux vérifier ce que dit la loi sur ce point"
        else:
            return "Complément juridique disponible"

    def _get_web_reason(self, analysis: QueryAnalysis) -> str:
        """Génère une explication pour la suggestion Web"""
        if analysis.web_confidence > 0.7:
            return "Je peux rechercher les prix actuels du marché"
        elif "prix" in analysis.original_query.lower():
            return "Comparaison avec les prix du marché disponible"
        else:
            return "Informations web actualisées disponibles"

    async def _execute_legal_only(
        self,
        query: str,
        context: Dict[str, Any],
        db
    ) -> AgentResponse:
        """Exécute uniquement Legal (short-circuit rare)"""
        try:
            result = await self._legal_agent.process(
                query=query,
                context=context,
                db=db
            )
            if result:
                result.agents_used = ["core_first_orchestrator", "legal_agent"]
                return result
        except Exception as e:
            logger.warning("legal_shortcircuit_error", error=str(e))

        return AgentResponse(
            success=False,
            message="Erreur lors de la recherche légale",
            agents_used=["core_first_orchestrator"]
        )

    async def _execute_web_only(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> AgentResponse:
        """Exécute uniquement Web (short-circuit rare)"""
        try:
            result = await self._web_agent.search(query=query)
            if result:
                return AgentResponse(
                    success=True,
                    message=result.get("summary", "Recherche web effectuée"),
                    data=result,
                    agents_used=["core_first_orchestrator", "web_agent"],
                    sources_used=[DataSource.WEB]
                )
        except Exception as e:
            logger.warning("web_shortcircuit_error", error=str(e))

        return AgentResponse(
            success=False,
            message="Erreur lors de la recherche web",
            agents_used=["core_first_orchestrator"]
        )

    async def process_action(
        self,
        action: str,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        db = None
    ) -> AgentResponse:
        """
        Traite une action de follow-up (clic sur bouton suggestion).

        Appelé quand l'utilisateur clique sur:
        - ⚖️ "Consulter la loi" → action="legal_lookup"
        - 🌐 "Rechercher les prix" → action="web_search"

        C'est un call séparé, one-shot, sans modifier l'état global.

        Args:
            action: Type d'action ("legal_lookup" | "web_search")
            payload: Données de l'action (original_query, etc.)
            context: Contexte actuel
            db: Session BDD

        Returns:
            AgentResponse avec le résultat de l'action
        """
        original_query = payload.get("original_query", "")

        if action == "legal_lookup":
            if not self._legal_agent:
                return AgentResponse(
                    success=False,
                    message="Agent légal non disponible",
                    agents_used=["core_first_orchestrator"]
                )

            await self._emit_thought("followup", "legal_agent", {
                "action": "legal_lookup",
                "query": original_query[:50]
            })

            return await self._execute_legal_only(original_query, context, db)

        elif action == "web_search":
            if not self._web_agent:
                return AgentResponse(
                    success=False,
                    message="Agent web non disponible",
                    agents_used=["core_first_orchestrator"]
                )

            await self._emit_thought("followup", "web_agent", {
                "action": "web_search",
                "query": original_query[:50]
            })

            return await self._execute_web_only(original_query, context)

        else:
            return AgentResponse(
                success=False,
                message=f"Action inconnue: {action}",
                agents_used=["core_first_orchestrator"]
            )


# Singleton
_core_first_orchestrator: Optional[CoreFirstOrchestrator] = None


def get_core_first_orchestrator() -> Optional[CoreFirstOrchestrator]:
    """Retourne l'instance singleton du CoreFirstOrchestrator"""
    global _core_first_orchestrator
    return _core_first_orchestrator


def init_core_first_orchestrator(
    sql_agent,
    rag_service,
    synthesis_agent,
    legal_agent=None,
    web_agent=None,
    thought_callback=None
) -> CoreFirstOrchestrator:
    """Initialise le singleton CoreFirstOrchestrator"""
    global _core_first_orchestrator
    _core_first_orchestrator = CoreFirstOrchestrator(
        sql_agent=sql_agent,
        rag_service=rag_service,
        synthesis_agent=synthesis_agent,
        legal_agent=legal_agent,
        web_agent=web_agent,
        thought_callback=thought_callback
    )
    logger.info("core_first_orchestrator_initialized")
    return _core_first_orchestrator
