"""
Web Agent - Internet Search for Real-Time Information

Performs web searches to answer questions requiring current information not
available in the internal knowledge base (RAG/SQL).

Capabilities:
- Real-time web search (news, regulations, market prices)
- Source citation and ranking
- Content synthesis from multiple sources
- Fact verification

Use Cases:
- "Quelle est la nouvelle loi sur les copropriétés en 2025 ?"
- "Quel est le prix actuel du fioul domestique ?"
- "Dernières actualités sur les normes énergétiques ?"

APIs Supported:
- Brave Search API (Recommended - GDPR compliant, European)
- Serper API (Google Search wrapper)
- DuckDuckGo (Fallback - no API key required)

References:
- Perplexity AI architecture
- WebGPT (OpenAI)
- Bing Chat / ChatGPT browsing mode
"""

import asyncio
import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx

from app.services.llm_service import LLMService
from app.core.config import settings

logger = structlog.get_logger()


class WebAgent:
    """
    Web Search Agent for real-time information retrieval

    Architecture:
    1. Detect search intent (query classification)
    2. Perform web search (Brave/Serper/DuckDuckGo)
    3. Extract and rank snippets
    4. Synthesize answer with citations
    5. Return structured response
    """

    def __init__(self):
        self.llm_service = LLMService()

        # API keys from settings
        self.brave_api_key = getattr(settings, 'BRAVE_SEARCH_API_KEY', None)
        self.serper_api_key = getattr(settings, 'SERPER_API_KEY', None)

        # Default to Brave if available, else Serper, else DuckDuckGo
        if self.brave_api_key:
            self.search_provider = "brave"
            logger.info("web_agent_initialized", provider="brave")
        elif self.serper_api_key:
            self.search_provider = "serper"
            logger.info("web_agent_initialized", provider="serper")
        else:
            self.search_provider = "duckduckgo"
            logger.info("web_agent_initialized", provider="duckduckgo", note="No API key - using free tier")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_type: str = "web"
    ) -> Dict[str, Any]:
        """
        Perform web search and synthesize answer

        Args:
            query: User's search query
            max_results: Maximum number of search results to retrieve
            search_type: Type of search ("web", "news", "images")

        Returns:
            Dict with:
                - answer: Synthesized answer with citations
                - sources: List of source URLs and snippets
                - metadata: Search metadata (provider, timestamp, etc.)

        Example:
            >>> result = await web_agent.search("nouvelle loi copropriété 2025")
            >>> print(result["answer"])
            "En 2025, la loi Climat et Résilience impose... [1][2]"
            >>> print(result["sources"])
            [
                {
                    "title": "Loi Climat 2025...",
                    "url": "https://...",
                    "snippet": "...",
                    "rank": 1
                }
            ]
        """
        try:
            logger.info("web_search_started", query=query[:50], provider=self.search_provider)

            # Step 1: Perform web search
            search_results = await self._perform_search(query, max_results, search_type)

            if not search_results:
                return {
                    "answer": "Aucun résultat trouvé sur internet pour cette requête.",
                    "sources": [],
                    "metadata": {
                        "provider": self.search_provider,
                        "timestamp": datetime.now().isoformat(),
                        "query": query,
                        "results_count": 0
                    }
                }

            # Step 2: Synthesize answer from search results
            answer = await self._synthesize_answer(query, search_results)

            # Step 3: Format response
            response = {
                "answer": answer,
                "sources": [
                    {
                        "title": result.get("title", "Sans titre"),
                        "url": result.get("url", ""),
                        "snippet": result.get("snippet", ""),
                        "rank": idx + 1
                    }
                    for idx, result in enumerate(search_results)
                ],
                "metadata": {
                    "provider": self.search_provider,
                    "timestamp": datetime.now().isoformat(),
                    "query": query,
                    "results_count": len(search_results)
                }
            }

            logger.info(
                "web_search_completed",
                query=query[:50],
                results_count=len(search_results),
                answer_length=len(answer)
            )

            return response

        except Exception as e:
            logger.error("web_search_failed", error=str(e), exc_info=True)
            return {
                "answer": f"Erreur lors de la recherche web : {str(e)}",
                "sources": [],
                "metadata": {
                    "provider": self.search_provider,
                    "timestamp": datetime.now().isoformat(),
                    "query": query,
                    "error": str(e)
                }
            }

    async def _perform_search(
        self,
        query: str,
        max_results: int,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """
        Perform web search using configured provider

        Args:
            query: Search query
            max_results: Max results to return
            search_type: Type of search

        Returns:
            List of search results with title, url, snippet
        """
        if self.search_provider == "brave":
            return await self._brave_search(query, max_results, search_type)
        elif self.search_provider == "serper":
            return await self._serper_search(query, max_results, search_type)
        else:
            return await self._duckduckgo_search(query, max_results)

    async def _brave_search(
        self,
        query: str,
        max_results: int,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """
        Search using Brave Search API

        API Docs: https://api.search.brave.com/app/documentation/web-search/get-started
        Pricing: Free tier (2,000 queries/month), then $5/1,000 queries

        Advantages:
        - GDPR compliant
        - No user tracking
        - High quality results
        - European data centers
        """
        try:
            url = "https://api.search.brave.com/res/v1/web/search"

            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.brave_api_key
            }

            params = {
                "q": query,
                "count": max_results,
                "search_lang": "fr",  # French results
                "country": "FR",  # France
                "freshness": "pw"  # Past week for recent results
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

            # Parse results
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", ""),
                    "age": item.get("age", "")
                })

            logger.info("brave_search_completed", results_count=len(results))
            return results

        except Exception as e:
            logger.error("brave_search_failed", error=str(e))
            # Fallback to DuckDuckGo
            return await self._duckduckgo_search(query, max_results)

    async def _serper_search(
        self,
        query: str,
        max_results: int,
        search_type: str
    ) -> List[Dict[str, Any]]:
        """
        Search using Serper API (Google Search wrapper)

        API Docs: https://serper.dev/
        Pricing: Free tier (2,500 queries), then $50/10,000 queries

        Advantages:
        - Google search results
        - Fast and reliable
        - Good for news and current events
        """
        try:
            url = "https://google.serper.dev/search"

            headers = {
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "q": query,
                "num": max_results,
                "gl": "fr",  # France
                "hl": "fr"   # French language
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            # Parse results
            results = []
            for item in data.get("organic", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position", 0)
                })

            logger.info("serper_search_completed", results_count=len(results))
            return results

        except Exception as e:
            logger.error("serper_search_failed", error=str(e))
            # Fallback to DuckDuckGo
            return await self._duckduckgo_search(query, max_results)

    async def _duckduckgo_search(
        self,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo (no API key required)

        Uses duckduckgo-search library (free, no API key)

        Advantages:
        - Free (no API key)
        - Privacy-focused
        - Good fallback option

        Note:
            Install with: pip install duckduckgo-search
        """
        try:
            from duckduckgo_search import DDGS

            # Run in thread pool (blocking I/O)
            def search_sync():
                with DDGS() as ddgs:
                    results = list(ddgs.text(
                        query,
                        region="fr-fr",
                        safesearch="moderate",
                        max_results=max_results
                    ))
                    return results

            results_raw = await asyncio.to_thread(search_sync)

            # Format results
            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", "")
                }
                for item in results_raw
            ]

            logger.info("duckduckgo_search_completed", results_count=len(results))
            return results

        except ImportError:
            logger.error("duckduckgo_search_library_not_installed",
                        message="Install with: pip install duckduckgo-search")
            return []
        except Exception as e:
            logger.error("duckduckgo_search_failed", error=str(e))
            return []

    async def _synthesize_answer(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """
        Synthesize answer from search results using LLM

        Args:
            query: User's original query
            search_results: List of search results

        Returns:
            Synthesized answer with inline citations [1], [2], etc.
        """
        try:
            # Build context from search results
            context_parts = []
            for idx, result in enumerate(search_results, start=1):
                context_parts.append(
                    f"[{idx}] {result['title']}\n"
                    f"URL: {result['url']}\n"
                    f"Contenu: {result['snippet']}\n"
                )

            context = "\n".join(context_parts)

            # Prompt for synthesis
            prompt = f"""Tu es un assistant expert qui synthétise des informations provenant de sources web.

QUESTION DE L'UTILISATEUR :
{query}

SOURCES WEB (avec citations) :
{context}

CONSIGNES :
- Réponds à la question en te basant UNIQUEMENT sur les sources fournies
- Cite tes sources avec [1], [2], etc. après chaque affirmation
- Sois précis et factuel
- Si les sources sont contradictoires, mentionne-le
- Si les sources ne permettent pas de répondre, dis-le clairement
- Structure ta réponse en paragraphes clairs
- Utilise un ton professionnel mais accessible

Réponds maintenant :
"""

            answer = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,  # Lower for factual accuracy
                max_tokens=800
            )

            return answer.strip()

        except Exception as e:
            logger.error("answer_synthesis_failed", error=str(e))
            # Fallback to simple concatenation
            return f"Résultats trouvés :\n" + "\n\n".join([
                f"[{idx + 1}] {result['title']}\n{result['snippet']}"
                for idx, result in enumerate(search_results)
            ])

    def get_capabilities(self) -> Dict[str, Any]:
        """Get web agent capabilities and configuration"""
        return {
            "name": "Web Agent",
            "description": "Recherche d'informations en temps réel sur internet",
            "provider": self.search_provider,
            "capabilities": [
                "web_search",
                "news_search",
                "fact_checking",
                "source_citation"
            ],
            "use_cases": [
                "Actualités et nouvelles réglementations",
                "Prix du marché et tarifs actuels",
                "Informations techniques récentes",
                "Vérification de faits"
            ],
            "limitations": [
                "Dépend de la qualité des sources web",
                "Peut contenir des informations non vérifiées",
                "Limité par les quotas API" if self.search_provider != "duckduckgo" else "Gratuit mais plus lent"
            ]
        }
