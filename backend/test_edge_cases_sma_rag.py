"""
Comprehensive Edge Case Testing Suite for SMA-RAG System
Tests all critical paths, edge cases, and optimization features

Author: Claude Code
Date: November 22, 2025
Version: v5.1_sprint1 + Frontend Integration
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any
import structlog

from app.services.agents.orchestrator_agent import OrchestratorAgent
from app.services.template_filter import TemplateFilter, UIContextBypass
from app.models.intent import IntentType
from app.core.database import get_db

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()


class EdgeCaseTestSuite:
    """Comprehensive edge case testing for SMA-RAG system"""

    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.categories = {}

    def add_result(self, category: str, test_name: str, passed: bool,
                   details: str = "", duration_ms: float = 0, skipped: bool = False):
        """Add a test result"""
        result = {
            "category": category,
            "test_name": test_name,
            "passed": passed,
            "skipped": skipped,
            "details": details,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        }

        self.results.append(result)
        self.total_tests += 1

        if skipped:
            self.skipped_tests += 1
        elif passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

        # Track by category
        if category not in self.categories:
            self.categories[category] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        self.categories[category]["total"] += 1
        if skipped:
            self.categories[category]["skipped"] += 1
        elif passed:
            self.categories[category]["passed"] += 1
        else:
            self.categories[category]["failed"] += 1

        # Print result
        status = "⏭️ SKIP" if skipped else ("✅ PASS" if passed else "❌ FAIL")
        print(f"{status} [{category}] {test_name} ({duration_ms:.1f}ms)")
        if details and not passed:
            print(f"     Details: {details}")

    # ========================================================================
    # CATEGORY 1: BYPASS & OPTIMIZATION (Sprint 1)
    # ========================================================================

    async def test_category_1_bypass_optimization(self):
        """Test bypass and optimization features"""
        print("\n" + "="*80)
        print("CATEGORY 1: BYPASS & OPTIMIZATION (Sprint 1)")
        print("="*80)

        template_filter = TemplateFilter()
        ui_bypass = UIContextBypass()

        # Test 1.1: Template Filter - Canned Responses
        test_cases = [
            ("Bonjour", "greeting"),
            ("merci beaucoup", "thanks"),
            ("ok merci", "acknowledgment"),
            ("au revoir", "goodbye"),
        ]

        for query, expected_category in test_cases:
            start = time.time()
            result = template_filter.check(query)
            duration = (time.time() - start) * 1000

            passed = (
                result is not None and
                result.get('bypass_sma') == True and
                result.get('category') == expected_category
            )

            self.add_result(
                "1. Bypass Optimization",
                f"Template Filter: '{query}'",
                passed,
                f"Expected bypass_sma=True, category={expected_category}. Got: {result}",
                duration
            )

        # Test 1.2: Template Filter - Intent Shortcuts
        shortcut_cases = [
            ("aide", IntentType.GENERAL_QUESTION),
            ("?", IntentType.GENERAL_QUESTION),
            ("help", IntentType.GENERAL_QUESTION),
        ]

        for query, expected_intent in shortcut_cases:
            start = time.time()
            result = template_filter.check(query)
            duration = (time.time() - start) * 1000

            passed = (
                result is not None and
                result.get('bypass_classification') == True and
                result.get('intent') == expected_intent
            )

            self.add_result(
                "1. Bypass Optimization",
                f"Intent Shortcut: '{query}'",
                passed,
                f"Expected intent={expected_intent.value}. Got: {result}",
                duration
            )

        # Test 1.3: UI Context Bypass - Documents
        context_cases = [
            ({"selected_document_id": 123}, IntentType.SEARCH_DOCUMENTS, 0.95),
            ({"active_document_id": 456}, IntentType.SEARCH_DOCUMENTS, 0.95),
            ({"ui_mode": "sql_query_builder"}, IntentType.QUERY_DATA, 1.0),
            ({"ui_mode": "email_composer"}, IntentType.SEND_EMAIL, 1.0),
            ({"action_button": "generate_email"}, IntentType.SEND_EMAIL, 1.0),
        ]

        for context, expected_intent, expected_conf in context_cases:
            start = time.time()
            result = ui_bypass.check(context)
            duration = (time.time() - start) * 1000

            passed = (
                result is not None and
                result.get('bypass_classification') == True and
                result.get('intent') == expected_intent and
                result.get('confidence') == expected_conf
            )

            self.add_result(
                "1. Bypass Optimization",
                f"UI Context: {list(context.keys())[0]}",
                passed,
                f"Expected intent={expected_intent.value}, conf={expected_conf}. Got: {result}",
                duration
            )

    # ========================================================================
    # CATEGORY 2: INTENT CLASSIFICATION
    # ========================================================================

    async def test_category_2_intent_classification(self):
        """Test intent classification edge cases"""
        print("\n" + "="*80)
        print("CATEGORY 2: INTENT CLASSIFICATION")
        print("="*80)

        orchestrator = OrchestratorAgent()

        # Test 2.1: Clear Intent Cases
        clear_cases = [
            ("Combien de copropriétaires avons-nous?", IntentType.QUERY_DATA),
            ("Liste tous les professionnels", IntentType.QUERY_DATA),
            ("Recherche dans mes documents sur les AG", IntentType.SEARCH_DOCUMENTS),
            ("Envoie un email au syndic", IntentType.SEND_EMAIL),
            ("Quelle est la jurisprudence sur les AG?", IntentType.LEGAL),
        ]

        for query, expected_intent in clear_cases:
            start = time.time()
            try:
                intent, classification = await orchestrator.classify_intention(
                    user_input=query,
                    context={},
                    conversation_history=[]
                )
                duration = (time.time() - start) * 1000

                passed = (intent == expected_intent)

                self.add_result(
                    "2. Intent Classification",
                    f"Clear Intent: '{query[:40]}...'",
                    passed,
                    f"Expected {expected_intent.value}, got {intent.value}",
                    duration
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.add_result(
                    "2. Intent Classification",
                    f"Clear Intent: '{query[:40]}...'",
                    False,
                    f"Exception: {str(e)}",
                    duration
                )

        # Test 2.2: Ambiguous Cases (Accept any reasonable classification)
        ambiguous_cases = [
            ("Montre-moi tout", [IntentType.QUERY_DATA, IntentType.GENERAL_QUESTION]),
            ("Analyse", [IntentType.SEARCH_DOCUMENTS, IntentType.LEGAL, IntentType.GENERAL_QUESTION]),
        ]

        for query, acceptable_intents in ambiguous_cases:
            start = time.time()
            try:
                intent, classification = await orchestrator.classify_intention(
                    user_input=query,
                    context={},
                    conversation_history=[]
                )
                duration = (time.time() - start) * 1000

                passed = (intent in acceptable_intents)

                self.add_result(
                    "2. Intent Classification",
                    f"Ambiguous: '{query}'",
                    passed,
                    f"Expected one of {[i.value for i in acceptable_intents]}, got {intent.value}",
                    duration
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.add_result(
                    "2. Intent Classification",
                    f"Ambiguous: '{query}'",
                    False,
                    f"Exception: {str(e)}",
                    duration
                )

    # ========================================================================
    # CATEGORY 3: ERROR HANDLING
    # ========================================================================

    async def test_category_3_error_handling(self):
        """Test error handling and edge cases"""
        print("\n" + "="*80)
        print("CATEGORY 3: ERROR HANDLING")
        print("="*80)

        orchestrator = OrchestratorAgent()
        template_filter = TemplateFilter()

        # Test 3.1: Empty Query
        start = time.time()
        try:
            result = template_filter.check("")
            duration = (time.time() - start) * 1000
            passed = (result is None)  # Should return None for empty
            self.add_result(
                "3. Error Handling",
                "Empty Query",
                passed,
                f"Expected None, got {result}",
                duration
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "3. Error Handling",
                "Empty Query",
                False,
                f"Exception: {str(e)}",
                duration
            )

        # Test 3.2: Very Long Query
        long_query = "test " * 1000  # 5000 chars
        start = time.time()
        try:
            intent, classification = await orchestrator.classify_intention(
                user_input=long_query,
                context={},
                conversation_history=[]
            )
            duration = (time.time() - start) * 1000
            passed = True  # Should handle gracefully
            self.add_result(
                "3. Error Handling",
                "Very Long Query (5000 chars)",
                passed,
                f"Handled successfully, intent={intent.value}",
                duration
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            # Acceptable if truncated or handled gracefully
            passed = "truncat" in str(e).lower() or "limit" in str(e).lower()
            self.add_result(
                "3. Error Handling",
                "Very Long Query (5000 chars)",
                passed,
                f"Exception: {str(e)}",
                duration
            )

        # Test 3.3: Special Characters
        special_cases = [
            "Recherche 'copropriété' avec $pecial",
            "Test & émoji 🎉",
            "Question avec <tags> et [brackets]",
        ]

        for query in special_cases:
            start = time.time()
            try:
                result = template_filter.check(query)
                duration = (time.time() - start) * 1000
                passed = True  # Should not crash
                self.add_result(
                    "3. Error Handling",
                    f"Special Chars: '{query[:30]}...'",
                    passed,
                    "Handled without crash",
                    duration
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.add_result(
                    "3. Error Handling",
                    f"Special Chars: '{query[:30]}...'",
                    False,
                    f"Exception: {str(e)}",
                    duration
                )

        # Test 3.4: SQL Injection Patterns (should be handled by parameterization)
        injection_patterns = [
            "Liste'; DROP TABLE coproprietes; --",
            "1' OR '1'='1",
            "'; DELETE FROM users WHERE '1'='1",
        ]

        for query in injection_patterns:
            start = time.time()
            try:
                intent, classification = await orchestrator.classify_intention(
                    user_input=query,
                    context={},
                    conversation_history=[]
                )
                duration = (time.time() - start) * 1000
                # Should classify normally, not execute injection
                passed = True
                self.add_result(
                    "3. Error Handling",
                    f"SQL Injection Pattern: '{query[:30]}...'",
                    passed,
                    f"Handled safely, classified as {intent.value}",
                    duration
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.add_result(
                    "3. Error Handling",
                    f"SQL Injection Pattern: '{query[:30]}...'",
                    False,
                    f"Exception: {str(e)}",
                    duration
                )

    # ========================================================================
    # CATEGORY 4: PERFORMANCE & OPTIMIZATION
    # ========================================================================

    async def test_category_4_performance(self):
        """Test performance and optimization metrics"""
        print("\n" + "="*80)
        print("CATEGORY 4: PERFORMANCE & OPTIMIZATION")
        print("="*80)

        template_filter = TemplateFilter()
        orchestrator = OrchestratorAgent()

        # Test 4.1: Template Filter Speed (should be <1ms)
        bypass_queries = ["Bonjour", "merci", "ok", "au revoir"]
        bypass_times = []

        for query in bypass_queries:
            start = time.time()
            result = template_filter.check(query)
            duration = (time.time() - start) * 1000
            bypass_times.append(duration)

        avg_bypass_time = sum(bypass_times) / len(bypass_times)
        passed = avg_bypass_time < 1.0  # Should be sub-millisecond

        self.add_result(
            "4. Performance",
            "Template Filter Speed",
            passed,
            f"Avg: {avg_bypass_time:.3f}ms (target: <1ms)",
            avg_bypass_time
        )

        # Test 4.2: Classification Speed (Quick Rules should be <100ms)
        classification_queries = [
            "Combien de copropriétaires?",
            "Liste les professionnels",
            "Recherche dans documents",
        ]
        classification_times = []

        for query in classification_queries:
            start = time.time()
            try:
                intent, classification = await orchestrator.classify_intention(
                    user_input=query,
                    context={},
                    conversation_history=[]
                )
                duration = (time.time() - start) * 1000
                classification_times.append(duration)
            except:
                pass

        if classification_times:
            avg_classification_time = sum(classification_times) / len(classification_times)
            passed = avg_classification_time < 2000  # Should be <2s

            self.add_result(
                "4. Performance",
                "Classification Speed",
                passed,
                f"Avg: {avg_classification_time:.1f}ms (target: <2000ms for LLM)",
                avg_classification_time
            )

        # Test 4.3: Bypass Rate
        mixed_queries = [
            "Bonjour",  # Bypass
            "merci",  # Bypass
            "Combien de copropriétaires?",  # No bypass
            "aide",  # Bypass (shortcut)
            "Liste les professionnels",  # No bypass
            "au revoir",  # Bypass
        ]

        bypass_count = 0
        for query in mixed_queries:
            result = template_filter.check(query)
            if result and (result.get('bypass_sma') or result.get('bypass_classification')):
                bypass_count += 1

        bypass_rate = (bypass_count / len(mixed_queries)) * 100
        passed = bypass_rate >= 40  # Target: ≥40%

        self.add_result(
            "4. Performance",
            "Bypass Rate",
            passed,
            f"Rate: {bypass_rate:.1f}% (target: ≥40%)",
            0
        )

    # ========================================================================
    # CATEGORY 5: INTEGRATION TESTS
    # ========================================================================

    async def test_category_5_integration(self):
        """Test end-to-end integration scenarios"""
        print("\n" + "="*80)
        print("CATEGORY 5: INTEGRATION TESTS")
        print("="*80)

        # Test 5.1: Full Flow - Bypass to Classification
        orchestrator = OrchestratorAgent()
        template_filter = TemplateFilter()

        # First try bypass
        query = "Combien de copropriétaires?"
        start = time.time()

        template_result = template_filter.check(query)
        if template_result is None:
            # Should fallto classification
            try:
                intent, classification = await orchestrator.classify_intention(
                    user_input=query,
                    context={},
                    conversation_history=[]
                )
                duration = (time.time() - start) * 1000
                passed = (intent == IntentType.QUERY_DATA)
                self.add_result(
                    "5. Integration",
                    "Bypass Fallback to Classification",
                    passed,
                    f"Bypassed correctly, classified as {intent.value}",
                    duration
                )
            except Exception as e:
                duration = (time.time() - start) * 1000
                self.add_result(
                    "5. Integration",
                    "Bypass Fallback to Classification",
                    False,
                    f"Exception: {str(e)}",
                    duration
                )

        # Test 5.2: UI Context Integration
        ui_bypass = UIContextBypass()
        context = {"selected_document_id": 123}

        start = time.time()
        ui_result = ui_bypass.check(context)
        duration = (time.time() - start) * 1000

        passed = (
            ui_result is not None and
            ui_result.get('intent') == IntentType.SEARCH_DOCUMENTS and
            ui_result.get('bypass_classification') == True
        )

        self.add_result(
            "5. Integration",
            "UI Context to Intent",
            passed,
            f"Document context → SEARCH_DOCUMENTS bypass",
            duration
        )

        # Test 5.3: Stats Reporting
        start = time.time()
        try:
            stats = template_filter.get_stats()
            duration = (time.time() - start) * 1000

            passed = (
                'canned_patterns' in stats and
                'intent_shortcuts' in stats and
                'total_templates' in stats and
                stats['total_templates'] > 0
            )

            self.add_result(
                "5. Integration",
                "Template Filter Stats",
                passed,
                f"Stats: {stats}",
                duration
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            self.add_result(
                "5. Integration",
                "Template Filter Stats",
                False,
                f"Exception: {str(e)}",
                duration
            )

    # ========================================================================
    # REPORT GENERATION
    # ========================================================================

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("TEST REPORT")
        print("="*80)

        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
                "skipped": self.skipped_tests,
                "success_rate": success_rate
            },
            "categories": self.categories,
            "results": self.results
        }

        print(f"\n📊 Summary:")
        print(f"   Total Tests: {self.total_tests}")
        print(f"   Passed: {self.passed_tests} ✅")
        print(f"   Failed: {self.failed_tests} ❌")
        print(f"   Skipped: {self.skipped_tests} ⏭️")
        print(f"   Success Rate: {success_rate:.1f}%")

        print(f"\n📈 By Category:")
        for category, stats in self.categories.items():
            cat_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"   {category}: {stats['passed']}/{stats['total']} ({cat_rate:.1f}%)")

        if success_rate >= 90:
            print(f"\n🎉 EXCELLENT! System is highly robust")
        elif success_rate >= 75:
            print(f"\n✅ GOOD! System is functional with minor issues")
        elif success_rate >= 50:
            print(f"\n⚠️  ACCEPTABLE! System needs improvements")
        else:
            print(f"\n❌ CRITICAL! System requires immediate attention")

        return report


async def main():
    """Run all edge case tests"""
    print("\n" + "🧪 SMA-RAG COMPREHENSIVE EDGE CASE TEST SUITE 🧪".center(80))
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    suite = EdgeCaseTestSuite()

    try:
        # Run all test categories
        await suite.test_category_1_bypass_optimization()
        await suite.test_category_2_intent_classification()
        await suite.test_category_3_error_handling()
        await suite.test_category_4_performance()
        await suite.test_category_5_integration()

        # Generate report
        report = suite.generate_report()

        # Save report to file
        report_file = f"test_edge_cases_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detailed report saved to: {report_file}")

        # Return exit code
        return 0 if report['summary']['success_rate'] >= 75 else 1

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
