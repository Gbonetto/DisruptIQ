"""
Response Fusion Agent - Intelligently merge SQL and RAG results

This agent takes results from both SQL and RAG agents and:
1. Detects contradictions between sources
2. Synthesizes a coherent response
3. Formats with proper source attribution [SQL] and [1], [2]
4. Enriches SQL facts with RAG context

Fusion strategies:
- ENRICHMENT: SQL provides facts, RAG adds context/details
- VALIDATION: Cross-check SQL data against documents
- COMPLEMENTARY: SQL and RAG answer different aspects
"""

import structlog
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from app.services.llm_service import LLMService
from .hybrid_executor import HybridResult, SQLResult, RAGResult

logger = structlog.get_logger()


class FusedResponse(BaseModel):
    """Fused response combining SQL and RAG"""
    text: str  # Final formatted response
    has_contradictions: bool
    contradiction_note: Optional[str] = None
    fusion_strategy: str  # "enrichment", "validation", "complementary"
    sources: List[Dict[str, Any]] = []  # Includes both [SQL] and [1], [2] etc.
    confidence: float = 0.0


class ResponseFusionAgent:
    """
    Fuses SQL and RAG results into coherent response

    Core principle: Maximize value from both structured and unstructured data
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("response_fusion_agent_initialized")

    async def fuse_responses(
        self,
        query: str,
        hybrid_result: HybridResult
    ) -> FusedResponse:
        """
        Main fusion method

        Args:
            query: Original user question
            hybrid_result: Results from hybrid executor

        Returns:
            FusedResponse with intelligently merged content
        """
        try:
            # Case 1: Only SQL
            if hybrid_result.has_sql and not hybrid_result.has_rag:
                return await self._format_sql_only(query, hybrid_result.sql_result)

            # Case 2: Only RAG
            elif hybrid_result.has_rag and not hybrid_result.has_sql:
                return await self._format_rag_only(query, hybrid_result.rag_result)

            # Case 3: Both (FUSION)
            elif hybrid_result.has_sql and hybrid_result.has_rag:
                return await self._fuse_both(query, hybrid_result.sql_result, hybrid_result.rag_result)

            # Case 4: Neither (empty)
            else:
                return FusedResponse(
                    text="Je n'ai trouvé aucune information pertinente pour répondre à votre question.",
                    has_contradictions=False,
                    fusion_strategy="empty",
                    confidence=0.0
                )

        except Exception as e:
            logger.error("fusion_failed", error=str(e), exc_info=True)
            return FusedResponse(
                text=f"Erreur lors de la fusion des résultats : {str(e)}",
                has_contradictions=False,
                fusion_strategy="error",
                confidence=0.0
            )

    async def _format_sql_only(
        self,
        query: str,
        sql_result: SQLResult
    ) -> FusedResponse:
        """Format SQL-only response"""
        if not sql_result or not sql_result.success:
            return FusedResponse(
                text="Aucune donnée trouvée dans la base de données.",
                has_contradictions=False,
                fusion_strategy="sql_only",
                confidence=0.0
            )

        # Format SQL results
        results = sql_result.data.get("results", [])

        if not results:
            return FusedResponse(
                text="Aucune donnée trouvée dans la base de données.",
                has_contradictions=False,
                fusion_strategy="sql_only",
                confidence=0.0
            )

        # Use LLM to format nicely
        formatted_text = await self._format_sql_results(query, results)

        # Add source footer
        formatted_text += "\n\n---\n📊 **Source** : Base de données DisruptIQ[SQL]"

        return FusedResponse(
            text=formatted_text,
            has_contradictions=False,
            fusion_strategy="sql_only",
            sources=[{"type": "sql", "name": "Base de données DisruptIQ"}],
            confidence=1.0  # SQL data is always reliable
        )

    async def _format_rag_only(
        self,
        query: str,
        rag_result: RAGResult
    ) -> FusedResponse:
        """Format RAG-only response (already formatted by synthesis_agent)"""
        if not rag_result or not rag_result.success:
            return FusedResponse(
                text="Aucun document pertinent trouvé.",
                has_contradictions=False,
                fusion_strategy="rag_only",
                confidence=0.0
            )

        # RAG response is already well-formatted with citations
        return FusedResponse(
            text=rag_result.message,
            has_contradictions=rag_result.data.get("has_contradictions", False),
            fusion_strategy="rag_only",
            sources=rag_result.sources,
            confidence=rag_result.confidence
        )

    async def _fuse_both(
        self,
        query: str,
        sql_result: SQLResult,
        rag_result: RAGResult
    ) -> FusedResponse:
        """
        Fusion strategy when both SQL and RAG have results

        This is where the magic happens! 🎩✨
        """
        logger.info("fusing_sql_and_rag",
                   query=query[:50],
                   sql_rows=sql_result.rows_returned,
                   rag_chunks=rag_result.chunks_retrieved)

        # Extract data
        sql_data = sql_result.data.get("results", [])
        rag_text = rag_result.message
        rag_sources = rag_result.sources

        # Determine fusion strategy
        strategy = self._determine_fusion_strategy(query, sql_data, rag_text)

        logger.info("fusion_strategy_determined", strategy=strategy)

        # Execute fusion based on strategy
        if strategy == "enrichment":
            fused = await self._fusion_enrichment(query, sql_data, rag_text, rag_sources)
        elif strategy == "validation":
            fused = await self._fusion_validation(query, sql_data, rag_text, rag_sources)
        else:  # complementary
            fused = await self._fusion_complementary(query, sql_data, rag_text, rag_sources)

        return fused

    def _determine_fusion_strategy(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str
    ) -> str:
        """
        Determine which fusion strategy to use

        Strategies:
        - ENRICHMENT: SQL has facts, RAG adds details
          Example: "Tarif du plombier ?" → SQL: 80€, RAG: conditions contrat

        - VALIDATION: Cross-check SQL against RAG
          Example: "Contact du plombier" → SQL: email, RAG: email dans contrat

        - COMPLEMENTARY: SQL and RAG answer different aspects
          Example: "Budget Les Mimosas" → SQL: montant, RAG: détails PDF
        """
        query_lower = query.lower()

        # Enrichment indicators
        enrichment_keywords = ["tarif", "prix", "coût", "combien facture"]
        if any(kw in query_lower for kw in enrichment_keywords):
            return "enrichment"

        # Validation indicators
        validation_keywords = ["contact", "email", "téléphone", "adresse"]
        if any(kw in query_lower for kw in validation_keywords):
            return "validation"

        # Default: complementary
        return "complementary"

    async def _fusion_enrichment(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str,
        rag_sources: List[Dict]
    ) -> FusedResponse:
        """
        Enrichment fusion: SQL provides facts, RAG adds context

        Example:
        SQL: "tarif_horaire: 80€"
        RAG: "Tarif week-end 120€, minimum 2h, frais déplacement 25€"

        Result: Combine both with proper attribution
        """
        # Format SQL data
        sql_formatted = await self._format_sql_results(query, sql_data)

        # Build fusion prompt
        prompt = f"""Tu dois fusionner ces informations de deux sources différentes pour répondre à : "{query}"

**Source 1 - Base de données (SQL)** :
{sql_formatted}

**Source 2 - Documents (RAG)** :
{rag_text}

INSTRUCTIONS :
1. Commence par les faits de la base de données[SQL]
2. Enrichis avec les détails des documents (garde les citations [1], [2])
3. Indique clairement quelle info vient d'où : [SQL] ou [1], [2]
4. Format markdown professionnel

Réponds directement avec la réponse fusionnée."""

        fused_text = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.2,
            max_tokens=800
        )

        # Add sources footer
        sources_footer = self._build_sources_footer(rag_sources, include_sql=True)
        fused_text += sources_footer

        # Detect contradictions
        contradictions = await self._detect_contradictions_sql_rag(sql_data, rag_text)

        return FusedResponse(
            text=fused_text,
            has_contradictions=contradictions is not None,
            contradiction_note=contradictions,
            fusion_strategy="enrichment",
            sources=[{"type": "sql", "name": "Base de données"}] + rag_sources,
            confidence=(1.0 + rag_sources[0]["confidence"]) / 2 if rag_sources else 0.9
        )

    async def _fusion_validation(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str,
        rag_sources: List[Dict]
    ) -> FusedResponse:
        """
        Validation fusion: Cross-check SQL data against documents

        Example:
        SQL: "email: jean@plomberie.fr"
        RAG: "Contact : contact@plomberie-cannes.fr"

        Result: Show both + warning if different
        """
        sql_formatted = await self._format_sql_results(query, sql_data)

        # Detect contradictions explicitly
        contradictions = await self._detect_contradictions_sql_rag(sql_data, rag_text)

        prompt = f"""Compare ces informations et signale les différences : "{query}"

**Base de données (SQL)** :
{sql_formatted}

**Documents (RAG)** :
{rag_text}

INSTRUCTIONS :
1. Présente les deux sources clairement
2. Si divergences, signale avec ⚠️
3. Suggère quelle source est probablement à jour
4. Garde les citations [SQL] et [1], [2]

Réponds :"""

        fused_text = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.2,
            max_tokens=600
        )

        # Add sources footer
        sources_footer = self._build_sources_footer(rag_sources, include_sql=True)
        fused_text += sources_footer

        return FusedResponse(
            text=fused_text,
            has_contradictions=contradictions is not None,
            contradiction_note=contradictions,
            fusion_strategy="validation",
            sources=[{"type": "sql", "name": "Base de données"}] + rag_sources,
            confidence=0.8  # Lower confidence when validating
        )

    async def _fusion_complementary(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str,
        rag_sources: List[Dict]
    ) -> FusedResponse:
        """
        Complementary fusion: SQL and RAG answer different aspects

        Example:
        Query: "Procédure dégât des eaux pour Les Mimosas"
        SQL: Contacts spécifiques copropriété (syndic, assurance)
        RAG: Procédure générale étapes

        Result: Combine both to create personalized response
        """
        sql_formatted = await self._format_sql_results(query, sql_data)

        prompt = f"""Combine ces informations complémentaires pour répondre à : "{query}"

**Données de la copropriété (SQL)** :
{sql_formatted}

**Procédure générale (Documents)** :
{rag_text}

INSTRUCTIONS :
1. Utilise la procédure des documents[1]
2. Personnalise avec les données spécifiques[SQL]
3. Crée une réponse actionnable et complète
4. Garde toutes les citations [SQL], [1], [2]

Réponds :"""

        fused_text = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1000
        )

        # Add sources footer
        sources_footer = self._build_sources_footer(rag_sources, include_sql=True)
        fused_text += sources_footer

        return FusedResponse(
            text=fused_text,
            has_contradictions=False,
            fusion_strategy="complementary",
            sources=[{"type": "sql", "name": "Base de données"}] + rag_sources,
            confidence=0.95
        )

    async def _format_sql_results(
        self,
        query: str,
        results: List[Dict]
    ) -> str:
        """Format SQL results nicely using LLM"""
        if not results:
            return "Aucune donnée"

        # Prepare results for prompt
        results_str = "\n".join([str(row) for row in results[:10]])  # Limit to 10 rows

        prompt = f"""Formate ces résultats de base de données de manière claire pour répondre à : "{query}"

DONNÉES :
{results_str}

INSTRUCTIONS :
- Format lisible et professionnel
- Mets en valeur les informations importantes avec **gras**
- Si liste : utilise format markdown
- Concis et direct

Réponds uniquement avec les données formatées :"""

        try:
            formatted = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.2,
                max_tokens=400
            )
            return formatted.strip()
        except Exception as e:
            logger.error("sql_formatting_failed", error=str(e))
            # Fallback: simple format
            return "\n".join([f"- {row}" for row in results[:5]])

    async def _detect_contradictions_sql_rag(
        self,
        sql_data: List[Dict],
        rag_text: str
    ) -> Optional[str]:
        """Detect contradictions between SQL and RAG"""
        if not sql_data:
            return None

        sql_str = "\n".join([str(row) for row in sql_data[:5]])

        prompt = f"""Compare ces deux sources et détecte les CONTRADICTIONS :

**Source SQL (base de données)** :
{sql_str}

**Source RAG (documents)** :
{rag_text}

Si contradiction : explique-la brièvement.
Si cohérent : réponds "COHERENT"

Réponds :"""

        try:
            result = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=200
            )

            if "COHERENT" in result.upper():
                return None
            else:
                return result.strip()

        except Exception as e:
            logger.error("contradiction_detection_failed", error=str(e))
            return None

    def _build_sources_footer(
        self,
        rag_sources: List[Dict],
        include_sql: bool = False
    ) -> str:
        """Build sources footer with [SQL] and [1], [2] etc."""
        footer_parts = ["\n\n---\n📚 **Sources** :"]

        # Add RAG sources [1], [2], [3]
        for source in rag_sources:
            source_id = source.get("id", "?")
            title = source.get("title", "Document")
            page = source.get("page")
            confidence = source.get("confidence", 0)

            page_info = f" (page {page})" if page else ""
            confidence_pct = int(confidence * 100)

            footer_parts.append(
                f"\n[{source_id}] **{title}**{page_info} - {confidence_pct}%"
            )

        # Add SQL source
        if include_sql:
            footer_parts.append("\n[SQL] **Base de données DisruptIQ** - 100%")

        return "".join(footer_parts)
