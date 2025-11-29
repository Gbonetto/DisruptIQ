"""
Edge Case Tests for DisruptIQ SMA (Système Multi-Agent)

Tests for handling edge cases, ambiguities, errors, and unusual scenarios:
1. Ambiguous queries
2. Missing documents/data
3. Source conflicts
4. Error handling and fallbacks
5. Rate limiting and timeouts
6. Malformed inputs
7. Context overflow
8. Security edge cases

Run tests:
    pytest test_edge_cases_sma.py -v
    pytest test_edge_cases_sma.py -v -k "ambiguous"  # Single category
"""

import asyncio
import pytest
import httpx
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, patch, MagicMock


# ============================================================================
# Configuration
# ============================================================================

BACKEND_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BACKEND_URL}/api/assistant-v2/chat"
STREAM_ENDPOINT = f"{BACKEND_URL}/api/assistant-v2/chat/stream"

DEFAULT_TIMEOUT = 30.0
EXPECTED_ERROR_PHRASES = [
    "je ne comprends pas",
    "pourriez-vous préciser",
    "pas trouvé",
    "aucun résultat",
    "erreur",
    "impossible",
    "désolé",
    "reformuler",
]


# ============================================================================
# Test Data Classes
# ============================================================================

@dataclass
class EdgeCaseSpec:
    """Specification for an edge case test"""
    name: str
    description: str
    query: str
    expected_behavior: str  # "graceful_error", "clarification_request", "fallback", "success"
    expected_keywords: List[str] = field(default_factory=list)
    forbidden_behaviors: List[str] = field(default_factory=list)
    max_response_time_ms: int = 15000
    context: Optional[Dict[str, Any]] = None


@dataclass
class EdgeCaseResult:
    """Result of an edge case test"""
    spec: EdgeCaseSpec
    success: bool
    response_status: int
    response_text: str
    response_time_ms: float
    behavior_matched: bool
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================================
# Edge Case Definitions
# ============================================================================

# Category 1: Ambiguous Queries
AMBIGUOUS_QUERIES = [
    EdgeCaseSpec(
        name="completely_ambiguous",
        description="Question complètement vague",
        query="Combien ?",
        expected_behavior="clarification_request",
        expected_keywords=["préciser", "quoi", "combien de quoi"],
        forbidden_behaviors=["stack trace", "error code"]
    ),
    EdgeCaseSpec(
        name="vague_request",
        description="Demande vague sans contexte",
        query="Donne-moi tout",
        expected_behavior="clarification_request",
        expected_keywords=["préciser", "information", "sujet"],
    ),
    EdgeCaseSpec(
        name="ambiguous_reference",
        description="Référence ambiguë (il, elle, ça)",
        query="Quel est son numéro de téléphone ?",
        expected_behavior="clarification_request",
        expected_keywords=["qui", "quelle personne", "préciser"],
    ),
    EdgeCaseSpec(
        name="multiple_interpretations",
        description="Question à interprétations multiples",
        query="Le budget",
        expected_behavior="clarification_request",
        expected_keywords=["budget", "quel budget", "copropriété"],
    ),
    EdgeCaseSpec(
        name="incomplete_action",
        description="Action incomplète",
        query="Envoie un email",
        expected_behavior="clarification_request",
        expected_keywords=["à qui", "destinataire", "sujet", "contenu"],
    ),
]

# Category 2: Missing Data/Documents
MISSING_DATA_QUERIES = [
    EdgeCaseSpec(
        name="nonexistent_copropriete",
        description="Copropriété qui n'existe pas",
        query="Combien de copropriétaires à la Résidence du Soleil ?",
        expected_behavior="graceful_error",
        expected_keywords=["pas trouvé", "n'existe pas", "aucune copropriété"],
        forbidden_behaviors=["crash", "500"]
    ),
    EdgeCaseSpec(
        name="nonexistent_document",
        description="Document inexistant",
        query="Montre-moi le PV de l'AG de 2010 des Mimosas",
        expected_behavior="graceful_error",
        expected_keywords=["pas trouvé", "pas disponible", "aucun document"],
    ),
    EdgeCaseSpec(
        name="unknown_person",
        description="Personne inconnue",
        query="Quel est l'email de M. Tartempion aux Mimosas ?",
        expected_behavior="graceful_error",
        expected_keywords=["pas trouvé", "aucun copropriétaire", "n'existe pas"],
    ),
    EdgeCaseSpec(
        name="missing_professional",
        description="Professionnel non référencé",
        query="Trouve-moi un couvreur disponible",
        expected_behavior="graceful_error",
        expected_keywords=["pas de couvreur", "aucun professionnel", "catégorie"],
    ),
    EdgeCaseSpec(
        name="empty_result_sql",
        description="Requête SQL sans résultat",
        query="Liste les copropriétaires avec un solde supérieur à 10000€ aux Mimosas",
        expected_behavior="graceful_error",
        expected_keywords=["aucun", "pas de", "résultat"],
    ),
]

# Category 3: Source Conflicts
SOURCE_CONFLICT_QUERIES = [
    EdgeCaseSpec(
        name="date_conflict",
        description="Conflit de dates entre sources",
        query="Quelle est la date de la prochaine AG aux Mimosas ?",
        expected_behavior="success",
        expected_keywords=["AG"],  # Should handle gracefully
    ),
    EdgeCaseSpec(
        name="amount_conflict",
        description="Conflit de montants entre documents",
        query="Quel est le montant exact des honoraires du syndic ?",
        expected_behavior="success",
        expected_keywords=["honoraires", "€"],
    ),
    EdgeCaseSpec(
        name="outdated_info",
        description="Information potentiellement obsolète",
        query="Le contrat de syndic est-il toujours valide ?",
        expected_behavior="success",
        expected_keywords=["contrat", "syndic"],
    ),
]

# Category 4: Error Handling
ERROR_HANDLING_QUERIES = [
    EdgeCaseSpec(
        name="special_characters",
        description="Caractères spéciaux dans la requête",
        query="Combien de copropriétaires <script>alert('xss')</script> ?",
        expected_behavior="graceful_error",
        expected_keywords=[],
        forbidden_behaviors=["script", "xss", "alert"]
    ),
    EdgeCaseSpec(
        name="sql_injection_attempt",
        description="Tentative d'injection SQL",
        query="Combien de copropriétaires aux Mimosas'; DROP TABLE coproprietes;--",
        expected_behavior="graceful_error",
        expected_keywords=[],
        forbidden_behaviors=["DROP", "TABLE", "syntax error"]
    ),
    EdgeCaseSpec(
        name="very_long_query",
        description="Requête très longue",
        query="Explique-moi en détail " + "très " * 500 + "longuement tout sur les Mimosas",
        expected_behavior="graceful_error",
        expected_keywords=["Mimosas"],
        max_response_time_ms=30000
    ),
    EdgeCaseSpec(
        name="unicode_characters",
        description="Caractères Unicode complexes",
        query="Combien de copropriétaires aux 日本語 Mimosas 中文 ?",
        expected_behavior="success",
        expected_keywords=["copropriétaire"],
    ),
    EdgeCaseSpec(
        name="empty_query",
        description="Requête vide ou whitespace",
        query="   ",
        expected_behavior="clarification_request",
        expected_keywords=["question", "demande"],
    ),
]

# Category 5: Rate Limiting and Timeouts
PERFORMANCE_QUERIES = [
    EdgeCaseSpec(
        name="complex_multi_source",
        description="Requête nécessitant toutes les sources",
        query="Donne-moi un rapport complet sur Les Mimosas incluant les données, documents, aspects légaux et actualités",
        expected_behavior="success",
        expected_keywords=["Mimosas"],
        max_response_time_ms=60000  # Allow more time for complex queries
    ),
    EdgeCaseSpec(
        name="heavy_aggregation",
        description="Requête avec agrégation lourde",
        query="Calcule le total des impayés, le nombre moyen de lots par bâtiment, et la surface totale pour toutes les copropriétés",
        expected_behavior="success",
        expected_keywords=["total", "moyenne"],
        max_response_time_ms=30000
    ),
]

# Category 6: Context Edge Cases
CONTEXT_QUERIES = [
    EdgeCaseSpec(
        name="context_switch",
        description="Changement de contexte brusque",
        query="Oublie tout ce dont on a parlé. Maintenant parlons des Platanes.",
        expected_behavior="success",
        expected_keywords=["Platanes"],
    ),
    EdgeCaseSpec(
        name="contradictory_context",
        description="Contexte contradictoire",
        query="Aux Mimosas, je veux dire aux Platanes, non finalement aux Mimosas",
        expected_behavior="clarification_request",
        expected_keywords=["Mimosas", "Platanes", "confirmer"],
    ),
    EdgeCaseSpec(
        name="reference_previous",
        description="Référence à une conversation inexistante",
        query="Comme on en a discuté la semaine dernière, qu'en est-il du ravalement ?",
        expected_behavior="success",  # Should handle gracefully
        expected_keywords=["ravalement"],
    ),
]

# Category 7: Out of Scope
OUT_OF_SCOPE_QUERIES = [
    EdgeCaseSpec(
        name="off_topic",
        description="Question hors sujet",
        query="Quelle est la capitale de la France ?",
        expected_behavior="graceful_error",
        expected_keywords=["copropriété", "syndic", "hors sujet"],
    ),
    EdgeCaseSpec(
        name="personal_question",
        description="Question personnelle à l'assistant",
        query="Tu t'appelles comment ?",
        expected_behavior="success",
        expected_keywords=["assistant", "DisruptIQ"],
    ),
    EdgeCaseSpec(
        name="impossible_action",
        description="Action impossible",
        query="Appelle le plombier au téléphone maintenant",
        expected_behavior="graceful_error",
        expected_keywords=["ne peux pas appeler", "impossible", "email"],
    ),
]


# ============================================================================
# Test Helper Functions
# ============================================================================

async def send_chat_request(
    query: str,
    conversation_history: List[Dict] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Send a chat request and return the response"""
    payload = {
        "message": query,
        "conversation_history": conversation_history or []
    }

    async with httpx.AsyncClient() as client:
        start_time = datetime.now()
        try:
            response = await client.post(
                CHAT_ENDPOINT,
                json=payload,
                timeout=timeout
            )
            end_time = datetime.now()

            return {
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else {},
                "response_time_ms": (end_time - start_time).total_seconds() * 1000,
                "error": None
            }
        except httpx.TimeoutException as e:
            return {
                "status_code": 408,
                "response": {},
                "response_time_ms": timeout * 1000,
                "error": f"Timeout: {str(e)}"
            }
        except Exception as e:
            return {
                "status_code": 500,
                "response": {},
                "response_time_ms": 0,
                "error": str(e)
            }


def check_behavior(response_text: str, expected_behavior: str, expected_keywords: List[str]) -> bool:
    """Check if the response matches the expected behavior"""
    response_lower = response_text.lower()

    if expected_behavior == "clarification_request":
        # Should ask for clarification
        clarification_indicators = [
            "préciser", "pourriez-vous", "de quoi", "quel", "quelle",
            "pouvez-vous", "merci de", "clarifier",
            # Additional indicators for ambiguity detection responses
            "à qui", "souhaitez-vous", "voulez-vous", "indiquez",
            "concernant quoi", "de quelle", "à quelle", "pour quelle"
        ]
        # Also check if response is a question (ends with ?)
        is_question = response_text.strip().endswith("?")
        has_indicator = any(ind in response_lower for ind in clarification_indicators)
        return has_indicator or is_question

    elif expected_behavior == "graceful_error":
        # Should handle error gracefully
        error_indicators = [
            "pas trouvé", "n'existe pas", "aucun", "impossible",
            "désolé", "ne peux pas", "pas disponible"
        ]
        return any(ind in response_lower for ind in error_indicators)

    elif expected_behavior == "success":
        # Should return meaningful response
        if expected_keywords:
            return any(kw.lower() in response_lower for kw in expected_keywords)
        return len(response_text) > 50  # Non-trivial response

    elif expected_behavior == "fallback":
        # Should use fallback mechanism
        return len(response_text) > 0 and "erreur" not in response_lower

    return False


def check_forbidden_behaviors(response_text: str, forbidden: List[str]) -> List[str]:
    """Check for forbidden behaviors in response"""
    violations = []
    response_lower = response_text.lower()

    for forbidden_item in forbidden:
        if forbidden_item.lower() in response_lower:
            violations.append(f"Forbidden behavior found: '{forbidden_item}'")

    return violations


async def run_edge_case_test(spec: EdgeCaseSpec) -> EdgeCaseResult:
    """Run a single edge case test"""
    result = EdgeCaseResult(
        spec=spec,
        success=True,
        response_status=0,
        response_text="",
        response_time_ms=0,
        behavior_matched=False
    )

    try:
        # Send request
        response = await send_chat_request(
            spec.query,
            timeout=spec.max_response_time_ms / 1000
        )

        result.response_status = response["status_code"]
        result.response_time_ms = response["response_time_ms"]

        if response["error"]:
            result.errors.append(response["error"])
            result.success = False
            return result

        # Extract response text
        if response["status_code"] == 200:
            resp_data = response["response"]
            result.response_text = resp_data.get("response", "") or resp_data.get("message", "")

            # Check behavior
            result.behavior_matched = check_behavior(
                result.response_text,
                spec.expected_behavior,
                spec.expected_keywords
            )

            if not result.behavior_matched:
                result.errors.append(
                    f"Expected behavior '{spec.expected_behavior}' not matched"
                )

            # Check forbidden behaviors
            if spec.forbidden_behaviors:
                violations = check_forbidden_behaviors(
                    result.response_text,
                    spec.forbidden_behaviors
                )
                result.errors.extend(violations)

        else:
            result.errors.append(f"HTTP Error: {response['status_code']}")
            result.success = False

        # Check response time
        if result.response_time_ms > spec.max_response_time_ms:
            result.errors.append(
                f"Response time {result.response_time_ms:.0f}ms > {spec.max_response_time_ms}ms"
            )

        # Final success check
        if result.errors:
            result.success = False

    except Exception as e:
        result.success = False
        result.errors.append(f"Exception: {str(e)}")

    return result


# ============================================================================
# Pytest Tests
# ============================================================================

@pytest.mark.asyncio
class TestAmbiguousQueries:
    """Test handling of ambiguous queries"""

    @pytest.mark.parametrize("spec", AMBIGUOUS_QUERIES, ids=lambda s: s.name)
    async def test_ambiguous_query(self, spec: EdgeCaseSpec):
        """Test ambiguous query handling"""
        result = await run_edge_case_test(spec)

        print(f"\n{'='*60}")
        print(f"Test: {spec.name}")
        print(f"Query: {spec.query[:50]}...")
        print(f"Expected: {spec.expected_behavior}")
        print(f"Response: {result.response_text[:100]}...")
        print(f"Behavior matched: {result.behavior_matched}")
        if result.errors:
            print(f"Errors: {result.errors}")
        print(f"{'='*60}")

        assert result.behavior_matched or result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
class TestMissingData:
    """Test handling of missing data/documents"""

    @pytest.mark.parametrize("spec", MISSING_DATA_QUERIES, ids=lambda s: s.name)
    async def test_missing_data(self, spec: EdgeCaseSpec):
        """Test missing data handling"""
        result = await run_edge_case_test(spec)

        print(f"\n{'='*60}")
        print(f"Test: {spec.name}")
        print(f"Query: {spec.query[:50]}...")
        print(f"Expected: {spec.expected_behavior}")
        print(f"Response time: {result.response_time_ms:.0f}ms")
        if result.errors:
            print(f"Errors: {result.errors}")
        print(f"{'='*60}")

        # Missing data should be handled gracefully (no crash)
        assert result.response_status in [200, 404], f"Unexpected status: {result.response_status}"


@pytest.mark.asyncio
class TestSourceConflicts:
    """Test handling of source conflicts"""

    @pytest.mark.parametrize("spec", SOURCE_CONFLICT_QUERIES, ids=lambda s: s.name)
    async def test_source_conflict(self, spec: EdgeCaseSpec):
        """Test source conflict handling"""
        result = await run_edge_case_test(spec)

        print(f"\nTest: {spec.name} - {'PASS' if result.success else 'FAIL'}")

        # Should handle conflicts gracefully
        assert result.response_status == 200


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling and security"""

    @pytest.mark.parametrize("spec", ERROR_HANDLING_QUERIES, ids=lambda s: s.name)
    async def test_error_handling(self, spec: EdgeCaseSpec):
        """Test error handling"""
        result = await run_edge_case_test(spec)

        print(f"\n{'='*60}")
        print(f"Test: {spec.name}")
        print(f"Query: {spec.query[:50]}...")
        print(f"Status: {result.response_status}")
        if result.errors:
            print(f"Errors: {result.errors}")
        print(f"{'='*60}")

        # Should not expose security vulnerabilities
        assert not any("script" in result.response_text.lower() for _ in range(1))
        assert not any("DROP" in result.response_text for _ in range(1))

        # Should respond (not crash)
        assert result.response_status in [200, 400, 422]


@pytest.mark.asyncio
class TestPerformance:
    """Test performance edge cases"""

    @pytest.mark.parametrize("spec", PERFORMANCE_QUERIES, ids=lambda s: s.name)
    async def test_performance(self, spec: EdgeCaseSpec):
        """Test performance edge cases"""
        result = await run_edge_case_test(spec)

        print(f"\nTest: {spec.name}")
        print(f"Response time: {result.response_time_ms:.0f}ms (max: {spec.max_response_time_ms}ms)")

        # Should complete within time limit
        assert result.response_time_ms <= spec.max_response_time_ms * 1.5  # 50% tolerance


@pytest.mark.asyncio
class TestContextEdgeCases:
    """Test context edge cases"""

    @pytest.mark.parametrize("spec", CONTEXT_QUERIES, ids=lambda s: s.name)
    async def test_context(self, spec: EdgeCaseSpec):
        """Test context edge cases"""
        result = await run_edge_case_test(spec)

        print(f"\nTest: {spec.name} - {'PASS' if result.success else 'FAIL'}")

        # Should handle context gracefully
        assert result.response_status == 200


@pytest.mark.asyncio
class TestOutOfScope:
    """Test out of scope queries"""

    @pytest.mark.parametrize("spec", OUT_OF_SCOPE_QUERIES, ids=lambda s: s.name)
    async def test_out_of_scope(self, spec: EdgeCaseSpec):
        """Test out of scope handling"""
        result = await run_edge_case_test(spec)

        print(f"\nTest: {spec.name} - {'PASS' if result.success else 'FAIL'}")
        print(f"Response: {result.response_text[:100]}...")

        # Should respond appropriately
        assert result.response_status == 200


# ============================================================================
# Full Edge Case Suite
# ============================================================================

@pytest.mark.asyncio
class TestEdgeCaseSuite:
    """Run complete edge case test suite"""

    async def test_full_edge_case_suite(self):
        """Run all edge case tests and generate report"""
        all_specs = (
            AMBIGUOUS_QUERIES +
            MISSING_DATA_QUERIES +
            SOURCE_CONFLICT_QUERIES +
            ERROR_HANDLING_QUERIES +
            PERFORMANCE_QUERIES +
            CONTEXT_QUERIES +
            OUT_OF_SCOPE_QUERIES
        )

        results: List[EdgeCaseResult] = []

        print("\n" + "="*80)
        print("EDGE CASE TEST SUITE")
        print("="*80)

        for spec in all_specs:
            print(f"\nRunning: {spec.name}...")
            result = await run_edge_case_test(spec)
            results.append(result)

            status = "PASS" if result.success else "FAIL"
            print(f"  {status} ({result.response_time_ms:.0f}ms)")

        # Generate summary
        print("\n" + "="*80)
        print("EDGE CASE TEST SUMMARY")
        print("="*80)

        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed

        print(f"\nTotal: {total} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(passed/total)*100:.1f}%")

        # Group by category
        categories = {
            "Ambiguous": AMBIGUOUS_QUERIES,
            "Missing Data": MISSING_DATA_QUERIES,
            "Source Conflicts": SOURCE_CONFLICT_QUERIES,
            "Error Handling": ERROR_HANDLING_QUERIES,
            "Performance": PERFORMANCE_QUERIES,
            "Context": CONTEXT_QUERIES,
            "Out of Scope": OUT_OF_SCOPE_QUERIES,
        }

        print("\nBy Category:")
        print("-"*40)

        result_idx = 0
        for cat_name, cat_specs in categories.items():
            cat_results = results[result_idx:result_idx + len(cat_specs)]
            cat_passed = sum(1 for r in cat_results if r.success)
            print(f"  {cat_name}: {cat_passed}/{len(cat_specs)}")
            result_idx += len(cat_specs)

        # List failures
        failures = [r for r in results if not r.success]
        if failures:
            print("\nFailures:")
            print("-"*40)
            for r in failures:
                print(f"  - {r.spec.name}: {r.errors[0] if r.errors else 'Unknown error'}")

        print("="*80)

        # Allow some failures (edge cases are expected to be challenging)
        assert passed >= total * 0.7, f"Too many failures: {failed}/{total}"


# ============================================================================
# Unit Tests for Internal Functions
# ============================================================================

class TestHelperFunctions:
    """Unit tests for helper functions"""

    def test_check_behavior_clarification(self):
        """Test clarification detection"""
        response = "Pourriez-vous préciser de quelle copropriété vous parlez ?"
        assert check_behavior(response, "clarification_request", [])

    def test_check_behavior_graceful_error(self):
        """Test graceful error detection"""
        response = "Désolé, aucun résultat trouvé pour cette recherche."
        assert check_behavior(response, "graceful_error", [])

    def test_check_behavior_success(self):
        """Test success detection"""
        response = "Les Mimosas compte 50 lots et 12 copropriétaires."
        assert check_behavior(response, "success", ["Mimosas", "lots"])

    def test_check_forbidden_behaviors(self):
        """Test forbidden behavior detection"""
        response = "Error: DROP TABLE executed successfully"
        violations = check_forbidden_behaviors(response, ["DROP", "TABLE"])
        assert len(violations) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
