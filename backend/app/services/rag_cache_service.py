"""
RAG Cache Service - Cache des résultats de recherche RAG
Phase RAG World-Class - DisruptIQ SMA

Cache LRU simple pour éviter de refaire les mêmes recherches:
- Clé: hash(query + limit + document_ids)
- TTL: 5 minutes (configurable)
- Max: 100 entrées

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import hashlib
import time
import structlog
from typing import List, Dict, Any, Optional, Tuple
from collections import OrderedDict
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class CacheEntry:
    """Entrée de cache avec TTL"""
    results: List[Dict[str, Any]]
    created_at: float
    hit_count: int = 0


class RAGCacheService:
    """
    Cache LRU pour les résultats de recherche RAG.

    Évite de refaire les mêmes recherches coûteuses (embedding + reranking).
    """

    def __init__(
        self,
        max_entries: int = 100,
        ttl_seconds: float = 300.0  # 5 minutes
    ):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _make_key(
        self,
        query: str,
        limit: int,
        document_ids: Optional[List[int]] = None
    ) -> str:
        """Génère une clé de cache unique"""
        key_data = f"{query}|{limit}"
        if document_ids:
            key_data += f"|{sorted(document_ids)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(
        self,
        query: str,
        limit: int,
        document_ids: Optional[List[int]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Récupère des résultats du cache.

        Args:
            query: Requête de recherche
            limit: Nombre de résultats demandés
            document_ids: IDs de documents (filter)

        Returns:
            Résultats cachés ou None si non trouvé/expiré
        """
        key = self._make_key(query, limit, document_ids)

        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Vérifier TTL
        if time.time() - entry.created_at > self._ttl_seconds:
            # Expiré, supprimer
            del self._cache[key]
            self._misses += 1
            logger.debug("rag_cache_expired", query=query[:30])
            return None

        # Cache hit - move to end (LRU)
        self._cache.move_to_end(key)
        entry.hit_count += 1
        self._hits += 1

        logger.info("rag_cache_hit",
                   query=query[:30],
                   hit_count=entry.hit_count,
                   cache_size=len(self._cache))

        return entry.results

    def set(
        self,
        query: str,
        limit: int,
        results: List[Dict[str, Any]],
        document_ids: Optional[List[int]] = None
    ) -> None:
        """
        Stocke des résultats dans le cache.

        Args:
            query: Requête de recherche
            limit: Nombre de résultats demandés
            results: Résultats à cacher
            document_ids: IDs de documents (filter)
        """
        key = self._make_key(query, limit, document_ids)

        # Éviction LRU si nécessaire
        while len(self._cache) >= self._max_entries:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug("rag_cache_evicted", key=oldest_key[:8])

        self._cache[key] = CacheEntry(
            results=results,
            created_at=time.time()
        )

        logger.debug("rag_cache_set",
                    query=query[:30],
                    results_count=len(results))

    def invalidate(self, document_id: Optional[int] = None) -> int:
        """
        Invalide le cache (tout ou par document).

        Args:
            document_id: Si fourni, invalide uniquement les entrées
                        contenant ce document

        Returns:
            Nombre d'entrées invalidées
        """
        if document_id is None:
            count = len(self._cache)
            self._cache.clear()
            logger.info("rag_cache_cleared", entries_removed=count)
            return count

        # Invalider par document_id
        keys_to_remove = []
        for key, entry in self._cache.items():
            for result in entry.results:
                if result.get("document_id") == document_id:
                    keys_to_remove.append(key)
                    break

        for key in keys_to_remove:
            del self._cache[key]

        if keys_to_remove:
            logger.info("rag_cache_invalidated_by_doc",
                       document_id=document_id,
                       entries_removed=len(keys_to_remove))

        return len(keys_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self._max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
            "ttl_seconds": self._ttl_seconds
        }


# Singleton
_rag_cache: Optional[RAGCacheService] = None


def get_rag_cache() -> RAGCacheService:
    """Retourne l'instance singleton du RAG Cache"""
    global _rag_cache
    if _rag_cache is None:
        _rag_cache = RAGCacheService()
        logger.info("rag_cache_service_initialized")
    return _rag_cache
