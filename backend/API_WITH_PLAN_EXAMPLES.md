# API `/chat/with-plan` - Examples & Testing

Nouveau endpoint avec **Planner DAG + Evaluator + Observability** intégrés.

## 🚀 Quick Start

### Démarrer le backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Tester avec curl

## 📝 Examples

### 1. SQL Query (Liste des professionnels)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/chat/with-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Liste des plombiers actifs à Paris",
    "conversation_history": [],
    "session_id": "test-session-1"
  }'
```

**Expected Response:**
```json
{
  "message": "Voici les plombiers actifs...",
  "sources": [{
    "text": "SQL Database Query",
    "metadata": {
      "title": "SQL Query Result",
      "sql": "SELECT * FROM vw_professionnels_min WHERE...",
      "table": "Canonical Views (vw_*)"
    }
  }],
  "session_id": "test-session-1",
  "observability": {
    "run_id": 456,
    "plan_steps": 3,
    "total_latency_ms": 1234,
    "estimated_tokens": 500
  },
  "evaluation": {
    "passed": true,
    "rules_checked": 3,
    "rules_passed": 3,
    "critical_failures": 0,
    "warnings": 0,
    "failed_rules": []
  },
  "agents_used": ["sql_agent"],
  "confidence": 0.95
}
```

### 2. RAG Query (Document search)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/chat/with-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quelle est la procédure en cas de dégât des eaux?",
    "conversation_history": [],
    "session_id": "test-session-2"
  }'
```

**Expected Response:**
```json
{
  "message": "Selon le règlement [1], vous devez contacter l'assurance dans les 5 jours [2]...",
  "sources": [
    {
      "id": "doc1",
      "text": "...",
      "metadata": {"title": "Règlement copropriété"}
    }
  ],
  "session_id": "test-session-2",
  "observability": {
    "run_id": 457,
    "plan_steps": 4,
    "total_latency_ms": 2341,
    "estimated_tokens": 1500
  },
  "evaluation": {
    "passed": true,
    "rules_checked": 2,
    "rules_passed": 2,
    "critical_failures": 0,
    "warnings": 0,
    "failed_rules": []
  },
  "agents_used": ["rag_agent", "synthesis_agent"],
  "confidence": 0.89
}
```

### 3. HYBRID Query (SQL + RAG)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/chat/with-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quel est le tarif horaire du plombier Jean Dupont?",
    "conversation_history": [],
    "session_id": "test-session-3"
  }'
```

**Expected Response:**
```json
{
  "message": "Jean Dupont (email: dupont@plomberie.fr) facture 45€/h selon le contrat [1].",
  "sources": [
    {"type": "sql", "table": "vw_professionnels_min"},
    {"type": "rag", "doc": "contrat_plomberie.pdf"}
  ],
  "session_id": "test-session-3",
  "observability": {
    "run_id": 458,
    "plan_steps": 6,
    "total_latency_ms": 3210,
    "estimated_tokens": 2500
  },
  "evaluation": {
    "passed": true,
    "rules_checked": 5,
    "rules_passed": 5,
    "critical_failures": 0,
    "warnings": 0,
    "failed_rules": []
  },
  "agents_used": ["sql_agent", "rag_agent", "fusion_agent"],
  "confidence": 0.93
}
```

### 4. Failed Evaluation Example (No citations)

**Request:**
```bash
curl -X POST "http://localhost:8000/api/chat/with-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quelle est la procédure?",
    "conversation_history": [],
    "session_id": "test-session-4"
  }'
```

**Response with FAILED evaluation:**
```json
{
  "message": "La procédure est simple.\n\n⚠️ **Attention**: 1 règle(s) critique(s) non respectée(s).",
  "sources": [],
  "session_id": "test-session-4",
  "observability": {
    "run_id": 459,
    "plan_steps": 4,
    "total_latency_ms": 1890,
    "estimated_tokens": 1200
  },
  "evaluation": {
    "passed": false,
    "rules_checked": 2,
    "rules_passed": 1,
    "critical_failures": 1,
    "warnings": 0,
    "failed_rules": ["rag_has_citations"]
  },
  "agents_used": ["rag_agent"],
  "confidence": 0.5
}
```

## 📊 Response Fields Explanation

### Observability
- **run_id**: Unique ID in `agent_runs` table for tracking
- **plan_steps**: Number of steps in execution plan
- **total_latency_ms**: Total execution time in milliseconds
- **estimated_tokens**: Estimated token cost

### Evaluation
- **passed**: `true` if all critical rules passed
- **rules_checked**: Total number of rules evaluated
- **rules_passed**: Number of rules that succeeded
- **critical_failures**: Number of CRITICAL rule failures (blocks quality)
- **warnings**: Number of WARNING-level issues
- **failed_rules**: Array of rule IDs that failed

### Rules by Intent

| Intent | Rules Checked |
|--------|--------------|
| **SQL_ONLY** | sql_no_error, sql_results_not_empty, sql_whitelist_tables |
| **RAG_ONLY** | rag_has_citations, rag_min_sources_2 |
| **HYBRID** | All SQL + RAG rules + hybrid_no_contradiction + hybrid_sources_attributed |
| **EMAIL** | email_has_evidence, email_preview_shown |
| **N8N** | n8n_preview_if_danger_high, n8n_correlation_id |
| **WEB** | web_urls_cited |

## 🔍 Debugging

### Check AgentRun in Database

```sql
-- Get last 10 runs
SELECT id, conversation_id, intent, status, evaluator_passed, started_at, finished_at
FROM agent_runs
ORDER BY id DESC
LIMIT 10;

-- Get run details
SELECT *
FROM agent_runs
WHERE id = 456;

-- Get run steps
SELECT step_number, tool, latency_ms, error, executed_at
FROM agent_steps
WHERE run_id = 456
ORDER BY step_number;
```

### Check Evaluation Details

```sql
-- Count evaluation pass rate
SELECT
  intent,
  COUNT(*) as total,
  SUM(CASE WHEN evaluator_passed THEN 1 ELSE 0 END) as passed,
  ROUND(100.0 * SUM(CASE WHEN evaluator_passed THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate
FROM agent_runs
GROUP BY intent;

-- Find failed evaluations
SELECT id, conversation_id, intent, plan_json->>'goal' as goal
FROM agent_runs
WHERE evaluator_passed = false
ORDER BY id DESC
LIMIT 10;
```

### Monitor Performance

```sql
-- Average latency by intent
SELECT
  intent,
  COUNT(*) as runs,
  AVG((finished_at - started_at) * 1000) as avg_latency_ms,
  AVG(cost_tokens) as avg_tokens
FROM agent_runs
WHERE finished_at IS NOT NULL
GROUP BY intent
ORDER BY avg_latency_ms DESC;
```

## 🧪 Testing Script

Save as `test_api.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8000/api/chat/with-plan"

echo "Testing API endpoint..."
echo ""

# Test 1: SQL Query
echo "Test 1: SQL Query (plombiers)"
curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Liste des plombiers actifs",
    "session_id": "test-1"
  }' | jq '.observability, .evaluation'

echo ""
echo "---"
echo ""

# Test 2: RAG Query
echo "Test 2: RAG Query (procédure)"
curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Procédure dégât des eaux",
    "session_id": "test-2"
  }' | jq '.observability, .evaluation'

echo ""
echo "Done!"
```

Run: `bash test_api.sh`

## 🎯 Integration with Frontend

### React/Vue Example

```typescript
interface ObservabilityData {
  run_id: number;
  plan_steps: number;
  total_latency_ms: number;
  estimated_tokens: number;
}

interface EvaluationData {
  passed: boolean;
  rules_checked: number;
  rules_passed: number;
  critical_failures: number;
  warnings: number;
  failed_rules: string[];
}

interface ChatResponseWithPlan {
  message: string;
  sources: any[];
  session_id: string;
  observability: ObservabilityData;
  evaluation: EvaluationData;
  agents_used: string[];
  confidence: number;
}

async function askWithPlan(message: string): Promise<ChatResponseWithPlan> {
  const response = await fetch('/api/chat/with-plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_history: [],
      session_id: getCurrentSessionId()
    })
  });

  const data = await response.json();

  // Display warning if evaluation failed
  if (!data.evaluation.passed) {
    showWarning(`⚠️ Quality check failed: ${data.evaluation.failed_rules.join(', ')}`);
  }

  // Display observability badge
  showObservabilityBadge({
    runId: data.observability.run_id,
    latency: data.observability.total_latency_ms,
    tokens: data.observability.estimated_tokens
  });

  return data;
}
```

## 📈 Metrics Dashboard (Grafana)

Recommended queries for monitoring:

1. **Requests per minute by intent**
```sql
SELECT intent, COUNT(*) / 60.0 as rpm
FROM agent_runs
WHERE started_at > NOW() - INTERVAL '1 hour'
GROUP BY intent
```

2. **Evaluation pass rate**
```sql
SELECT
  DATE_TRUNC('hour', started_at) as hour,
  AVG(CASE WHEN evaluator_passed THEN 1.0 ELSE 0.0 END) as pass_rate
FROM agent_runs
WHERE started_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour
```

3. **P95 latency**
```sql
SELECT
  intent,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (finished_at - started_at) * 1000) as p95_ms
FROM agent_runs
WHERE finished_at IS NOT NULL
GROUP BY intent
```

## 🔐 Security Notes

- **SQL Agent** uses canonical views (`vw_*`) only
- **Sensitive fields** (passwords, SIRET, etc.) not exposed
- **Evaluator** enforces citation requirements
- **Planner** tracks all operations for audit
- **Observability** enables compliance tracking

## 🚨 Troubleshooting

### Error: "Failed to process question with plan"

Check logs for details. Common issues:
- Database connection failed
- Migration not run (missing agent_runs table)
- LLM service error

### Evaluation always fails

Check which rule is failing:
```bash
curl -s http://localhost:8000/api/chat/with-plan \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}' | jq '.evaluation.failed_rules'
```

### High latency

Check observability breakdown:
```sql
SELECT tool, AVG(latency_ms) as avg_ms, COUNT(*) as count
FROM agent_steps
GROUP BY tool
ORDER BY avg_ms DESC;
```

---

✅ **L'endpoint `/chat/with-plan` est maintenant prêt à l'emploi !**
