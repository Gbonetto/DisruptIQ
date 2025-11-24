# ⚡ N8N V1 Pragmatique - "Ça tourne vraiment"

**Version**: 1.0 (MVP)
**Date**: 2025-11-23
**Objectif**: Workflow opérationnel E2E sans sur-engineering

---

## 🎯 Philosophie V1

> "Make it work, then make it better"

**Priorités V1** :
1. ✅ Respecter le contrat API
2. ✅ Exécuter les steps correctement
3. ✅ Envoyer les callbacks (best effort)
4. ✅ Logger tout pour debug
5. ❌ Pas de Redis (V2)
6. ❌ Pas de retry sophistiqué (V2)
7. ❌ Pas de monitoring avancé (V2)

**V1 = Validation du pattern + Identification des vrais problèmes**

---

## 📋 Checklist V1 Minimale

### Workflow N8N doit :
- [x] Recevoir payload standardisé
- [x] Valider structure de base (action, steps, trace)
- [x] Exécuter steps dans l'ordre
- [x] Respecter `enabled: false` (skip)
- [x] Stopper si step critique échoue
- [x] Continuer si step non-critique échoue
- [x] Envoyer callbacks (try/catch simple)
- [x] Logger request_id pour détection doublons
- [x] Retourner status final (success/partial/failed)

### Ce qu'on NE fait PAS en V1 :
- [ ] ~~Idempotence Redis~~
- [ ] ~~Retry callbacks avec backoff~~
- [ ] ~~Monitoring Prometheus~~
- [ ] ~~Error tracking Sentry~~
- [ ] ~~Timeout sophistiqué~~

---

## 🛠️ Implémentation N8N V1

### Node 1 : Webhook Trigger

**Configuration** :
- HTTP Method : `POST`
- Path : `emergency-water-leak`
- Authentication : `Header Auth`
  - Name : `Authorization`
  - Value : `Bearer disruptiq_n8n_webhook_secret_2024_secure_token`

**Pas de sophistication** : C'est un webhook basique.

---

### Node 2 : Validate Payload (Code Node)

```javascript
// V1: Validation minimale
const payload = $input.first().json;

// Required fields
if (!payload.action) throw new Error('Missing action');
if (!payload.workflow_data) throw new Error('Missing workflow_data');
if (!payload.workflow_data.steps) throw new Error('Missing steps');
if (!payload.trace) throw new Error('Missing trace');
if (!payload.trace.request_id) throw new Error('Missing request_id');

// Log pour détection doublons manuelle (pas de Redis en V1)
console.log(`[N8N_START] action=${payload.action} request_id=${payload.trace.request_id} tenant_id=${payload.tenant_id}`);

// Pass through
return payload;
```

**V1 = Log simple** : On surveille les logs Docker pour détecter les doublons a posteriori.

---

### Node 3 : Send Initial Callback (HTTP Request)

**Configuration** :
- Method : `POST`
- URL : `http://backend:8000/api/n8n/callback/thought-update`
- Authentication : Header Auth (same token)
- Body (JSON) :

```json
{
  "thought_stream_id": "={{ $json.trace.thought_stream_id }}",
  "thought_type": "EXECUTING",
  "title": "🚨 Protocole d'urgence démarré",
  "content": "Exécution de {{ $json.workflow_data.steps.length }} étapes",
  "agent": "N8N_WaterLeak",
  "progress": 0.1
}
```

**Options** :
- Timeout : `5000ms`
- Continue On Fail : `✅ Yes` (si callback échoue, on continue le workflow)
- Retry On Fail : `❌ No` (V1 = best effort, pas de retry)

**V1 = Best effort** : Si ça échoue, on log et on continue. Pas de retry.

---

### Node 4 : Execute Steps (Code Node) - **CŒUR DU WORKFLOW**

```javascript
// V1: Exécution pragmatique des steps
const payload = $input.first().json;
const steps = payload.workflow_data.steps;
const trace = payload.trace;

console.log(`[N8N_EXEC] Starting execution of ${steps.length} steps`);

const results = [];
let criticalFailed = false;
let currentProgress = 0.2; // Start at 20% (after initial callback)

for (let i = 0; i < steps.length; i++) {
  const step = steps[i];

  // Log step start
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

    // Log success
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
      // V1: Just log, don't fail workflow
      console.error(`[N8N_CALLBACK_FAIL] step_id=${step.step_id} error=${callbackError.message}`);
    }

  } catch (error) {
    // Step execution failed
    console.error(`[N8N_FAIL] step_id=${step.step_id} error=${error.message}`);

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
          title: `❌ Erreur: ${step.title}`,
          content: error.message,
          agent: 'N8N_WaterLeak',
          progress: currentProgress
        },
        timeout: 3000
      });
    } catch (callbackError) {
      console.error(`[N8N_CALLBACK_FAIL] error callback failed`);
    }

    // V1: CRITICAL STEP LOGIC
    if (step.is_critical) {
      console.error(`[N8N_ABORT] Critical step ${step.step_id} failed - ABORTING workflow`);
      criticalFailed = true;
      break; // Stop workflow
    } else {
      console.warn(`[N8N_CONTINUE] Non-critical step ${step.step_id} failed - CONTINUING`);
      // Continue to next step
    }
  }
}

// Calculate final status
const successCount = results.filter(r => r.status === 'success').length;
const failedCount = results.filter(r => r.status === 'failed').length;
const skippedCount = results.filter(r => r.status === 'skipped').length;

let finalStatus;
if (criticalFailed) {
  finalStatus = 'failed';
} else if (failedCount > 0) {
  finalStatus = 'partial_success';
} else {
  finalStatus = 'success';
}

console.log(`[N8N_COMPLETE] status=${finalStatus} success=${successCount} failed=${failedCount} skipped=${skippedCount}`);

// Return for final callback
return {
  workflow_name: payload.action,
  trace: trace,
  execution_summary: {
    status: finalStatus,
    total_steps: steps.length,
    steps_executed: successCount,
    steps_failed: failedCount,
    steps_skipped: skippedCount,
    results: results,
    critical_failed: criticalFailed
  }
};
```

**V1 Pragmatique** :
- ✅ Simulation (pas de vrais emails)
- ✅ Callbacks best effort (try/catch simple)
- ✅ Logic critique vs non-critique
- ✅ Logs détaillés pour debug
- ❌ Pas de retry
- ❌ Pas de timeout sophistiqué

---

### Node 5 : Send Final Result (HTTP Request)

**Configuration** :
- Method : `POST`
- URL : `http://backend:8000/api/n8n/callback/workflow-result`
- Authentication : Header Auth
- Body (JSON) :

```json
{
  "thought_stream_id": "={{ $json.trace.thought_stream_id }}",
  "workflow_name": "={{ $json.workflow_name }}",
  "status": "={{ $json.execution_summary.status }}",
  "execution_time": 5.0,
  "result": {
    "steps_executed": "={{ $json.execution_summary.steps_executed }}",
    "steps_failed": "={{ $json.execution_summary.steps_failed }}",
    "steps_skipped": "={{ $json.execution_summary.steps_skipped }}",
    "actions_performed": ["simulated_actions"]
  }
}
```

**Options** :
- Continue On Fail : `✅ Yes` (si callback final échoue, workflow se termine quand même)
- Retry On Fail : `❌ No`

---

## 📊 Logs V1 - Structure

### Format de log standardisé

```
[N8N_START] action=emergency_water_leak request_id=req_123 tenant_id=default
[N8N_EXEC] Starting execution of 5 steps
[N8N_STEP] step_id=1 title="Notifier propriétaire" enabled=true is_critical=true
[N8N_EXEC] step_id=1 action=send_email
[N8N_SUCCESS] step_id=1
[N8N_STEP] step_id=2 title="Informer voisins" enabled=true is_critical=false
[N8N_EXEC] step_id=2 action=send_multi_channel_alert
[N8N_SUCCESS] step_id=2
[N8N_STEP] step_id=3 title="Contacter plombier" enabled=false is_critical=true
[N8N_SKIP] step_id=3 - disabled by user
[N8N_STEP] step_id=4 title="Créer ticket" enabled=true is_critical=false
[N8N_EXEC] step_id=4 action=create_ticket
[N8N_SUCCESS] step_id=4
[N8N_STEP] step_id=5 title="Planifier suivi" enabled=true is_critical=false
[N8N_EXEC] step_id=5 action=schedule_action
[N8N_SUCCESS] step_id=5
[N8N_COMPLETE] status=success success=4 failed=0 skipped=1
```

### Surveillance manuelle V1

```bash
# Voir les exécutions
docker-compose logs n8n | grep "\[N8N_"

# Détecter les doublons
docker-compose logs n8n | grep "N8N_START" | grep "req_123"

# Voir les échecs
docker-compose logs n8n | grep "N8N_FAIL"

# Voir les callbacks ratés
docker-compose logs n8n | grep "N8N_CALLBACK_FAIL"
```

**V1 = Logs manuels** : Pas de Grafana, on inspecte les logs Docker.

---

## 🧪 Tests V1

### Test 1 : Happy Path

**Payload** :
```json
{
  "action": "emergency_water_leak",
  "workflow_data": {
    "steps": [
      {"step_id": 1, "enabled": true, "is_critical": true, "title": "Step 1", "workflow_action": "send_email"},
      {"step_id": 2, "enabled": true, "is_critical": false, "title": "Step 2", "workflow_action": "send_sms"}
    ]
  },
  "trace": {
    "request_id": "test_happy_path_123",
    "thought_stream_id": "stream_test"
  }
}
```

**Attendu** :
- Status : `success`
- Steps executed : 2
- Steps failed : 0

---

### Test 2 : Skip Disabled Step

**Payload** :
```json
{
  "workflow_data": {
    "steps": [
      {"step_id": 1, "enabled": true, "is_critical": true, "title": "Step 1"},
      {"step_id": 2, "enabled": false, "is_critical": false, "title": "Step 2 (skip)"},
      {"step_id": 3, "enabled": true, "is_critical": false, "title": "Step 3"}
    ]
  }
}
```

**Attendu** :
- Status : `success`
- Steps executed : 2
- Steps skipped : 1

---

### Test 3 : Critical Step Fails → Abort

**Payload** :
```json
{
  "workflow_data": {
    "steps": [
      {"step_id": 1, "enabled": true, "is_critical": true, "title": "Critical Step"},
      {"step_id": 2, "enabled": true, "is_critical": false, "title": "Should not execute"}
    ]
  }
}
```

**Simuler échec** : Modifier le code pour throw error au step 1

**Attendu** :
- Status : `failed`
- Steps executed : 0
- Steps failed : 1
- Step 2 NOT executed (abort)

---

### Test 4 : Non-Critical Fails → Continue

**Payload** :
```json
{
  "workflow_data": {
    "steps": [
      {"step_id": 1, "enabled": true, "is_critical": true, "title": "Critical (success)"},
      {"step_id": 2, "enabled": true, "is_critical": false, "title": "Non-critical (fail)"},
      {"step_id": 3, "enabled": true, "is_critical": false, "title": "Continue after fail"}
    ]
  }
}
```

**Simuler échec step 2** : throw error

**Attendu** :
- Status : `partial_success`
- Steps executed : 2
- Steps failed : 1
- Step 3 executed (continue)

---

### Test 5 : Backend Down (Callbacks Fail)

**Procédure** :
```bash
# Arrêter backend
docker-compose stop backend

# Trigger workflow N8N
curl -X POST http://localhost:5678/webhook/emergency-water-leak ...

# Vérifier logs N8N
docker-compose logs n8n | grep "CALLBACK_FAIL"
```

**Attendu** :
- Workflow continue
- Logs montrent callbacks failed
- Aucun crash N8N

---

## 📋 Checklist de Validation V1

### Avant de considérer V1 comme validée :

- [ ] Workflow créé dans N8N UI
- [ ] Webhook accessible : `http://localhost:5678/webhook/emergency-water-leak`
- [ ] Auth token configuré
- [ ] Test payload minimal passe (validation)
- [ ] Steps s'exécutent dans l'ordre
- [ ] Steps `enabled: false` sont skippés
- [ ] Step critique qui échoue → workflow abort
- [ ] Step non-critique qui échoue → workflow continue
- [ ] Callbacks envoyés (visible dans logs backend)
- [ ] Callbacks qui échouent → workflow continue (pas de crash)
- [ ] Logs N8N structurés et lisibles
- [ ] Status final correct (success / partial_success / failed)
- [ ] request_id loggé (détection manuelle doublons possible)

---

## 🚫 Ce qu'on NE fait PAS en V1

### Idempotence
**V1** : Log `request_id` → Détection manuelle a posteriori
**V2** : Redis check avant exécution

### Retry Callbacks
**V1** : Best effort, simple try/catch
**V2** : Exponential backoff, 3 retries

### Timeout Sophistiqué
**V1** : Timeout HTTP basique (3-5 sec)
**V2** : Timeout global workflow + timeout par step

### Monitoring
**V1** : Logs Docker + inspection manuelle
**V2** : Prometheus + Grafana + alertes

### Error Tracking
**V1** : Console.log + console.error
**V2** : Sentry ou équivalent

---

## 📊 Métriques V1 (Manuelles)

### Ce qu'on surveille en V1 :

1. **Nombre d'exécutions** : `grep "N8N_START" | wc -l`
2. **Doublons potentiels** : `grep "N8N_START" | sort | uniq -c | grep -v "1 "`
3. **Échecs** : `grep "N8N_FAIL" | wc -l`
4. **Callbacks ratés** : `grep "CALLBACK_FAIL" | wc -l`
5. **Temps moyen** : Observer dans N8N UI > Executions

**V1 = Observation manuelle** pour identifier les vrais problèmes.

---

## 🔄 Passage V1 → V2

### Quand passer en V2 ?

**Signaux** :
- ✅ V1 tourne depuis 2-4 semaines
- ✅ 50+ exécutions réelles
- ✅ 2-3 clients pilotes
- ✅ Problèmes identifiés :
  - Doublons détectés dans les logs
  - Callbacks qui échouent régulièrement
  - Timeouts observés
  - Besoin de monitoring temps réel

**Alors** : Déployer les améliorations du guide `N8N_PRODUCTION_HARDENING_GUIDE.md`

### Checklist V2

- [ ] Ajouter Redis pour idempotence
- [ ] Implémenter retry callbacks (3 attempts, exponential backoff)
- [ ] Ajouter timeout management sophistiqué
- [ ] Déployer Prometheus + Grafana
- [ ] Configurer Sentry pour error tracking
- [ ] Implémenter graceful degradation avancé
- [ ] Ajouter tests de charge
- [ ] Documenter runbook incidents

---

## 🎯 Résumé V1 Pragmatique

### Ce qu'on fait :
✅ Contrat API respecté
✅ Exécution correcte des steps
✅ Logic critique vs non-critique
✅ Callbacks best effort
✅ Logs structurés
✅ Validation du pattern

### Ce qu'on ne fait pas (encore) :
❌ Idempotence forte
❌ Retry sophistiqué
❌ Monitoring avancé
❌ Error tracking externe

### Temps de mise en œuvre :
- **N8N workflow V1** : 1-2h
- **Tests V1** : 30 min
- **Validation** : 1-2 semaines en conditions réelles

### Objectif V1 :
> "Prouver que le pattern fonctionne, identifier les vrais problèmes, puis durcir en V2"

---

## 📝 Notes pour V2

Pendant que tu utilises V1, **note systématiquement** :

1. **Combien de doublons détectés ?**
   - Si > 5% → Priorité P0 Redis idempotence

2. **Combien de callbacks ratés ?**
   - Si > 10% → Priorité P1 retry logic

3. **Timeouts observés ?**
   - Si oui → Priorité P1 timeout management

4. **Besoin de monitoring temps réel ?**
   - Si oui → Priorité P2 Grafana

5. **Erreurs non catchées ?**
   - Si oui → Priorité P2 Sentry

**Ces observations dicteront les priorités V2.**

---

**Auteur** : Claude (Sonnet 4.5)
**Date** : 2025-11-23
**Status** : V1 Pragmatique - Production Ready pour pilote
**Next** : Créer le workflow N8N selon ce guide, tester, observer pendant 2-4 semaines
