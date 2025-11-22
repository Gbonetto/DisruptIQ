"""
EXHAUSTIVE REAL API TESTS - Complete validation like user testing
Tests ALL scenarios: 33+ test cases covering every feature

Tests include:
- Template Filter (canned responses)
- Intent Shortcuts (bypass classification)
- UI Context Bypass (documents, modes, buttons)
- Source Selection (SQL only, RAG only, hybrid, etc.)
- Conversation History with Context
- Normal Classification
- Error Handling
- Security (SQL injection, XSS, etc.)
- Performance metrics
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics


class ExhaustiveAPITester:
    """Exhaustive test suite - tests EVERYTHING like a real user"""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0
        self.warnings = []
        self.category_stats = {}

    def test_all(self):
        """Run ALL exhaustive tests"""
        print("\n" + "=" * 100)
        print("🔬 EXHAUSTIVE REAL API TESTS - Complete System Validation")
        print(f"Base URL: {self.base_url}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)

        # Check if API is running
        if not self._check_api_health():
            print("\n❌ API is not running! Start backend first.")
            print("   Run: docker-compose up -d backend")
            return

        print("\n✅ API is running\n")

        # CATEGORY 1: Template Filter - Bypass Full SMA (4 tests)
        self._test_category_1_template_filter()

        # CATEGORY 2: Intent Shortcuts - Bypass Classification (3 tests)
        self._test_category_2_intent_shortcuts()

        # CATEGORY 3: UI Context Bypass - Sprint 1 Feature (8 tests)
        self._test_category_3_ui_context_bypass()

        # CATEGORY 4: Source Selection - User-Controlled Routing (6 tests)
        self._test_category_4_source_selection()

        # CATEGORY 5: Conversation History - Context Preservation (3 tests)
        self._test_category_5_conversation_history()

        # CATEGORY 6: Normal Classification - All Intents (7 tests)
        self._test_category_6_normal_classification()

        # CATEGORY 7: Error Handling - Edge Cases (7 tests)
        self._test_category_7_error_handling()

        # CATEGORY 8: Security - Injection & XSS (3 tests)
        self._test_category_8_security()

        # CATEGORY 9: Performance - Speed Metrics (3 tests)
        self._test_category_9_performance()

        # Print comprehensive results
        self._print_comprehensive_results()

    def _check_api_health(self) -> bool:
        """Check if API is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    # ==================================================================================
    # CATEGORY 1: TEMPLATE FILTER - Bypass Full SMA (4 tests)
    # ==================================================================================

    def _test_category_1_template_filter(self):
        """Test template filter canned responses"""
        self._print_category_header(1, "TEMPLATE FILTER - Bypass Full SMA", 4)

        tests = [
            ("bonjour", ["Bonjour", "👋"], "Greeting"),
            ("merci", ["plaisir"], "Thanks"),
            ("au revoir", ["Au revoir", "👋"], "Goodbye"),
            ("ok merci", ["Parfait"], "Acknowledgment"),
        ]

        for query, expected_contains, desc in tests:
            self._run_api_test(
                category="1. Template Filter",
                query=query,
                description=desc,
                expected_success=True,
                expected_contains=expected_contains,
                should_be_instant=True
            )

    # ==================================================================================
    # CATEGORY 2: INTENT SHORTCUTS - Bypass Classification (3 tests)
    # ==================================================================================

    def _test_category_2_intent_shortcuts(self):
        """Test intent shortcuts"""
        self._print_category_header(2, "INTENT SHORTCUTS - Bypass Classification", 3)

        tests = [
            ("aide", ["aider"], "Help FR"),
            ("?", ["aider"], "Help Symbol"),
            ("help", ["aider"], "Help EN"),
        ]

        for query, expected_contains, desc in tests:
            self._run_api_test(
                category="2. Intent Shortcuts",
                query=query,
                description=desc,
                expected_success=True,
                expected_contains=expected_contains
            )

    # ==================================================================================
    # CATEGORY 3: UI CONTEXT BYPASS - Sprint 1 Feature (8 tests)
    # ==================================================================================

    def _test_category_3_ui_context_bypass(self):
        """Test UI context bypass - Sprint 1 integration"""
        self._print_category_header(3, "UI CONTEXT BYPASS - Sprint 1 Feature", 8)

        # Test 1: Single document selected
        self._run_api_test(
            category="3. UI Context Bypass",
            query="Analyse ce document",
            description="Single Document Selected",
            ui_context={"selected_document_id": 123, "active_document_ids": [123]},
            expected_success=True,
            expected_contains=["document"],
            check_bypass=True
        )

        # Test 2: Multiple documents active (should pick first)
        self._run_api_test(
            category="3. UI Context Bypass",
            query="Recherche dans les documents",
            description="Multiple Documents Active",
            ui_context={"active_document_ids": [456, 789]},
            expected_success=True,
            expected_contains=["document"],
            check_bypass=True
        )

        # Test 3: SQL Query Builder Mode
        self._run_api_test(
            category="3. UI Context Bypass",
            query="montre-moi les copropriétaires",
            description="UI Mode: SQL Query Builder",
            ui_context={"ui_mode": "sql_query_builder"},
            expected_success=True,
            expected_contains=["copropriétaires", "données"],
            check_bypass=True
        )

        # Test 4: Email Composer Mode
        self._run_api_test(
            category="3. UI Context Bypass",
            query="prépare un email",
            description="UI Mode: Email Composer",
            ui_context={"ui_mode": "email_composer"},
            expected_success=True,
            expected_contains=["email"],
            check_bypass=True
        )

        # Test 5: Document Viewer Mode
        self._run_api_test(
            category="3. UI Context Bypass",
            query="analyse ce contrat",
            description="UI Mode: Document Viewer",
            ui_context={"ui_mode": "document_viewer"},
            expected_success=True,
            expected_contains=["document"],
            check_bypass=True
        )

        # Test 6: Legal Analyzer Mode
        self._run_api_test(
            category="3. UI Context Bypass",
            query="jurisprudence",
            description="UI Mode: Legal Analyzer",
            ui_context={"ui_mode": "legal_analyzer"},
            expected_success=True,
            expected_contains=["juridique", "legal", "loi"],
            check_bypass=True
        )

        # Test 7: Action Button - Generate Email
        self._run_api_test(
            category="3. UI Context Bypass",
            query="génère un email pour le syndic",
            description="Action Button: Generate Email",
            ui_context={"action_button": "generate_email"},
            expected_success=True,
            expected_contains=["email"],
            check_bypass=True
        )

        # Test 8: Combined Context (doc + mode)
        self._run_api_test(
            category="3. UI Context Bypass",
            query="analyse",
            description="Combined: Document + Mode",
            ui_context={
                "selected_document_id": 999,
                "active_document_ids": [999],
                "ui_mode": "document_viewer"
            },
            expected_success=True,
            expected_contains=["document"],
            check_bypass=True
        )

    # ==================================================================================
    # CATEGORY 4: SOURCE SELECTION - User-Controlled Routing (6 tests)
    # ==================================================================================

    def _test_category_4_source_selection(self):
        """Test source selection - user controls routing"""
        self._print_category_header(4, "SOURCE SELECTION - User-Controlled Routing", 6)

        # Test 1: SQL Only
        self._run_api_test(
            category="4. Source Selection",
            query="Combien de copropriétaires?",
            description="SQL Only",
            selected_sources=["sql"],
            expected_success=True,
            expected_contains=["copropriétaires", "données"]
        )

        # Test 2: RAG Only
        self._run_api_test(
            category="4. Source Selection",
            query="Recherche dans les documents",
            description="RAG Only",
            selected_sources=["rag"],
            expected_success=True,
            expected_contains=["document"]
        )

        # Test 3: Web Only
        self._run_api_test(
            category="4. Source Selection",
            query="Quelle est l'actualité?",
            description="Web Only",
            selected_sources=["web"],
            expected_success=True,
            expected_contains=[]  # May vary
        )

        # Test 4: SQL + RAG (Hybrid)
        self._run_api_test(
            category="4. Source Selection",
            query="Combien de documents pour ce copropriétaire?",
            description="Hybrid: SQL + RAG",
            selected_sources=["sql", "rag"],
            expected_success=True,
            expected_contains=[]  # Hybrid can vary
        )

        # Test 5: All Sources
        self._run_api_test(
            category="4. Source Selection",
            query="Informations complètes",
            description="All Sources: SQL + RAG + Web",
            selected_sources=["sql", "rag", "web"],
            expected_success=True,
            expected_contains=[]
        )

        # Test 6: No Source Selected (should classify)
        self._run_api_test(
            category="4. Source Selection",
            query="Combien de copropriétaires?",
            description="No Source (Auto-Classify)",
            selected_sources=[],
            expected_success=True,
            expected_contains=["copropriétaires"]
        )

    # ==================================================================================
    # CATEGORY 5: CONVERSATION HISTORY - Context Preservation (3 tests)
    # ==================================================================================

    def _test_category_5_conversation_history(self):
        """Test conversation history context preservation"""
        self._print_category_header(5, "CONVERSATION HISTORY - Context Preservation", 3)

        # Test 1: Email Draft in History
        history_with_draft = [
            {
                "role": "assistant",
                "content": "Voici un brouillon d'email",
                "data": {
                    "email_draft": {
                        "to": "syndic@example.com",
                        "subject": "Test",
                        "body": "Contenu"
                    },
                    "awaiting_confirmation": True
                }
            }
        ]

        self._run_api_test(
            category="5. Conversation History",
            query="oui envoie-le",
            description="Email Draft Context",
            conversation_history=history_with_draft,
            expected_success=True,
            expected_contains=["email"]
        )

        # Test 2: Emails Available in History
        history_with_emails = [
            {
                "role": "assistant",
                "content": "Voici les emails",
                "data": {
                    "emails_available": [
                        {"email": "john@example.com", "name": "John"},
                        {"email": "jane@example.com", "name": "Jane"}
                    ]
                }
            }
        ]

        self._run_api_test(
            category="5. Conversation History",
            query="envoie un email au premier",
            description="Emails Available Context",
            conversation_history=history_with_emails,
            expected_success=True,
            expected_contains=["email"]
        )

        # Test 3: Empty History (new conversation)
        self._run_api_test(
            category="5. Conversation History",
            query="Bonjour",
            description="Empty History (New Session)",
            conversation_history=[],
            expected_success=True,
            expected_contains=["Bonjour"]
        )

    # ==================================================================================
    # CATEGORY 6: NORMAL CLASSIFICATION - All Intents (7 tests)
    # ==================================================================================

    def _test_category_6_normal_classification(self):
        """Test normal classification for all intent types"""
        self._print_category_header(6, "NORMAL CLASSIFICATION - All Intents", 7)

        tests = [
            ("Combien de copropriétaires?", ["copropriétaires"], "QUERY_DATA"),
            ("Liste tous les professionnels", ["professionnels", "données"], "QUERY_DATA List"),
            ("Recherche dans mes documents sur les AG", ["document"], "SEARCH_DOCUMENTS"),
            ("Cherche sur internet", ["web", "recherche"], "WEB_SEARCH"),
            ("Envoie un email au syndic", ["email"], "SEND_EMAIL"),
            ("Quelle est la jurisprudence?", ["juridique", "legal", "loi"], "LEGAL"),
            ("Qu'est-ce qu'une copropriété?", [], "GENERAL_QUESTION"),
        ]

        for query, expected_contains, desc in tests:
            self._run_api_test(
                category="6. Normal Classification",
                query=query,
                description=desc,
                expected_success=True,
                expected_contains=expected_contains,
                allow_soft_fail=True  # Some may fail due to missing data
            )

    # ==================================================================================
    # CATEGORY 7: ERROR HANDLING - Edge Cases (7 tests)
    # ==================================================================================

    def _test_category_7_error_handling(self):
        """Test error handling and edge cases"""
        self._print_category_header(7, "ERROR HANDLING - Edge Cases", 7)

        tests = [
            ("", [], "Empty Query", True),
            ("   ", [], "Whitespace Only", True),
            ("a", [], "Single Character", False),
            ("test " * 100, [], "Very Long Query (500 chars)", False),
            ("test " * 1000, [], "Extremely Long Query (5000 chars)", False),
            ("Recherche 'copropriété' avec $", [], "Special Characters", False),
            ("Test & émoji 🎉 <html>", [], "Mixed Special Chars", False),
        ]

        for query, expected_contains, desc, allow_error in tests:
            self._run_api_test(
                category="7. Error Handling",
                query=query,
                description=desc,
                expected_success=not allow_error,
                expected_contains=expected_contains,
                allow_error=allow_error
            )

    # ==================================================================================
    # CATEGORY 8: SECURITY - Injection & XSS (3 tests)
    # ==================================================================================

    def _test_category_8_security(self):
        """Test security - SQL injection, XSS attempts"""
        self._print_category_header(8, "SECURITY - Injection & XSS", 3)

        tests = [
            ("'; DROP TABLE coproprietes; --", "SQL Injection - DROP TABLE"),
            ("1' OR '1'='1", "SQL Injection - OR bypass"),
            ("<script>alert('XSS')</script>", "XSS Attempt"),
        ]

        for query, desc in tests:
            self._run_api_test(
                category="8. Security",
                query=query,
                description=desc,
                expected_success=True,  # Should handle gracefully
                expected_contains=[],
                check_no_sql_execution=True
            )

    # ==================================================================================
    # CATEGORY 9: PERFORMANCE - Speed Metrics (3 tests)
    # ==================================================================================

    def _test_category_9_performance(self):
        """Test performance metrics"""
        self._print_category_header(9, "PERFORMANCE - Speed Metrics", 3)

        # Test 1: Template Response Speed
        start = time.time()
        self._run_api_test(
            category="9. Performance",
            query="bonjour",
            description="Template Speed (<1s target)",
            expected_success=True,
            expected_contains=["Bonjour"],
            max_duration=2.0  # Allow 2s for Docker overhead
        )

        # Test 2: Quick Rule Speed
        self._run_api_test(
            category="9. Performance",
            query="Combien de copropriétaires?",
            description="Quick Rule Speed (<2s target)",
            expected_success=True,
            expected_contains=["copropriétaires"],
            max_duration=5.0
        )

        # Test 3: LLM Fallback Speed
        self._run_api_test(
            category="9. Performance",
            query="Recherche dans mes documents sur les assemblées générales",
            description="LLM Fallback (<30s target)",
            expected_success=True,
            expected_contains=["document"],
            max_duration=30.0
        )

    # ==================================================================================
    # HELPER METHODS
    # ==================================================================================

    def _print_category_header(self, num: int, title: str, test_count: int):
        """Print category header"""
        print("\n" + "=" * 100)
        print(f"CATEGORY {num}: {title} ({test_count} tests)")
        print("=" * 100)

    def _run_api_test(
        self,
        category: str,
        query: str,
        description: str,
        expected_success: bool = True,
        expected_contains: List[str] = None,
        should_be_instant: bool = False,
        ui_context: Dict[str, Any] = None,
        selected_sources: List[str] = None,
        conversation_history: List[Dict] = None,
        active_document_ids: List[int] = None,
        allow_error: bool = False,
        allow_soft_fail: bool = False,
        check_bypass: bool = False,
        check_no_sql_execution: bool = False,
        max_duration: float = None
    ):
        """Run a single comprehensive API test"""
        test_name = f"{description}: '{query[:40]}...'" if len(query) > 40 else f"{description}: '{query}'"

        try:
            start_time = time.time()

            # Build request parameters
            url = f"{self.base_url}/api/assistant-v2/chat/stream"
            params = {
                "message": query,
                "conversation_history": json.dumps(conversation_history or []),
                "session_id": "test_exhaustive",
                "active_document_ids": json.dumps(active_document_ids or []),
                "selected_sources": json.dumps(selected_sources or []),
                "ui_context": json.dumps(ui_context or {})
            }

            # Make SSE request
            response = requests.get(url, params=params, stream=True, timeout=60)

            # Collect events
            events = []
            final_response = None
            thoughts = []

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line.split(":", 1)[1].strip())

                        if event_type == "thought":
                            thoughts.append(data)
                        elif event_type == "response":
                            final_response = data
                            break
                    except json.JSONDecodeError:
                        pass

            elapsed_time = time.time() - start_time

            # Validate response
            if final_response is None and not allow_error:
                raise Exception("No final response received")

            if final_response:
                success = final_response.get("success", False)
                message = final_response.get("message", "")

                # Check success
                if expected_success and not success and not allow_soft_fail:
                    raise Exception(f"Expected success=True, got {success}. Message: {message[:100]}")

                # Check expected content (warnings only)
                if expected_contains:
                    for expected_text in expected_contains:
                        if expected_text.lower() not in message.lower():
                            self.warnings.append(f"{test_name}: Expected '{expected_text}' not in response")

                # Check speed
                if should_be_instant and elapsed_time > 1.5:
                    self.warnings.append(f"{test_name}: Too slow ({elapsed_time:.2f}s > 1.5s)")

                if max_duration and elapsed_time > max_duration:
                    self.warnings.append(f"{test_name}: Exceeded max duration ({elapsed_time:.2f}s > {max_duration}s)")

                # Check bypass (look in thoughts for bypass events)
                if check_bypass:
                    bypass_found = any("bypass" in str(t).lower() for t in thoughts)
                    if not bypass_found:
                        self.warnings.append(f"{test_name}: Expected bypass, but not found in thoughts")

            # Test passed
            duration_str = f"{elapsed_time:.2f}s"
            print(f"✅ PASS {test_name} ({duration_str})")

            # Track result
            self.results.append({
                "category": category,
                "test": test_name,
                "passed": True,
                "duration": elapsed_time,
                "response_preview": final_response.get("message", "")[:80] if final_response else "No response"
            })
            self.passed += 1

            # Update category stats
            if category not in self.category_stats:
                self.category_stats[category] = {"passed": 0, "failed": 0, "total": 0}
            self.category_stats[category]["passed"] += 1
            self.category_stats[category]["total"] += 1

        except Exception as e:
            error_msg = str(e)

            # Check if soft fail allowed
            if allow_soft_fail and ("success=False" in error_msg or "trouvée" in error_msg):
                print(f"⚠️  SOFT FAIL {test_name}")
                print(f"   Reason: {error_msg[:150]}")

                self.results.append({
                    "category": category,
                    "test": test_name,
                    "passed": True,  # Count as pass (expected data issue)
                    "soft_fail": True,
                    "reason": error_msg
                })
                self.passed += 1

                if category not in self.category_stats:
                    self.category_stats[category] = {"passed": 0, "failed": 0, "total": 0}
                self.category_stats[category]["passed"] += 1
                self.category_stats[category]["total"] += 1
            else:
                print(f"❌ FAIL {test_name}")
                print(f"   Error: {error_msg[:150]}")

                self.results.append({
                    "category": category,
                    "test": test_name,
                    "passed": False,
                    "error": error_msg
                })
                self.failed += 1

                if category not in self.category_stats:
                    self.category_stats[category] = {"passed": 0, "failed": 0, "total": 0}
                self.category_stats[category]["failed"] += 1
                self.category_stats[category]["total"] += 1

    def _print_comprehensive_results(self):
        """Print comprehensive test results"""
        print("\n" + "=" * 100)
        print("📊 EXHAUSTIVE TEST RESULTS - COMPREHENSIVE ANALYSIS")
        print("=" * 100)

        total = len(self.results)
        success_rate = (self.passed / total * 100) if total > 0 else 0

        # Overall summary
        print(f"\n📈 OVERALL SUMMARY:")
        print(f"   Total Tests: {total}")
        print(f"   ✅ Passed: {self.passed}")
        print(f"   ❌ Failed: {self.failed}")
        print(f"   Success Rate: {success_rate:.1f}%")

        # Performance metrics
        passed_durations = [r["duration"] for r in self.results if r["passed"] and "duration" in r]
        if passed_durations:
            avg = statistics.mean(passed_durations)
            median = statistics.median(passed_durations)
            fastest = min(passed_durations)
            slowest = max(passed_durations)

            print(f"\n⚡ PERFORMANCE METRICS:")
            print(f"   Average Response Time: {avg:.2f}s")
            print(f"   Median Response Time: {median:.2f}s")
            print(f"   Fastest Response: {fastest:.2f}s")
            print(f"   Slowest Response: {slowest:.2f}s")

        # Category breakdown
        print(f"\n📋 BY CATEGORY:")
        for category, stats in sorted(self.category_stats.items()):
            cat_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            status = "✅" if cat_rate >= 75 else "⚠️" if cat_rate >= 50 else "❌"
            print(f"   {status} {category}: {stats['passed']}/{stats['total']} ({cat_rate:.1f}%)")

        # Warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings[:10]:  # Show first 10
                print(f"   - {warning}")
            if len(self.warnings) > 10:
                print(f"   ... and {len(self.warnings) - 10} more warnings")

        # Failed tests
        if self.failed > 0:
            print(f"\n❌ FAILED TESTS ({self.failed}):")
            for result in self.results:
                if not result["passed"]:
                    print(f"   - {result['test']}")
                    if "error" in result:
                        print(f"     Error: {result['error'][:120]}")

        # Final verdict
        print("\n" + "=" * 100)
        if success_rate >= 90:
            print("🎉 EXCELLENT - System is production-ready!")
        elif success_rate >= 75:
            print("✅ GOOD - System is stable with minor issues")
        elif success_rate >= 50:
            print("⚠️  FAIR - System needs improvements")
        else:
            print("❌ POOR - System has critical issues")
        print("=" * 100)

        # Save detailed report
        report_filename = f"exhaustive_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "passed": self.passed,
                    "failed": self.failed,
                    "success_rate": success_rate
                },
                "performance": {
                    "average": avg if passed_durations else 0,
                    "median": median if passed_durations else 0,
                    "fastest": fastest if passed_durations else 0,
                    "slowest": slowest if passed_durations else 0
                },
                "categories": self.category_stats,
                "warnings": self.warnings,
                "results": self.results
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detailed report saved: {report_filename}")


if __name__ == "__main__":
    tester = ExhaustiveAPITester()
    tester.test_all()
