"""
Web Search Agent - Recherche web avec cache TTL

Service de recherche web pour enrichir les réponses RAG avec:
- Recherche via API (Serper, Bing, Google)
- Cache TTL court (1h) pour limiter appels API
- Citation URLs obligatoire
- Intégration comme source secondaire HYBRID
"""

import structlog
import httpx
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime, timedelta
import hashlib
import json

logger = structlog.get_logger()


class SearchResult(BaseModel):
    """Résultat de recherche web"""
    title: str
    url: HttpUrl
    snippet: str
    position: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebSearchResponse(BaseModel):
    """Réponse de recherche web"""
    query: str
    results: List[SearchResult] = []
    total_results: int = 0
    cached: bool = False
    cache_expires_at: Optional[datetime] = None
    api_provider: str = "serper"  # serper, bing, google
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebSearchAgent:
    """
    Web Search Agent with cache.

    Features:
    - Search via API (Serper by default, fallback to mock)
    - Cache results with TTL (default 1h)
    - Extract and format snippets
    - Generate citations with URLs

    Usage:
    ```python
    agent = WebSearchAgent(api_key="...", cache_ttl_seconds=3600)
    response = await agent.search("jurisprudence copropriété")
    # Returns WebSearchResponse with results + citations
    ```
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_ttl_seconds: int = 3600,  # 1 hour
        max_results: int = 10
    ):
        """
        Initialize Web Search Agent

        Args:
            api_key: API key for search provider (Serper, Bing, etc.)
            cache_ttl_seconds: Cache TTL in seconds (default 3600 = 1h)
            max_results: Maximum results to return
        """
        self.api_key = api_key or self._get_api_key_from_env()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_results = max_results

        # In-memory cache (TODO: use Redis for production)
        self._cache: Dict[str, tuple[WebSearchResponse, datetime]] = {}

        logger.info(
            "web_search_agent_initialized",
            cache_ttl_seconds=cache_ttl_seconds,
            max_results=max_results,
            has_api_key=self.api_key is not None
        )

    def _get_api_key_from_env(self) -> Optional[str]:
        """Get API key from environment"""
        import os
        return os.getenv("SERPER_API_KEY") or os.getenv("BING_SEARCH_API_KEY")

    def _generate_cache_key(self, query: str, **kwargs) -> str:
        """Generate cache key from query + params"""
        cache_input = f"{query}|{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(cache_input.encode()).hexdigest()

    def _is_cache_valid(self, cached_at: datetime) -> bool:
        """Check if cache is still valid"""
        expiration = cached_at + timedelta(seconds=self.cache_ttl_seconds)
        return datetime.utcnow() < expiration

    async def search(
        self,
        query: str,
        num_results: Optional[int] = None,
        use_cache: bool = True
    ) -> WebSearchResponse:
        """
        Search the web for a query.

        Args:
            query: Search query
            num_results: Number of results (default: self.max_results)
            use_cache: Use cache if available (default: True)

        Returns:
            WebSearchResponse with results
        """
        num_results = num_results or self.max_results

        logger.info(
            "web_search_requested",
            query=query,
            num_results=num_results,
            use_cache=use_cache
        )

        # Check cache
        cache_key = self._generate_cache_key(query, num_results=num_results)

        if use_cache and cache_key in self._cache:
            cached_response, cached_at = self._cache[cache_key]

            if self._is_cache_valid(cached_at):
                logger.info(
                    "web_search_cache_hit",
                    query=query,
                    cache_age_seconds=int((datetime.utcnow() - cached_at).total_seconds())
                )

                # Mark as cached and set expiration
                cached_response.cached = True
                cached_response.cache_expires_at = cached_at + timedelta(seconds=self.cache_ttl_seconds)

                return cached_response

            else:
                # Cache expired, remove it
                del self._cache[cache_key]
                logger.info("web_search_cache_expired", query=query)

        # Cache miss or expired, perform search
        if self.api_key:
            response = await self._search_with_api(query, num_results)
        else:
            # Fallback to mock results
            logger.warning(
                "web_search_no_api_key_using_mock",
                query=query
            )
            response = self._generate_mock_results(query, num_results)

        # Store in cache
        if use_cache:
            self._cache[cache_key] = (response, datetime.utcnow())

        logger.info(
            "web_search_completed",
            query=query,
            results_count=len(response.results),
            cached=False
        )

        return response

    async def _search_with_api(
        self,
        query: str,
        num_results: int
    ) -> WebSearchResponse:
        """
        Perform search via API (Serper.dev by default).

        Serper API Doc: https://serper.dev/api
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Serper API
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "q": query,
                        "num": num_results,
                        "gl": "fr",  # Country: France
                        "hl": "fr"   # Language: French
                    }
                )

                if response.status_code == 200:
                    data = response.json()

                    results = []
                    for idx, item in enumerate(data.get("organic", [])[:num_results]):
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                            position=idx + 1,
                            metadata={
                                "date": item.get("date"),
                                "sitelinks": item.get("sitelinks")
                            }
                        ))

                    return WebSearchResponse(
                        query=query,
                        results=results,
                        total_results=len(results),
                        cached=False,
                        api_provider="serper"
                    )

                else:
                    logger.error(
                        "web_search_api_error",
                        query=query,
                        status_code=response.status_code,
                        response=response.text
                    )
                    # Fallback to mock
                    return self._generate_mock_results(query, num_results)

        except Exception as e:
            logger.error(
                "web_search_api_exception",
                query=query,
                error=str(e),
                exc_info=True
            )
            # Fallback to mock
            return self._generate_mock_results(query, num_results)

    def _generate_mock_results(
        self,
        query: str,
        num_results: int
    ) -> WebSearchResponse:
        """Generate mock search results for testing"""
        results = []

        for i in range(min(num_results, 5)):
            results.append(SearchResult(
                title=f"Result {i+1} for '{query}'",
                url=f"https://example.com/page{i+1}",
                snippet=f"This is a mock result snippet for query: {query}. Position {i+1}.",
                position=i + 1,
                metadata={"mock": True}
            ))

        return WebSearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            cached=False,
            api_provider="mock"
        )

    def format_results_for_rag(
        self,
        response: WebSearchResponse
    ) -> List[Dict[str, Any]]:
        """
        Format search results for RAG integration.

        Converts search results to chunks with URL citations.

        Returns:
            List of chunks suitable for RAG synthesis
        """
        chunks = []

        for result in response.results:
            chunks.append({
                "id": f"web_{hashlib.md5(str(result.url).encode()).hexdigest()[:8]}",
                "type": "web",
                "title": result.title,
                "content": result.snippet,
                "url": str(result.url),
                "position": result.position,
                "metadata": {
                    **result.metadata,
                    "source": "web_search",
                    "query": response.query
                }
            })

        return chunks

    def clear_cache(self):
        """Clear all cache"""
        self._cache.clear()
        logger.info("web_search_cache_cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = datetime.utcnow()

        valid_count = 0
        expired_count = 0

        for cached_response, cached_at in self._cache.values():
            if self._is_cache_valid(cached_at):
                valid_count += 1
            else:
                expired_count += 1

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "expired_entries": expired_count,
            "ttl_seconds": self.cache_ttl_seconds
        }
