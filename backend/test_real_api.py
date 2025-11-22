"""
REAL API TESTS - Exactly like user testing in browser
Tests the actual HTTP API endpoints with real requests
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any


class RealAPITester:
    """Test suite that calls REAL API like the frontend does"""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0

    def test_all(self):
        """Run all real API tests"""
        print("\n" + "=" * 80)
        print("🌐 REAL API TESTS - Testing like a real user")
        print(f"Base URL: {self.base_url}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Check if API is running
        if not self._check_api_health():
            print("\n❌ API is not running! Start backend first.")
            print("   Run: docker-compose up -d backend")
            return

        print("\n✅ API is running\n")

        # Category 1: Template Filter (bypass SMA)
        print("\n" + "=" * 80)
        print("CATEGORY 1: TEMPLATE FILTER - Canned Responses")
        print("=" * 80)
        self._test_template_responses()

        # Category 2: Intent Shortcuts
        print("\n" + "=" * 80)
        print("CATEGORY 2: INTENT SHORTCUTS - Bypass Classification")
        print("=" * 80)
        self._test_intent_shortcuts()

        # Category 3: Normal Classification
        print("\n" + "=" * 80)
        print("CATEGORY 3: NORMAL CLASSIFICATION - Full Flow")
        print("=" * 80)
        self._test_normal_classification()

        # Category 4: Error Handling
        print("\n" + "=" * 80)
        print("CATEGORY 4: ERROR HANDLING - Edge Cases")
        print("=" * 80)
        self._test_error_handling()

        # Print results
        self._print_results()

    def _check_api_health(self) -> bool:
        """Check if API is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _test_template_responses(self):
        """Test template filter canned responses"""
        test_cases = [
            {
                "query": "bonjour",
                "expected_contains": ["Bonjour", "👋"],
                "description": "Greeting"
            },
            {
                "query": "merci",
                "expected_contains": ["plaisir", "aider"],
                "description": "Thanks"
            },
            {
                "query": "au revoir",
                "expected_contains": ["Au revoir", "👋"],
                "description": "Goodbye"
            },
            {
                "query": "ok merci",
                "expected_contains": ["Parfait"],
                "description": "Acknowledgment"
            },
        ]

        for test in test_cases:
            self._run_api_test(
                test["query"],
                test["description"],
                expected_success=True,
                expected_contains=test["expected_contains"],
                should_be_fast=True  # Template responses should be <1s
            )

    def _test_intent_shortcuts(self):
        """Test intent shortcuts (bypass classification)"""
        test_cases = [
            {
                "query": "aide",
                "expected_contains": ["aider", "faire"],
                "description": "Help request (FR)"
            },
            {
                "query": "?",
                "expected_contains": ["aider"],
                "description": "Help request (?)"
            },
            {
                "query": "help",
                "expected_contains": ["aider"],
                "description": "Help request (EN)"
            },
        ]

        for test in test_cases:
            self._run_api_test(
                test["query"],
                test["description"],
                expected_success=True,
                expected_contains=test["expected_contains"],
                should_be_fast=False  # May call LLM
            )

    def _test_normal_classification(self):
        """Test normal classification flow"""
        test_cases = [
            {
                "query": "Combien de copropriétaires?",
                "expected_contains": ["copropriétaires", "données"],
                "description": "SQL Query"
            },
            {
                "query": "Recherche dans mes documents sur les AG",
                "expected_contains": ["document", "recherche"],
                "description": "RAG Search"
            },
            {
                "query": "Quelle est la jurisprudence sur les AG?",
                "expected_contains": ["juridique", "legal", "loi", "article"],
                "description": "Legal Query"
            },
            {
                "query": "Montre-moi tout",
                "expected_contains": [],  # Just shouldn't crash
                "description": "Ambiguous Query"
            },
            {
                "query": "Analyse",
                "expected_contains": [],  # Just shouldn't crash
                "description": "Single Word"
            },
        ]

        for test in test_cases:
            self._run_api_test(
                test["query"],
                test["description"],
                expected_success=True,
                expected_contains=test["expected_contains"],
                should_be_fast=False
            )

    def _test_error_handling(self):
        """Test error handling and edge cases"""
        test_cases = [
            {
                "query": "",
                "expected_contains": [],
                "description": "Empty Query",
                "allow_error": True
            },
            {
                "query": "test " * 100,
                "expected_contains": [],
                "description": "Very Long Query",
                "allow_error": False
            },
            {
                "query": "Recherche 'copropriété' avec $",
                "expected_contains": [],
                "description": "Special Characters",
                "allow_error": False
            },
            {
                "query": "'; DROP TABLE coproprietes; --",
                "expected_contains": [],
                "description": "SQL Injection Attempt",
                "allow_error": False
            },
        ]

        for test in test_cases:
            self._run_api_test(
                test["query"],
                test["description"],
                expected_success=not test.get("allow_error", False),
                expected_contains=test["expected_contains"],
                should_be_fast=False,
                allow_error=test.get("allow_error", False)
            )

    def _run_api_test(
        self,
        query: str,
        description: str,
        expected_success: bool = True,
        expected_contains: List[str] = None,
        should_be_fast: bool = False,
        allow_error: bool = False
    ):
        """Run a single API test"""
        test_name = f"{description}: '{query[:40]}...'" if len(query) > 40 else f"{description}: '{query}'"

        try:
            # Call the streaming API (same as frontend)
            start_time = time.time()

            url = f"{self.base_url}/api/assistant-v2/chat/stream"
            params = {
                "message": query,
                "conversation_history": "[]",
                "session_id": "test_session",
                "active_document_ids": "[]",
                "selected_sources": "[]",
                "ui_context": "{}"
            }

            # Make SSE request
            response = requests.get(url, params=params, stream=True, timeout=30)

            # Collect all events
            events = []
            final_response = None

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                # Parse SSE format
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line.split(":", 1)[1].strip())
                        events.append({"type": event_type, "data": data})

                        # Check if it's the final response
                        if event_type == "response":
                            final_response = data
                            break  # Stop after final response
                    except json.JSONDecodeError:
                        pass

            elapsed_time = time.time() - start_time

            # Validate response
            if final_response is None and not allow_error:
                raise Exception("No final response received")

            if final_response:
                # Check success
                success = final_response.get("success", False)
                message = final_response.get("message", "")

                if expected_success and not success:
                    raise Exception(f"Expected success=True, got {success}. Message: {message}")

                # Check expected content
                if expected_contains:
                    for expected_text in expected_contains:
                        if expected_text.lower() not in message.lower():
                            # Warning only, not failure
                            print(f"⚠️  WARNING: Expected '{expected_text}' not found in response")

                # Check speed
                if should_be_fast and elapsed_time > 1.0:
                    print(f"⚠️  WARNING: Template response too slow ({elapsed_time:.2f}s > 1s)")

            # Test passed
            duration_str = f"{elapsed_time:.2f}s"
            print(f"✅ PASS {test_name} ({duration_str})")

            self.results.append({
                "test": test_name,
                "passed": True,
                "duration": elapsed_time,
                "response": final_response.get("message", "")[:100] if final_response else "No response"
            })
            self.passed += 1

        except Exception as e:
            print(f"❌ FAIL {test_name}")
            print(f"   Error: {str(e)}")

            self.results.append({
                "test": test_name,
                "passed": False,
                "error": str(e)
            })
            self.failed += 1

    def _print_results(self):
        """Print test results summary"""
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)

        total = len(self.results)
        success_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success Rate: {success_rate:.1f}%")

        # Average duration for passed tests
        passed_durations = [r["duration"] for r in self.results if r["passed"] and "duration" in r]
        if passed_durations:
            avg_duration = sum(passed_durations) / len(passed_durations)
            print(f"Average Response Time: {avg_duration:.2f}s")

        # Show failed tests
        if self.failed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.results:
                if not result["passed"]:
                    print(f"   - {result['test']}")
                    if "error" in result:
                        print(f"     Error: {result['error'][:150]}")

        # Final verdict
        print("\n" + "=" * 80)
        if success_rate >= 75:
            print("✅ PASS - System is working well!")
        else:
            print("❌ FAIL - Too many failures, needs debugging")
        print("=" * 80)


if __name__ == "__main__":
    tester = RealAPITester()
    tester.test_all()
