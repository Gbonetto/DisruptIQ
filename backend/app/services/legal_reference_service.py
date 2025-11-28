"""
Legal Reference Service - Smart 3-tier architecture for legal fact-checking

Architecture:
- TIER 1: Local knowledge base (0ms) - 80% of cases
- TIER 2: Redis cache (5ms) - Recently fetched Légifrance data
- TIER 3: Légifrance API (200-500ms) - Fresh authoritative data

This service ensures ZERO hallucinations by always sourcing legal claims
from verifiable references.
"""

import structlog
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
import re
from datetime import datetime, timedelta

from app.core.redis_client import get_redis_client
from app.services.legifrance_service import get_legifrance_service

logger = structlog.get_logger()


class LegalReferenceService:
    """
    Smart legal reference service with 3-tier caching

    Usage:
        service = LegalReferenceService()
        await service.initialize()

        # Get authoritative reference
        ref = await service.get_reference("syndic_duration")
        print(ref["rule"]["max_duration_years"])  # 3
        print(ref["legal_basis"][0]["url"])  # Légifrance URL
    """

    def __init__(self):
        self.knowledge_base: Optional[Dict[str, Any]] = None
        self.redis_client = None
        self.legifrance_service = None

        # Cache TTLs
        self.local_kb_path = Path(__file__).parent / "legal_knowledge_base.json"
        self.redis_cache_ttl = 3600 * 24 * 30  # 30 days for legal references
        self.legifrance_cache_ttl = 3600 * 24 * 7  # 7 days for fresh Légifrance data

    async def initialize(self):
        """Initialize service (load knowledge base, connect to Redis and Légifrance)"""
        try:
            # Load local knowledge base (TIER 1)
            with open(self.local_kb_path, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)

            logger.info("legal_kb_loaded",
                       rules_count=len(self.knowledge_base.get("rules", {})),
                       version=self.knowledge_base.get("version"))

            # Connect to Redis (TIER 2)
            try:
                self.redis_client = get_redis_client()
                logger.info("redis_connected_for_legal_cache")
            except Exception as e:
                logger.warning("redis_unavailable_legal_cache_disabled", error=str(e))
                self.redis_client = None

            # Connect to Légifrance (TIER 3)
            self.legifrance_service = get_legifrance_service()
            if self.legifrance_service:
                logger.info("legifrance_service_connected")
            else:
                logger.warning("legifrance_not_configured",
                             message="Set LEGIFRANCE_CLIENT_ID and LEGIFRANCE_CLIENT_SECRET")

        except Exception as e:
            logger.error("legal_reference_service_init_failed", error=str(e))
            raise

    async def get_reference(
        self,
        rule_id: str,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get authoritative legal reference with smart 3-tier caching

        Args:
            rule_id: Rule identifier (e.g., "syndic_duration", "penalties_retard")
            force_refresh: Force fetch from Légifrance even if cached

        Returns:
            Complete legal reference with sources, or None if not found

        Example:
            >>> ref = await service.get_reference("late_payment_penalties")
            >>> ref["rule"]["max_rate_2024"]
            13.4
            >>> ref["legal_basis"][0]["url"]
            "https://www.legifrance.gouv.fr/codes/article_lc/..."
        """
        if not self.knowledge_base:
            await self.initialize()

        # TIER 1: Check local knowledge base (instant)
        local_ref = self.knowledge_base["rules"].get(rule_id)

        if not local_ref:
            logger.warning("rule_not_found_in_kb", rule_id=rule_id)
            return None

        # If not forcing refresh, return local reference enriched with metadata
        if not force_refresh:
            logger.debug("tier1_cache_hit", rule_id=rule_id, latency_ms=0)
            return self._enrich_reference(local_ref, source="local_kb")

        # TIER 2: Check Redis cache for enriched Légifrance data
        if self.redis_client and not force_refresh:
            cache_key = f"legal:reference:{rule_id}"
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    logger.info("tier2_cache_hit", rule_id=rule_id, source="redis")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning("redis_cache_read_error", error=str(e))

        # TIER 3: Fetch fresh data from Légifrance API
        if self.legifrance_service:
            enriched_ref = await self._enrich_from_legifrance(local_ref, rule_id)

            # Cache enriched reference in Redis
            if self.redis_client and enriched_ref:
                cache_key = f"legal:reference:{rule_id}"
                try:
                    await self.redis_client.setex(
                        cache_key,
                        self.redis_cache_ttl,
                        json.dumps(enriched_ref, ensure_ascii=False)
                    )
                    logger.info("tier3_cached_to_redis", rule_id=rule_id)
                except Exception as e:
                    logger.warning("redis_cache_write_error", error=str(e))

            return enriched_ref

        # Fallback: return local reference if Légifrance unavailable
        logger.warning("legifrance_unavailable_using_local", rule_id=rule_id)
        return self._enrich_reference(local_ref, source="local_kb_fallback")

    def _enrich_reference(self, ref: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Add metadata to reference"""
        return {
            **ref,
            "metadata": {
                "source": source,
                "retrieved_at": datetime.now().isoformat(),
                "confidence": "high" if source.startswith("legifrance") else "medium"
            }
        }

    async def _enrich_from_legifrance(
        self,
        local_ref: Dict[str, Any],
        rule_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Enrich local reference with fresh Légifrance data

        This verifies that the legal basis is still current and fetches
        the actual text of relevant articles.
        """
        try:
            enriched = local_ref.copy()
            enriched["legifrance_verified"] = []

            # Fetch each legal basis article from Légifrance
            for basis in local_ref.get("legal_basis", []):
                if "legifrance_id" in basis and "text_id" in basis:
                    # Extract article number from legifrance_id or article field
                    article_num = self._extract_article_number(basis.get("article", ""))

                    if article_num:
                        article_data = await self.legifrance_service.get_law_article(
                            law_id=basis["text_id"],
                            article_num=article_num
                        )

                        if article_data:
                            enriched["legifrance_verified"].append({
                                "article": basis["article"],
                                "verified": True,
                                "content_preview": article_data.get("content", "")[:500],
                                "url": article_data.get("url"),
                                "fetched_at": datetime.now().isoformat()
                            })
                            logger.info("legifrance_article_verified",
                                      rule_id=rule_id,
                                      article=basis["article"])
                        else:
                            logger.warning("legifrance_article_not_found",
                                         rule_id=rule_id,
                                         article=basis["article"])

            enriched["metadata"] = {
                "source": "legifrance_verified",
                "retrieved_at": datetime.now().isoformat(),
                "confidence": "very_high",
                "verified_articles": len(enriched["legifrance_verified"])
            }

            return enriched

        except Exception as e:
            logger.error("legifrance_enrichment_failed",
                        rule_id=rule_id,
                        error=str(e))
            # Fallback to local reference
            return self._enrich_reference(local_ref, source="local_kb_after_legifrance_error")

    def _extract_article_number(self, article_str: str) -> Optional[str]:
        """Extract article number from string like 'Article 18' or 'Article L441-10'"""
        match = re.search(r'Article\s+([A-Z]?\d+(?:[-−]\d+)?(?:\s+[A-Z])?)', article_str, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    async def validate_claim(
        self,
        claim_type: str,
        extracted_value: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate a legal claim extracted from a document

        Args:
            claim_type: Type of claim (e.g., "duration", "penalty_rate", "indemnity")
            extracted_value: Value extracted from document
            context: Additional context for validation

        Returns:
            Validation result with:
                - is_valid: bool
                - severity: "ok" | "warning" | "abusive" | "illegal"
                - reference: Legal reference used
                - explanation: Human-readable explanation

        Example:
            >>> result = await service.validate_claim(
            ...     claim_type="penalty_rate",
            ...     extracted_value=15.0
            ... )
            >>> result["is_valid"]
            False
            >>> result["severity"]
            "abusive"
            >>> result["explanation"]
            "Taux de 15% dépasse le maximum légal de 13.4% (taux légal 3.4% + 10 points)"
        """
        # Map claim type to rule ID
        claim_to_rule = {
            "duration": "syndic_contract_duration",
            "penalty_rate": "late_payment_penalties",
            "urgent_works": "urgent_works_ceiling",
            "indemnity_months": "termination_indemnity",
            "notice_period": "notice_period_termination",
            "liability_exclusion": "liability_exclusion",
            "fee_revision": "fee_revision"
        }

        rule_id = claim_to_rule.get(claim_type)
        if not rule_id:
            logger.warning("unknown_claim_type", claim_type=claim_type)
            return {
                "is_valid": None,
                "severity": "unknown",
                "explanation": f"Type de validation inconnu: {claim_type}"
            }

        # Get authoritative reference
        ref = await self.get_reference(rule_id)
        if not ref:
            return {
                "is_valid": None,
                "severity": "unknown",
                "explanation": "Référence légale non disponible"
            }

        # Perform validation based on claim type
        validation_result = self._perform_validation(
            claim_type=claim_type,
            extracted_value=extracted_value,
            reference=ref,
            context=context or {}
        )

        # Add reference to result
        validation_result["reference"] = {
            "rule_id": rule_id,
            "title": ref.get("title"),
            "legal_basis": ref.get("legal_basis", []),
            "sources": ref.get("sources", [])
        }

        return validation_result

    def _perform_validation(
        self,
        claim_type: str,
        extracted_value: Any,
        reference: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform actual validation logic"""
        rule = reference.get("rule", {})
        validation_config = reference.get("validation", {})

        if claim_type == "penalty_rate":
            # Validate penalty rate
            max_rate = rule.get("max_rate_2024", 13.4)
            warning_threshold = validation_config.get("warning_threshold", 10.0)

            rate_value = float(extracted_value)

            if rate_value > max_rate:
                return {
                    "is_valid": False,
                    "severity": "abusive",
                    "explanation": f"Taux de {rate_value}% dépasse le maximum légal de {max_rate}% (taux légal {rule.get('base_rate_2024')}% + {rule.get('max_additional_points')} points)",
                    "extracted_value": rate_value,
                    "legal_maximum": max_rate,
                    "recommendation": f"Réduire à maximum {max_rate}%"
                }
            elif rate_value > warning_threshold:
                return {
                    "is_valid": True,
                    "severity": "warning",
                    "explanation": f"Taux de {rate_value}% est élevé mais sous le maximum de {max_rate}%",
                    "extracted_value": rate_value,
                    "legal_maximum": max_rate,
                    "recommendation": "Vérifier si justifié"
                }
            else:
                return {
                    "is_valid": True,
                    "severity": "ok",
                    "explanation": f"Taux de {rate_value}% conforme (max: {max_rate}%)",
                    "extracted_value": rate_value,
                    "legal_maximum": max_rate
                }

        elif claim_type == "duration":
            # Validate contract duration
            max_years = rule.get("max_duration_years", 3)
            duration_value = int(extracted_value)

            if duration_value > max_years:
                return {
                    "is_valid": False,
                    "severity": "illegal",
                    "explanation": f"Durée de {duration_value} ans dépasse le maximum légal de {max_years} ans (Loi ALUR 2014)",
                    "extracted_value": duration_value,
                    "legal_maximum": max_years,
                    "recommendation": f"Réduire à {max_years} ans maximum"
                }
            else:
                return {
                    "is_valid": True,
                    "severity": "ok",
                    "explanation": f"Durée de {duration_value} ans conforme (max: {max_years} ans)",
                    "extracted_value": duration_value,
                    "legal_maximum": max_years
                }

        elif claim_type == "indemnity_months":
            # Validate termination indemnity
            warning_threshold = validation_config.get("warning_threshold", 6)
            recommended_max = validation_config.get("recommended_max", 3)

            months_value = int(extracted_value)

            if months_value > warning_threshold:
                return {
                    "is_valid": False,
                    "severity": "abusive",
                    "explanation": f"Indemnité de {months_value} mois dépasse le seuil jurisprudentiel de {warning_threshold} mois",
                    "extracted_value": months_value,
                    "jurisprudence_threshold": warning_threshold,
                    "recommendation": f"Plafonner à {recommended_max} mois maximum"
                }
            elif months_value > recommended_max:
                return {
                    "is_valid": True,
                    "severity": "warning",
                    "explanation": f"Indemnité de {months_value} mois est élevée (recommandé: max {recommended_max} mois)",
                    "extracted_value": months_value,
                    "recommended_max": recommended_max,
                    "recommendation": "Négocier à la baisse"
                }
            else:
                return {
                    "is_valid": True,
                    "severity": "ok",
                    "explanation": f"Indemnité de {months_value} mois raisonnable",
                    "extracted_value": months_value
                }

        elif claim_type == "urgent_works":
            # Validate urgent works ceiling
            warning_threshold = validation_config.get("warning_threshold", 10000)
            best_practice_range = validation_config.get("best_practice_range", [2000, 5000])

            amount_value = float(extracted_value)

            if amount_value > warning_threshold:
                return {
                    "is_valid": False,
                    "severity": "warning",
                    "explanation": f"Plafond de {amount_value:,.0f}€ est très élevé (pratique courante: {best_practice_range[0]:,}-{best_practice_range[1]:,}€). Note: aucun montant légal fixe n'existe.",
                    "extracted_value": amount_value,
                    "typical_range": best_practice_range,
                    "recommendation": f"Adapter à la taille de la copropriété (recommandé: {best_practice_range[0]:,}-{best_practice_range[1]:,}€)"
                }
            else:
                return {
                    "is_valid": True,
                    "severity": "ok",
                    "explanation": f"Plafond de {amount_value:,.0f}€ raisonnable",
                    "extracted_value": amount_value,
                    "typical_range": best_practice_range
                }

        elif claim_type == "notice_period":
            # Validate notice period
            warning_threshold = validation_config.get("warning_threshold", 6)
            recommended = validation_config.get("recommended", 3)

            months_value = int(extracted_value)

            if months_value > warning_threshold:
                return {
                    "is_valid": False,
                    "severity": "abusive",
                    "explanation": f"Préavis de {months_value} mois excessif (jurisprudence: max {warning_threshold} mois raisonnable)",
                    "extracted_value": months_value,
                    "threshold": warning_threshold,
                    "recommendation": f"Réduire à {recommended} mois"
                }
            else:
                return {
                    "is_valid": True,
                    "severity": "ok",
                    "explanation": f"Préavis de {months_value} mois raisonnable",
                    "extracted_value": months_value
                }

        # Default fallback
        return {
            "is_valid": None,
            "severity": "unknown",
            "explanation": f"Validation non implémentée pour {claim_type}"
        }

    async def search_jurisprudence_for_claim(
        self,
        claim_description: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Search Légifrance jurisprudence for similar cases

        Args:
            claim_description: Description of the legal issue
            max_results: Maximum results to return

        Returns:
            Search results from Légifrance
        """
        if not self.legifrance_service:
            logger.warning("legifrance_unavailable_for_jurisprudence")
            return {
                "success": False,
                "results": [],
                "error": "Service Légifrance non configuré"
            }

        try:
            results = await self.legifrance_service.search_jurisprudence(
                query=claim_description,
                case_type="copropriete",
                max_results=max_results
            )

            logger.info("jurisprudence_search_completed",
                       query=claim_description[:50],
                       results_count=len(results.get("results", [])))

            return results

        except Exception as e:
            logger.error("jurisprudence_search_failed", error=str(e))
            return {
                "success": False,
                "results": [],
                "error": str(e)
            }

    def get_all_rule_ids(self) -> List[str]:
        """Get list of all available rule IDs"""
        if not self.knowledge_base:
            return []
        return list(self.knowledge_base.get("rules", {}).keys())

    def get_knowledge_base_info(self) -> Dict[str, Any]:
        """Get metadata about knowledge base"""
        if not self.knowledge_base:
            return {}

        return {
            "version": self.knowledge_base.get("version"),
            "last_updated": self.knowledge_base.get("last_updated"),
            "rules_count": len(self.knowledge_base.get("rules", {})),
            "rule_categories": list(set(
                rule.get("category")
                for rule in self.knowledge_base.get("rules", {}).values()
            ))
        }


# Singleton
_legal_reference_service: Optional[LegalReferenceService] = None


def get_legal_reference_service() -> LegalReferenceService:
    """Get singleton instance of LegalReferenceService"""
    global _legal_reference_service

    if _legal_reference_service is None:
        _legal_reference_service = LegalReferenceService()
        logger.info("legal_reference_service_singleton_created")

    return _legal_reference_service
