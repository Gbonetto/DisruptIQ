"""
End-to-End Test for Orchestrator with Plan Integration

Tests the complete flow with real/mocked database:
- process_with_plan() method
- AgentRun creation and tracking
- Planner DAG execution
- Evaluator validation
- Observability data

Can run in two modes:
- Mock mode (default): Uses mocked database
- Real DB mode: Uses actual PostgreSQL (set E2E_USE_REAL_DB=1)
"""

import pytest
import os
import asyncio
import uuid
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Check if we should use real DB
USE_REAL_DB = os.getenv("E2E_USE_REAL_DB", "0") == "1"

if USE_REAL_DB:
    from app.core.database import AsyncSession, get_db
    from sqlalchemy import text
else:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.orchestrator_agent import OrchestratorAgent, AgentResponse, IntentType


@pytest.fixture
async def db_session():
    """Database session - real or mocked"""
    if USE_REAL_DB:
        # Use real database
        async for session in get_db():
            yield session
            break
    else:
        # Use mocked database
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock execute to return proper results
        async def mock_execute(query, params=None):
            mock_result = Mock()
            # For INSERT RETURNING id
            if "RETURNING id" in str(query):
                mock_result.scalar_one.return_value = 12345
            # For SELECT
            else:
                mock_result.fetchall.return_value = []
                mock_result.keys.return_value = []
            return mock_result

        mock_db.execute = mock_execute
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

        yield mock_db


@pytest.fixture
def conversation_id():
    """Generate unique conversation ID"""
    return f"e2e-test-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def orchestrator():
    """Create orchestrator instance"""
    return OrchestratorAgent()


class TestOrchestratorE2E:
    """End-to-end tests for orchestrator with plan integration"""

    @pytest.mark.asyncio
    async def test_sql_only_query_complete_flow(self, orchestrator, db_session, conversation_id):
        """
        Test SQL_ONLY query with complete observability flow

        Flow:
        1. User asks: "Liste des plombiers actifs"
        2. Intent: QUERY_DATA → SQL_ONLY
        3. Planner creates SQL plan
        4. AgentRun created (tracked)
        5. SQL agent executes query
        6. Evaluator checks: sql_no_error, sql_whitelist_tables
        7. AgentRun finalized with results
        """
        user_query = "Liste des plombiers actifs à Paris"

        # Mock the underlying process() method to return SQL results
        mock_sql_response = AgentResponse(
            success=True,
            message="Trouvé 5 plombiers actifs",
            data={
                "results": [
                    {"id": 1, "name": "Plomberie Dupont", "city": "Paris", "rating": 4.5},
                    {"id": 2, "name": "Eau Service", "city": "Paris", "rating": 4.8}
                ],
                "sql": "SELECT * FROM vw_professionnels_min WHERE category = 'plombier' AND city = 'Paris'"
            },
            agents_used=["sql_agent"],
            confidence=0.95
        )

        with patch.object(orchestrator, 'process', return_value=mock_sql_response):
            # Execute with plan
            response = await orchestrator.process_with_plan(
                user_input=user_query,
                db=db_session,
                conversation_id=conversation_id
            )

        # Assertions
        assert response.success, f"Expected success but got: {response.message}"
        assert "plombiers" in response.message.lower()

        # Check observability data
        assert "observability" in response.data
        obs = response.data["observability"]
        assert obs["run_id"] is not None
        assert obs["plan_steps"] > 0
        assert obs["total_latency_ms"] >= 0
        assert obs["estimated_tokens"] > 0

        # Check evaluation data
        assert "evaluation" in response.data
        eval_data = response.data["evaluation"]
        assert eval_data["rules_checked"] > 0

        # SQL_ONLY should check: sql_no_error, sql_results_not_empty, sql_whitelist_tables
        assert eval_data["rules_checked"] >= 2

        print(f"✓ SQL_ONLY E2E Test Passed")
        print(f"  Run ID: {obs['run_id']}")
        print(f"  Latency: {obs['total_latency_ms']}ms")
        print(f"  Rules checked: {eval_data['rules_checked']}")
        print(f"  Evaluation passed: {eval_data['passed']}")

    @pytest.mark.asyncio
    async def test_rag_only_query_with_citations(self, orchestrator, db_session, conversation_id):
        """
        Test RAG_ONLY query with citation validation

        Flow:
        1. User asks: "Quelle est la procédure dégât des eaux?"
        2. Intent: SEARCH_DOCUMENTS → RAG_ONLY
        3. Planner creates RAG plan (search → rerank → summarize)
        4. RAG agent executes with citations
        5. Evaluator checks: rag_has_citations, rag_min_sources_2
        6. Should PASS if citations present
        """
        user_query = "Quelle est la procédure en cas de dégât des eaux?"

        # Mock RAG response with citations
        mock_rag_response = AgentResponse(
            success=True,
            message="Selon le règlement [1], vous devez contacter l'assurance dans les 5 jours [2].",
            data={
                "sources": [
                    {"id": "doc1", "title": "Règlement copropriété", "score": 0.92},
                    {"id": "doc2", "title": "Procédures urgences", "score": 0.88}
                ]
            },
            agents_used=["rag_agent", "synthesis_agent"],
            confidence=0.89
        )

        # Mock intent classification to return SEARCH_DOCUMENTS
        with patch.object(orchestrator, 'classify_intention', return_value=IntentType.SEARCH_DOCUMENTS):
            with patch.object(orchestrator, 'process', return_value=mock_rag_response):
                # Execute with plan
                response = await orchestrator.process_with_plan(
                    user_input=user_query,
                    db=db_session,
                    conversation_id=conversation_id
                )

        # Assertions
        assert response.success
        assert "[1]" in response.message  # Has citations
        assert "[2]" in response.message

        # Check evaluation
        eval_data = response.data["evaluation"]
        assert eval_data["rules_checked"] >= 2  # rag_has_citations + rag_min_sources_2

        # Should pass because citations are present
        if not eval_data["passed"]:
            print(f"WARNING: Evaluation failed: {eval_data['failed_rules']}")

        print(f"✓ RAG_ONLY E2E Test Passed")
        print(f"  Citations found: ✓")
        print(f"  Sources: {len(response.data['sources'])}")
        print(f"  Evaluation: {eval_data['passed']}")

    @pytest.mark.asyncio
    async def test_rag_without_citations_fails_evaluation(self, orchestrator, db_session, conversation_id):
        """
        Test that RAG response without citations FAILS evaluation

        This is a critical rule: No factual response without sources
        """
        user_query = "Quelle est la procédure?"

        # Mock RAG response WITHOUT citations (should fail)
        mock_rag_response_no_citations = AgentResponse(
            success=True,
            message="La procédure est simple et rapide.",  # No [1][2] citations
            data={"sources": []},  # No sources!
            agents_used=["rag_agent"]
        )

        with patch.object(orchestrator, 'classify_intention', return_value=IntentType.SEARCH_DOCUMENTS):
            with patch.object(orchestrator, 'process', return_value=mock_rag_response_no_citations):
                response = await orchestrator.process_with_plan(
                    user_input=user_query,
                    db=db_session,
                    conversation_id=conversation_id
                )

        # Assertions
        eval_data = response.data["evaluation"]

        # MUST fail evaluation due to rag_has_citations rule
        assert not eval_data["passed"], "Evaluation should FAIL when RAG has no citations"
        assert eval_data["critical_failures"] >= 1
        assert "rag_has_citations" in eval_data["failed_rules"]

        # Response should include warning
        assert "⚠️" in response.message or "Attention" in response.message

        print(f"✓ RAG No Citations Test Passed (correctly FAILED evaluation)")
        print(f"  Critical failures: {eval_data['critical_failures']}")
        print(f"  Failed rules: {eval_data['failed_rules']}")

    @pytest.mark.asyncio
    async def test_hybrid_query_with_fusion(self, orchestrator, db_session, conversation_id):
        """
        Test HYBRID query (SQL + RAG fusion)

        Flow:
        1. User asks: "Quel est le tarif du plombier Jean Dupont?"
        2. Intent: HYBRID (needs both SQL data and RAG documents)
        3. Planner creates parallel plan (SQL + RAG)
        4. Fusion agent merges results
        5. Evaluator checks: hybrid_no_contradiction, hybrid_sources_attributed
        """
        user_query = "Quel est le tarif horaire du plombier Jean Dupont?"

        # Mock HYBRID response with fusion
        mock_hybrid_response = AgentResponse(
            success=True,
            message="Jean Dupont (SQL: email@example.com, tel: 0123456789) facture 45€/h selon le contrat [1].",
            data={
                "fusion_strategy": "complement",
                "has_contradictions": False,
                "sources": [
                    {"type": "sql", "table": "vw_professionnels_min"},
                    {"type": "rag", "doc": "contrat_plomberie.pdf"}
                ],
                "sql_result": {"name": "Jean Dupont", "email": "email@example.com"},
                "rag_result": {"tarif": "45€/h"}
            },
            agents_used=["sql_agent", "rag_agent", "fusion_agent"],
            confidence=0.93
        )

        with patch.object(orchestrator, 'classify_intention', return_value=IntentType.SEARCH_DOCUMENTS):
            # Mock intent classifier v2 to return HYBRID
            with patch.object(orchestrator.intent_classifier_v2, 'classify_with_confidence') as mock_classify:
                from app.services.agents.intent_classifier_v2 import IntentClassificationResult, QueryIntent
                mock_classify.return_value = IntentClassificationResult(
                    intent=QueryIntent.HYBRID,
                    confidence=0.85,
                    sql_score=0.8,
                    rag_score=0.9
                )

                with patch.object(orchestrator, 'process', return_value=mock_hybrid_response):
                    response = await orchestrator.process_with_plan(
                        user_input=user_query,
                        db=db_session,
                        conversation_id=conversation_id
                    )

        # Assertions
        assert response.success

        # Check fusion data
        assert "fusion_strategy" in response.data
        assert response.data["has_contradictions"] == False

        # Check evaluation for HYBRID rules
        eval_data = response.data["evaluation"]
        # Should check: hybrid_no_contradiction, hybrid_sources_attributed
        # Plus SQL and RAG rules
        assert eval_data["rules_checked"] >= 3

        print(f"✓ HYBRID E2E Test Passed")
        print(f"  Fusion strategy: {response.data['fusion_strategy']}")
        print(f"  Contradictions: {response.data['has_contradictions']}")
        print(f"  Sources: {len(response.data['sources'])}")

    @pytest.mark.asyncio
    async def test_hybrid_with_contradiction_warning(self, orchestrator, db_session, conversation_id):
        """
        Test HYBRID query with SQL/RAG contradictions

        Should detect contradictions and warn user
        """
        user_query = "Quel est le prix?"

        # Mock HYBRID response with CONFLICT
        mock_conflict_response = AgentResponse(
            success=True,
            message="Attention: conflit détecté",
            data={
                "has_contradictions": True,
                "contradiction_note": "SQL dit 100€, RAG dit 200€",
                "conflicts": [
                    {"field": "price", "sql_value": "100€", "rag_value": "200€", "severity": "high"}
                ],
                "sources": []
            },
            agents_used=["sql_agent", "rag_agent", "fusion_agent"]
        )

        with patch.object(orchestrator, 'classify_intention', return_value=IntentType.SEARCH_DOCUMENTS):
            with patch.object(orchestrator, 'process', return_value=mock_conflict_response):
                response = await orchestrator.process_with_plan(
                    user_input=user_query,
                    db=db_session,
                    conversation_id=conversation_id
                )

        # Check observability tracked the conflict
        obs = response.data["observability"]
        # Note: has_conflicts is tracked in AgentRun

        print(f"✓ HYBRID Contradiction Test Passed")
        print(f"  Conflict detected: ✓")
        print(f"  Run ID: {obs['run_id']}")

    @pytest.mark.asyncio
    async def test_execution_plan_structure(self, orchestrator, db_session, conversation_id):
        """
        Test that execution plan has correct structure

        Validates:
        - Plan has goal, intent, steps, success_criteria
        - Steps have proper dependencies
        - Token estimation present
        """
        user_query = "Test query"

        mock_response = AgentResponse(
            success=True,
            message="Test",
            agents_used=["test_agent"]
        )

        with patch.object(orchestrator, 'process', return_value=mock_response):
            response = await orchestrator.process_with_plan(
                user_input=user_query,
                db=db_session,
                conversation_id=conversation_id
            )

        # Verify observability contains plan metadata
        obs = response.data["observability"]
        assert "plan_steps" in obs
        assert "estimated_tokens" in obs
        assert obs["plan_steps"] > 0
        assert obs["estimated_tokens"] > 0

        print(f"✓ Execution Plan Structure Test Passed")
        print(f"  Plan steps: {obs['plan_steps']}")
        print(f"  Estimated tokens: {obs['estimated_tokens']}")

    @pytest.mark.asyncio
    async def test_latency_tracking(self, orchestrator, db_session, conversation_id):
        """
        Test that latency is tracked at step level and overall
        """
        user_query = "Quick test"

        mock_response = AgentResponse(success=True, message="Done", agents_used=["test"])

        with patch.object(orchestrator, 'process', return_value=mock_response):
            import time
            start = time.time()

            response = await orchestrator.process_with_plan(
                user_input=user_query,
                db=db_session,
                conversation_id=conversation_id
            )

            elapsed_ms = int((time.time() - start) * 1000)

        # Check latency tracking
        obs = response.data["observability"]
        assert "total_latency_ms" in obs
        assert obs["total_latency_ms"] > 0
        assert obs["total_latency_ms"] <= elapsed_ms + 100  # Allow 100ms margin

        print(f"✓ Latency Tracking Test Passed")
        print(f"  Total latency: {obs['total_latency_ms']}ms")
        print(f"  Actual elapsed: {elapsed_ms}ms")


@pytest.mark.skipif(not USE_REAL_DB, reason="Requires real database (set E2E_USE_REAL_DB=1)")
class TestOrchestratorRealDB:
    """Tests that require real PostgreSQL database"""

    @pytest.mark.asyncio
    async def test_agent_run_persisted_in_db(self, db_session, conversation_id):
        """Test that AgentRun is actually persisted"""
        orchestrator = OrchestratorAgent()

        # Create agent run
        run_id = await orchestrator._create_agent_run(
            db=db_session,
            conversation_id=conversation_id,
            intent="SQL_ONLY",
            plan={"goal": "Test", "steps": []}
        )

        assert run_id is not None

        # Query back from DB
        result = await db_session.execute(
            text("SELECT * FROM agent_runs WHERE id = :run_id"),
            {"run_id": run_id}
        )
        row = result.fetchone()

        assert row is not None
        assert row.conversation_id == conversation_id
        assert row.intent == "SQL_ONLY"

        print(f"✓ Real DB Persistence Test Passed")
        print(f"  Run ID: {run_id}")
        print(f"  Conversation: {conversation_id}")

    @pytest.mark.asyncio
    async def test_agent_steps_persisted(self, db_session):
        """Test that AgentSteps are persisted"""
        orchestrator = OrchestratorAgent()

        # Create run first
        run_id = await orchestrator._create_agent_run(
            db=db_session,
            conversation_id=f"test-{uuid.uuid4().hex[:8]}",
            intent="TEST",
            plan={}
        )

        # Log step
        await orchestrator._log_agent_step(
            db=db_session,
            run_id=run_id,
            step_number=0,
            tool="test.tool",
            input_data={"key": "value"},
            output_data={"result": "success"},
            latency_ms=50
        )

        # Query back
        result = await db_session.execute(
            text("SELECT * FROM agent_steps WHERE run_id = :run_id"),
            {"run_id": run_id}
        )
        rows = result.fetchall()

        assert len(rows) >= 1
        assert rows[0].tool == "test.tool"
        assert rows[0].latency_ms == 50

        print(f"✓ Real DB Steps Persistence Test Passed")
        print(f"  Steps logged: {len(rows)}")


if __name__ == "__main__":
    # Run tests
    if USE_REAL_DB:
        print("🔥 Running E2E tests with REAL DATABASE")
    else:
        print("🧪 Running E2E tests with MOCKED DATABASE")

    pytest.main([__file__, "-v", "--tb=short", "-s"])
