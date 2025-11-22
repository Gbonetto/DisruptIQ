"""
End-to-End API Test for Legal Agent Standardization

Tests the complete flow via the /chat/stream endpoint:
1. Legal query is sent to orchestrator
2. Orchestrator passes thought_stream to Legal Agent
3. Chain of Thought is displayed in real-time (SSE events)
4. Response has standardized sources format (like RAG Agent)
"""

import requests
import json
import time


def test_legal_agent_e2e():
    """Test Legal Agent via real HTTP API call"""

    print("=" * 100)
    print("LEGAL AGENT E2E TEST - Chain of Thought & Standardized Sources")
    print("=" * 100)

    # Test configuration
    BASE_URL = "http://localhost:8000"
    ENDPOINT = f"{BASE_URL}/api/assistant-v2/chat/stream"

    # Legal query for jurisprudence
    query = "Quelle est la jurisprudence sur les charges de copropriété ?"

    print(f"\n🔍 Query: {query}")
    print(f"📡 Endpoint: {ENDPOINT}")

    # Prepare request (GET with query params)
    conversation_id = "test_legal_e2e_" + str(int(time.time()))

    print("\n📤 Sending request...")

    try:
        # Send SSE request (GET method)
        response = requests.get(
            ENDPOINT,
            params={
                "message": query,
                "conversation_id": conversation_id,
                "active_mode": "legal"
            },
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=90
        )

        print(f"✅ Response status: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Error: {response.text}")
            return False

        # Parse SSE stream
        thoughts_collected = []
        final_answer = None
        sources_collected = []

        print("\n" + "=" * 100)
        print("📺 STREAMING EVENTS:")
        print("=" * 100)

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')

                # Parse SSE format
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove 'data: ' prefix

                    if data_str.strip() == '[DONE]':
                        print("\n✅ Stream completed")
                        break

                    try:
                        event_data = json.loads(data_str)
                        event_type = event_data.get('type')

                        if event_type == 'thought':
                            # Chain of Thought event
                            thought = event_data.get('thought', {})
                            thoughts_collected.append(thought)

                            thought_type = thought.get('type', 'unknown')
                            title = thought.get('title', '')
                            agent = thought.get('agent', '')
                            progress = thought.get('progress', 0)

                            # Display thought
                            print(f"\n💭 [{thought_type.upper()}] {title}")
                            print(f"   Agent: {agent}, Progress: {progress:.0%}")

                        elif event_type == 'answer':
                            # Final answer
                            final_answer = event_data.get('answer', '')
                            print(f"\n📝 FINAL ANSWER:\n{final_answer[:300]}...")

                        elif event_type == 'sources':
                            # Sources
                            sources_collected = event_data.get('sources', [])
                            print(f"\n🔗 SOURCES: {len(sources_collected)} sources received")

                    except json.JSONDecodeError:
                        pass

        # Validation
        print("\n" + "=" * 100)
        print("VALIDATION RESULTS:")
        print("=" * 100)

        validations = {
            "Thoughts collected": len(thoughts_collected) > 0,
            "Legal Agent thoughts": any('legal' in t.get('agent', '').lower() for t in thoughts_collected),
            "Final answer received": final_answer is not None,
            "Sources collected": len(sources_collected) > 0,
            "Sources have 'type'": all('type' in s for s in sources_collected),
            "Sources have 'id'": all('id' in s for s in sources_collected),
            "Sources have 'confidence'": all('confidence' in s for s in sources_collected),
            "Uses numbered citations [1]": '[1]' in (final_answer or '')
        }

        all_passed = True
        for check, passed in validations.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check}: {passed}")
            if not passed:
                all_passed = False

        # Display collected thoughts
        if thoughts_collected:
            print(f"\n📊 Chain of Thought Summary ({len(thoughts_collected)} thoughts):")
            for i, thought in enumerate(thoughts_collected, 1):
                agent = thought.get('agent', 'unknown')
                thought_type = thought.get('type', 'unknown')
                title = thought.get('title', '')[:60]
                print(f"   {i}. [{agent}] {thought_type}: {title}...")

        # Display sources
        if sources_collected:
            print(f"\n🔗 Sources Summary ({len(sources_collected)} sources):")
            for i, source in enumerate(sources_collected, 1):
                source_type = source.get('type', 'unknown')
                title = source.get('title', '')[:50]
                confidence = source.get('confidence', 0)
                print(f"   {i}. [{source_type}] {title}... (confidence: {confidence:.0%})")

        print("\n" + "=" * 100)
        if all_passed:
            print("🎉 SUCCESS - Legal Agent E2E test passed!")
            print("   ✓ Chain of Thought displayed in real-time")
            print("   ✓ Sources in standardized format")
            print("   ✓ Response uses numbered citations")
        else:
            print("⚠️  FAILURE - Some validations failed")
        print("=" * 100)

        return all_passed

    except requests.exceptions.ConnectionError:
        print("❌ Connection error - Is the backend server running?")
        print("   Run: docker-compose up backend")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_legal_agent_e2e()
    exit(0 if success else 1)
