"""
Debug: voir la structure exacte de la réponse
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.legifrance_service import get_legifrance_service


async def test_debug_response():
    """Voir la structure complète de la réponse"""

    print("=" * 80)
    print("DEBUG RÉPONSE LÉGIFRANCE")
    print("=" * 80)
    print()

    service = get_legifrance_service()
    token = await service._get_access_token()

    payload = {
        "fond": "JURI",
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
            "pageSize": 2  # Just 2 for debug
        }
    }

    response = await service.http_client.post(
        f"{service.api_base_url}/search",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )

    data = response.json()

    print("📋 Structure complète de la réponse :")
    print()
    print(json.dumps(data, ensure_ascii=False, indent=2))

    await service.close()


if __name__ == "__main__":
    asyncio.run(test_debug_response())
