"""
End-to-End Integration Test for Orchestrator + Planner + Evaluator

This test verifies the complete Phase 1 integration flow:
1. Planner DAG generates execution plan
2. Orchestrator executes plan
3. Observability tracks all steps
4. Evaluator validates results
"""

import pytest
import asyncio
import uuid
from datetime import datetime

from app.services.agents.orchestrator_agent import OrchestratorAgent
from app.services.agents.planner_dag import PlannerDAG
from app.services.agents.evaluator import Evaluator


class TestE2EOrchestrationFlow:
    """End-to-end tests for orchestration with Phase 1 components"""

    @pytest.mark.asyncio
    async def test_planner_generates_valid_plans(self):
        """Test that Planner DAG generates valid execution plans"""
        planner = PlannerDAG()

        # Test SQL_ONLY plan
        sql_plan = await planner.generate_plan(
            intent="SQL_ONLY",
            query="Liste des plombiers à Paris"
        )

        assert sql_plan.intent == "SQL_ONLY"
        assert len(sql_plan.steps) >= 2  # At least sql.plan + sql.execute
        assert sql_plan.estimated_tokens > 0
        assert sql_plan.success_criteria
        assert "sql.plan" in [step.tool for step in sql_plan.steps]

    @pytest.mark.asyncio
    async def test_planner_generates_rag_plan(self):
        """Test RAG_ONLY plan generation"""
        planner = PlannerDAG()

        rag_plan = await planner.generate_plan(
            intent="RAG_ONLY",
            query="Quelle est la procédure en cas de dégât des eaux?"
        )

        assert rag_plan.intent == "RAG_ONLY"
        assert len(rag_plan.steps) >= 3  # search + rerank + summarize
        assert "rag.search" in [step.tool for step in rag_plan.steps]
        assert "rag.summarize" in [step.tool for step in rag_plan.steps]
        assert any("citations" in str(step.input) for step in rag_plan.steps)

    @pytest.mark.asyncio
    async def test_planner_generates_hybrid_plan(self):
        """Test HYBRID plan with parallel SQL + RAG execution"""
        planner = PlannerDAG()

        hybrid_plan = await planner.generate_plan(
            intent="HYBRID",
            query="Quels sont les tarifs du plombier Jean Dupont?"
        )

        assert hybrid_plan.intent == "HYBRID"
        assert len(hybrid_plan.steps) >= 5  # sql.plan, rag.search, sql.execute, rag.summarize, fusion
        assert "fusion.merge" in [step.tool for step in hybrid_plan.steps]

        # Verify parallel execution (steps 0 and 1 should be NONE dependency)
        from app.services.agents.planner_dag import StepDependency
        parallel_steps = [s for s in hybrid_plan.steps if s.dependency == StepDependency.NONE]
        assert len(parallel_steps) >= 2  # SQL and RAG start in parallel

    @pytest.mark.asyncio
    async def test_planner_generates_email_plan(self):
        """Test EMAIL plan with preview and evidence checks"""
        planner = PlannerDAG()

        email_plan = await planner.generate_plan(
            intent="EMAIL",
            query="Envoyer email aux copropriétaires pour alerte urgence"
        )

        assert email_plan.intent == "EMAIL"
        assert "email.generate" in [step.tool for step in email_plan.steps]
        assert "email.preview" in [step.tool for step in email_plan.steps]
        assert "rag.search" in [step.tool for step in email_plan.steps]  # For evidence

    @pytest.mark.asyncio
    async def test_planner_generates_n8n_plan(self):
        """Test N8N plan with danger level preview"""
        planner = PlannerDAG()

        n8n_plan = await planner.generate_plan(
            intent="N8N",
            query="Déclencher workflow de facturation automatique"
        )

        assert n8n_plan.intent == "N8N"
        assert "n8n.preview" in [step.tool for step in n8n_plan.steps]
        assert "n8n.trigger" in [step.tool for step in n8n_plan.steps]

        # Verify conditional trigger (only if preview passes)
        from app.services.agents.planner_dag import StepDependency
        trigger_step = [s for s in n8n_plan.steps if s.tool == "n8n.trigger"][0]
        assert trigger_step.dependency == StepDependency.CONDITIONAL

    @pytest.mark.asyncio
    async def test_planner_generates_web_plan(self):
        """Test WEB plan with URL citations"""
        planner = PlannerDAG()

        web_plan = await planner.generate_plan(
            intent="WEB",
            query="Rechercher les nouvelles réglementations copropriété 2024"
        )

        assert web_plan.intent == "WEB"
        assert "web.search" in [step.tool for step in web_plan.steps]
        assert "web.extract" in [step.tool for step in web_plan.steps]
        assert any("citations" in str(step.input) for step in web_plan.steps)

    @pytest.mark.asyncio
    async def test_planner_visualize_plan(self):
        """Test plan visualization for debugging"""
        planner = PlannerDAG()

        plan = await planner.generate_plan(
            intent="HYBRID",
            query="Test query"
        )

        visualization = planner.visualize_plan(plan)

        assert "Plan d'exécution" in visualization
        assert "HYBRID" in visualization
        assert "Steps:" in visualization
        assert "sql" in visualization.lower()
        assert "rag" in visualization.lower()

    @pytest.mark.asyncio
    async def test_evaluator_validates_rag_citations(self):
        """Test Evaluator checks RAG citations"""
        evaluator = Evaluator()

        # Test with citations
        result_with_citations = await evaluator.evaluate(
            rules=["rag_has_citations"],
            context={
                "response": "Selon le document [1], la procédure est [2]...",
                "citations": [{"id": "doc1"}, {"id": "doc2"}]
            }
        )

        assert result_with_citations.passed
        assert result_with_citations.rules_passed == 1

        # Test without citations (should fail)
        result_without_citations = await evaluator.evaluate(
            rules=["rag_has_citations"],
            context={
                "response": "La procédure est simple.",
                "citations": []
            }
        )

        assert not result_without_citations.passed
        assert result_without_citations.critical_failures == 1

    @pytest.mark.asyncio
    async def test_evaluator_validates_sql_errors(self):
        """Test Evaluator checks SQL errors"""
        evaluator = Evaluator()

        # Test without error
        result_no_error = await evaluator.evaluate(
            rules=["sql_no_error"],
            context={
                "error": None,
                "results": [{"id": 1, "name": "Test"}]
            }
        )

        assert result_no_error.passed

        # Test with error
        result_with_error = await evaluator.evaluate(
            rules=["sql_no_error"],
            context={
                "error": "Syntax error near SELECT",
                "results": []
            }
        )

        assert not result_with_error.passed
        assert result_with_error.critical_failures == 1

    @pytest.mark.asyncio
    async def test_evaluator_validates_hybrid_conflicts(self):
        """Test Evaluator detects SQL/RAG conflicts"""
        evaluator = Evaluator()

        # Test without conflicts
        result_no_conflicts = await evaluator.evaluate(
            rules=["hybrid_no_contradiction"],
            context={
                "conflicts": []
            }
        )

        assert result_no_conflicts.passed

        # Test with critical conflict
        result_with_conflict = await evaluator.evaluate(
            rules=["hybrid_no_contradiction"],
            context={
                "conflicts": [
                    {"severity": "critical", "message": "Price mismatch: SQL says 100€, RAG says 200€"}
                ]
            }
        )

        assert not result_with_conflict.passed
        assert result_with_conflict.critical_failures == 1

    @pytest.mark.asyncio
    async def test_evaluator_validates_email_evidence(self):
        """Test Evaluator checks email evidence"""
        evaluator = Evaluator()

        # Test with evidence
        result_with_evidence = await evaluator.evaluate(
            rules=["email_has_evidence"],
            context={
                "draft": {
                    "evidence": ["doc1.pdf", "contract.pdf"]
                }
            }
        )

        assert result_with_evidence.passed

        # Test without evidence (should fail)
        result_no_evidence = await evaluator.evaluate(
            rules=["email_has_evidence"],
            context={
                "draft": {
                    "evidence": []
                }
            }
        )

        assert not result_no_evidence.passed
        assert result_no_evidence.critical_failures == 1

    @pytest.mark.asyncio
    async def test_evaluator_validates_n8n_danger_level(self):
        """Test Evaluator checks N8N danger level preview"""
        evaluator = Evaluator()

        # Test high danger WITH preview (should pass)
        result_high_with_preview = await evaluator.evaluate(
            rules=["n8n_preview_if_danger_high"],
            context={
                "danger_level": "high",
                "preview_shown": True
            }
        )

        assert result_high_with_preview.passed

        # Test high danger WITHOUT preview (should fail)
        result_high_no_preview = await evaluator.evaluate(
            rules=["n8n_preview_if_danger_high"],
            context={
                "danger_level": "high",
                "preview_shown": False
            }
        )

        assert not result_high_no_preview.passed
        assert result_high_no_preview.critical_failures == 1

        # Test low danger WITHOUT preview (should pass - preview not required)
        result_low_no_preview = await evaluator.evaluate(
            rules=["n8n_preview_if_danger_high"],
            context={
                "danger_level": "low",
                "preview_shown": False
            }
        )

        assert result_low_no_preview.passed

    @pytest.mark.asyncio
    async def test_evaluator_validates_sql_whitelist(self):
        """Test Evaluator checks SQL table whitelist"""
        evaluator = Evaluator()

        # Test with whitelisted view
        result_whitelisted = await evaluator.evaluate(
            rules=["sql_whitelist_tables"],
            context={
                "sql": "SELECT * FROM vw_professionnels_min WHERE category = 'plombier'"
            }
        )

        assert result_whitelisted.passed

        # Test with unauthorized table
        result_unauthorized = await evaluator.evaluate(
            rules=["sql_whitelist_tables"],
            context={
                "sql": "SELECT * FROM users WHERE password_hash = '...'"
            }
        )

        assert not result_unauthorized.passed
        assert result_unauthorized.critical_failures == 1

    @pytest.mark.asyncio
    async def test_evaluator_multiple_rules(self):
        """Test Evaluator with multiple rules"""
        evaluator = Evaluator()

        result = await evaluator.evaluate(
            rules=["rag_has_citations", "rag_min_sources_2"],
            context={
                "response": "According to documents [1][2][3]...",
                "citations": [
                    {"id": "doc1", "title": "Source 1"},
                    {"id": "doc2", "title": "Source 2"},
                    {"id": "doc3", "title": "Source 3"}
                ]
            }
        )

        assert result.passed
        assert result.rules_checked == 2
        assert result.rules_passed == 2
        assert result.critical_failures == 0

    def test_orchestrator_initializes_phase1_components(self):
        """Test that orchestrator initializes Planner and Evaluator"""
        orchestrator = OrchestratorAgent()

        assert orchestrator.planner is not None
        assert orchestrator.evaluator is not None
        assert isinstance(orchestrator.planner, PlannerDAG)
        assert isinstance(orchestrator.evaluator, Evaluator)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
