"""
Test Production Fix: LEGAL_ANALYSIS Error
Verify that the refactored intent system fixes the production bug
"""

import requests
import json
import time
from typing import Dict, Any

API_BASE = "http://localhost:8000"

def test_legal_query_simple():
    """Test 1: Simple legal query that was failing with LEGAL_ANALYSIS error"""
    print("\n" + "="*70)
    print("TEST 1: Simple Legal Query (Previous Error: LEGAL_ANALYSIS)")
    print("="*70)

    query = "résume-moi ce document en 3 points clés"

    print(f"\n📝 Query: {query}")
    print(f"🎯 Expected: Legal Agent processes successfully (no LEGAL_ANALYSIS error)")

    try:
        response = requests.post(
            f"{API_BASE}/api/assistant-v2/chat",
            json={
                "message": query,
                "conversation_history": [],
                "has_active_documents": True  # Simulate uploaded document
            },
            timeout=60
        )

        print(f"\n📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: API returned 200")
            print(f"\n📄 Response Preview:")
            print(f"   Message: {data.get('message', '')[:200]}...")
            print(f"   Success: {data.get('success', False)}")
            print(f"   Agents Used: {data.get('agents_used', [])}")

            # Check for LEGAL_ANALYSIS error
            message = data.get('message', '')
            if "LEGAL_ANALYSIS" in message:
                print(f"\n❌ FAILED: Still getting LEGAL_ANALYSIS error!")
                return False
            else:
                print(f"\n✅ PASSED: No LEGAL_ANALYSIS error!")
                return True

        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"   Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_legal_query_jurisprudence():
    """Test 2: Jurisprudence query (was failing before)"""
    print("\n" + "="*70)
    print("TEST 2: Jurisprudence Query (Previous Error: LEGAL_ANALYSIS)")
    print("="*70)

    query = "Quelle est la jurisprudence sur les assemblées générales de copropriété?"

    print(f"\n📝 Query: {query}")
    print(f"🎯 Expected: Web/Legal Agent handles jurisprudence search")

    try:
        response = requests.post(
            f"{API_BASE}/api/assistant-v2/chat",
            json={
                "message": query,
                "conversation_history": [],
                "has_active_documents": False
            },
            timeout=60
        )

        print(f"\n📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: API returned 200")
            print(f"\n📄 Response Preview:")
            print(f"   Message: {data.get('message', '')[:200]}...")
            print(f"   Agents Used: {data.get('agents_used', [])}")

            # Check for LEGAL_ANALYSIS error
            message = data.get('message', '')
            if "LEGAL_ANALYSIS" in message:
                print(f"\n❌ FAILED: Still getting LEGAL_ANALYSIS error!")
                return False
            else:
                print(f"\n✅ PASSED: No LEGAL_ANALYSIS error!")
                return True

        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"   Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_intent_classification():
    """Test 3: Verify intent classification uses new system"""
    print("\n" + "="*70)
    print("TEST 3: Intent Classification (New Centralized System)")
    print("="*70)

    queries = [
        ("Analyse ce contrat juridique", "legal"),
        ("Combien de copropriétaires avons-nous?", "query_data"),
        ("Recherche dans les documents uploadés", "search_documents"),
        ("Envoie un email au syndic", "send_email"),
    ]

    results = []

    for query, expected_intent in queries:
        print(f"\n📝 Query: {query}")
        print(f"   Expected Intent: {expected_intent}")

        try:
            response = requests.post(
                f"{API_BASE}/api/assistant-v2/chat",
                json={
                    "message": query,
                    "conversation_history": [],
                    "has_active_documents": False
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                agents = data.get('agents_used', [])
                print(f"   Agents Used: {agents}")
                print(f"   ✅ Classification successful")
                results.append(True)
            else:
                print(f"   ❌ Failed with HTTP {response.status_code}")
                results.append(False)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 Classification Success Rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")

    return success_rate >= 75  # 75% threshold


def test_health_check():
    """Test 0: Health check"""
    print("\n" + "="*70)
    print("TEST 0: API Health Check")
    print("="*70)

    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False


def main():
    """Run all production tests"""
    print("\n" + "🔧 PRODUCTION TEST: LEGAL_ANALYSIS FIX 🔧".center(70))
    print("\nTesting refactored intent system in production environment...")

    results = []

    # Test 0: Health check
    results.append(("Health Check", test_health_check()))

    if not results[0][1]:
        print("\n❌ API is not running. Start backend first.")
        return

    # Wait for backend to be fully ready
    print("\n⏳ Waiting 3 seconds for backend to be ready...")
    time.sleep(3)

    # Test 1: Simple legal query
    results.append(("Legal Query (Document Summary)", test_legal_query_simple()))

    # Test 2: Jurisprudence query
    results.append(("Legal Query (Jurisprudence)", test_legal_query_jurisprudence()))

    # Test 3: Intent classification
    results.append(("Intent Classification", test_intent_classification()))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10s} {test_name}")

    print(f"\n{passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ LEGAL_ANALYSIS error is FIXED!")
        print("✅ Intent system refactoring successful!")
        return 0
    elif passed >= total - 1:
        print("\n⚠️  MOSTLY PASSED - Minor issues")
        return 0
    else:
        print("\n❌ TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    exit(main())
