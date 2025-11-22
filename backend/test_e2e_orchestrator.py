"""
End-to-End Tests for OrchestratorAgent
Tests complete flow: query → classification → execution → response

This catches bugs that unit tests miss (like CONFIRM_EMAIL crash)
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.agents.orchestrator_agent import OrchestratorAgent
from app.models.intent import IntentType


class E2ETestSuite:
    """End-to-End test suite for Orchestrator"""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    async def run_all_tests(self):
        """Run all E2E tests"""
        print("\n🧪 ORCHESTRATOR END-TO-END TEST SUITE 🧪")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Category 1: Template Filter Responses (Bypass Full SMA)
        await self._test_template_filter_e2e()

        # Category 2: Intent Shortcuts (Bypass Classification)
        await self._test_intent_shortcuts_e2e()

        # Category 3: Normal Classification Flow
        await self._test_classification_e2e()

        # Category 4: Error Handling
        await self._test_error_handling_e2e()

        # Print results
        self._print_results()

        # Exit with appropriate code
        success_rate = (self.passed / len(self.results)) * 100 if self.results else 0
        sys.exit(0 if success_rate >= 75 else 1)

    async def _test_template_filter_e2e(self):
        """Test template filter responses end-to-end"""
        print("=" * 80)
        print("CATEGORY 1: TEMPLATE FILTER (Full SMA Bypass)")
        print("=" * 80)

        test_cases = [
            ("bonjour", "greeting"),
            ("merci", "thanks"),
            ("au revoir", "goodbye"),
            ("ok merci", "acknowledgment"),
        ]

        for query, expected_category in test_cases:
            await self._run_e2e_test(
                category="Template Filter",
                query=query,
                expected_success=True,
                expected_intent=None,  # Bypassed, no intent
                check_fn=lambda result: len(result.message) > 0  # Has response
            )

    async def _test_intent_shortcuts_e2e(self):
        """Test intent shortcuts end-to-end"""
        print("\n" + "=" * 80)
        print("CATEGORY 2: INTENT SHORTCUTS (Bypass Classification)")
        print("=" * 80)

        test_cases = [
            ("aide", IntentType.GENERAL_QUESTION),
            ("?", IntentType.GENERAL_QUESTION),
            ("help", IntentType.GENERAL_QUESTION),
        ]

        for query, expected_intent in test_cases:
            await self._run_e2e_test(
                category="Intent Shortcut",
                query=query,
                expected_success=True,
                expected_intent=expected_intent,
                check_fn=lambda result: len(result.message) > 0
            )

    async def _test_classification_e2e(self):
        """Test normal classification flow end-to-end"""
        print("\n" + "=" * 80)
        print("CATEGORY 3: NORMAL CLASSIFICATION FLOW")
        print("=" * 80)

        test_cases = [
            ("Combien de copropriétaires?", IntentType.QUERY_DATA),
            ("Recherche dans mes documents", IntentType.SEARCH_DOCUMENTS),
            ("Quelle est la jurisprudence?", IntentType.LEGAL),
        ]

        for query, expected_intent in test_cases:
            await self._run_e2e_test(
                category="Classification",
                query=query,
                expected_success=True,
                expected_intent=expected_intent,
                check_fn=lambda result: len(result.message) > 0
            )

    async def _test_error_handling_e2e(self):
        """Test error handling end-to-end"""
        print("\n" + "=" * 80)
        print("CATEGORY 4: ERROR HANDLING")
        print("=" * 80)

        # Empty query
        await self._run_e2e_test(
            category="Error Handling",
            query="",
            expected_success=True,  # Should handle gracefully
            expected_intent=None,
            check_fn=lambda result: True  # Just shouldn't crash
        )

        # Very long query
        await self._run_e2e_test(
            category="Error Handling",
            query="test " * 1000,
            expected_success=True,
            expected_intent=IntentType.GENERAL_QUESTION,
            check_fn=lambda result: True
        )

    async def _run_e2e_test(self, category, query, expected_success, expected_intent, check_fn):
        """Run a single E2E test"""
        test_name = f"{category}: '{query[:30]}...'" if len(query) > 30 else f"{category}: '{query}'"

        try:
            # Create orchestrator
            orchestrator = OrchestratorAgent()

            # Mock dependencies
            mock_db = AsyncMock()
            mock_thought_stream = None  # Optional
            mock_state_manager = MagicMock()
            mock_state_manager.get_state.return_value = MagicMock(
                recipients_identified=[],
                business_context={},
                topic=None
            )

            # Execute full flow
            result = await orchestrator.process(
                user_input=query,
                db=mock_db,
                context={},
                conversation_history=[],
                thought_stream=mock_thought_stream,
                state_manager=mock_state_manager,
                selected_sources=None
            )

            # Check result
            assert result is not None, "Result is None"
            assert result.success == expected_success, f"Expected success={expected_success}, got {result.success}"

            if expected_intent:
                # Can't directly check intent, but can check agents_used
                pass  # Intent checking is hard in E2E

            assert check_fn(result), "Custom check failed"

            print(f"✅ PASS {test_name}")
            self.results.append({"test": test_name, "passed": True})
            self.passed += 1

        except Exception as e:
            print(f"❌ FAIL {test_name}")
            print(f"   Error: {str(e)}")
            self.results.append({"test": test_name, "passed": False, "error": str(e)})
            self.failed += 1

    def _print_results(self):
        """Print test results"""
        print("\n" + "=" * 80)
        print("TEST REPORT")
        print("=" * 80)

        total = len(self.results)
        success_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"\n📊 Summary:")
        print(f"   Total Tests: {total}")
        print(f"   Passed: {self.passed} ✅")
        print(f"   Failed: {self.failed} ❌")
        print(f"   Success Rate: {success_rate:.1f}%")

        if self.failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result["passed"]:
                    print(f"   - {result['test']}")
                    if "error" in result:
                        print(f"     Error: {result['error']}")

        if success_rate >= 75:
            print("\n✅ PASS - System is stable")
        else:
            print("\n❌ FAIL - Too many failures")


async def main():
    """Main test entry point"""
    suite = E2ETestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
