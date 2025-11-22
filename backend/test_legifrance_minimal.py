"""
Test minimal de recherche Légifrance avec différentes structures
"""

import asyncio
import sys
import os
import httpx
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.legifrance_service import get_legifrance_service


async def test_minimal_search():
    """Test avec différentes structures minimales"""

    print("=" * 80)
    print("TEST MINIMAL RECHERCHE LÉGIFRANCE")
    print("=" * 80)
    print()

    service = get_legifrance_service()
    if not service:
        print("❌ Service non configuré")
        return

    # Get token
    print("📋 Obtention du token...")
    token = await service._get_access_token()
    print(f"✅ Token: {token[:20]}...")
    print()

    # Test different payload structures
    test_payloads = [
        {
            "name": "Structure 1: Minimal avec fond JADE",
            "payload": {
                "fond": "JADE",
                "recherche": {
                    "pageNumber": 1,
                    "pageSize": 3
                }
            }
        },
        {
            "name": "Structure 2: Avec champs vide",
            "payload": {
                "fond": "JADE",
                "recherche": {
                    "champs": [],
                    "pageNumber": 1,
                    "pageSize": 3
                }
            }
        },
        {
            "name": "Structure 3: Fond CASS (Cour de Cassation)",
            "payload": {
                "fond": "CASS",
                "recherche": {
                    "pageNumber": 1,
                    "pageSize": 3
                }
            }
        },
        {
            "name": "Structure 4: Fond ACCO (Accords collectifs)",
            "payload": {
                "fond": "ACCO",
                "recherche": {
                    "pageNumber": 1,
                    "pageSize": 3
                }
            }
        },
        {
            "name": "Structure 5: Exemple du doc avec critères simples",
            "payload": {
                "fond": "JADE",
                "recherche": {
                    "champs": [
                        {
                            "typeChamp": "ALL",
                            "criteres": [
                                {
                                    "typeRecherche": "UN_DES_MOTS",
                                    "valeur": "copropriété",
                                    "operateur": "ET"
                                }
                            ],
                            "operateur": "ET"
                        }
                    ],
                    "operateur": "ET",
                    "pageNumber": 1,
                    "pageSize": 3,
                    "typePagination": "DEFAUT"
                }
            }
        }
    ]

    for test in test_payloads:
        print(f"📋 {test['name']}")
        print(f"   Payload: {json.dumps(test['payload'], ensure_ascii=False, indent=2)[:200]}...")

        try:
            response = await service.http_client.post(
                f"{service.api_base_url}/search",
                json=test['payload'],
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )

            print(f"   ✅ Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ SUCCESS! Keys: {list(data.keys())}")
                if 'results' in data:
                    print(f"   ✅ Results found: {len(data.get('results', []))}")
                print(f"   Full response preview: {json.dumps(data, ensure_ascii=False)[:500]}")
                break  # Stop on first success
            else:
                print(f"   Response: {response.text[:200]}")

        except httpx.HTTPStatusError as e:
            print(f"   ❌ HTTP {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

        print()

    await service.close()


if __name__ == "__main__":
    asyncio.run(test_minimal_search())
