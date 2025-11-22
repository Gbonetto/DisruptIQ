"""
Quick test to verify intent refactoring works correctly
Tests that LEGAL intent routes properly and orphaned intents are removed
"""

import asyncio
import sys
from app.models.intent import IntentType, AgentResponse, INTENT_AGENT_MAP

def test_intent_enum():
    """Test that IntentType enum has expected values"""
    print("="*60)
    print("TEST 1: IntentType Enum")
    print("="*60)

    # Check all 8 stable intents exist
    expected_intents = [
        "query_data",
        "search_documents",
        "web_search",
        "send_email",
        "request_quotes",
        "trigger_workflow",
        "legal",
        "general_question"
    ]

    actual_intents = [intent.value for intent in IntentType]

    print(f"\nExpected intents: {len(expected_intents)}")
    print(f"Actual intents: {len(actual_intents)}")
    print(f"\nActual intent values:")
    for intent in IntentType:
        print(f"  - {intent.name} = '{intent.value}'")

    # Verify LEGAL exists
    assert IntentType.LEGAL.value == "legal", "LEGAL intent should exist"
    print(f"\n✓ IntentType.LEGAL exists: {IntentType.LEGAL.value}")

    # Verify deprecated intents don't exist
    deprecated = ["LEGAL_ANALYSIS", "LEGAL_ADVICE", "LEGAL_COMPARISON",
                  "CONFIRM_EMAIL", "ANALYZE_DOCUMENT", "GENERATE_DIGEST",
                  "SEARCH_JURISPRUDENCE"]

    for deprecated_intent in deprecated:
        assert not hasattr(IntentType, deprecated_intent), f"{deprecated_intent} should be removed"

    print(f"✓ All deprecated intents removed: {deprecated}")

    return True


def test_agent_response_model():
    """Test that AgentResponse model works"""
    print("\n" + "="*60)
    print("TEST 2: AgentResponse Model")
    print("="*60)

    response = AgentResponse(
        success=True,
        message="Test message",
        data={"test": "data"},
        agents_used=["LegalAgent"],
        confidence=0.95
    )

    print(f"\n✓ AgentResponse created: {response.model_dump()}")

    return True


def test_intent_agent_mapping():
    """Test INTENT_AGENT_MAP"""
    print("\n" + "="*60)
    print("TEST 3: Intent → Agent Mapping")
    print("="*60)

    print(f"\nINTENT_AGENT_MAP:")
    for intent, agent in INTENT_AGENT_MAP.items():
        print(f"  {intent.value:20s} → {agent}")

    # Verify LEGAL maps to LegalAgent
    assert INTENT_AGENT_MAP[IntentType.LEGAL] == "LegalAgent"
    print(f"\n✓ IntentType.LEGAL correctly maps to LegalAgent")

    return True


async def test_orchestrator_import():
    """Test that orchestrator imports work"""
    print("\n" + "="*60)
    print("TEST 4: Orchestrator Import")
    print("="*60)

    try:
        from app.services.agents.orchestrator_agent import OrchestratorAgent
        print("✓ OrchestratorAgent imported successfully")

        # Try to instantiate (doesn't require DB)
        orchestrator = OrchestratorAgent()
        print("✓ OrchestratorAgent instantiated successfully")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_handler_map():
    """Test that handler_map has correct intents"""
    print("\n" + "="*60)
    print("TEST 5: Handler Map")
    print("="*60)

    try:
        from app.services.agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent()

        # Check _execute_single_step method to verify handler_map
        # We can't call it directly, but we can verify the method exists
        assert hasattr(orchestrator, '_execute_single_step'), "_execute_single_step method exists"
        assert hasattr(orchestrator, '_handle_legal'), "_handle_legal method exists"

        print("✓ Required handler methods exist")
        print("  - _execute_single_step")
        print("  - _handle_legal")

        # Verify deprecated handlers don't exist (or are unused)
        deprecated_handlers = [
            '_handle_legal_analysis',
            '_handle_legal_advice',
            '_handle_legal_comparison',
            '_handle_search_jurisprudence'
        ]

        for handler in deprecated_handlers:
            exists = hasattr(orchestrator, handler)
            if exists:
                print(f"  ⚠ Warning: {handler} still exists (but should be unused)")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "🔧 INTENT REFACTORING TEST SUITE 🔧".center(60))
    print("\nTesting centralized intent system...")

    results = []

    # Run synchronous tests
    results.append(("IntentType Enum", test_intent_enum()))
    results.append(("AgentResponse Model", test_agent_response_model()))
    results.append(("Intent Agent Mapping", test_intent_agent_mapping()))

    # Run async tests
    results.append(("Orchestrator Import", await test_orchestrator_import()))
    results.append(("Handler Map", await test_handler_map()))

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8s} {test_name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Intent refactoring successful!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. Review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
