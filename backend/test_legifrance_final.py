"""
Test final de l'API Légifrance
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.legifrance_service import get_legifrance_service


async def test_legifrance_final():
    """Test final avec parsing corrigé"""

    print("=" * 80)
    print("TEST FINAL API LÉGIFRANCE - Recherche Jurisprudence")
    print("=" * 80)
    print()

    service = get_legifrance_service()
    if not service:
        print("❌ Service non configuré")
        return

    # Test search
    print("📋 Recherche : 'assemblée générale copropriété'")
    print()

    result = await service.search_jurisprudence(
        query="assemblée générale copropriété",
        case_type="copropriete",
        max_results=3
    )

    if result.get("success"):
        print(f"✅ Recherche réussie")
        print(f"   Total trouvé: {result.get('total', 0):,} décisions")
        print(f"   Retournés: {len(result.get('results', []))}")
        print()

        # Display results
        for idx, case in enumerate(result["results"], 1):
            print(f"📄 Décision {idx}:")
            print(f"   ID: {case.get('id', 'N/A')}")
            print(f"   Titre: {case.get('title', 'N/A')}")
            print(f"   Nature: {case.get('nature', 'N/A')}")
            if case.get('summary'):
                print(f"   Résumé: {case['summary'][:150]}...")
            if case.get('url'):
                print(f"   URL: {case['url']}")
            print()

        print("=" * 80)
        print("✅ API LÉGIFRANCE OPÉRATIONNELLE")
        print("=" * 80)
        print()
        print("💡 Intégration réussie :")
        print("   - OAuth2 auto-refresh")
        print("   - Recherche jurisprudence officielle")
        print("   - Parsing complet des résultats")
        print()

    else:
        print(f"❌ Erreur: {result.get('error')}")

    await service.close()


if __name__ == "__main__":
    asyncio.run(test_legifrance_final())
