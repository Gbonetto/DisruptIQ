"""
WebSearch Agent - Performs web searches and synthesizes results

Uses DuckDuckGo Search API (free, no key required)
Optional: Tavily API for advanced searches (requires API key)

Features:
- Web search with context synthesis
- Source citation and credibility scoring
- Result filtering and ranking
- RAG-style answer generation with citations
- Cross-encoder re-ranking for better relevance
- Redis caching for faster responses
- Contextual memory for multi-turn conversations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
from duckduckgo_search import DDGS
import re
import asyncio
from functools import partial
import os
import httpx
import json

logger = structlog.get_logger()

# Lazy import for Mistral (only when LLM synthesis is used)
_mistral_client = None

def get_mistral_client():
    """Lazy load Mistral client for LLM synthesis"""
    global _mistral_client
    if _mistral_client is None:
        try:
            from langchain_mistralai import ChatMistralAI
            api_key = os.getenv("MISTRAL_API_KEY")
            if api_key:
                _mistral_client = ChatMistralAI(
                    model="mistral-small-latest",
                    temperature=0.3,
                    api_key=api_key
                )
                logger.info("mistral_llm_loaded_for_synthesis", model="mistral-small-latest")
            else:
                logger.warning("mistral_api_key_not_found")
        except Exception as e:
            logger.warning("mistral_llm_load_failed", error=str(e))
    return _mistral_client


# Lazy import for Cross-Encoder (for re-ranking)
_cross_encoder = None

def get_cross_encoder():
    """Lazy load Cross-Encoder for result re-ranking"""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("cross_encoder_loaded", model="ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.warning("cross_encoder_load_failed", error=str(e))
    return _cross_encoder


class SearchResult:
    """Represents a single search result"""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        source: str = "duckduckgo",
        relevance_score: float = 0.0
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.relevance_score = relevance_score
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "relevance_score": self.relevance_score
        }


class SearchResults:
    """Collection of search results with synthesis"""

    def __init__(
        self,
        query: str,
        results: List[SearchResult],
        synthesized_answer: Optional[str] = None,
        confidence: float = 0.0
    ):
        self.query = query
        self.results = results
        self.synthesized_answer = synthesized_answer
        self.confidence = confidence
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "answer": self.synthesized_answer,
            "sources": [r.url for r in self.results],
            "confidence": self.confidence,
            "result_count": len(self.results)
        }


class WebSearchAgent:
    """
    Web Search Agent using DuckDuckGo (free) or Tavily (premium)

    Capabilities:
    - General web search with cross-encoder re-ranking
    - News search
    - Legal/regulatory search
    - Context-aware answer synthesis
    - Source citation with credibility scoring
    - Redis caching for performance
    - Contextual memory for multi-turn conversations
    """

    def __init__(self, use_tavily: bool = False, tavily_api_key: Optional[str] = None, brave_api_key: Optional[str] = None):
        """
        Initialize WebSearch Agent

        Args:
            use_tavily: Whether to use Tavily API (requires key)
            tavily_api_key: Tavily API key (optional)
            brave_api_key: Brave Search API key (optional)
        """
        from app.core.config import settings

        # Priority: Brave > Tavily > DuckDuckGo (free but rate-limited)
        self.brave_api_key = brave_api_key or settings.BRAVE_SEARCH_API_KEY
        self.use_brave = self.brave_api_key is not None and self.brave_api_key != ""

        self.tavily_api_key = tavily_api_key or getattr(settings, "TAVILY_API_KEY", "")
        self.use_tavily = (use_tavily or not self.use_brave) and self.tavily_api_key is not None and self.tavily_api_key != ""

        # Initialize cache service for Redis caching
        try:
            from app.services.cache_service import CacheService
            self.cache_service = CacheService()
            self.cache_ttl = 3600  # 1 hour cache by default
            logger.info("cache_service_initialized_for_websearch")
        except Exception as e:
            logger.warning("cache_service_init_failed", error=str(e))
            self.cache_service = None

        provider = "brave" if self.use_brave else ("tavily" if self.use_tavily else "duckduckgo")
        logger.info(
            "websearch_agent_initialized",
            provider=provider,
            caching_enabled=self.cache_service is not None
        )

    async def search(
        self,
        query: str,
        num_results: int = 5,
        search_depth: str = "basic",
        region: str = "fr-fr",
        time_range: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> SearchResults:
        """
        Perform web search with contextual awareness, caching, and re-ranking

        Args:
            query: Search query
            num_results: Number of results to return (max 10)
            search_depth: "basic" or "advanced" (Tavily only)
            region: Search region (e.g., "fr-fr" for France)
            time_range: Time filter ("d" = day, "w" = week, "m" = month, "y" = year)
            conversation_history: Recent conversation for contextual understanding

        Returns:
            SearchResults with synthesized answer
        """
        logger.info(
            "websearch_started",
            query=query[:100],
            num_results=num_results,
            provider="tavily" if self.use_tavily else "duckduckgo",
            has_conversation_history=conversation_history is not None
        )

        try:
            # STEP 1: Enrich query with conversational context
            enriched_query = await self._enrich_query_with_context(query, conversation_history)
            if enriched_query != query:
                logger.info("query_enriched_with_context",
                           original=query[:80],
                           enriched=enriched_query[:80])

            # STEP 2: Check cache
            cache_hit = False
            if self.cache_service:
                cache_key = f"websearch:{enriched_query.lower()}:{num_results}:{region}"
                cached_data = await self.cache_service.get(cache_key)

                if cached_data:
                    cache_hit = True
                    logger.info("websearch_cache_hit",
                               query=enriched_query[:80],
                               cache_key_hash=hash(cache_key) % 10000)

                    # Reconstruct SearchResults from cached data
                    cached_results = []
                    for r_dict in cached_data.get("results", []):
                        cached_results.append(SearchResult(
                            title=r_dict.get("title", ""),
                            url=r_dict.get("url", ""),
                            snippet=r_dict.get("snippet", ""),
                            source=r_dict.get("source", "duckduckgo"),
                            relevance_score=r_dict.get("relevance_score", 0.0)
                        ))

                    return SearchResults(
                        query=enriched_query,
                        results=cached_results,
                        synthesized_answer=cached_data.get("answer"),
                        confidence=cached_data.get("confidence", 0.8)
                    )

            # STEP 3: Perform search (cache miss)
            logger.info("websearch_cache_miss", query=enriched_query[:80])

            if self.use_brave:
                results = await self._search_brave(enriched_query, num_results, region)
            elif self.use_tavily:
                results = await self._search_tavily(enriched_query, num_results, search_depth)
            else:
                results = await self._search_duckduckgo(enriched_query, num_results, region, time_range)

            # STEP 4: Re-rank results with cross-encoder
            if results.results:
                results.results = await self._rerank_results(enriched_query, results.results)

            # STEP 5: Store in cache
            if self.cache_service and results.results:
                cache_key = f"websearch:{enriched_query.lower()}:{num_results}:{region}"
                await self.cache_service.set(
                    cache_key,
                    results.to_dict(),
                    ttl=self.cache_ttl
                )
                logger.info("websearch_cached",
                           query=enriched_query[:80],
                           ttl_seconds=self.cache_ttl)

            logger.info(
                "websearch_completed",
                query=enriched_query[:80],
                result_count=len(results.results),
                has_answer=results.synthesized_answer is not None,
                cache_hit=cache_hit,
                reranked=len(results.results) > 0
            )

            return results

        except Exception as e:
            logger.error(
                "websearch_failed",
                query=query[:80],
                error=str(e),
                exc_info=True
            )
            # Return empty results on error
            return SearchResults(
                query=query,
                results=[],
                synthesized_answer=f"Erreur lors de la recherche: {str(e)}",
                confidence=0.0
            )

    async def _search_duckduckgo(
        self,
        query: str,
        num_results: int,
        region: str,
        time_range: Optional[str]
    ) -> SearchResults:
        """
        Search using DuckDuckGo (free, no API key)

        Args:
            query: Search query
            num_results: Number of results
            region: Search region
            time_range: Time filter

        Returns:
            SearchResults
        """
        # DuckDuckGo API is often rate-limited, use HTML scraping directly
        # This is more reliable than the API for production use
        logger.info("duckduckgo_using_html_method",
                   reason="More reliable than API (avoids rate limiting)")
        raw_results = await self._search_duckduckgo_html(query, num_results)

        # If HTML scraping failed, try API as fallback
        if not raw_results:
            logger.info("duckduckgo_html_failed_trying_api")
            loop = asyncio.get_event_loop()

            def _search():
                try:
                    with DDGS() as ddgs:
                        search_params = {
                            "keywords": query,
                            "region": region,
                            "safesearch": "moderate",
                            "max_results": num_results
                        }
                        if time_range:
                            search_params["timelimit"] = time_range
                        raw_results = list(ddgs.text(**search_params))
                        return raw_results
                except Exception as e:
                    logger.warning("duckduckgo_api_failed", error=str(e))
                    return []

            raw_results = await loop.run_in_executor(None, _search)

        # Convert to SearchResult objects
        results = []
        for idx, r in enumerate(raw_results):
            result = SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
                source="duckduckgo",
                relevance_score=1.0 - (idx * 0.1)  # Simple ranking
            )
            results.append(result)

        # Generate LLM synthesis (with fallback to basic)
        synthesized_answer = await self._synthesize_llm(query, results)

        return SearchResults(
            query=query,
            results=results,
            synthesized_answer=synthesized_answer,
            confidence=0.8 if results else 0.0  # Higher confidence with LLM synthesis
        )

    async def _search_brave(
        self,
        query: str,
        num_results: int,
        region: str
    ) -> SearchResults:
        """
        Search using Brave Search API (requires API key)

        API Documentation: https://api.search.brave.com/app/documentation/web-search/get-started

        Args:
            query: Search query
            num_results: Number of results to return
            region: Region/country code (e.g., 'fr-fr')

        Returns:
            SearchResults with AI-generated synthesis
        """
        try:
            # Brave API endpoint
            api_url = "https://api.search.brave.com/res/v1/web/search"

            # Extract country code from region (e.g., 'fr-fr' -> 'FR')
            country_code = region.split('-')[0].upper() if region else "FR"

            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.brave_api_key
            }

            params = {
                "q": query,
                "count": num_results,
                "country": country_code,
                "search_lang": "fr",
                "ui_lang": "fr-FR",
                "safesearch": "moderate",
                "freshness": None  # Can be: "24h", "week", "month", "year"
            }

            logger.info(
                "brave_search_request",
                query=query[:80],
                num_results=num_results,
                country=country_code
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(api_url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            # Parse results from Brave API response
            results = []
            web_results = data.get("web", {}).get("results", [])

            logger.info("brave_api_response", total_results=len(web_results))

            for idx, item in enumerate(web_results[:num_results]):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    source="brave",
                    relevance_score=1.0 - (idx * 0.05)  # Decreasing score by position
                )
                results.append(result)

            if not results:
                logger.warning("brave_search_empty_results", query=query[:80])
                return SearchResults(
                    query=query,
                    results=[],
                    synthesized_answer="Aucun résultat trouvé",
                    confidence=0.0
                )

            logger.info("brave_search_success", result_count=len(results))

            # Generate LLM synthesis of search results
            synthesized_answer = await self._synthesize_llm(query, results)

            return SearchResults(
                query=query,
                results=results,
                synthesized_answer=synthesized_answer,
                confidence=0.9 if results else 0.0  # High confidence with Brave API
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "brave_api_http_error",
                status_code=e.response.status_code,
                error=str(e),
                exc_info=True
            )
            # Fallback to DuckDuckGo on API errors
            logger.warning("brave_api_failed_fallback_to_duckduckgo")
            return await self._search_duckduckgo(query, num_results, region, None)

        except Exception as e:
            logger.error("brave_search_failed", error=str(e), exc_info=True)
            # Fallback to DuckDuckGo
            logger.warning("brave_search_exception_fallback_to_duckduckgo")
            return await self._search_duckduckgo(query, num_results, region, None)

    async def _search_tavily(
        self,
        query: str,
        num_results: int,
        search_depth: str
    ) -> SearchResults:
        """
        Search using Tavily API (requires API key)

        Args:
            query: Search query
            num_results: Number of results
            search_depth: "basic" or "advanced"

        Returns:
            SearchResults with AI-generated answer
        """
        # TODO: Implement Tavily integration when API key available
        # For now, fall back to DuckDuckGo
        logger.warning(
            "tavily_not_implemented",
            message="Tavily support not yet implemented, falling back to DuckDuckGo"
        )
        return await self._search_duckduckgo(query, num_results, "fr-fr", None)

    async def _search_duckduckgo_html(self, query: str, num_results: int) -> List[Dict]:
        """
        Fallback: Search DuckDuckGo via HTML scraping when API is rate limited
        """
        try:
            from urllib.parse import unquote, parse_qs, urlparse, quote
            import html as html_module

            # URL encode the query properly
            encoded_query = quote(query)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(search_url, headers=headers)
                response.raise_for_status()

            html = response.text
            results = []

            # Parse result links - DDG uses redirect URLs
            link_pattern = r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            snippet_pattern = r'class="result__snippet"[^>]*>([^<]+)'

            links = re.findall(link_pattern, html)
            snippets = re.findall(snippet_pattern, html)

            logger.info("duckduckgo_html_parsing", links_found=len(links), snippets_found=len(snippets))

            for i, (redirect_url, title) in enumerate(links[:num_results]):
                # Extract real URL from DDG redirect
                if 'uddg=' in redirect_url:
                    parsed = urlparse(redirect_url)
                    params = parse_qs(parsed.query)
                    real_url = unquote(params.get('uddg', [''])[0])
                else:
                    real_url = redirect_url

                # Get snippet if available
                snippet = html_module.unescape(snippets[i]) if i < len(snippets) else ""

                # Only add if we have a valid URL
                if real_url and real_url.startswith('http'):
                    results.append({
                        "href": real_url,
                        "title": html_module.unescape(title.strip()),
                        "body": snippet.strip()
                    })

            logger.info("duckduckgo_html_fallback_success", result_count=len(results))
            return results

        except Exception as e:
            logger.error("duckduckgo_html_fallback_failed", error=str(e), exc_info=True)
            return []

    async def _synthesize_llm(self, query: str, results: List[SearchResult]) -> str:
        """
        Generate intelligent synthesis using Mistral LLM

        Args:
            query: Original query
            results: List of search results

        Returns:
            LLM-generated synthesis with citations
        """
        if not results:
            return "Aucun résultat trouvé."

        mistral = get_mistral_client()

        if mistral is None:
            # Fallback to basic synthesis
            return self._synthesize_basic(query, results)

        try:
            # Prepare context from search results
            context_parts = []
            for idx, result in enumerate(results[:5], 1):
                context_parts.append(
                    f"[Source {idx}] {result.title}\n"
                    f"URL: {result.url}\n"
                    f"Contenu: {result.snippet}\n"
                )

            context = "\n".join(context_parts)

            # LLM synthesis prompt
            synthesis_prompt = f"""Tu es un assistant expert qui synthétise des résultats de recherche web.

Question de l'utilisateur: {query}

Résultats de recherche:
{context}

Instructions:
1. Réponds à la question de l'utilisateur en français de manière concise et précise
2. Base ta réponse UNIQUEMENT sur les informations fournies dans les résultats
3. Cite tes sources en utilisant [Source X] pour chaque information
4. Si les résultats ne permettent pas de répondre complètement, indique-le clairement
5. Sois factuel et objectif

Réponse synthétique:"""

            # Call Mistral LLM
            response = await asyncio.to_thread(
                lambda: mistral.invoke(synthesis_prompt).content
            )

            logger.info("llm_synthesis_generated",
                       query=query[:50],
                       response_length=len(response),
                       sources_count=len(results))

            return response

        except Exception as e:
            logger.error("llm_synthesis_failed",
                        query=query,
                        error=str(e),
                        exc_info=True)
            # Fallback to basic synthesis
            return self._synthesize_basic(query, results)

    def _synthesize_basic(self, query: str, results: List[SearchResult]) -> str:
        """
        Generate basic synthesis from search results (without LLM) - FALLBACK

        Args:
            query: Original query
            results: List of search results

        Returns:
            Synthesized answer
        """
        if not results:
            return "Aucun résultat trouvé."

        # Extract key information from snippets
        snippets = [r.snippet for r in results[:3]]  # Top 3 results

        # Simple synthesis: combine snippets
        synthesis = f"Voici les informations trouvées sur '{query}':\n\n"

        for idx, (result, snippet) in enumerate(zip(results[:3], snippets), 1):
            synthesis += f"{idx}. {snippet[:200]}... [Source: {result.url}]\n\n"

        synthesis += f"\nBasé sur {len(results)} résultats de recherche."

        return synthesis

    async def _enrich_query_with_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Enrich query using conversation history for contextual understanding

        Handles:
        - Implicit references ("et pour les copropriétaires ?")
        - Follow-up questions ("maintenant les décrets")
        - Corrections/refinements ("non, je voulais...")

        Args:
            query: Current user query
            conversation_history: Last N messages from conversation

        Returns:
            Enriched, self-contained query
        """
        # No history → return query as-is
        if not conversation_history or len(conversation_history) == 0:
            logger.debug("query_enrichment_skipped", reason="no_history")
            return query

        # Check if query needs context (heuristics)
        needs_context = self._query_needs_context(query)
        if not needs_context:
            logger.debug("query_enrichment_skipped", reason="query_is_self_contained")
            return query

        # Use LLM to enrich query
        mistral = get_mistral_client()
        if not mistral:
            logger.warning("query_enrichment_failed", reason="llm_unavailable")
            return query

        try:
            # Build conversation context (last 6 messages = 3 turns)
            context_messages = []
            for msg in conversation_history[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    # Truncate long messages
                    truncated = content[:300] + "..." if len(content) > 300 else content
                    context_messages.append(f"{role.upper()}: {truncated}")

            context_str = "\n".join(context_messages)

            # LLM enrichment prompt
            enrichment_prompt = f"""Tu es un assistant qui reformule des requêtes de recherche web pour les rendre autonomes et complètes.

Contexte de la conversation:
{context_str}

Nouvelle requête de l'utilisateur: {query}

Instructions:
1. Si la requête fait référence au contexte précédent, reformule-la en incluant les éléments contextuels nécessaires
2. Si la requête est déjà complète et autonome, retourne-la telle quelle
3. Garde la requête concise (max 150 caractères)
4. Conserve les termes techniques et noms propres exacts
5. Réponds UNIQUEMENT avec la requête reformulée, sans explication

Requête reformulée:"""

            # Call LLM
            enriched = await asyncio.to_thread(
                lambda: mistral.invoke(enrichment_prompt).content.strip()
            )

            # Clean response (remove quotes, explanations)
            enriched = enriched.strip('"\'').split('\n')[0].strip()

            # Sanity check: If enriched is too different or too long, use original
            if len(enriched) > 200 or len(enriched) < 5:
                logger.warning("query_enrichment_rejected",
                              reason="invalid_length",
                              enriched_length=len(enriched))
                return query

            logger.info("query_enriched_successfully",
                       original=query[:80],
                       enriched=enriched[:80])

            return enriched

        except Exception as e:
            logger.error("query_enrichment_failed",
                        query=query[:80],
                        error=str(e))
            return query  # Fallback to original

    def _query_needs_context(self, query: str) -> bool:
        """
        Heuristic to determine if query needs contextual enrichment

        Returns:
            True if query likely needs context, False otherwise
        """
        query_lower = query.lower()

        # Patterns indicating need for context
        context_indicators = [
            # Pronouns/references
            r'\b(il|elle|ils|elles|celui|celle|ceux|celles)\b',
            r'\b(ça|cela|ce|cet|cette)\b',

            # Implicit references
            r'\b(aussi|également|pareillement)\b',
            r'\b(et pour|qu\'en est-il de|concernant)\b',
            r'\b(maintenant|ensuite|après)\b',

            # Corrections/refinements
            r'\b(non|pas|plutôt|en fait)\b',
            r'\b(précisément|exactement|spécifiquement)\b',

            # Follow-ups
            r'\b(plus d\'infos|plus de détails|approfondir)\b',
            r'\b(décrets|arrêtés|circulaires)\b\s+(d\')?application',

            # Incomplete queries
            r'^(et|ou|mais|donc)',
        ]

        for pattern in context_indicators:
            if re.search(pattern, query_lower):
                logger.debug("query_needs_context_detected",
                           query=query[:50],
                           pattern=pattern)
                return True

        # Query is very short (< 20 chars) → likely needs context
        if len(query) < 20:
            logger.debug("query_needs_context_detected",
                       query=query,
                       reason="query_too_short")
            return True

        return False

    async def _rerank_results(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Re-rank search results using cross-encoder for better relevance

        Args:
            query: User query
            results: List of search results

        Returns:
            Re-ranked list of search results
        """
        if not results or len(results) <= 1:
            return results

        cross_encoder = get_cross_encoder()
        if not cross_encoder:
            logger.warning("cross_encoder_unavailable", message="Skipping re-ranking")
            return results

        try:
            # Prepare pairs for cross-encoder (query, document)
            pairs = []
            for result in results:
                # Combine title + snippet for better context
                text = f"{result.title}. {result.snippet}"
                pairs.append([query, text])

            # Calculate cross-encoder scores
            scores = await asyncio.to_thread(
                lambda: cross_encoder.predict(pairs)
            )

            # Store original scores for logging
            original_scores = [r.relevance_score for r in results]

            # Update relevance scores
            for result, score in zip(results, scores):
                result.relevance_score = float(score)

            # Sort by cross-encoder score (descending)
            reranked = sorted(results, key=lambda r: r.relevance_score, reverse=True)

            logger.info(
                "results_reranked",
                query=query[:50],
                original_top_score=f"{original_scores[0]:.3f}" if original_scores else "N/A",
                reranked_top_score=f"{reranked[0].relevance_score:.3f}",
                original_top=results[0].title[:50] if results else "N/A",
                reranked_top=reranked[0].title[:50] if reranked else "N/A"
            )

            return reranked

        except Exception as e:
            logger.error("reranking_failed",
                        query=query[:50],
                        error=str(e),
                        exc_info=True)
            return results  # Fallback to original order

    async def search_with_context(
        self,
        query: str,
        context: Dict[str, Any],
        num_results: int = 5
    ) -> str:
        """
        Search and generate contextualized answer

        Uses RAG-like approach:
        1. Web search for relevant pages
        2. Extract key information
        3. Generate answer with citations

        Args:
            query: Search query
            context: Conversation context
            num_results: Number of results

        Returns:
            Contextualized answer with citations
        """
        # Enrich query with context (use synchronous version)
        enriched_query = self._enrich_query_simple(query, context)

        logger.info(
            "websearch_context_enrichment",
            original=query,
            enriched=enriched_query
        )

        # Perform search
        results = await self.search(enriched_query, num_results)

        # Generate contextualized answer
        if context.get("incident_type"):
            # Legal/incident context
            answer = self._contextualize_legal(query, results, context)
        else:
            # General context
            answer = results.synthesized_answer or "Aucune information trouvée."

        return answer

    def _enrich_query_simple(self, query: str, context: Dict[str, Any]) -> str:
        """
        Enrich query with conversation context (simple synchronous version)

        Args:
            query: Original query
            context: Conversation context

        Returns:
            Enriched query
        """
        enriched = query

        # Add incident type context
        if "incident_type" in context:
            incident_type = context["incident_type"]
            incident_map = {
                "gas": "gaz",
                "water_damage": "dégât des eaux",
                "electrical": "électrique",
                "heating": "chauffage"
            }
            if incident_type in incident_map:
                enriched += f" {incident_map[incident_type]}"

        # Add location context if available
        if "property_name" in context:
            enriched += f" copropriété"

        # Add profession context
        if "profession_requested" in context:
            enriched += f" {context['profession_requested']}"

        return enriched

    def _contextualize_legal(
        self,
        query: str,
        results: SearchResults,
        context: Dict[str, Any]
    ) -> str:
        """
        Generate legal/incident-specific answer

        Args:
            query: Original query
            results: Search results
            context: Conversation context

        Returns:
            Contextualized answer
        """
        if not results.results:
            return "Aucune information légale ou réglementaire trouvée."

        # Start with basic synthesis
        answer = f"Informations légales concernant '{query}':\n\n"

        # Add top results with legal focus
        for idx, result in enumerate(results.results[:3], 1):
            # Check if result is from legal source
            is_legal = any(
                domain in result.url.lower()
                for domain in ["legifrance", "service-public", "droit", "loi"]
            )

            source_marker = "⚖️ " if is_legal else ""
            answer += f"{source_marker}{idx}. {result.snippet[:150]}...\n"
            answer += f"   Source: {result.url}\n\n"

        # Add incident context if available
        if "incident_type" in context:
            answer += f"\n⚠️ Contexte: {context.get('incident_type', 'incident')}\n"

        return answer

    async def search_news(
        self,
        query: str,
        num_results: int = 5,
        days_back: int = 30
    ) -> SearchResults:
        """
        Search recent news

        Args:
            query: Search query
            num_results: Number of results
            days_back: How many days back to search

        Returns:
            SearchResults with recent news
        """
        # Map days to DuckDuckGo time range
        time_range = "d" if days_back <= 1 else "w" if days_back <= 7 else "m"

        logger.info(
            "websearch_news",
            query=query,
            days_back=days_back,
            time_range=time_range
        )

        return await self._search_duckduckgo(
            query=query,
            num_results=num_results,
            region="fr-fr",
            time_range=time_range
        )

    async def search_legal(
        self,
        query: str,
        num_results: int = 5
    ) -> SearchResults:
        """
        Search legal/regulatory information

        Focuses on official French legal sources

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            SearchResults with legal sources
        """
        # Enhance query for legal search
        legal_query = f"{query} site:legifrance.gouv.fr OR site:service-public.fr"

        logger.info("websearch_legal", query=query, enhanced=legal_query)

        return await self._search_duckduckgo(
            query=legal_query,
            num_results=num_results,
            region="fr-fr",
            time_range=None
        )
