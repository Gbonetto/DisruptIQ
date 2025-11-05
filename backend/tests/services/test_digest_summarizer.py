"""
Tests for Digest Summarizer Service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.services.digest_summarizer import DigestSummarizer


@pytest.fixture
def summarizer():
    """Fixture for DigestSummarizer instance"""
    return DigestSummarizer()


@pytest.fixture
def classified_emails_sample():
    """Sample classified emails for testing"""
    return {
        "urgent": [
            {
                "message_id": "urgent1",
                "subject": "Fuite d'eau urgente - Appartement 302",
                "sender": "resident@example.com",
                "body": "Fuite importante dans la salle de bain, intervention urgente requise",
                "llm_analysis": {
                    "category": "intervention_urgente",
                    "action_required": True,
                    "deadline": "2024-11-05T18:00:00Z",
                    "priority_score": 95,
                    "entities": {
                        "amounts": [],
                        "dates": [],
                        "persons": [],
                        "companies": [],
                        "locations": ["Appartement 302"]
                    }
                }
            },
            {
                "message_id": "urgent2",
                "subject": "Devis travaux - Confirmation avant 17h",
                "sender": "plombier@example.com",
                "body": "Devis plomberie 2500€, besoin confirmation avant 17h aujourd'hui",
                "llm_analysis": {
                    "category": "devis_fournisseur",
                    "action_required": True,
                    "deadline": "2024-11-05T17:00:00Z",
                    "priority_score": 85,
                    "entities": {
                        "amounts": [{"value": 2500.0, "currency": "EUR"}],
                        "dates": [],
                        "persons": [],
                        "companies": [],
                        "locations": []
                    }
                }
            }
        ],
        "important": [
            {
                "message_id": "important1",
                "subject": "Assemblée générale - 15 novembre 2024",
                "sender": "syndic@example.com",
                "body": "Convocation à l'assemblée générale du 15 novembre",
                "llm_analysis": {
                    "category": "assemblee_generale",
                    "action_required": False,
                    "deadline": "2024-11-15T14:00:00Z",
                    "priority_score": 70,
                    "entities": {
                        "amounts": [],
                        "dates": ["2024-11-15"],
                        "persons": [],
                        "companies": [],
                        "locations": []
                    }
                }
            }
        ],
        "routine": [
            {
                "message_id": "routine1",
                "subject": "Newsletter mensuelle",
                "sender": "newsletter@example.com",
                "body": "Votre newsletter mensuelle",
                "llm_analysis": {
                    "category": "information",
                    "action_required": False,
                    "deadline": None,
                    "priority_score": 20,
                    "entities": {
                        "amounts": [],
                        "dates": [],
                        "persons": [],
                        "companies": [],
                        "locations": []
                    }
                }
            }
        ]
    }


@pytest.fixture
def llm_summary_response():
    """Mock LLM summary response"""
    return {
        "overview": "Activité soutenue avec 4 emails reçus. 2 actions urgentes nécessitent une attention immédiate.",
        "highlights": [
            "Intervention urgente requise - Fuite Apt 302",
            "Devis plomberie à confirmer avant 17h (2 500€)",
            "Assemblée générale programmée le 15 novembre"
        ],
        "by_category": {
            "intervention_urgente": "1 intervention requise (fuite Apt 302)",
            "devis_fournisseur": "1 devis en attente de confirmation (2 500€)",
            "assemblee_generale": "Convocation envoyée pour le 15/11"
        }
    }


class TestDigestSummarizer:
    """Test suite for DigestSummarizer"""

    @pytest.mark.asyncio
    async def test_generate_executive_summary_success(
        self,
        summarizer,
        classified_emails_sample,
        llm_summary_response
    ):
        """Test successful executive summary generation"""
        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            import json
            mock_llm.return_value = json.dumps(llm_summary_response)

            result = await summarizer.generate_executive_summary(classified_emails_sample)

            # Verify structure
            assert "overview" in result
            assert "urgent_actions" in result
            assert "highlights" in result
            assert "by_category" in result
            assert "metrics" in result
            assert "generated_at" in result

            # Verify content
            assert len(result["urgent_actions"]) <= summarizer.MAX_URGENT_ACTIONS
            assert len(result["highlights"]) <= summarizer.MAX_HIGHLIGHTS
            assert result["overview"] == llm_summary_response["overview"]
            assert result["highlights"] == llm_summary_response["highlights"]

    @pytest.mark.asyncio
    async def test_analytics_calculation(
        self,
        summarizer,
        classified_emails_sample
    ):
        """Test analytics calculation from classified emails"""
        analytics = summarizer._calculate_analytics(classified_emails_sample)

        # Verify total counts
        assert analytics["total_emails"] == 4
        assert analytics["urgent_count"] == 2
        assert analytics["important_count"] == 1
        assert analytics["routine_count"] == 1

        # Verify action required count
        assert analytics["action_required_count"] == 2  # 2 urgent emails with action_required

        # Verify category breakdown
        assert analytics["category_breakdown"]["intervention_urgente"] == 1
        assert analytics["category_breakdown"]["devis_fournisseur"] == 1
        assert analytics["category_breakdown"]["assemblee_generale"] == 1
        assert analytics["category_breakdown"]["information"] == 1

        # Verify amounts
        assert analytics["total_amounts_eur"] == 2500.0
        assert analytics["amounts_count"] == 1

    @pytest.mark.asyncio
    async def test_urgent_actions_extraction(
        self,
        summarizer,
        classified_emails_sample
    ):
        """Test urgent actions extraction from urgent emails"""
        urgent_emails = classified_emails_sample["urgent"]
        actions = summarizer._extract_urgent_actions(urgent_emails)

        # Verify actions extracted
        assert len(actions) == 2
        assert all("action" in action for action in actions)
        assert all("description" in action for action in actions)
        assert all("sender" in action for action in actions)

        # Verify sorting by priority score (descending)
        assert actions[0]["priority_score"] >= actions[1]["priority_score"]

        # Verify deadline present for actions
        assert actions[0]["deadline"] is not None

    @pytest.mark.asyncio
    async def test_urgent_actions_max_limit(
        self,
        summarizer,
        llm_summary_response
    ):
        """Test urgent actions are limited to MAX_URGENT_ACTIONS in executive summary"""
        # Create 10 urgent emails
        classified_emails = {
            "urgent": [
                {
                    "subject": f"Urgent {i}",
                    "sender": f"sender{i}@example.com",
                    "llm_analysis": {
                        "action_required": True,
                        "suggested_response": f"Action {i}",
                        "deadline": "2024-11-05T17:00:00Z",
                        "priority_score": 90 - i
                    }
                }
                for i in range(10)
            ],
            "important": [],
            "routine": []
        }

        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            import json
            mock_llm.return_value = json.dumps(llm_summary_response)

            result = await summarizer.generate_executive_summary(classified_emails)

            # urgent_actions should be limited to MAX_URGENT_ACTIONS (5)
            assert len(result["urgent_actions"]) <= summarizer.MAX_URGENT_ACTIONS
            assert len(result["urgent_actions"]) == 5  # Exactly 5 out of 10

    @pytest.mark.asyncio
    async def test_fallback_overview_generation(
        self,
        summarizer
    ):
        """Test fallback overview when LLM fails"""
        analytics = {
            "total_emails": 10,
            "urgent_count": 3,
            "action_required_count": 5
        }

        overview = summarizer._generate_fallback_overview(analytics)

        assert "10 emails" in overview
        assert "3 emails urgents" in overview
        assert "5 actions requises" in overview

    @pytest.mark.asyncio
    async def test_fallback_summary_generation(
        self,
        summarizer,
        classified_emails_sample
    ):
        """Test complete fallback summary when LLM fails"""
        analytics = {
            "total_emails": 4,
            "urgent_count": 2,
            "important_count": 1,
            "routine_count": 1,
            "action_required_count": 2
        }

        result = summarizer._generate_fallback_summary(
            classified_emails_sample,
            analytics
        )

        # Verify structure
        assert "overview" in result
        assert "urgent_actions" in result
        assert "highlights" in result
        assert "by_category" in result
        assert "metrics" in result

        # Verify fallback values
        assert result["highlights"] == []
        assert result["by_category"] == {}
        assert len(result["urgent_actions"]) <= summarizer.MAX_URGENT_ACTIONS

    @pytest.mark.asyncio
    async def test_llm_summary_generation_with_context(
        self,
        summarizer,
        classified_emails_sample,
        llm_summary_response
    ):
        """Test LLM summary includes proper context"""
        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            import json
            mock_llm.return_value = json.dumps(llm_summary_response)

            analytics = summarizer._calculate_analytics(classified_emails_sample)
            context = summarizer._prepare_context(classified_emails_sample, analytics)

            await summarizer._generate_llm_summary(context, classified_emails_sample)

            # Verify LLM was called with proper context
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            prompt = call_args[1]["prompt"]

            # Verify context includes key information
            assert "Total emails:" in context
            assert "Urgents:" in context
            assert "EMAILS URGENTS" in context
            assert "EMAILS IMPORTANTS" in context

    @pytest.mark.asyncio
    async def test_llm_summary_json_parsing(
        self,
        summarizer,
        classified_emails_sample
    ):
        """Test LLM summary handles JSON parsing correctly"""
        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            # Return JSON wrapped in markdown code block
            markdown_response = """```json
{
    "overview": "Test overview",
    "highlights": ["Highlight 1", "Highlight 2"],
    "by_category": {"devis_fournisseur": "2 devis"}
}
```"""
            mock_llm.return_value = markdown_response

            analytics = summarizer._calculate_analytics(classified_emails_sample)
            context = summarizer._prepare_context(classified_emails_sample, analytics)

            result = await summarizer._generate_llm_summary(context, classified_emails_sample)

            # Should successfully parse JSON from markdown
            assert result["overview"] == "Test overview"
            assert len(result["highlights"]) == 2

    @pytest.mark.asyncio
    async def test_llm_summary_error_handling(
        self,
        summarizer,
        classified_emails_sample
    ):
        """Test LLM summary handles errors gracefully"""
        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            # Simulate LLM error
            mock_llm.side_effect = Exception("LLM service unavailable")

            analytics = summarizer._calculate_analytics(classified_emails_sample)
            context = summarizer._prepare_context(classified_emails_sample, analytics)

            result = await summarizer._generate_llm_summary(context, classified_emails_sample)

            # Should return fallback with empty highlights
            assert "overview" in result
            assert result["highlights"] == []
            assert result["by_category"] == {}

    @pytest.mark.asyncio
    async def test_executive_summary_with_provided_analytics(
        self,
        summarizer,
        classified_emails_sample,
        llm_summary_response
    ):
        """Test executive summary with pre-calculated analytics"""
        custom_analytics = {
            "total_emails": 4,
            "urgent_count": 2,
            "important_count": 1,
            "routine_count": 1,
            "action_required_count": 2,
            "category_breakdown": {},
            "total_amounts_eur": 2500.0,
            "amounts_count": 1
        }

        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            import json
            mock_llm.return_value = json.dumps(llm_summary_response)

            result = await summarizer.generate_executive_summary(
                classified_emails_sample,
                analytics=custom_analytics
            )

            # Should use provided analytics
            assert result["metrics"] == custom_analytics

    @pytest.mark.asyncio
    async def test_urgent_actions_only_for_action_required(
        self,
        summarizer
    ):
        """Test urgent actions only includes emails with action_required=True"""
        urgent_emails = [
            {
                "subject": "Action requise",
                "sender": "sender1@example.com",
                "llm_analysis": {
                    "action_required": True,
                    "suggested_response": "Répondre",
                    "priority_score": 90
                }
            },
            {
                "subject": "Info seulement",
                "sender": "sender2@example.com",
                "llm_analysis": {
                    "action_required": False,
                    "priority_score": 85
                }
            }
        ]

        actions = summarizer._extract_urgent_actions(urgent_emails)

        # Should only include email with action_required=True
        assert len(actions) == 1
        assert actions[0]["email_subject"] == "Action requise"

    @pytest.mark.asyncio
    async def test_highlights_max_limit(
        self,
        summarizer,
        classified_emails_sample
    ):
        """Test highlights are limited to MAX_HIGHLIGHTS"""
        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            import json
            # Return 10 highlights
            response_with_many_highlights = {
                "overview": "Test",
                "highlights": [f"Highlight {i}" for i in range(10)],
                "by_category": {}
            }
            mock_llm.return_value = json.dumps(response_with_many_highlights)

            result = await summarizer.generate_executive_summary(classified_emails_sample)

            # Should be limited to MAX_HIGHLIGHTS (5)
            assert len(result["highlights"]) <= summarizer.MAX_HIGHLIGHTS

    @pytest.mark.asyncio
    async def test_generated_at_timestamp(
        self,
        summarizer,
        classified_emails_sample,
        llm_summary_response
    ):
        """Test generated_at timestamp is included"""
        with patch.object(
            summarizer.llm_service,
            'generate_response',
            new_callable=AsyncMock
        ) as mock_llm:
            import json
            mock_llm.return_value = json.dumps(llm_summary_response)

            result = await summarizer.generate_executive_summary(classified_emails_sample)

            # Verify timestamp
            assert "generated_at" in result
            # Should be ISO format
            datetime.fromisoformat(result["generated_at"])  # Should not raise exception
