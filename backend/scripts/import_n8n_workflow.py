#!/usr/bin/env python3
"""
Import N8N workflow directly into database (V1 pragmatic approach)
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import settings
import sys
sys.path.append('/app')
from app.core.config import settings


# Workflow JSON structure
WORKFLOW_JSON = {
    "name": "emergency-water-leak",
    "nodes": [
        {
            "parameters": {
                "httpMethod": "POST",
                "path": "emergency-water-leak",
                "options": {},
                "authentication": "headerAuth"
            },
            "id": str(uuid.uuid4()),
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 1.1,
            "position": [250, 300],
            "webhookId": str(uuid.uuid4())
        },
        {
            "parameters": {
                "functionCode": """// ========================
// NODE 1: VALIDATION
// ========================

const payload = $input.item.json.body || $input.item.json;

// Log webhook reception
console.log('[N8N_START] Workflow emergency-water-leak triggered');
console.log('[N8N_PAYLOAD]', JSON.stringify(payload, null, 2));

// Validate auth
const authHeader = $input.item.json.headers?.authorization || '';
const expectedToken = 'Bearer disruptiq_n8n_webhook_secret_2024_secure_token';

if (authHeader !== expectedToken) {
  console.error('[N8N_AUTH_FAIL] Invalid token');
  throw new Error('Unauthorized');
}

console.log('[N8N_AUTH_OK]');

// Validate payload structure
if (!payload.request_id || !payload.workflow_data || !payload.trace) {
  console.error('[N8N_INVALID_PAYLOAD] Missing required fields');
  throw new Error('Invalid payload structure');
}

console.log('[N8N_VALID] request_id=' + payload.request_id);

return {
  json: payload
};"""
            },
            "id": str(uuid.uuid4()),
            "name": "Validate Payload",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [450, 300]
        },
        {
            "parameters": {
                "functionCode": """// ========================
// NODE 2: INITIAL CALLBACK
// ========================

const payload = $input.item.json;
const trace = payload.trace;

console.log('[N8N_CALLBACK_INIT] Sending initial callback');

// Send initial callback (best effort)
try {
  const response = await $http.request({
    method: 'POST',
    url: 'http://backend:8000/api/n8n/callback/thought-update',
    headers: {
      'Authorization': 'Bearer disruptiq_n8n_webhook_secret_2024_secure_token',
      'Content-Type': 'application/json'
    },
    body: {
      thought_stream_id: trace.thought_stream_id,
      thought_type: 'EXECUTING',
      title: '🚨 Workflow d\\'urgence démarré',
      content: 'Exécution du workflow eau en cours...',
      agent: 'N8N_WaterLeak',
      progress: 0.1,
      metadata: {
        request_id: payload.request_id,
        workflow_type: 'water_leak'
      }
    },
    timeout: 3000
  });
  console.log('[N8N_CALLBACK_INIT_OK]');
} catch (error) {
  // V1: Best effort, don't fail on callback error
  console.error('[N8N_CALLBACK_INIT_FAIL]', error.message);
}

return {
  json: payload
};"""
            },
            "id": str(uuid.uuid4()),
            "name": "Send Initial Callback",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [650, 300]
        },
        {
            "parameters": {
                "functionCode": """// ========================
// NODE 3: EXECUTE STEPS
// ========================

const payload = $input.item.json;
const steps = payload.workflow_data.steps;
const trace = payload.trace;

console.log('[N8N_EXEC] Starting execution of', steps.length, 'steps');

const results = [];
let criticalFailed = false;
let currentProgress = 0.2; // Start at 20% (after initial callback)

for (let i = 0; i < steps.length; i++) {
  const step = steps[i];

  console.log(`[N8N_STEP] step_id=${step.step_id} title="${step.title}" enabled=${step.enabled} is_critical=${step.is_critical}`);

  // Skip disabled steps
  if (!step.enabled) {
    console.log(`[N8N_SKIP] step_id=${step.step_id} - disabled by user`);
    results.push({
      step_id: step.step_id,
      title: step.title,
      status: 'skipped',
      reason: 'disabled_by_user'
    });
    continue;
  }

  // If a critical step already failed, skip remaining
  if (criticalFailed) {
    console.log(`[N8N_SKIP] step_id=${step.step_id} - critical step already failed`);
    results.push({
      step_id: step.step_id,
      title: step.title,
      status: 'skipped',
      reason: 'critical_step_failed'
    });
    continue;
  }

  // Calculate progress
  currentProgress = 0.2 + (0.7 * (i + 1) / steps.length); // 20% → 90%

  try {
    // V1: SIMULATE execution (pas de vrais emails)
    console.log(`[N8N_EXEC] step_id=${step.step_id} action=${step.workflow_action}`);

    // Simulate delay
    await new Promise(resolve => setTimeout(resolve, 500));

    // V1: Mock success
    const stepResult = {
      action: step.workflow_action,
      simulated: true,
      timestamp: new Date().toISOString()
    };

    console.log(`[N8N_SUCCESS] step_id=${step.step_id}`);

    results.push({
      step_id: step.step_id,
      title: step.title,
      status: 'success',
      result: stepResult
    });

    // Send progress callback (best effort)
    try {
      await $http.request({
        method: 'POST',
        url: 'http://backend:8000/api/n8n/callback/thought-update',
        headers: {
          'Authorization': 'Bearer disruptiq_n8n_webhook_secret_2024_secure_token',
          'Content-Type': 'application/json'
        },
        body: {
          thought_stream_id: trace.thought_stream_id,
          thought_type: 'EXECUTING',
          title: `✅ ${step.title}`,
          content: `Step ${i + 1}/${steps.length} complétée (simulation)`,
          agent: 'N8N_WaterLeak',
          progress: currentProgress,
          metadata: {
            step_id: step.step_id,
            action: step.workflow_action
          }
        },
        timeout: 3000
      });
    } catch (callbackError) {
      console.error(`[N8N_CALLBACK_FAIL] step_id=${step.step_id}`, callbackError.message);
    }

  } catch (error) {
    console.error(`[N8N_FAIL] step_id=${step.step_id}`, error.message);

    results.push({
      step_id: step.step_id,
      title: step.title,
      status: 'failed',
      error: error.message
    });

    // Send error callback (best effort)
    try {
      await $http.request({
        method: 'POST',
        url: 'http://backend:8000/api/n8n/callback/thought-update',
        headers: {
          'Authorization': 'Bearer disruptiq_n8n_webhook_secret_2024_secure_token',
          'Content-Type': 'application/json'
        },
        body: {
          thought_stream_id: trace.thought_stream_id,
          thought_type: 'ERROR',
          title: `❌ ${step.title}`,
          content: 'Échec: ' + error.message,
          agent: 'N8N_WaterLeak',
          progress: currentProgress,
          metadata: {
            step_id: step.step_id,
            error: error.message
          }
        },
        timeout: 3000
      });
    } catch (callbackError) {
      console.error(`[N8N_CALLBACK_FAIL] step_id=${step.step_id}`);
    }

    // Check if this was a critical step
    if (step.is_critical) {
      console.error(`[N8N_CRITICAL_FAIL] step_id=${step.step_id} - stopping workflow`);
      criticalFailed = true;
    } else {
      console.log(`[N8N_NON_CRITICAL_FAIL] step_id=${step.step_id} - continuing workflow`);
    }
  }
}

// Prepare result
const successCount = results.filter(r => r.status === 'success').length;
const failedCount = results.filter(r => r.status === 'failed').length;
const skippedCount = results.filter(r => r.status === 'skipped').length;

const finalResult = {
  request_id: payload.request_id,
  workflow_type: 'water_leak',
  status: criticalFailed ? 'failed' : 'success',
  execution_time: new Date().toISOString(),
  steps_executed: results.length,
  success_count: successCount,
  failed_count: failedCount,
  skipped_count: skippedCount,
  results: results,
  trace: trace
};

console.log(`[N8N_COMPLETE] status=${finalResult.status} success=${successCount} failed=${failedCount} skipped=${skippedCount}`);

return {
  json: finalResult
};"""
            },
            "id": str(uuid.uuid4()),
            "name": "Execute Steps",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [850, 300]
        },
        {
            "parameters": {
                "functionCode": """// ========================
// NODE 4: FINAL RESULT CALLBACK
// ========================

const result = $input.item.json;
const trace = result.trace;

console.log('[N8N_CALLBACK_FINAL] Sending final result');

// Send final result callback (best effort)
try {
  await $http.request({
    method: 'POST',
    url: 'http://backend:8000/api/n8n/callback/workflow-result',
    headers: {
      'Authorization': 'Bearer disruptiq_n8n_webhook_secret_2024_secure_token',
      'Content-Type': 'application/json'
    },
    body: {
      request_id: result.request_id,
      thought_stream_id: trace.thought_stream_id,
      workflow_type: result.workflow_type,
      status: result.status,
      results: result.results,
      metadata: {
        execution_time: result.execution_time,
        success_count: result.success_count,
        failed_count: result.failed_count,
        skipped_count: result.skipped_count
      }
    },
    timeout: 3000
  });
  console.log('[N8N_CALLBACK_FINAL_OK]');
} catch (error) {
  console.error('[N8N_CALLBACK_FINAL_FAIL]', error.message);
}

console.log('[N8N_END] Workflow complete');

return {
  json: {
    success: true,
    result: result
  }
};"""
            },
            "id": str(uuid.uuid4()),
            "name": "Send Final Result",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1050, 300]
        }
    ],
    "connections": {
        "Webhook": {
            "main": [[{"node": "Validate Payload", "type": "main", "index": 0}]]
        },
        "Validate Payload": {
            "main": [[{"node": "Send Initial Callback", "type": "main", "index": 0}]]
        },
        "Send Initial Callback": {
            "main": [[{"node": "Execute Steps", "type": "main", "index": 0}]]
        },
        "Execute Steps": {
            "main": [[{"node": "Send Final Result", "type": "main", "index": 0}]]
        }
    },
    "active": True,
    "settings": {
        "executionOrder": "v1"
    }
}


async def import_workflow():
    """Import workflow directly into N8N database"""
    print("🚀 Importing N8N workflow...")

    # Create N8N database connection
    # Keep asyncpg for async operations
    # DATABASE_URL format: postgresql+asyncpg://disruptiq:disruptiq_password@postgres:5432/disruptiq
    # Change only the database name from disruptiq to n8n
    db_url = settings.DATABASE_URL
    if '/disruptiq' in db_url:
        # Replace only the last '/disruptiq' (the database name)
        db_url = db_url.rsplit('/disruptiq', 1)[0] + '/n8n'
    if '+asyncpg' not in db_url:
        db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')

    engine = create_async_engine(db_url, echo=True)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if workflow already exists
        check_query = text("SELECT id FROM workflow_entity WHERE name = :name")
        result = await session.execute(check_query, {"name": "emergency-water-leak"})
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  Workflow 'emergency-water-leak' already exists (ID: {existing})")
            print("   Deleting and recreating...")
            delete_query = text("DELETE FROM workflow_entity WHERE id = :id")
            await session.execute(delete_query, {"id": existing})
            await session.commit()

        # Generate workflow ID
        workflow_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Prepare data
        nodes_json = json.dumps(WORKFLOW_JSON["nodes"])
        connections_json = json.dumps(WORKFLOW_JSON["connections"])
        settings_json = json.dumps(WORKFLOW_JSON["settings"])

        # Insert workflow
        insert_query = text("""
            INSERT INTO workflow_entity (
                id, name, active, nodes, connections,
                "createdAt", "updatedAt", settings, "triggerCount"
            ) VALUES (
                :id, :name, :active, CAST(:nodes AS json), CAST(:connections AS json),
                :created_at, :updated_at, CAST(:settings AS json), :trigger_count
            )
        """)

        await session.execute(insert_query, {
            "id": workflow_id,
            "name": "emergency-water-leak",
            "active": True,
            "nodes": nodes_json,
            "connections": connections_json,
            "created_at": now,
            "updated_at": now,
            "settings": settings_json,
            "trigger_count": 0
        })

        await session.commit()

        print(f"✅ Workflow 'emergency-water-leak' created!")
        print(f"   ID: {workflow_id}")
        print(f"   Webhook URL: http://localhost:5678/webhook/emergency-water-leak")
        print(f"   Nodes: {len(WORKFLOW_JSON['nodes'])}")
        print(f"   Status: Active")

    print("\n🎉 Import complete!")
    print("\nNext steps:")
    print("1. Restart N8N to activate webhook: docker-compose restart n8n")
    print("2. Test workflow via DisruptIQ UI")


if __name__ == "__main__":
    asyncio.run(import_workflow())
