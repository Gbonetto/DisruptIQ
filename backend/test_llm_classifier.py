"""
Test script for LLM Intent Classifier
Tests various query types to verify proper routing
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.services.agents.llm_intent_classifier import classify_intent_with_llm
from app.models.intent import IntentType

# Test queries covering all intent types
TEST_QUERIES = [
    # SQL / Data queries
    ("Combien de copropriétaires aux Mimosas ?", IntentType.QUERY_DATA),
    ("Liste des impayés supérieurs à 1000 euros", IntentType.QUERY_DATA),
    ("Quel est le budget prévisionnel 2024 ?", IntentType.QUERY_DATA),
    ("Montre-moi les charges de la copropriété", IntentType.QUERY_DATA),

    # RAG / Document search
    ("Que dit le règlement de copropriété sur les animaux ?", IntentType.SEARCH_DOCUMENTS),
    ("Trouve dans le contrat de syndic les clauses de résiliation", IntentType.SEARCH_DOCUMENTS),
    ("Qu'est-ce qui est prévu pour le parking dans les documents ?", IntentType.SEARCH_DOCUMENTS),

    # Legal queries
    ("Que dit la loi sur les assemblées générales ?", IntentType.LEGAL),
    ("Quelles sont les règles légales pour les travaux en copropriété ?", IntentType.LEGAL),
    ("Article 25 de la loi du 10 juillet 1965", IntentType.LEGAL),

    # Email actions
    ("Envoie un email aux copropriétaires pour les travaux", IntentType.SEND_EMAIL),
    ("Rédige un mail pour convoquer l'AG", IntentType.SEND_EMAIL),
    ("Prépare une lettre de relance pour les impayés", IntentType.SEND_EMAIL),

    # Web search
    ("Tarifs des électriciens à Paris", IntentType.WEB_SEARCH),
    ("Trouve-moi des entreprises de ravalement", IntentType.WEB_SEARCH),
    ("Prix moyen d'un ascenseur en 2024", IntentType.WEB_SEARCH),

    # Workflow triggers
    ("Lance le processus de relance des impayés", IntentType.TRIGGER_WORKFLOW),
    ("Déclenche l'envoi des appels de fonds", IntentType.TRIGGER_WORKFLOW),

    # Digest
    ("Fais-moi un résumé des emails de la semaine", IntentType.GENERATE_DIGEST),
    ("Quels emails urgents ai-je reçus ?", IntentType.GENERATE_DIGEST),

    # General questions
    ("Comment fonctionne une copropriété ?", IntentType.GENERAL_QUESTION),
    ("Explique-moi le rôle du syndic", IntentType.GENERAL_QUESTION),
    ("Bonjour, comment vas-tu ?", IntentType.GENERAL_QUESTION),
]

async def test_classifier():
    print("=" * 70)
    print("TEST DU LLM INTENT CLASSIFIER")
    print("=" * 70)

    correct = 0
    total = len(TEST_QUERIES)
    results = []

    for query, expected_intent in TEST_QUERIES:
        print(f"\n📝 Query: {query[:50]}...")
        print(f"   Expected: {expected_intent.value}")

        try:
            result = await classify_intent_with_llm(query)

            # Access Pydantic model attributes directly
            detected = result.intent.value
            confidence = result.confidence
            method = getattr(result, 'classification_method', 'llm')

            is_correct = detected == expected_intent.value
            status = "✅" if is_correct else "❌"

            print(f"   Detected: {detected} ({confidence:.0%}) via {method}")
            print(f"   Status: {status}")

            if is_correct:
                correct += 1

            results.append({
                "query": query,
                "expected": expected_intent.value,
                "detected": detected,
                "confidence": confidence,
                "method": method,
                "correct": is_correct
            })

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "query": query,
                "expected": expected_intent.value,
                "detected": "ERROR",
                "confidence": 0,
                "method": "error",
                "correct": False
            })

    # Summary
    print("\n" + "=" * 70)
    print("RÉSUMÉ DES TESTS")
    print("=" * 70)
    accuracy = correct / total * 100
    print(f"\n✅ Correct: {correct}/{total} ({accuracy:.1f}%)")

    # Show failures
    failures = [r for r in results if not r["correct"]]
    if failures:
        print(f"\n❌ Échecs ({len(failures)}):")
        for f in failures:
            print(f"   - {f['query'][:40]}...")
            print(f"     Expected: {f['expected']}, Got: {f['detected']}")

    # Analysis by intent type
    print("\n📊 Par type d'intention:")
    intent_stats = {}
    for r in results:
        expected = r["expected"]
        if expected not in intent_stats:
            intent_stats[expected] = {"total": 0, "correct": 0}
        intent_stats[expected]["total"] += 1
        if r["correct"]:
            intent_stats[expected]["correct"] += 1

    for intent, stats in sorted(intent_stats.items()):
        acc = stats["correct"] / stats["total"] * 100
        print(f"   {intent}: {stats['correct']}/{stats['total']} ({acc:.0f}%)")

    return accuracy

if __name__ == "__main__":
    accuracy = asyncio.run(test_classifier())
    print(f"\n🎯 Accuracy globale: {accuracy:.1f}%")
