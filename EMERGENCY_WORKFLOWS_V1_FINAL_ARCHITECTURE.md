# Emergency Workflows V1 - Architecture Finale

**Date**: 2025-11-23
**Approche**: Hybrid Smart Assistant (Agent-based + N8N pour emails uniquement)

---

## 🎯 Objectif

Créer un **assistant de procédure d'urgence** qui:
1. Détecte les urgences et génère des checklists personnalisées
2. Propose des **actions cliquables** pour chaque étape
3. Utilise les **agents existants** (SQL, Email, Web) pour la logique
4. Utilise **N8N uniquement pour l'envoi d'emails** (ce que DisruptIQ ne peut pas faire directement)

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER (Frontend)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
                 "URGENT: Dégât des eaux..."
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              WorkflowAgent (Backend)                        │
│  - Détecte intent URGENCE:water_leak                        │
│  - Charge template depuis PostgreSQL                        │
│  - Enrichit avec LLM (extraction contexte)                  │
│  - Génère checklist avec ACTIONS CLIQUABLES                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
                  Returns Response:
                  {
                    "type": "emergency_checklist",
                    "checklist": [...],
                    "quick_actions": [
                      {"id": "email_neighbors", "label": "Alerter voisins"},
                      {"id": "find_plumbers", "label": "Trouver plombiers"},
                      ...
                    ]
                  }
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Frontend affiche:                          │
│  - Checklist formatée                                       │
│  - Boutons d'action rapide                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
              User clique "Alerter voisins"
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         POST /api/emergency-actions/email_neighbors         │
│                                                             │
│  OrchestratorAgent:                                         │
│    1. SQLAgent → Trouve voisins étages inférieurs           │
│    2. EmailAgent → Génère brouillon personnalisé            │
│    3. Retourne brouillon pour validation                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
              User valide/modifie le brouillon
                            ↓
┌─────────────────────────────────────────────────────────────┐
│       POST /api/emergency-actions/send_validated_email      │
│                                                             │
│  Backend:                                                   │
│    → Trigger N8N workflow "send-bulk-email"                 │
│    → N8N envoie les emails                                  │
│    → Callback ThoughtStream (emails envoyés)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Composants

### 1. WorkflowAgent (Backend)

**Responsabilités:**
- Détecte urgences via intent classifier
- Charge template emergency_workflows depuis PostgreSQL
- Enrichit avec LLM pour extraire contexte
- **NOUVEAU**: Génère `quick_actions` au lieu de `requires_confirmation`

**Exemple de Réponse:**

```json
{
  "type": "emergency_checklist",
  "workflow_name": "Dégât des eaux - Procédure standard",
  "severity": "critical",
  "context": {
    "building_name": "Résidence Les Tilleuls",
    "apartment_number": "12",
    "floor": 3,
    "owner_name": "M. Dupont",
    "owner_email": "dupont@example.com",
    "owner_phone": "06 12 34 56 78"
  },
  "checklist": [
    {
      "step_id": 1,
      "title": "⚠️ Sécuriser la situation",
      "description": "Vérifier que l'eau est coupée et que M. Dupont a pris les précautions nécessaires",
      "manual": true,
      "actions": []
    },
    {
      "step_id": 2,
      "title": "📧 Alerter les voisins des étages inférieurs",
      "description": "Prévenir les copropriétaires potentiellement impactés (étages 1 et 2)",
      "manual": false,
      "actions": [
        {
          "id": "prepare_neighbor_email",
          "label": "Préparer email aux voisins",
          "type": "email_draft",
          "endpoint": "/api/emergency-actions/prepare-neighbor-email",
          "payload": {
            "building": "Résidence Les Tilleuls",
            "affected_floor": 3,
            "incident_type": "water_leak"
          }
        }
      ]
    },
    {
      "step_id": 3,
      "title": "🔧 Contacter plombier d'urgence",
      "description": "Trouver et contacter un plombier disponible",
      "manual": false,
      "actions": [
        {
          "id": "find_plumbers",
          "label": "Chercher plombiers disponibles",
          "type": "query",
          "endpoint": "/api/emergency-actions/find-plumbers",
          "payload": {
            "location": "Paris",
            "urgency": "immediate"
          }
        },
        {
          "id": "prepare_quote_request",
          "label": "Générer demande de devis",
          "type": "email_draft",
          "endpoint": "/api/emergency-actions/prepare-quote-request",
          "payload": {
            "incident_type": "water_leak",
            "building": "Résidence Les Tilleuls",
            "floor": 3,
            "urgency": "critical"
          }
        }
      ]
    },
    {
      "step_id": 4,
      "title": "📋 Documenter l'incident",
      "description": "Créer un rapport d'incident pour traçabilité",
      "manual": false,
      "actions": [
        {
          "id": "create_incident_report",
          "label": "Générer rapport d'incident",
          "type": "export",
          "endpoint": "/api/emergency-actions/create-incident-report",
          "payload": {
            "incident_data": "{{ all context }}"
          }
        }
      ]
    },
    {
      "step_id": 5,
      "title": "📅 Planifier suivi dans 24h",
      "description": "Programmer un rappel pour vérifier la résolution",
      "manual": false,
      "actions": [
        {
          "id": "schedule_reminder",
          "label": "Programmer rappel 24h",
          "type": "schedule",
          "endpoint": "/api/emergency-actions/schedule-reminder",
          "payload": {
            "delay_hours": 24,
            "reminder_text": "Vérifier résolution dégât des eaux - Résidence Les Tilleuls, Apt 12"
          }
        }
      ]
    }
  ],
  "message": "🚨 **Procédure d'urgence détectée**\n\n5 étapes recommandées pour gérer ce dégât des eaux. Utilisez les actions rapides ci-dessous."
}
```

---

### 2. Emergency Actions API (Backend - NOUVEAU)

**Endpoint unique**: `/api/emergency-actions/{action_id}`

Chaque action déclenche la logique appropriée:

#### **Action: `prepare-neighbor-email`**
```python
@router.post("/emergency-actions/prepare-neighbor-email")
async def prepare_neighbor_email(
    request: PrepareNeighborEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    # 1. SQLAgent → Trouve voisins des étages inférieurs
    neighbors = await sql_agent.query(
        f"SELECT * FROM residents WHERE building = '{request.building}'
         AND floor < {request.affected_floor}"
    )

    # 2. EmailAgent → Génère brouillon personnalisé
    draft = await email_agent.generate_draft(
        template="neighbor_water_leak_alert",
        context={
            "building": request.building,
            "affected_floor": request.affected_floor,
            "incident_type": request.incident_type
        },
        recipients=[n.email for n in neighbors]
    )

    # 3. Retourne brouillon pour validation
    return {
        "draft": {
            "recipients": draft.recipients,
            "subject": draft.subject,
            "body": draft.body
        },
        "next_action": {
            "id": "send_validated_email",
            "label": "Envoyer cet email",
            "endpoint": "/api/emergency-actions/send-email"
        }
    }
```

#### **Action: `find-plumbers`**
```python
@router.post("/emergency-actions/find-plumbers")
async def find_plumbers(
    request: FindPlumbersRequest,
    db: AsyncSession = Depends(get_db)
):
    # SQLAgent → Query plumbers table
    plumbers = await sql_agent.query(
        f"SELECT * FROM plumbers WHERE location LIKE '%{request.location}%' LIMIT 10"
    )

    return {
        "plumbers": [
            {
                "name": p.name,
                "email": p.email,
                "phone": p.phone,
                "actions": [
                    {
                        "id": "send_quote_request",
                        "label": f"Envoyer demande à {p.name}",
                        "endpoint": "/api/emergency-actions/send-quote-request",
                        "payload": {"plumber_id": p.id}
                    }
                ]
            }
            for p in plumbers
        ]
    }
```

#### **Action: `send-email`** (Final step - N8N)
```python
@router.post("/emergency-actions/send-email")
async def send_email(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    # Trigger N8N workflow "send-bulk-email"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.N8N_WEBHOOK_BASE_URL}/webhook/send-bulk-email",
            json={
                "recipients": request.recipients,
                "subject": request.subject,
                "body": request.body,
                "trace": {
                    "thought_stream_id": request.thought_stream_id
                }
            }
        )

    return {"status": "sent", "message": "Emails en cours d'envoi via N8N"}
```

---

### 3. N8N Micro-Workflows

#### **Workflow 1: `send-bulk-email`** (Priorité 1)

```json
{
  "name": "send-bulk-email",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "send-bulk-email"
      }
    },
    {
      "name": "Validate",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "// Validate auth + payload"
      }
    },
    {
      "name": "Loop Recipients",
      "type": "n8n-nodes-base.splitInBatches",
      "parameters": {
        "batchSize": 1
      }
    },
    {
      "name": "Send Email (SMTP/Gmail)",
      "type": "n8n-nodes-base.emailSend",
      "parameters": {
        "fromEmail": "noreply@disruptiq.com",
        "toEmail": "={{ $json.recipient }}",
        "subject": "={{ $json.subject }}",
        "text": "={{ $json.body }}"
      }
    },
    {
      "name": "Callback Progress",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://backend:8000/api/n8n/callback/thought-update",
        "body": {
          "thought_stream_id": "={{ $json.trace.thought_stream_id }}",
          "thought_type": "EXECUTING",
          "title": "Email envoyé à {{ $json.recipient }}",
          "progress": "={{ $json.index / $json.total }}"
        }
      }
    },
    {
      "name": "Final Callback",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://backend:8000/api/n8n/callback/workflow-result",
        "body": {
          "status": "success",
          "result": {
            "emails_sent": "={{ $json.total }}"
          }
        }
      }
    }
  ]
}
```

#### **Workflow 2: `schedule-reminder`** (Priorité 2 - optionnel V2)

```json
{
  "name": "schedule-reminder",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook"
    },
    {
      "name": "Wait 24h",
      "type": "n8n-nodes-base.wait",
      "parameters": {
        "amount": 24,
        "unit": "hours"
      }
    },
    {
      "name": "Send Reminder Notification",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://backend:8000/api/notifications/reminder"
      }
    }
  ]
}
```

---

## 🎨 Frontend UX

### Affichage de la Checklist

```tsx
// MainChatPageV2.tsx ou EmergencyChecklistComponent.tsx

interface EmergencyChecklistResponse {
  type: "emergency_checklist";
  workflow_name: string;
  severity: string;
  context: Record<string, any>;
  checklist: ChecklistStep[];
  message: string;
}

interface ChecklistStep {
  step_id: number;
  title: string;
  description: string;
  manual: boolean;
  actions: QuickAction[];
}

interface QuickAction {
  id: string;
  label: string;
  type: "email_draft" | "query" | "export" | "schedule";
  endpoint: string;
  payload: Record<string, any>;
}

const EmergencyChecklist = ({ response }: { response: EmergencyChecklistResponse }) => {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const handleAction = async (action: QuickAction) => {
    const result = await fetch(action.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(action.payload)
    });

    const data = await result.json();

    // Si c'est un draft email, afficher modal de validation
    if (action.type === "email_draft") {
      showEmailDraftModal(data.draft, data.next_action);
    }

    // Si c'est une query, afficher résultats
    if (action.type === "query") {
      displayQueryResults(data);
    }
  };

  return (
    <div className="emergency-checklist">
      <div className="header">
        <span className={`severity-badge ${response.severity}`}>
          {response.severity.toUpperCase()}
        </span>
        <h3>{response.workflow_name}</h3>
      </div>

      <div className="context">
        {Object.entries(response.context).map(([key, value]) => (
          <div key={key}>
            <strong>{key}:</strong> {value}
          </div>
        ))}
      </div>

      <div className="checklist">
        {response.checklist.map(step => (
          <div key={step.step_id} className="step">
            <div className="step-header" onClick={() => toggleStep(step.step_id)}>
              {step.title}
            </div>

            {expandedStep === step.step_id && (
              <div className="step-content">
                <p>{step.description}</p>

                {step.actions.length > 0 && (
                  <div className="actions">
                    {step.actions.map(action => (
                      <button
                        key={action.id}
                        onClick={() => handleAction(action)}
                        className={`action-btn ${action.type}`}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
```

---

## 🚀 Plan d'Implémentation

### Phase 1: Backend (2-3h)
1. ✅ Modifier WorkflowAgent pour retourner format `emergency_checklist`
2. ✅ Créer `/api/emergency-actions/{action_id}` endpoints
3. ✅ Implémenter actions prioritaires:
   - `prepare-neighbor-email` (SQLAgent + EmailAgent)
   - `find-plumbers` (SQLAgent)
   - `send-email` (N8N trigger)

### Phase 2: N8N (1h)
1. ✅ Créer workflow `send-bulk-email`
2. ✅ Tester avec callback ThoughtStream

### Phase 3: Frontend (2-3h)
1. ✅ Détecter response type `emergency_checklist`
2. ✅ Créer component `EmergencyChecklist`
3. ✅ Implémenter action handlers
4. ✅ Modal de validation email

### Phase 4: Testing (1h)
1. ✅ Test E2E depuis UI
2. ✅ Vérifier tous les flows d'actions
3. ✅ Valider callbacks N8N

---

## ✅ Avantages de cette Approche

1. **Cohérent**: Utilise vos agents existants (SQL, Email, Web)
2. **Flexible**: User peut modifier/valider chaque action
3. **Simple**: N8N seulement pour emails (ce qu'il fait bien)
4. **Évolutif**: Facile d'ajouter nouvelles actions
5. **UX naturel**: Conversation + boutons d'action

---

## 📝 Exemple de Flow Complet

```
1. User: "URGENT: Dégât des eaux apt 12"

2. DisruptIQ: [Affiche checklist avec 5 steps]

3. User: Clique "Préparer email aux voisins"

4. DisruptIQ:
   → SQLAgent trouve 4 voisins étages inférieurs
   → EmailAgent génère brouillon:

   📧 Brouillon généré:
   À: marie.dubois@gmail.com, pierre.martin@outlook.fr, ...
   Objet: Alerte: Dégât des eaux - Résidence Les Tilleuls

   Message:
   Madame, Monsieur,

   Nous vous informons qu'un dégât des eaux a été signalé au 3ème étage...

   [Envoyer] [Modifier] [Annuler]

5. User: [Envoyer]

6. DisruptIQ:
   → Trigger N8N send-bulk-email
   → N8N envoie 4 emails
   → Callbacks ThoughtStream
   → "✅ 4 emails envoyés aux voisins"
```

---

**Prêt à implémenter cette architecture?**

Prochaine étape: Modifier `WorkflowAgent.py` pour retourner le nouveau format `emergency_checklist` au lieu de `requires_confirmation`.
