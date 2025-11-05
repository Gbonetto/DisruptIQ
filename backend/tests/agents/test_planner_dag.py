"""
Tests for PlannerDAG
"""

import pytest
from app.services.agents.planner_dag import (
    PlannerDAG, ExecutionPlan, PlanStep, StepDependency
)


class TestPlannerDAG:
    """Test suite for PlannerDAG"""

    @pytest.fixture
    def planner(self):
        """Create PlannerDAG instance"""
        return PlannerDAG()

    @pytest.mark.asyncio
    async def test_plan_sql_only(self, planner):
        """Test SQL_ONLY plan generation"""
        plan = await planner.generate_plan(
            intent="SQL_ONLY",
            query="Combien de copropriétaires actifs?"
        )

        assert plan.intent == "SQL_ONLY"
        assert len(plan.steps) >= 2  # At least plan + execute
        assert plan.steps[0].tool == "sql.plan"
        assert plan.steps[1].tool == "sql.execute"
        assert plan.steps[1].depends_on == [0]
        assert plan.estimated_tokens > 0
        assert plan.estimated_latency_ms > 0

    @pytest.mark.asyncio
    async def test_plan_rag_only(self, planner):
        """Test RAG_ONLY plan generation"""
        plan = await planner.generate_plan(
            intent="RAG_ONLY",
            query="Quelle est la procédure dégât des eaux?"
        )

        assert plan.intent == "RAG_ONLY"
        assert len(plan.steps) >= 3  # search + rerank + summarize
        assert plan.steps[0].tool == "rag.search"
        assert plan.steps[2].tool == "rag.summarize"

        # Vérifier qu'il y a un step evaluator
        evaluator_steps = [s for s in plan.steps if s.tool == "evaluator.check"]
        assert len(evaluator_steps) > 0

    @pytest.mark.asyncio
    async def test_plan_hybrid(self, planner):
        """Test HYBRID plan generation"""
        plan = await planner.generate_plan(
            intent="HYBRID",
            query="Qui est le plombier et quelle est sa procédure?"
        )

        assert plan.intent == "HYBRID"
        assert len(plan.steps) >= 5  # SQL + RAG + fusion + evaluator

        # Vérifier étapes parallèles (step 0 et 1)
        assert plan.steps[0].dependency == StepDependency.NONE
        assert plan.steps[1].dependency == StepDependency.NONE

        # Vérifier fusion step
        fusion_steps = [s for s in plan.steps if s.tool == "fusion.merge"]
        assert len(fusion_steps) == 1
        fusion_step = fusion_steps[0]
        assert len(fusion_step.depends_on) >= 2  # Depends on SQL + RAG

    @pytest.mark.asyncio
    async def test_plan_email(self, planner):
        """Test EMAIL plan generation"""
        plan = await planner.generate_plan(
            intent="EMAIL",
            query="Envoyer email aux copropriétaires pour AG"
        )

        assert plan.intent == "EMAIL"

        # Vérifier présence des steps essentiels
        tools = [s.tool for s in plan.steps]
        assert "email.generate" in tools
        assert "email.preview" in tools
        assert "evaluator.check" in tools

        # Vérifier que preview est bien APRÈS generate
        generate_idx = tools.index("email.generate")
        preview_idx = tools.index("email.preview")
        assert preview_idx > generate_idx

    @pytest.mark.asyncio
    async def test_plan_n8n(self, planner):
        """Test N8N plan generation"""
        plan = await planner.generate_plan(
            intent="N8N",
            query="Déclencher workflow notification voisins"
        )

        assert plan.intent == "N8N"

        tools = [s.tool for s in plan.steps]
        assert "n8n.preview" in tools
        assert "n8n.trigger" in tools

        # Vérifier que trigger est conditionnel
        trigger_steps = [s for s in plan.steps if s.tool == "n8n.trigger"]
        assert len(trigger_steps) == 1
        assert trigger_steps[0].dependency == StepDependency.CONDITIONAL
        assert trigger_steps[0].condition is not None

    @pytest.mark.asyncio
    async def test_plan_web(self, planner):
        """Test WEB plan generation"""
        plan = await planner.generate_plan(
            intent="WEB",
            query="Rechercher jurisprudence copropriété"
        )

        assert plan.intent == "WEB"

        tools = [s.tool for s in plan.steps]
        assert "web.search" in tools
        assert "web.extract" in tools
        assert "rag.summarize" in tools

    @pytest.mark.asyncio
    async def test_plan_ocr(self, planner):
        """Test OCR plan generation"""
        plan = await planner.generate_plan(
            intent="OCR",
            query="Extraire facture",
            context={"doc_id": "doc_123"}
        )

        assert plan.intent == "OCR"

        tools = [s.tool for s in plan.steps]
        assert "ocr.extract" in tools
        assert "ocr.validate" in tools
        assert "ocr.index" in tools

    @pytest.mark.asyncio
    async def test_plan_with_entities(self, planner):
        """Test plan generation with entities"""
        entities = {
            "persons": ["Marie Dupont"],
            "categories": ["plombier"],
            "locations": ["Cannes"]
        }

        plan = await planner.generate_plan(
            intent="SQL_ONLY",
            query="Contact du plombier à Cannes",
            entities=entities
        )

        # Vérifier que entities sont passées au premier step
        assert plan.steps[0].input.get("entities") == entities

    def test_visualize_plan(self, planner):
        """Test plan visualization"""
        plan = ExecutionPlan(
            goal="Test goal",
            intent="SQL_ONLY",
            steps=[
                PlanStep(
                    step_number=0,
                    tool="sql.plan",
                    input={"query": "test"},
                    description="Plan SQL"
                ),
                PlanStep(
                    step_number=1,
                    tool="sql.execute",
                    input={"sql": "SELECT *"},
                    dependency=StepDependency.SEQUENTIAL,
                    depends_on=[0],
                    description="Execute SQL"
                )
            ],
            success_criteria="SQL executed",
            estimated_tokens=500,
            estimated_latency_ms=1500
        )

        visualization = planner.visualize_plan(plan)

        assert "Test goal" in visualization
        assert "SQL_ONLY" in visualization
        assert "sql.plan" in visualization
        assert "sql.execute" in visualization
        assert "depends: [0]" in visualization
        assert "500" in visualization  # tokens
        assert "1500ms" in visualization  # latency

    @pytest.mark.asyncio
    async def test_estimated_metrics(self, planner):
        """Test that all plans have estimated metrics"""
        intents = ["SQL_ONLY", "RAG_ONLY", "HYBRID", "EMAIL", "N8N", "WEB", "OCR"]

        for intent in intents:
            context = {"doc_id": "test"} if intent == "OCR" else None
            plan = await planner.generate_plan(
                intent=intent,
                query="test query",
                context=context
            )

            assert plan.estimated_tokens is not None
            assert plan.estimated_tokens > 0
            assert plan.estimated_latency_ms is not None
            assert plan.estimated_latency_ms > 0

    @pytest.mark.asyncio
    async def test_step_dependencies_valid(self, planner):
        """Test that step dependencies are valid"""
        plan = await planner.generate_plan(
            intent="HYBRID",
            query="test query"
        )

        for step in plan.steps:
            if step.depends_on:
                # Vérifier que tous les depends_on pointent vers des steps antérieurs
                for dep_step_num in step.depends_on:
                    assert dep_step_num < step.step_number

    @pytest.mark.asyncio
    async def test_evaluator_steps_present(self, planner):
        """Test that all plans have evaluator steps"""
        intents_requiring_eval = ["SQL_ONLY", "RAG_ONLY", "HYBRID", "EMAIL", "N8N", "WEB"]

        for intent in intents_requiring_eval:
            plan = await planner.generate_plan(
                intent=intent,
                query="test query"
            )

            # Vérifier présence d'au moins un step evaluator
            evaluator_steps = [s for s in plan.steps if "evaluator" in s.tool]
            assert len(evaluator_steps) > 0, f"No evaluator step for intent {intent}"
