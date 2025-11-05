"""
Planner DAG - Génère un plan d'exécution structuré (DAG JSON)

Transforme l'intent + query en plan d'exécution avec steps explicites.
Chaque step spécifie le tool à utiliser et ses paramètres.
"""

import structlog
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

from app.services.llm_service import LLMService

logger = structlog.get_logger()


class StepDependency(str, Enum):
    """Type de dépendance entre steps"""
    NONE = "none"  # Pas de dépendance, peut s'exécuter en parallèle
    SEQUENTIAL = "sequential"  # Doit attendre le step précédent
    CONDITIONAL = "conditional"  # S'exécute seulement si condition satisfaite


class PlanStep(BaseModel):
    """Une étape du plan d'exécution"""
    step_number: int = Field(..., description="Numéro de l'étape (0, 1, 2, ...)")
    tool: str = Field(..., description="Tool/skill à exécuter (ex: sql.plan, rag.search)")
    input: Dict[str, Any] = Field(default_factory=dict, description="Paramètres d'entrée")
    dependency: StepDependency = Field(
        default=StepDependency.SEQUENTIAL,
        description="Type de dépendance"
    )
    depends_on: Optional[List[int]] = Field(
        default=None,
        description="Numéros des steps dont dépend cette étape"
    )
    condition: Optional[str] = Field(
        default=None,
        description="Condition pour exécuter (ex: 'step0.confidence > 0.7')"
    )
    description: str = Field(..., description="Description lisible de l'étape")


class ExecutionPlan(BaseModel):
    """Plan d'exécution DAG complet"""
    goal: str = Field(..., description="Objectif de l'exécution")
    intent: str = Field(..., description="Intent détecté (SQL_ONLY, RAG_ONLY, HYBRID, etc.)")
    steps: List[PlanStep] = Field(default_factory=list, description="Liste des étapes")
    success_criteria: str = Field(..., description="Critère de succès")
    estimated_tokens: Optional[int] = Field(None, description="Estimation tokens total")
    estimated_latency_ms: Optional[int] = Field(None, description="Estimation latence")


class PlannerDAG:
    """
    Planner DAG - Génère un plan d'exécution structuré.

    Responsabilités:
    1. Analyser l'intent et la query
    2. Déterminer les steps nécessaires
    3. Identifier les dépendances entre steps
    4. Générer un JSON DAG exécutable
    5. Estimer coûts (tokens, latence)

    Le plan généré sera:
    - Traçable (stocké dans agent_runs.plan_json)
    - Auditable (chaque décision est explicite)
    - Debuggable (on peut rejouer chaque step)
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("planner_dag_initialized")

    async def generate_plan(
        self,
        intent: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        entities: Optional[Dict[str, List[str]]] = None
    ) -> ExecutionPlan:
        """
        Génère un plan d'exécution pour une query donnée.

        Args:
            intent: Intent détecté (SQL_ONLY, RAG_ONLY, HYBRID, etc.)
            query: Query utilisateur
            context: Contexte additionnel (conversation, hints)
            entities: Entités extraites (personnes, lieux, dates)

        Returns:
            ExecutionPlan avec steps et dépendances
        """
        logger.info(
            "planner_dag_generating_plan",
            intent=intent,
            query_len=len(query),
            has_entities=entities is not None
        )

        # Sélectionner le générateur de plan selon l'intent
        if intent == "SQL_ONLY":
            plan = self._plan_sql_only(query, entities)
        elif intent == "RAG_ONLY":
            plan = self._plan_rag_only(query, entities)
        elif intent == "HYBRID":
            plan = self._plan_hybrid(query, entities)
        elif intent == "EMAIL":
            plan = self._plan_email(query, context, entities)
        elif intent == "N8N":
            plan = self._plan_n8n(query, context)
        elif intent == "WEB":
            plan = self._plan_web(query)
        elif intent == "OCR":
            plan = self._plan_ocr(query, context)
        else:
            # Intent inconnu, plan générique
            plan = self._plan_generic(intent, query)

        logger.info(
            "planner_dag_plan_generated",
            intent=intent,
            steps_count=len(plan.steps),
            estimated_tokens=plan.estimated_tokens
        )

        return plan

    def _plan_sql_only(
        self,
        query: str,
        entities: Optional[Dict[str, List[str]]] = None
    ) -> ExecutionPlan:
        """Plan pour SQL_ONLY"""
        steps = [
            PlanStep(
                step_number=0,
                tool="sql.plan",
                input={"query": query, "entities": entities},
                dependency=StepDependency.NONE,
                description="Traduire la query en SQL"
            ),
            PlanStep(
                step_number=1,
                tool="sql.execute",
                input={"sql": "{{step0.sql}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Exécuter la requête SQL"
            ),
            PlanStep(
                step_number=2,
                tool="evaluator.check",
                input={
                    "rules": ["sql_no_error", "sql_results_not_empty"],
                    "results": "{{step1.rows}}"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[1],
                description="Vérifier que les résultats SQL sont valides"
            )
        ]

        return ExecutionPlan(
            goal=f"Exécuter query SQL: {query[:100]}",
            intent="SQL_ONLY",
            steps=steps,
            success_criteria="Résultats SQL retournés et validés",
            estimated_tokens=500,
            estimated_latency_ms=1500
        )

    def _plan_rag_only(
        self,
        query: str,
        entities: Optional[Dict[str, List[str]]] = None
    ) -> ExecutionPlan:
        """Plan pour RAG_ONLY"""
        steps = [
            PlanStep(
                step_number=0,
                tool="rag.search",
                input={"query": query, "top_k": 5, "entities": entities},
                dependency=StepDependency.NONE,
                description="Rechercher dans la base documentaire (RAG)"
            ),
            PlanStep(
                step_number=1,
                tool="rag.rerank",
                input={"query": query, "chunks": "{{step0.chunks}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Reranker les chunks pertinents"
            ),
            PlanStep(
                step_number=2,
                tool="rag.summarize",
                input={
                    "query": query,
                    "chunks": "{{step1.chunks}}",
                    "with_citations": True
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[1],
                description="Synthétiser avec citations inline [1][2][3]"
            ),
            PlanStep(
                step_number=3,
                tool="evaluator.check",
                input={
                    "rules": ["rag_has_citations", "rag_min_sources_2"],
                    "response": "{{step2.response}}",
                    "citations": "{{step2.citations}}"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[2],
                description="Vérifier présence citations (règle: 0 citation → refus)"
            )
        ]

        return ExecutionPlan(
            goal=f"Recherche RAG: {query[:100]}",
            intent="RAG_ONLY",
            steps=steps,
            success_criteria="Réponse avec au moins 2 citations",
            estimated_tokens=1500,
            estimated_latency_ms=3000
        )

    def _plan_hybrid(
        self,
        query: str,
        entities: Optional[Dict[str, List[str]]] = None
    ) -> ExecutionPlan:
        """Plan pour HYBRID (SQL + RAG en parallèle puis fusion)"""
        steps = [
            # Step 0-1: Exécution parallèle SQL + RAG
            PlanStep(
                step_number=0,
                tool="sql.plan",
                input={"query": query, "entities": entities},
                dependency=StepDependency.NONE,
                description="Traduire en SQL"
            ),
            PlanStep(
                step_number=1,
                tool="rag.search",
                input={"query": query, "top_k": 5, "entities": entities},
                dependency=StepDependency.NONE,  # Parallèle avec step 0
                description="Recherche RAG parallèle"
            ),
            # Step 2-3: Exécution séquentielle
            PlanStep(
                step_number=2,
                tool="sql.execute",
                input={"sql": "{{step0.sql}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Exécuter SQL"
            ),
            PlanStep(
                step_number=3,
                tool="rag.summarize",
                input={"query": query, "chunks": "{{step1.chunks}}", "with_citations": True},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[1],
                description="Synthétiser RAG"
            ),
            # Step 4: Fusion des résultats
            PlanStep(
                step_number=4,
                tool="fusion.merge",
                input={
                    "query": query,
                    "sql_results": "{{step2.rows}}",
                    "rag_response": "{{step3.response}}",
                    "rag_citations": "{{step3.citations}}",
                    "detect_conflicts": True
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[2, 3],
                description="Fusionner SQL + RAG (détecter conflits)"
            ),
            # Step 5: Évaluation
            PlanStep(
                step_number=5,
                tool="evaluator.check",
                input={
                    "rules": ["hybrid_no_contradiction", "hybrid_sources_attributed"],
                    "merged_response": "{{step4.response}}",
                    "conflicts": "{{step4.conflicts}}"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[4],
                description="Vérifier cohérence et attribution sources"
            )
        ]

        return ExecutionPlan(
            goal=f"Exécution hybride SQL+RAG: {query[:100]}",
            intent="HYBRID",
            steps=steps,
            success_criteria="SQL et RAG fusionnés sans conflits critiques",
            estimated_tokens=2500,
            estimated_latency_ms=4000
        )

    def _plan_email(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        entities: Optional[Dict[str, List[str]]] = None
    ) -> ExecutionPlan:
        """Plan pour EMAIL (génération safe-send)"""
        steps = [
            # Step 0: Récupérer contexte (destinataires candidats)
            PlanStep(
                step_number=0,
                tool="sql.plan",
                input={
                    "query": f"Récupérer contacts pour: {query}",
                    "entities": entities
                },
                dependency=StepDependency.NONE,
                description="Identifier destinataires candidats (SQL)"
            ),
            PlanStep(
                step_number=1,
                tool="sql.execute",
                input={"sql": "{{step0.sql}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Récupérer contacts"
            ),
            # Step 2: Chercher evidence dans RAG
            PlanStep(
                step_number=2,
                tool="rag.search",
                input={"query": query, "top_k": 3},
                dependency=StepDependency.NONE,  # Parallèle avec step 0-1
                description="Chercher evidence/procédures (RAG)"
            ),
            # Step 3: Générer brouillon
            PlanStep(
                step_number=3,
                tool="email.generate",
                input={
                    "topic": query,
                    "recipient_candidates": "{{step1.rows}}",
                    "evidence": "{{step2.chunks}}",
                    "context": context
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[1, 2],
                description="Générer brouillon email avec sources"
            ),
            # Step 4: Preview obligatoire
            PlanStep(
                step_number=4,
                tool="email.preview",
                input={
                    "draft_id": "{{step3.draft_id}}",
                    "checklist": [
                        "Destinataires corrects",
                        "Sources attachées",
                        "Ton approprié",
                        "Pas d'informations sensibles"
                    ]
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[3],
                description="Afficher preview + checklist validation"
            ),
            # Step 5: Évaluation (pas d'envoi automatique)
            PlanStep(
                step_number=5,
                tool="evaluator.check",
                input={
                    "rules": ["email_has_evidence", "email_preview_shown"],
                    "draft": "{{step3.draft}}"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[4],
                description="Vérifier evidence présente (règle: 0 evidence → preview obligatoire)"
            )
        ]

        return ExecutionPlan(
            goal=f"Générer email safe-send: {query[:100]}",
            intent="EMAIL",
            steps=steps,
            success_criteria="Brouillon généré avec preview + checklist validée",
            estimated_tokens=1800,
            estimated_latency_ms=3500
        )

    def _plan_n8n(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """Plan pour N8N (workflow avec preview si danger élevé)"""
        steps = [
            PlanStep(
                step_number=0,
                tool="n8n.preview",
                input={
                    "workflow_id": "{{workflow_id}}",  # À remplir par orchestrator
                    "inputs": "{{inputs}}",
                    "dry_run": True
                },
                dependency=StepDependency.NONE,
                description="Preview du workflow N8N (dry run)"
            ),
            PlanStep(
                step_number=1,
                tool="evaluator.check",
                input={
                    "rules": ["n8n_preview_if_danger_high"],
                    "workflow": "{{step0.workflow}}",
                    "danger_level": "{{step0.danger_level}}"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Vérifier niveau de danger (règle: high danger → preview)"
            ),
            PlanStep(
                step_number=2,
                tool="n8n.trigger",
                input={
                    "workflow_id": "{{workflow_id}}",
                    "inputs": "{{inputs}}",
                    "correlation_id": "{{correlation_id}}"
                },
                dependency=StepDependency.CONDITIONAL,
                depends_on=[1],
                condition="step1.evaluator_passed == True",
                description="Déclencher workflow N8N (si validé)"
            )
        ]

        return ExecutionPlan(
            goal=f"Déclencher workflow N8N: {query[:100]}",
            intent="N8N",
            steps=steps,
            success_criteria="Workflow déclenché avec preview si danger élevé",
            estimated_tokens=800,
            estimated_latency_ms=2000
        )

    def _plan_web(self, query: str) -> ExecutionPlan:
        """Plan pour WEB (recherche web + intégration RAG)"""
        steps = [
            PlanStep(
                step_number=0,
                tool="web.search",
                input={"query": query, "top_k": 5},
                dependency=StepDependency.NONE,
                description="Rechercher sur le web"
            ),
            PlanStep(
                step_number=1,
                tool="web.extract",
                input={"urls": "{{step0.urls}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Extraire contenu des URLs"
            ),
            PlanStep(
                step_number=2,
                tool="rag.summarize",
                input={
                    "query": query,
                    "chunks": "{{step1.content}}",
                    "with_citations": True,
                    "source_type": "web"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[1],
                description="Synthétiser avec citations URLs"
            ),
            PlanStep(
                step_number=3,
                tool="evaluator.check",
                input={
                    "rules": ["web_urls_cited"],
                    "response": "{{step2.response}}",
                    "citations": "{{step2.citations}}"
                },
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[2],
                description="Vérifier citation URLs obligatoire"
            )
        ]

        return ExecutionPlan(
            goal=f"Recherche web: {query[:100]}",
            intent="WEB",
            steps=steps,
            success_criteria="Réponse avec URLs citées",
            estimated_tokens=2000,
            estimated_latency_ms=5000
        )

    def _plan_ocr(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """Plan pour OCR (extraction + indexation)"""
        doc_id = context.get("doc_id") if context else None

        steps = [
            PlanStep(
                step_number=0,
                tool="ocr.extract",
                input={"doc_id": doc_id},
                dependency=StepDependency.NONE,
                description="Extraire texte et champs (OCR)"
            ),
            PlanStep(
                step_number=1,
                tool="ocr.validate",
                input={"fields": "{{step0.fields}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[0],
                description="Valider formats et cohérence"
            ),
            PlanStep(
                step_number=2,
                tool="ocr.index",
                input={"doc_id": doc_id, "fields": "{{step1.validated_fields}}"},
                dependency=StepDependency.SEQUENTIAL,
                depends_on=[1],
                description="Indexer dans Qdrant + écrire en BDD"
            )
        ]

        return ExecutionPlan(
            goal=f"OCR document: {doc_id}",
            intent="OCR",
            steps=steps,
            success_criteria="Document extrait, validé et indexé",
            estimated_tokens=1200,
            estimated_latency_ms=4000
        )

    def _plan_generic(self, intent: str, query: str) -> ExecutionPlan:
        """Plan générique pour intents inconnus"""
        steps = [
            PlanStep(
                step_number=0,
                tool="intent.classify",
                input={"query": query},
                dependency=StepDependency.NONE,
                description="Re-classifier l'intent"
            )
        ]

        return ExecutionPlan(
            goal=f"Traiter query générique: {query[:100]}",
            intent=intent,
            steps=steps,
            success_criteria="Intent re-classifié et traité",
            estimated_tokens=500,
            estimated_latency_ms=1000
        )

    def visualize_plan(self, plan: ExecutionPlan) -> str:
        """
        Génère une visualisation textuelle du plan (pour logs/debug).

        Returns:
            str: Représentation ASCII du plan
        """
        lines = [
            f"=== Plan d'exécution: {plan.goal} ===",
            f"Intent: {plan.intent}",
            f"Tokens estimés: {plan.estimated_tokens}",
            f"Latence estimée: {plan.estimated_latency_ms}ms",
            f"Critère de succès: {plan.success_criteria}",
            "",
            "Steps:"
        ]

        for step in plan.steps:
            dep_str = ""
            if step.depends_on:
                dep_str = f" (depends: {step.depends_on})"
            condition_str = f" IF {step.condition}" if step.condition else ""

            lines.append(
                f"  [{step.step_number}] {step.tool}{dep_str}{condition_str}"
            )
            lines.append(f"      → {step.description}")

        return "\n".join(lines)
