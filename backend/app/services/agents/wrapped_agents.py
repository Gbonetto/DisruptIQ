"""
Wrapped Agents - Adapters for Legacy Agents
Phase 3.7 - World-Class SMA Architecture

Provides BaseAgent-compliant wrappers around existing agents.
This allows gradual migration without breaking existing code.

Each wrapper:
- Implements BaseAgent interface
- Delegates to existing agent implementation
- Adds metrics and observability
- Provides can_handle() for smart routing

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

import structlog
from typing import Dict, Any, List, Optional

from app.services.agents.base_agent import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentCapability
)

logger = structlog.get_logger()


class WrappedSQLAgent(BaseAgent):
    """Wrapper for SQLAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.sql_agent import SQLAgent
        self._agent = SQLAgent()

    @property
    def name(self) -> str:
        return "sql_agent"

    @property
    def description(self) -> str:
        return "Convertit les questions en requêtes SQL et interroge la base de données"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.DATA_QUERY]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query is SQL-related"""
        query_lower = query.lower()

        # High confidence patterns
        high_patterns = [
            "combien", "liste", "quels", "quelles", "qui sont",
            "nombre de", "total", "moyenne", "statistiques",
            "copropriétaires", "fournisseurs", "prestataires",
            "copropriétés", "immeubles", "bâtiments"
        ]

        for pattern in high_patterns:
            if pattern in query_lower:
                return 0.85

        # Medium confidence
        medium_patterns = ["donne", "montre", "affiche", "trouve"]
        for pattern in medium_patterns:
            if pattern in query_lower:
                return 0.60

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Process SQL query"""
        try:
            if not input.db_session:
                return AgentOutput(
                    success=False,
                    response="Session de base de données non disponible",
                    confidence=0.0
                )

            result = await self._agent.process(input.query, input.db_session)

            return AgentOutput(
                success=result.get("success", False),
                response=result.get("response", ""),
                data=result.get("data", {}),
                confidence=result.get("confidence", 0.8),
                metadata={
                    "sql_query": result.get("sql_query"),
                    "row_count": result.get("row_count", 0)
                }
            )

        except Exception as e:
            logger.error("sql_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur SQL: {str(e)}",
                confidence=0.0
            )


class WrappedEmailAgent(BaseAgent):
    """Wrapper for EmailAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.email_agent import EmailAgent
        self._agent = EmailAgent()

    @property
    def name(self) -> str:
        return "email_agent"

    @property
    def description(self) -> str:
        return "Génère des emails professionnels contextuels pour syndics"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.EMAIL_GENERATION, AgentCapability.TEXT_GENERATION]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query is email-related"""
        query_lower = query.lower()

        # High confidence - explicit email request
        if any(w in query_lower for w in ["rédige", "écris", "prépare", "génère"]):
            if any(w in query_lower for w in ["email", "mail", "courrier", "message"]):
                return 0.95

        # High confidence - email types
        email_types = [
            "devis", "relance", "convocation", "rappel",
            "notification", "urgent", "intervention"
        ]
        if any(t in query_lower for t in email_types):
            if any(w in query_lower for w in ["envoyer", "contacter", "prévenir", "informer"]):
                return 0.85

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Generate email"""
        try:
            result = await self._agent.generate_email(
                user_request=input.query,
                db=input.db_session,
                recipients=input.context.get("recipients"),
                conversation_history=input.conversation_history,
                workflow_context=input.context.get("workflow_context")
            )

            return AgentOutput(
                success=result.get("success", True),
                response=result.get("formatted_response", ""),
                data={
                    "subject": result.get("subject"),
                    "body": result.get("body"),
                    "recipients": result.get("recipients", []),
                    "email_type": result.get("email_type")
                },
                confidence=0.9,
                suggestions=["Envoyer", "Modifier", "Annuler"]
            )

        except Exception as e:
            logger.error("email_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur génération email: {str(e)}",
                confidence=0.0
            )


class WrappedLegalAgent(BaseAgent):
    """Wrapper for LegalAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.legal_agent import LegalAgent
        self._agent = LegalAgent()

    @property
    def name(self) -> str:
        return "legal_agent"

    @property
    def description(self) -> str:
        return "Analyse juridique, détection clauses abusives, conformité réglementaire"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.LEGAL_ANALYSIS, AgentCapability.DOCUMENT_ANALYSIS]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query is legal-related"""
        query_lower = query.lower()

        # High confidence - explicit legal
        legal_keywords = [
            "juridique", "légal", "loi", "article", "clause",
            "contrat", "règlement", "conformité", "abusif",
            "jurisprudence", "décret", "copropriété"
        ]

        matches = sum(1 for k in legal_keywords if k in query_lower)
        if matches >= 2:
            return 0.95
        if matches == 1:
            return 0.75

        # Document analysis context
        if context.get("document_type") in ["contrat", "règlement", "legal"]:
            return 0.85

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Process legal analysis"""
        try:
            result = await self._agent.process_request(
                user_input=input.query,
                context=input.context,
                db=input.db_session,
                thought_stream=input.thought_stream
            )

            return AgentOutput(
                success=result.get("success", True),
                response=result.get("response", ""),
                data=result.get("data", {}),
                confidence=result.get("confidence", 0.85),
                sources=result.get("sources", []),
                warnings=result.get("warnings", [])
            )

        except Exception as e:
            logger.error("legal_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur analyse juridique: {str(e)}",
                confidence=0.0
            )


class WrappedOCRAgent(BaseAgent):
    """Wrapper for OCRAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.ocr_agent import OCRAgent
        self._agent = OCRAgent()

    @property
    def name(self) -> str:
        return "ocr_agent"

    @property
    def description(self) -> str:
        return "Extraction de texte et métadonnées depuis documents (PDF, images)"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.OCR_EXTRACTION, AgentCapability.DOCUMENT_ANALYSIS]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query needs OCR"""
        # Check for uploaded file
        if context.get("uploaded_file") or context.get("file_content"):
            return 0.95

        query_lower = query.lower()
        if any(w in query_lower for w in ["ocr", "extraire", "scanner", "numériser"]):
            return 0.85

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Process OCR request"""
        try:
            file_content = input.context.get("file_content")
            filename = input.context.get("filename", "document")
            content_type = input.context.get("content_type", "application/pdf")

            if not file_content:
                return AgentOutput(
                    success=False,
                    response="Aucun fichier fourni pour l'OCR",
                    confidence=0.0
                )

            result = await self._agent.process(
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                db=input.db_session
            )

            return AgentOutput(
                success=result.get("success", True),
                response=result.get("response", "Document traité"),
                data={
                    "extracted_text": result.get("text", ""),
                    "document_type": result.get("doc_type"),
                    "metadata": result.get("metadata", {}),
                    "document_id": result.get("document_id")
                },
                confidence=0.9
            )

        except Exception as e:
            logger.error("ocr_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur OCR: {str(e)}",
                confidence=0.0
            )


class WrappedSynthesisAgent(BaseAgent):
    """Wrapper for SynthesisAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.synthesis_agent import SynthesisAgent
        self._agent = SynthesisAgent()

    @property
    def name(self) -> str:
        return "synthesis_agent"

    @property
    def description(self) -> str:
        return "Synthèse de réponses RAG avec citations et sources"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.SYNTHESIS, AgentCapability.TEXT_GENERATION]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Synthesis is typically called by orchestrator, not directly"""
        # Low direct routing confidence - usually called internally
        if context.get("force_synthesis"):
            return 0.95
        return 0.3

    async def process(self, input: AgentInput) -> AgentOutput:
        """Synthesize response"""
        try:
            chunks = input.context.get("chunks", [])

            result = await self._agent.synthesize_with_citations(
                query=input.query,
                chunks=chunks,
                conversation_context=input.context.get("conversation_context"),
                is_procedural=input.context.get("is_procedural", False)
            )

            return AgentOutput(
                success=True,
                response=result.text if hasattr(result, 'text') else str(result),
                data={
                    "sources": [s.to_dict() if hasattr(s, 'to_dict') else s for s in getattr(result, 'sources', [])],
                    "has_contradictions": getattr(result, 'has_contradictions', False)
                },
                confidence=getattr(result, 'overall_confidence', 0.8),
                sources=getattr(result, 'sources', [])
            )

        except Exception as e:
            logger.error("synthesis_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur synthèse: {str(e)}",
                confidence=0.0
            )


class WrappedReflectionAgent(BaseAgent):
    """Wrapper for ReflectionAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.reflection_agent import ReflectionAgent
        self._agent = ReflectionAgent()

    @property
    def name(self) -> str:
        return "reflection_agent"

    @property
    def description(self) -> str:
        return "Optimisation RAG - diagnostique et corrige les échecs de recherche"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.REFLECTION]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Reflection is called when RAG quality is low"""
        if context.get("low_confidence") or context.get("force_reflection"):
            return 0.95
        return 0.1  # Very low - only called internally

    async def process(self, input: AgentInput) -> AgentOutput:
        """Run reflection/optimization"""
        try:
            original_results = input.context.get("original_results", [])

            result = await self._agent.reflect(
                query=input.query,
                original_results=original_results,
                context=input.context
            )

            return AgentOutput(
                success=result.should_return if hasattr(result, 'should_return') else True,
                response=result.fallback_message if hasattr(result, 'fallback_message') else "",
                data={
                    "failure_type": result.failure_type.value if hasattr(result, 'failure_type') else None,
                    "strategy_used": result.strategy_used.value if hasattr(result, 'strategy_used') else None,
                    "improved_results": result.improved_results if hasattr(result, 'improved_results') else None
                },
                confidence=result.confidence if hasattr(result, 'confidence') else 0.5
            )

        except Exception as e:
            logger.error("reflection_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur reflection: {str(e)}",
                confidence=0.0
            )


class WrappedWorkflowAgent(BaseAgent):
    """Wrapper for WorkflowAgent"""

    def __init__(self):
        super().__init__()
        from app.services.agents.workflow_agent import WorkflowAgent
        self._agent = WorkflowAgent()

    @property
    def name(self) -> str:
        return "workflow_agent"

    @property
    def description(self) -> str:
        return "Déclenche des workflows N8N (emails, urgences, notifications)"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.WORKFLOW_TRIGGER]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query triggers a workflow"""
        query_lower = query.lower()

        # High confidence - workflow triggers
        triggers = [
            "déclenche", "lance", "exécute", "workflow",
            "automatise", "envoie en masse", "notification groupée"
        ]

        for trigger in triggers:
            if trigger in query_lower:
                return 0.90

        # Emergency workflows
        emergencies = ["urgence", "fuite", "incendie", "sinistre"]
        if any(e in query_lower for e in emergencies):
            return 0.85

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Trigger workflow"""
        try:
            result = await self._agent.process_request(
                user_input=input.query,
                context=input.context,
                thought_stream=input.thought_stream,
                conversation_id=input.session_id,
                tenant_id=input.tenant_id,
                user_id=input.user_id
            )

            return AgentOutput(
                success=result.get("success", True),
                response=result.get("response", "Workflow déclenché"),
                data={
                    "workflow_id": result.get("workflow_id"),
                    "workflow_type": result.get("workflow_type"),
                    "n8n_response": result.get("n8n_response")
                },
                confidence=0.9
            )

        except Exception as e:
            logger.error("workflow_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur workflow: {str(e)}",
                confidence=0.0
            )


class WrappedWebSearchAgent(BaseAgent):
    """Wrapper for WebSearchAgent"""

    def __init__(self):
        super().__init__()
        self._agent = None  # Lazy load

    def _get_agent(self):
        if self._agent is None:
            from app.services.agents.websearch_agent import WebSearchAgent
            self._agent = WebSearchAgent()
        return self._agent

    @property
    def name(self) -> str:
        return "websearch_agent"

    @property
    def description(self) -> str:
        return "Recherche d'informations sur le web"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [AgentCapability.WEB_SEARCH]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query needs web search"""
        query_lower = query.lower()

        # Explicit web search
        if any(w in query_lower for w in ["recherche", "internet", "web", "google", "en ligne"]):
            return 0.90

        # Current events / news
        if any(w in query_lower for w in ["actualité", "news", "dernière", "récent"]):
            return 0.80

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Perform web search"""
        try:
            agent = self._get_agent()
            result = await agent.search(input.query, input.context)

            return AgentOutput(
                success=result.get("success", True),
                response=result.get("response", ""),
                data={
                    "results": result.get("results", []),
                    "sources": result.get("sources", [])
                },
                confidence=0.75,
                sources=result.get("sources", [])
            )

        except Exception as e:
            logger.error("websearch_agent_error", error=str(e))
            return AgentOutput(
                success=False,
                response=f"Erreur recherche web: {str(e)}",
                confidence=0.0
            )


class WrappedDigestAgent(BaseAgent):
    """Wrapper for DigestAgent - uses the new unified implementation"""

    def __init__(self):
        super().__init__()
        from app.services.agents.digest_agent import DigestAgent
        self._agent = DigestAgent()

    @property
    def name(self) -> str:
        return "digest_agent"

    @property
    def description(self) -> str:
        return self._agent.description

    @property
    def capabilities(self) -> List[AgentCapability]:
        return self._agent.capabilities

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        return await self._agent.can_handle(query, context)

    async def process(self, input: AgentInput) -> AgentOutput:
        return await self._agent.process(input)
