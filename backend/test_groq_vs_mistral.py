"""
Test Groq (Mixtral-8x7B) vs Mistral for Intent Classification
Benchmark: Speed + Accuracy

Usage:
1. Set GROQ_API_KEY in .env (get from https://console.groq.com)
2. Run: python test_groq_vs_mistral.py
"""
import asyncio
import os
import sys
import time
import json
import re
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

sys.path.insert(0, '.')
load_dotenv()

# Check for Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("=" * 70)
    print("❌ GROQ_API_KEY non configurée!")
    print("=" * 70)
    print("\n1. Va sur https://console.groq.com et crée une clé API (gratuite)")
    print("2. Ajoute dans backend/.env:")
    print("   GROQ_API_KEY=gsk_xxxxxxxxxxxx")
    print("\n3. Relance le test")
    sys.exit(1)

# Now import after dotenv
from app.services.agents.llm_intent_classifier import (
    classify_intent_with_llm,
    CLASSIFIER_SYSTEM_PROMPT,
    _build_user_prompt,
    _parse_llm_response,
    _map_to_intent_classification
)
from app.models.intent import IntentType

# ============================================================================
# GROQ CLIENT
# ============================================================================

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    print("Installing groq package...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "groq", "-q"])
    from groq import Groq
    GROQ_AVAILABLE = True

groq_client = Groq(api_key=GROQ_API_KEY)


async def classify_with_groq(
    query: str,
    conversation_history: List[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classify intent using Groq + Mixtral-8x7B
    """
    user_prompt = _build_user_prompt(query, conversation_history, context)

    start = time.time()

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Ultra-fast, good for classification
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )

        duration_ms = (time.time() - start) * 1000
        response_text = response.choices[0].message.content

        # Parse response
        parsed = _parse_llm_response(response_text)

        if parsed:
            classification = _map_to_intent_classification(parsed, query)
            return {
                "intent": classification.intent.value,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
                "duration_ms": duration_ms,
                "success": True
            }
        else:
            return {
                "intent": "error",
                "confidence": 0,
                "reasoning": f"Parse failed: {response_text[:100]}",
                "duration_ms": duration_ms,
                "success": False
            }

    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        return {
            "intent": "error",
            "confidence": 0,
            "reasoning": str(e),
            "duration_ms": duration_ms,
            "success": False
        }


async def classify_with_mistral(
    query: str,
    conversation_history: List[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Classify intent using existing Mistral implementation
    """
    start = time.time()

    try:
        result = await classify_intent_with_llm(query, conversation_history, context)
        duration_ms = (time.time() - start) * 1000

        return {
            "intent": result.intent.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "duration_ms": duration_ms,
            "success": True
        }
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        return {
            "intent": "error",
            "confidence": 0,
            "reasoning": str(e),
            "duration_ms": duration_ms,
            "success": False
        }


# ============================================================================
# TEST CASES
# ============================================================================

BASIC_TESTS = [
    ("Combien de copropriétaires aux Mimosas ?", "query_data"),
    ("Que dit le règlement de copropriété sur les animaux ?", "search_documents"),
    ("Que dit la loi sur les assemblées générales ?", "legal"),
    ("Envoie un email aux copropriétaires pour les travaux", "send_email"),
    ("Tarifs des électriciens à Paris", "web_search"),
    ("URGENT: fuite d'eau apt 12", "trigger_workflow"),
    ("Résumé des emails de la semaine", "generate_digest"),
    ("Comment fonctionne une copropriété ?", "general_question"),
]

CASCADING_TESTS = [
    {
        "name": "SQL → Follow-up",
        "history": [
            {"role": "user", "content": "Combien de copropriétaires aux Mimosas ?"},
            {"role": "assistant", "content": "Il y a 45 copropriétaires aux Mimosas."}
        ],
        "context": {"last_intent": "query_data"},
        "query": "Et ceux qui ont des impayés ?",
        "expected": "query_data"
    },
    {
        "name": "RAG → Follow-up",
        "history": [
            {"role": "user", "content": "Que dit le règlement sur les animaux ?"},
            {"role": "assistant", "content": "Le règlement interdit les animaux dangereux..."}
        ],
        "context": {"last_intent": "search_documents"},
        "query": "Et pour les chiens ?",
        "expected": "search_documents"
    },
    {
        "name": "Email → Confirmation",
        "history": [
            {"role": "user", "content": "Envoie un email aux copropriétaires pour les travaux"},
            {"role": "assistant", "content": "J'ai préparé l'email suivant: ..."}
        ],
        "context": {"last_intent": "send_email"},
        "query": "Oui, envoie-le",
        "expected": "send_email"
    },
]


# ============================================================================
# BENCHMARK
# ============================================================================

async def run_benchmark():
    print("=" * 70)
    print("🏎️  BENCHMARK: GROQ (Mixtral-8x7B) vs MISTRAL")
    print("=" * 70)

    results = {
        "groq": {"times": [], "correct": 0, "total": 0, "errors": 0},
        "mistral": {"times": [], "correct": 0, "total": 0, "errors": 0}
    }

    # === BASIC TESTS ===
    print("\n📝 TESTS BASIQUES (8 queries)")
    print("-" * 70)

    for query, expected in BASIC_TESTS:
        print(f"\n🔹 Query: {query[:50]}...")
        print(f"   Expected: {expected}")

        # Groq
        groq_result = await classify_with_groq(query)
        groq_correct = groq_result["intent"] == expected
        results["groq"]["total"] += 1
        if groq_result["success"]:
            results["groq"]["times"].append(groq_result["duration_ms"])
            if groq_correct:
                results["groq"]["correct"] += 1
        else:
            results["groq"]["errors"] += 1

        # Mistral
        mistral_result = await classify_with_mistral(query)
        mistral_correct = mistral_result["intent"] == expected
        results["mistral"]["total"] += 1
        if mistral_result["success"]:
            results["mistral"]["times"].append(mistral_result["duration_ms"])
            if mistral_correct:
                results["mistral"]["correct"] += 1
        else:
            results["mistral"]["errors"] += 1

        # Display
        g_status = "✅" if groq_correct else "❌"
        m_status = "✅" if mistral_correct else "❌"

        print(f"   Groq:    {g_status} {groq_result['intent']:<20} ({groq_result['duration_ms']:.0f}ms)")
        print(f"   Mistral: {m_status} {mistral_result['intent']:<20} ({mistral_result['duration_ms']:.0f}ms)")

    # === CASCADING TESTS ===
    print("\n\n🔗 TESTS CASCADING (3 queries)")
    print("-" * 70)

    for test in CASCADING_TESTS:
        print(f"\n🔹 {test['name']}")
        print(f"   Query: \"{test['query']}\"")
        print(f"   Expected: {test['expected']}")

        # Groq
        groq_result = await classify_with_groq(
            test['query'],
            test['history'],
            test['context']
        )
        groq_correct = groq_result["intent"] == test["expected"]
        results["groq"]["total"] += 1
        if groq_result["success"]:
            results["groq"]["times"].append(groq_result["duration_ms"])
            if groq_correct:
                results["groq"]["correct"] += 1
        else:
            results["groq"]["errors"] += 1

        # Mistral
        mistral_result = await classify_with_mistral(
            test['query'],
            test['history'],
            test['context']
        )
        mistral_correct = mistral_result["intent"] == test["expected"]
        results["mistral"]["total"] += 1
        if mistral_result["success"]:
            results["mistral"]["times"].append(mistral_result["duration_ms"])
            if mistral_correct:
                results["mistral"]["correct"] += 1
        else:
            results["mistral"]["errors"] += 1

        g_status = "✅" if groq_correct else "❌"
        m_status = "✅" if mistral_correct else "❌"

        print(f"   Groq:    {g_status} {groq_result['intent']:<20} ({groq_result['duration_ms']:.0f}ms)")
        print(f"   Mistral: {m_status} {mistral_result['intent']:<20} ({mistral_result['duration_ms']:.0f}ms)")

    # === SUMMARY ===
    print("\n\n" + "=" * 70)
    print("📊 RÉSUMÉ")
    print("=" * 70)

    for provider in ["groq", "mistral"]:
        r = results[provider]
        times = r["times"]
        if times:
            avg = sum(times) / len(times)
            min_t = min(times)
            max_t = max(times)
        else:
            avg = min_t = max_t = 0

        accuracy = (r["correct"] / r["total"] * 100) if r["total"] > 0 else 0

        print(f"\n{provider.upper():}")
        print(f"   ⏱️  Temps moyen: {avg:.0f}ms (min: {min_t:.0f}ms, max: {max_t:.0f}ms)")
        print(f"   🎯 Précision: {r['correct']}/{r['total']} ({accuracy:.0f}%)")
        if r["errors"] > 0:
            print(f"   ❌ Erreurs: {r['errors']}")

    # === COMPARISON ===
    print("\n" + "-" * 70)

    groq_avg = sum(results["groq"]["times"]) / len(results["groq"]["times"]) if results["groq"]["times"] else 0
    mistral_avg = sum(results["mistral"]["times"]) / len(results["mistral"]["times"]) if results["mistral"]["times"] else 0

    groq_acc = results["groq"]["correct"] / results["groq"]["total"] * 100 if results["groq"]["total"] > 0 else 0
    mistral_acc = results["mistral"]["correct"] / results["mistral"]["total"] * 100 if results["mistral"]["total"] > 0 else 0

    speedup = mistral_avg / groq_avg if groq_avg > 0 else 0

    print(f"\n🏆 GROQ est {speedup:.1f}x plus rapide que Mistral")
    print(f"   Groq: {groq_avg:.0f}ms vs Mistral: {mistral_avg:.0f}ms")

    if groq_acc >= mistral_acc:
        print(f"   ✅ Groq maintient la précision ({groq_acc:.0f}% vs {mistral_acc:.0f}%)")
    else:
        print(f"   ⚠️  Groq légèrement moins précis ({groq_acc:.0f}% vs {mistral_acc:.0f}%)")

    # === RECOMMENDATION ===
    print("\n" + "=" * 70)
    print("💡 RECOMMANDATION")
    print("=" * 70)

    if groq_avg < 300 and groq_acc >= 90:
        print("\n✅ GROQ est un excellent choix!")
        print("   - Ultra-rapide (<300ms)")
        print("   - Précision maintenue (≥90%)")
        print("   - Coût très faible")
        print("\n   → Recommandation: Utiliser Groq comme provider principal")
    elif groq_avg < 500 and groq_acc >= 85:
        print("\n✅ GROQ est un bon choix")
        print("   - Rapide (<500ms)")
        print("   - Précision acceptable (≥85%)")
        print("\n   → Recommandation: Utiliser Groq pour les cas simples, Mistral pour les cascades complexes")
    else:
        print("\n⚠️  GROQ a des limites sur ce use case")
        print(f"   - Temps: {groq_avg:.0f}ms")
        print(f"   - Précision: {groq_acc:.0f}%")
        print("\n   → Recommandation: Garder Mistral ou tester d'autres modèles Groq")

    return results


if __name__ == "__main__":
    asyncio.run(run_benchmark())
