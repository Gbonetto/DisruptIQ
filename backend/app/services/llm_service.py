"""
LLM Service
Wrapper for Mistral AI (primary), OpenAI/Anthropic (fallback)
Migrated to Mistral for better French support, GDPR compliance, and lower costs
"""

import structlog
from typing import List, Dict, Any, Optional
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage

from app.core.config import settings

logger = structlog.get_logger()


class LLMService:
    """Service for LLM operations (Mistral AI primary)"""

    def __init__(self):
        # Initialize Mistral AI (primary) - European, GDPR-compliant, French-optimized
        self.chat_model = ChatMistralAI(
            model=settings.MISTRAL_MODEL,
            api_key=settings.MISTRAL_API_KEY,
            temperature=0.1,
            timeout=120,  # 120 seconds timeout
        )

        # Initialize Mistral embeddings (1024 dimensions)
        self.embeddings = MistralAIEmbeddings(
            model=settings.MISTRAL_EMBEDDING_MODEL,
            api_key=settings.MISTRAL_API_KEY
        )

        logger.info("mistral_ai_initialized", model=settings.MISTRAL_MODEL, embedding_model=settings.MISTRAL_EMBEDDING_MODEL)

        # OpenAI fallback (deprecated but kept for compatibility)
        self.fallback_model = None
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "":
            try:
                from langchain_openai import ChatOpenAI
                self.fallback_model = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                    temperature=0.1,
                    request_timeout=120.0
                )
                logger.info("openai_fallback_enabled")
            except Exception as e:
                logger.warning("openai_fallback_init_failed", error=str(e))
        else:
            logger.info("openai_fallback_disabled")

    async def classify_email_urgency(
        self,
        subject: str,
        sender: str,
        body: str,
        snippet: str
    ) -> str:
        """
        Classify email urgency using Mistral AI

        Returns: "urgent", "important", or "routine"
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es un assistant spécialisé dans la classification d'emails pour un syndic de copropriété.

Classe chaque email dans une de ces catégories:
- URGENT: Dégâts des eaux, pannes urgentes, accidents, situations d'urgence
- IMPORTANT: Devis, relances, réclamations, assemblées générales
- ROUTINE: Informations, confirmations, factures normales

Réponds uniquement par: urgent, important, ou routine"""),
            ("human", f"""Classe cet email:

Expéditeur: {sender}
Sujet: {subject}
Contenu: {snippet}

Urgence:""")
        ])

        try:
            messages = prompt.format_messages()
            response = await self.chat_model.ainvoke(messages)
            urgency = response.content.strip().lower()

            # Validate response
            if urgency not in ['urgent', 'important', 'routine']:
                logger.warning("invalid_urgency_classification", response=urgency)
                urgency = 'routine'

            return urgency

        except Exception as e:
            logger.error("llm_classification_error", error=str(e), provider="mistral")
            # Try fallback model
            if self.fallback_model:
                try:
                    logger.info("using_openai_fallback")
                    messages = prompt.format_messages()
                    response = await self.fallback_model.ainvoke(messages)
                    return response.content.strip().lower()
                except:
                    pass

            # Default to routine if all fails
            return 'routine'

    async def generate_email(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a professional email based on prompt and context

        Returns:
            Dict with 'subject', 'body', 'tone'
        """
        system_prompt = """Tu es un assistant qui génère des emails professionnels pour un syndic de copropriété.

Les emails doivent être:
- Clairs et concis
- Professionnels mais courtois
- Bien formatés
- En français formel

Réponds au format JSON:
{
    "subject": "Objet de l'email",
    "body": "Corps de l'email avec formules de politesse"
}"""

        context_str = ""
        if context:
            context_str = f"\n\nContexte additionnel:\n{context}"

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Génère un email pour: {prompt}{context_str}")
            ]

            response = await self.chat_model.ainvoke(messages)

            # Parse JSON response
            import json
            result = json.loads(response.content)

            logger.info("email_generated", prompt=prompt[:50], provider="mistral")
            return result

        except Exception as e:
            logger.error("email_generation_error", error=str(e), provider="mistral")
            return {
                "subject": "Email",
                "body": "Erreur lors de la génération de l'email."
            }

    async def extract_document_info(
        self,
        text: str,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured information from document text using Mistral AI

        Returns:
            Dict with extracted fields
        """
        system_prompt = """Tu es un assistant qui analyse des documents pour un syndic.

Extrait les informations pertinentes et retourne au format JSON:
{
    "document_type": "facture|contrat|courrier|pv_ag|autre",
    "vendor": "nom du fournisseur si applicable",
    "amount": montant en euros si facture,
    "date": "date du document au format YYYY-MM-DD",
    "summary": "résumé en une phrase",
    "tags": ["tag1", "tag2"]
}"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Analyse ce document:\n\n{text[:2000]}")
            ]

            response = await self.chat_model.ainvoke(messages)

            # Parse JSON response
            import json
            result = json.loads(response.content)

            logger.info("document_analyzed", doc_type=result.get('document_type'), provider="mistral")
            return result

        except Exception as e:
            logger.error("document_analysis_error", error=str(e), provider="mistral")
            return {
                "document_type": "autre",
                "summary": "Analyse non disponible"
            }

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for a list of texts using Mistral AI (1024 dimensions)

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors (1024-dimensional)
        """
        try:
            embeddings = await self.embeddings.aembed_documents(texts)
            logger.info("embeddings_generated", count=len(texts), dimensions=1024, provider="mistral")
            return embeddings

        except Exception as e:
            logger.error("embeddings_error", error=str(e), provider="mistral")
            return []

    async def answer_question(
        self,
        question: str,
        context: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Answer a question based on context (RAG) using Mistral AI

        Args:
            question: User's question
            context: Retrieved context from vector DB
            conversation_history: Previous messages

        Returns:
            Answer string
        """
        system_prompt = """Tu es DisruptIQ, l'assistant intelligent pour syndics de copropriété.

Tu réponds aux questions en te basant sur les documents fournis.
Si l'information n'est pas dans le contexte, dis-le clairement.
Sois concis, précis et professionnel."""

        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-5:]:  # Last 5 messages
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                # Add AI messages if needed

        # Add current question with context
        messages.append(HumanMessage(
            content=f"""Contexte (documents pertinents):
{context}

Question: {question}

Réponse:"""
        ))

        try:
            response = await self.chat_model.ainvoke(messages)
            logger.info("question_answered", question=question[:50], provider="mistral")
            return response.content

        except Exception as e:
            logger.error("answer_error", error=str(e), provider="mistral")
            return "Désolé, je n'ai pas pu répondre à votre question."

    async def generate_response(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """
        Generic text generation method using Mistral AI

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        try:
            response = await self.chat_model.ainvoke(
                [HumanMessage(content=prompt)],
                max_tokens=max_tokens,
                temperature=temperature
            )
            logger.info("response_generated", provider="mistral")
            return response.content

        except Exception as e:
            logger.error("generate_response_error", error=str(e), provider="mistral")

            # Try OpenAI fallback if available
            if self.fallback_model:
                try:
                    logger.info("using_openai_fallback")
                    response = await self.fallback_model.ainvoke(
                        [HumanMessage(content=prompt)],
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    return response.content
                except Exception as fallback_error:
                    logger.error("fallback_error", error=str(fallback_error))

            raise Exception(f"Failed to generate response: {str(e)}")
