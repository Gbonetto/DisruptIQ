"""
Test Core-First Pipeline - Validation du nouveau pipeline simplifié
DisruptIQ SMA - Phase Core-First

Tests:
1. QueryAnalyzer avec scores de confiance
2. Détection short-circuit (pure_legal, pure_web)
3. Génération de suggestions contextuelles
4. Absence de 4-sources automatique

Author: Claude Code
Date: December 2024
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_query_analyzer_scores():
    """Test QueryAnalyzer avec les nouveaux scores de confiance"""
    from app.services.query_analyzer import get_query_analyzer

    analyzer = get_query_analyzer()

    print("\n" + "="*70)
    print("TEST 1: QueryAnalyzer - Scores de confiance")
    print("="*70)

    test_cases = [
        # (query, expected_pure_legal, expected_pure_web, expected_has_biz)
        ("Que dit la loi du 10 juillet 1965 sur les parties communes ?", True, False, False),
        ("Quel est l'article 25 du code civil ?", True, False, False),
        ("Prix moyen d'un ravalement au m² en 2024", False, True, False),
        ("Quelles sont les aides MaPrimeRénov actuelles ?", False, True, False),
        ("Combien de copropriétaires dans la résidence des Mimosas ?", False, False, True),
        ("Liste les lots du bâtiment A avec M. Dupont", False, False, True),
        ("Quel est le règlement de copropriété ?", False, False, False),  # Legal mais pas pur (règlement interne)
        ("Quelle majorité pour les travaux des Mimosas ?", False, False, True),  # Legal + entité métier
    ]

    passed = 0
    for query, exp_pure_legal, exp_pure_web, exp_has_biz in test_cases:
        result = analyzer.analyze(query)

        status_legal = "✅" if result.pure_legal_query == exp_pure_legal else "❌"
        status_web = "✅" if result.pure_web_query == exp_pure_web else "❌"
        status_biz = "✅" if result.has_business_entities == exp_has_biz else "❌"

        all_pass = (result.pure_legal_query == exp_pure_legal and
                   result.pure_web_query == exp_pure_web and
                   result.has_business_entities == exp_has_biz)

        if all_pass:
            passed += 1

        print(f"\nQuery: {query[:50]}...")
        print(f"  Legal: {status_legal} pure={result.pure_legal_query} (exp={exp_pure_legal}) conf={result.legal_confidence:.0%}")
        print(f"  Web:   {status_web} pure={result.pure_web_query} (exp={exp_pure_web}) conf={result.web_confidence:.0%}")
        print(f"  Biz:   {status_biz} has_entities={result.has_business_entities} (exp={exp_has_biz})")

    print(f"\n{'='*70}")
    print(f"RÉSULTAT: {passed}/{len(test_cases)} tests passés")
    return passed == len(test_cases)


def test_shortcircuit_detection():
    """Test détection des short-circuits"""
    from app.services.query_analyzer import get_query_analyzer

    analyzer = get_query_analyzer()

    print("\n" + "="*70)
    print("TEST 2: Détection Short-Circuit")
    print("="*70)

    # Cas qui DOIVENT déclencher un short-circuit
    shortcircuit_cases = [
        ("Que dit la loi du 10 juillet 1965 ?", "legal"),
        ("Article 25 de la loi de copropriété", "legal"),
        ("Prix moyen ravalement 2024 en France", "web"),
        ("Quelles aides MaPrimeRénov disponibles ?", "web"),
    ]

    # Cas qui NE DOIVENT PAS déclencher un short-circuit
    no_shortcircuit_cases = [
        "Combien de copropriétaires aux Mimosas ?",  # Entité métier
        "Quelle majorité pour le lot 5 ?",  # Legal + entité
        "Prix du devis de M. Dupont",  # Web + entité
        "Quel est le règlement de copropriété ?",  # Doit chercher dans docs
    ]

    passed = 0

    print("\n--- Cas avec short-circuit attendu ---")
    for query, expected_type in shortcircuit_cases:
        result = analyzer.analyze(query)

        if expected_type == "legal":
            should_sc = result.should_shortcircuit_legal
        else:
            should_sc = result.should_shortcircuit_web

        status = "✅" if should_sc else "❌"
        if should_sc:
            passed += 1

        print(f"{status} {query[:50]}... → short-circuit {expected_type}: {should_sc}")
        if not should_sc:
            print(f"   DEBUG: pure_{expected_type}={getattr(result, f'pure_{expected_type}_query')}, "
                  f"conf={getattr(result, f'{expected_type}_confidence'):.0%}, "
                  f"has_biz={result.has_business_entities}")

    print("\n--- Cas SANS short-circuit attendu ---")
    for query in no_shortcircuit_cases:
        result = analyzer.analyze(query)

        should_sc = result.should_shortcircuit_legal or result.should_shortcircuit_web

        status = "✅" if not should_sc else "❌"
        if not should_sc:
            passed += 1

        print(f"{status} {query[:50]}... → shortcircuit: {should_sc} (attendu: False)")

    total = len(shortcircuit_cases) + len(no_shortcircuit_cases)
    print(f"\n{'='*70}")
    print(f"RÉSULTAT: {passed}/{total} tests passés")
    return passed == total


def test_suggestion_generation():
    """Test génération des suggestions contextuelles"""
    from app.services.query_analyzer import get_query_analyzer

    analyzer = get_query_analyzer()

    print("\n" + "="*70)
    print("TEST 3: Génération de Suggestions")
    print("="*70)

    # Cas qui doivent générer des suggestions
    suggestion_cases = [
        ("Quel est le règlement de copropriété ?", True, False),  # Legal suggestion
        ("Combien coûte le ravalement ?", False, True),  # Web suggestion (prix)
        ("Quelle majorité pour voter ?", True, False),  # Legal suggestion
        ("Compare notre devis avec le marché", False, True),  # Web suggestion
        ("Liste les copropriétaires", False, False),  # Pas de suggestion
    ]

    passed = 0
    for query, exp_legal_sugg, exp_web_sugg in suggestion_cases:
        result = analyzer.analyze(query)

        # Note: should_suggest_* est True si confidence >= 0.5 et pas de short-circuit
        legal_sugg = result.should_suggest_legal
        web_sugg = result.should_suggest_web

        status_legal = "✅" if legal_sugg == exp_legal_sugg else "❌"
        status_web = "✅" if web_sugg == exp_web_sugg else "❌"

        all_pass = legal_sugg == exp_legal_sugg and web_sugg == exp_web_sugg
        if all_pass:
            passed += 1

        print(f"\nQuery: {query[:50]}...")
        print(f"  {status_legal} Legal suggestion: {legal_sugg} (exp={exp_legal_sugg}) conf={result.legal_confidence:.0%}")
        print(f"  {status_web} Web suggestion: {web_sugg} (exp={exp_web_sugg}) conf={result.web_confidence:.0%}")

    print(f"\n{'='*70}")
    print(f"RÉSULTAT: {passed}/{len(suggestion_cases)} tests passés")
    return passed == len(suggestion_cases)


def test_no_four_sources_auto():
    """Vérifie que le système ne déclenche JAMAIS 4 sources automatiquement"""
    from app.services.query_analyzer import get_query_analyzer

    analyzer = get_query_analyzer()

    print("\n" + "="*70)
    print("TEST 4: Invariant - Pas de 4 sources automatiques")
    print("="*70)

    # Requêtes complexes qui pourraient tenter le système
    complex_queries = [
        "Pour notre copropriété de 42 lots, selon le règlement et la loi, quel est le prix actuel des travaux ?",
        "Fais-moi un audit complet avec les copropriétaires, documents, loi et prix du marché",
        "Compare tout: données SQL, documents, Légifrance et internet",
    ]

    print("\nVérification que should_shortcircuit ne peut être True pour les deux à la fois:")

    passed = 0
    for query in complex_queries:
        result = analyzer.analyze(query)

        # On ne peut JAMAIS avoir les deux short-circuits en même temps
        both_sc = result.should_shortcircuit_legal and result.should_shortcircuit_web

        status = "✅" if not both_sc else "❌"
        if not both_sc:
            passed += 1

        print(f"\n{status} Query: {query[:50]}...")
        print(f"   SC Legal: {result.should_shortcircuit_legal}, SC Web: {result.should_shortcircuit_web}")
        print(f"   Sugg Legal: {result.should_suggest_legal}, Sugg Web: {result.should_suggest_web}")

    print(f"\n{'='*70}")
    print(f"RÉSULTAT: {passed}/{len(complex_queries)} tests passés")
    print("\nNote: Le Core (SQL+RAG) est toujours exécuté sauf short-circuit rare.")
    print("Legal/Web ne sont jamais exécutés automatiquement ensemble.")
    return passed == len(complex_queries)


def main():
    """Exécute tous les tests"""
    print("\n" + "="*70)
    print("TESTS CORE-FIRST PIPELINE")
    print("DisruptIQ SMA - Validation de l'architecture")
    print("="*70)

    results = []

    # Test 1: Scores de confiance
    results.append(("QueryAnalyzer Scores", test_query_analyzer_scores()))

    # Test 2: Short-circuit
    results.append(("Short-Circuit Detection", test_shortcircuit_detection()))

    # Test 3: Suggestions
    results.append(("Suggestion Generation", test_suggestion_generation()))

    # Test 4: Invariant 4 sources
    results.append(("No 4-Sources Auto", test_no_four_sources_auto()))

    # Résumé
    print("\n" + "="*70)
    print("RÉSUMÉ FINAL")
    print("="*70)

    total_passed = 0
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if passed:
            total_passed += 1

    print(f"\n{'='*70}")
    overall = "SUCCESS" if total_passed == len(results) else "FAILURE"
    print(f"OVERALL: {overall} ({total_passed}/{len(results)} tests passés)")
    print("="*70)

    return total_passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
