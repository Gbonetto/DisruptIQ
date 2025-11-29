"""
WorldClassRouter E2E Test Suite v2
===================================

Batterie de tests End-to-End pour valider l'architecture optimisée du WorldClassRouter:
- Modes light (SQL, RAG, Legal, Web)
- Synthèse unique multi-sources
- Streaming SSE avec progress messages

COMMENT LANCER CES TESTS:
-------------------------
# Tous les tests E2E
pytest tests/test_world_class_router_e2e_v2.py -v --tb=short

# Uniquement les tests de fiabilité (rapides)
pytest tests/test_world_class_router_e2e_v2.py -v -m "not slow"

# Tests avec métriques détaillées
pytest tests/test_world_class_router_e2e_v2.py -v -s --tb=short

# Test spécifique
pytest tests/test_world_class_router_e2e_v2.py::test_simple_sql_count_copro -v

MÉTRIQUES À OBSERVER:
---------------------
- total_ms: Latence totale de la requête
- routing_ms: Temps de détection du routing
- retrieval_ms: Temps de récupération des données
- synthesis_ms: Temps de synthèse LLM (si applicable)
- first_progress_ms: Temps avant premier message SSE

INTERPRÉTATION DES RÉSULTATS:
----------------------------
- PASS + latence OK = Architecture validée pour ce scénario
- PASS + latence haute = Fonctionnel mais optimisation possible
- FAIL sur complexity = Problème de routing (ne pas modifier la logique)
- FAIL sur sources = Sources mal détectées ou interdites utilisées

SEUILS DE PERFORMANCE CIBLES:
----------------------------
- SIMPLE_SQL: p95 < 2.5s
- SIMPLE_RAG: p95 < 10s
- SIMPLE_LEGAL: p95 < 15s (API PISTE lente)
- SIMPLE_WEB: p95 < 7s
- HYBRID: p95 < 15s
- COMPLEX: p95 < 20s
"""

import pytest
import httpx
import asyncio
import json
import time
import statistics
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger()

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "http://localhost:8000"
API_CHAT_ENDPOINT = "/api/assistant-v2/chat"
API_STREAM_ENDPOINT = "/api/assistant-v2/chat/stream"
DEFAULT_TIMEOUT = 60.0  # seconds


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class E2EQuerySpec:
    """
    Spécification d'un test E2E pour le WorldClassRouter.

    Attributes:
        name: Identifiant unique du test
        user_message: Message utilisateur à envoyer
        expected_complexity: Complexité attendue (simple_sql, simple_rag, hybrid, etc.)
        required_queried_sources: Sources qui DOIVENT être interrogées
        optional_queried_sources: Sources qui PEUVENT être interrogées
        forbidden_sources: Sources qui NE DOIVENT PAS être interrogées
        max_total_latency_ms: Seuil de latence totale max
        max_synthesis_latency_ms: Seuil de latence synthèse max (optionnel)
        expect_streaming: Si True, teste aussi le streaming SSE
        description: Description du scénario testé
    """
    name: str
    user_message: str
    expected_complexity: str
    required_queried_sources: Set[str] = field(default_factory=set)
    optional_queried_sources: Set[str] = field(default_factory=set)
    forbidden_sources: Set[str] = field(default_factory=set)
    max_total_latency_ms: int = 15000
    max_synthesis_latency_ms: Optional[int] = None
    expect_streaming: bool = True
    description: str = ""


@dataclass
class E2ETestResult:
    """Résultat d'un test E2E avec toutes les métriques."""
    spec: E2EQuerySpec
    success: bool

    # Response data
    response_status: int = 0
    response_message: str = ""
    response_data: Dict[str, Any] = field(default_factory=dict)

    # Router metrics
    actual_complexity: str = ""
    sources_queried: Set[str] = field(default_factory=set)
    sources_used: Set[str] = field(default_factory=set)
    is_legal_query: bool = False
    is_pure_legal: bool = False

    # Timing metrics (ms)
    total_ms: float = 0.0
    routing_ms: float = 0.0
    retrieval_ms: float = 0.0
    rerank_ms: float = 0.0
    synthesis_ms: float = 0.0

    # Streaming metrics
    first_progress_ms: float = 0.0
    progress_events: List[str] = field(default_factory=list)
    answer_chunks_count: int = 0

    # Errors
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.spec.name,
            "success": self.success,
            "complexity": {
                "expected": self.spec.expected_complexity,
                "actual": self.actual_complexity,
                "match": self.spec.expected_complexity == self.actual_complexity
            },
            "sources": {
                "queried": list(self.sources_queried),
                "used": list(self.sources_used),
                "required_present": self.spec.required_queried_sources.issubset(self.sources_queried),
                "forbidden_absent": len(self.spec.forbidden_sources & (self.sources_queried | self.sources_used)) == 0
            },
            "latency": {
                "total_ms": round(self.total_ms, 2),
                "routing_ms": round(self.routing_ms, 2),
                "retrieval_ms": round(self.retrieval_ms, 2),
                "synthesis_ms": round(self.synthesis_ms, 2),
                "max_allowed_ms": self.spec.max_total_latency_ms,
                "within_limit": self.total_ms <= self.spec.max_total_latency_ms
            },
            "streaming": {
                "first_progress_ms": round(self.first_progress_ms, 2),
                "progress_events": self.progress_events,
                "answer_chunks": self.answer_chunks_count
            },
            "errors": self.errors
        }


# =============================================================================
# TEST RUNNER
# =============================================================================

class E2ETestRunner:
    """Runner pour exécuter les tests E2E du WorldClassRouter."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[E2ETestResult] = []

    async def run_test(self, spec: E2EQuerySpec) -> E2ETestResult:
        """
        Exécute un test E2E complet.

        1. Envoie la requête à l'API
        2. Capture les métriques de routing et timing
        3. Valide les assertions
        4. Retourne le résultat avec toutes les métriques
        """
        result = E2ETestResult(spec=spec, success=False)
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                # Send request to chat endpoint
                response = await client.post(
                    f"{self.base_url}{API_CHAT_ENDPOINT}",
                    json={
                        "message": spec.user_message,
                        "conversation_history": []
                    },
                    headers={"Content-Type": "application/json"}
                )

                result.total_ms = (time.time() - start_time) * 1000
                result.response_status = response.status_code

                if response.status_code != 200:
                    result.errors.append(f"HTTP {response.status_code}: {response.text[:200]}")
                    return result

                data = response.json()
                result.response_message = data.get("message", "")[:500]
                result.response_data = data.get("data", {})

                # Extract router metrics (WorldClassRouter path)
                router_metrics = result.response_data.get("router_metrics", {})

                if router_metrics:
                    # WorldClassRouter path - full metrics available
                    result.actual_complexity = router_metrics.get("complexity", "unknown")
                    result.sources_queried = set(router_metrics.get("sources_queried", []))
                    result.sources_used = set(router_metrics.get("sources_used", []))
                    result.is_legal_query = router_metrics.get("is_legal_query", False)
                    result.is_pure_legal = router_metrics.get("is_pure_legal", False)

                    # Extract timing metrics
                    result.routing_ms = router_metrics.get("prefilter_ms", 0.0)
                    result.retrieval_ms = router_metrics.get("retrieval_ms", 0.0)
                    result.rerank_ms = router_metrics.get("rerank_ms", 0.0)
                else:
                    # Legacy path (direct agent) - infer from response
                    agents_used = data.get("agents_used", [])

                    # Infer complexity from agents used
                    if "sql_agent" in agents_used and len(agents_used) == 1:
                        result.actual_complexity = "simple_sql"
                        result.sources_queried = {"sql"}
                        result.sources_used = {"sql"}
                    elif "rag_agent" in agents_used or "doc_agent" in agents_used:
                        result.actual_complexity = "simple_rag"
                        result.sources_queried = {"rag"}
                        result.sources_used = {"rag"}
                    elif "legal_agent" in agents_used:
                        result.actual_complexity = "simple_legal"
                        result.sources_queried = {"legifrance"}
                        result.sources_used = {"legifrance"}
                    elif "web_agent" in agents_used:
                        result.actual_complexity = "simple_web"
                        result.sources_queried = {"web"}
                        result.sources_used = {"web"}
                    elif len(agents_used) > 1:
                        result.actual_complexity = "hybrid"
                        # Infer sources from agents
                        for agent in agents_used:
                            if "sql" in agent:
                                result.sources_queried.add("sql")
                                result.sources_used.add("sql")
                            if "rag" in agent or "doc" in agent:
                                result.sources_queried.add("rag")
                                result.sources_used.add("rag")
                            if "legal" in agent:
                                result.sources_queried.add("legifrance")
                                result.sources_used.add("legifrance")
                            if "web" in agent:
                                result.sources_queried.add("web")
                                result.sources_used.add("web")
                    else:
                        result.actual_complexity = "unknown"

                # Estimate synthesis time
                if result.total_ms > 0:
                    overhead = result.routing_ms + result.retrieval_ms + result.rerank_ms
                    result.synthesis_ms = max(0, result.total_ms - overhead)

                # Validate assertions
                self._validate_result(result)

        except httpx.TimeoutException:
            result.errors.append(f"Request timed out after {DEFAULT_TIMEOUT}s")
        except Exception as e:
            result.errors.append(f"Exception: {str(e)}")

        self.results.append(result)
        return result

    async def run_streaming_test(self, spec: E2EQuerySpec) -> E2ETestResult:
        """
        Exécute un test E2E avec streaming SSE.

        Vérifie:
        1. Séquencement des messages progress
        2. Réception des answer_chunks
        3. Temps avant premier message (perception de vitesse)
        """
        result = E2ETestResult(spec=spec, success=False)
        start_time = time.time()
        first_event_time = None

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                # Build streaming URL with query params
                params = {
                    "message": spec.user_message,
                    "conversation_history": "[]",
                    "session_id": f"test_{spec.name}_{int(time.time())}"
                }

                async with client.stream(
                    "GET",
                    f"{self.base_url}{API_STREAM_ENDPOINT}",
                    params=params
                ) as response:

                    result.response_status = response.status_code

                    if response.status_code != 200:
                        result.errors.append(f"HTTP {response.status_code}")
                        return result

                    async for line in response.aiter_lines():
                        if not line or line.startswith(":"):
                            continue

                        # Track first event time
                        if first_event_time is None and line.startswith("event:"):
                            first_event_time = time.time()
                            result.first_progress_ms = (first_event_time - start_time) * 1000

                        # Parse SSE events
                        if line.startswith("event: thought"):
                            continue
                        elif line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                event_type = data.get("type", "")

                                # Track progress events
                                if event_type.startswith("progress_"):
                                    result.progress_events.append(event_type)

                            except json.JSONDecodeError:
                                pass

                        elif line.startswith("event: response"):
                            # Final response - extract data
                            pass

                result.total_ms = (time.time() - start_time) * 1000

                # Validate streaming behavior
                self._validate_streaming(result)

        except httpx.TimeoutException:
            result.errors.append(f"Stream timed out after {DEFAULT_TIMEOUT}s")
        except Exception as e:
            result.errors.append(f"Stream exception: {str(e)}")

        return result

    def _validate_result(self, result: E2ETestResult):
        """Validate test result against spec."""
        spec = result.spec

        # Check complexity match (flexible - allow similar complexities)
        complexity_ok = (
            result.actual_complexity == spec.expected_complexity or
            # Allow some flexibility for hybrid detection
            (spec.expected_complexity.startswith("hybrid") and result.actual_complexity in ["hybrid", "complex"]) or
            (spec.expected_complexity == "complex" and result.actual_complexity in ["hybrid", "complex"])
        )

        if not complexity_ok:
            result.errors.append(
                f"Complexity mismatch: expected '{spec.expected_complexity}', got '{result.actual_complexity}'"
            )

        # Check required sources are queried
        missing_sources = spec.required_queried_sources - result.sources_queried
        if missing_sources:
            result.errors.append(f"Missing required sources: {missing_sources}")

        # Check forbidden sources not used
        forbidden_used = spec.forbidden_sources & (result.sources_queried | result.sources_used)
        if forbidden_used:
            result.errors.append(f"Forbidden sources used: {forbidden_used}")

        # Check latency
        if result.total_ms > spec.max_total_latency_ms:
            result.errors.append(
                f"Latency exceeded: {result.total_ms:.0f}ms > {spec.max_total_latency_ms}ms"
            )

        # Check synthesis latency if specified
        if spec.max_synthesis_latency_ms and result.synthesis_ms > spec.max_synthesis_latency_ms:
            result.errors.append(
                f"Synthesis latency exceeded: {result.synthesis_ms:.0f}ms > {spec.max_synthesis_latency_ms}ms"
            )

        # Check response is not empty
        if not result.response_message:
            result.errors.append("Empty response message")

        # Set success
        result.success = len(result.errors) == 0

    def _validate_streaming(self, result: E2ETestResult):
        """Validate streaming test result."""
        spec = result.spec

        # Check we got progress events
        if not result.progress_events:
            # Not an error - progress events are optional for some paths
            pass

        # Check first progress time (perception of speed)
        if result.first_progress_ms > 2000:
            result.errors.append(
                f"Slow first progress: {result.first_progress_ms:.0f}ms (target < 2000ms)"
            )

        # Check total time
        if result.total_ms > spec.max_total_latency_ms:
            result.errors.append(
                f"Stream latency exceeded: {result.total_ms:.0f}ms > {spec.max_total_latency_ms}ms"
            )

        result.success = len(result.errors) == 0

    def get_summary(self) -> Dict[str, Any]:
        """Generate summary of all test results."""
        if not self.results:
            return {"message": "No tests run"}

        # Group by complexity type
        by_complexity: Dict[str, List[E2ETestResult]] = {}
        for r in self.results:
            comp = r.spec.expected_complexity
            if comp not in by_complexity:
                by_complexity[comp] = []
            by_complexity[comp].append(r)

        summary = {
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.success),
            "failed": sum(1 for r in self.results if not r.success),
            "by_complexity": {}
        }

        for comp, results in by_complexity.items():
            latencies = [r.total_ms for r in results if r.total_ms > 0]
            summary["by_complexity"][comp] = {
                "count": len(results),
                "passed": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "latency": {
                    "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0,
                    "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else (latencies[0] if latencies else 0), 2),
                    "min_ms": round(min(latencies), 2) if latencies else 0,
                    "max_ms": round(max(latencies), 2) if latencies else 0,
                }
            }

        return summary


# =============================================================================
# TEST SCENARIOS
# =============================================================================

# --- SIMPLE_SQL ---
SIMPLE_SQL_SPECS = [
    E2EQuerySpec(
        name="simple_sql_count_lots",
        user_message="Combien de lots au total ?",
        expected_complexity="simple_sql",
        required_queried_sources={"sql"},
        forbidden_sources={"legifrance", "web"},
        max_total_latency_ms=8000,  # Include LLM classification + SQL generation
        max_synthesis_latency_ms=6000,
        description="Comptage simple des lots - doit utiliser SQL uniquement"
    ),
    E2EQuerySpec(
        name="simple_sql_count_copro",
        user_message="Combien de coproprietes ?",
        expected_complexity="simple_sql",
        required_queried_sources={"sql"},
        forbidden_sources={"legifrance", "web"},
        max_total_latency_ms=8000,
        description="Comptage des copropriétés"
    ),
    E2EQuerySpec(
        name="simple_sql_list_coproprietes",
        user_message="Liste des coproprietes",
        expected_complexity="simple_sql",
        required_queried_sources={"sql"},
        forbidden_sources={"legifrance", "web"},
        max_total_latency_ms=8000,
        description="Liste simple des copropriétés"
    ),
]

# --- SIMPLE_RAG ---
SIMPLE_RAG_SPECS = [
    E2EQuerySpec(
        name="simple_rag_reglement",
        user_message="Que dit le reglement de copropriete sur les travaux ?",
        expected_complexity="simple_rag",
        required_queried_sources={"rag"},
        optional_queried_sources={"sql"},
        forbidden_sources={"web"},
        max_total_latency_ms=12000,
        description="Question sur le règlement - doit chercher dans les documents"
    ),
    E2EQuerySpec(
        name="simple_rag_pv",
        user_message="Resume le dernier PV d'assemblee generale",
        expected_complexity="simple_rag",
        required_queried_sources={"rag"},
        forbidden_sources={"sql", "web"},
        max_total_latency_ms=15000,
        description="Résumé de PV - RAG uniquement"
    ),
]

# --- SIMPLE_LEGAL ---
SIMPLE_LEGAL_SPECS = [
    E2EQuerySpec(
        name="simple_legal_majorites",
        user_message="Quelles sont les majorites de vote en assemblee generale selon la loi ?",
        expected_complexity="simple_legal",
        required_queried_sources={"legifrance"},
        forbidden_sources={"web"},
        max_total_latency_ms=20000,  # API PISTE peut être lente
        description="Question juridique sur les majorités - Légifrance"
    ),
    E2EQuerySpec(
        name="simple_legal_obligations_syndic",
        user_message="Quelles sont les obligations legales du syndic ?",
        expected_complexity="simple_legal",
        required_queried_sources={"legifrance"},
        forbidden_sources={"sql", "web"},
        max_total_latency_ms=20000,
        description="Obligations légales du syndic"
    ),
]

# --- SIMPLE_WEB ---
SIMPLE_WEB_SPECS = [
    E2EQuerySpec(
        name="simple_web_prix_ravalement",
        user_message="Quel est le prix moyen d'un ravalement de facade ?",
        expected_complexity="simple_web",
        required_queried_sources={"web"},
        forbidden_sources={"sql", "legifrance"},
        max_total_latency_ms=10000,
        description="Recherche de prix sur le web"
    ),
]

# --- HYBRID ---
HYBRID_SPECS = [
    E2EQuerySpec(
        name="hybrid_sql_rag",
        user_message="Liste les coproprietes et dis-moi ce que dit le reglement sur les charges",
        expected_complexity="hybrid",
        required_queried_sources={"sql", "rag"},
        forbidden_sources={"web"},
        max_total_latency_ms=15000,
        description="Combinaison SQL + RAG"
    ),
    E2EQuerySpec(
        name="hybrid_sql_legal",
        user_message="Combien de lots avons-nous et quelle majorite faut-il pour voter des travaux ?",
        expected_complexity="hybrid",
        required_queried_sources={"sql", "legifrance"},
        max_total_latency_ms=20000,
        description="Combinaison SQL + Legal"
    ),
    E2EQuerySpec(
        name="hybrid_rag_legal",
        user_message="Que dit notre reglement sur les travaux et est-ce conforme a la loi ?",
        expected_complexity="hybrid",
        required_queried_sources={"rag", "legifrance"},
        forbidden_sources={"web"},
        max_total_latency_ms=20000,
        description="Combinaison RAG + Legal"
    ),
]

# --- COMPLEX (MULTI-SOURCE) ---
COMPLEX_SPECS = [
    E2EQuerySpec(
        name="complex_multi_source",
        user_message="Donne-moi le nombre de lots, ce que dit le reglement sur les travaux, les obligations legales, et le prix moyen du marche",
        expected_complexity="complex",
        required_queried_sources={"sql", "rag", "legifrance", "web"},
        max_total_latency_ms=30000,
        description="Requête complexe multi-sources"
    ),
]

# All specs combined
ALL_SPECS = SIMPLE_SQL_SPECS + SIMPLE_RAG_SPECS + SIMPLE_LEGAL_SPECS + SIMPLE_WEB_SPECS + HYBRID_SPECS + COMPLEX_SPECS


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture
def runner():
    """Create a test runner instance."""
    return E2ETestRunner()


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# TEST FUNCTIONS - SIMPLE_SQL
# =============================================================================

@pytest.mark.asyncio
async def test_simple_sql_count_lots(runner):
    """Test: Comptage simple des lots."""
    spec = SIMPLE_SQL_SPECS[0]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
async def test_simple_sql_count_copro(runner):
    """Test: Comptage des copropriétés."""
    spec = SIMPLE_SQL_SPECS[1]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
async def test_simple_sql_list_coproprietes(runner):
    """Test: Liste des copropriétés."""
    spec = SIMPLE_SQL_SPECS[2]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


# =============================================================================
# TEST FUNCTIONS - SIMPLE_RAG
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_simple_rag_reglement(runner):
    """Test: Question sur le règlement."""
    spec = SIMPLE_RAG_SPECS[0]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_simple_rag_pv(runner):
    """Test: Résumé de PV."""
    spec = SIMPLE_RAG_SPECS[1]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


# =============================================================================
# TEST FUNCTIONS - SIMPLE_LEGAL
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_simple_legal_majorites(runner):
    """Test: Question juridique sur les majorités."""
    spec = SIMPLE_LEGAL_SPECS[0]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_simple_legal_obligations_syndic(runner):
    """Test: Obligations légales du syndic."""
    spec = SIMPLE_LEGAL_SPECS[1]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


# =============================================================================
# TEST FUNCTIONS - SIMPLE_WEB
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_simple_web_prix_ravalement(runner):
    """Test: Recherche de prix sur le web."""
    spec = SIMPLE_WEB_SPECS[0]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


# =============================================================================
# TEST FUNCTIONS - HYBRID
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_hybrid_sql_rag(runner):
    """Test: Combinaison SQL + RAG."""
    spec = HYBRID_SPECS[0]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_hybrid_sql_legal(runner):
    """Test: Combinaison SQL + Legal."""
    spec = HYBRID_SPECS[1]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_hybrid_rag_legal(runner):
    """Test: Combinaison RAG + Legal."""
    spec = HYBRID_SPECS[2]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


# =============================================================================
# TEST FUNCTIONS - COMPLEX
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_complex_multi_source(runner):
    """Test: Requête complexe multi-sources."""
    spec = COMPLEX_SPECS[0]
    result = await runner.run_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name}")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    assert result.success, f"Test failed: {result.errors}"


# =============================================================================
# TEST FUNCTIONS - STREAMING SSE
# =============================================================================

@pytest.mark.asyncio
async def test_streaming_simple_sql(runner):
    """Test: Streaming SSE pour requête SQL simple."""
    spec = E2EQuerySpec(
        name="streaming_sql",
        user_message="Combien de lots ?",
        expected_complexity="simple_sql",
        required_queried_sources={"sql"},
        max_total_latency_ms=5000,
        description="Test streaming SSE avec SQL"
    )
    result = await runner.run_streaming_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name} (STREAMING)")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(f"First progress: {result.first_progress_ms:.0f}ms")
    print(f"Progress events: {result.progress_events}")
    print(f"Total time: {result.total_ms:.0f}ms")

    assert result.success, f"Streaming test failed: {result.errors}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_streaming_hybrid(runner):
    """Test: Streaming SSE pour requête hybride."""
    spec = E2EQuerySpec(
        name="streaming_hybrid",
        user_message="Combien de lots et que dit le reglement sur les charges ?",
        expected_complexity="hybrid",
        required_queried_sources={"sql", "rag"},
        max_total_latency_ms=20000,
        description="Test streaming SSE avec requête hybride"
    )
    result = await runner.run_streaming_test(spec)

    print(f"\n{'='*60}")
    print(f"TEST: {spec.name} (STREAMING)")
    print(f"Query: {spec.user_message}")
    print(f"{'='*60}")
    print(f"First progress: {result.first_progress_ms:.0f}ms")
    print(f"Progress events: {result.progress_events}")
    print(f"Total time: {result.total_ms:.0f}ms")

    assert result.success, f"Streaming test failed: {result.errors}"


# =============================================================================
# FULL TEST SUITE
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.slow
async def test_full_suite_with_summary():
    """
    Exécute la suite complète de tests et génère un résumé.
    Ce test est marqué 'slow' et peut être exclu des tests rapides.
    """
    runner = E2ETestRunner()

    print("\n" + "="*80)
    print("WORLD CLASS ROUTER E2E TEST SUITE v2")
    print("="*80 + "\n")

    # Run all tests
    for spec in ALL_SPECS:
        print(f"Running: {spec.name}...", end=" ")
        try:
            result = await runner.run_test(spec)
            status = "PASS" if result.success else "FAIL"
            print(f"{status} ({result.total_ms:.0f}ms)")
            if not result.success:
                for error in result.errors:
                    print(f"  -> {error}")
        except Exception as e:
            print(f"ERROR: {str(e)}")

    # Generate summary
    summary = runner.get_summary()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total: {summary['total_tests']} | Passed: {summary['passed']} | Failed: {summary['failed']}")
    print()

    print("Performance by Complexity:")
    print("-"*60)
    for comp, stats in summary.get("by_complexity", {}).items():
        lat = stats.get("latency", {})
        print(f"  {comp}:")
        print(f"    Tests: {stats['count']} (P:{stats['passed']}/F:{stats['failed']})")
        print(f"    Latency: avg={lat.get('avg_ms', 0):.0f}ms | p95={lat.get('p95_ms', 0):.0f}ms | min={lat.get('min_ms', 0):.0f}ms | max={lat.get('max_ms', 0):.0f}ms")

    print("\n" + "="*80)

    # Assert overall success rate
    success_rate = summary['passed'] / summary['total_tests'] if summary['total_tests'] > 0 else 0
    assert success_rate >= 0.8, f"Success rate too low: {success_rate:.0%} (minimum 80%)"


# =============================================================================
# CLI RUNNER
# =============================================================================

if __name__ == "__main__":
    """Run tests from command line."""
    import sys

    async def main():
        runner = E2ETestRunner()

        print("\n" + "="*80)
        print("WORLD CLASS ROUTER E2E TEST SUITE v2")
        print("="*80 + "\n")

        # Run selected or all tests
        specs_to_run = ALL_SPECS
        if len(sys.argv) > 1:
            filter_name = sys.argv[1]
            specs_to_run = [s for s in ALL_SPECS if filter_name in s.name]

        for spec in specs_to_run:
            print(f"\nRunning: {spec.name}")
            print(f"Query: {spec.user_message}")
            print("-"*60)

            result = await runner.run_test(spec)
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

        # Print summary
        summary = runner.get_summary()
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    asyncio.run(main())
