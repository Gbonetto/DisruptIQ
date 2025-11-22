#!/usr/bin/env python3
"""
Manual test of Legal Agent with real query to verify:
1. Chain of Thought display
2. Proper synthesis with citations
3. Correct relevance percentages
"""

import requests
import time

def test_legal_query():
    """Test legal query via SSE stream"""

    url = "http://localhost:8000/api/assistant-v2/chat/stream"
    query = "Quelle est la jurisprudence sur les charges de copropriété ?"

    params = {
        "message": query,
        "conversation_id": f"test_legal_cot_{int(time.time())}",
        "active_mode": "legal"
    }

    print("=" * 100)
    print(f"🔍 Query: {query}")
    print(f"📡 URL: {url}")
    print("=" * 100)
    print("\n📺 STREAMING EVENTS:\n")

    response = requests.get(url, params=params, stream=True, headers={"Accept": "text/event-stream"}, timeout=120)

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return

    thoughts_count = 0
    final_answer = None

    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')

            if line_str.startswith('data: '):
                data_str = line_str[6:]

                if data_str.strip() == '[DONE]':
                    print("\n✅ Stream completed\n")
                    break

                try:
                    import json
                    event = json.loads(data_str)
                    event_type = event.get('type')

                    if event_type == 'thought':
                        thoughts_count += 1
                        thought = event.get('thought', {})
                        print(f"💭 [{thought.get('type')}] {thought.get('title')}")
                        print(f"   Agent: {thought.get('agent')}, Progress: {thought.get('progress', 0):.0%}")

                    elif event_type == 'answer':
                        final_answer = event.get('answer', '')
                        print("\n" + "=" * 100)
                        print("📝 FINAL ANSWER:")
                        print("=" * 100)
                        print(final_answer)
                        print("\n" + "=" * 100)

                    elif event_type == 'sources':
                        sources = event.get('sources', [])
                        print(f"\n🔗 Sources: {len(sources)} sources")
                        for i, src in enumerate(sources[:3], 1):
                            print(f"   {i}. {src.get('title', '')[:60]}... ({src.get('confidence', 0):.0%})")

                except json.JSONDecodeError:
                    pass

    print("\n" + "=" * 100)
    print("VALIDATION:")
    print("=" * 100)

    checks = {
        "Thoughts displayed": thoughts_count > 0,
        "Multiple thoughts": thoughts_count >= 3,
        "Final answer received": final_answer is not None,
        "Has citations [1]": "[1]" in (final_answer or ""),
        "Has Sources section": "Sources (" in (final_answer or "")
    }

    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}: {passed}")

    print(f"\n📊 Total thoughts displayed: {thoughts_count}")

    if all(checks.values()):
        print("\n🎉 SUCCESS - All validations passed!")
    else:
        print("\n⚠️  PARTIAL SUCCESS - Some validations failed")

if __name__ == "__main__":
    test_legal_query()
