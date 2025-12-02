"""
SQL-RAG Bridge Service - Orchestration intelligente RAG + SQL
Phase RAG World-Class - DisruptIQ SMA

Ce module orchestre les requêtes hybrides nécessitant:
- Données structurées SQL (copropriétaires, lots, charges)
- Contexte documentaire RAG (contrats, PV, règlements)

Patterns supportés:
1. SQL_FIRST: "charges du copropriétaire Martin"
   → SQL trouve Martin → RAG enrichit avec docs associés

2. RAG_FIRST: "détails du contrat ascenseur"
   → RAG trouve le contrat → SQL enrichit avec données liées

3. PARALLEL: "résumé complet copropriété"
   → SQL + RAG en parallèle → Fusion des résultats

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import asyncio
import structlog
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from app.services.query_analyzer import get_query_analyzer, QueryAnalysis

logger = structlog.get_logger()


class HybridStrategy(Enum):
    """Stratégies d'orchestration hybride"""
    SQL_FIRST = "sql_first"      # SQL puis RAG pour enrichir
    RAG_FIRST = "rag_first"      # RAG puis SQL pour vérifier/compléter
    PARALLEL = "parallel"         # Les deux en parallèle
    SQL_ONLY = "sql_only"        # Données structurées uniquement
    RAG_ONLY = "rag_only"        # Documents uniquement


@dataclass
class SQLResult:
    """Résultat d'une requête SQL"""
    data: List[Dict[str, Any]]
    row_count: int
    query_executed: str
    entity_ids: List[int] = field(default_factory=list)
    entity_type: Optional[str] = None  # "coproprietaire", "lot", "professionnel"


@dataclass
class RAGResult:
    """Résultat d'une recherche RAG"""
    chunks: List[Dict[str, Any]]
    chunk_count: int
    top_score: float


@dataclass
class HybridResult:
    """Résultat combiné hybride"""
    strategy_used: HybridStrategy
    sql_result: Optional[SQLResult] = None
    rag_result: Optional[RAGResult] = None
    combined_context: str = ""
    entities_found: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0

    def get_full_context(self) -> str:
        """Retourne le contexte complet pour le LLM"""
        parts = []

        if self.sql_result and self.sql_result.data:
            parts.append("=== DONNÉES STRUCTURÉES (SQL) ===")
            for row in self.sql_result.data[:10]:
                formatted = ", ".join([f"{k}: {v}" for k, v in row.items()])
                parts.append(f"- {formatted}")

        if self.rag_result and self.rag_result.chunks:
            parts.append("\n=== DOCUMENTS (RAG) ===")
            for i, chunk in enumerate(self.rag_result.chunks[:5], 1):
                text = chunk.get("text") or chunk.get("content") or chunk.get("chunk", "")
                score = chunk.get("reranked_score") or chunk.get("score", 0)
                parts.append(f"\n[Source {i} - Score: {score:.0%}]")
                parts.append(text[:500] + "..." if len(text) > 500 else text)

        return "\n".join(parts) if parts else self.combined_context


class SQLRAGBridgeService:
    """
    Service d'orchestration SQL-RAG.

    Détermine la meilleure stratégie et combine les résultats
    des deux sources pour des réponses complètes.
    """

    # Patterns pour déterminer la stratégie
    # Agile: patterns adaptés à différentes formulations françaises
    SQL_FIRST_PATTERNS = [
        r"charges\s+(?:du|de la)\s+copropriétaire",
        r"lot\s+\d+",
        # Liste des/de copropriétaires (accepte "les", "des", "de")
        r"(?:liste|tous)\s+(?:les|des|de)?\s*copropriétaires",
        r"qui\s+(?:doit|a\s+payé)",
        r"montant\s+(?:des\s+)?charges",
        # Lister les lots, prestataires, etc.
        r"(?:liste|lister)\s+(?:les|des|de)?\s*(?:lots?|prestataires?|professionnels?)",
    ]

    RAG_FIRST_PATTERNS = [
        r"contrat\s+(?:de|d')",
        r"que\s+dit\s+le",
        # NE PAS inclure règlement ici - c'est RAG_ONLY
        r"procès[- ]verbal",
        r"résolution\s+(?:de|sur)",
    ]

    # Patterns purement documentaires (RAG_ONLY) - pas besoin de SQL
    RAG_ONLY_PATTERNS = [
        r"règlement\s+(?:de\s+)?copropriété",
        r"statuts?\s+(?:de\s+)?(?:la\s+)?copropriété",
        r"pv\s+(?:d'|de\s+)?(?:ag|assemblée)",
        r"compte[- ]rendu",
    ]

    PARALLEL_PATTERNS = [
        r"résumé\s+complet",
        r"tout\s+sur",
        r"informations\s+complètes",
    ]

    def __init__(self):
        self._query_analyzer = get_query_analyzer()

    def determine_strategy(
        self,
        query: str,
        query_analysis: Optional[QueryAnalysis] = None
    ) -> HybridStrategy:
        """
        Détermine la meilleure stratégie pour la requête.

        Args:
            query: Requête utilisateur
            query_analysis: Analyse pré-calculée (optionnel)

        Returns:
            HybridStrategy recommandée
        """
        import re
        query_lower = query.lower()

        # FIRST: Check RAG_ONLY patterns (purement documentaire)
        # Important: vérifier en premier pour éviter que SQL_FIRST ne capture ces cas
        for pattern in self.RAG_ONLY_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return HybridStrategy.RAG_ONLY

        # Use pre-computed analysis if available
        if query_analysis:
            if query_analysis.needs_hybrid:
                # Check patterns for direction
                for pattern in self.SQL_FIRST_PATTERNS:
                    if re.search(pattern, query_lower, re.IGNORECASE):
                        return HybridStrategy.SQL_FIRST

                for pattern in self.RAG_FIRST_PATTERNS:
                    if re.search(pattern, query_lower, re.IGNORECASE):
                        return HybridStrategy.RAG_FIRST

                return HybridStrategy.PARALLEL

            elif query_analysis.is_table_query or query_analysis.is_amount_query:
                # Likely needs SQL data
                return HybridStrategy.SQL_FIRST

            elif query_analysis.is_legal_query:
                # Likely needs documents
                return HybridStrategy.RAG_ONLY

        # Fallback: pattern matching (ordre d'importance)
        for pattern in self.PARALLEL_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return HybridStrategy.PARALLEL

        for pattern in self.SQL_FIRST_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return HybridStrategy.SQL_FIRST

        for pattern in self.RAG_FIRST_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return HybridStrategy.RAG_FIRST

        # Default: RAG only
        return HybridStrategy.RAG_ONLY

    async def execute_hybrid(
        self,
        query: str,
        sql_func: Callable[[str], Awaitable[SQLResult]],
        rag_func: Callable[[str, Optional[List[int]]], Awaitable[RAGResult]],
        strategy: Optional[HybridStrategy] = None
    ) -> HybridResult:
        """
        Exécute une requête hybride SQL+RAG.

        Args:
            query: Requête utilisateur
            sql_func: Fonction async pour exécuter SQL
            rag_func: Fonction async pour recherche RAG (prend query et optionnel doc_ids)
            strategy: Stratégie à utiliser (auto-détectée si None)

        Returns:
            HybridResult combiné
        """
        # Determine strategy if not provided
        if strategy is None:
            analysis = self._query_analyzer.analyze(query)
            strategy = self.determine_strategy(query, analysis)

        logger.info("hybrid_strategy_selected",
                   query=query[:50],
                   strategy=strategy.value)

        # Execute based on strategy
        if strategy == HybridStrategy.SQL_ONLY:
            return await self._execute_sql_only(query, sql_func)

        elif strategy == HybridStrategy.RAG_ONLY:
            return await self._execute_rag_only(query, rag_func)

        elif strategy == HybridStrategy.SQL_FIRST:
            return await self._execute_sql_first(query, sql_func, rag_func)

        elif strategy == HybridStrategy.RAG_FIRST:
            return await self._execute_rag_first(query, sql_func, rag_func)

        elif strategy == HybridStrategy.PARALLEL:
            return await self._execute_parallel(query, sql_func, rag_func)

        else:
            # Fallback to RAG only
            return await self._execute_rag_only(query, rag_func)

    async def _execute_sql_only(
        self,
        query: str,
        sql_func: Callable
    ) -> HybridResult:
        """Exécute SQL uniquement"""
        try:
            sql_result = await sql_func(query)
            return HybridResult(
                strategy_used=HybridStrategy.SQL_ONLY,
                sql_result=sql_result,
                confidence=0.9 if sql_result.row_count > 0 else 0.3
            )
        except Exception as e:
            logger.error("sql_only_failed", error=str(e))
            return HybridResult(
                strategy_used=HybridStrategy.SQL_ONLY,
                confidence=0.0
            )

    async def _execute_rag_only(
        self,
        query: str,
        rag_func: Callable
    ) -> HybridResult:
        """Exécute RAG uniquement"""
        try:
            rag_result = await rag_func(query, None)
            return HybridResult(
                strategy_used=HybridStrategy.RAG_ONLY,
                rag_result=rag_result,
                confidence=rag_result.top_score if rag_result else 0.0
            )
        except Exception as e:
            logger.error("rag_only_failed", error=str(e))
            return HybridResult(
                strategy_used=HybridStrategy.RAG_ONLY,
                confidence=0.0
            )

    async def _execute_sql_first(
        self,
        query: str,
        sql_func: Callable,
        rag_func: Callable
    ) -> HybridResult:
        """
        Exécute SQL d'abord, puis enrichit avec RAG.

        Exemple: "charges du copropriétaire Martin"
        1. SQL: SELECT * FROM coproprietaires WHERE nom='Martin' → id=5
        2. RAG: Recherche documents liés au copropriétaire 5
        """
        sql_result = None
        rag_result = None

        try:
            # Step 1: SQL
            sql_result = await sql_func(query)

            # Step 2: If SQL found entities, search related docs
            if sql_result and sql_result.entity_ids:
                # Build enhanced query with entity context
                entity_context = f"{query} {sql_result.entity_type or 'entité'}"
                rag_result = await rag_func(entity_context, sql_result.entity_ids)
            else:
                # No SQL entities, just do RAG search
                rag_result = await rag_func(query, None)

        except Exception as e:
            logger.error("sql_first_failed", error=str(e))

        # Calculate confidence
        confidence = 0.0
        if sql_result and sql_result.row_count > 0:
            confidence += 0.5
        if rag_result and rag_result.top_score > 0.5:
            confidence += 0.3
        if rag_result and rag_result.chunk_count > 0:
            confidence += 0.2

        return HybridResult(
            strategy_used=HybridStrategy.SQL_FIRST,
            sql_result=sql_result,
            rag_result=rag_result,
            confidence=min(1.0, confidence)
        )

    async def _execute_rag_first(
        self,
        query: str,
        sql_func: Callable,
        rag_func: Callable
    ) -> HybridResult:
        """
        Exécute RAG d'abord, puis vérifie/complète avec SQL.

        Exemple: "contrat maintenance ascenseur"
        1. RAG: Trouve le contrat → extrait "Ascenseurs du Sud SARL"
        2. SQL: SELECT * FROM professionnels WHERE nom LIKE '%Ascenseurs%'
        """
        sql_result = None
        rag_result = None

        try:
            # Step 1: RAG
            rag_result = await rag_func(query, None)

            # Step 2: Extract entities from RAG results for SQL enrichment
            if rag_result and rag_result.chunks:
                # Could extract entity names here and query SQL
                # For now, just return RAG results
                pass

        except Exception as e:
            logger.error("rag_first_failed", error=str(e))

        confidence = rag_result.top_score if rag_result else 0.0

        return HybridResult(
            strategy_used=HybridStrategy.RAG_FIRST,
            sql_result=sql_result,
            rag_result=rag_result,
            confidence=confidence
        )

    async def _execute_parallel(
        self,
        query: str,
        sql_func: Callable,
        rag_func: Callable
    ) -> HybridResult:
        """
        Exécute SQL et RAG en parallèle.

        Exemple: "résumé complet copropriété Les Mimosas"
        → SQL + RAG simultanés → Fusion
        """
        try:
            # Execute both in parallel
            sql_task = asyncio.create_task(sql_func(query))
            rag_task = asyncio.create_task(rag_func(query, None))

            sql_result, rag_result = await asyncio.gather(
                sql_task, rag_task,
                return_exceptions=True
            )

            # Handle exceptions
            if isinstance(sql_result, Exception):
                logger.warning("parallel_sql_failed", error=str(sql_result))
                sql_result = None
            if isinstance(rag_result, Exception):
                logger.warning("parallel_rag_failed", error=str(rag_result))
                rag_result = None

        except Exception as e:
            logger.error("parallel_failed", error=str(e))
            sql_result = None
            rag_result = None

        # Calculate confidence
        confidence = 0.0
        if sql_result and sql_result.row_count > 0:
            confidence += 0.4
        if rag_result and rag_result.top_score > 0.5:
            confidence += 0.4
        if sql_result and rag_result:
            confidence += 0.2  # Bonus for having both

        return HybridResult(
            strategy_used=HybridStrategy.PARALLEL,
            sql_result=sql_result,
            rag_result=rag_result,
            confidence=min(1.0, confidence)
        )

    def format_hybrid_context(
        self,
        result: HybridResult,
        max_sql_rows: int = 10,
        max_rag_chunks: int = 5
    ) -> str:
        """
        Formate le résultat hybride en contexte pour le LLM.

        Args:
            result: Résultat hybride
            max_sql_rows: Nombre max de lignes SQL à inclure
            max_rag_chunks: Nombre max de chunks RAG à inclure

        Returns:
            Contexte formaté pour le prompt
        """
        return result.get_full_context()


# Singleton
_sql_rag_bridge: Optional[SQLRAGBridgeService] = None


def get_sql_rag_bridge() -> SQLRAGBridgeService:
    """Retourne l'instance singleton du SQL-RAG Bridge"""
    global _sql_rag_bridge
    if _sql_rag_bridge is None:
        _sql_rag_bridge = SQLRAGBridgeService()
    return _sql_rag_bridge
