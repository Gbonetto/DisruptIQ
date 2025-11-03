"""
Orchestrator Agent - Brain of the Multi-Agent System
Routes user requests to appropriate specialized agents
"""

import structlog
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.core.database import AsyncSession
from app.services.agents.thought_stream import ThoughtStream, ThoughtType

logger = structlog.get_logger()


class IntentType(str, Enum):
    """Types of user intentions"""
    QUERY_DATA = "query_data"  # SQL queries (copropriétaires, copropriétés, etc.)
    SEARCH_DOCUMENTS = "search_documents"  # RAG search (contracts, regulations)
    SEND_EMAIL = "send_email"  # Generate and send emails
    REQUEST_QUOTES = "request_quotes"  # Request devis from vendors
    ANALYZE_DOCUMENT = "analyze_document"  # OCR + extraction
    GENERATE_DIGEST = "generate_digest"  # Generate email digest
    GENERAL_QUESTION = "general_question"  # General assistant question
    TRIGGER_WORKFLOW = "trigger_workflow"  # Explicit N8N workflow trigger


class AgentResponse(BaseModel):
    """Standardized agent response format"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    agents_used: List[str] = []
    confidence: float = 1.0
    suggestions: List[str] = []


class OrchestratorAgent:
    """
    Orchestrator Agent - Routes requests to specialized agents

    This is the brain that:
    1. Classifies user intentions
    2. Determines which agents to call
    3. Coordinates multi-agent workflows
    4. Aggregates and formats results
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()
        logger.info("orchestrator_agent_initialized")

    async def classify_intention(self, user_input: str, context: Dict[str, Any] = None) -> IntentType:
        """
        Classify user intention using LLM

        Args:
            user_input: User's message
            context: Optional context (uploaded files, conversation history)

        Returns:
            IntentType enum
        """
        classification_prompt = f"""
Analyse l'intention de l'utilisateur et classifie-la dans UNE de ces catégories:

CATÉGORIES:
- query_data: Questions sur données structurées (copropriétaires, copropriétés, fournisseurs, statistiques)
  Exemples: "Combien de copropriétaires?", "Liste des fournisseurs jardiniers", "Budget Immeuble A"

- search_documents: Recherche dans documents (contrats, règlements, procédures)
  Exemples: "Procédure dégât des eaux", "Règlement copropriété article 5", "Contrat jardinier"

- send_email: Générer et envoyer emails
  Exemples: "Envoyer email aux copropriétaires", "Alerter pour urgence", "Convocation AG"

- request_quotes: Demander devis aux fournisseurs
  Exemples: "Demander devis jardinier", "Obtenir prix plombier", "Comparer devis électriciens"

- analyze_document: Analyser document uploadé (OCR, extraction données)
  Exemples: Détecté si fichier uploadé dans context

- generate_digest: Générer digest quotidien/hebdomadaire des emails
  Exemples: "Générer le digest", "Digest des emails", "Résumé emails", "Mail digest"

- trigger_workflow: Déclencher workflow N8N spécifique
  Exemples: "Créer brouillon Gmail", "Lancer workflow facturation", "Déclencher alerte SMS"

- general_question: Question générale assistant
  Exemples: "Comment ça marche?", "Aide-moi", "Qu'est-ce que tu peux faire?"

MESSAGE UTILISATEUR:
"{user_input}"

CONTEXTE:
{context if context else "Aucun"}

Réponds UNIQUEMENT avec le nom de la catégorie (ex: query_data), sans explication.
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=classification_prompt,
                max_tokens=20,
                temperature=0.1
            )

            # Clean response
            intent_str = response.strip().lower().replace('"', '').replace("'", "")

            # Map to IntentType
            intent_mapping = {
                "query_data": IntentType.QUERY_DATA,
                "search_documents": IntentType.SEARCH_DOCUMENTS,
                "send_email": IntentType.SEND_EMAIL,
                "request_quotes": IntentType.REQUEST_QUOTES,
                "analyze_document": IntentType.ANALYZE_DOCUMENT,
                "generate_digest": IntentType.GENERATE_DIGEST,
                "trigger_workflow": IntentType.TRIGGER_WORKFLOW,
                "general_question": IntentType.GENERAL_QUESTION,
            }

            intent = intent_mapping.get(intent_str, IntentType.GENERAL_QUESTION)

            logger.info("intention_classified", user_input=user_input[:50], intent=intent.value)
            return intent

        except Exception as e:
            logger.error("intention_classification_failed", error=str(e))
            return IntentType.GENERAL_QUESTION

    async def process(
        self,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict[str, str]] = None,
        thought_stream: ThoughtStream = None
    ) -> AgentResponse:
        """
        Main orchestration method - routes to appropriate agents

        Args:
            user_input: User's message
            db: Database session
            context: Optional context (files, metadata)
            conversation_history: Previous messages

        Returns:
            AgentResponse with results
        """
        try:
            # Thought 1: Analyzing request
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Analyse de la demande",
                    content=f"Je commence par analyser votre demande : « {user_input[:100]}... »",
                    agent="orchestrator",
                    progress=0.1
                )

            # 1. Classify intention
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.CLASSIFYING,
                    title="Classification de l'intention",
                    content="Je détermine quel type d'action est nécessaire (requête de données, recherche documentaire, génération d'email, etc.)",
                    agent="orchestrator",
                    progress=0.2
                )

            intent = await self.classify_intention(user_input, context)

            logger.info("processing_request", intent=intent.value, input=user_input[:50])

            # Thought 2: Planning
            if thought_stream:
                intent_descriptions = {
                    IntentType.QUERY_DATA: "requête de données structurées → SQL Agent",
                    IntentType.SEARCH_DOCUMENTS: "recherche documentaire → RAG Agent",
                    IntentType.SEND_EMAIL: "génération et envoi d'email → Email + Workflow Agents",
                    IntentType.REQUEST_QUOTES: "demande de devis → SQL + Template + Workflow Agents",
                    IntentType.ANALYZE_DOCUMENT: "analyse de document → OCR Agent",
                    IntentType.TRIGGER_WORKFLOW: "déclenchement de workflow → Workflow Agent",
                    IntentType.GENERAL_QUESTION: "question générale → LLM"
                }
                await thought_stream.add_thought(
                    ThoughtType.PLANNING,
                    title="Plan d'action",
                    content=f"J'ai identifié votre intention : **{intent.value}**\n\nJe vais utiliser : {intent_descriptions.get(intent, 'agents appropriés')}",
                    agent="orchestrator",
                    data={"intent": intent.value},
                    progress=0.3
                )

            # 2. Route to appropriate agent(s)
            if intent == IntentType.QUERY_DATA:
                return await self._handle_query_data(user_input, db)

            elif intent == IntentType.SEARCH_DOCUMENTS:
                return await self._handle_search_documents(user_input, db)

            elif intent == IntentType.SEND_EMAIL:
                return await self._handle_send_email(user_input, db)

            elif intent == IntentType.REQUEST_QUOTES:
                return await self._handle_request_quotes(user_input, db)

            elif intent == IntentType.ANALYZE_DOCUMENT:
                return await self._handle_analyze_document(user_input, context, db)

            elif intent == IntentType.GENERATE_DIGEST:
                return await self._handle_generate_digest(user_input, db)

            elif intent == IntentType.TRIGGER_WORKFLOW:
                return await self._handle_trigger_workflow(user_input, db)

            else:  # GENERAL_QUESTION
                return await self._handle_general_question(user_input, conversation_history)

        except Exception as e:
            logger.error("orchestrator_processing_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Désolé, une erreur s'est produite : {str(e)}",
                agents_used=["orchestrator"]
            )

    async def _handle_query_data(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle SQL data queries"""
        # Import here to avoid circular imports
        from .sql_agent import SQLAgent

        sql_agent = SQLAgent()
        result = await sql_agent.process(user_input, db)

        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data=result.get("data"),
            agents_used=["sql_agent"],
            confidence=result.get("confidence", 1.0)
        )

    async def _handle_search_documents(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """
        Handle document search via RAG with intelligent formatting

        Detects if query is procedural ("how to", "que faire") and formats
        results as actionable steps. Otherwise, returns informational format.
        """
        try:
            # Use existing RAG service
            results = await self.rag_service.search(user_input, limit=3)

            if not results:
                return AgentResponse(
                    success=True,
                    message="Je n'ai pas trouvé de documents pertinents. Pouvez-vous reformuler votre question ?",
                    agents_used=["rag_agent"],
                    confidence=0.0
                )

            # Detect if this is a procedural question
            is_procedural = self._is_procedural_query(user_input)

            # Format response based on query type
            if is_procedural:
                logger.info("rag_procedural_query_detected", query=user_input[:50])
                response_message = await self._format_as_action_list(user_input, results)
            else:
                logger.info("rag_informational_query_detected", query=user_input[:50])
                response_message = self._format_as_informational(results)

            # Prepare sources for frontend
            sources = []
            for doc in results:
                sources.append({
                    "title": doc.get("metadata", {}).get("title", "Document"),
                    "page": doc.get("metadata", {}).get("page"),
                    "score": doc.get("score", 0)
                })

            return AgentResponse(
                success=True,
                message=response_message,
                data={"sources": sources, "results": results, "is_procedural": is_procedural},
                agents_used=["rag_agent"],
                confidence=results[0].get("score", 1.0) if results else 0.0
            )

        except Exception as e:
            logger.error("rag_search_failed", error=str(e))
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la recherche documentaire : {str(e)}",
                agents_used=["rag_agent"]
            )

    async def _handle_send_email(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle email generation and sending workflow"""
        from .email_agent import EmailAgent
        from .workflow_agent import WorkflowAgent

        email_agent = EmailAgent()
        workflow_agent = WorkflowAgent()

        # Multi-step workflow
        agents_used = []

        # Step 1: Generate email draft
        email_draft = await email_agent.generate_email(user_input, db)
        agents_used.append("email_agent")

        if not email_draft["success"]:
            return AgentResponse(
                success=False,
                message=email_draft["message"],
                agents_used=agents_used
            )

        # Step 2: Trigger N8N workflow to create Gmail draft
        workflow_result = await workflow_agent.trigger_email_draft(email_draft["data"])
        agents_used.append("workflow_agent")

        return AgentResponse(
            success=workflow_result["success"],
            message=workflow_result["message"],
            data={
                "email_draft": email_draft["data"],
                "workflow_result": workflow_result.get("data")
            },
            agents_used=agents_used,
            suggestions=[
                "Voulez-vous que je modifie le brouillon ?",
                "Souhaitez-vous ajouter des pièces jointes ?",
                "Dois-je l'envoyer maintenant ?"
            ]
        )

    async def _handle_request_quotes(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle vendor quote requests"""
        from .sql_agent import SQLAgent
        from .template_agent import TemplateAgent
        from .workflow_agent import WorkflowAgent

        sql_agent = SQLAgent()
        template_agent = TemplateAgent()
        workflow_agent = WorkflowAgent()

        agents_used = []

        # Step 1: Get relevant vendors from DB
        vendor_query = f"Extract vendor information for: {user_input}"
        vendors_result = await sql_agent.process(vendor_query, db)
        agents_used.append("sql_agent")

        if not vendors_result["success"]:
            return AgentResponse(
                success=False,
                message="Je n'ai pas pu trouver de fournisseurs correspondants.",
                agents_used=agents_used
            )

        # Step 2: Generate quote request template
        template_result = await template_agent.fill_template(
            template_name="demande_devis",
            user_request=user_input,
            context=vendors_result.get("data")
        )
        agents_used.append("template_agent")

        # Step 3: Trigger N8N workflow for bulk quote requests
        workflow_result = await workflow_agent.trigger_bulk_quotes(
            vendors=vendors_result.get("data", {}).get("vendors", []),
            message=template_result["message"]
        )
        agents_used.append("workflow_agent")

        return AgentResponse(
            success=workflow_result["success"],
            message=workflow_result["message"],
            data=workflow_result.get("data"),
            agents_used=agents_used
        )

    async def _handle_analyze_document(
        self,
        user_input: str,
        context: Dict[str, Any],
        db: AsyncSession
    ) -> AgentResponse:
        """Handle document analysis with OCR"""
        from .ocr_agent import OCRAgent

        # Check if file is in context
        if not context or "file" not in context:
            return AgentResponse(
                success=False,
                message="Veuillez uploader un document (PDF ou image) pour que je puisse l'analyser.",
                agents_used=["orchestrator"],
                suggestions=["Uploadez une facture, un contrat, ou tout autre document"]
            )

        file_data = context["file"]

        ocr_agent = OCRAgent()
        result = await ocr_agent.process(
            file_content=file_data["content"],
            filename=file_data["filename"],
            content_type=file_data["content_type"],
            db=db,
            user_context={"message": user_input}
        )

        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data=result.get("data"),
            agents_used=["ocr_agent"],
            suggestions=[
                "Rechercher des documents similaires",
                "Extraire les montants de toutes les factures",
                "Trouver le contrat avec ce fournisseur"
            ]
        )

    async def _handle_generate_digest(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle email digest generation - reads from database"""
        try:
            # Import digest service
            from app.api.endpoints.digest import generate_digest, DigestGenerateRequest

            logger.info("generating_digest_from_db")

            request = DigestGenerateRequest(since_hours=24, max_emails=100)
            digest_result = await generate_digest(request=request, db=db)

            # digest_result is a dict
            if digest_result and isinstance(digest_result, dict):
                urgent_emails = digest_result.get('urgent', {}).get('emails', [])
                important_emails = digest_result.get('important', {}).get('emails', [])
                routine_emails = digest_result.get('routine', {}).get('emails', [])

                urgent_count = len(urgent_emails)
                important_count = len(important_emails)
                routine_count = len(routine_emails)
                total = digest_result.get('total_emails', 0)

                message_parts = [
                    f"📧 **Digest des emails généré** ({total} emails analysés)\n",
                    f"\n🔴 **Urgents**: {urgent_count}",
                    f"\n🟡 **Importants**: {important_count}",
                    f"\n🟢 **Routiniers**: {routine_count}\n"
                ]

                # Add sample urgent emails
                if urgent_emails:
                    message_parts.append("\n**Emails urgents:**")
                    for i, email in enumerate(urgent_emails[:3], 1):
                        subject = email.get('subject', 'Sans objet')
                        sender = email.get('sender', 'Inconnu')
                        message_parts.append(f"\n{i}. {subject} (de {sender})")

                return AgentResponse(
                    success=True,
                    message="".join(message_parts),
                    data={
                        "urgent_count": urgent_count,
                        "important_count": important_count,
                        "routine_count": routine_count,
                        "digest": digest_result
                    },
                    agents_used=["digest_agent"],
                    suggestions=[
                        "Voir tous les emails urgents",
                        "Générer le digest en HTML",
                        "Envoyer le digest par email"
                    ]
                )
            else:
                return AgentResponse(
                    success=True,
                    message="Aucun nouveau email trouvé dans les dernières 24 heures.",
                    agents_used=["digest_agent"]
                )

        except Exception as e:
            logger.error("digest_generation_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la génération du digest: {str(e)}",
                agents_used=["digest_agent"]
            )

    async def _handle_trigger_workflow(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle explicit workflow triggers"""
        from .workflow_agent import WorkflowAgent

        workflow_agent = WorkflowAgent()
        result = await workflow_agent.trigger_generic(user_input, {})

        return AgentResponse(
            success=result["success"],
            message=result["message"],
            agents_used=["workflow_agent"]
        )

    async def _handle_general_question(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> AgentResponse:
        """Handle general assistant questions"""
        try:
            # Build context from conversation history
            context = ""
            if conversation_history:
                context = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])

            prompt = f"""
Tu es l'assistant DisruptIQ, un assistant intelligent pour syndics de copropriété.

TES CAPACITÉS:
- Requêter les données (copropriétaires, copropriétés, fournisseurs)
- Chercher dans les documents (contrats, règlements, procédures)
- Générer et envoyer des emails
- Demander des devis aux fournisseurs
- Analyser des documents (factures, contrats)
- Déclencher des workflows automatisés

HISTORIQUE:
{context if context else "Aucun"}

QUESTION:
{user_input}

Réponds de manière claire, professionnelle et utile. Si tu peux aider avec une action spécifique, propose-la.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )

            return AgentResponse(
                success=True,
                message=response,
                agents_used=["orchestrator", "llm"],
                suggestions=[
                    "Rechercher dans mes documents",
                    "Voir la liste des copropriétaires",
                    "Générer un email",
                    "Demander un devis"
                ]
            )

        except Exception as e:
            logger.error("general_question_failed", error=str(e))
            return AgentResponse(
                success=False,
                message="Désolé, je n'ai pas pu traiter votre question.",
                agents_used=["orchestrator"]
            )

    def _is_procedural_query(self, query: str) -> bool:
        """
        Detect if query is asking for a procedure/steps/actions

        Args:
            query: User's question

        Returns:
            True if the query is procedural (asking "how to" or "what to do")
        """
        procedural_keywords = [
            "how to", "comment", "procédure", "étapes", "steps",
            "what to do", "que faire", "marche à suivre", "actions",
            "comment faire", "quoi faire", "procedure", "démarche"
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in procedural_keywords)

    async def _format_as_action_list(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Format RAG results as actionable step-by-step instructions using LLM

        Args:
            query: Original user query
            results: RAG search results with context

        Returns:
            Formatted action list with markdown
        """
        try:
            # Combine context from all results
            context = "\n\n".join([r.get("text", "")[:1000] for r in results])

            # Use LLM to extract and structure steps
            prompt = f"""À partir des documents suivants, extrais et structure les étapes à suivre pour : {query}

DOCUMENTS:
{context}

INSTRUCTIONS:
1. Identifie les actions concrètes à entreprendre
2. Structure-les en liste numérotée claire
3. Utilise des tirets (-) pour les sous-actions si nécessaire
4. Utilise le markdown pour le formatage (** pour gras)
5. Termine par une note si des informations importantes sont manquantes

FORMAT ATTENDU:
## 📋 Actions à suivre

1. **[Action principale]**
   - Sous-action A
   - Sous-action B

2. **[Action suivante]**
   - Details...

**Note:** [Informations complémentaires ou contacts]
"""

            action_list = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3  # Low temperature for consistent formatting
            )

            # Add sources footer
            sources_text = "\n\n---\n**📚 Sources:**\n" + "\n".join([
                f"- {r.get('metadata', {}).get('title', 'Document')} (pertinence: {r.get('score', 0):.0%})"
                for r in results[:3]
            ])

            return action_list + sources_text

        except Exception as e:
            logger.error("action_list_formatting_failed", error=str(e))
            # Fallback to simple formatting
            return self._format_as_informational(results)

    def _format_as_informational(self, results: List[Dict[str, Any]]) -> str:
        """
        Format RAG results as informational (non-procedural queries)

        Args:
            results: RAG search results

        Returns:
            Formatted informational response with markdown
        """
        response_parts = ["**Voici ce que j'ai trouvé dans les documents:**\n"]

        for i, doc in enumerate(results, 1):
            title = doc.get('metadata', {}).get('title', 'Document')
            text_preview = doc.get('text', '')[:300]
            score = doc.get('score', 0)

            response_parts.append(f"\n**{i}. {title}** (pertinence: {score:.0%})")
            response_parts.append(f"\n{text_preview}...\n")

        response_parts.append("\n---\n_Sources citées ci-dessus._")
        return "".join(response_parts)
