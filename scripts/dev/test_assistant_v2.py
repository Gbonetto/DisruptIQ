"""
Test script for Multi-Agent Assistant
"""

import asyncio
import httpx
import json


async def test_assistant():
    """Test the multi-agent assistant with various queries"""

    base_url = "http://localhost:8000/api/assistant-v2"

    test_queries = [
        {
            "name": "Test 1: Capabilities",
            "endpoint": f"{base_url}/capabilities",
            "method": "GET"
        },
        {
            "name": "Test 2: List Templates",
            "endpoint": f"{base_url}/templates",
            "method": "GET"
        },
        {
            "name": "Test 3: SQL Query - Copropriétaires",
            "endpoint": f"{base_url}/chat",
            "method": "POST",
            "payload": {
                "message": "Combien de copropriétaires avons-nous en tout?",
                "conversation_history": []
            }
        },
        {
            "name": "Test 4: Email Generation",
            "endpoint": f"{base_url}/chat",
            "method": "POST",
            "payload": {
                "message": "Envoyer un email aux copropriétaires pour les informer d'un dégât des eaux survenu aujourd'hui au 2ème étage",
                "conversation_history": []
            }
        },
        {
            "name": "Test 5: General Question",
            "endpoint": f"{base_url}/chat",
            "method": "POST",
            "payload": {
                "message": "Qu'est-ce que tu peux faire pour moi?",
                "conversation_history": []
            }
        }
    ]

    print("=" * 70)
    print("🤖 TESTING MULTI-AGENT ASSISTANT")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, test in enumerate(test_queries, 1):
            print(f"\n{'='*70}")
            print(f"TEST {i}: {test['name']}")
            print(f"{'='*70}")

            try:
                if test['method'] == 'GET':
                    response = await client.get(test['endpoint'])
                else:  # POST
                    response = await client.post(
                        test['endpoint'],
                        json=test['payload']
                    )

                response.raise_for_status()
                result = response.json()

                print(f"✅ Status: {response.status_code}")
                print(f"Response:")
                print(json.dumps(result, indent=2, ensure_ascii=False))

            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP Error: {e.response.status_code}")
                print(f"Response: {e.response.text}")

            except Exception as e:
                print(f"❌ Error: {str(e)}")

            # Small delay between tests
            await asyncio.sleep(1)

    print("\n" + "=" * 70)
    print("✅ TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_assistant())
