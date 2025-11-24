#!/usr/bin/env python3
"""
Create N8N workflow incrementally via API
Step by step validation
"""
import requests
import json
import time

N8N_API_URL = "http://localhost:5678/api/v1"
API_KEY = "n8n_api_disruptiq_2024_secure_key"

headers = {
    "X-N8N-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

print("="*60)
print("🔧 Creating N8N Workflow Incrementally")
print("="*60)
print()

# Step 1: Minimal workflow (just webhook + response)
print("📝 Step 1: Creating MINIMAL workflow (webhook only)")
print()

minimal_workflow = {
    "name": "emergency-water-leak",
    "nodes": [
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "emergency-water-leak",
                "responseMode": "onReceived",
                "options": {}
            },
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1.1,
            "position": [250, 300],
            "webhookId": ""
        }
    ],
    "connections": {},
    "settings": {
        "executionOrder": "v1"
    }
}

try:
    response = requests.post(
        f"{N8N_API_URL}/workflows",
        headers=headers,
        json=minimal_workflow,
        timeout=10
    )

    if response.status_code in [200, 201]:
        workflow = response.json()
        workflow_id = workflow.get('id')
        print(f"✅ Workflow created! ID: {workflow_id}")
        print(f"   Name: {workflow.get('name')}")
        print(f"   Active: {workflow.get('active')}")
        print()

        # Step 2: Activate workflow
        print("📝 Step 2: Activating workflow")

        # N8N activation endpoint
        activate_response = requests.post(
            f"{N8N_API_URL}/workflows/{workflow_id}/activate",
            headers=headers,
            timeout=10
        )

        if activate_response.status_code == 200:
            print("✅ Workflow activated!")
            print()

            # Step 3: Test webhook
            print("📝 Step 3: Testing webhook")
            webhook_url = f"http://localhost:5678/webhook/emergency-water-leak"
            print(f"   URL: {webhook_url}")

            time.sleep(2)  # Wait for activation

            test_payload = {"test": "minimal", "message": "Hello N8N!"}
            test_response = requests.post(
                webhook_url,
                json=test_payload,
                timeout=5
            )

            if test_response.status_code == 200:
                print(f"✅ Webhook responds! Status: {test_response.status_code}")
                print(f"   Response: {test_response.text}")
                print()
                print("="*60)
                print("✅ STEP 1 SUCCESS - Minimal workflow works!")
                print("="*60)
                print()
                print(f"🎯 Workflow ID: {workflow_id}")
                print(f"🔗 Webhook URL: {webhook_url}")
                print()
                print("📋 Next steps:")
                print("   1. Add validation node")
                print("   2. Add callback nodes")
                print("   3. Add execution logic")
                print()
            else:
                print(f"❌ Webhook test failed: {test_response.status_code}")
                print(f"   {test_response.text}")
        else:
            print(f"❌ Activation failed: {activate_response.status_code}")
            print(f"   {activate_response.text}")
    else:
        print(f"❌ Workflow creation failed: {response.status_code}")
        print(f"   {response.text}")

except Exception as e:
    print(f"❌ Error: {e}")
