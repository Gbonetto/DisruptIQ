#!/usr/bin/env python3
"""
Fix N8N workflow final callback to match backend contract
"""
import asyncio
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import settings
import sys
sys.path.append('/app')
from app.core.config import settings


# New final callback code that matches backend contract
FIXED_FINAL_CALLBACK_CODE = """// ========================
// NODE 4: FINAL RESULT CALLBACK (Fixed to match backend contract)
// ========================

const result = $input.item.json;
const trace = result.trace;

console.log('[N8N_CALLBACK_FINAL] Sending final result');

// Calculate execution time (assume 5 seconds for simulation)
const executionTime = 5.0;

// Transform results to match backend contract
const actionsPerformed = result.results
  .filter(r => r.status === 'success')
  .map(r => r.step_id.toString());

const errors = result.results
  .filter(r => r.status === 'failed')
  .map(r => ({
    step_id: r.step_id,
    error_message: r.error || 'Unknown error'
  }));

// Prepare payload matching backend's N8NWorkflowResult model
const callbackPayload = {
  thought_stream_id: trace.thought_stream_id,
  workflow_name: 'emergency_water_leak',
  status: result.status,  // 'success' or 'failed'
  execution_time: executionTime,
  result: {
    steps_executed: result.results.length,
    steps_failed: result.failed_count,
    actions_performed: actionsPerformed,
    errors: errors.length > 0 ? errors : undefined
  },
  metadata: {
    request_id: result.request_id,
    workflow_type: result.workflow_type,
    success_count: result.success_count,
    skipped_count: result.skipped_count
  },
  error: result.status === 'failed' ? 'Critical step failed' : null
};

console.log('[N8N_CALLBACK_PAYLOAD]', JSON.stringify(callbackPayload, null, 2));

// Send final result callback (best effort)
try {
  await $http.request({
    method: 'POST',
    url: 'http://backend:8000/api/n8n/callback/workflow-result',
    headers: {
      'Authorization': 'Bearer disruptiq_n8n_webhook_secret_2024_secure_token',
      'Content-Type': 'application/json'
    },
    body: callbackPayload,
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


async def fix_workflow():
    """Fix the final callback node in the workflow"""
    print("🔧 Fixing N8N workflow callback...")

    # Create N8N database connection
    db_url = settings.DATABASE_URL.replace('/disruptiq', '/n8n')
    if '+asyncpg' not in db_url:
        db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')

    engine = create_async_engine(db_url, echo=False)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Get workflow
        get_query = text("SELECT id, nodes FROM workflow_entity WHERE name = :name")
        result = await session.execute(get_query, {"name": "emergency-water-leak"})
        row = result.fetchone()

        if not row:
            print("❌ Workflow 'emergency-water-leak' not found!")
            return

        workflow_id = row[0]
        nodes_json = row[1]
        nodes = json.loads(nodes_json) if isinstance(nodes_json, str) else nodes_json

        print(f"✅ Found workflow (ID: {workflow_id})")
        print(f"   Nodes: {len(nodes)}")

        # Find and update the final callback node
        updated = False
        for node in nodes:
            if node.get("name") == "Send Final Result":
                print(f"🎯 Found node 'Send Final Result'")
                node["parameters"]["functionCode"] = FIXED_FINAL_CALLBACK_CODE
                updated = True
                print("   ✅ Updated callback code")
                break

        if not updated:
            print("❌ Node 'Send Final Result' not found!")
            return

        # Update workflow in database
        nodes_json_str = json.dumps(nodes)
        update_query = text("""
            UPDATE workflow_entity
            SET nodes = CAST(:nodes AS json),
                "updatedAt" = CURRENT_TIMESTAMP
            WHERE id = :id
        """)

        await session.execute(update_query, {
            "id": workflow_id,
            "nodes": nodes_json_str
        })

        await session.commit()

        print("✅ Workflow updated successfully!")
        print("\nNext step: Restart N8N to reload workflow")
        print("   docker-compose restart n8n")


if __name__ == "__main__":
    asyncio.run(fix_workflow())
