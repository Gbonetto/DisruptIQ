"""
Test script for Streaming Chain of Thoughts
Tests the SSE streaming endpoint
"""

import asyncio
import httpx
import json
from urllib.parse import urlencode


async def test_streaming():
    """Test the streaming Chain of Thoughts endpoint"""

    base_url = "http://localhost:8000"

    print("=" * 70)
    print("🧠 TESTING STREAMING CHAIN OF THOUGHTS")
    print("=" * 70)

    # Test 1: Simple test endpoint
    print("\n" + "=" * 70)
    print("TEST 1: Simple Streaming Test")
    print("=" * 70)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream('GET', f"{base_url}/api/assistant-v2/chat/stream/test") as response:
                print(f"✅ Connection established: {response.status_code}")
                print("Receiving events...\n")

                async for line in response.aiter_lines():
                    if line.startswith('event:'):
                        print(f"📡 {line}")
                    elif line.startswith('data:'):
                        print(f"   {line}")
                        print()
    except Exception as e:
        print(f"❌ Error: {str(e)}")

    # Test 2: Real assistant query with streaming
    print("\n" + "=" * 70)
    print("TEST 2: Assistant Query with Chain of Thoughts")
    print("=" * 70)

    test_query = "Combien de copropriétaires avons-nous en tout?"
    print(f"Query: {test_query}\n")

    try:
        params = {
            'message': test_query,
            'conversation_history': json.dumps([])
        }
        url = f"{base_url}/api/assistant-v2/chat/stream?{urlencode(params)}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream('GET', url) as response:
                print(f"✅ Connection established: {response.status_code}")
                print("Receiving thoughts and response...\n")

                thought_count = 0

                async for line in response.aiter_lines():
                    if line.startswith('event:'):
                        event_type = line.split(':', 1)[1].strip()
                        print(f"\n{'='*50}")
                        print(f"📡 EVENT: {event_type}")
                        print('='*50)
                    elif line.startswith('data:'):
                        data_str = line.split(':', 1)[1].strip()
                        try:
                            data = json.loads(data_str)

                            # Format thought events
                            if 'type' in data and 'title' in data:
                                thought_count += 1
                                print(f"\n🧠 Thought #{thought_count}")
                                print(f"   Type: {data.get('type')}")
                                print(f"   Agent: {data.get('agent', 'N/A')}")
                                print(f"   Title: {data.get('title')}")
                                print(f"   Content: {data.get('content')}")
                                if data.get('progress') is not None:
                                    progress_pct = int(data['progress'] * 100)
                                    print(f"   Progress: {progress_pct}%")

                            # Format response event
                            elif 'message' in data:
                                print(f"\n✅ FINAL RESPONSE")
                                print(f"   Success: {data.get('success')}")
                                print(f"   Message: {data.get('message')}")
                                print(f"   Agents Used: {', '.join(data.get('agents_used', []))}")
                                if data.get('suggestions'):
                                    print(f"   Suggestions: {data.get('suggestions')}")

                            else:
                                print(f"   Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
                        except json.JSONDecodeError:
                            print(f"   Raw data: {data_str}")

                print(f"\n{'='*50}")
                print(f"📊 Summary: Received {thought_count} thought events")
                print('='*50)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("✅ STREAMING TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_streaming())
