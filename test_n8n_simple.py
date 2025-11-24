"""
Test Simple N8N - Vérification de la connectivité
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_n8n_connectivity():
    """Test 1: Vérifier que N8N est accessible"""
    print("="*60)
    print("TEST 1: Connectivité N8N")
    print("="*60)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:5678")

            if response.status_code == 200:
                print("✅ N8N est accessible")
                print(f"   Status: {response.status_code}")
                return True
            else:
                print(f"⚠️  N8N répond avec status: {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Erreur de connexion : {str(e)}")
        return False


async def test_existing_webhook():
    """Test 2: Tester le webhook existant (emergency-water-leak)"""
    print("\n" + "="*60)
    print("TEST 2: Webhook Existant (emergency-water-leak)")
    print("="*60)

    payload = {
        "request_id": f"test_{datetime.now().timestamp()}",
        "workflow_data": {
            "workflow_type": "water_leak",
            "workflow_name": "Test Workflow",
            "steps": []
        },
        "trace": {
            "conversation_id": "test_conv",
            "request_id": f"test_{datetime.now().timestamp()}",
            "thought_stream_id": "test_stream"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:5678/webhook/emergency-water-leak",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            print(f"✅ Webhook appelé")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")

            return response.status_code == 200

    except Exception as e:
        print(f"❌ Erreur : {str(e)}")
        return False


async def test_email_webhook():
    """Test 3: Tester le webhook email (s'il existe)"""
    print("\n" + "="*60)
    print("TEST 3: Webhook Email (send-email)")
    print("="*60)

    payload = {
        "data": {
            "subject": "Test Email Simple",
            "body": "Ceci est un email de test.\n\nCordialement,\nLe Syndic",
            "recipients": [
                {
                    "email": "test@example.com",
                    "name": "Test User"
                }
            ],
            "tone": "professional",
            "urgency": "medium"
        },
        "trace": {
            "request_id": f"test_email_{datetime.now().timestamp()}",
            "thought_stream_id": "test_stream_email",
            "conversation_id": "test_conv_email"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:5678/webhook/send-email",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                print(f"✅ Email webhook fonctionne!")
                print(f"   Response: {response.text[:200]}")
                return True
            elif response.status_code == 404:
                print(f"⚠️  Webhook email pas encore importé (404)")
                print(f"\n💡 Pour importer le workflow:")
                print(f"   1. Ouvrir http://localhost:5678")
                print(f"   2. Importer n8n_workflows/email_sender_workflow.json")
                print(f"   3. Activer le workflow")
                print(f"\n   Ou suivre : IMPORT_EMAIL_WORKFLOW_MANUAL.md")
                return False
            else:
                print(f"❌ Erreur: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False

    except Exception as e:
        print(f"❌ Erreur : {str(e)}")
        return False


async def check_mailhog():
    """Test 4: Vérifier que Mailhog est accessible"""
    print("\n" + "="*60)
    print("TEST 4: Mailhog (Serveur SMTP Test)")
    print("="*60)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8025")

            if response.status_code == 200:
                print(f"✅ Mailhog est accessible")
                print(f"   UI: http://localhost:8025")
                print(f"   SMTP: localhost:1025")
                return True
            else:
                print(f"⚠️  Mailhog répond avec status: {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Mailhog n'est pas accessible")
        print(f"   Pour le démarrer:")
        print(f"   docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog")
        return False


async def main():
    """Exécution des tests"""
    print("\n" + "#"*60)
    print("# TESTS SIMPLES N8N")
    print("#"*60)
    print(f"\nDate: {datetime.now().isoformat()}")

    results = {
        "n8n_connectivity": False,
        "existing_webhook": False,
        "email_webhook": False,
        "mailhog": False
    }

    # Test 1
    results["n8n_connectivity"] = await test_n8n_connectivity()
    await asyncio.sleep(1)

    # Test 2
    results["existing_webhook"] = await test_existing_webhook()
    await asyncio.sleep(1)

    # Test 3
    results["email_webhook"] = await test_email_webhook()
    await asyncio.sleep(1)

    # Test 4
    results["mailhog"] = await check_mailhog()

    # Summary
    print("\n" + "="*60)
    print("RÉSUMÉ")
    print("="*60)

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nScore: {passed}/{total} ({passed/total*100:.0f}%)")

    if results["email_webhook"]:
        print("\n✅ Workflow email prêt ! Vous pouvez lancer:")
        print("   python test_n8n_email_integration.py")
    else:
        print("\n📝 Prochaine étape:")
        print("   Importer le workflow email (voir IMPORT_EMAIL_WORKFLOW_MANUAL.md)")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
