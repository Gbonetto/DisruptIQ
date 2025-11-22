"""
Test simple de l'API Légifrance - Consultation d'un code
"""

import asyncio
import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.legifrance_service import get_legifrance_service


async def test_simple_endpoints():
    """Test différents endpoints pour voir lesquels fonctionnent"""

    print("=" * 80)
    print("TEST ENDPOINTS LÉGIFRANCE")
    print("=" * 80)
    print()

    service = get_legifrance_service()
    if not service:
        print("❌ Service non configuré")
        return

    # Get token
    print("📋 Obtention du token...")
    try:
        token = await service._get_access_token()
        print(f"✅ Token obtenu: {token[:20]}...")
        print()
    except Exception as e:
        print(f"❌ Erreur token: {e}")
        return

    # Test different endpoints
    endpoints_to_test = [
        {
            "name": "list/code",
            "url": f"{service.api_base_url}/list/code",
            "payload": {
                "fond": "CODE",
                "nature": "CODE_DATE"
            }
        },
        {
            "name": "consult/jorf",
            "url": f"{service.api_base_url}/consult/jorf",
            "payload": {
                "textId": "JORFTEXT000000000001"
            }
        },
        {
            "name": "search (empty)",
            "url": f"{service.api_base_url}/search",
            "payload": {}
        }
    ]

    for endpoint_test in endpoints_to_test:
        print(f"📋 Test endpoint: {endpoint_test['name']}")
        print(f"   URL: {endpoint_test['url']}")
        print(f"   Payload: {endpoint_test['payload']}")

        try:
            response = await service.http_client.post(
                endpoint_test['url'],
                json=endpoint_test['payload'],
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )

            print(f"   ✅ Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Response OK - Keys: {list(data.keys())[:5]}")
            else:
                print(f"   Response: {response.text[:200]}")

        except httpx.HTTPStatusError as e:
            print(f"   ❌ HTTP Error {e.response.status_code}")
            print(f"   Response: {e.response.text[:300]}")
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {str(e)}")

        print()

    await service.close()

    print("=" * 80)
    print("Tests terminés")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_simple_endpoints())
