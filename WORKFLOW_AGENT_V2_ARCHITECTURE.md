# WorkflowAgent V2 - Architecture Intelligente

**Date**: 2025-11-23
**Inspiration**: LegalAgent architecture
**Objectif**: Agent généraliste pour workflows multi-domaines (urgences, communications, maintenance)

---

## 🎯 Vision

Le **WorkflowAgent** est un orchestrateur intelligent qui:

1. **Analyse la demande** utilisateur pour déterminer le type de workflow
2. **Génère un plan d'action** structuré et contextuel
3. **Coordonne les agents spécialisés** (SQL, Email, Web, etc.)
4. **Guide l'utilisateur étape par étape** avec actions intelligentes
5. **S'adapte au contexte** (urgence vs. routine, multi-professionnels, etc.)

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  OrchestratorAgent                          │
│  Intent: WORKFLOW:* → route to WorkflowAgent                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              WorkflowAgent.process_request()                │
│                                                             │
│  1. Classify workflow type (emergency, communication, etc.) │
│  2. Extract context (who, what, when, where, urgency)       │
│  3. Load relevant template if exists                        │
│  4. Generate intelligent action plan                        │
│  5. Return interactive workflow with smart actions          │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
┌──────────────────┐                  ┌──────────────────┐
│ Emergency Flow   │                  │ Communication    │
│ - water_leak     │                  │ Flow             │
│ - fire           │                  │ - ag_invitation  │
│ - electrical     │                  │ - info_broadcast │
│ - structural     │                  │ - vote_request   │
└──────────────────┘                  └──────────────────┘
        ↓                                       ↓
┌─────────────────────────────────────────────────────────────┐
│           Intelligent Action Generator                      │
│                                                             │
│  For each step, generate smart actions:                    │
│  - [Find contacts] → SQLAgent                               │
│  - [Generate email] → EmailAgent                            │
│  - [Send emails] → N8N                                      │
│  - [Search professionals] → WebAgent or SQLAgent            │
│  - [Create report] → Export markdown                        │
│  - [Schedule reminder] → N8N scheduler                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧠 Intelligence Layer - Workflow Classification

### Workflow Types

```python
WORKFLOW_TYPES = {
    "emergency": {
        "subtypes": ["water_leak", "fire", "electrical", "gas_leak", "structural"],
        "urgency": "critical",
        "requires_immediate_action": True,
        "professional_types": ["plumber", "electrician", "engineer", "firefighter"]
    },
    "communication": {
        "subtypes": ["ag_invitation", "info_broadcast", "vote_request", "work_notice"],
        "urgency": "normal",
        "requires_immediate_action": False,
        "professional_types": []
    },
    "maintenance": {
        "subtypes": ["scheduled_maintenance", "inspection", "cleaning"],
        "urgency": "low",
        "requires_immediate_action": False,
        "professional_types": ["maintenance_company", "inspector", "cleaner"]
    },
    "administrative": {
        "subtypes": ["document_request", "complaint_handling", "insurance_claim"],
        "urgency": "normal",
        "requires_immediate_action": False,
        "professional_types": ["lawyer", "insurance_agent"]
    }
}
```

### Classification avec LLM

```python
async def classify_workflow_type(self, user_input: str) -> Dict[str, Any]:
    """
    Classify user request into workflow type and extract key entities

    Returns:
        {
            "workflow_type": "emergency",
            "subtype": "water_leak",
            "urgency": "critical",
            "entities": {
                "building": "Résidence Les Tilleuls",
                "apartment": "12",
                "floor": 3,
                "affected_people": ["M. Dupont"],
                "professionals_needed": ["plumber"]
            },
            "context": {
                "description": "...",
                "severity": "high"
            }
        }
    """
```

---

## 🔄 Multi-Professional Workflow Management

### Scénario: Besoin de plusieurs professionnels

**User**: "Urgence: incendie électrique étage 2, dégât des eaux suite à extinction"

**WorkflowAgent Intelligence**:

```json
{
  "workflow_type": "emergency",
  "subtypes": ["electrical", "fire", "water_leak"],
  "professionals_needed": [
    {"type": "firefighter", "priority": 1, "reason": "Sécurité immédiate"},
    {"type": "electrician", "priority": 2, "reason": "Diagnostic et mise en sécurité"},
    {"type": "plumber", "priority": 3, "reason": "Réparation dégâts des eaux"}
  ],
  "action_sequence": [
    {
      "step_id": 1,
      "title": "🚨 Sécurité immédiate",
      "parallel": false,
      "actions": [
        {"type": "manual", "title": "Vérifier évacuation immeuble"},
        {"type": "manual", "title": "Couper électricité générale"}
      ]
    },
    {
      "step_id": 2,
      "title": "📧 Alerter résidents",
      "parallel": false,
      "actions": [
        {"type": "prepare_email", "recipients": "all_residents", "template": "emergency_fire"}
      ]
    },
    {
      "step_id": 3,
      "title": "🔧 Contacter professionnels (en parallèle)",
      "parallel": true,
      "sub_actions": [
        {
          "professional_type": "electrician",
          "actions": [
            {"type": "find_professionals", "query": "electrician_emergency"},
            {"type": "prepare_quote_request", "template": "electrical_emergency"}
          ]
        },
        {
          "professional_type": "plumber",
          "actions": [
            {"type": "find_professionals", "query": "plumber_emergency"},
            {"type": "prepare_quote_request", "template": "water_damage"}
          ]
        }
      ]
    },
    {
      "step_id": 4,
      "title": "📋 Documentation",
      "parallel": false,
      "actions": [
        {"type": "create_incident_report"},
        {"type": "notify_insurance"}
      ]
    }
  ]
}
```

### Gestion de la Séquence avec État

```python
class WorkflowExecutionState:
    """Track workflow execution state for continuity"""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.current_step = 1
        self.completed_steps = []
        self.pending_actions = []
        self.professional_responses = {}

    def mark_step_complete(self, step_id: int, result: Dict):
        """Mark step as completed and determine next action"""
        self.completed_steps.append(step_id)

        # Auto-advance to next step if current step is complete
        next_step = self.get_next_step()

        return {
            "completed_step": step_id,
            "next_step": next_step,
            "message": f"✅ Étape {step_id} terminée. Passons à l'étape {next_step}.",
            "auto_display_next": True
        }
```

---

## 💡 Exemples de Workflows

### 1. Emergency: Dégât des Eaux (Existant)

**Input**: "URGENT: Dégât des eaux apt 12"

**Output**:
```markdown
🚨 Procédure d'urgence: Dégât des eaux
Résidence Les Tilleuls, Apt 12, Étage 3

📋 Plan d'action (5 étapes):

**1. ⚠️ Sécurité immédiate** (manuel)
   → Vérifier que M. Dupont a coupé l'eau
   → Couper l'électricité si risque

**2. 📧 Alerter les personnes concernées**
   [Action: Préparer email voisins étages inférieurs]
   [Action: Informer propriétaire étages impactés]

**3. 🔧 Mobiliser plombier d'urgence**
   [Action: Chercher plombiers Paris - Urgence 24/7]
   [Action: Générer demande devis (avec photos si dispo)]
   [Action: Envoyer demandes à 3 plombiers]

**4. 📋 Documentation incident**
   [Action: Créer rapport d'incident détaillé]
   [Action: Photos + constat dégâts]

**5. 📅 Suivi et assurance**
   [Action: Notifier assurance copropriété]
   [Action: Programmer rappel 24h]
```

### 2. Communication: Invitation AG

**Input**: "Je veux convoquer les copropriétaires à une AG le 15 décembre"

**Output**:
```markdown
📧 Workflow: Convocation Assemblée Générale

📋 Plan d'action (4 étapes):

**1. 📝 Préparer ordre du jour**
   [Action: Générer template ordre du jour]
   → Points obligatoires (budget, comptes, travaux)
   → Points spécifiques à ajouter

**2. 👥 Identifier destinataires**
   [Action: Liste tous copropriétaires]
   → Affichera: Nom, Email, Tantièmes, Apt
   → Vérifier coordonnées à jour

**3. ✍️ Rédiger convocation**
   [Action: Générer convocation AG]
   → Conforme Loi 1965 (délai 21 jours minimum)
   → Inclut: Date, Lieu, Ordre du jour, Documents joints

**4. 📤 Envoyer convocations**
   [Action: Prévisualiser email]
   [Action: Envoyer par email + courrier recommandé si nécessaire]

⚖️ Rappels légaux:
- Délai minimum: 21 jours avant AG
- Documents à joindre: Budget prévisionnel, comptes, règlement intérieur
```

### 3. Multi-Professional: Travaux Rénovation

**Input**: "Organiser travaux de rénovation hall d'entrée: électricité, peinture, sol"

**Output**:
```markdown
🔧 Workflow: Coordination Travaux Multi-Corps

📋 Plan d'action (6 étapes):

**1. 📐 Définir périmètre travaux**
   [Action: Générer cahier des charges]
   → Électricité: Spots LED, interrupteurs
   → Peinture: Murs, plafond
   → Sol: Carrelage ou parquet

**2. 🔍 Rechercher professionnels (en parallèle)**

   **Électricien**
   [Action: Chercher électriciens Paris]
   [Action: Générer demande devis électricité]

   **Peintre**
   [Action: Chercher peintres Paris]
   [Action: Générer demande devis peinture]

   **Carreleur/Parqueteur**
   [Action: Chercher poseurs de sol Paris]
   [Action: Générer demande devis sol]

**3. 📊 Comparer devis**
   [Action: Tableau comparatif devis reçus]
   → Prix, délais, garanties

**4. 🗳️ Validation AG**
   [Action: Préparer vote AG pour travaux]
   → Montant total, planning, professionnels retenus

**5. 📝 Contractualisation**
   [Action: Générer contrats travaux]
   [Action: Coordonner planning entre corps de métiers]

**6. 📅 Suivi chantier**
   [Action: Programmer rappels étapes clés]
```

---

## 🛠️ Action Types & Handlers

### Action Registry

```python
ACTION_HANDLERS = {
    # Query actions (SQLAgent)
    "find_contacts": {
        "handler": "sql_agent.find_contacts",
        "params": ["building", "floor", "criteria"],
        "returns": "list[Contact]"
    },
    "find_professionals": {
        "handler": "sql_agent.find_professionals",
        "params": ["profession_type", "location", "urgency"],
        "returns": "list[Professional]",
        "fallback": "web_agent.search_professionals"  # Si SQL vide
    },

    # Email actions (EmailAgent)
    "prepare_email": {
        "handler": "email_agent.generate_draft",
        "params": ["template", "context", "recipients"],
        "returns": "EmailDraft"
    },

    # N8N actions (email sending)
    "send_email": {
        "handler": "n8n_service.trigger_workflow",
        "workflow": "send-bulk-email",
        "params": ["recipients", "subject", "body"],
        "returns": "ExecutionStatus"
    },

    # Export actions
    "create_report": {
        "handler": "export_service.generate_markdown",
        "params": ["template", "data"],
        "returns": "MarkdownFile"
    },

    # Web search actions (WebAgent)
    "search_professionals": {
        "handler": "web_agent.search_duckduckgo",
        "params": ["query", "location"],
        "returns": "list[SearchResult]"
    },

    # Scheduling actions (N8N)
    "schedule_reminder": {
        "handler": "n8n_service.trigger_workflow",
        "workflow": "schedule-reminder",
        "params": ["delay_hours", "message"],
        "returns": "ScheduleID"
    }
}
```

---

## 🔄 Continuité de Séquence - State Management

### Problème:
"Une fois que le mail est validé et envoyé aux voisins, comment prévenir les professionnels?"

### Solution: Workflow State Tracking

```python
# Redis ou PostgreSQL pour persister l'état
workflow_state = {
    "workflow_id": "wf_12345",
    "type": "emergency_water_leak",
    "current_step": 2,
    "steps": [
        {
            "step_id": 1,
            "status": "completed",
            "result": {"action": "security_check", "done": True}
        },
        {
            "step_id": 2,
            "status": "completed",
            "result": {
                "action": "send_email_neighbors",
                "emails_sent": 4,
                "timestamp": "2025-11-23T19:15:00"
            }
        },
        {
            "step_id": 3,
            "status": "in_progress",
            "sub_actions": [
                {
                    "action_id": "find_plumbers",
                    "status": "pending"
                },
                {
                    "action_id": "generate_quote_request",
                    "status": "pending"
                }
            ]
        }
    ]
}
```

### Auto-Prompting Next Step

Après envoi email voisins (step 2 complet), le système affiche automatiquement:

```markdown
✅ Emails envoyés à 4 voisins des étages inférieurs

📌 **Prochaine étape: Contacter plombier d'urgence**

[Action: Chercher plombiers disponibles]
[Action: Générer demande de devis]

💡 Ou dites "suivant" pour passer à l'étape 3
```

---

## 📡 API Endpoints pour Actions

### Endpoint Unifié

```python
@router.post("/api/workflow-actions/execute")
async def execute_workflow_action(
    request: WorkflowActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a workflow action and return next step

    Body:
    {
        "workflow_id": "wf_12345",
        "action_id": "send_email_neighbors",
        "action_type": "send_email",
        "payload": {
            "recipients": [...],
            "subject": "...",
            "body": "..."
        }
    }
    """
    # 1. Load workflow state
    state = await get_workflow_state(request.workflow_id)

    # 2. Execute action via appropriate handler
    handler = ACTION_HANDLERS[request.action_type]["handler"]
    result = await execute_handler(handler, request.payload)

    # 3. Update workflow state
    await update_workflow_state(request.workflow_id, request.action_id, result)

    # 4. Determine next step
    next_step = await get_next_workflow_step(request.workflow_id)

    return {
        "success": True,
        "result": result,
        "next_step": next_step,
        "message": f"✅ Action '{request.action_id}' terminée. {next_step.title}"
    }
```

---

## 🎨 Frontend UX - Conversational Workflow

### User Experience

```
User: "URGENT: Dégât des eaux apt 12"

DisruptIQ:
🚨 Procédure d'urgence détectée: Dégât des eaux
Résidence Les Tilleuls, Apt 12, Étage 3

Je vais vous guider à travers 5 étapes.

**Étape 1/5: Sécurité immédiate**
→ Avez-vous coupé l'eau?
→ L'électricité est-elle coupée si nécessaire?

[✓ Oui, c'est fait] [⚠️ Besoin d'aide]

---

User: [✓ Oui, c'est fait]

DisruptIQ:
✅ Étape 1 validée

**Étape 2/5: Alerter les voisins**

J'ai trouvé 4 voisins aux étages inférieurs qui doivent être prévenus.

[Voir la liste] [Préparer email d'alerte]

---

User: [Préparer email d'alerte]

DisruptIQ:
📧 Email d'alerte généré

À: marie.dubois@gmail.com, pierre.martin@outlook.fr, ...
Objet: 🚨 Alerte: Dégât des eaux - Résidence Les Tilleuls

Madame, Monsieur,

Nous vous informons qu'un dégât des eaux a été signalé au 3ème étage...

[Modifier] [Envoyer maintenant]

---

User: [Envoyer maintenant]

DisruptIQ:
✅ 4 emails envoyés avec succès

**Étape 3/5: Contacter plombier d'urgence**

[Chercher plombiers disponibles]
[Ou] Voulez-vous que je prépare directement une demande de devis?

---

User: [Chercher plombiers disponibles]

DisruptIQ:
🔍 J'ai trouvé 12 plombiers dans votre base de données.

📊 Résultats:
- Céline Girard (contact.girard1@girard.pro) - 06 94 99 91 8
- Anne Durand (contact.durand13@durand.pro) - 04 89 40 74 94
...

[Générer demande devis pour tous]
[Sélectionner 3 plombiers]
[Chercher d'autres plombiers sur internet]

---

User: [Sélectionner 3 plombiers]

(Interface pour sélectionner 3)

DisruptIQ:
✅ 3 plombiers sélectionnés

📧 Demande de devis générée:

Objet: Demande de devis urgent - Dégât des eaux
Message: ...

[Modifier] [Envoyer aux 3 plombiers]

---

User: [Envoyer aux 3 plombiers]

DisruptIQ:
✅ 3 demandes de devis envoyées

**Étape 4/5: Documentation**
[Créer rapport d'incident]

---
```

---

## 🚀 Plan d'Implémentation

### Phase 1: Refactoring WorkflowAgent (4-6h)

1. **Créer nouveau fichier** `workflow_agent_v2.py` (comme LegalAgent)
2. **Implémenter**:
   - `process_request()` - Point d'entrée intelligent
   - `classify_workflow_type()` - Classification LLM
   - `generate_action_plan()` - Génération plan structuré
   - `execute_action()` - Dispatch vers handlers appropriés
3. **Workflow State** - Redis ou PostgreSQL
4. **Action Registry** - Mapping actions → handlers

### Phase 2: Action Handlers (3-4h)

1. **SQLAgent actions**:
   - `find_contacts()`
   - `find_professionals()`
2. **EmailAgent actions**:
   - `generate_draft()` (existe déjà?)
3. **N8N triggers**:
   - `send_bulk_email()`
   - `schedule_reminder()`
4. **Export actions**:
   - `create_incident_report()`

### Phase 3: Frontend Integration (3-4h)

1. **Workflow Component** - Affiche steps + actions
2. **Action Buttons** - Handlers pour chaque type d'action
3. **State Persistence** - Track workflow progress
4. **Next Step Auto-Display** - Continuité naturelle

### Phase 4: Templates (2-3h)

1. **Emergency templates** (water_leak, fire, etc.)
2. **Communication templates** (AG, info, etc.)
3. **Maintenance templates**

---

## ✅ Avantages Architecture V2

1. **Intelligent**: Décide automatiquement du workflow approprié
2. **Contextuel**: Extrait entités et adapte actions
3. **Multi-professionnel**: Gère plusieurs corps de métiers en parallèle
4. **Séquentiel**: Continuité naturelle step-by-step
5. **Généraliste**: Urgences ET communications normales
6. **Évolutif**: Facile d'ajouter nouveaux workflow types
7. **Cohérent**: Utilise agents existants (SQL, Email, Web)
8. **Pragmatique**: N8N seulement pour ce qu'il fait bien (emails, scheduling)

---

**Prêt à implémenter?**

Prochaine étape: Créer `workflow_agent_v2.py` avec architecture inspirée de LegalAgent.
