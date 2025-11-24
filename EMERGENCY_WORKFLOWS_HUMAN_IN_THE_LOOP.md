# Emergency Workflows - Human-in-the-Loop Implementation

**Date**: 2025-11-23
**Status**: Backend Ready - Frontend Implementation Required

---

## Vue d'ensemble

Les Emergency Workflows V1 implémentent un système de **human-in-the-loop** où chaque procédure d'urgence nécessite une validation manuelle de l'utilisateur avant exécution.

### Flux de Contrôle

```
User → Message Urgent
  → WorkflowAgent détecte URGENCE
  → Charge template depuis PostgreSQL
  → Enrichit avec LLM
  → Retourne requires_confirmation: true
  → Frontend affiche modal de confirmation
  → User valide
  → Frontend POST /api/emergency-workflows/execute
  → Backend trigger N8N
  → N8N exécute steps
  → Callbacks ThoughtStream en temps réel
  → Frontend affiche progression
```

---

## Format de Réponse Backend

Quand le WorkflowAgent détecte une urgence, il retourne:

```json
{
  "success": true,
  "requires_confirmation": true,
  "workflow_action": "URGENCE:water_leak",
  "message": "🚨 **Procédure d'urgence détectée: Fuite d'eau - Intervention d'urgence**\n\n**Contexte détecté:**\n- Bâtiment: Résidence Les Tilleuls\n- Appartement: 12\n- Étage: 3\n- Gravité: HIGH\n\n**5 étapes à exécuter:**\n\n1. Notifier le propriétaire de l'appartement concerné\n   → Informer M. Dupont de la situation urgente\n2. Prévenir les voisins des étages inférieurs\n   → Alerter les résidents potentiellement impactés\n3. Contacter plombier d'urgence\n   → Mobiliser intervention professionnelle immédiate\n4. Créer ticket d'intervention\n   → Documenter l'incident dans le système\n5. Planifier suivi dans 24h\n   → S'assurer de la résolution complète\n\n**Veuillez confirmer l'exécution de cette procédure.**",
  "workflow_data": {
    "workflow_name": "Fuite d'eau - Intervention d'urgence",
    "workflow_type": "water_leak",
    "steps": [
      {
        "step_id": 1,
        "title": "Notifier le propriétaire de l'appartement concerné",
        "description": "Informer M. Dupont de la situation urgente",
        "workflow_action": "send_email",
        "enabled": true,
        "is_critical": true,
        "payload_template": {
          "email_subject": "🚨 URGENT: Dégât des eaux - Appartement {{apartment_number}}",
          "email_body_template": "Bonjour {{owner_name}},\n\nNous vous informons qu'un dégât des eaux a été signalé...",
          "recipient_source": "owner_from_SQL"
        },
        "preview": {
          "type": "send_email",
          "subject": "🚨 URGENT: Dégât des eaux - Appartement 12",
          "body": "Bonjour M. Dupont,\n\nNous vous informons qu'un dégât des eaux a été signalé...",
          "recipients": ["propriétaire@email.com (sera résolu depuis SQL)"],
          "has_sms_fallback": true
        },
        "extracted_data": {
          "building_name": "Résidence Les Tilleuls",
          "apartment_number": "12",
          "floor": 3,
          "owner_name": "M. Dupont",
          "severity": "high"
        }
      },
      // ... 4 autres steps
    ],
    "context_data": {
      "building_name": "Résidence Les Tilleuls",
      "building_address": "Non spécifié",
      "floor": 3,
      "apartment_number": "12",
      "owner_name": "M. Dupont",
      "incident_type": "fuite d'eau",
      "incident_description": "Dégât des eaux détecté...",
      "severity": "high",
      "actions_taken": [],
      "affected_floors": ["3"],
      "reporter": "Non spécifié"
    }
  },
  "trace": {
    "conversation_id": "conv_123",
    "thought_stream_id": "stream_456",
    "tenant_id": "default",
    "user_id": "user_789"
  }
}
```

---

## Frontend Implementation Required

### 1. Détecter la Réponse `requires_confirmation: true`

Dans `MainChatPageV2.tsx` ou le composant qui gère les réponses:

```typescript
const handleAgentResponse = (response: any) => {
  if (response.requires_confirmation === true) {
    // Afficher modal de confirmation
    showEmergencyWorkflowModal(response);
  } else {
    // Affichage normal
    displayMessage(response.message);
  }
};
```

### 2. Créer le Modal de Confirmation

Le modal doit afficher:

1. **Header**: Titre de l'urgence + contexte
   - Bâtiment, Appartement, Étage, Gravité

2. **Liste des Steps** (avec preview si disponible):
   - Checkbox pour chaque step (enabled par défaut)
   - Titre + description
   - Preview des emails/SMS si `step.preview` existe

3. **Actions**:
   - Bouton "Annuler" → fermer modal
   - Bouton "Exécuter la procédure" → appeler API

### 3. Exécuter la Procédure

Quand l'utilisateur clique "Exécuter":

```typescript
const executeWorkflow = async (workflowData: any, trace: any) => {
  try {
    const response = await fetch('/api/emergency-workflows/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        workflow_data: workflowData,
        trace: {
          ...trace,
          request_id: `req_${Date.now()}`,
          timestamp: new Date().toISOString()
        }
      })
    });

    if (response.ok) {
      // Fermer modal
      closeModal();

      // Afficher message de succès
      showSuccessMessage("Procédure d'urgence démarrée");

      // Les ThoughtStream updates arriveront automatiquement via SSE
    } else {
      showErrorMessage("Erreur lors de l'exécution");
    }
  } catch (error) {
    showErrorMessage(error.message);
  }
};
```

### 4. Afficher les ThoughtStream Updates

Les callbacks N8N injecteront des thoughts en temps réel:

```typescript
// Dans setupStreamListeners ou équivalent
onThoughtUpdate: (thought: Thought) => {
  if (thought.agent.startsWith("N8N_")) {
    // Afficher la progression du workflow N8N
    updateWorkflowProgress({
      title: thought.title,
      progress: thought.progress,
      type: thought.type
    });
  }
}
```

---

## Example Modal UI (Suggestion)

```
┌─────────────────────────────────────────────────────────┐
│ 🚨 Procédure d'urgence: Fuite d'eau                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Contexte détecté:                                       │
│ • Bâtiment: Résidence Les Tilleuls                      │
│ • Appartement: 12                                       │
│ • Étage: 3ème                                           │
│ • Gravité: 🔴 HIGH                                      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 5 étapes à exécuter:                                    │
│                                                         │
│ ☑ 1. Notifier le propriétaire (M. Dupont)              │
│    📧 Email: "URGENT: Dégât des eaux - App. 12"        │
│    → dupont@example.com                                 │
│                                                         │
│ ☑ 2. Prévenir les voisins des étages inférieurs        │
│    📧 Email: "Alerte dégât des eaux étage supérieur"   │
│    → voisin1@email.com, voisin2@email.com              │
│                                                         │
│ ☑ 3. Contacter plombier d'urgence                      │
│    📞 Appel + SMS au plombier de garde                 │
│                                                         │
│ ☑ 4. Créer ticket d'intervention                       │
│    📝 Documentation automatique de l'incident          │
│                                                         │
│ ☑ 5. Planifier suivi dans 24h                          │
│    📅 Rappel automatique pour vérification             │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              [Annuler]  [Exécuter la procédure]         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Variation: Step-by-Step Confirmation (V2+)

Pour une approche encore plus granulaire (optionnel pour V2):

1. Afficher seulement le premier step
2. User valide → exécuter step 1
3. Afficher step 2
4. User valide → exécuter step 2
5. Etc.

Cela nécessiterait:
- Un endpoint `/api/emergency-workflows/execute-step`
- Modification du workflow N8N pour accepter step individuel
- State management côté frontend

**Pour V1**: Validation unique pour toutes les steps suffit.

---

## Testing du Frontend

### Scénario de Test

1. **Envoyer message urgent**:
   ```
   URGENT: Dégât des eaux détecté dans l'appartement 12,
   résidence Les Tilleuls, 3ème étage.
   Propriétaire: M. Dupont (dupont@example.com, 06 12 34 56 78).
   Eau coule du plafond, situation critique.
   ```

2. **Vérifier réponse backend**:
   - `requires_confirmation: true` ✓
   - `workflow_data` contient 5 steps ✓
   - `message` contient recap détaillé ✓

3. **Modal s'affiche**:
   - Contexte visible (bâtiment, appartement, gravité) ✓
   - 5 steps listées avec titres et descriptions ✓
   - Bouton "Exécuter" enabled ✓

4. **User clique "Exécuter"**:
   - POST `/api/emergency-workflows/execute` → 200 ✓
   - Modal se ferme ✓
   - Message "Procédure démarrée" affiché ✓

5. **ThoughtStream updates arrivent**:
   - 🚨 Workflow d'urgence démarré (progress: 0.1) ✓
   - ⚙️ Step 1 exécuté (progress: 0.2) ✓
   - ⚙️ Step 2 exécuté (progress: 0.4) ✓
   - ... ✓
   - ✅ Workflow terminé (progress: 1.0) ✓

---

## Backend Endpoints (Already Implemented)

### 1. Chat Stream (WorkflowAgent Response)
- **Endpoint**: `/api/chat/stream` ou équivalent
- **Method**: POST (SSE stream)
- **Retourne**: `requires_confirmation: true` quand urgence détectée

### 2. Execute Workflow
- **Endpoint**: `/api/emergency-workflows/execute`
- **Method**: POST
- **Auth**: Bearer token required
- **Body**:
  ```json
  {
    "workflow_data": { /* from response */ },
    "trace": { /* from response + request_id */ }
  }
  ```
- **Response**: `200 OK` si succès

### 3. N8N Callbacks (Automatic)
- **Endpoint**: `/api/n8n/callback/thought-update`
- **Method**: POST (called by N8N)
- **Effect**: Injecte thoughts dans ThoughtStream
- **Frontend**: Reçoit via SSE automatiquement

---

## État Actuel

✅ **Backend**: 100% complet et testé
- WorkflowAgent retourne `requires_confirmation: true`
- Message contient recap des 5 steps
- `workflow_data` enrichi avec contexte LLM
- Endpoint `/execute` fonctionnel
- Callbacks N8N → ThoughtStream opérationnels

⏳ **Frontend**: À implémenter
- Détection `requires_confirmation: true`
- Modal de confirmation avec liste steps
- Bouton "Exécuter" → POST `/execute`
- Affichage ThoughtStream updates

---

## Prochaines Étapes

1. **Frontend**: Implémenter modal de confirmation
2. **Test E2E**: Vérifier workflow complet avec validation user
3. **V2** (optionnel): Step-by-step confirmation au lieu de all-at-once

---

**Contact**: Claude (Sonnet 4.5)
**Session**: Emergency Workflows V1 - Human-in-the-Loop
**Date**: 2025-11-23
