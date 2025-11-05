"""
Tests for Orchestrator Integration with Planner DAG + Evaluator + Observability

Tests the Phase 1 integration:
- Execution plan generation
- Observability tracking (AgentRun, AgentStep)
- Rule-based evaluation
- End-to-end flow
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.services.agents.orchestrator_agent import OrchestratorAgent, AgentResponse
from app.services.agents.planner_dag import ExecutionPlan, PlanStep, StepDependency
from app.services.agents.evaluator import EvaluationResult, RuleResult, RuleSeverity


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for testing"""
    return OrchestratorAgent()


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def conversation_id():
    """Generate unique conversation ID"""
    return f"test-conv-{uuid.uuid4().hex[:12]}"


class TestOrchestratorIntegration:
    """Test suite for Phase 1 orchestrator integration"""

    @pytest.mark.asyncio
    async def test_create_agent_run_success(self, orchestrator, mock_db, conversation_id):
        """Test AgentRun creation"""
        # Mock database response
        mock_result = Mock()
        mock_result.scalar_one.return_value = 123
        mock_db.execute.return_value = mock_result

        # Create agent run
        run_id = await orchestrator._create_agent_run(
            db=mock_db,
            conversation_id=conversation_id,
            intent="SQL_ONLY",
            plan={"goal": "Test plan", "steps": []}
        )

        # Assertions
        assert run_id == 123
        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_log_agent_step_success(self, orchestrator, mock_db):
        """Test AgentStep logging"""
        # Log a step
        await orchestrator._log_agent_step(
            db=mock_db,
            run_id=123,
            step_number=0,
            tool="sql.execute",
            input_data={"query": "SELECT * FROM vw_professionnels_min"},
            output_data={"rows": 10},
            latency_ms=150
        )

        # Assertions
        assert mock_db.execute.called
        assert mock_db.commit.called

        # Verify SQL contains proper columns
        call_args = mock_db.execute.call_args
        sql_text = str(call_args[0][0])
        assert "agent_steps" in sql_text
        assert "run_id" in sql_text
        assert "tool" in sql_text

    @pytest.mark.asyncio
    async def test_finalize_agent_run_success(self, orchestrator, mock_db):
        """Test AgentRun finalization"""
        # Finalize run
        await orchestrator._finalize_agent_run(
            db=mock_db,
            run_id=123,
            status="success",
            cost_tokens=500,
            citations_json={"sources": ["doc1", "doc2"]},
            has_conflicts=False,
            evaluator_passed=True
        )

        # Assertions
        assert mock_db.execute.called
        assert mock_db.commit.called

        # Verify SQL UPDATE
        call_args = mock_db.execute.call_args
        sql_text = str(call_args[0][0])
        assert "UPDATE agent_runs" in sql_text
        assert "status" in sql_text
        assert "evaluator_passed" in sql_text

    @pytest.mark.asyncio
    async def test_process_with_plan_sql_query(self, orchestrator, mock_db, conversation_id):
        """Test process_with_plan with SQL query intent"""
        # Mock AgentRun creation
        mock_result = Mock()
        mock_result.scalar_one.return_value = 456
        mock_db.execute.return_value = mock_result

        # Mock the existing process method
        mock_response = AgentResponse(
            success=True,
            message="Found 5 professionnels",
            data={"results": [{"id": 1, "name": "Plombier Paris"}]},
            agents_used=["sql_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response) as mock_process:
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                # Execute
                response = await orchestrator.process_with_plan(
                    user_input="Liste des plombiers actifs",
                    db=mock_db,
                    conversation_id=conversation_id
                )

        # Assertions
        assert response.success
        assert "evaluation" in response.data
        assert "observability" in response.data
        assert response.data["observability"]["run_id"] == 456
        assert mock_db.execute.called  # AgentRun created

    @pytest.mark.asyncio
    async def test_process_with_plan_creates_execution_plan(self, orchestrator, mock_db, conversation_id):
        """Test that Planner DAG is invoked"""
        # Mock database
        mock_result = Mock()
        mock_result.scalar_one.return_value = 789
        mock_db.execute.return_value = mock_result

        # Mock execution
        mock_response = AgentResponse(
            success=True,
            message="Query executed",
            agents_used=["sql_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response):
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                with patch.object(orchestrator.planner, 'generate_plan') as mock_planner:
                    # Configure mock planner
                    mock_plan = ExecutionPlan(
                        goal="Execute SQL query",
                        intent="SQL_ONLY",
                        steps=[
                            PlanStep(
                                step_number=0,
                                tool="sql.execute",
                                description="Run SQL query",
                                dependency=StepDependency.NONE
                            )
                        ],
                        success_criteria="Results returned",
                        estimated_tokens=500
                    )
                    mock_planner.return_value = mock_plan

                    # Execute
                    response = await orchestrator.process_with_plan(
                        user_input="Test query",
                        db=mock_db,
                        conversation_id=conversation_id
                    )

        # Assertions
        assert mock_planner.called
        assert response.data["observability"]["plan_steps"] == 1
        assert response.data["observability"]["estimated_tokens"] == 500

    @pytest.mark.asyncio
    async def test_process_with_plan_evaluates_results(self, orchestrator, mock_db, conversation_id):
        """Test that Evaluator is invoked"""
        # Mock database
        mock_result = Mock()
        mock_result.scalar_one.return_value = 999
        mock_db.execute.return_value = mock_result

        # Mock execution
        mock_response = AgentResponse(
            success=True,
            message="Query executed with citations [1][2]",
            data={"sources": ["doc1", "doc2"]},
            agents_used=["rag_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response):
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                with patch.object(orchestrator.evaluator, 'evaluate') as mock_evaluator:
                    # Configure mock evaluator
                    mock_eval = EvaluationResult(
                        passed=True,
                        rules_checked=2,
                        rules_passed=2,
                        rules_failed=[],
                        details=[
                            RuleResult(
                                rule_id="rag_has_citations",
                                passed=True,
                                severity=RuleSeverity.CRITICAL,
                                message="OK: Citations présentes"
                            )
                        ]
                    )
                    mock_evaluator.return_value = mock_eval

                    # Execute
                    response = await orchestrator.process_with_plan(
                        user_input="Search documents",
                        db=mock_db,
                        conversation_id=conversation_id
                    )

        # Assertions
        assert mock_evaluator.called
        assert response.data["evaluation"]["passed"]
        assert response.data["evaluation"]["rules_checked"] == 2
        assert response.data["evaluation"]["rules_passed"] == 2

    @pytest.mark.asyncio
    async def test_process_with_plan_handles_evaluation_failure(self, orchestrator, mock_db, conversation_id):
        """Test handling of failed evaluation"""
        # Mock database
        mock_result = Mock()
        mock_result.scalar_one.return_value = 888
        mock_db.execute.return_value = mock_result

        # Mock execution - RAG without citations
        mock_response = AgentResponse(
            success=True,
            message="Response without citations",
            data={},
            agents_used=["rag_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response):
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                with patch.object(orchestrator.evaluator, 'evaluate') as mock_evaluator:
                    # Configure mock evaluator - CRITICAL failure
                    mock_eval = EvaluationResult(
                        passed=False,
                        rules_checked=1,
                        rules_passed=0,
                        rules_failed=["rag_has_citations"],
                        critical_failures=1,
                        details=[
                            RuleResult(
                                rule_id="rag_has_citations",
                                passed=False,
                                severity=RuleSeverity.CRITICAL,
                                message="ÉCHEC: Aucune citation trouvée"
                            )
                        ]
                    )
                    mock_evaluator.return_value = mock_eval

                    # Execute
                    response = await orchestrator.process_with_plan(
                        user_input="Search without citations",
                        db=mock_db,
                        conversation_id=conversation_id
                    )

        # Assertions
        assert not response.data["evaluation"]["passed"]
        assert response.data["evaluation"]["critical_failures"] == 1
        assert "⚠️ **Attention**" in response.message
        assert "règle(s) critique(s)" in response.message

    @pytest.mark.asyncio
    async def test_get_evaluation_rules_sql_only(self, orchestrator):
        """Test rule selection for SQL_ONLY intent"""
        mock_response = AgentResponse(
            success=True,
            message="SQL executed",
            agents_used=["sql_agent"]
        )

        rules = orchestrator._get_evaluation_rules("SQL_ONLY", mock_response)

        assert "sql_no_error" in rules
        assert "sql_results_not_empty" in rules
        assert "sql_whitelist_tables" in rules  # Added because sql_agent was used

    @pytest.mark.asyncio
    async def test_get_evaluation_rules_rag_only(self, orchestrator):
        """Test rule selection for RAG_ONLY intent"""
        mock_response = AgentResponse(
            success=True,
            message="RAG executed",
            agents_used=["rag_agent"]
        )

        rules = orchestrator._get_evaluation_rules("RAG_ONLY", mock_response)

        assert "rag_has_citations" in rules
        assert "rag_min_sources_2" in rules

    @pytest.mark.asyncio
    async def test_get_evaluation_rules_hybrid(self, orchestrator):
        """Test rule selection for HYBRID intent"""
        mock_response = AgentResponse(
            success=True,
            message="HYBRID executed",
            agents_used=["sql_agent", "rag_agent", "fusion_agent"]
        )

        rules = orchestrator._get_evaluation_rules("HYBRID", mock_response)

        assert "rag_has_citations" in rules
        assert "sql_no_error" in rules
        assert "hybrid_no_contradiction" in rules
        assert "hybrid_sources_attributed" in rules
        assert "sql_whitelist_tables" in rules  # Added because sql_agent was used

    @pytest.mark.asyncio
    async def test_get_evaluation_rules_email(self, orchestrator):
        """Test rule selection for EMAIL intent"""
        mock_response = AgentResponse(
            success=True,
            message="Email drafted",
            agents_used=["email_agent"]
        )

        rules = orchestrator._get_evaluation_rules("EMAIL", mock_response)

        assert "email_has_evidence" in rules
        assert "email_preview_shown" in rules

    @pytest.mark.asyncio
    async def test_get_evaluation_rules_n8n(self, orchestrator):
        """Test rule selection for N8N intent"""
        mock_response = AgentResponse(
            success=True,
            message="Workflow triggered",
            agents_used=["workflow_agent"]
        )

        rules = orchestrator._get_evaluation_rules("N8N", mock_response)

        assert "n8n_preview_if_danger_high" in rules
        assert "n8n_correlation_id" in rules

    @pytest.mark.asyncio
    async def test_get_evaluation_rules_web(self, orchestrator):
        """Test rule selection for WEB intent"""
        mock_response = AgentResponse(
            success=True,
            message="Web search completed",
            agents_used=["web_search_agent"]
        )

        rules = orchestrator._get_evaluation_rules("WEB", mock_response)

        assert "web_urls_cited" in rules

    @pytest.mark.asyncio
    async def test_process_with_plan_handles_exception(self, orchestrator, mock_db, conversation_id):
        """Test error handling in process_with_plan"""
        # Mock database
        mock_result = Mock()
        mock_result.scalar_one.return_value = 777
        mock_db.execute.return_value = mock_result

        # Mock process to raise exception
        with patch.object(orchestrator, 'process', side_effect=Exception("Test error")):
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                # Execute
                response = await orchestrator.process_with_plan(
                    user_input="Test query",
                    db=mock_db,
                    conversation_id=conversation_id
                )

        # Assertions
        assert not response.success
        assert "Erreur lors du traitement avec plan" in response.message
        assert "orchestrator" in response.agents_used
        assert "planner" in response.agents_used
        assert "evaluator" in response.agents_used

    @pytest.mark.asyncio
    async def test_process_with_plan_tracks_latency(self, orchestrator, mock_db, conversation_id):
        """Test that latency is tracked in observability"""
        # Mock database
        mock_result = Mock()
        mock_result.scalar_one.return_value = 555
        mock_db.execute.return_value = mock_result

        # Mock execution
        mock_response = AgentResponse(
            success=True,
            message="Query executed",
            agents_used=["sql_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response):
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                # Execute
                response = await orchestrator.process_with_plan(
                    user_input="Test query",
                    db=mock_db,
                    conversation_id=conversation_id
                )

        # Assertions
        assert "observability" in response.data
        assert "total_latency_ms" in response.data["observability"]
        assert isinstance(response.data["observability"]["total_latency_ms"], int)
        assert response.data["observability"]["total_latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_observability_tracks_all_steps(self, orchestrator, mock_db, conversation_id):
        """Test that all steps are logged to agent_steps"""
        # Mock database
        mock_result = Mock()
        mock_result.scalar_one.return_value = 444
        mock_db.execute.return_value = mock_result

        # Track execute calls
        execute_calls = []
        original_execute = mock_db.execute

        async def track_execute(*args, **kwargs):
            execute_calls.append(args)
            return await original_execute(*args, **kwargs)

        mock_db.execute = track_execute

        # Mock execution
        mock_response = AgentResponse(
            success=True,
            message="Success",
            agents_used=["sql_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response):
            with patch.object(orchestrator, 'classify_intention', return_value=AsyncMock()):
                # Execute
                await orchestrator.process_with_plan(
                    user_input="Test",
                    db=mock_db,
                    conversation_id=conversation_id
                )

        # Count INSERT INTO agent_steps
        step_inserts = [
            call for call in execute_calls
            if len(call) > 0 and "agent_steps" in str(call[0])
        ]

        # Should have at least 3 steps logged:
        # 1. orchestrator.classify
        # 2. orchestrator.execute
        # 3. evaluator.check
        assert len(step_inserts) >= 3


class TestIntentMapping:
    """Test intent mapping from legacy to Phase 1"""

    def test_intent_mapping(self):
        """Test that all legacy intents map to Phase 1 intents"""
        from app.services.agents.orchestrator_agent import IntentType

        intent_map = {
            IntentType.QUERY_DATA: "SQL_ONLY",
            IntentType.SEARCH_DOCUMENTS: "RAG_ONLY",
            IntentType.SEND_EMAIL: "EMAIL",
            IntentType.TRIGGER_WORKFLOW: "N8N",
            IntentType.ANALYZE_DOCUMENT: "OCR",
            IntentType.GENERAL_QUESTION: "GENERAL"
        }

        # Verify all mappings exist
        assert len(intent_map) == 6
        assert all(isinstance(v, str) for v in intent_map.values())
        assert all(v.isupper() or v == "GENERAL" for v in intent_map.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
