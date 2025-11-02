"""
Orchestrator Service
Intelligent routing between RAG and SQL modes based on user query
"""

import structlog
from typing import Dict, Any, Literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag_service import RAGService
from app.services.sql_agent_service import SQLAgentService
from app.services.llm_service import LLMService

logger = structlog.get_logger()

QueryMode = Literal["rag", "sql"]


class OrchestratorService:
    """
    Intelligent orchestrator that routes queries to appropriate service (RAG or SQL)
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()
        self.sql_agent = SQLAgentService()

    async def route_query(self, query: str) -> QueryMode:
        """
        Analyze query and determine if it should use RAG or SQL

        SQL queries typically:
        - Ask for counts, statistics, numbers
        - Search for specific records (emails, vendors, copropriétaires)
        - Use words like: "combien", "liste", "tous les", "nombre de"
        - Ask about database content directly

        RAG queries typically:
        - Ask for explanations, advice, context
        - Reference documents or knowledge
        - Use words like: "comment", "pourquoi", "explique", "conseil"
        - Ask about procedures, best practices, or domain knowledge

        Args:
            query: User's natural language query

        Returns:
            "rag" or "sql"
        """
        query_lower = query.lower().strip()

        # SQL indicators (strong signals for database queries)
        sql_keywords = [
            "combien", "nombre", "liste", "tous les", "toutes les",
            "affiche", "montre", "recherche", "trouve",
            "derniers", "dernières", "récents", "récentes",
            "statistiques", "total", "moyenne", "somme",
            "email", "emails", "vendor", "vendeur", "professionnels",
            "copropriétaires", "copropriétés", "documents",
            "actifs", "inactifs", "traités", "non traités"
        ]

        # RAG indicators (strong signals for knowledge/document queries)
        rag_keywords = [
            "comment", "pourquoi", "explique", "qu'est-ce",
            "conseil", "recommandation", "suggère",
            "procédure", "process", "workflow",
            "meilleur", "meilleures pratiques",
            "que penses-tu", "que sais-tu",
            "résume", "résumé", "synthèse"
        ]

        # Count matches
        sql_score = sum(1 for kw in sql_keywords if kw in query_lower)
        rag_score = sum(1 for kw in rag_keywords if kw in query_lower)

        # Decision logic
        if sql_score > rag_score:
            logger.info("routing_to_sql", query=query[:50], sql_score=sql_score, rag_score=rag_score)
            return "sql"
        elif rag_score > sql_score:
            logger.info("routing_to_rag", query=query[:50], sql_score=sql_score, rag_score=rag_score)
            return "rag"
        else:
            # Default to RAG for ambiguous queries (safer, more conversational)
            logger.info("routing_to_rag_default", query=query[:50], reason="ambiguous")
            return "rag"

    async def process_query(
        self,
        query: str,
        db: AsyncSession,
        conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        Process query by routing to appropriate service

        Args:
            query: User's natural language query
            db: Database session (for SQL queries)
            conversation_history: Previous messages (for RAG context)

        Returns:
            Dict with response, mode used, and additional data
        """
        # Determine routing
        mode = await self.route_query(query)

        try:
            if mode == "sql":
                # Use SQL Agent
                result = await self.sql_agent.execute_natural_query(
                    query=query,
                    db=db,
                    operation_type="SELECT"
                )

                # Format response
                if result["success"]:
                    response_text = result.get("explanation", "")
                    if result.get("results") and len(result["results"]) > 0:
                        response_text += f"\n\n📊 {result.get('row_count', 0)} résultat(s) trouvé(s)."

                    return {
                        "mode": "sql",
                        "response": response_text or "Requête exécutée avec succès.",
                        "sql_query": result.get("sql"),
                        "results": result.get("results", []),
                        "row_count": result.get("row_count", 0),
                        "success": True
                    }
                else:
                    return {
                        "mode": "sql",
                        "response": f"❌ Erreur SQL: {result.get('error', 'Erreur inconnue')}",
                        "success": False,
                        "error": result.get("error")
                    }

            else:  # RAG mode
                # Search for context
                sources = await self.rag_service.search(query, limit=3)

                # Build context
                context = "\n\n".join([
                    f"Document: {src.get('metadata', {}).get('title', 'Sans titre')}\n{src.get('text', '')}"
                    for src in sources
                ])

                # Get answer from LLM
                answer = await self.llm_service.answer_question(
                    question=query,
                    context=context,
                    conversation_history=conversation_history or []
                )

                return {
                    "mode": "rag",
                    "response": answer,
                    "sources": sources,
                    "success": True
                }

        except Exception as e:
            logger.error("orchestrator_error", error=str(e), mode=mode, query=query[:50])
            return {
                "mode": mode,
                "response": f"❌ Une erreur s'est produite: {str(e)}",
                "success": False,
                "error": str(e)
            }
