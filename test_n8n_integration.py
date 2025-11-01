#!/usr/bin/env python3
"""
Test N8N Integration
Tests webhook connection with real N8N instance
"""

import requests
import json
from datetime import datetime

# Configuration
N8N_WEBHOOK_URL = "https://innoflow.app.n8n.cloud/webhook-test/fef6db21-e46a-4789-b263-cc7360132edc"

def test_simple_webhook():
    """Test 1: Simple ping to verify N8N is listening"""
    print("\n🧪 Test 1: Simple Webhook Ping")
    print("-" * 50)

    payload = {
        "test_type": "simple_ping",
        "message": "Hello from DisruptIQ!",
        "timestamp": datetime.now().isoformat(),
        "source": "DisruptIQ Backend"
    }

    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=False,  # Ignore SSL warnings
            timeout=10
        )

        print(f"✅ Status Code: {response.status_code}")
        print(f"📦 Response: {response.text[:200]}")

        return response.status_code == 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_vendor_email_workflow():
    """Test 2: Vendor email generation workflow"""
    print("\n🧪 Test 2: Vendor Email Workflow")
    print("-" * 50)

    payload = {
        "workflow": "send_vendor_emails",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "email_content": "Bonjour {{name}},\n\nNous recherchons un devis pour des travaux de plomberie.\n\nCordialement,\nSyndic",
            "recipients": [
                {
                    "email": "plombier@example.com",
                    "name": "Jean Dupont",
                    "company": "Plomberie Dupont"
                },
                {
                    "email": "electricien@example.com",
                    "name": "Marie Martin",
                    "company": "Électricité Martin"
                }
            ],
            "metadata": {
                "subject": "Demande de devis - Travaux immeuble",
                "property_address": "123 Rue de la Paix, 75001 Paris",
                "service_type": "plomberie",
                "urgency": "normal",
                "budget_estimate": "2000-5000€"
            }
        }
    }

    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=10
        )

        print(f"✅ Status Code: {response.status_code}")
        print(f"📦 Response: {response.text[:500]}")

        return response.status_code == 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_notify_neighbors_workflow():
    """Test 3: Neighbor notification workflow"""
    print("\n🧪 Test 3: Notify Neighbors Workflow")
    print("-" * 50)

    payload = {
        "workflow": "notify_neighbors",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "address": "15 Avenue Montaigne, 75008 Paris",
            "apartment": "Appartement 3B",
            "issue": "water_damage",
            "issue_description": "Fuite d'eau constatée au plafond",
            "neighbors": [
                {
                    "apt": "3A",
                    "name": "M. Dubois",
                    "email": "dubois@example.com"
                },
                {
                    "apt": "3C",
                    "name": "Mme. Leclerc",
                    "email": "leclerc@example.com"
                },
                {
                    "apt": "4B",
                    "name": "M. Petit",
                    "email": "petit@example.com"
                }
            ],
            "urgency": "high",
            "action_required": "Vérifier vos canalisations",
            "contact": {
                "syndic_phone": "+33 1 23 45 67 89",
                "syndic_email": "contact@syndic.com"
            }
        }
    }

    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=10
        )

        print(f"✅ Status Code: {response.status_code}")
        print(f"📦 Response: {response.text[:500]}")

        return response.status_code == 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_digest_summary():
    """Test 4: Daily digest summary"""
    print("\n🧪 Test 4: Daily Digest Summary")
    print("-" * 50)

    payload = {
        "workflow": "daily_digest",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_emails": 15,
            "urgent_count": 3,
            "important_count": 7,
            "routine_count": 5,
            "urgent_emails": [
                {
                    "subject": "URGENT: Fuite d'eau Apt 12",
                    "sender": "resident@example.com",
                    "received_at": "2025-11-01T08:30:00Z"
                },
                {
                    "subject": "Panne ascenseur",
                    "sender": "maintenance@example.com",
                    "received_at": "2025-11-01T09:15:00Z"
                }
            ],
            "summary": "3 urgences identifiées nécessitant action immédiate"
        }
    }

    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=10
        )

        print(f"✅ Status Code: {response.status_code}")
        print(f"📦 Response: {response.text[:500]}")

        return response.status_code == 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all N8N integration tests"""
    print("=" * 50)
    print("🚀 DisruptIQ - N8N Integration Tests")
    print("=" * 50)
    print(f"📍 Webhook URL: {N8N_WEBHOOK_URL}")
    print(f"⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        "Simple Ping": test_simple_webhook(),
        "Vendor Emails": test_vendor_email_workflow(),
        "Notify Neighbors": test_notify_neighbors_workflow(),
        "Digest Summary": test_digest_summary()
    }

    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20s} : {status}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print(f"\n🎯 Overall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("🎉 All tests passed! N8N integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check N8N workflow configuration.")


if __name__ == "__main__":
    main()
