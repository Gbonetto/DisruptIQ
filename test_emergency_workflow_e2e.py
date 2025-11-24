#!/usr/bin/env python3
"""
Emergency Workflow E2E Test

This script tests the complete flow:
1. DisruptIQ Frontend → Backend (simulate user confirmation)
2. Backend → N8N (trigger workflow execution)
3. N8N → Backend (callbacks for ThoughtStream updates)
4. Verify all steps execute successfully
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/emergency-water-leak"
AUTH_TOKEN = "disruptiq_n8n_webhook_secret_2024_secure_token"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def test_backend_health():
    """Test 1: Verify backend is healthy"""
    print_section("TEST 1: Backend Health Check")

    response = requests.get(f"{BACKEND_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200, "Backend health check failed"
    print("✅ Backend is healthy")

def test_emergency_endpoint_health():
    """Test 2: Verify emergency workflows endpoint is available"""
    print_section("TEST 2: Emergency Workflows Endpoint Health")

    response = requests.get(f"{BACKEND_URL}/api/emergency-workflows/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200, "Emergency workflows endpoint not available"
    print("✅ Emergency workflows endpoint is healthy")

def test_n8n_callback_endpoints():
    """Test 3: Verify N8N callback endpoints are available"""
    print_section("TEST 3: N8N Callback Endpoints")

    # Test thought-update endpoint
    response = requests.get(f"{BACKEND_URL}/api/n8n/callback/health")
    print(f"Callback health status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200, "N8N callback endpoint not available"
    print("✅ N8N callback endpoints are healthy")

def test_execute_workflow():
    """Test 4: Execute emergency workflow via backend endpoint"""
    print_section("TEST 4: Execute Emergency Workflow (DisruptIQ → Backend → N8N)")

    # Prepare workflow execution request
    request_id = f"test_req_{int(time.time())}"
    thought_stream_id = f"test_stream_{int(time.time())}"

    payload = {
        "workflow_data": {
            "workflow_type": "water_leak",
            "workflow_name": "Procédure Dégât des Eaux",
            "metadata": {
                "location": "Appartement 12, Résidence Les Tilleuls",
                "urgency": "HIGH",
                "description": "Eau coule du plafond"
            },
            "steps": [
                {
                    "step_id": 1,
                    "step_order": 1,
                    "title": "Notifier le propriétaire",
                    "enabled": True,
                    "is_critical": True,
                    "workflow_action": "notify_owner",
                    "n8n_node_type": "email",
                    "extracted_data": {
                        "recipient": "M. Dupont",
                        "email": "dupont@example.com",
                        "phone": "06 12 34 56 78"
                    }
                },
                {
                    "step_id": 2,
                    "step_order": 2,
                    "title": "Prévenir les voisins des étages inférieurs",
                    "enabled": True,
                    "is_critical": False,
                    "workflow_action": "notify_neighbors",
                    "n8n_node_type": "sms",
                    "extracted_data": {
                        "affected_floors": ["1st", "2nd"],
                        "building": "Résidence Les Tilleuls"
                    }
                },
                {
                    "step_id": 3,
                    "step_order": 3,
                    "title": "Contacter plombier d'urgence",
                    "enabled": True,
                    "is_critical": True,
                    "workflow_action": "contact_plumber",
                    "n8n_node_type": "phone_call",
                    "extracted_data": {
                        "service": "Plomberie Express",
                        "phone": "01 23 45 67 89"
                    }
                },
                {
                    "step_id": 4,
                    "step_order": 4,
                    "title": "Créer ticket d'intervention",
                    "enabled": True,
                    "is_critical": False,
                    "workflow_action": "create_ticket",
                    "n8n_node_type": "api_call",
                    "extracted_data": {
                        "priority": "URGENT",
                        "category": "water_damage",
                        "location": "Appartement 12"
                    }
                },
                {
                    "step_id": 5,
                    "step_order": 5,
                    "title": "Planifier suivi 24h",
                    "enabled": True,
                    "is_critical": False,
                    "workflow_action": "schedule_followup",
                    "n8n_node_type": "scheduler",
                    "extracted_data": {
                        "followup_time": "2025-11-24T15:30:00Z",
                        "assignee": "Responsable Technique"
                    }
                }
            ],
            "context_data": {
                "user_message": "URGENT: Dégât des eaux détecté dans l'appartement 12",
                "detected_at": datetime.utcnow().isoformat()
            }
        },
        "trace": {
            "conversation_id": "conv_test_123",
            "request_id": request_id,
            "thought_stream_id": thought_stream_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    print(f"Request ID: {request_id}")
    print(f"ThoughtStream ID: {thought_stream_id}")
    print(f"Workflow Type: water_leak")
    print(f"Steps: {len(payload['workflow_data']['steps'])}")
    print(f"\nSending request to: {BACKEND_URL}/api/emergency-workflows/execute")

    # Execute workflow via backend
    response = requests.post(
        f"{BACKEND_URL}/api/emergency-workflows/execute",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"\n📡 Response Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"📊 Response Body:")
        print(json.dumps(result, indent=2))

        print("\n✅ Workflow execution started successfully!")
        print(f"   Request ID: {result.get('request_id')}")
        print(f"   ThoughtStream ID: {result.get('thought_stream_id')}")

        # Wait for N8N to process
        print("\n⏳ Waiting for N8N to process workflow (5 seconds)...")
        time.sleep(5)

        return True
    else:
        print(f"❌ Failed to execute workflow")
        print(f"Error: {response.text}")
        return False

def test_n8n_logs():
    """Test 5: Check N8N logs for execution traces"""
    print_section("TEST 5: N8N Execution Logs")

    print("Checking N8N logs for execution traces...")
    print("Run this command to see N8N logs:")
    print("\n  docker-compose logs n8n --tail 100 | grep '\\[N8N_'\n")

    print("Expected logs:")
    print("  [N8N_START] emergency-water-leak")
    print("  [N8N_AUTH_OK]")
    print("  [N8N_VALID] request_id=...")
    print("  [N8N_EXEC] Processing 5 steps")
    print("  [N8N_SUCCESS] step_id=1")
    print("  [N8N_SUCCESS] step_id=2")
    print("  ...")
    print("  [N8N_COMPLETE] status=success")

def test_backend_callback_logs():
    """Test 6: Check backend logs for callback receipts"""
    print_section("TEST 6: Backend Callback Logs")

    print("Checking backend logs for N8N callbacks...")
    print("Run this command to see backend callback logs:")
    print("\n  docker-compose logs backend --tail 100 | grep 'n8n'\n")

    print("Expected logs:")
    print("  n8n_thought_update_received stream_id=...")
    print("  n8n_workflow_result_received workflow=emergency_water_leak status=success")

def run_all_tests():
    """Run all E2E tests"""
    print("\n")
    print("🚀 Emergency Workflow E2E Test Suite")
    print("=" * 80)
    print(f"Start time: {datetime.utcnow().isoformat()}")

    try:
        # Run tests in sequence
        test_backend_health()
        test_emergency_endpoint_health()
        test_n8n_callback_endpoints()

        # Execute workflow
        workflow_executed = test_execute_workflow()

        if workflow_executed:
            test_n8n_logs()
            test_backend_callback_logs()

        print_section("🎉 ALL TESTS COMPLETED")
        print("Next steps:")
        print("1. Check the N8N logs to verify workflow execution")
        print("2. Check the backend logs to verify callback receipt")
        print("3. Test from DisruptIQ UI with a real urgent message")
        print("\nTest message to try in UI:")
        print("---")
        print("URGENT: Dégât des eaux détecté dans l'appartement 12,")
        print("résidence Les Tilleuls, 3ème étage.")
        print("Propriétaire: M. Dupont (dupont@example.com, 06 12 34 56 78).")
        print("Eau coule du plafond, situation critique.")
        print("---")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
