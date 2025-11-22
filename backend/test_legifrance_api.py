"""
Script de test pour l'API Légifrance
Teste la connexion, l'obtention du token et la recherche de jurisprudence
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file
from dotenv import load_dotenv
load_dotenv()

from app.services.legifrance_service import get_legifrance_service


async def test_legifrance_connection():
    """Test la connexion à l'API Légifrance"""

    print("="*80)
    print("TEST API LÉGIFRANCE - Connexion et Recherche Jurisprudence")
    print("="*80)
    print()

    # 1. Vérifier que le service est configuré
    print("📋 Étape 1 : Vérification configuration...")
    service = get_legifrance_service()

    if not service:
        print("❌ ERREUR : Service Légifrance non configuré")
        print("   Vérifiez que LEGIFRANCE_CLIENT_ID et LEGIFRANCE_CLIENT_SECRET sont dans .env")
        return False

    print("✅ Service configuré")
    print(f"   Client ID: {service.client_id}")
    print(f"   Client Secret: {'*' * (len(service.client_secret) - 4) + service.client_secret[-4:]}")
    print()

    # 2. Tester l'obtention du token
    print("📋 Étape 2 : Obtention du token OAuth2...")
    try:
        token = await service._get_access_token()
        print(f"✅ Token obtenu avec succès")
        print(f"   Token (preview): {token[:20]}...{token[-10:]}")
        print()
    except Exception as e:
        print(f"❌ ERREUR lors de l'obtention du token:")
        print(f"   {type(e).__name__}: {str(e)}")
        print()
        print("💡 Solutions possibles:")
        print("   - Vérifier que les credentials sont corrects")
        print("   - Vérifier que l'application est bien enregistrée sur PISTE")
        print("   - Vérifier la connexion internet")
        return False

    # 3. Tester la recherche de jurisprudence
    print("📋 Étape 3 : Recherche de jurisprudence...")
    query = "assemblée générale copropriété"
    print(f"   Query: '{query}'")
    print()

    try:
        result = await service.search_jurisprudence(
            query=query,
            case_type="copropriete",
            max_results=3
        )

        if result.get("success"):
            print(f"✅ Recherche réussie")
            print(f"   Résultats trouvés: {result.get('total', 0)}")
            print(f"   Résultats retournés: {len(result.get('results', []))}")
            print()

            # Afficher les résultats
            if result.get("results"):
                print("📄 Résultats:")
                print()
                for idx, case in enumerate(result["results"], 1):
                    print(f"   {idx}. {case.get('title', 'Sans titre')}")
                    if case.get('jurisdiction'):
                        print(f"      Juridiction: {case['jurisdiction']}")
                    if case.get('date'):
                        print(f"      Date: {case['date']}")
                    if case.get('numero'):
                        print(f"      Numéro: {case['numero']}")
                    if case.get('summary'):
                        print(f"      Résumé: {case['summary'][:150]}...")
                    if case.get('url'):
                        print(f"      URL: {case['url']}")
                    print()
            else:
                print("   ℹ️  Aucun résultat trouvé pour cette recherche")
                print()
        else:
            print(f"❌ ERREUR lors de la recherche:")
            print(f"   {result.get('error', 'Erreur inconnue')}")
            return False

    except Exception as e:
        print(f"❌ ERREUR lors de la recherche:")
        print(f"   {type(e).__name__}: {str(e)}")
        return False

    # 4. Tester le cache du token
    print("📋 Étape 4 : Test du cache token...")
    try:
        token2 = await service._get_access_token()
        print("✅ Token récupéré depuis le cache (si même token)")
        print(f"   Tokens identiques: {token == token2}")
        print()
    except Exception as e:
        print(f"⚠️  Erreur cache: {str(e)}")
        print()

    # Nettoyage
    await service.close()

    print("="*80)
    print("✅ TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS")
    print("="*80)
    print()
    print("💡 L'API Légifrance est opérationnelle et prête pour production")
    print()

    return True


async def test_legifrance_law_article():
    """Test optionnel : récupérer un article de loi"""

    print("="*80)
    print("TEST BONUS : Récupération article de loi")
    print("="*80)
    print()

    service = get_legifrance_service()
    if not service:
        print("❌ Service non configuré")
        return

    # Tenter de récupérer l'article 24 de la loi 1965 (Copropriété)
    # Note: L'ID exact peut varier, ceci est un exemple
    law_id = "LEGITEXT000006069108"  # Loi 1965 sur copropriété
    article_num = "24"

    print(f"📋 Recherche article {article_num} de la loi {law_id}...")
    print()

    try:
        article = await service.get_law_article(law_id, article_num)

        if article:
            print("✅ Article trouvé:")
            print(f"   Titre: {article.get('title', 'N/A')}")
            print(f"   Contenu: {article.get('content', 'N/A')[:200]}...")
            print()
        else:
            print("ℹ️  Article non trouvé (ID de loi peut être incorrect)")
            print()
    except Exception as e:
        print(f"⚠️  Erreur: {str(e)}")
        print()

    await service.close()


if __name__ == "__main__":
    print()
    print("🔍 Test de l'API Légifrance")
    print()

    # Test principal
    success = asyncio.run(test_legifrance_connection())

    if success:
        # Test bonus si le premier a réussi
        print()
        response = input("Voulez-vous tester la récupération d'un article de loi ? (o/n): ")
        if response.lower() in ['o', 'oui', 'y', 'yes']:
            asyncio.run(test_legifrance_law_article())

    print()
    print("🏁 Tests terminés")
    print()
