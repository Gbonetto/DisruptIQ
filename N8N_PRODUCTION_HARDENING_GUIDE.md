# 🛡️ Guide de Robustesse Production - N8N Workflows

**Version**: 1.0
**Date**: 2025-11-23
**Objectif**: Préparer les workflows N8N pour la production

---

## 🎯 Principes de Robustesse

### 1. **Idempotence** (Priority: HIGH)
Un même `request_id` ne doit jamais produire deux exécutions.

### 2. **Retry Logic** (Priority: HIGH)
Les callbacks doivent retry en cas d'échec réseau.

### 3. **Timeout Management** (Priority: MEDIUM)
Workflow et actions doivent timeout proprement.

### 4. **Error Tracking** (Priority: HIGH)
Toute erreur doit être loggée et observable.

### 5. **Graceful Degradation** (Priority: MEDIUM)
Si une action échoue, continuer les autres actions non-dépendantes.

---

## 🔒 1. Idempotence avec Redis

### Problème
```
User clique "Exécuter" → Payload envoyé à N8N
Network timeout côté DisruptIQ
User pense que ça a échoué → Re-clique "Exécuter"
→ 2 exécutions du même workflow ! ❌
```

### Solution : Request ID Tracking

#### A. Backend DisruptIQ - Générer request_id unique

```python
# backend/app/services/agents/workflow_agent.py
import uuid
from datetime import datetime

def _generate_request_id() -> str:
    """Generate unique request ID with timestamp"""
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    unique = str(uuid.uuid4())[:8]
    return f"req_{timestamp}_{unique}"

# Dans _build_standardized_payload()
payload = {
    "trace": {
        "request_id": _generate_request_id(),  # Unique ID
        ...
    }
}
```

#### B. N8N - Check Redis avant exécution

**Node 1 : Redis Check**

```javascript
// N8N Code Node: Check if request already processed
const redis = $redis;  // Assuming Redis connection configured
const requestId = $json.trace.request_id;

// Key pattern: n8n:request:{request_id}
const redisKey = `n8n:request:${requestId}`;

// Check if exists
const exists = await redis.exists(redisKey);

if (exists) {
  console.warn(`Request ${requestId} already processed, skipping`);

  // Return early with cached result
  return {
    skipped: true,
    reason: 'duplicate_request',
    original_result: await redis.get(`${redisKey}:result`)
  };
}

// Mark as processing (TTL: 1 hour)
await redis.setex(redisKey, 3600, JSON.stringify({
  status: 'processing',
  started_at: new Date().toISOString(),
  workflow_name: $json.action
}));

// Pass data to next node
return $json;
```

**Node Final : Store Result in Redis**

```javascript
// Store final result in Redis for idempotence
const requestId = $json.trace.request_id;
const redisKey = `n8n:request:${requestId}`;

const result = {
  status: 'completed',
  completed_at: new Date().toISOString(),
  steps_executed: $json.result.steps_executed,
  workflow_name: $json.workflow_name
};

// Store result (TTL: 24 hours for caching)
await $redis.setex(`${redisKey}:result`, 86400, JSON.stringify(result));

// Update status
await $redis.setex(redisKey, 86400, JSON.stringify(result));

return result;
```

**Configuration N8N Redis** :

```yaml
# docker-compose.yml (ajouter Redis)
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - disruptiq_network
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

**V1 Workaround sans Redis** :

Si pas de Redis en V1, utiliser un simple in-memory cache N8N :

```javascript
// Global variable (persist across executions in same container)
if (typeof global.processedRequests === 'undefined') {
  global.processedRequests = new Map();
}

const requestId = $json.trace.request_id;

if (global.processedRequests.has(requestId)) {
  console.warn(`Duplicate request ${requestId}`);
  return { skipped: true };
}

global.processedRequests.set(requestId, Date.now());

// Cleanup old entries (> 1 hour)
const oneHourAgo = Date.now() - 3600000;
for (const [id, timestamp] of global.processedRequests.entries()) {
  if (timestamp < oneHourAgo) {
    global.processedRequests.delete(id);
  }
}
```

⚠️ **Limitation** : In-memory cache perdu au restart de N8N.

---

## 🔄 2. Retry Logic pour Callbacks

### Problème
```
N8N exécute workflow → Tout se passe bien
N8N envoie callback à DisruptIQ → Network timeout ❌
DisruptIQ ne reçoit jamais la confirmation
User pense que le workflow a échoué
```

### Solution : Exponential Backoff Retry

```javascript
// N8N Function: Send callback with retry
async function sendCallbackWithRetry(url, payload, options = {}) {
  const maxRetries = options.maxRetries || 3;
  const baseDelay = options.baseDelay || 1000; // 1 second
  const timeout = options.timeout || 5000; // 5 seconds

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await $http.request({
        method: 'POST',
        url: url,
        headers: {
          'Authorization': `Bearer ${$env.N8N_WEBHOOK_AUTH_TOKEN}`,
          'Content-Type': 'application/json'
        },
        body: payload,
        timeout: timeout,
        ignoreHttpStatusErrors: false
      });

      // Success
      console.log(`Callback sent successfully on attempt ${attempt + 1}`);
      return response;

    } catch (error) {
      const isLastAttempt = attempt === maxRetries - 1;

      console.error(`Callback attempt ${attempt + 1} failed:`, error.message);

      if (isLastAttempt) {
        // All retries exhausted
        console.error('All callback retries failed, logging to error queue');

        // Log to error tracking (Sentry, CloudWatch, etc.)
        await logCallbackError({
          url: url,
          payload: payload,
          error: error.message,
          attempts: maxRetries
        });

        // Don't throw - workflow continues even if callback fails
        return null;
      }

      // Wait before retry (exponential backoff)
      const delay = baseDelay * Math.pow(2, attempt);
      console.log(`Retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}

// Usage dans N8N
const callbackUrl = 'http://backend:8000/api/n8n/callback/thought-update';
const payload = {
  thought_stream_id: $json.trace.thought_stream_id,
  thought_type: 'EXECUTING',
  title: 'Step completed',
  content: 'Email sent successfully',
  agent: 'N8N_WaterLeak',
  progress: 0.5
};

await sendCallbackWithRetry(callbackUrl, payload, {
  maxRetries: 3,
  baseDelay: 1000,
  timeout: 5000
});
```

**Retry Schedule** :
- Attempt 1: Immédiat
- Attempt 2: +1 seconde (2^0 * 1000ms)
- Attempt 3: +2 secondes (2^1 * 1000ms)
- Attempt 4: +4 secondes (2^2 * 1000ms)

**Total max delay** : 7 secondes

---

## ⏱️ 3. Timeout Management

### A. Timeout Global Workflow

```javascript
// N8N: Set workflow timeout (Node Settings)
// Settings → Execution → Timeout: 300 seconds (5 minutes)
```

Configuration dans N8N UI :
1. Settings → Workflows → Default Timeout : 300s
2. Par workflow : Settings → Execution Timeout : 300s

### B. Timeout par Action

```javascript
// N8N HTTP Request Node
{
  "timeout": 30000,  // 30 seconds max per HTTP call
  "continueOnFail": true,  // Don't stop workflow if one step fails
  "retryOnFail": true,
  "maxTries": 2
}
```

### C. Timeout Handler

```javascript
// Wrapper avec timeout
async function executeWithTimeout(asyncFunction, timeoutMs = 30000) {
  return Promise.race([
    asyncFunction(),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Timeout exceeded')), timeoutMs)
    )
  ]);
}

// Usage
try {
  const result = await executeWithTimeout(
    () => sendEmail(payload),
    30000  // 30 sec
  );
} catch (error) {
  if (error.message === 'Timeout exceeded') {
    console.error('Action timed out, continuing to next step');
    // Mark step as failed but continue
  } else {
    throw error;
  }
}
```

---

## 📊 4. Error Tracking et Monitoring

### A. Structured Logging

```javascript
// N8N: Structured error logging
function logError(context) {
  const logEntry = {
    timestamp: new Date().toISOString(),
    workflow_name: $json.action,
    request_id: $json.trace.request_id,
    thought_stream_id: $json.trace.thought_stream_id,
    error_type: context.error_type,
    error_message: context.error_message,
    step_id: context.step_id,
    step_title: context.step_title,
    stack_trace: context.stack_trace
  };

  console.error('[N8N_ERROR]', JSON.stringify(logEntry));

  // Send to error tracking service (Sentry, etc.)
  if ($env.SENTRY_DSN) {
    // Sentry.captureException(context);
  }

  return logEntry;
}

// Usage
try {
  await executeStep(step);
} catch (error) {
  logError({
    error_type: 'step_execution_failed',
    error_message: error.message,
    step_id: step.step_id,
    step_title: step.title,
    stack_trace: error.stack
  });

  // Send error callback to DisruptIQ
  await sendCallbackWithRetry('http://backend:8000/api/n8n/callback/thought-update', {
    thought_stream_id: $json.trace.thought_stream_id,
    thought_type: 'ERROR',
    title: `❌ Erreur: ${step.title}`,
    content: error.message,
    agent: 'N8N_WaterLeak',
    progress: currentProgress
  });
}
```

### B. Backend - Error Callback Handling

```python
# backend/app/api/endpoints/n8n_callback.py
@router.post("/thought-update")
async def receive_thought_update(callback: ThoughtUpdateCallback):
    """Receive real-time updates from N8N workflows"""
    try:
        # Store in ThoughtStream
        await thought_stream_service.add_thought(callback)

        # If ERROR type, log to monitoring
        if callback.thought_type == "ERROR":
            logger.error(
                "n8n_workflow_error",
                thought_stream_id=callback.thought_stream_id,
                title=callback.title,
                content=callback.content,
                agent=callback.agent,
                metadata=callback.metadata
            )

            # Alert if critical
            if callback.metadata and callback.metadata.get("is_critical"):
                await alert_service.send_critical_alert(callback)

        return {"status": "ok"}
    except Exception as e:
        logger.error("callback_processing_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

### C. Monitoring Dashboard

**Métriques à tracker** :

1. **Workflow Executions**
   - Total executions / jour
   - Success rate
   - Average execution time
   - P95 / P99 execution time

2. **Step Failures**
   - Failed steps by type
   - Most failing steps
   - Retry success rate

3. **Callback Health**
   - Callback success rate
   - Average callback latency
   - Failed callbacks (need retry)

4. **Idempotence**
   - Duplicate requests detected
   - Duplicate rate

**Stack Grafana + Prometheus** :

```yaml
# docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**N8N expose metrics** :

```javascript
// N8N: Send metrics to Prometheus
const metrics = {
  workflow_executions_total: 1,
  workflow_execution_duration_seconds: executionTime,
  workflow_execution_status: status,  // success, failed, partial
  workflow_steps_executed_total: stepsExecuted,
  workflow_steps_failed_total: stepsFailed
};

// Push to Prometheus Pushgateway
await $http.request({
  method: 'POST',
  url: 'http://prometheus-pushgateway:9091/metrics/job/n8n_workflows',
  body: formatPrometheusMetrics(metrics)
});
```

---

## 🔧 5. Graceful Degradation

### Principe
Si une étape non-critique échoue, continuer les autres étapes.

### Implémentation

```javascript
// N8N: Execute steps with graceful degradation
const steps = $json.workflow_data.steps;
const results = [];
let criticalFailed = false;

for (const step of steps) {
  // Skip disabled steps
  if (!step.enabled) {
    results.push({
      step_id: step.step_id,
      status: 'skipped',
      reason: 'disabled_by_user'
    });
    continue;
  }

  try {
    // Execute step
    const result = await executeStep(step);

    results.push({
      step_id: step.step_id,
      status: 'success',
      result: result
    });

    // Send progress callback
    await sendProgressCallback(step, 'success');

  } catch (error) {
    console.error(`Step ${step.step_id} failed:`, error.message);

    results.push({
      step_id: step.step_id,
      status: 'failed',
      error: error.message
    });

    // Send error callback
    await sendProgressCallback(step, 'failed', error.message);

    // If critical step failed → STOP workflow
    if (step.is_critical) {
      console.error(`CRITICAL step ${step.step_id} failed, aborting workflow`);
      criticalFailed = true;
      break;
    }

    // Non-critical step failed → Continue
    console.warn(`Non-critical step ${step.step_id} failed, continuing`);
  }
}

// Determine final status
let finalStatus;
const failedSteps = results.filter(r => r.status === 'failed').length;
const successSteps = results.filter(r => r.status === 'success').length;

if (criticalFailed) {
  finalStatus = 'failed';
} else if (failedSteps > 0) {
  finalStatus = 'partial_success';
} else {
  finalStatus = 'success';
}

// Send final result
await sendFinalResultCallback({
  status: finalStatus,
  steps_executed: successSteps,
  steps_failed: failedSteps,
  results: results
});
```

**Résultat** :
- ✅ Étape 1 (critique) : Succès → Continue
- ❌ Étape 2 (non-critique) : Échec → Continue quand même
- ✅ Étape 3 (critique) : Succès → Continue
- ✅ Étape 4 (non-critique) : Succès → Continue
- **Status final** : `partial_success` (1 échec non-critique)

---

## 🧪 6. Testing et Validation

### A. Test d'Idempotence

```bash
# Test: Send same request_id twice
REQUEST_ID="req_test_idempotence_123"

# First call
curl -X POST http://localhost:5678/webhook/emergency-water-leak \
  -H "Authorization: Bearer TOKEN" \
  -d "{\"trace\": {\"request_id\": \"$REQUEST_ID\", ...}}"

# Second call (should be skipped)
curl -X POST http://localhost:5678/webhook/emergency-water-leak \
  -H "Authorization: Bearer TOKEN" \
  -d "{\"trace\": {\"request_id\": \"$REQUEST_ID\", ...}}"

# Expected: Second call returns {skipped: true}
```

### B. Test de Retry

```bash
# Test: Simulate backend down
docker-compose stop backend

# Trigger N8N workflow
curl -X POST http://localhost:5678/webhook/emergency-water-leak \
  -H "Authorization: Bearer TOKEN" \
  -d @payload.json

# Check N8N logs for retry attempts
docker-compose logs n8n | grep "Callback attempt"

# Expected: 3 retry attempts before giving up

# Restart backend
docker-compose start backend

# Trigger again → Should succeed
```

### C. Test de Timeout

```javascript
// N8N Test Node: Simulate slow action
await new Promise(resolve => setTimeout(resolve, 35000)); // 35 sec

// Expected: Timeout at 30 sec, error logged, workflow continues
```

### D. Test de Graceful Degradation

```bash
# Payload with 1 critical + 2 non-critical steps
# Simulate failure on non-critical step 2

# Expected:
# - Step 1 (critical): Success
# - Step 2 (non-critical): Failed (but workflow continues)
# - Step 3 (non-critical): Success
# - Final status: "partial_success"
```

---

## 📋 Production Checklist

Avant de déployer en production :

### Infrastructure
- [ ] Redis déployé et configuré (idempotence)
- [ ] Prometheus + Grafana configurés (monitoring)
- [ ] Sentry ou équivalent configuré (error tracking)
- [ ] N8N workflow timeout : 300s
- [ ] HTTP request timeout : 30s

### Code N8N
- [ ] Idempotence check (Redis ou in-memory)
- [ ] Retry logic sur tous les callbacks (3 retries, exponential backoff)
- [ ] Timeout handlers sur toutes les actions
- [ ] Error logging structuré
- [ ] Graceful degradation (critical vs non-critical steps)
- [ ] Validation du payload en entrée
- [ ] Metrics export vers Prometheus

### Backend DisruptIQ
- [ ] Request ID unique généré
- [ ] Payload validation avec Pydantic
- [ ] Error callback handling
- [ ] Monitoring des callbacks reçus
- [ ] Alertes sur erreurs critiques

### Tests
- [ ] Test d'idempotence (double envoi)
- [ ] Test de retry (backend down)
- [ ] Test de timeout (action lente)
- [ ] Test de graceful degradation (step failed)
- [ ] Load test (100 workflows simultanés)

### Documentation
- [ ] Contrat API figé et versionné
- [ ] Runbook pour incidents
- [ ] Procédure de rollback
- [ ] Playbook d'alertes

---

## 🚨 Runbook - Incidents Production

### Incident 1 : Workflow bloqué (hanging)

**Symptômes** : Workflow ne se termine jamais, ThoughtStream reste à 70%

**Diagnostic** :
```bash
# Check N8N execution status
docker-compose logs n8n | grep "execution-id-xxx"

# Check Redis for stuck request
docker-compose exec redis redis-cli GET "n8n:request:req_xxx"
```

**Résolution** :
1. Identifier le step bloqué dans N8N UI
2. Cancel l'exécution manuellement
3. Cleanup Redis : `redis-cli DEL n8n:request:req_xxx`
4. Vérifier les timeouts dans N8N settings

### Incident 2 : Callbacks ne passent pas

**Symptômes** : N8N exécute mais DisruptIQ ne reçoit rien

**Diagnostic** :
```bash
# Check N8N logs pour retry attempts
docker-compose logs n8n | grep "Callback attempt"

# Check backend logs
docker-compose logs backend | grep "n8n_callback"

# Test connectivity
docker-compose exec n8n curl http://backend:8000/health
```

**Résolution** :
1. Vérifier network connectivity entre N8N et Backend
2. Vérifier auth token dans N8N
3. Vérifier endpoint backend actif : `/api/n8n/callback/health`
4. Forcer retry manuel si besoin

### Incident 3 : Duplicate executions

**Symptômes** : Même workflow exécuté 2 fois

**Diagnostic** :
```bash
# Check Redis pour le request_id
docker-compose exec redis redis-cli KEYS "n8n:request:req_*"
docker-compose exec redis redis-cli GET "n8n:request:req_xxx"
```

**Résolution** :
1. Vérifier que idempotence check est actif dans N8N
2. Vérifier TTL Redis (doit être > 1 hour)
3. Si Redis down → Restart Redis + check data persistence

---

## 📊 Résumé

### V1 (MVP - Dev)
- ✅ Basic error handling
- ✅ Simple try/catch
- ❌ Pas de Redis (in-memory fallback)
- ❌ Pas de retry (best effort)
- ❌ Monitoring basique (logs)

### V2 (Production)
- ✅ Idempotence avec Redis
- ✅ Retry logic avec exponential backoff
- ✅ Timeout management
- ✅ Structured logging
- ✅ Graceful degradation
- ✅ Monitoring Grafana + Prometheus
- ✅ Error tracking Sentry
- ✅ Runbook incidents

### Priorités

**P0 (Must-have)** :
1. Idempotence (Redis ou in-memory)
2. Error handling (try/catch + logging)
3. Callback retry (3 attempts minimum)

**P1 (Should-have)** :
4. Timeout management
5. Graceful degradation
6. Basic monitoring

**P2 (Nice-to-have)** :
7. Advanced monitoring (Grafana)
8. Error tracking (Sentry)
9. Load testing

---

**Auteur** : Claude (Sonnet 4.5)
**Date** : 2025-11-23
**Status** : Production Hardening Guide - Ready for Implementation
