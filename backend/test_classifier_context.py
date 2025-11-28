"""
Test LLM Classifier - Context & Performance
Tests:
1. Speed / Performance
2. Context understanding
3. Cascading prompts (follow-ups)
"""
import asyncio
import sys
import time
sys.path.insert(0, '.')

from app.services.agents.llm_intent_classifier import classify_intent_with_llm
from app.models.intent import IntentType

# =============================================================================
# TEST 1: CASCADING PROMPTS (Follow-up questions)
# =============================================================================

CASCADING_TESTS = [
    {
        "name": "SQL → Follow-up",
        "history": [
            {"role": "user", "content": "Combien de copropriétaires aux Mimosas ?"},
            {"role": "assistant", "content": "Il y a 45 copropriétaires aux Mimosas."}
        ],
        "context": {"last_intent": "query_data"},  # NEW: Pass last_intent
        "query": "Et ceux qui ont des impayés ?",  # Follow-up without context = ambiguous
        "expected": IntentType.QUERY_DATA,  # Should understand we're still asking SQL
        "reason": "Should understand 'ceux' refers to copropriétaires"
    },
    {
        "name": "RAG → Follow-up",
        "history": [
            {"role": "user", "content": "Que dit le règlement sur les animaux ?"},
            {"role": "assistant", "content": "Le règlement interdit les animaux dangereux..."}
        ],
        "context": {"last_intent": "search_documents"},  # NEW: Pass last_intent
        "query": "Et pour les chiens ?",
        "expected": IntentType.SEARCH_DOCUMENTS,  # Still RAG context
        "reason": "Should understand we're still in document context"
    },
    {
        "name": "Email → Confirmation",
        "history": [
            {"role": "user", "content": "Envoie un email aux copropriétaires pour les travaux"},
            {"role": "assistant", "content": "J'ai préparé l'email suivant: ..."}
        ],
        "context": {"last_intent": "send_email"},  # NEW
        "query": "Oui, envoie-le",
        "expected": IntentType.SEND_EMAIL,  # Should confirm email action
        "reason": "Should understand this is a confirmation of email"
    },
    {
        "name": "Mixed context",
        "history": [
            {"role": "user", "content": "Qui est M. Dupont ?"},
            {"role": "assistant", "content": "M. Dupont est le copropriétaire du lot 12..."}
        ],
        "context": {"last_intent": "query_data", "last_query_entities": [{"name": "M. Dupont"}]},  # NEW
        "query": "Envoie-lui un email pour le dégât des eaux",
        "expected": IntentType.SEND_EMAIL,  # Action on entity from context
        "reason": "Should understand 'lui' refers to M. Dupont"
    },
    {
        "name": "Implicit reference",
        "history": [
            {"role": "user", "content": "Liste des plombiers disponibles"},
            {"role": "assistant", "content": "Voici 3 plombiers: 1. ABC Plomberie, 2. ..."}
        ],
        "context": {"last_intent": "query_data"},  # NEW
        "query": "Contacte le premier",
        "expected": IntentType.SEND_EMAIL,  # Action on implicit entity
        "reason": "Should understand 'le premier' from context"
    },
]


async def test_cascading():
    print("\n" + "=" * 70)
    print("TEST CASCADING PROMPTS (Follow-ups with context)")
    print("=" * 70)

    correct = 0
    results = []

    for test in CASCADING_TESTS:
        print(f"\n📝 {test['name']}")
        print(f"   History: {test['history'][-1]['content'][:40]}...")
        print(f"   Query: \"{test['query']}\"")
        print(f"   Expected: {test['expected'].value}")

        start = time.time()
        result = await classify_intent_with_llm(
            test['query'],
            conversation_history=test['history'],
            context=test.get('context')  # NEW: Pass context with last_intent
        )
        duration = (time.time() - start) * 1000

        detected = result.intent.value
        is_correct = detected == test['expected'].value
        status = "✅" if is_correct else "❌"

        print(f"   Detected: {detected} ({result.confidence:.0%}) [{duration:.0f}ms]")
        print(f"   {status} {test['reason']}")

        if is_correct:
            correct += 1
        results.append({"test": test['name'], "correct": is_correct, "detected": detected})

    print(f"\n🎯 Cascading: {correct}/{len(CASCADING_TESTS)} ({correct/len(CASCADING_TESTS)*100:.0f}%)")
    return correct, len(CASCADING_TESTS), results


# =============================================================================
# TEST 2: SPEED / PERFORMANCE
# =============================================================================

async def test_performance():
    print("\n" + "=" * 70)
    print("TEST PERFORMANCE (Speed)")
    print("=" * 70)

    queries = [
        "Combien de copropriétaires ?",
        "Que dit le contrat de syndic ?",
        "Envoie un email aux copropriétaires",
        "Tarifs électriciens Paris",
        "Comment fonctionne une AG ?"
    ]

    times = []
    for query in queries:
        start = time.time()
        await classify_intent_with_llm(query)
        duration = (time.time() - start) * 1000
        times.append(duration)
        print(f"   {query[:40]}... → {duration:.0f}ms")

    avg = sum(times) / len(times)
    min_t = min(times)
    max_t = max(times)

    print(f"\n📊 Stats:")
    print(f"   Average: {avg:.0f}ms")
    print(f"   Min: {min_t:.0f}ms")
    print(f"   Max: {max_t:.0f}ms")

    return avg, min_t, max_t


# =============================================================================
# TEST 3: CONTEXT WITH STATE
# =============================================================================

async def test_context_state():
    print("\n" + "=" * 70)
    print("TEST CONTEXT STATE (Rich context)")
    print("=" * 70)

    # Test with rich context
    context = {
        "topic": "dégât des eaux",
        "pending_action": "email à rédiger",
        "last_query_entities": [
            {"name": "M. Dupont", "type": "copropriétaire"},
            {"name": "Lot 12", "type": "lot"}
        ],
        "business_context": {
            "urgency": "high",
            "incident_type": "water_damage"
        }
    }

    # Ambiguous query that needs context
    query = "Préviens le voisin du dessous"

    print(f"   Context: urgency=high, incident=water_damage, entities=[M. Dupont, Lot 12]")
    print(f"   Query: \"{query}\"")

    start = time.time()
    result = await classify_intent_with_llm(query, context=context)
    duration = (time.time() - start) * 1000

    print(f"   Detected: {result.intent.value} ({result.confidence:.0%}) [{duration:.0f}ms]")
    print(f"   Reasoning: {result.reasoning[:80]}...")

    # Should understand it's an email action in water damage context
    is_correct = result.intent == IntentType.SEND_EMAIL
    print(f"   {'✅' if is_correct else '❌'} Should be send_email (notifier quelqu'un)")

    return is_correct


# =============================================================================
# MAIN
# =============================================================================

async def main():
    print("=" * 70)
    print("LLM CLASSIFIER - CONTEXT & PERFORMANCE TESTS")
    print("=" * 70)

    # Performance test
    avg_time, _, _ = await test_performance()

    # Context state test
    context_ok = await test_context_state()

    # Cascading prompts test
    cascade_correct, cascade_total, _ = await test_cascading()

    # Summary
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    print(f"   ⏱️  Temps moyen: {avg_time:.0f}ms")
    print(f"   🔗 Cascading prompts: {cascade_correct}/{cascade_total} ({cascade_correct/cascade_total*100:.0f}%)")
    print(f"   📋 Context state: {'✅' if context_ok else '❌'}")

    if avg_time > 1500:
        print("\n⚠️  ATTENTION: Temps moyen > 1.5s - optimisation possible")
    if cascade_correct < cascade_total:
        print("\n⚠️  ATTENTION: Cascading prompts pas parfait - amélioration possible")


if __name__ == "__main__":
    asyncio.run(main())
