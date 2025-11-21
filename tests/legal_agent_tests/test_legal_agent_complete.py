"""
Test Complet du LegalAgent
Tests de tous les use cases avec documents factices

Date: 21 novembre 2025
Architecture: Routing Propre (Orchestrator -> LegalAgent.process_request())
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.agents.legal_agent import LegalAgent


class Color:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{Color.HEADER}{Color.BOLD}{'='*80}{Color.ENDC}")
    print(f"{Color.HEADER}{Color.BOLD}{title.center(80)}{Color.ENDC}")
    print(f"{Color.HEADER}{Color.BOLD}{'='*80}{Color.ENDC}\n")


def print_test(test_name: str, status: str, details: str = ""):
    """Print test result"""
    if status == "PASS":
        status_str = f"{Color.OKGREEN}✓ PASS{Color.ENDC}"
    elif status == "FAIL":
        status_str = f"{Color.FAIL}✗ FAIL{Color.ENDC}"
    else:
        status_str = f"{Color.WARNING}⚠ {status}{Color.ENDC}"

    print(f"{status_str} - {test_name}")
    if details:
        print(f"  {Color.OKCYAN}{details}{Color.ENDC}")


def load_document(filename: str) -> str:
    """Load test document"""
    test_dir = Path(__file__).parent
    file_path = test_dir / filename

    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


async def test_use_case_1_analyze_full():
    """
    USE CASE 1: Analyse Complète d'un Contrat de Syndic

    Prompt: "Analyser ce contrat de syndic"
    Action attendue: analyze (mode=full)
    """
    print_section("USE CASE 1: Analyse Complète")

    legal_agent = LegalAgent()

    # Load document
    doc_text = load_document("contrat_syndic_risque.txt")

    # Simulate user request
    user_input = "Analyser ce contrat de syndic"
    context = {"document_text": doc_text}

    print(f"Prompt utilisateur: \"{user_input}\"")
    print(f"Document: contrat_syndic_risque.txt ({len(doc_text)} chars)")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "analyze", f"Expected action=analyze, got {result['action']}"
    assert result["mode"] == "full", f"Expected mode=full, got {result.get('mode')}"
    assert result["success"] == True, "Analysis should succeed"

    analysis_result = result["result"]

    # Check analysis components
    has_summary = "summary" in analysis_result and analysis_result["summary"]
    has_risks = "risks" in analysis_result and len(analysis_result["risks"]) > 0
    has_obligations = "obligations" in analysis_result and len(analysis_result["obligations"]) > 0
    has_document_type = "document_type" in analysis_result

    print_test("Action détectée: analyze", "PASS", f"Mode: {result['mode']}")
    print_test("Résumé généré", "PASS" if has_summary else "FAIL")
    print_test(f"Risques identifiés: {len(analysis_result.get('risks', []))}",
              "PASS" if has_risks else "FAIL")
    print_test(f"Obligations identifiées: {len(analysis_result.get('obligations', []))}",
              "PASS" if has_obligations else "FAIL")
    print_test(f"Type de document: {analysis_result.get('document_type', 'N/A')}",
              "PASS" if has_document_type else "FAIL")

    # Display first risk
    if has_risks:
        first_risk = analysis_result["risks"][0]
        print(f"\n  {Color.WARNING}Exemple de risque détecté:{Color.ENDC}")
        print(f"  Severity: {first_risk.get('severity', 'N/A')}")
        print(f"  Category: {first_risk.get('category', 'N/A')}")
        print(f"  Description: {first_risk.get('description', 'N/A')[:100]}...")

    return result


async def test_use_case_2_analyze_risk():
    """
    USE CASE 2: Analyse Focalisée sur les Risques

    Prompt: "Analyser ce contrat et identifier les risques juridiques"
    Action attendue: analyze (mode=risk)
    """
    print_section("USE CASE 2: Analyse des Risques")

    legal_agent = LegalAgent()

    # Load document
    doc_text = load_document("contrat_syndic_risque.txt")

    # Simulate user request
    user_input = "Analyser ce contrat et identifier les risques juridiques"
    context = {"document_text": doc_text}

    print(f"Prompt utilisateur: \"{user_input}\"")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "analyze", f"Expected action=analyze, got {result['action']}"
    assert result["mode"] == "risk", f"Expected mode=risk, got {result.get('mode')}"

    analysis_result = result["result"]
    has_risks = "risks" in analysis_result and len(analysis_result["risks"]) > 0

    print_test("Action détectée: analyze", "PASS", f"Mode: {result['mode']}")
    print_test(f"Risques identifiés: {len(analysis_result.get('risks', []))}",
              "PASS" if has_risks else "FAIL")

    # Check risk severity levels
    if has_risks:
        risk_levels = {}
        for risk in analysis_result["risks"]:
            severity = risk.get("severity", "unknown")
            risk_levels[severity] = risk_levels.get(severity, 0) + 1

        print(f"\n  {Color.OKCYAN}Répartition des risques:{Color.ENDC}")
        for severity, count in risk_levels.items():
            print(f"  - {severity}: {count}")

    return result


async def test_use_case_3_analyze_summary():
    """
    USE CASE 3: Résumé Exécutif

    Prompt: "Résume-moi ce contrat"
    Action attendue: analyze (mode=summary)
    """
    print_section("USE CASE 3: Résumé Exécutif")

    legal_agent = LegalAgent()

    # Load document
    doc_text = load_document("contrat_syndic_conforme.txt")

    # Simulate user request
    user_input = "Résume-moi ce contrat"
    context = {"document_text": doc_text}

    print(f"Prompt utilisateur: \"{user_input}\"")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "analyze", f"Expected action=analyze, got {result['action']}"
    assert result["mode"] == "summary", f"Expected mode=summary, got {result.get('mode')}"

    analysis_result = result["result"]
    has_summary = "summary" in analysis_result and analysis_result["summary"]

    print_test("Action détectée: analyze", "PASS", f"Mode: {result['mode']}")
    print_test("Résumé généré", "PASS" if has_summary else "FAIL")

    if has_summary:
        summary_length = len(analysis_result["summary"])
        print(f"\n  {Color.OKCYAN}Résumé ({summary_length} chars):{Color.ENDC}")
        print(f"  {analysis_result['summary'][:300]}...")

    return result


async def test_use_case_4_analyze_compliance():
    """
    USE CASE 4: Vérification de Conformité

    Prompt: "Vérifier la conformité de ce règlement avec la loi ELAN"
    Action attendue: analyze (mode=compliance)
    """
    print_section("USE CASE 4: Vérification de Conformité")

    legal_agent = LegalAgent()

    # Load document
    doc_text = load_document("reglement_copropriete.txt")

    # Simulate user request
    user_input = "Vérifier la conformité de ce règlement avec la loi ELAN"
    context = {"document_text": doc_text}

    print(f"Prompt utilisateur: \"{user_input}\"")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "analyze", f"Expected action=analyze, got {result['action']}"
    assert result["mode"] == "compliance", f"Expected mode=compliance, got {result.get('mode')}"

    analysis_result = result["result"]
    has_compliance = "compliance" in analysis_result

    print_test("Action détectée: analyze", "PASS", f"Mode: {result['mode']}")
    print_test("Vérification conformité", "PASS" if has_compliance else "FAIL")

    if has_compliance:
        print(f"\n  {Color.OKCYAN}Résultat conformité:{Color.ENDC}")
        print(f"  {str(analysis_result['compliance'])[:300]}...")

    return result


async def test_use_case_5_compare_documents():
    """
    USE CASE 5: Comparaison de Deux Contrats

    Prompt: "Comparer ces deux contrats de syndic"
    Action attendue: compare
    """
    print_section("USE CASE 5: Comparaison de Documents")

    legal_agent = LegalAgent()

    # Load both documents
    doc1_text = load_document("contrat_syndic_risque.txt")
    doc2_text = load_document("contrat_syndic_conforme.txt")

    # Simulate user request
    user_input = "Comparer ces deux contrats de syndic"
    context = {
        "document1": doc1_text,
        "document2": doc2_text
    }

    print(f"Prompt utilisateur: \"{user_input}\"")
    print(f"Document 1: contrat_syndic_risque.txt ({len(doc1_text)} chars)")
    print(f"Document 2: contrat_syndic_conforme.txt ({len(doc2_text)} chars)")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "compare", f"Expected action=compare, got {result['action']}"
    assert result["success"] == True, "Comparison should succeed"

    comparison_result = result["result"]
    has_differences = "differences" in comparison_result and len(comparison_result["differences"]) > 0
    has_similarities = "similarities" in comparison_result and len(comparison_result["similarities"]) > 0

    print_test("Action détectée: compare", "PASS")
    print_test(f"Différences identifiées: {len(comparison_result.get('differences', []))}",
              "PASS" if has_differences else "FAIL")
    print_test(f"Similarités identifiées: {len(comparison_result.get('similarities', []))}",
              "PASS" if has_similarities else "FAIL")

    # Display first difference
    if has_differences:
        first_diff = comparison_result["differences"][0]
        print(f"\n  {Color.WARNING}Exemple de différence:{Color.ENDC}")
        print(f"  Aspect: {first_diff.get('aspect', 'N/A')}")
        print(f"  Doc 1: {first_diff.get('doc1', 'N/A')}")
        print(f"  Doc 2: {first_diff.get('doc2', 'N/A')}")
        print(f"  Importance: {first_diff.get('importance', 'N/A')}")

    return result


async def test_use_case_6_legal_advice():
    """
    USE CASE 6: Conseil Juridique

    Prompt: "Quelles sont les obligations légales du syndic en matière de rénovation énergétique ?"
    Action attendue: advice
    """
    print_section("USE CASE 6: Conseil Juridique")

    legal_agent = LegalAgent()

    # Simulate user request (no document needed for advice)
    user_input = "Quelles sont les obligations légales du syndic en matière de rénovation énergétique ?"
    context = {}

    print(f"Prompt utilisateur: \"{user_input}\"")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "advice", f"Expected action=advice, got {result['action']}"
    assert result["success"] == True, "Advice should succeed"

    advice_result = result["result"]
    has_advice = "advice" in advice_result and advice_result["advice"]
    has_laws = "relevant_laws" in advice_result and len(advice_result["relevant_laws"]) > 0
    has_recommendations = "recommendations" in advice_result

    print_test("Action détectée: advice", "PASS")
    print_test("Conseil juridique généré", "PASS" if has_advice else "FAIL")
    print_test(f"Lois pertinentes identifiées: {len(advice_result.get('relevant_laws', []))}",
              "PASS" if has_laws else "FAIL")
    print_test("Recommandations incluses", "PASS" if has_recommendations else "FAIL")

    # Display relevant laws
    if has_laws:
        print(f"\n  {Color.OKCYAN}Lois pertinentes:{Color.ENDC}")
        for law in advice_result["relevant_laws"]:
            print(f"  - {law}")

    # Display advice excerpt
    if has_advice:
        print(f"\n  {Color.OKCYAN}Conseil juridique (extrait):{Color.ENDC}")
        print(f"  {advice_result['advice'][:400]}...")

    return result


async def test_use_case_7_search_jurisprudence():
    """
    USE CASE 7: Recherche de Jurisprudence

    Prompt: "Rechercher de la jurisprudence sur les assemblées générales en copropriété"
    Action attendue: jurisprudence
    """
    print_section("USE CASE 7: Recherche de Jurisprudence")

    legal_agent = LegalAgent()

    # Simulate user request
    user_input = "Rechercher de la jurisprudence sur les assemblées générales en copropriété"
    context = {}

    print(f"Prompt utilisateur: \"{user_input}\"")

    # Call LegalAgent
    result = await legal_agent.process_request(
        user_input=user_input,
        context=context
    )

    # Verify result
    assert result["action"] == "jurisprudence", f"Expected action=jurisprudence, got {result['action']}"

    jurisprudence_result = result["result"]
    has_cases = "cases" in jurisprudence_result and len(jurisprudence_result["cases"]) > 0
    has_summary = "summary" in jurisprudence_result and jurisprudence_result["summary"]

    print_test("Action détectée: jurisprudence", "PASS")
    print_test(f"Cas trouvés: {len(jurisprudence_result.get('cases', []))}",
              "PASS" if has_cases else "WARN")
    print_test("Synthèse générée", "PASS" if has_summary else "FAIL")

    # Display first case
    if has_cases:
        first_case = jurisprudence_result["cases"][0]
        print(f"\n  {Color.OKCYAN}Premier cas trouvé:{Color.ENDC}")
        print(f"  Source: {first_case.get('source', 'N/A')}")
        print(f"  Title: {first_case.get('title', 'N/A')}")
        print(f"  Relevance: {first_case.get('relevance', 0)*100:.1f}%")

    return result


async def generate_test_report(test_results: dict):
    """Generate comprehensive test report"""
    print_section("RAPPORT DE TESTS - LEGAL AGENT")

    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results.values() if r["success"])

    print(f"{Color.BOLD}Tests exécutés: {total_tests}{Color.ENDC}")
    print(f"{Color.OKGREEN}Tests réussis: {passed_tests}{Color.ENDC}")
    print(f"{Color.FAIL}Tests échoués: {total_tests - passed_tests}{Color.ENDC}")
    print(f"{Color.BOLD}Taux de réussite: {passed_tests/total_tests*100:.1f}%{Color.ENDC}")

    print(f"\n{Color.HEADER}Détails par Use Case:{Color.ENDC}\n")

    for use_case, result in test_results.items():
        status_icon = "✓" if result["success"] else "✗"
        status_color = Color.OKGREEN if result["success"] else Color.FAIL

        print(f"{status_color}{status_icon}{Color.ENDC} {use_case}")
        print(f"  Action: {result['action']}")
        if "mode" in result:
            print(f"  Mode: {result['mode']}")
        print(f"  Succès: {result['success']}")
        print()

    # Save report to file
    report_path = Path(__file__).parent / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("RAPPORT DE TESTS - LEGAL AGENT\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        f.write(f"Tests exécutés: {total_tests}\n")
        f.write(f"Tests réussis: {passed_tests}\n")
        f.write(f"Tests échoués: {total_tests - passed_tests}\n")
        f.write(f"Taux de réussite: {passed_tests/total_tests*100:.1f}%\n\n")

        for use_case, result in test_results.items():
            f.write(f"\n{'='*60}\n")
            f.write(f"{use_case}\n")
            f.write(f"{'='*60}\n")
            f.write(f"Action: {result['action']}\n")
            if "mode" in result:
                f.write(f"Mode: {result['mode']}\n")
            f.write(f"Succès: {result['success']}\n")
            f.write(f"Message: {result['message'][:200]}...\n")

    print(f"\n{Color.OKGREEN}Rapport sauvegardé: {report_path}{Color.ENDC}")


async def main():
    """Main test runner"""
    print(f"\n{Color.HEADER}{Color.BOLD}")
    print("="*80)
    print("TESTS COMPLETS DU LEGAL AGENT".center(80))
    print("Architecture: Routing Propre (Orchestrator -> LegalAgent.process_request())".center(80))
    print("="*80)
    print(f"{Color.ENDC}\n")

    test_results = {}

    try:
        # USE CASE 1: Full Analysis
        result1 = await test_use_case_1_analyze_full()
        test_results["USE CASE 1: Analyse Complète"] = result1

        # USE CASE 2: Risk Analysis
        result2 = await test_use_case_2_analyze_risk()
        test_results["USE CASE 2: Analyse des Risques"] = result2

        # USE CASE 3: Summary
        result3 = await test_use_case_3_analyze_summary()
        test_results["USE CASE 3: Résumé Exécutif"] = result3

        # USE CASE 4: Compliance
        result4 = await test_use_case_4_analyze_compliance()
        test_results["USE CASE 4: Vérification de Conformité"] = result4

        # USE CASE 5: Document Comparison
        result5 = await test_use_case_5_compare_documents()
        test_results["USE CASE 5: Comparaison de Documents"] = result5

        # USE CASE 6: Legal Advice
        result6 = await test_use_case_6_legal_advice()
        test_results["USE CASE 6: Conseil Juridique"] = result6

        # USE CASE 7: Jurisprudence Search
        result7 = await test_use_case_7_search_jurisprudence()
        test_results["USE CASE 7: Recherche de Jurisprudence"] = result7

        # Generate report
        await generate_test_report(test_results)

        print(f"\n{Color.OKGREEN}{Color.BOLD}✓ TOUS LES TESTS TERMINÉS{Color.ENDC}\n")

    except Exception as e:
        print(f"\n{Color.FAIL}✗ ERREUR DURANT LES TESTS:{Color.ENDC}")
        print(f"{Color.FAIL}{str(e)}{Color.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
