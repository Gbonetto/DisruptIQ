"""
Intent Classifier v2.0 - Advanced disambiguation for RAG vs SQL

Features:
- Keyword-based scoring (SQL vs RAG signals)
- LLM semantic analysis
- Confidence scoring (0-1)
- Hybrid intent detection
- Clarification requests for ambiguous queries
- Contextual boosting

Intents:
- SQL_ONLY: Query structured database only
- RAG_ONLY: Search documents only
- HYBRID: Use both SQL and RAG, then fuse
- AMBIGUOUS: Request user clarification
"""

import re
import structlog
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel

from app.services.llm_service import LLMService

logger = structlog.get_logger()


class ExecutionIntent(str, Enum):
    """Execution intent types"""
    SQL_ONLY = "SQL_ONLY"
    RAG_ONLY = "RAG_ONLY"
    HYBRID = "HYBRID"
    AMBIGUOUS = "AMBIGUOUS"


class ClassificationResult(BaseModel):
    """Classification result with confidence"""
    intent: ExecutionIntent
    confidence: float  # 0.0 - 1.0
    sql_score: float  # 0.0 - 1.0
    rag_score: float  # 0.0 - 1.0
    reasoning: str
    clarification_options: Optional[List[str]] = None
    suggested_action: str  # "execute_sql" | "execute_rag" | "execute_both" | "ask_clarification"


class IntentClassifierV2:
    """
    Advanced intent classifier with disambiguation

    Determines whether a query should:
    - Query SQL database only
    - Search RAG documents only
    - Use both (HYBRID)
    - Request clarification (AMBIGUOUS)
    """

    def __init__(self):
        self.llm_service = LLMService()

        # SQL indicator keywords with weights
        self.sql_keywords = {
            # Quantitative
            "combien": 0.85,
            "nombre": 0.85,
            "total": 0.80,
            "count": 0.90,
            "quantité": 0.80,

            # Aggregations
            "moyenne": 0.90,
            "somme": 0.90,
            "maximum": 0.85,
            "minimum": 0.85,
            "statistique": 0.90,

            # Lists & filters
            "liste": 0.75,
            "tous les": 0.80,
            "toutes les": 0.80,
            "filtrer": 0.85,
            "avec profession": 0.90,
            "de catégorie": 0.85,
            "dont": 0.70,

            # Comparisons
            "compare": 0.85,
            "différence": 0.80,
            "écart": 0.80,

            # Specific entities (often in SQL)
            "copropriétaire": 0.60,  # Can be doc or SQL
            "copropriété": 0.60,
            "professionnel": 0.65,
            "fournisseur": 0.65,
            "budget": 0.55,  # Often SQL but can be doc
        }

        # RAG indicator keywords with weights
        self.rag_keywords = {
            # Documents (STRONG signals)
            "document": 0.90,
            "document sélectionné": 1.0,  # VERY STRONG
            "ce document": 1.0,  # VERY STRONG
            "le document": 0.95,
            "dans le document": 1.0,  # VERY STRONG
            "fichier": 0.90,
            "ce fichier": 0.95,
            "pdf": 0.95,
            "contrat": 0.85,
            "règlement": 0.85,
            "procédure": 0.90,
            "charte": 0.90,
            "uploadé": 0.90,

            # Content queries (STRONG)
            "de quoi parle": 1.0,  # VERY STRONG
            "que dit": 0.95,
            "que contient": 0.95,
            "contenu": 0.85,
            "résume": 0.95,
            "résumé": 0.95,
            "détaille": 0.85,
            "explique": 0.85,

            # Semantic search
            "parle de": 0.85,
            "mentionne": 0.90,
            "traite de": 0.85,
            "selon le": 0.80,
            "dans le fichier": 0.95,

            # Procedural
            "comment faire": 0.90,
            "comment procéder": 0.95,
            "quelles sont les étapes": 0.95,
            "marche à suivre": 0.95,
        }

        logger.info("intent_classifier_v2_initialized",
                    sql_keywords=len(self.sql_keywords),
                    rag_keywords=len(self.rag_keywords))

    async def classify_with_confidence(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        Classify query intent with confidence scoring

        Args:
            query: User's question
            context: Optional context (uploaded docs, conversation history)

        Returns:
            ClassificationResult with intent, confidence, and reasoning
        """
        try:
            # Step 1: Keyword-based scoring
            sql_keyword_score = self._compute_sql_score(query)
            rag_keyword_score = self._compute_rag_score(query)

            logger.debug("keyword_scores",
                        sql=sql_keyword_score,
                        rag=rag_keyword_score,
                        query=query[:50])

            # Step 2: Contextual boosting
            sql_boost, rag_boost = self._compute_contextual_boost(context)

            sql_keyword_score *= sql_boost
            rag_keyword_score *= rag_boost

            # Step 3: LLM semantic analysis
            llm_scores = await self._llm_classify(query, context)

            # Step 4: Weighted fusion (keywords 40%, LLM 60%)
            final_sql = (0.4 * sql_keyword_score) + (0.6 * llm_scores["sql"])
            final_rag = (0.4 * rag_keyword_score) + (0.6 * llm_scores["rag"])

            logger.info("classification_scores",
                       query=query[:50],
                       sql_final=final_sql,
                       rag_final=final_rag,
                       sql_keywords=sql_keyword_score,
                       rag_keywords=rag_keyword_score,
                       sql_llm=llm_scores["sql"],
                       rag_llm=llm_scores["rag"])

            # Step 5: Decision logic
            return self._determine_intent(
                query=query,
                sql_score=final_sql,
                rag_score=final_rag,
                context=context
            )

        except Exception as e:
            logger.error("classification_failed", error=str(e), exc_info=True)
            # Fallback: assume RAG_ONLY for safety
            return ClassificationResult(
                intent=ExecutionIntent.RAG_ONLY,
                confidence=0.5,
                sql_score=0.0,
                rag_score=0.5,
                reasoning=f"Classification failed: {str(e)}, defaulting to RAG",
                suggested_action="execute_rag"
            )

    def _compute_sql_score(self, query: str) -> float:
        """
        Compute SQL likelihood based on keywords

        Returns:
            Score 0.0-1.0
        """
        score = 0.0
        query_lower = query.lower()
        matches = []

        for keyword, weight in self.sql_keywords.items():
            if keyword in query_lower:
                score += weight
                matches.append(keyword)

        # Normalize: cap at 1.0
        normalized = min(score / 2.0, 1.0)  # Divide by 2 to account for multiple matches

        logger.debug("sql_score_computed",
                    score=normalized,
                    matches=matches)

        return normalized

    def _compute_rag_score(self, query: str) -> float:
        """
        Compute RAG likelihood based on keywords

        Returns:
            Score 0.0-1.0
        """
        score = 0.0
        query_lower = query.lower()
        matches = []

        for keyword, weight in self.rag_keywords.items():
            if keyword in query_lower:
                score += weight
                matches.append(keyword)

        # Normalize
        normalized = min(score / 2.0, 1.0)

        logger.debug("rag_score_computed",
                    score=normalized,
                    matches=matches)

        return normalized

    def _compute_contextual_boost(
        self,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[float, float]:
        """
        Compute contextual boost factors

        Args:
            context: Optional context

        Returns:
            (sql_boost, rag_boost) tuple of multipliers (typically 1.0-1.3)
        """
        sql_boost = 1.0
        rag_boost = 1.0

        if not context:
            return (sql_boost, rag_boost)

        # Boost RAG if user has uploaded documents
        if context.get("has_uploaded_documents"):
            rag_boost = 1.2
            logger.debug("context_boost", reason="has_uploaded_documents", rag_boost=rag_boost)

        # Boost SQL if last query was SQL (user in "SQL mode")
        if context.get("last_query_was_sql"):
            sql_boost = 1.1
            logger.debug("context_boost", reason="last_query_was_sql", sql_boost=sql_boost)

        # Boost RAG if last query was RAG
        if context.get("last_query_was_rag"):
            rag_boost = 1.1

        return (sql_boost, rag_boost)

    async def _llm_classify(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Use LLM for semantic classification

        Args:
            query: User question
            context: Optional context

        Returns:
            {"sql": 0.0-1.0, "rag": 0.0-1.0}
        """
        prompt = f"""Analyse cette question et détermine si elle nécessite:
1. Une requête SQL (base de données structurées : copropriétaires, copropriétés, professionnels)
2. Une recherche RAG (documents PDF uploadés : contrats, règlements, procédures)
3. Les deux
4. Aucun (trop vague)

QUESTION: "{query}"

CONTEXTE:
{context if context else "Aucun"}

RÈGLES:
- SQL: Questions quantitatives, listes, agrégations, filtres
  Exemples: "Combien de copropriétaires ?", "Liste des plombiers", "Moyenne des budgets"

- RAG: Questions sur contenu de documents, procédures, explications
  Exemples: "Que dit le règlement ?", "Procédure dégât des eaux", "Résume le contrat"

- Les deux: Questions nécessitant données ET documents
  Exemples: "Tarif du plombier ?" (DB + contrat), "Contact du plombier" (DB + validation doc)

Réponds avec un score 0-10 pour chaque:
Format: SQL: X/10, RAG: Y/10

Réponds UNIQUEMENT avec les scores, rien d'autre."""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=50
            )

            # Parse "SQL: 8/10, RAG: 2/10"
            sql_match = re.search(r'SQL:\s*(\d+)/10', response, re.IGNORECASE)
            rag_match = re.search(r'RAG:\s*(\d+)/10', response, re.IGNORECASE)

            sql_score = int(sql_match.group(1)) / 10.0 if sql_match else 0.5
            rag_score = int(rag_match.group(1)) / 10.0 if rag_match else 0.5

            logger.debug("llm_classification", sql=sql_score, rag=rag_score, response=response)

            return {"sql": sql_score, "rag": rag_score}

        except Exception as e:
            logger.error("llm_classification_failed", error=str(e))
            # Fallback: neutral scores
            return {"sql": 0.5, "rag": 0.5}

    def _determine_intent(
        self,
        query: str,
        sql_score: float,
        rag_score: float,
        context: Optional[Dict[str, Any]]
    ) -> ClassificationResult:
        """
        Determine final intent based on scores

        IMPROVED Decision thresholds (less strict, more intelligent):
        - SQL_ONLY: sql > 0.65 AND rag < 0.5 AND (sql - rag > 0.2)
        - RAG_ONLY: rag > 0.65 AND sql < 0.5 AND (rag - sql > 0.2)
        - HYBRID: both > 0.5 OR (sql > 0.4 AND rag > 0.4 AND close scores)
        - AMBIGUOUS: ONLY if both < 0.35 (very low confidence)

        Args:
            query: User question
            sql_score: Final SQL score (0-1)
            rag_score: Final RAG score (0-1)
            context: Optional context

        Returns:
            ClassificationResult
        """
        # Calculate score difference
        score_diff = abs(sql_score - rag_score)

        # Decision logic (IMPROVED - less AMBIGUOUS, more decisive)

        # 1. Strong SQL dominance
        if sql_score > 0.65 and rag_score < 0.5 and (sql_score - rag_score > 0.2):
            return ClassificationResult(
                intent=ExecutionIntent.SQL_ONLY,
                confidence=sql_score,
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=f"Clear SQL intent (SQL: {sql_score:.2f} >> RAG: {rag_score:.2f})",
                suggested_action="execute_sql"
            )

        # 2. Strong RAG dominance
        elif rag_score > 0.65 and sql_score < 0.5 and (rag_score - sql_score > 0.2):
            return ClassificationResult(
                intent=ExecutionIntent.RAG_ONLY,
                confidence=rag_score,
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=f"Clear RAG intent (RAG: {rag_score:.2f} >> SQL: {sql_score:.2f})",
                suggested_action="execute_rag"
            )

        # 3. Moderate SQL preference (lower threshold)
        elif sql_score > 0.5 and sql_score > rag_score and score_diff > 0.15:
            return ClassificationResult(
                intent=ExecutionIntent.SQL_ONLY,
                confidence=sql_score,
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=f"SQL preferred (SQL: {sql_score:.2f} > RAG: {rag_score:.2f})",
                suggested_action="execute_sql"
            )

        # 4. Moderate RAG preference (lower threshold)
        elif rag_score > 0.5 and rag_score > sql_score and score_diff > 0.15:
            return ClassificationResult(
                intent=ExecutionIntent.RAG_ONLY,
                confidence=rag_score,
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=f"RAG preferred (RAG: {rag_score:.2f} > SQL: {sql_score:.2f})",
                suggested_action="execute_rag"
            )

        # 5. Both applicable → HYBRID
        elif sql_score > 0.4 and rag_score > 0.4:
            confidence = (sql_score + rag_score) / 2
            return ClassificationResult(
                intent=ExecutionIntent.HYBRID,
                confidence=confidence,
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=f"Both applicable (SQL: {sql_score:.2f}, RAG: {rag_score:.2f}) → hybrid",
                suggested_action="execute_both"
            )

        # 6. AMBIGUOUS only if BOTH very low (< 0.35)
        elif sql_score < 0.35 and rag_score < 0.35:
            return ClassificationResult(
                intent=ExecutionIntent.AMBIGUOUS,
                confidence=max(sql_score, rag_score),
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=f"Very low confidence (SQL: {sql_score:.2f}, RAG: {rag_score:.2f})",
                suggested_action="ask_clarification",
                clarification_options=self._generate_clarification_options(query, sql_score, rag_score)
            )

        # 7. Fallback: choose the higher score (even if low)
        else:
            if sql_score > rag_score:
                intent = ExecutionIntent.SQL_ONLY
                confidence = sql_score
                action = "execute_sql"
                reasoning = f"SQL slightly preferred (SQL: {sql_score:.2f} vs RAG: {rag_score:.2f})"
            else:
                intent = ExecutionIntent.RAG_ONLY
                confidence = rag_score
                action = "execute_rag"
                reasoning = f"RAG slightly preferred (RAG: {rag_score:.2f} vs SQL: {sql_score:.2f})"

            return ClassificationResult(
                intent=intent,
                confidence=confidence,
                sql_score=sql_score,
                rag_score=rag_score,
                reasoning=reasoning,
                suggested_action=action
            )

    def _generate_clarification_options(
        self,
        query: str,
        sql_score: float,
        rag_score: float
    ) -> List[str]:
        """
        Generate clarification options for ambiguous queries

        Args:
            query: User question
            sql_score: SQL likelihood
            rag_score: RAG likelihood

        Returns:
            List of clarification options
        """
        options = []

        # Always offer both primary options
        if sql_score > 0.2:
            options.append("Consulter la base de données (listes, statistiques)")

        if rag_score > 0.2:
            options.append("Chercher dans les documents uploadés (contrats, règlements)")

        # If both moderate, offer hybrid
        if sql_score > 0.3 and rag_score > 0.3:
            options.append("Les deux : combiner base de données et documents")

        # Fallback
        if not options:
            options = [
                "Consulter la base de données",
                "Chercher dans les documents",
                "Les deux"
            ]

        return options
