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

        # Extract table names for source metadata
        tables = sql_result.tables if hasattr(sql_result, 'tables') else []
        sql_source = {
            "type": "sql",
            "name": "Base de données DisruptIQ",
            "tables": tables  # Include table names for frontend display
        }

        return FusedResponse(
            text=formatted_text,
            has_contradictions=False,
            fusion_strategy="sql_only",
            sources=[sql_source],
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
        sql_tables = sql_result.tables  # Extract table names from SQLResult
        rag_text = rag_result.message
        rag_sources = rag_result.sources

        # CRITICAL: Extract raw chunks to avoid losing details in synthesis
        # The synthesis_agent might filter out important biographical details
        rag_raw_chunks = []
        if rag_result.data and "chunks" in rag_result.data:
            rag_raw_chunks = rag_result.data.get("chunks", [])
            logger.info("fusion_using_raw_chunks", chunk_count=len(rag_raw_chunks))

        # Determine fusion strategy
        strategy = self._determine_fusion_strategy(query, sql_data, rag_text)

        logger.info("fusion_strategy_determined", strategy=strategy)

        # Execute fusion based on strategy
        if strategy == "enrichment":
            fused = await self._fusion_enrichment(query, sql_data, rag_text, rag_sources, rag_raw_chunks, sql_tables)
        elif strategy == "validation":
            fused = await self._fusion_validation(query, sql_data, rag_text, rag_sources, rag_raw_chunks, sql_tables)
        else:  # complementary
            fused = await self._fusion_complementary(query, sql_data, rag_text, rag_sources, rag_raw_chunks, sql_tables)

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
          Example: "Qui est Laurent Moussu ?" → SQL: profession/contact, RAG: détails biographiques

        - VALIDATION: Cross-check SQL against RAG
          Example: "Contact du plombier" → SQL: email, RAG: email dans contrat

        - COMPLEMENTARY: SQL and RAG answer different aspects
          Example: "Budget Les Mimosas" → SQL: montant, RAG: détails PDF
        """
        query_lower = query.lower()

        # Enrichment indicators - Questions requiring both SQL facts + RAG details
        enrichment_keywords = [
            "tarif", "prix", "coût", "combien facture",
            "qui est", "c'est qui", "c'est quoi",  # Biographical/entity questions
            "quel age", "quelle age", "quel âge", "quelle âge",  # Age questions
            "quand est né", "date de naissance",  # Birth date questions
            "profession de", "métier de", "travail de",  # Profession questions
            "habite où", "domicile de", "adresse de"  # Address questions (but not standalone "adresse")
        ]
        if any(kw in query_lower for kw in enrichment_keywords):
            return "enrichment"

        # Validation indicators
        validation_keywords = ["contact", "email", "téléphone", "adresse"]
        # Only use validation if not already caught by enrichment (e.g., "adresse de X" vs "adresse")
        if any(kw in query_lower for kw in validation_keywords):
            return "validation"

        # Default: complementary
        return "complementary"

    async def _fusion_enrichment(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str,
        rag_sources: List[Dict],
        rag_raw_chunks: List[Dict] = [],
        sql_tables: List[str] = []
    ) -> FusedResponse:
        """
        Enrichment fusion: SQL provides facts, RAG adds context

        Example:
        SQL: "tarif_horaire: 80€"
        RAG: "Tarif week-end 120€, minimum 2h, frais déplacement 25€"

        Example:
        SQL: "Laurent Moussu - LOLO Corp - lolo@repas.com"
        RAG: "Laurent MOUSSU, né le 14 avril 1981, paysagiste indépendant, 12 Chemin des Oliviers..."

        Result: Combine both with proper attribution, giving equal weight to both sources
        """
        # Format SQL data
        sql_formatted = await self._format_sql_results(query, sql_data)

        # CRITICAL: Use raw chunks instead of synthesis to preserve ALL details
        # The synthesis might filter out important biographical/contractual details
        if rag_raw_chunks:
            # Extract text from raw chunks (they contain full, unfiltered content)
            raw_texts = []
            for chunk in rag_raw_chunks[:5]:  # Limit to top 5 chunks
                if isinstance(chunk, dict) and "text" in chunk:
                    raw_texts.append(chunk["text"])
                elif isinstance(chunk, dict) and "content" in chunk:
                    raw_texts.append(chunk["content"])

            if raw_texts:
                rag_content = "\n\n---\n\n".join(raw_texts)
                logger.info("fusion_using_raw_content", total_chars=len(rag_content))
            else:
                rag_content = rag_text  # Fallback to synthesis
                logger.warning("fusion_no_text_in_chunks_fallback_to_synthesis")
        else:
            rag_content = rag_text  # Fallback if no raw chunks
            logger.warning("fusion_no_raw_chunks_using_synthesis")

        # Build fusion prompt
        prompt = f"""Tu dois créer une réponse COMPLÈTE en combinant TOUTES les informations de ces deux sources pour : "{query}"

**Source 1 - Base de données (SQL)** :
{sql_formatted}

**Source 2 - Documents (CONTENU BRUT COMPLET)** :
{rag_content}

RÈGLES STRICTES :
1. Tu DOIS inclure TOUTES les informations présentes dans les deux sources
2. Pour une question biographique ("qui est X"), tu DOIS mentionner :
   - Nom complet, date/lieu de naissance si disponible (depuis documents)
   - Profession/métier détaillé (depuis documents)
   - Adresse complète (depuis documents)
   - Entreprise/activité actuelle (depuis SQL)
   - Contact (email, téléphone) (depuis SQL)
   - Tout autre détail pertinent des deux sources
3. SIMPLIFIE : Ne liste QUE les informations DISPONIBLES - n'écris PAS "Non disponible" pour chaque champ manquant
4. Indique la source UNIQUEMENT avec [SQL] pour les données de la base - NE METS PAS [1] [2] [3] car les documents ont déjà leurs citations
5. FORMAT : Réponds en TEXTE NATUREL sous forme de paragraphes fluides et lisibles - PAS de symboles markdown (##, **, etc.)
6. ⚠️ N'INVENTE AUCUNE information manquante
7. ❌ NE CRÉE PAS de section "Sources documentaires" ou "Sources" - les sources sont déjà affichées automatiquement

Crée une réponse exhaustive en texte naturel qui combine la richesse des documents avec les données structurées."""

        fused_text = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.2,
            max_tokens=1200  # Increased for more detailed biographical responses
        )

        # DON'T add sources footer - sources are already shown in the frontend widget
        # sources_footer = self._build_sources_footer(rag_sources, include_sql=True)
        # fused_text += sources_footer

        # Detect contradictions
        contradictions = await self._detect_contradictions_sql_rag(sql_data, rag_text)

        # Build SQL source with table names
        sql_source = {"type": "sql", "name": "Base de données"}
        if sql_tables:
            sql_source["tables"] = sql_tables

        return FusedResponse(
            text=fused_text,
            has_contradictions=contradictions is not None,
            contradiction_note=contradictions,
            fusion_strategy="enrichment",
            sources=[sql_source] + rag_sources,
            confidence=(1.0 + rag_sources[0]["confidence"]) / 2 if rag_sources else 0.9
        )

    async def _fusion_validation(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str,
        rag_sources: List[Dict],
        rag_raw_chunks: List[Dict] = [],
        sql_tables: List[str] = []
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

        # Build SQL source with table names
        sql_source = {"type": "sql", "name": "Base de données"}
        if sql_tables:
            sql_source["tables"] = sql_tables

        return FusedResponse(
            text=fused_text,
            has_contradictions=contradictions is not None,
            contradiction_note=contradictions,
            fusion_strategy="validation",
            sources=[sql_source] + rag_sources,
            confidence=0.8  # Lower confidence when validating
        )

    async def _fusion_complementary(
        self,
        query: str,
        sql_data: List[Dict],
        rag_text: str,
        rag_sources: List[Dict],
        rag_raw_chunks: List[Dict] = [],
        sql_tables: List[str] = []
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

        # Build SQL source with table names
        sql_source = {"type": "sql", "name": "Base de données"}
        if sql_tables:
            sql_source["tables"] = sql_tables

        return FusedResponse(
            text=fused_text,
            has_contradictions=False,
            fusion_strategy="complementary",
            sources=[sql_source] + rag_sources,
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

        # SECURITY: Filter out internal/technical columns that shouldn't be exposed to LLM
        # These columns are for internal use only and should NOT be interpreted as business data
        excluded_columns = {'created_at', 'updated_at', 'deleted_at', 'id', 'password', 'password_hash'}

        # Clean results by removing excluded columns and formatting phone numbers
        cleaned_results = []
        for row in results[:10]:  # Limit to 10 rows
            cleaned_row = {}
            for k, v in row.items():
                if k in excluded_columns:
                    continue
                # Format phone numbers (numeric fields with 'phone' or 'telephone' in name)
                if v is not None and ('phone' in k.lower() or 'telephone' in k.lower() or 'tel' in k.lower()):
                    # Convert float to int then to string to remove decimals
                    if isinstance(v, (int, float)):
                        cleaned_row[k] = str(int(v))
                    else:
                        cleaned_row[k] = str(v)
                else:
                    cleaned_row[k] = v
            cleaned_results.append(cleaned_row)

        results_str = "\n".join([str(row) for row in cleaned_results])

        prompt = f"""Formate ces résultats de base de données de manière claire pour répondre à : "{query}"

DONNÉES :
{results_str}

⚠️ RÈGLES CRITIQUES :
- N'INVENTE AUCUNE information qui n'est pas dans les données
- Si une information n'est pas disponible, écris explicitement "Non renseigné" ou "Non disponible"
- NE SUPPOSE PAS de dates, d'âges, ou d'autres informations manquantes
- Format lisible et professionnel avec **gras** pour les informations importantes
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
