"""
Parallel Search Service - Exécution parallèle de recherches Multi-Query
Phase RAG World-Class - DisruptIQ SMA

Module isolé pour paralléliser les recherches Multi-Query:
- Exécute les reformulations en parallèle (asyncio.gather)
- Fallback séquentiel si le parallélisme échoue
- Timeout configurable par recherche

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import asyncio
import structlog
from typing import List, Dict, Any, Callable, Awaitable, Optional
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class ParallelSearchResult:
    """Résultat d'une recherche parallèle"""
    all_chunks: List[Dict[str, Any]]
    queries_executed: int
    queries_failed: int
    used_parallel: bool
    total_latency_ms: float


class ParallelSearchService:
    """
    Service de recherche parallèle pour Multi-Query.

    Exécute plusieurs recherches en parallèle avec fallback séquentiel.
    """

    def __init__(
        self,
        timeout_per_query: float = 10.0,  # 10s par requête
        max_concurrent: int = 5           # Max 5 requêtes simultanées
    ):
        self._timeout = timeout_per_query
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def _execute_single_search(
        self,
        query: str,
        search_func: Callable[[str], Awaitable[List[Dict[str, Any]]]]
    ) -> List[Dict[str, Any]]:
        """Exécute une recherche avec semaphore et timeout"""
        async with self._semaphore:
            try:
                return await asyncio.wait_for(
                    search_func(query),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                logger.warning("parallel_search_timeout", query=query[:30])
                return []
            except Exception as e:
                logger.warning("parallel_search_error", query=query[:30], error=str(e))
                return []

    async def search_parallel(
        self,
        queries: List[str],
        search_func: Callable[[str], Awaitable[List[Dict[str, Any]]]]
    ) -> ParallelSearchResult:
        """
        Exécute plusieurs recherches en parallèle.

        Args:
            queries: Liste de requêtes à exécuter
            search_func: Fonction de recherche async (query -> results)

        Returns:
            ParallelSearchResult avec tous les résultats combinés
        """
        import time
        start = time.time()

        if not queries:
            return ParallelSearchResult(
                all_chunks=[],
                queries_executed=0,
                queries_failed=0,
                used_parallel=True,
                total_latency_ms=0.0
            )

        all_chunks = []
        queries_failed = 0
        used_parallel = True

        try:
            # Essayer d'exécuter en parallèle
            tasks = [
                self._execute_single_search(q, search_func)
                for q in queries
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning("parallel_search_exception",
                                 query=queries[i][:30],
                                 error=str(result))
                    queries_failed += 1
                elif result:
                    all_chunks.extend(result)

            logger.info("parallel_search_completed",
                       total_queries=len(queries),
                       failed=queries_failed,
                       total_chunks=len(all_chunks))

        except Exception as e:
            # Fallback séquentiel si le parallélisme échoue complètement
            logger.warning("parallel_search_fallback_sequential", error=str(e))
            used_parallel = False

            for query in queries:
                try:
                    results = await search_func(query)
                    all_chunks.extend(results)
                except Exception as seq_error:
                    logger.warning("sequential_search_error",
                                 query=query[:30],
                                 error=str(seq_error))
                    queries_failed += 1

        latency = (time.time() - start) * 1000

        return ParallelSearchResult(
            all_chunks=all_chunks,
            queries_executed=len(queries),
            queries_failed=queries_failed,
            used_parallel=used_parallel,
            total_latency_ms=latency
        )


# Singleton
_parallel_search: Optional[ParallelSearchService] = None


def get_parallel_search_service() -> ParallelSearchService:
    """Retourne l'instance singleton du Parallel Search Service"""
    global _parallel_search
    if _parallel_search is None:
        _parallel_search = ParallelSearchService()
        logger.info("parallel_search_service_initialized")
    return _parallel_search
