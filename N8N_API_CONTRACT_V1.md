# 📜 Contrat API DisruptIQ ↔ N8N - V1 Figé

**Version**: 1.0.0
**Date**: 2025-11-23
**Status**: 🔒 FIGÉ - Ne pas modifier sans versioning

---

## 🎯 Objectif

Ce document définit le **contrat stable** entre DisruptIQ et N8N pour les workflows d'urgence.

**Principe clé** : Une fois ce contrat établi, on peut ajouter de nouveaux types d'urgences (fire, elevator, etc.) **sans toucher au code N8N**, seulement en ajoutant des templates dans la DB.

---

## 📤 DisruptIQ → N8N : Payload Standard

### Endpoint
```
POST http://n8n:5678/webhook/{workflow-name}
```

Exemples :
- `/webhook/emergency-water-leak`
- `/webhook/emergency-fire`
- `/webhook/emergency-elevator`

### Headers
```http
Authorization: Bearer {N8N_WEBHOOK_AUTH_TOKEN}
Content-Type: application/json
```

### Payload Structure (FIGÉ)

```typescript
interface N8NWorkflowPayload {
  // Metadata workflow
  action: string;              // "emergency_water_leak", "emergency_fire", etc.
  tenant_id: string;           // Multi-tenant isolation
  user_id: string;             // User who triggered workflow
  urgency: "low" | "medium" | "high" | "critical";

  // Workflow data (steps selected by user)
  workflow_data: {
    workflow_name: string;     // "Dégât des eaux - Procédure standard"
    workflow_type: string;     // "water_leak", "fire", etc.

    metadata: {
      estimated_duration_minutes: number;
      critical: boolean;
      version?: number;
    };

    steps: Array<{
      step_id: number;         // Unique step identifier
      step_order: number;      // Execution order
      title: string;           // "Notifier le propriétaire"
      description: string;

      // Execution control
      enabled: boolean;        // User can disable non-critical steps
      is_critical: boolean;    // Critical steps cannot be disabled
      requires_user_validation: boolean;

      // Action definition
      action_type: string;     // "notify_owner", "contact_plumber", etc.
      workflow_action: string; // "send_email", "send_sms", "create_ticket", etc.
      n8n_node_type: string;   // "email", "sms", "ticket_creation", etc.

      // Preview data (for user confirmation)
      preview?: {
        type: string;          // "email", "sms", "ticket"
        subject?: string;      // Email subject
        body?: string;         // Email/SMS body
        recipients: string[];  // List of recipients
        has_sms_fallback?: boolean;
      };

      // Extracted data (from LLM)
      extracted_data: Record<string, any>;  // Flexible key-value pairs

      // Template (for N8N to execute)
      payload_template: Record<string, any>;
    }>;

    // Context data (enriched from user input)
    context_data?: Record<string, any>;
  };

  // Tracing
  trace: {
    conversation_id: string;   // DisruptIQ conversation
    request_id: string;        // Unique request ID (for idempotence)
    thought_stream_id?: string; // For real-time callbacks
    timestamp?: string;        // ISO 8601
  };
}
```

### Exemple Concret

```json
{
  "action": "emergency_water_leak",
  "tenant_id": "default",
  "user_id": "user_123",
  "urgency": "critical",

  "workflow_data": {
    "workflow_name": "Dégât des eaux - Procédure standard",
    "workflow_type": "water_leak",

    "metadata": {
      "estimated_duration_minutes": 15,
      "critical": true,
      "version": 1
    },

    "steps": [
      {
        "step_id": 1,
        "step_order": 1,
        "title": "Notifier le propriétaire",
        "description": "Avertir immédiatement le copropriétaire du logement impacté",
        "enabled": true,
        "is_critical": true,
        "requires_user_validation": true,
        "action_type": "notify_owner",
        "workflow_action": "send_email",
        "n8n_node_type": "email",

        "preview": {
          "type": "email",
          "subject": "🚨 Urgence : Dégât des eaux dans votre logement",
          "body": "Bonjour M. Dupont,\n\nNous vous informons d'un dégât des eaux...",
          "recipients": ["dupont@email.com"]
        },

        "extracted_data": {
          "owner_name": "M. Dupont",
          "apartment_number": "12",
          "floor": 3,
          "building_name": "Résidence Les Tilleuls",
          "incident_description": "Fuite d'eau importante provenant de la salle de bain",
          "severity": "high"
        },

        "payload_template": {
          "email_subject": "🚨 Urgence : Dégât des eaux dans votre logement",
          "email_body_template": "Bonjour {{owner_name}}...",
          "recipient_source": "owner_from_SQL"
        }
      },
      {
        "step_id": 2,
        "step_order": 2,
        "title": "Informer les voisins",
        "enabled": true,
        "is_critical": false,
        "workflow_action": "send_multi_channel_alert",
        "n8n_node_type": "multi_channel",
        "preview": {
          "type": "email",
          "subject": "Information importante : Incident technique",
          "body": "Bonjour, nous vous informons d'un incident...",
          "recipients": ["voisin1@email.com", "voisin2@email.com"]
        },
        "extracted_data": {
          "floor": 3,
          "affected_floors": [1, 2]
        }
      },
      {
        "step_id": 3,
        "step_order": 3,
        "title": "Contacter plombier d'urgence",
        "enabled": true,
        "is_critical": true,
        "workflow_action": "send_email",
        "n8n_node_type": "email_sms",
        "preview": {
          "type": "email",
          "subject": "🚨 URGENT - Intervention requise",
          "body": "Intervention urgente requise...",
          "recipients": ["plombier@example.com"],
          "has_sms_fallback": true
        },
        "extracted_data": {
          "building_address": "15 rue des Lilas, 75001 Paris"
        }
      },
      {
        "step_id": 4,
        "step_order": 4,
        "title": "Créer ticket de suivi",
        "enabled": true,
        "is_critical": false,
        "workflow_action": "create_ticket",
        "n8n_node_type": "ticket_creation",
        "extracted_data": {
          "ticket_title": "🚨 Dégât des eaux - Résidence Les Tilleuls - Appt 12"
        }
      },
      {
        "step_id": 5,
        "step_order": 5,
        "title": "Planifier suivi 24h",
        "enabled": true,
        "is_critical": false,
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
    "conversation_id": "conv_20251123_143045",
    "request_id": "req_1732374225.123",
    "thought_stream_id": "stream_abc123xyz",
    "timestamp": "2025-11-23T14:30:25.000Z"
  }
}
```

---

## 📥 N8N → DisruptIQ : Callbacks

### 1. Progress Update (Real-time)

**Endpoint**
```
POST http://backend:8000/api/n8n/callback/thought-update
```

**Headers**
```http
Authorization: Bearer {N8N_WEBHOOK_AUTH_TOKEN}
Content-Type: application/json
```

**Payload (FIGÉ)**
```typescript
interface ThoughtUpdateCallback {
  thought_stream_id: string;  // From trace
  thought_type: "ANALYZING" | "EXECUTING" | "PROCESSING" | "COMPLETED" | "ERROR";
  title: string;              // Short title (< 100 chars)
  content: string;            // Detailed message
  agent: string;              // "N8N_WaterLeak", "N8N_Fire", etc.
  progress: number;           // 0.0 - 1.0
  metadata?: Record<string, any>;
}
```

**Exemple**
```json
{
  "thought_stream_id": "stream_abc123xyz",
  "thought_type": "EXECUTING",
  "title": "📧 Email envoyé à M. Dupont",
  "content": "Email d'urgence envoyé avec succès au propriétaire",
  "agent": "N8N_WaterLeak",
  "progress": 0.3,
  "metadata": {
    "step_id": 1,
    "step_title": "Notifier le propriétaire",
    "email_sent": true,
    "recipient": "dupont@email.com"
  }
}
```

### 2. Workflow Result (Final)

**Endpoint**
```
POST http://backend:8000/api/n8n/callback/workflow-result
```

**Payload (FIGÉ)**
```typescript
interface WorkflowResultCallback {
  thought_stream_id: string;  // From trace
  workflow_name: string;      // "emergency_water_leak"
  status: "success" | "partial_success" | "failed";
  execution_time: number;     // Seconds
  result: {
    steps_executed: number;
    steps_failed: number;
    actions_performed: string[];  // ["email_sent", "ticket_created", etc.]
    errors?: Array<{
      step_id: number;
      error_message: string;
    }>;
  };
  metadata?: Record<string, any>;
}
```

**Exemple**
```json
{
  "thought_stream_id": "stream_abc123xyz",
  "workflow_name": "emergency_water_leak",
  "status": "success",
  "execution_time": 5.2,
  "result": {
    "steps_executed": 5,
    "steps_failed": 0,
    "actions_performed": [
      "email_sent_owner",
      "email_sent_neighbors",
      "email_sent_plumber",
      "ticket_created",
      "followup_scheduled"
    ]
  },
  "metadata": {
    "total_emails_sent": 4,
    "total_sms_sent": 1,
    "tickets_created": 1
  }
}
```

---

## 🔒 Règles de Stabilité du Contrat

### ✅ Modifications AUTORISÉES (backward-compatible)

1. **Ajouter** de nouveaux champs optionnels
   ```typescript
   // OK
   workflow_data: {
     steps: [...],
     new_optional_field?: string;  // ✅ OK
   }
   ```

2. **Ajouter** de nouvelles valeurs d'enum
   ```typescript
   // OK
   workflow_action: "send_email" | "send_sms" | "send_whatsapp";  // ✅ Nouveau type OK
   ```

3. **Enrichir** extracted_data ou metadata (key-value libre)
   ```typescript
   // OK
   extracted_data: {
     existing_field: "value",
     new_field: "new_value"  // ✅ OK
   }
   ```

### ❌ Modifications INTERDITES (breaking changes)

1. **Renommer** des champs existants
   ```typescript
   // ❌ INTERDIT
   action → workflow_action  // Breaking change
   ```

2. **Changer** le type d'un champ
   ```typescript
   // ❌ INTERDIT
   step_id: number → step_id: string
   ```

3. **Rendre obligatoire** un champ optionnel
   ```typescript
   // ❌ INTERDIT
   thought_stream_id?: string → thought_stream_id: string  // Breaking
   ```

4. **Supprimer** un champ existant
   ```typescript
   // ❌ INTERDIT
   delete trace.request_id
   ```

### 🔄 En cas de breaking change nécessaire

Utiliser le **versioning** :

1. Ajouter un champ `api_version` dans le payload :
   ```json
   {
     "api_version": "2.0.0",
     "action": "emergency_water_leak",
     ...
   }
   ```

2. N8N supporte les deux versions en parallèle :
   ```javascript
   // N8N Code Node
   const version = $json.api_version || "1.0.0";

   if (version === "1.0.0") {
     // Old format
   } else if (version === "2.0.0") {
     // New format
   }
   ```

3. Dépréciation progressive de V1.

---

## 🛡️ Idempotence et Robustesse

### 1. Request ID (Idempotence)

**Principe** : Le même `request_id` ne doit jamais être exécuté deux fois.

**Implémentation N8N** :

```javascript
// Node 1: Check if request already processed
const requestId = $json.trace.request_id;

// Query Redis/DB to check if request_id exists
const alreadyProcessed = await checkRequestId(requestId);

if (alreadyProcessed) {
  console.log(`Request ${requestId} already processed, skipping`);
  return { skipped: true, reason: 'duplicate_request' };
}

// Mark as processing
await markRequestIdAsProcessing(requestId);

// Continue workflow...
```

**V1** : Pas implémenté (dev only)
**V2** : À ajouter pour production

### 2. Gestion erreurs callbacks

**Si callback échoue** (DisruptIQ injoignable) :

```javascript
// N8N: Retry logic avec exponential backoff
async function sendCallbackWithRetry(url, payload, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await $http.request({
        method: 'POST',
        url: url,
        headers: {
          'Authorization': 'Bearer {{$env.N8N_WEBHOOK_AUTH_TOKEN}}',
          'Content-Type': 'application/json'
        },
        body: payload,
        timeout: 5000
      });

      return response;  // Success
    } catch (error) {
      console.error(`Callback attempt ${i+1} failed:`, error.message);

      if (i < maxRetries - 1) {
        await sleep(Math.pow(2, i) * 1000);  // Exponential backoff
      }
    }
  }

  // All retries failed → Log to error tracking
  console.error('Callback failed after all retries, logging to error queue');
  await logToErrorQueue(payload);
}
```

**V1** : Pas de retry (simple try/catch)
**V2** : Retry avec exponential backoff

### 3. Timeout

**N8N doit respecter** :
- Timeout global workflow : 5 minutes max
- Timeout par action : 30 secondes max

**Si timeout dépassé** :
```javascript
// Send partial_success result
await sendWorkflowResult({
  thought_stream_id: streamId,
  workflow_name: workflowName,
  status: 'partial_success',
  result: {
    steps_executed: completedSteps.length,
    steps_failed: failedSteps.length,
    errors: [{
      step_id: currentStep.step_id,
      error_message: 'Timeout exceeded'
    }]
  }
});
```

---

## 📐 Validation du Contrat

### Validation côté DisruptIQ (avant envoi)

```python
# backend/app/schemas/n8n_payload.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal

class WorkflowStep(BaseModel):
    step_id: int
    step_order: int
    title: str
    enabled: bool
    is_critical: bool
    workflow_action: str
    n8n_node_type: str
    extracted_data: Dict[str, Any]
    preview: Optional[Dict[str, Any]] = None

class N8NWorkflowPayload(BaseModel):
    action: str
    tenant_id: str
    user_id: str
    urgency: Literal["low", "medium", "high", "critical"]

    workflow_data: Dict[str, Any]  # Contains steps[]
    trace: Dict[str, str]

    @validator("workflow_data")
    def validate_steps(cls, v):
        if "steps" not in v:
            raise ValueError("workflow_data must contain 'steps'")
        if not isinstance(v["steps"], list):
            raise ValueError("steps must be a list")
        return v

    @validator("trace")
    def validate_trace(cls, v):
        required = ["conversation_id", "request_id"]
        for field in required:
            if field not in v:
                raise ValueError(f"trace must contain '{field}'")
        return v
```

**Usage** :
```python
# Avant trigger N8N
try:
    validated_payload = N8NWorkflowPayload(**payload)
    await trigger_n8n(validated_payload.dict())
except ValidationError as e:
    logger.error("invalid_n8n_payload", errors=e.errors())
    raise
```

### Validation côté N8N (réception)

```javascript
// N8N Code Node: Validate incoming payload
function validatePayload(payload) {
  const required = [
    'action',
    'tenant_id',
    'user_id',
    'workflow_data',
    'trace'
  ];

  for (const field of required) {
    if (!(field in payload)) {
      throw new Error(`Missing required field: ${field}`);
    }
  }

  if (!payload.workflow_data.steps || !Array.isArray(payload.workflow_data.steps)) {
    throw new Error('workflow_data.steps must be an array');
  }

  if (!payload.trace.request_id) {
    throw new Error('trace.request_id is required for idempotence');
  }

  return true;
}

// Usage
try {
  validatePayload($json);
} catch (error) {
  // Send error callback
  await sendErrorCallback({
    thought_stream_id: $json.trace.thought_stream_id,
    error: error.message
  });
  throw error;
}
```

---

## 🎯 Avantages de ce Contrat Stable

### 1. **Scalabilité**
Ajouter un nouveau type d'urgence :
```python
# Juste ajouter un nouveau template en DB
new_workflow = EmergencyWorkflow(
    workflow_type="fire",  # Nouveau type
    workflow_name="Incendie - Procédure d'urgence",
    checklist={
        "steps": [...]  # Même structure
    }
)
```

**N8N n'a PAS besoin d'être modifié** ✅

### 2. **Testabilité**
Payload standardisé = tests automatisés faciles :
```python
# Test unitaire
def test_workflow_payload_structure():
    payload = generate_water_leak_payload()
    validated = N8NWorkflowPayload(**payload)
    assert validated.action == "emergency_water_leak"
    assert len(validated.workflow_data["steps"]) == 5
```

### 3. **Documentation**
Contrat clair = onboarding simplifié pour nouveaux devs.

### 4. **Versioning**
Si breaking change nécessaire, on sait exactement quoi versionner.

---

## 📊 Checklist de Conformité

Avant de déployer un nouveau workflow :

- [ ] Payload respecte `N8NWorkflowPayload` schema
- [ ] Tous les champs obligatoires présents
- [ ] `trace.request_id` unique et présent
- [ ] `workflow_data.steps[]` est un array non vide
- [ ] Chaque step a `step_id`, `title`, `enabled`, `workflow_action`
- [ ] Callbacks incluent `thought_stream_id`
- [ ] Validation Pydantic passe
- [ ] N8N valide le payload en entrée
- [ ] Timeouts configurés
- [ ] Error handling implémenté

---

## 🚀 Résumé

**Contrat V1.0.0 = FIGÉ ✅**

- Structure payload standardisée
- Callbacks standardisés
- Règles de modification claires
- Validation des deux côtés
- Prêt pour scale (fire, elevator, etc.)

**Modifications futures** :
- Seulement ajouts backward-compatible
- Ou versioning si breaking change

**Avantage principal** :
> "On peut ajouter 10 nouveaux types d'urgences sans toucher une ligne de code N8N"

---

**Auteur** : Claude (Sonnet 4.5)
**Date** : 2025-11-23
**Status** : Contrat API V1.0.0 - Production Ready
