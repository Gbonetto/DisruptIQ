#!/usr/bin/env python3
"""
Test N8N Emergency Workflow E2E

This script simulates what DisruptIQ backend sends to N8N when a user
triggers an emergency workflow.
"""
import requests
import json
import time
import uuid
from datetime import datetime

# Configuration
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/emergency-water-leak"
AUTH_TOKEN = "Bearer disruptiq_n8n_webhook_secret_2024_secure_token"

# Generate test IDs
request_id = f"req_{int(time.time())}"
thought_stream_id = f"stream_{uuid.uuid4().hex[:12]}"
conversation_id = f"conv_{uuid.uuid4().hex[:8]}"

# Prepare payload (matching N8N_API_CONTRACT_V1.md)
payload = {
    "request_id": request_id,
    "workflow_data": {
        "workflow_type": "water_leak",
        "workflow_name": "Dégât des eaux - Procédure standard",
        "metadata": {
            "estimated_duration_minutes": 5,
            "urgency_level": "high",
            "created_at": datetime.utcnow().isoformat() + "Z"
        },
        "steps": [
            {
                "step_id": 1,
                "step_order": 1,
                "title": "Notifier le propriétaire",
                "enabled": True,
                "is_critical": True,
                "workflow_action": "send_email",
                "n8n_node_type": "email",
                "extracted_data": {
                    "recipient_email": "owner@example.com",
                    "recipient_name": "M. Dupont",
                    "subject": "🚨 URGENCE: Dégât des eaux",
                    "body_preview": "Un dégât des eaux a été détecté..."
                }
            },
            {
                "step_id": 2,
                "step_order": 2,
                "title": "Prévenir les voisins",
                "enabled": True,
                "is_critical": False,
                "workflow_action": "send_email",
                "n8n_node_type": "email",
                "extracted_data": {
                    "recipient_email": "neighbors@example.com",
                    "subject": "Alerte: Dégât des eaux dans l'immeuble"
                }
            },
            {
                "step_id": 3,
                "step_order": 3,
                "title": "Contacter plombier d'urgence",
                "enabled": True,
                "is_critical": True,
                "workflow_action": "send_sms",
                "n8n_node_type": "sms",
                "extracted_data": {
                    "phone_number": "+33612345678",
                    "message_preview": "Urgence plomberie..."
                }
            },
            {
                "step_id": 4,
                "step_order": 4,
                "title": "Créer ticket maintenance",
                "enabled": True,
                "is_critical": False,
                "workflow_action": "create_ticket",
                "n8n_node_type": "ticket_creation",
                "extracted_data": {
                    "ticket_title": "🚨 Dégât des eaux - Appt 12"
                }
            },
            {
                "step_id": 5,
                "step_order": 5,
                "title": "Planifier suivi 24h",
                "enabled": True,
                "is_critical": False,
                "workflow_action": "schedule_action",
                "n8n_node_type": "scheduler",
                "extracted_data": {
                    "scheduled_delay_hours": 24
                }
            }
        ],
        "context_data": {
            "building_name": "Résidence Les Tilleuls",
            "floor": 3,
            "apartment_number": "12",
            "owner_name": "M. Dupont",
            "severity": "high"
        }
    },
    "trace": {
        "conversation_id": conversation_id,
        "request_id": request_id,
        "thought_stream_id": thought_stream_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
}

print("="*60)
print("🧪 Testing N8N Emergency Workflow E2E")
print("="*60)
print()
print(f"📋 Test Details:")
print(f"   Request ID: {request_id}")
print(f"   ThoughtStream ID: {thought_stream_id}")
print(f"   Conversation ID: {conversation_id}")
print(f"   Workflow: {payload['workflow_data']['workflow_name']}")
print(f"   Steps: {len(payload['workflow_data']['steps'])}")
print()
print(f"🔗 N8N Webhook URL: {N8N_WEBHOOK_URL}")
print()

# Send request to N8N
print("📤 Sending payload to N8N...")
print()

try:
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }

    response = requests.post(
        N8N_WEBHOOK_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    print(f"✅ Response Status: {response.status_code}")
    print()

    if response.status_code == 200:
        try:
            result = response.json()
            print("📊 Response Body:")
            print(json.dumps(result, indent=2))
        except:
            print("📊 Response Body (text):")
            print(response.text)

        print()
        print("="*60)
        print("✅ Test SUCCESSFUL!")
        print("="*60)
        print()
        print("📝 Next Steps:")
        print("   1. Check N8N logs: docker-compose logs n8n | grep '[N8N_'")
        print("   2. Check Backend logs: docker-compose logs backend | grep 'n8n_'")
        print(f"   3. Check ThoughtStream updates (ID: {thought_stream_id})")
        print()

    else:
        print(f"❌ Test FAILED!")
        print(f"   Status: {response.status_code}")
        print(f"   Body: {response.text}")
        print()

except requests.exceptions.Timeout:
    print("❌ Request TIMEOUT (>30s)")
    print("   N8N workflow may still be running, check logs")
    print()

except requests.exceptions.ConnectionError as e:
    print(f"❌ CONNECTION ERROR: {e}")
    print("   Is N8N running? Check: docker-compose ps n8n")
    print()

except Exception as e:
    print(f"❌ UNEXPECTED ERROR: {e}")
    print()
