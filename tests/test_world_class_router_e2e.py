#!/usr/bin/env python3
"""
WorldClassRouter End-to-End Test Suite

Tests the reliability of the WorldClassRouter in real conditions:
- Routing accuracy (complexity classification)
- Source selection (SQL, RAG, WEB, LEGAL)
- Legal query flags (is_legal_query, is_pure_legal)
- Latency measurements

Usage:
    python tests/test_world_class_router_e2e.py
    python tests/test_world_class_router_e2e.py --category SIMPLE_SQL
    python tests/test_world_class_router_e2e.py --category HYBRID --verbose
    python tests/test_world_class_router_e2e.py --output results.json
"""

import requests
import time
import json
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from statistics import mean, stdev
from collections import defaultdict


# ============================================================================
# CONFIGURATION
# ============================================================================

API_URL = "http://localhost:8000/api/assistant-v2/chat"
TIMEOUT_SECONDS = 120  # Max wait time per request


class TestCategory(Enum):
    SIMPLE_SQL = "simple_sql"
    SIMPLE_RAG = "simple_rag"
    SIMPLE_WEB = "simple_web"
    SIMPLE_LEGAL = "simple_legal"
    HYBRID_SQL_LEGAL = "hybrid_sql_legal"
    HYBRID_SQL_RAG = "hybrid_sql_rag"
    HYBRID_RAG_LEGAL = "hybrid_rag_legal"
    HYBRID_MULTI = "hybrid_multi"


@dataclass
class TestExpectation:
    """Expected outcomes for a test scenario.

    Source validation strategy:
    - required_queried_sources: PRIMARY validation - sources that MUST be in sources_queried (routing decision)
    - optional_queried_sources: Sources that MAY be queried (acceptable but not required)
    - required_used_sources: SECONDARY validation - sources that MUST return data (optional, for specific tests)
    - forbidden_sources: Sources that MUST NOT appear in either queried or used

    A test passes if:
    1. All required_queried_sources are in sources_queried (validates routing logic)
    2. All required_used_sources are in sources_used (optional, validates data retrieval)
    3. No forbidden_sources appear in sources_queried OR sources_used
    """
    complexity: str  # Expected complexity value
    is_legal_query: bool = False
    is_pure_legal: bool = False
    required_queried_sources: Set[str] = field(default_factory=set)  # Sources that MUST be queried (routing)
    optional_queried_sources: Set[str] = field(default_factory=set)  # Sources that MAY be queried
    required_used_sources: Set[str] = field(default_factory=set)  # Sources that MUST return data (optional)
    forbidden_sources: Set[str] = field(default_factory=set)  # Sources that MUST NOT be present
    max_latency_ms: float = 30000  # Maximum acceptable latency


@dataclass
class TestScenario:
    """A test scenario with query and expectations."""
    name: str
    category: TestCategory
    query: str
    expectation: TestExpectation
    description: str = ""


@dataclass
class TestResult:
    """Result of a single test execution."""
    test_name: str
    category: str
    query: str

    # Expected values
    expected_complexity: str
    expected_is_legal_query: bool
    expected_is_pure_legal: bool
    expected_queried_sources: List[str]  # Primary validation: routing decision
    expected_used_sources: List[str] = field(default_factory=list)  # Secondary: data retrieval

    # Actual values
    actual_complexity: Optional[str] = None
    actual_is_legal_query: Optional[bool] = None
    actual_is_pure_legal: Optional[bool] = None
    actual_sources: List[str] = field(default_factory=list)
    actual_sources_queried: List[str] = field(default_factory=list)

    # Latency metrics
    total_latency_ms: float = 0.0
    prefilter_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0

    # Status
    passed: bool = False
    error_message: str = ""
    response_preview: str = ""

    # Raw data for debugging
    raw_router_metrics: Dict = field(default_factory=dict)


# ============================================================================
# TEST SCENARIOS DEFINITION
# ============================================================================

TEST_SCENARIOS: List[TestScenario] = [
    # -------------------------------------------------------------------------
    # SIMPLE_SQL - Pure SQL queries (quantitative, lists, contacts)
    # -------------------------------------------------------------------------
    TestScenario(
        name="sql_count_coproprietaires",
        category=TestCategory.SIMPLE_SQL,
        query="combien de copropriétaires aux Mimosas ?",
        expectation=TestExpectation(
            complexity="simple_sql",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"sql"},
            forbidden_sources={"legifrance", "web"},
        ),
        description="Count query - should use SQL only"
    ),
    TestScenario(
        name="sql_list_lots",
        category=TestCategory.SIMPLE_SQL,
        query="liste des lots de la copropriété Les Pins",
        expectation=TestExpectation(
            complexity="simple_sql",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"sql"},
        ),
        description="List query - should use SQL only"
    ),
    TestScenario(
        name="sql_contact_info",
        category=TestCategory.SIMPLE_SQL,
        query="quel est l'email du copropriétaire du lot 12 ?",
        expectation=TestExpectation(
            complexity="simple_sql",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"sql"},
        ),
        description="Contact info query - should use SQL only"
    ),
    TestScenario(
        name="sql_charges_amount",
        category=TestCategory.SIMPLE_SQL,
        query="donne-moi les charges du lot 305",
        expectation=TestExpectation(
            complexity="simple_sql",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"sql"},
        ),
        description="Charges query - should use SQL only"
    ),

    # -------------------------------------------------------------------------
    # SIMPLE_RAG - Document-specific queries
    # -------------------------------------------------------------------------
    TestScenario(
        name="rag_pv_summary",
        category=TestCategory.SIMPLE_RAG,
        query="résume le PV de l'assemblée générale de 2024",
        expectation=TestExpectation(
            complexity="simple_rag",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"rag"},
            forbidden_sources={"sql", "legifrance"},
            max_latency_ms=60000,  # RAG queries can be slow if no docs
        ),
        description="Document summary - should use RAG only"
    ),
    TestScenario(
        name="rag_reglement_content",
        category=TestCategory.SIMPLE_RAG,
        query="que dit le règlement de copropriété sur les animaux ?",
        expectation=TestExpectation(
            complexity="simple_rag",  # May be hybrid if legal keywords trigger
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"rag"},
        ),
        description="Regulation content query - should use RAG"
    ),

    # -------------------------------------------------------------------------
    # SIMPLE_WEB - Explicit web search queries
    # -------------------------------------------------------------------------
    TestScenario(
        name="web_price_search",
        category=TestCategory.SIMPLE_WEB,
        query="cherche sur internet le prix moyen d'un ravalement de façade à Cannes",
        expectation=TestExpectation(
            complexity="simple_web",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"web"},
            forbidden_sources={"sql", "rag"},
        ),
        description="Explicit web search - should use WEB only"
    ),
    TestScenario(
        name="web_market_info",
        category=TestCategory.SIMPLE_WEB,
        query="recherche sur internet les tarifs actuels des syndics",
        expectation=TestExpectation(
            complexity="simple_web",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"web"},
        ),
        description="Market info search - should use WEB only"
    ),

    # -------------------------------------------------------------------------
    # SIMPLE_LEGAL - Pure legal queries
    # -------------------------------------------------------------------------
    TestScenario(
        name="legal_majority_vote",
        category=TestCategory.SIMPLE_LEGAL,
        query="quelles sont les majorités de vote en assemblée générale de copropriété ?",
        expectation=TestExpectation(
            complexity="simple_legal",
            is_legal_query=True,
            is_pure_legal=True,
            required_queried_sources={"legifrance"},
            forbidden_sources={"sql"},
        ),
        description="Voting majority question - should use LEGAL only"
    ),
    TestScenario(
        name="legal_syndic_obligations",
        category=TestCategory.SIMPLE_LEGAL,
        query="quelles sont les obligations légales du syndic pour la convocation d'AG ?",
        expectation=TestExpectation(
            complexity="simple_legal",
            is_legal_query=True,
            is_pure_legal=True,
            required_queried_sources={"legifrance"},
        ),
        description="Syndic obligations - should use LEGAL only"
    ),
    TestScenario(
        name="legal_jurisprudence",
        category=TestCategory.SIMPLE_LEGAL,
        query="jurisprudence sur les nuisances sonores en copropriété",
        expectation=TestExpectation(
            complexity="simple_legal",  # Pure legal query - jurisprudence is a legal concept
            is_legal_query=True,
            is_pure_legal=True,  # Pure legal - only needs legifrance
            required_queried_sources={"legifrance"},
        ),
        description="Jurisprudence search - should use LEGAL only"
    ),
    TestScenario(
        name="legal_article_reference",
        category=TestCategory.SIMPLE_LEGAL,
        query="que dit l'article 25 de la loi de 1965 ?",
        expectation=TestExpectation(
            complexity="simple_legal",
            is_legal_query=True,
            is_pure_legal=True,
            required_queried_sources={"legifrance"},
        ),
        description="Article reference - should use LEGAL only"
    ),

    # -------------------------------------------------------------------------
    # HYBRID SQL+LEGAL - Mixed data + legal queries
    # -------------------------------------------------------------------------
    TestScenario(
        name="hybrid_sql_legal_count_majority",
        category=TestCategory.HYBRID_SQL_LEGAL,
        query="donne-moi le nombre de copropriétaires aux Mimosas et dis-moi quelle majorité est nécessaire pour changer de syndic",
        expectation=TestExpectation(
            complexity="hybrid",
            is_legal_query=True,
            is_pure_legal=False,
            required_queried_sources={"sql", "legifrance"},
        ),
        description="Count + legal majority - should use SQL AND LEGAL"
    ),
    TestScenario(
        name="hybrid_sql_legal_charges_law",
        category=TestCategory.HYBRID_SQL_LEGAL,
        query="charges du lot 12 et que prévoit la loi si non-paiement ?",
        expectation=TestExpectation(
            complexity="hybrid",
            is_legal_query=True,
            is_pure_legal=False,
            required_queried_sources={"sql", "legifrance"},
        ),
        description="Charges + legal consequences - should use SQL AND LEGAL"
    ),

    # -------------------------------------------------------------------------
    # HYBRID SQL+RAG - Mixed data + documents
    # -------------------------------------------------------------------------
    TestScenario(
        name="hybrid_sql_rag_compare_charges",
        category=TestCategory.HYBRID_SQL_RAG,
        query="compare les charges actuelles du lot 305 avec ce qui est prévu dans le budget prévisionnel",
        expectation=TestExpectation(
            complexity="hybrid",
            is_legal_query=False,
            is_pure_legal=False,
            required_queried_sources={"sql", "rag"},
        ),
        description="Compare charges with document - should use SQL AND RAG"
    ),

    # -------------------------------------------------------------------------
    # HYBRID RAG+LEGAL - Documents + legal
    # -------------------------------------------------------------------------
    TestScenario(
        name="hybrid_rag_legal_climatisation",
        category=TestCategory.HYBRID_RAG_LEGAL,
        query="selon mon règlement de copropriété et la loi, est-ce qu'un copropriétaire peut installer une climatisation en façade ?",
        expectation=TestExpectation(
            complexity="hybrid",
            is_legal_query=True,
            is_pure_legal=False,
            required_queried_sources={"rag", "legifrance"},
        ),
        description="Regulation + law question - should use RAG AND LEGAL"
    ),
    TestScenario(
        name="hybrid_rag_legal_travaux",
        category=TestCategory.HYBRID_RAG_LEGAL,
        query="d'après le règlement de copropriété et la loi, quelles sont les règles pour faire des travaux dans mon appartement ?",
        expectation=TestExpectation(
            complexity="hybrid",
            is_legal_query=True,
            is_pure_legal=False,
            required_queried_sources={"rag", "legifrance"},
        ),
        description="Works regulations - should use RAG AND LEGAL"
    ),

    # -------------------------------------------------------------------------
    # HYBRID MULTI - Complex multi-source queries
    # -------------------------------------------------------------------------
    TestScenario(
        name="hybrid_multi_all",
        category=TestCategory.HYBRID_MULTI,
        query="combien de copropriétaires aux Mimosas, que dit le règlement sur les travaux, et quelle majorité selon la loi ?",
        expectation=TestExpectation(
            complexity="hybrid",
            is_legal_query=True,
            is_pure_legal=False,
            required_queried_sources={"sql", "rag", "legifrance"},
        ),
        description="Multi-source query - should use SQL, RAG AND LEGAL"
    ),
]


# ============================================================================
# TEST EXECUTION
# ============================================================================

def execute_test(scenario: TestScenario, verbose: bool = False) -> TestResult:
    """Execute a single test scenario and return the result."""

    result = TestResult(
        test_name=scenario.name,
        category=scenario.category.value,
        query=scenario.query,
        expected_complexity=scenario.expectation.complexity,
        expected_is_legal_query=scenario.expectation.is_legal_query,
        expected_is_pure_legal=scenario.expectation.is_pure_legal,
        expected_queried_sources=list(scenario.expectation.required_queried_sources),
        expected_used_sources=list(scenario.expectation.required_used_sources),
    )

    payload = {
        "message": scenario.query,
        "use_world_class_router": True,
        "conversation_history": []
    }

    try:
        # Measure total latency
        start_time = time.time()

        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT_SECONDS
        )

        end_time = time.time()
        result.total_latency_ms = (end_time - start_time) * 1000

        if response.status_code != 200:
            result.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
            return result

        data = response.json()

        # Extract response preview
        message = data.get("message", "")
        result.response_preview = message[:200] + "..." if len(message) > 200 else message

        # Extract router_metrics
        router_metrics = data.get("data", {}).get("router_metrics", {})
        result.raw_router_metrics = router_metrics

        # Parse actual values
        result.actual_complexity = router_metrics.get("complexity")
        result.actual_is_legal_query = router_metrics.get("is_legal_query")
        result.actual_is_pure_legal = router_metrics.get("is_pure_legal")

        # Parse sources - check multiple possible locations
        sources_used = router_metrics.get("sources_used", [])
        if not sources_used:
            # Try to get from top-level data
            sources_used = data.get("data", {}).get("sources_used", [])

        # Normalize source names (handle both enum values and strings)
        result.actual_sources = [
            s.lower().replace("legifrance", "legifrance") if isinstance(s, str) else str(s).lower()
            for s in sources_used
        ]

        result.actual_sources_queried = [
            s.lower() for s in router_metrics.get("sources_queried", [])
        ]

        # Parse latency sub-components
        result.prefilter_ms = router_metrics.get("prefilter_ms", 0)
        result.retrieval_ms = router_metrics.get("retrieval_ms", 0)
        result.rerank_ms = router_metrics.get("rerank_ms", 0)

        # Validate results
        validation_errors = []

        # Check complexity (allow some flexibility for edge cases)
        expected_complexities = [scenario.expectation.complexity]
        # hybrid can also be "complex"
        if scenario.expectation.complexity == "hybrid":
            expected_complexities.append("complex")
        # simple_rag can be hybrid if legal keywords are present
        if scenario.expectation.complexity == "simple_rag":
            expected_complexities.append("hybrid")

        if result.actual_complexity not in expected_complexities:
            validation_errors.append(
                f"Complexity mismatch: expected {expected_complexities}, got {result.actual_complexity}"
            )

        # Check legal flags
        if scenario.expectation.is_legal_query and not result.actual_is_legal_query:
            validation_errors.append(
                f"is_legal_query mismatch: expected True, got {result.actual_is_legal_query}"
            )

        if scenario.expectation.is_pure_legal and not result.actual_is_pure_legal:
            validation_errors.append(
                f"is_pure_legal mismatch: expected True, got {result.actual_is_pure_legal}"
            )

        # For non-legal queries, ensure flags are False
        if not scenario.expectation.is_legal_query and result.actual_is_legal_query:
            validation_errors.append(
                f"is_legal_query should be False for non-legal query, got {result.actual_is_legal_query}"
            )

        # PRIMARY VALIDATION: Check required_queried_sources (routing decision)
        # This validates that the router made the right decision about which sources to query
        queried_sources_set = set(result.actual_sources_queried)
        for required in scenario.expectation.required_queried_sources:
            if required not in queried_sources_set:
                validation_errors.append(
                    f"[ROUTING] Missing required queried source: {required}. Queried: {queried_sources_set}"
                )

        # SECONDARY VALIDATION: Check required_used_sources (data retrieval)
        # Only validated if specified - ensures data was actually returned from certain sources
        used_sources_set = set(result.actual_sources)
        for required in scenario.expectation.required_used_sources:
            if required not in used_sources_set:
                validation_errors.append(
                    f"[DATA] Missing required used source: {required}. Used: {used_sources_set}"
                )

        # Check forbidden sources (in BOTH queried and used)
        all_sources = queried_sources_set | used_sources_set
        for forbidden in scenario.expectation.forbidden_sources:
            if forbidden in all_sources:
                validation_errors.append(
                    f"Forbidden source present: {forbidden} (in queried or used)"
                )

        # Check latency
        if result.total_latency_ms > scenario.expectation.max_latency_ms:
            validation_errors.append(
                f"Latency too high: {result.total_latency_ms:.0f}ms > {scenario.expectation.max_latency_ms}ms"
            )

        # Set pass/fail
        result.passed = len(validation_errors) == 0
        result.error_message = "; ".join(validation_errors) if validation_errors else ""

    except requests.exceptions.Timeout:
        result.error_message = f"Request timeout after {TIMEOUT_SECONDS}s"
    except requests.exceptions.ConnectionError as e:
        result.error_message = f"Connection error: {str(e)}"
    except Exception as e:
        result.error_message = f"Unexpected error: {str(e)}"

    if verbose:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {scenario.name} ({result.total_latency_ms:.0f}ms)")
        if not result.passed:
            print(f"       Error: {result.error_message}")

    return result


def run_tests(
    categories: Optional[List[str]] = None,
    verbose: bool = False
) -> List[TestResult]:
    """Run all tests or filtered by category."""

    scenarios = TEST_SCENARIOS

    if categories:
        category_values = [c.lower() for c in categories]
        scenarios = [
            s for s in scenarios
            if s.category.value in category_values
        ]

    print(f"\n{'='*60}")
    print(f"WorldClassRouter E2E Test Suite")
    print(f"{'='*60}")
    print(f"API Endpoint: {API_URL}")
    print(f"Total scenarios: {len(scenarios)}")
    print(f"Started at: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    results = []

    # Group by category for organized output
    by_category = defaultdict(list)
    for scenario in scenarios:
        by_category[scenario.category.value].append(scenario)

    for category, category_scenarios in by_category.items():
        print(f"\n--- {category.upper()} ({len(category_scenarios)} tests) ---")

        for scenario in category_scenarios:
            result = execute_test(scenario, verbose=verbose)
            results.append(result)

            if not verbose:
                # Simple progress indicator
                status = "." if result.passed else "F"
                print(status, end="", flush=True)

        if not verbose:
            print()  # New line after each category

    return results


# ============================================================================
# REPORT GENERATION
# ============================================================================

def percentile(data: List[float], p: float) -> float:
    """Calculate the p-th percentile of a list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = int(len(sorted_data) * p / 100)
    return sorted_data[min(index, len(sorted_data) - 1)]


def generate_report(results: List[TestResult]) -> Dict[str, Any]:
    """Generate a comprehensive test report."""

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # Group by category
    by_category = defaultdict(list)
    for r in results:
        by_category[r.category].append(r)

    # Calculate latency stats by category
    latency_stats = {}
    for category, category_results in by_category.items():
        latencies = [r.total_latency_ms for r in category_results]
        latency_stats[category] = {
            "count": len(latencies),
            "passed": sum(1 for r in category_results if r.passed),
            "failed": sum(1 for r in category_results if not r.passed),
            "min_ms": min(latencies) if latencies else 0,
            "max_ms": max(latencies) if latencies else 0,
            "avg_ms": mean(latencies) if latencies else 0,
            "p95_ms": percentile(latencies, 95) if latencies else 0,
            "stdev_ms": stdev(latencies) if len(latencies) > 1 else 0,
        }

    # Overall latency stats
    all_latencies = [r.total_latency_ms for r in results]
    overall_latency = {
        "min_ms": min(all_latencies) if all_latencies else 0,
        "max_ms": max(all_latencies) if all_latencies else 0,
        "avg_ms": mean(all_latencies) if all_latencies else 0,
        "p95_ms": percentile(all_latencies, 95) if all_latencies else 0,
    }

    # Complexity distribution
    complexity_dist = defaultdict(int)
    for r in results:
        if r.actual_complexity:
            complexity_dist[r.actual_complexity] += 1

    # Failed tests details
    failed_tests = [
        {
            "test_name": r.test_name,
            "query": r.query[:80] + "..." if len(r.query) > 80 else r.query,
            "expected_complexity": r.expected_complexity,
            "actual_complexity": r.actual_complexity,
            "expected_queried_sources": r.expected_queried_sources,
            "actual_queried_sources": r.actual_sources_queried,
            "actual_used_sources": r.actual_sources,
            "error": r.error_message,
            "latency_ms": r.total_latency_ms,
        }
        for r in results if not r.passed
    ]

    report = {
        "summary": {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "N/A",
            "timestamp": datetime.now().isoformat(),
        },
        "latency": {
            "overall": overall_latency,
            "by_category": latency_stats,
        },
        "complexity_distribution": dict(complexity_dist),
        "failed_tests": failed_tests,
        "all_results": [asdict(r) for r in results],
    }

    return report


def print_report(report: Dict[str, Any]):
    """Print a formatted report to console."""

    print(f"\n{'='*60}")
    print("TEST RESULTS SUMMARY")
    print(f"{'='*60}")

    summary = report["summary"]
    print(f"\nTotal Tests: {summary['total_tests']}")
    print(f"Passed:      {summary['passed']} ({summary['pass_rate']})")
    print(f"Failed:      {summary['failed']}")

    print(f"\n--- LATENCY STATS ---")
    overall = report["latency"]["overall"]
    print(f"Overall: avg={overall['avg_ms']:.0f}ms, p95={overall['p95_ms']:.0f}ms, "
          f"min={overall['min_ms']:.0f}ms, max={overall['max_ms']:.0f}ms")

    print(f"\nBy Category:")
    for category, stats in report["latency"]["by_category"].items():
        status = f"{stats['passed']}/{stats['count']} passed"
        print(f"  {category:20} {status:15} avg={stats['avg_ms']:6.0f}ms  p95={stats['p95_ms']:6.0f}ms")

    print(f"\n--- COMPLEXITY DISTRIBUTION ---")
    for complexity, count in sorted(report["complexity_distribution"].items()):
        print(f"  {complexity:20} {count}")

    if report["failed_tests"]:
        print(f"\n--- FAILED TESTS ({len(report['failed_tests'])}) ---")
        for ft in report["failed_tests"]:
            print(f"\n  Test: {ft['test_name']}")
            print(f"  Query: {ft['query']}")
            print(f"  Expected: complexity={ft['expected_complexity']}, queried={ft['expected_queried_sources']}")
            print(f"  Actual:   complexity={ft['actual_complexity']}, queried={ft['actual_queried_sources']}, used={ft['actual_used_sources']}")
            print(f"  Error: {ft['error']}")
            print(f"  Latency: {ft['latency_ms']:.0f}ms")

    print(f"\n{'='*60}")
    print(f"Test run completed at {summary['timestamp']}")
    print(f"{'='*60}\n")


def save_report(report: Dict[str, Any], output_path: str):
    """Save report to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report saved to: {output_path}")


def save_csv(results: List[TestResult], output_path: str):
    """Save results to CSV file."""
    import csv

    fieldnames = [
        'test_name', 'category', 'passed', 'total_latency_ms',
        'expected_complexity', 'actual_complexity',
        'expected_is_legal_query', 'actual_is_legal_query',
        'expected_is_pure_legal', 'actual_is_pure_legal',
        'expected_queried_sources', 'actual_queried_sources', 'actual_used_sources',
        'error_message'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            writer.writerow({
                'test_name': r.test_name,
                'category': r.category,
                'passed': r.passed,
                'total_latency_ms': f"{r.total_latency_ms:.0f}",
                'expected_complexity': r.expected_complexity,
                'actual_complexity': r.actual_complexity,
                'expected_is_legal_query': r.expected_is_legal_query,
                'actual_is_legal_query': r.actual_is_legal_query,
                'expected_is_pure_legal': r.expected_is_pure_legal,
                'actual_is_pure_legal': r.actual_is_pure_legal,
                'expected_queried_sources': ','.join(r.expected_queried_sources),
                'actual_queried_sources': ','.join(r.actual_sources_queried),
                'actual_used_sources': ','.join(r.actual_sources),
                'error_message': r.error_message,
            })

    print(f"CSV saved to: {output_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="WorldClassRouter End-to-End Test Suite"
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        action="append",
        help="Filter by category (can be repeated). Options: simple_sql, simple_rag, simple_web, simple_legal, hybrid_sql_legal, hybrid_sql_rag, hybrid_rag_legal, hybrid_multi"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Output CSV file path"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available test categories"
    )

    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for cat in TestCategory:
            count = sum(1 for s in TEST_SCENARIOS if s.category == cat)
            print(f"  {cat.value:20} ({count} tests)")
        return 0

    # Check API availability
    try:
        response = requests.get(
            API_URL.replace("/chat", "").rstrip("/") + "/../health",
            timeout=5
        )
    except:
        print(f"Warning: Could not verify API availability at {API_URL}")
        print("Make sure the backend is running before continuing.")

    # Run tests
    results = run_tests(
        categories=args.category,
        verbose=args.verbose
    )

    # Generate and print report
    report = generate_report(results)
    print_report(report)

    # Save outputs if requested
    if args.output:
        save_report(report, args.output)

    if args.csv:
        save_csv(results, args.csv)

    # Default output files
    if not args.output and not args.csv:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_json = f"tests/router_test_results_{timestamp}.json"
        save_report(report, default_json)

    # Return exit code based on test results
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
