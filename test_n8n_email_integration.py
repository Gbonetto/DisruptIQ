"""
Test N8N Email Integration

Tests automatisés pour valider l'intégration complète :
- DisruptIQ → N8N Webhook → Envoi Email → Callback
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()

# Configuration
N8N_BASE_URL = "http://localhost:5678"
BACKEND_BASE_URL = "http://localhost:8000"
WEBHOOK_AUTH_TOKEN = "disruptiq_n8n_webhook_secret_2024_secure_token"


class EmailIntegrationTester:
    """Tester for N8N email integration"""

    def __init__(self):
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "tests": []
        }

    async def test_webhook_single_recipient(self) -> Dict[str, Any]:
        """Test 1: Envoi d'un email à un seul destinataire"""
        test_name = "Single Recipient Email"
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")

        payload = {
            "action": "send_email",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "urgency": "medium",
            "data": {
                "subject": "Test Email - Single Recipient",
                "body": "Ceci est un email de test envoyé depuis DisruptIQ.\n\nCordialement,\nLe Syndic",
                "recipients": [
                    {
                        "email": "test@example.com",
                        "name": "John Doe"
                    }
                ],
                "tone": "professional",
                "urgency": "medium"
            },
            "trace": {
                "request_id": f"test_single_{datetime.now().timestamp()}",
                "thought_stream_id": "test_stream_001",
                "conversation_id": "test_conv_001"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"\n📤 Sending payload to N8N...")
                print(f"URL: {N8N_BASE_URL}/webhook/send-email")
                print(f"Payload: {json.dumps(payload, indent=2)}")

                response = await client.post(
                    f"{N8N_BASE_URL}/webhook/send-email",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {WEBHOOK_AUTH_TOKEN}",
                        "Content-Type": "application/json"
                    }
                )

                print(f"\n✅ Response Status: {response.status_code}")
                print(f"Response Body: {response.text}")

                if response.status_code == 200:
                    result_data = response.json()

                    # Validate response
                    assert result_data.get("success") == True, "Response should indicate success"
                    assert "emails_sent" in result_data, "Response should contain emails_sent"
                    assert len(result_data["emails_sent"]) == 1, "Should send to 1 recipient"
                    assert result_data["request_id"] == payload["trace"]["request_id"], "Request ID should match"

                    print(f"\n✅ TEST PASSED: {test_name}")
                    self.results["passed"] += 1

                    return {
                        "test": test_name,
                        "status": "PASSED",
                        "response": result_data
                    }
                else:
                    print(f"\n❌ TEST FAILED: {test_name}")
                    print(f"Expected status 200, got {response.status_code}")
                    self.results["failed"] += 1

                    return {
                        "test": test_name,
                        "status": "FAILED",
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }

        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"Error: {str(e)}")
            self.results["failed"] += 1

            return {
                "test": test_name,
                "status": "FAILED",
                "error": str(e)
            }

    async def test_webhook_multiple_recipients(self) -> Dict[str, Any]:
        """Test 2: Envoi d'un email à plusieurs destinataires"""
        test_name = "Multiple Recipients Email"
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")

        payload = {
            "action": "send_email",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "urgency": "high",
            "data": {
                "subject": "🚨 URGENT - Test Email Multiple Recipients",
                "body": "Ceci est un email urgent envoyé à plusieurs destinataires.\n\nAction requise immédiatement.\n\nCordialement,\nLe Syndic",
                "recipients": [
                    {
                        "email": "recipient1@example.com",
                        "name": "Alice Smith"
                    },
                    {
                        "email": "recipient2@example.com",
                        "name": "Bob Johnson"
                    },
                    {
                        "email": "recipient3@example.com",
                        "name": "Charlie Brown"
                    }
                ],
                "tone": "urgent",
                "urgency": "high"
            },
            "trace": {
                "request_id": f"test_multi_{datetime.now().timestamp()}",
                "thought_stream_id": "test_stream_002",
                "conversation_id": "test_conv_002"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"\n📤 Sending payload to N8N...")

                response = await client.post(
                    f"{N8N_BASE_URL}/webhook/send-email",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {WEBHOOK_AUTH_TOKEN}",
                        "Content-Type": "application/json"
                    }
                )

                print(f"\n✅ Response Status: {response.status_code}")

                if response.status_code == 200:
                    result_data = response.json()

                    assert result_data.get("success") == True
                    assert len(result_data["emails_sent"]) == 3, "Should send to 3 recipients"

                    print(f"\n✅ TEST PASSED: {test_name}")
                    print(f"Emails sent to: {', '.join([e['recipient'] for e in result_data['emails_sent']])}")
                    self.results["passed"] += 1

                    return {
                        "test": test_name,
                        "status": "PASSED",
                        "response": result_data
                    }
                else:
                    print(f"\n❌ TEST FAILED: {test_name}")
                    self.results["failed"] += 1

                    return {
                        "test": test_name,
                        "status": "FAILED",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"Error: {str(e)}")
            self.results["failed"] += 1

            return {
                "test": test_name,
                "status": "FAILED",
                "error": str(e)
            }

    async def test_webhook_no_recipients(self) -> Dict[str, Any]:
        """Test 3: Validation - pas de destinataires (devrait échouer)"""
        test_name = "No Recipients (Error Handling)"
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")

        payload = {
            "action": "send_email",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "data": {
                "subject": "Test Email - No Recipients",
                "body": "This should fail",
                "recipients": [],  # Empty!
                "tone": "professional"
            },
            "trace": {
                "request_id": f"test_no_recipients_{datetime.now().timestamp()}"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"\n📤 Sending payload with NO recipients...")

                response = await client.post(
                    f"{N8N_BASE_URL}/webhook/send-email",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {WEBHOOK_AUTH_TOKEN}",
                        "Content-Type": "application/json"
                    }
                )

                print(f"\n✅ Response Status: {response.status_code}")

                # We EXPECT this to fail (400 error)
                if response.status_code == 400:
                    result_data = response.json()

                    assert result_data.get("success") == False
                    assert "error" in result_data or "No recipients" in result_data.get("message", "")

                    print(f"\n✅ TEST PASSED: {test_name} (error handled correctly)")
                    self.results["passed"] += 1

                    return {
                        "test": test_name,
                        "status": "PASSED",
                        "note": "Error correctly returned for empty recipients"
                    }
                else:
                    print(f"\n❌ TEST FAILED: {test_name}")
                    print(f"Expected status 400, got {response.status_code}")
                    self.results["failed"] += 1

                    return {
                        "test": test_name,
                        "status": "FAILED",
                        "error": f"Expected 400 error, got {response.status_code}"
                    }

        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"Error: {str(e)}")
            self.results["failed"] += 1

            return {
                "test": test_name,
                "status": "FAILED",
                "error": str(e)
            }

    async def test_email_agent_integration(self) -> Dict[str, Any]:
        """Test 4: Test complet via EmailAgent (simulation)"""
        test_name = "EmailAgent Integration (End-to-End)"
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"{'='*60}")

        # Simulate what EmailAgent would send
        payload = {
            "action": "send_email",
            "tenant_id": "syndic_001",
            "user_id": "manager_123",
            "urgency": "high",
            "data": {
                "subject": "🚨 URGENT - Intervention Plomberie - Résidence Les Oliviers",
                "body": """Madame, Monsieur,

Nous faisons appel à vos services pour une intervention URGENTE concernant une fuite d'eau.

**Détails de l'incident:**
- Bâtiment: Résidence Les Oliviers
- Adresse: 15 Avenue des Fleurs, 75015 Paris
- Appartement: A305
- Étage: 3ème
- Propriétaire: Mme Dupont - Tél: 06 12 34 56 78
- Nature: Fuite d'eau importante dans la salle de bain
- Gravité: CRITIQUE

**Action requise:**
Intervention immédiate pour arrêter la fuite et réparer le système de plomberie

**Contact sur place:**
Mme Dupont - 06 12 34 56 78

Merci de nous confirmer votre disponibilité dans les plus brefs délais.

Cordialement,
Le Syndic""",
                "recipients": [
                    {
                        "email": "plombier@example.com",
                        "name": "Entreprise Plomberie Express",
                        "id": "pro_001"
                    }
                ],
                "tone": "urgent",
                "urgency": "high"
            },
            "context": {
                "active_documents": [],
                "conversation_history": [],
                "building_id": "building_001",
                "timestamp": datetime.utcnow().isoformat()
            },
            "trace": {
                "request_id": f"test_e2e_{datetime.now().timestamp()}",
                "thought_stream_id": "stream_e2e_001",
                "conversation_id": "conv_e2e_001"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"\n📤 Simulating EmailAgent request...")
                print(f"Incident: Fuite d'eau urgente")
                print(f"Recipient: Plombier professionnel")

                response = await client.post(
                    f"{N8N_BASE_URL}/webhook/send-email",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {WEBHOOK_AUTH_TOKEN}",
                        "Content-Type": "application/json"
                    }
                )

                print(f"\n✅ Response Status: {response.status_code}")

                if response.status_code == 200:
                    result_data = response.json()

                    assert result_data.get("success") == True
                    assert len(result_data["emails_sent"]) == 1
                    assert result_data["subject"] == payload["data"]["subject"]

                    print(f"\n✅ TEST PASSED: {test_name}")
                    print(f"Email sent successfully to: {result_data['emails_sent'][0]['recipient']}")
                    self.results["passed"] += 1

                    return {
                        "test": test_name,
                        "status": "PASSED",
                        "response": result_data
                    }
                else:
                    print(f"\n❌ TEST FAILED: {test_name}")
                    self.results["failed"] += 1

                    return {
                        "test": test_name,
                        "status": "FAILED",
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"Error: {str(e)}")
            self.results["failed"] += 1

            return {
                "test": test_name,
                "status": "FAILED",
                "error": str(e)
            }

    async def run_all_tests(self):
        """Execute tous les tests"""
        print(f"\n{'#'*60}")
        print(f"# N8N EMAIL INTEGRATION - TEST SUITE")
        print(f"{'#'*60}")
        print(f"\nDate: {datetime.now().isoformat()}")
        print(f"N8N URL: {N8N_BASE_URL}")
        print(f"Backend URL: {BACKEND_BASE_URL}")

        tests = [
            self.test_webhook_single_recipient(),
            self.test_webhook_multiple_recipients(),
            self.test_webhook_no_recipients(),
            self.test_email_agent_integration()
        ]

        for test_coro in tests:
            self.results["total_tests"] += 1
            result = await test_coro
            self.results["tests"].append(result)
            await asyncio.sleep(1)  # Pause entre les tests

        # Summary
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {self.results['total_tests']}")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"Success Rate: {(self.results['passed'] / self.results['total_tests'] * 100):.1f}%")

        # Save results
        results_file = f"test_results_n8n_email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {results_file}")

        return self.results


async def main():
    """Point d'entrée principal"""
    tester = EmailIntegrationTester()

    try:
        results = await tester.run_all_tests()

        # Exit code based on results
        if results["failed"] == 0:
            print("\n✅ ALL TESTS PASSED!")
            exit(0)
        else:
            print(f"\n❌ {results['failed']} TEST(S) FAILED")
            exit(1)

    except Exception as e:
        print(f"\n💥 Test suite crashed: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(2)


if __name__ == "__main__":
    asyncio.run(main())
