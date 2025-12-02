"""
Synthesis Agent - RAG v2.0
Generates responses with inline citations and multi-document synthesis

Key features:
- Inline citations [1], [2], [3]
- Multi-document information fusion
- Contradiction detection
- Confidence scoring per statement
- Source traceability
"""

import re
import structlog
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime
import uuid
from app.services.llm_service import LLMService
# TODO: Re-enable table generation when service is available
# from app.services.table_generation_service import TableGenerationService
# from app.api.endpoints.export import cache_table_data

logger = structlog.get_logger()


class Source(BaseModel):
    """Document source with metadata"""
    id: int  # Citation number [1], [2], etc.
    document_id: int
    title: str
    page: Optional[int] = None
    excerpt: str  # First 200 chars of chunk
    confidence: float  # Reranked score (0-1)
    chunk_text: str  # Full chunk text
    rrf_score: Optional[float] = None  # Reciprocal Rank Fusion score
    cross_encoder_score: Optional[float] = None  # Cross-encoder re-ranking score
    vector_score: Optional[float] = None  # Original vector similarity score


class CitedSentence(BaseModel):
    """Sentence with citation tracking"""
    text: str
    source_ids: List[int]  # [1, 2] means cited from sources 1 and 2
    has_citation: bool
    is_factual: bool  # True if contains factual claim


class SynthesizedResponse(BaseModel):
    """Complete response with citations"""
    text: str  # Full response with inline citations [N]
    sources: List[Source]
    sentences: List[CitedSentence]
    has_contradictions: bool
    contradiction_note: Optional[str] = None
    overall_confidence: float
    warnings: List[str] = []

    def get_factual_sentences(self) -> List[CitedSentence]:
        """Get only factual sentences (exclude greetings, transitions)"""
        return [s for s in self.sentences if s.is_factual]

    def add_warnings(self, warnings: List[str]):
        """Add validation warnings"""
        self.warnings.extend(warnings)


class SynthesisAgent:
    """
    Synthesis Agent - Generates coherent responses with inline citations

    This agent:
    1. Receives ranked chunks from retrieval/reranking
    2. Synthesizes coherent answer using LLM
    3. Ensures every factual claim is cited [N]
    4. Detects contradictions between sources
    5. Formats output with discrete source list at bottom
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("synthesis_agent_initialized")

    async def synthesize_with_citations(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        conversation_context: Optional[str] = None,
        is_procedural: bool = False
    ) -> SynthesizedResponse:
        """
        Main synthesis method with inline citations

        Args:
            query: User's question
            chunks: Retrieved and reranked chunks with scores
            conversation_context: Optional conversation history
            is_procedural: True if query asks for steps/procedure

        Returns:
            SynthesizedResponse with text, sources, and metadata
        """
        try:
            # Step 1: Prepare numbered sources
            sources = self._prepare_sources(chunks)

            if not sources:
                return await self._generate_empty_response_smart(query)

            # Step 2: Detect contradictions
            contradictions = await self._detect_contradictions(sources)

            # Step 3: Build synthesis prompt
            prompt = self._build_citation_prompt(
                query=query,
                sources=sources,
                context=conversation_context,
                is_procedural=is_procedural,
                contradictions=contradictions
            )

            # Step 4: Generate response with LLM
            logger.info("generating_synthesis", query=query[:50], num_sources=len(sources))

            response_text = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.2,  # Low temperature for factual accuracy
                max_tokens=800
            )

            # Step 5: Check if table was requested and generate if needed
            if self._detect_table_request(query):
                table_html = await self._generate_table_from_response(response_text, sources, query)
                if table_html:
                    response_text += f"\n\n{table_html}"

            # Step 6: Parse citations and sentences
            sentences = self._parse_sentences_with_citations(response_text)

            # Step 7: Format final response with IEEE citations, CoT, and professional markdown
            formatted_text = self._format_response_with_sources(response_text, sources, enable_cot=True)

            # Step 7: Compute overall confidence
            overall_confidence = self._compute_overall_confidence(sources, sentences)

            logger.info(
                "synthesis_completed",
                query=query[:50],
                num_sources=len(sources),
                num_sentences=len(sentences),
                confidence=overall_confidence,
                has_contradictions=contradictions is not None
            )

            return SynthesizedResponse(
                text=formatted_text,
                sources=sources,
                sentences=sentences,
                has_contradictions=contradictions is not None,
                contradiction_note=contradictions,
                overall_confidence=overall_confidence
            )

        except Exception as e:
            logger.error("synthesis_failed", error=str(e), exc_info=True)
            # Return fallback response
            return self._generate_fallback_response(query, chunks)

    def _prepare_sources(self, chunks: List[Dict[str, Any]]) -> List[Source]:
        """
        Convert chunks to numbered sources for citation

        Args:
            chunks: Raw chunks with metadata and scores

        Returns:
            List of Source objects numbered 1, 2, 3...
        """
        sources = []

        for i, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata", {})

            # Extract title (prefer original_filename over title)
            title = metadata.get("original_filename") or metadata.get("title", "Document")

            # Remove .pdf extension if present
            if title.endswith(".pdf"):
                title = title[:-4]

            source = Source(
                id=i,
                document_id=chunk.get("document_id", 0),
                title=title,
                page=metadata.get("page"),
                excerpt=chunk.get("text", "")[:200],
                confidence=chunk.get("score", 0.0),
                chunk_text=chunk.get("text", ""),
                rrf_score=chunk.get("rrf_score"),
                cross_encoder_score=chunk.get("cross_encoder_score"),
                vector_score=chunk.get("score", 0.0)  # Original vector score
            )
            sources.append(source)

        logger.debug("sources_prepared", count=len(sources))
        return sources

    def _build_citation_prompt(
        self,
        query: str,
        sources: List[Source],
        context: Optional[str],
        is_procedural: bool,
        contradictions: Optional[str]
    ) -> str:
        """
        Build synthesis prompt with strict citation instructions

        Args:
            query: User question
            sources: Numbered sources
            context: Conversation context
            is_procedural: True if asking for steps
            contradictions: Detected contradictions between sources

        Returns:
            Prompt string
        """
        # Format sources for prompt
        sources_text = self._format_sources_for_prompt(sources)

        # Base rules with Chain-of-Thought
        base_rules = """
CONSIGNES DE RÉPONSE :
1. **Chain-of-Thought (CoT)** :
   - Commence par réfléchir dans <thinking>...</thinking>
   - Explique ton raisonnement étape par étape (style Deepseek)
   - Analyse : Que demande l'utilisateur ? Quelles sources sont pertinentes ?
   - Synthèse : Comment structurer la réponse optimale ?

2. **Réponse finale** (après le </thinking>) :
   - Utilise un markdown sobre et élégant
   - Structure avec ##, **, listes à puces/numéros selon besoin
   - Cite chaque affirmation factuelle avec [N]
   - N'ajoute AUCUNE section "Sources :" ou "📄" - sera géré automatiquement
   - N'ajoute AUCUN titre comme "Factures dans votre contrat" - juste la réponse directe

3. **Citations IEEE** :
   - Format exact : "Le délai est de 24 heures[1]." (citation AVANT le point)
   - Si plusieurs sources : [1,2]
   - Si aucune source : "Je n'ai pas trouvé cette information"
   - Si contradictions : SIGNALE-LE avec les deux versions citées

4. **Règles absolues** :
   - N'invente JAMAIS d'information non présente dans les sources
   - Reste professionnel, clair, et structuré
   - N'ajoute AUCUNE décoration type "Sources :" ou liens - c'est géré automatiquement
"""

        # Procedural-specific rules
        procedural_rules = """
7. Structure la réponse en étapes numérotées claires
8. Utilise des tirets (-) pour les sous-actions
9. Chaque étape doit être citée
10. Formate avec markdown (** pour les titres d'étapes)
"""

        # Informational-specific rules
        informational_rules = """
7. Réponds de manière naturelle et directe
8. Synthétise les informations de plusieurs sources si pertinent
9. Pour les tableaux : génère UNIQUEMENT le tableau, sans texte explicatif avant/après
10. Reste concis, sobre et élégant
11. **Formatage Markdown obligatoire** :
    - Utilise **gras** pour les valeurs clés (montants, dates, noms importants)
    - Structure avec des listes à puces si plusieurs éléments
    - Pour les résumés de documents, utilise ce format :
      - **Prestataire :** Nom[N]
      - **Montant :** X,XX €[N]
      - **Date :** JJ/MM/AAAA[N]
    - Ajoute une phrase de conclusion si pertinent
"""

        # Context section
        context_section = ""
        if context:
            context_section = f"""
CONTEXTE CONVERSATIONNEL :
{context}
"""

        # Contradiction warning
        contradiction_section = ""
        if contradictions:
            contradiction_section = f"""
⚠️ ATTENTION - CONTRADICTIONS DÉTECTÉES :
{contradictions}

Tu DOIS mentionner cette contradiction dans ta réponse en citant les deux sources.
"""

        # Assemble prompt
        prompt = f"""Tu es un assistant expert qui répond avec des CITATIONS PRÉCISES et TRAÇABLES.

{base_rules}
{procedural_rules if is_procedural else informational_rules}

SOURCES NUMÉROTÉES :
{sources_text}
{context_section}
{contradiction_section}

QUESTION : {query}

Réponds en français, de manière professionnelle. Cite SYSTÉMATIQUEMENT tes sources avec [N].
N'ajoute PAS de section "Sources" à la fin - elle sera ajoutée automatiquement."""

        return prompt

    def _format_sources_for_prompt(self, sources: List[Source]) -> str:
        """
        Format sources for inclusion in prompt

        Returns:
            Formatted string like:
            [1] Règlement_copropriété (page 12, confiance: 95%)
            Extrait: "Le plombier doit intervenir dans un délai..."
        """
        formatted = []

        for source in sources:
            # Header
            page_info = f", page {source.page}" if source.page else ""
            confidence_pct = int(source.confidence * 100)

            header = f"[{source.id}] {source.title}{page_info} (confiance: {confidence_pct}%)"

            # Send FULL chunk to LLM - we increased chunk_size to 2000 for structured content
            # Mistral can handle 32k context, and HybridExecutor limits to 15 chunks max (30k chars)
            # Information is often in the MIDDLE/END of chunks (e.g., "Fenêtres = coloris acajou")
            excerpt = source.chunk_text  # No truncation

            formatted.append(f"{header}\n{excerpt}\n")

        return "\n".join(formatted)

    async def _detect_contradictions(self, sources: List[Source]) -> Optional[str]:
        """
        Use LLM to detect contradictions between sources

        Args:
            sources: List of sources to compare

        Returns:
            Contradiction description if found, None otherwise
        """
        if len(sources) < 2:
            return None

        # Format sources for comparison
        sources_text = "\n\n".join([
            f"[{s.id}] {s.title}:\n{s.chunk_text[:400]}"
            for s in sources[:5]  # Limit to top 5 to avoid prompt overflow
        ])

        prompt = f"""Analyse ces extraits de documents et détecte s'ils se CONTREDISENT.

SOURCES :
{sources_text}

INSTRUCTIONS :
- Si les sources sont COHÉRENTES entre elles, réponds uniquement : "COHERENT"
- Si tu détectes une CONTRADICTION, explique-la brièvement en citant les sources [N]
- Exemple : "Le document [1] indique 24h tandis que [2] mentionne 48h"

Réponds :"""

        try:
            result = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=200
            )

            result_clean = result.strip()

            if "COHERENT" in result_clean.upper():
                logger.debug("no_contradictions_detected")
                return None
            else:
                logger.warning("contradictions_detected", details=result_clean)
                return result_clean

        except Exception as e:
            logger.error("contradiction_detection_failed", error=str(e))
            return None

    def _parse_sentences_with_citations(self, text: str) -> List[CitedSentence]:
        """
        Parse response text into sentences with citation tracking

        Args:
            text: Generated response with inline citations

        Returns:
            List of CitedSentence objects

        Example:
            Input: "Le délai est 24h[1]. Le coût est 80€[2,3]."
            Output: [
                CitedSentence(text="Le délai est 24h", source_ids=[1], has_citation=True),
                CitedSentence(text="Le coût est 80€", source_ids=[2,3], has_citation=True)
            ]
        """
        sentences = []

        # Split into sentences (basic split on . ! ?)
        raw_sentences = re.split(r'[.!?]\s+', text)

        for raw_sentence in raw_sentences:
            if not raw_sentence.strip():
                continue

            # Find citations [N] or [N,M]
            citation_pattern = r'\[(\d+(?:,\d+)*)\]'
            citations = re.findall(citation_pattern, raw_sentence)

            # Extract source IDs
            source_ids = []
            for citation in citations:
                ids = [int(x.strip()) for x in citation.split(',')]
                source_ids.extend(ids)

            # Remove citations from text for clean sentence
            clean_text = re.sub(citation_pattern, '', raw_sentence).strip()

            # Determine if factual (heuristic: contains numbers, dates, or is >10 words)
            is_factual = bool(re.search(r'\d+|tarif|délai|coût|prix|date', clean_text.lower()))

            sentence = CitedSentence(
                text=clean_text,
                source_ids=source_ids,
                has_citation=len(source_ids) > 0,
                is_factual=is_factual
            )
            sentences.append(sentence)

        logger.debug("sentences_parsed", count=len(sentences))
        return sentences

    def _format_response_with_sources(self, response_text: str, sources: List[Source], enable_cot: bool = True) -> str:
        """
        Format response with special markers for frontend parsing
        Uses HTML comment markers for intelligent frontend parsing

        Args:
            response_text: Raw response from LLM (may contain <thinking> tags)
            sources: List of sources for IEEE citation
            enable_cot: Whether to include Chain-of-Thought

        Returns:
            Formatted text with markers for frontend parser
        """
        formatted = ""

        # Extract thinking tags
        thinking = ""
        answer = response_text

        if "<thinking>" in response_text and "</thinking>" in response_text:
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', response_text, re.DOTALL)
            if thinking_match:
                thinking = thinking_match.group(1).strip()
                answer = re.sub(r'<thinking>.*?</thinking>', '', response_text, flags=re.DOTALL).strip()

        # Add CoT marker
        if thinking and enable_cot:
            formatted += f"<!--COT_START-->\n{thinking}\n<!--COT_END-->\n\n"

        # Main answer (Markdown)
        formatted += f"<!--ANSWER_START-->\n{answer}\n<!--ANSWER_END-->\n\n"

        # Sources marker with parseable format
        if sources:
            formatted += "<!--SOURCES_START-->\n"
            for source in sources:
                doc_id = f"DOC-{source.document_id:04d}"
                page_info = f", p. {source.page}" if source.page else ""
                confidence_pct = int(source.confidence * 100)
                excerpt = source.excerpt[:150] + "..." if len(source.excerpt) > 150 else source.excerpt

                # Pipe-separated format for easy parsing
                formatted += f"[{source.id}]|{source.title}|{doc_id}{page_info}|{confidence_pct}%|{excerpt}\n"

            formatted += "<!--SOURCES_END-->\n"

        return formatted

    def _detect_table_request(self, query: str) -> bool:
        """
        Detect if user is requesting a table/comparison

        Args:
            query: User's question

        Returns:
            True if table is requested
        """
        table_keywords = [
            "tableau", "table", "liste", "compare", "comparaison",
            "récapitulatif", "synthèse", "résumé", "colonnes",
            "lignes", "fais-moi", "génère", "affiche"
        ]

        query_lower = query.lower()
        return any(keyword in query_lower for keyword in table_keywords)

    async def _generate_table_from_response(
        self,
        response_text: str,
        sources: List[Source],
        query: str
    ) -> Optional[str]:
        """
        Generate HTML table from LLM response and sources

        Args:
            response_text: LLM-generated response (may contain structured data)
            sources: Sources used in response
            query: Original user query

        Returns:
            HTML table string or None if no table could be generated
        """
        try:
            # Ask LLM to extract tabular data from response and sources
            table_extraction_prompt = f"""Extrait des données tabulaires structurées à partir de la réponse et des sources suivantes.

QUESTION : {query}

RÉPONSE GÉNÉRÉE :
{response_text}

SOURCES :
{self._format_sources_for_prompt(sources[:5])}

INSTRUCTIONS :
1. Identifie les données structurées qui peuvent être présentées en tableau
2. Détermine les colonnes appropriées (ex: Fournisseur, Montant HT, Montant TTC)
3. Extrait les données ligne par ligne
4. Réponds UNIQUEMENT au format JSON suivant :

{{
  "has_table": true/false,
  "columns": ["Colonne1", "Colonne2", "Colonne3"],
  "rows": [
    {{"Colonne1": "valeur1", "Colonne2": "valeur2", "Colonne3": "valeur3"}},
    {{"Colonne1": "valeur4", "Colonne2": "valeur5", "Colonne3": "valeur6"}}
  ],
  "title": "Titre du tableau"
}}

Si aucune donnée tabulaire n'est identifiable, réponds : {{"has_table": false}}
"""

            result = await self.llm_service.generate_response(
                prompt=table_extraction_prompt,
                temperature=0.1,
                max_tokens=1000
            )

            # Parse JSON response
            import json
            result_clean = result.strip()

            # Extract JSON if wrapped in markdown code blocks
            if "```json" in result_clean:
                result_clean = re.search(r'```json\s*(.*?)\s*```', result_clean, re.DOTALL).group(1)
            elif "```" in result_clean:
                result_clean = re.search(r'```\s*(.*?)\s*```', result_clean, re.DOTALL).group(1)

            table_data = json.loads(result_clean)

            if not table_data.get("has_table", False):
                logger.debug("no_table_data_found")
                return None

            # TODO: Re-enable table generation when service is available
            # For now, just return None to skip table generation
            logger.info("table_generation_disabled", reason="TableGenerationService not available")
            return None

            # # Generate HTML table using TableGenerationService
            # table_service = TableGenerationService()
            # table_id = f"table_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

            # rows = table_data.get("rows", [])
            # columns = table_data.get("columns", [])
            # title = table_data.get("title", "Tableau de données")

            # if not rows or not columns:
            #     return None

            # # Cache data for export
            # cache_table_data(table_id, rows, columns, title)

            # # Generate HTML
            # html_table = table_service.generate_html_table(
            #     data=rows,
            #     columns=columns,
            #     title=title,
            #     export_id=table_id
            # )
            # logger.info("table_generated", table_id=table_id, rows=len(rows), columns=len(columns))
            # return html_table

        except Exception as e:
            logger.error("table_generation_failed", error=str(e), exc_info=True)
            return None

    def _compute_overall_confidence(
        self,
        sources: List[Source],
        sentences: List[CitedSentence]
    ) -> float:
        """
        Compute overall confidence score for the response

        Factors:
        - INTERGALACTIC MODE: Weighted source confidence (top 5 chunks 70%, rest 30%)
        - Citation coverage (% of factual sentences cited)

        Args:
            sources: List of sources with confidence scores
            sentences: Parsed sentences with citation info

        Returns:
            Confidence score 0-1
        """
        if not sources:
            return 0.0

        # INTERGALACTIC MODE: Weighted confidence calculation
        # Top 5 chunks are weighted 70%, rest 30%
        # This prioritizes the most relevant chunks
        top_k = 5
        if len(sources) <= top_k:
            # All sources are top sources
            avg_source_confidence = sum(s.confidence for s in sources) / len(sources)
        else:
            # Split into top 5 and rest
            top_sources = sources[:top_k]
            rest_sources = sources[top_k:]

            top_avg = sum(s.confidence for s in top_sources) / len(top_sources)
            rest_avg = sum(s.confidence for s in rest_sources) / len(rest_sources)

            # Weighted average: top chunks 70%, rest 30%
            avg_source_confidence = (0.7 * top_avg) + (0.3 * rest_avg)

        # Factor 2: Citation coverage
        factual_sentences = [s for s in sentences if s.is_factual]
        if factual_sentences:
            cited_factual = [s for s in factual_sentences if s.has_citation]
            citation_coverage = len(cited_factual) / len(factual_sentences)
        else:
            citation_coverage = 1.0  # No factual claims, so 100% coverage

        # Weighted average (sources 70%, coverage 30%)
        overall = (0.7 * avg_source_confidence) + (0.3 * citation_coverage)

        logger.debug(
            "confidence_computed",
            source_conf=avg_source_confidence,
            citation_cov=citation_coverage,
            overall=overall,
            top_sources_count=min(len(sources), top_k),
            rest_sources_count=max(0, len(sources) - top_k)
        )

        return overall

    def _generate_empty_response(self, query: str) -> SynthesizedResponse:
        """Generate response when no sources found (legacy sync version)"""
        return SynthesizedResponse(
            text="Je n'ai pas trouvé de documents pertinents pour répondre à votre question. Pouvez-vous reformuler ou préciser votre demande ?",
            sources=[],
            sentences=[],
            has_contradictions=False,
            overall_confidence=0.0
        )

    async def _generate_empty_response_smart(self, query: str) -> SynthesizedResponse:
        """
        Generate intelligent response when no data found.

        Uses LLM to understand user intent and propose helpful alternatives.
        This is the "agile, non-deterministic" approach requested by the user.
        """
        try:
            prompt = f"""Tu es DisruptIQ, assistant intelligent pour syndics de copropriété.

L'utilisateur a posé cette question : "{query}"

MAIS je n'ai trouvé AUCUNE donnée correspondante dans :
- La base de données SQL (copropriétaires, lots, professionnels)
- Les documents uploadés (règlements, PV, contrats)
- Les sources légales

CONSIGNES :
1. Reconnaître l'intention de l'utilisateur
2. Expliquer poliment que ces données ne sont pas disponibles
3. Proposer 2-3 alternatives utiles et ACTIONNABLES :
   - Actions que l'utilisateur pourrait faire
   - Questions connexes auxquelles tu pourrais répondre
   - Suggestions pour enrichir les données
4. Rester professionnel et positif
5. Ne PAS inventer de données

EXEMPLE de réponse pour "Combien de dégâts des eaux cette année ?" :
"Je n'ai pas trouvé de données sur les dégâts des eaux dans votre base.

Voici ce que je peux vous proposer :
- **Déclarer un sinistre** : Si vous avez un dégât des eaux en cours, je peux vous guider avec une checklist d'urgence
- **Importer vos données** : Vous pouvez uploader vos documents de sinistres passés
- **Consulter les procédures** : Je peux vous expliquer la procédure légale en cas de dégât des eaux"

Réponds de manière concise et professionnelle (max 150 mots)."""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.5,  # Un peu de créativité pour les suggestions
                max_tokens=400
            )

            logger.info("smart_empty_response_generated", query=query[:50])

            return SynthesizedResponse(
                text=response,
                sources=[],
                sentences=[],
                has_contradictions=False,
                overall_confidence=0.0,
                warnings=["Réponse générée sans données sources - suggestions proposées"]
            )

        except Exception as e:
            # Fallback to static response if LLM fails
            logger.error("smart_empty_response_failed", error=str(e))
            return self._generate_empty_response(query)

    def _generate_fallback_response(
        self,
        query: str,
        chunks: List[Dict[str, Any]]
    ) -> SynthesizedResponse:
        """Generate basic response if synthesis fails"""
        logger.warning("using_fallback_response")

        # Simple formatting fallback
        sources = self._prepare_sources(chunks[:3])

        response_parts = [
            "Voici ce que j'ai trouvé dans les documents :\n"
        ]

        for source in sources:
            response_parts.append(
                f"\n**[{source.id}] {source.title}** :\n{source.excerpt}...\n"
            )

        response_parts.append("\n---\n📚 **Sources** :\n")
        for source in sources:
            response_parts.append(f"[{source.id}] {source.title} - {int(source.confidence * 100)}%\n")

        return SynthesizedResponse(
            text="".join(response_parts),
            sources=sources,
            sentences=[],
            has_contradictions=False,
            overall_confidence=0.5,
            warnings=["Fallback response used due to synthesis error"]
        )

    # ========================================================================
    # WORLD-CLASS ROUTER OPTIMIZATION: Multi-Source Synthesis (Single LLM Pass)
    # ========================================================================

    async def synthesize_multi_source(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        router_metrics: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[str] = None
    ) -> SynthesizedResponse:
        """
        OPTIMIZED multi-source synthesis for WorldClassRouter.

        This method receives RAW documents from multiple sources (SQL, RAG, Legal, Web)
        and performs a SINGLE LLM call for synthesis, replacing multiple agent syntheses.

        Architecture:
        - SQL Agent retrieve_light() -> raw SQL results
        - RAG Service search() -> raw document chunks
        - Legal Agent retrieve_light() -> raw legal articles
        - Web Agent retrieve_light() -> raw search results
        -> THIS METHOD: Single LLM synthesis

        Args:
            query: User's question
            documents: List of documents from all sources
            router_metrics: Metrics from WorldClassRouter (sources_queried, complexity, etc.)
            conversation_context: Optional conversation history

        Returns:
            SynthesizedResponse with text, sources, and metadata
        """
        try:
            if not documents:
                return await self._generate_empty_response_smart(query)

            # Group documents by source type
            sql_docs = [d for d in documents if d.get("source") == "sql"]
            rag_docs = [d for d in documents if d.get("source") == "rag"]
            legal_docs = [d for d in documents if d.get("source") in ["legifrance", "legal"]]
            web_docs = [d for d in documents if d.get("source") == "web"]

            # Build multi-source prompt
            prompt = self._build_multi_source_prompt(
                query=query,
                sql_docs=sql_docs,
                rag_docs=rag_docs,
                legal_docs=legal_docs,
                web_docs=web_docs,
                router_metrics=router_metrics,
                conversation_context=conversation_context
            )

            logger.info("multi_source_synthesis_started",
                       query=query[:50],
                       sql_count=len(sql_docs),
                       rag_count=len(rag_docs),
                       legal_count=len(legal_docs),
                       web_count=len(web_docs))

            # Single LLM call for synthesis
            response_text = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1000
            )

            # Build sources for response
            all_sources = []
            source_id = 1

            for doc in documents:
                source_type = doc.get("source", "unknown")
                source_label = {
                    "sql": "Base de données",
                    "rag": doc.get("metadata", {}).get("filename", "Document"),
                    "legifrance": "Légifrance",
                    "legal": "Légifrance",
                    "web": doc.get("metadata", {}).get("title", "Web")
                }.get(source_type, "Source")

                all_sources.append(Source(
                    id=source_id,
                    document_id=doc.get("metadata", {}).get("document_id", 0),
                    title=f"[{source_type.upper()}] {source_label}",
                    page=doc.get("metadata", {}).get("page"),
                    excerpt=doc.get("content", "")[:200],
                    confidence=doc.get("score", 0.7),
                    chunk_text=doc.get("content", "")
                ))
                source_id += 1

            # Parse sentences (simplified for speed)
            sentences = self._parse_sentences_with_citations(response_text)

            # Compute confidence
            overall_confidence = sum(d.get("score", 0.5) for d in documents) / len(documents) if documents else 0.5

            logger.info("multi_source_synthesis_complete",
                       query=query[:50],
                       sources_count=len(all_sources),
                       response_length=len(response_text))

            return SynthesizedResponse(
                text=response_text,
                sources=all_sources,
                sentences=sentences,
                has_contradictions=False,  # Skip contradiction detection for speed
                overall_confidence=overall_confidence
            )

        except Exception as e:
            logger.error("multi_source_synthesis_failed", error=str(e), exc_info=True)
            return self._generate_fallback_response(query, documents)

    def _build_multi_source_prompt(
        self,
        query: str,
        sql_docs: List[Dict],
        rag_docs: List[Dict],
        legal_docs: List[Dict],
        web_docs: List[Dict],
        router_metrics: Optional[Dict] = None,
        conversation_context: Optional[str] = None
    ) -> str:
        """
        Build optimized multi-source synthesis prompt.

        Key features:
        - Clear source type labels
        - Priority weighting (SQL facts > Documents > Legal > Web)
        - Conflict resolution instructions
        - Citation requirements
        """
        # Build source sections
        source_sections = []
        source_id = 1

        # SQL sources (highest priority for factual data)
        if sql_docs:
            sql_section = "## (SQL) Données structurées de la base de données\n"
            for doc in sql_docs:
                sql_section += f"[{source_id}] {doc.get('content', '')}\n\n"
                source_id += 1
            source_sections.append(sql_section)

        # RAG sources (documents, contracts, PV)
        if rag_docs:
            rag_section = "## (DOC) Documents internes (PV, règlements, contrats)\n"
            for doc in rag_docs:
                filename = doc.get("metadata", {}).get("filename", "Document")
                rag_section += f"[{source_id}] **{filename}**\n{doc.get('content', '')[:1500]}\n\n"
                source_id += 1
            source_sections.append(rag_section)

        # Legal sources (Légifrance)
        if legal_docs:
            legal_section = "## (LOI) Textes de loi et jurisprudence\n"
            for doc in legal_docs:
                legal_section += f"[{source_id}] {doc.get('content', '')}\n\n"
                source_id += 1
            source_sections.append(legal_section)

        # Web sources (external information)
        if web_docs:
            web_section = "## (WEB) Informations externes\n"
            for doc in web_docs:
                url = doc.get("metadata", {}).get("url", "")
                title = doc.get("metadata", {}).get("title", "Source web")
                web_section += f"[{source_id}] **{title}** ({url})\n{doc.get('content', '')[:800]}\n\n"
                source_id += 1
            source_sections.append(web_section)

        all_sources_text = "\n".join(source_sections)

        # Context section
        context_section = ""
        if conversation_context:
            context_section = f"\n## Contexte conversationnel\n{conversation_context}\n"

        # Build prompt with explicit SQL priority
        has_sql_data = bool(sql_docs) and any("DONNÉES TROUVÉES" in str(d.get("content", "")) or "résultat" in str(d.get("content", "")).lower() for d in sql_docs)

        sql_priority_instruction = ""
        if has_sql_data:
            sql_priority_instruction = """
## ⚠️ INSTRUCTION CRITIQUE - DONNÉES SQL DISPONIBLES
Les sources SQL ci-dessus contiennent des DONNÉES FACTUELLES de la base de données.
Ces données sont VÉRIFIÉES et EXACTES. Tu DOIS les utiliser comme base de ta réponse.
Si SQL dit "5 résultats trouvés", ta réponse DOIT mentionner ces 5 résultats.
NE PAS dire "pas d'information" si des données SQL existent.
"""

        prompt = f"""Tu es un assistant expert en copropriété. Tu réponds de manière précise et structurée en citant TOUJOURS tes sources.

# SOURCES DISPONIBLES
{all_sources_text}
{sql_priority_instruction}
{context_section}

# RÈGLES DE SYNTHÈSE

1. **PRIORITÉ ABSOLUE AUX DONNÉES SQL** :
   - Si une source (SQL) existe et contient des données, TU DOIS les utiliser
   - Les données SQL proviennent directement de la base de données
   - C'est la source la plus fiable et la plus récente
   - NE JAMAIS ignorer les données SQL

2. **FUSION SQL + RAG** (quand les deux sources existent) :
   - COMBINE les données SQL (faits: noms, emails, montants) avec les documents RAG (contexte: contrats, PV, règlements)
   - Exemple: SQL donne "Jean Dupont, lot 5, email: jean@mail.com" + DOC donne "Le lot 5 a été vendu en 2020"
   - Ta réponse DOIT intégrer les deux: "Jean Dupont (jean@mail.com) est propriétaire du lot 5, acquis en 2020[1][2]"
   - Ne JAMAIS ignorer une source si elle apporte des infos complémentaires

3. **Priorité des sources** (en cas de conflit UNIQUEMENT) :
   - (SQL) > (DOC) > (LOI) > (WEB)
   - Les données SQL sont des faits vérifiés - TOUJOURS les utiliser
   - Les documents apportent du contexte et des détails
   - Les lois donnent le cadre juridique
   - Le web est informatif mais à vérifier

4. **Citations obligatoires** :
   - Chaque information doit être citée [N]
   - Format : "Il y a 12 copropriétaires[1]."
   - Si conflit : mentionner les deux sources

5. **Structure de réponse** :
   - Réponse directe basée sur les données disponibles
   - Si SQL contient des noms/emails, les lister clairement
   - Markdown sobre (**, listes à puces)
   - Pas de section "Sources" (ajoutée automatiquement)

6. **Limitations** :
   - Si AUCUNE source ne contient d'info : dis-le clairement
   - Si SQL contient des données : les utiliser OBLIGATOIREMENT
   - N'invente JAMAIS

# QUESTION
{query}

# RÉPONSE
Réponds en français. Si des données SQL existent, UTILISE-LES dans ta réponse."""

        return prompt
