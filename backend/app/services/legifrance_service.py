"""
Légifrance API Service - Integration with automatic token management

Provides access to French legal database:
- Automatic OAuth2 token refresh (1h expiration)
- Jurisprudence search
- Law and regulation lookup
- Case law retrieval
"""

import structlog
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
from app.core.redis_client import get_redis_client
import json

logger = structlog.get_logger()


class LegifranceService:
    """
    Service for accessing Légifrance API with automatic token management.

    Features:
    - OAuth2 token auto-refresh (token expires after 1h)
    - Redis-based token caching
    - Jurisprudence search
    - Law article lookup
    """

    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize Légifrance service.

        Args:
            client_id: OAuth2 client ID from Légifrance
            client_secret: OAuth2 client secret from Légifrance
        """
        self.client_id = client_id
        self.client_secret = client_secret

        # Try to get Redis client (optional)
        try:
            self.redis_client = get_redis_client()
        except Exception as e:
            logger.warning("redis_client_init_failed", error=str(e))
            self.redis_client = None

        # API endpoints (PISTE Production)
        self.token_url = "https://oauth.piste.gouv.fr/api/oauth/token"
        self.api_base_url = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"

        # Token cache key
        self.token_cache_key = "legifrance:access_token"

        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)

        logger.info("legifrance_service_initialized")

    async def _get_access_token(self) -> str:
        """
        Get valid access token (from cache or by requesting new one).

        Token is cached in Redis for 55 minutes (5 min buffer before 1h expiration).

        Returns:
            Valid access token
        """
        # Try to get cached token (only if Redis is available)
        if self.redis_client:
            try:
                cached_token_data = await self.redis_client.get(self.token_cache_key)
                if cached_token_data:
                    token_data = json.loads(cached_token_data)
                    logger.info("legifrance_token_cache_hit")
                    return token_data["access_token"]
            except Exception as e:
                logger.warning("legifrance_cache_read_error", error=str(e))
                # Continue without cache

        # Request new token
        logger.info("legifrance_requesting_new_token")
        token_data = await self._request_new_token()

        # Cache token for 55 minutes (only if Redis available)
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    self.token_cache_key,
                    3300,  # 55 minutes in seconds
                    json.dumps(token_data)
                )
                logger.info("legifrance_token_cached", expires_in=3300)
            except Exception as e:
                logger.warning("legifrance_cache_write_error", error=str(e))
                # Continue without cache

        return token_data["access_token"]

    async def _request_new_token(self) -> Dict[str, Any]:
        """
        Request new OAuth2 access token from Légifrance.

        Returns:
            Token data with access_token, token_type, expires_in
        """
        try:
            response = await self.http_client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "openid resource.READ"
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )

            response.raise_for_status()
            token_data = response.json()

            logger.info("legifrance_token_obtained",
                       expires_in=token_data.get("expires_in", "unknown"))

            return token_data

        except httpx.HTTPStatusError as e:
            logger.error("legifrance_token_http_error",
                        status_code=e.response.status_code,
                        response=e.response.text)
            raise
        except Exception as e:
            logger.error("legifrance_token_request_failed", error=str(e))
            raise

    async def search_jurisprudence(
        self,
        query: str,
        case_type: str = "copropriete",
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search for jurisprudence (case law) in Légifrance database.

        Args:
            query: Search query (e.g., "assemblée générale copropriété")
            case_type: Type of case (copropriete, bail, etc.)
            max_results: Maximum number of results to return

        Returns:
            Dict with:
                - results: List of case law results
                - total: Total number of results found
                - query: Original query
        """
        try:
            # Get valid token
            access_token = await self._get_access_token()

            # Prepare search request
            search_endpoint = f"{self.api_base_url}/search"

            # Build query with filters
            full_query = f"{query} {case_type}"

            # Simplified payload based on working ACCO example
            payload = {
                "fond": "JURI",  # JURI = Jurisprudence judiciaire
                "recherche": {
                    "champs": [
                        {
                            "typeChamp": "ALL",
                            "criteres": [
                                {
                                    "typeRecherche": "UN_DES_MOTS",
                                    "valeur": query,  # Don't combine with case_type
                                    "operateur": "ET"
                                }
                            ],
                            "operateur": "ET"
                        }
                    ],
                    "operateur": "ET",
                    "pageNumber": 1,
                    "pageSize": max_results
                }
            }

            response = await self.http_client.post(
                search_endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )

            response.raise_for_status()
            data = response.json()

            # Parse results
            results = []
            for item in data.get("results", []):
                # Extract title from titles array
                title = ""
                if item.get("titles") and len(item["titles"]) > 0:
                    title = item["titles"][0].get("title", "")

                # Extract summary from resumePrincipal or text
                summary = ""
                if item.get("resumePrincipal") and len(item["resumePrincipal"]) > 0:
                    summary = item["resumePrincipal"][0].replace("<br/>", "")
                elif item.get("text"):
                    # Clean HTML tags from text
                    import re
                    text_clean = re.sub(r'<[^>]+>', '', item["text"])
                    summary = text_clean[:300] + "..." if len(text_clean) > 300 else text_clean

                # Get ID for URL construction
                doc_id = ""
                if item.get("titles") and len(item["titles"]) > 0:
                    doc_id = item["titles"][0].get("id", "")

                results.append({
                    "id": doc_id,
                    "title": title,
                    "summary": summary,
                    "nature": item.get("nature", ""),
                    "date": item.get("date", ""),
                    "url": f"https://www.legifrance.gouv.fr/juri/id/{doc_id}" if doc_id else ""
                })

            logger.info("legifrance_search_success",
                       query=query,
                       total_results=data.get("totalResultNumber", 0),
                       returned=len(results))

            return {
                "success": True,
                "results": results,
                "total": data.get("totalResultNumber", 0),
                "query": query
            }

        except httpx.HTTPStatusError as e:
            logger.error("legifrance_search_http_error",
                        status_code=e.response.status_code,
                        query=query)
            return {
                "success": False,
                "results": [],
                "total": 0,
                "query": query,
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except Exception as e:
            logger.error("legifrance_search_failed", query=query, error=str(e))
            return {
                "success": False,
                "results": [],
                "total": 0,
                "query": query,
                "error": str(e)
            }

    async def get_law_article(
        self,
        law_id: str,
        article_num: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve specific law article from Légifrance.

        Args:
            law_id: Law identifier (e.g., "LEGITEXT000006069108" for Loi 1965)
            article_num: Article number (e.g., "24")

        Returns:
            Article data or None if not found
        """
        try:
            access_token = await self._get_access_token()

            article_endpoint = f"{self.api_base_url}/consult/getArticle"

            payload = {
                "textId": law_id,
                "articleNum": article_num
            }

            response = await self.http_client.post(
                article_endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )

            response.raise_for_status()
            data = response.json()

            logger.info("legifrance_article_retrieved",
                       law_id=law_id,
                       article=article_num)

            return {
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "num": article_num,
                "law_id": law_id,
                "url": data.get("url", "")
            }

        except Exception as e:
            logger.error("legifrance_article_error",
                        law_id=law_id,
                        article=article_num,
                        error=str(e))
            return None

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# Singleton instance (lazy init with env variables)
_legifrance_service: Optional[LegifranceService] = None


def get_legifrance_service() -> Optional[LegifranceService]:
    """
    Get Légifrance service instance (singleton).

    Returns None if credentials are not configured.
    """
    global _legifrance_service

    if _legifrance_service is None:
        import os
        client_id = os.getenv("LEGIFRANCE_CLIENT_ID")
        client_secret = os.getenv("LEGIFRANCE_CLIENT_SECRET")

        if client_id and client_secret:
            _legifrance_service = LegifranceService(
                client_id=client_id,
                client_secret=client_secret
            )
            logger.info("legifrance_service_singleton_created")
        else:
            logger.warning("legifrance_credentials_not_configured")
            return None

    return _legifrance_service
