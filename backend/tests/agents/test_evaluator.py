"""
Tests for Evaluator
"""

import pytest
from app.services.agents.evaluator import (
    Evaluator, RuleSeverity, RuleResult, EvaluationResult
)


class TestEvaluator:
    """Test suite for Evaluator"""

    @pytest.fixture
    def evaluator(self):
        """Create Evaluator instance"""
        return Evaluator()

    @pytest.mark.asyncio
    async def test_rag_has_citations_success(self, evaluator):
        """Test RAG citations rule - success case"""
        result = await evaluator.evaluate(
            rules=["rag_has_citations"],
            context={
                "response": "Selon le document [1], la procédure est claire [2].",
                "citations": [
                    {"id": "doc_1", "content": "..."},
                    {"id": "doc_2", "content": "..."}
                ]
            }
        )

        assert result.passed is True
        assert result.rules_passed == 1
        assert result.critical_failures == 0
        assert len(result.rules_failed) == 0

    @pytest.mark.asyncio
    async def test_rag_has_citations_failure(self, evaluator):
        """Test RAG citations rule - failure case"""
        result = await evaluator.evaluate(
            rules=["rag_has_citations"],
            context={
                "response": "La procédure est claire.",
                "citations": []
            }
        )

        assert result.passed is False
        assert result.rules_passed == 0
        assert result.critical_failures == 1
        assert "rag_has_citations" in result.rules_failed

    @pytest.mark.asyncio
    async def test_rag_min_sources(self, evaluator):
        """Test RAG minimum sources rule"""
        # Success: 2+ sources
        result_success = await evaluator.evaluate(
            rules=["rag_min_sources_2"],
            context={
                "citations": [
                    {"id": "doc_1", "content": "..."},
                    {"id": "doc_2", "content": "..."}
                ]
            }
        )
        assert result_success.passed is True

        # Warning: only 1 source
        result_warning = await evaluator.evaluate(
            rules=["rag_min_sources_2"],
            context={
                "citations": [{"id": "doc_1", "content": "..."}]
            }
        )
        assert result_warning.passed is False
        assert result_warning.warnings == 1
        assert result_warning.critical_failures == 0  # Warning, not critical

    @pytest.mark.asyncio
    async def test_sql_no_error(self, evaluator):
        """Test SQL no error rule"""
        # Success
        result_success = await evaluator.evaluate(
            rules=["sql_no_error"],
            context={
                "error": None,
                "results": [{"id": 1}]
            }
        )
        assert result_success.passed is True

        # Failure
        result_failure = await evaluator.evaluate(
            rules=["sql_no_error"],
            context={
                "error": "Syntax error near WHERE",
                "results": []
            }
        )
        assert result_failure.passed is False
        assert result_failure.critical_failures == 1

    @pytest.mark.asyncio
    async def test_sql_results_not_empty(self, evaluator):
        """Test SQL results not empty rule"""
        # Success
        result_success = await evaluator.evaluate(
            rules=["sql_results_not_empty"],
            context={
                "results": [{"id": 1}, {"id": 2}],
                "query": "SELECT * FROM users"
            }
        )
        assert result_success.passed is True

        # Warning (not critical)
        result_warning = await evaluator.evaluate(
            rules=["sql_results_not_empty"],
            context={
                "results": [],
                "query": "SELECT * FROM users"
            }
        )
        assert result_warning.passed is False
        assert result_warning.warnings == 1
        assert result_warning.critical_failures == 0

    @pytest.mark.asyncio
    async def test_sql_whitelist_tables(self, evaluator):
        """Test SQL whitelist tables rule"""
        # Success: using whitelisted view
        result_success = await evaluator.evaluate(
            rules=["sql_whitelist_tables"],
            context={
                "sql": "SELECT * FROM vw_professionnels_min WHERE city = 'Cannes'"
            }
        )
        assert result_success.passed is True

        # Failure: using non-whitelisted table
        result_failure = await evaluator.evaluate(
            rules=["sql_whitelist_tables"],
            context={
                "sql": "SELECT * FROM users WHERE id = 1"
            }
        )
        assert result_failure.passed is False
        assert result_failure.critical_failures == 1

    @pytest.mark.asyncio
    async def test_email_has_evidence(self, evaluator):
        """Test email evidence rule"""
        # Success
        result_success = await evaluator.evaluate(
            rules=["email_has_evidence"],
            context={
                "draft": {
                    "evidence": [
                        {"type": "rag", "doc_id": "doc_1"},
                        {"type": "sql", "query": "..."}
                    ]
                }
            }
        )
        assert result_success.passed is True

        # Failure
        result_failure = await evaluator.evaluate(
            rules=["email_has_evidence"],
            context={
                "draft": {"evidence": []}
            }
        )
        assert result_failure.passed is False
        assert result_failure.critical_failures == 1

    @pytest.mark.asyncio
    async def test_email_preview_shown(self, evaluator):
        """Test email preview shown rule"""
        result = await evaluator.evaluate(
            rules=["email_preview_shown"],
            context={"preview_shown": True}
        )
        assert result.passed is True

        result_fail = await evaluator.evaluate(
            rules=["email_preview_shown"],
            context={"preview_shown": False}
        )
        assert result_fail.passed is False

    @pytest.mark.asyncio
    async def test_n8n_preview_if_danger_high(self, evaluator):
        """Test N8N preview for high danger rule"""
        # Success: high danger + preview shown
        result_success = await evaluator.evaluate(
            rules=["n8n_preview_if_danger_high"],
            context={
                "danger_level": "high",
                "preview_shown": True
            }
        )
        assert result_success.passed is True

        # Success: low danger + no preview (OK)
        result_low_danger = await evaluator.evaluate(
            rules=["n8n_preview_if_danger_high"],
            context={
                "danger_level": "low",
                "preview_shown": False
            }
        )
        assert result_low_danger.passed is True

        # Failure: high danger but no preview
        result_failure = await evaluator.evaluate(
            rules=["n8n_preview_if_danger_high"],
            context={
                "danger_level": "high",
                "preview_shown": False
            }
        )
        assert result_failure.passed is False
        assert result_failure.critical_failures == 1

    @pytest.mark.asyncio
    async def test_hybrid_no_contradiction(self, evaluator):
        """Test hybrid no contradiction rule"""
        # Success: no conflicts
        result_success = await evaluator.evaluate(
            rules=["hybrid_no_contradiction"],
            context={
                "conflicts": []
            }
        )
        assert result_success.passed is True

        # Success: only low severity conflicts
        result_low_conflicts = await evaluator.evaluate(
            rules=["hybrid_no_contradiction"],
            context={
                "conflicts": [
                    {"field": "price", "severity": "low"}
                ]
            }
        )
        assert result_low_conflicts.passed is True

        # Failure: critical conflicts
        result_failure = await evaluator.evaluate(
            rules=["hybrid_no_contradiction"],
            context={
                "conflicts": [
                    {"field": "name", "severity": "critical", "sql_value": "A", "rag_value": "B"}
                ]
            }
        )
        assert result_failure.passed is False
        assert result_failure.critical_failures == 1

    @pytest.mark.asyncio
    async def test_web_urls_cited(self, evaluator):
        """Test web URLs cited rule"""
        # Success
        result_success = await evaluator.evaluate(
            rules=["web_urls_cited"],
            context={
                "response": "Selon source [1]",
                "citations": [
                    {"id": "web_1", "url": "https://example.com/article"}
                ]
            }
        )
        assert result_success.passed is True

        # Failure
        result_failure = await evaluator.evaluate(
            rules=["web_urls_cited"],
            context={
                "response": "Les informations...",
                "citations": []
            }
        )
        assert result_failure.passed is False

    @pytest.mark.asyncio
    async def test_multiple_rules(self, evaluator):
        """Test evaluation with multiple rules"""
        result = await evaluator.evaluate(
            rules=["rag_has_citations", "rag_min_sources_2", "sql_no_error"],
            context={
                "response": "Selon [1] et [2]",
                "citations": [
                    {"id": "doc_1", "content": "..."},
                    {"id": "doc_2", "content": "..."}
                ],
                "error": None
            }
        )

        assert result.passed is True
        assert result.rules_checked == 3
        assert result.rules_passed == 3
        assert len(result.details) == 3

    @pytest.mark.asyncio
    async def test_mixed_results(self, evaluator):
        """Test evaluation with mixed pass/fail results"""
        result = await evaluator.evaluate(
            rules=["rag_has_citations", "sql_no_error"],
            context={
                "response": "No citations here",
                "citations": [],
                "error": None
            }
        )

        # One critical failure (rag_has_citations), one success (sql_no_error)
        assert result.passed is False  # Global fail due to critical failure
        assert result.rules_checked == 2
        assert result.rules_passed == 1
        assert result.critical_failures == 1
        assert "rag_has_citations" in result.rules_failed

    @pytest.mark.asyncio
    async def test_unknown_rule(self, evaluator):
        """Test evaluation with unknown rule"""
        result = await evaluator.evaluate(
            rules=["unknown_rule_xyz"],
            context={}
        )

        assert result.passed is False
        assert result.warnings == 1
        assert "unknown_rule_xyz" in result.rules_failed

    @pytest.mark.asyncio
    async def test_rule_exception_handling(self, evaluator):
        """Test that rule exceptions are handled gracefully"""
        # This should trigger an exception in the rule check
        result = await evaluator.evaluate(
            rules=["rag_has_citations"],
            context={}  # Missing required keys
        )

        # Should handle exception and mark as critical failure
        assert result.passed is False
        assert result.critical_failures >= 1

    @pytest.mark.asyncio
    async def test_evidence_collection(self, evaluator):
        """Test that rules collect evidence properly"""
        result = await evaluator.evaluate(
            rules=["rag_has_citations"],
            context={
                "response": "Test [1][2]",
                "citations": [{"id": "1"}, {"id": "2"}]
            }
        )

        # Check that details contain evidence
        assert len(result.details) == 1
        detail = result.details[0]
        assert detail.evidence is not None
        assert "inline_citations_count" in detail.evidence
        assert "citations_array_count" in detail.evidence

    @pytest.mark.asyncio
    async def test_severity_levels(self, evaluator):
        """Test that different severity levels are properly handled"""
        result = await evaluator.evaluate(
            rules=["rag_has_citations", "rag_min_sources_2"],  # critical + warning
            context={
                "response": "No citations",
                "citations": []
            }
        )

        # rag_has_citations is CRITICAL
        # rag_min_sources_2 is WARNING
        assert result.critical_failures >= 1
        assert result.warnings >= 1

    def test_evaluator_rules_registry(self, evaluator):
        """Test that all expected rules are registered"""
        expected_rules = [
            "rag_has_citations",
            "rag_min_sources_2",
            "sql_no_error",
            "sql_results_not_empty",
            "sql_whitelist_tables",
            "email_has_evidence",
            "email_preview_shown",
            "n8n_preview_if_danger_high",
            "hybrid_no_contradiction",
            "hybrid_sources_attributed",
            "web_urls_cited"
        ]

        for rule_id in expected_rules:
            assert rule_id in evaluator.rules_registry, f"Rule {rule_id} not registered"

    @pytest.mark.asyncio
    async def test_evaluation_result_model(self):
        """Test EvaluationResult model"""
        result = EvaluationResult(
            passed=True,
            rules_checked=5,
            rules_passed=5,
            rules_failed=[],
            critical_failures=0,
            warnings=0,
            details=[
                RuleResult(
                    rule_id="test_rule",
                    passed=True,
                    severity=RuleSeverity.CRITICAL,
                    message="Test message"
                )
            ]
        )

        assert result.passed is True
        assert result.rules_checked == 5
        assert len(result.details) == 1
