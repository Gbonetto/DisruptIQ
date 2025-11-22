"""
Test script to verify Legal Agent response format standardization
Tests:
1. Chain of Thought (CoT) display via ThoughtStream
2. Structured sources format (like RAG Agent)
3. Numbered citations in response text
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.agents.legal_agent import LegalAgent
from app.services.agents.thought_stream import ThoughtStream, ThoughtType


async def test_legal_agent_format():
    """Test Legal Agent with new standardized format"""

    print("=" * 80)
    print("TESTING LEGAL AGENT - Standardized Response Format")
    print("=" * 80)

    # Initialize Legal Agent
    legal_agent = LegalAgent()

    # Test 1: Jurisprudence search with ThoughtStream
    print("\n" + "=" * 80)
    print("TEST 1: Jurisprudence Search with Chain of Thought")
    print("=" * 80)

    # Create ThoughtStream to capture CoT
    thought_stream = ThoughtStream(session_id="test_legal_format_123")
    thoughts_collected = []

    # Mock thought collection
    original_add_thought = thought_stream.add_thought
    async def mock_add_thought(*args, **kwargs):
        thought_data = {
            "type": kwargs.get("thought_type", args[0] if args else None),
            "title": kwargs.get("title", args[1] if len(args) > 1 else ""),
            "content": kwargs.get("content", args[2] if len(args) > 2 else ""),
            "agent": kwargs.get("agent", ""),
            "progress": kwargs.get("progress", 0)
        }
        thoughts_collected.append(thought_data)
        print(f"\n📍 CoT Thought: [{thought_data['type']}] {thought_data['title']}")
        if thought_data['content']:
            print(f"   Content: {thought_data['content'][:100]}...")
        return await original_add_thought(*args, **kwargs)

    thought_stream.add_thought = mock_add_thought

    # Execute jurisprudence search
    query = "jurisprudence sur les charges de copropriété"
    print(f"\nQuery: {query}")

    result = await legal_agent.search_jurisprudence(
        legal_question=query,
        case_type="copropriete"
    )

    print("\n" + "-" * 80)
    print("RESULTS:")
    print("-" * 80)

    print(f"\n✅ Success: {result.get('success')}")
    print(f"📊 Confidence: {result.get('confidence')}")
    print(f"📚 Cases found: {len(result.get('cases', []))}")
    print(f"🔗 Structured sources: {len(result.get('sources', []))}")

    # Check if sources are in standard format
    if result.get('sources'):
        print("\n📋 Source Structure (first source):")
        first_source = result['sources'][0]
        print(f"   - Type: {first_source.get('type')}")
        print(f"   - ID: {first_source.get('id')}")
        print(f"   - Title: {first_source.get('title', '')[:60]}...")
        print(f"   - Confidence: {first_source.get('confidence')}")
        print(f"   - Has metadata: {bool(first_source.get('metadata'))}")

    # Display formatted response
    print("\n" + "-" * 80)
    print("FORMATTED RESPONSE:")
    print("-" * 80)
    print(result.get('summary', 'No summary')[:500])
    print("...\n")

    # Test 2: Verify ThoughtStream integration
    print("\n" + "=" * 80)
    print("TEST 2: Chain of Thought Verification")
    print("=" * 80)

    if thoughts_collected:
        print(f"✅ {len(thoughts_collected)} thoughts collected during execution:")
        for i, thought in enumerate(thoughts_collected, 1):
            print(f"\n   {i}. [{thought['type']}] {thought['title']}")
            print(f"      Agent: {thought['agent']}, Progress: {thought['progress']:.0%}")
    else:
        print("❌ No thoughts collected - ThoughtStream may not be integrated")

    # Test 3: Verify response format matches RAG Agent
    print("\n" + "=" * 80)
    print("TEST 3: Format Compatibility Check")
    print("=" * 80)

    checks = {
        "Has 'success' field": 'success' in result,
        "Has 'summary' field": 'summary' in result,
        "Has 'sources' field": 'sources' in result,
        "Sources is list": isinstance(result.get('sources'), list),
        "Each source has 'type'": all('type' in s for s in result.get('sources', [])),
        "Each source has 'id'": all('id' in s for s in result.get('sources', [])),
        "Each source has 'confidence'": all('confidence' in s for s in result.get('sources', [])),
        "Response uses [1] citations": '[1]' in result.get('summary', ''),
        "Response has Sources section": 'Sources (' in result.get('summary', '')
    }

    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {passed}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Legal Agent format is standardized!")
    else:
        print("⚠️  SOME TESTS FAILED - Review format standardization")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_legal_agent_format())
    sys.exit(0 if success else 1)
