# 🚨 Spécification - Workflow de Gestion des Urgences avec To-Do Lists

**Version**: 1.0
**Date**: 2025-11-23
**Objectif**: Implémentation intelligente de la gestion des urgences avec to-do lists préenregistrées ou génération dynamique

---

## 📊 ANALYSE CRITIQUE DE LA PROPOSITION INITIALE

### ✅ Points Excellents
1. **Validation utilisateur étape par étape** - Crucial pour éviter les erreurs
2. **To-do list structurée** - Format JSON clair et exploitable
3. **Intégration N8N** - Excellent choix pour l'orchestration
4. **Approche hybride** - To-do préenregistrée OU génération dynamique

### ⚠️ Points à Améliorer

#### 1. **Stockage des To-Do Lists**
**Problème initial**: "Où stocker ? Dans le RAG ? L'utilisateur doit-il la cocher ?"

**Solution recommandée**:
- ❌ **PAS dans le RAG** (réservé aux documents copropriété)
- ✅ **Système dédié en PostgreSQL** avec table `emergency_workflows`
- ✅ **API de gestion** pour CRUD des to-do lists
- ✅ **Versioning** pour traçabilité

#### 2. **UX/UI Simplifiée**
**Problème**: Validation action par action = trop de clics en urgence

**Solution recommandée**:
- ✅ **Vue d'ensemble** de toute la checklist en 1 écran
- ✅ **Validation globale** avec détails dépliables
- ✅ **Mode express** pour urgences critiques (1 clic = tout exécuter)
- ✅ **Édition inline** pour ajuster avant validation

#### 3. **To-Do List Dynamique**
**Problème**: Comment l'agent génère une to-do si elle n'existe pas ?

**Solution recommandée**:
- ✅ **LLM génère la structure** en se basant sur des exemples
- ✅ **Merge avec règles métier** (lois, bonnes pratiques)
- ✅ **L'utilisateur valide/édite** avant exécution
- ✅ **Option de sauvegarder** la nouvelle to-do pour réutilisation

---

## 🏗️ ARCHITECTURE TECHNIQUE

### 1. Base de Données - Table `emergency_workflows`

```sql
CREATE TABLE emergency_workflows (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,  -- Multi-tenant isolation
    workflow_type VARCHAR(100) NOT NULL,  -- 'water_leak', 'fire', 'elevator', etc.
    workflow_name VARCHAR(255) NOT NULL,  -- "Dégât des eaux standard"
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    is_template BOOLEAN DEFAULT false,  -- Template modifiable par admin

    -- To-Do List structure (JSON)
    checklist JSONB NOT NULL,

    -- Metadata
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    usage_count INTEGER DEFAULT 0,

    -- Index pour recherche rapide
    CONSTRAINT unique_workflow_type_version UNIQUE (tenant_id, workflow_type, version)
);

CREATE INDEX idx_emergency_workflows_tenant ON emergency_workflows(tenant_id);
CREATE INDEX idx_emergency_workflows_type ON emergency_workflows(workflow_type, is_active);
CREATE INDEX idx_emergency_workflows_template ON emergency_workflows(is_template);
```

### 2. Structure de la Checklist (JSONB)

```json
{
  "workflow_type": "water_leak",
  "workflow_name": "Dégât des eaux - Procédure standard",
  "metadata": {
    "estimated_duration_minutes": 15,
    "critical": true,
    "auto_execute": false
  },
  "steps": [
    {
      "step_id": 1,
      "step_order": 1,
      "action_type": "notify_owner",
      "title": "Notifier le propriétaire",
      "description": "Avertir immédiatement le copropriétaire du logement impacté",
      "requires_user_validation": true,
      "is_critical": true,
      "estimated_time_seconds": 30,

      "payload_template": {
        "email_subject": "🚨 Urgence : Dégât des eaux dans votre logement",
        "email_body_template": "Bonjour {{owner_name}},\n\nNous vous informons d'un dégât des eaux dans votre logement {{apartment_number}} situé au {{floor}}ème étage.\n\n**Situation** : {{incident_description}}\n**Mesures prises** : {{actions_taken}}\n\nMerci de nous contacter au plus vite.\n\nCordialement,\nLe Syndic",
        "recipient_source": "owner_from_SQL",
        "required_fields": ["owner_name", "apartment_number", "floor", "incident_description"]
      },

      "workflow_action": "send_email",
      "n8n_node_type": "email"
    },

    {
      "step_id": 2,
      "step_order": 2,
      "action_type": "notify_neighbors",
      "title": "Informer les voisins",
      "description": "Prévenir les copropriétaires des étages inférieurs/adjacents",
      "requires_user_validation": true,
      "is_critical": false,
      "estimated_time_seconds": 45,

      "payload_template": {
        "email_subject": "Information importante : Incident technique dans l'immeuble",
        "email_body_template": "Bonjour,\n\nNous vous informons qu'un incident technique (fuite d'eau) a été détecté au {{floor}}ème étage.\n\nPar précaution, nous vous recommandons de surveiller votre logement.\n\nNous vous tiendrons informés.\n\nCordialement,\nLe Syndic",
        "recipient_source": "neighbors_from_SQL",
        "required_fields": ["floor", "affected_floors"]
      },

      "workflow_action": "send_multi_channel_alert",
      "n8n_node_type": "multi_channel"
    },

    {
      "step_id": 3,
      "step_order": 3,
      "action_type": "contact_plumber",
      "title": "Contacter plombier",
      "description": "Contacter le plombier partenaire d'urgence",
      "requires_user_validation": true,
      "is_critical": true,
      "estimated_time_seconds": 60,

      "payload_template": {
        "email_subject": "🚨 URGENT - Intervention dégât des eaux",
        "email_body_template": "Bonjour,\n\nIntervention urgente requise :\n\n**Adresse** : {{building_address}}\n**Nature** : {{incident_type}}\n**Étage** : {{floor}}\n**Accès** : {{access_instructions}}\n\nMerci de nous confirmer votre disponibilité immédiate.\n\nCordialement,\nLe Syndic",
        "recipient_source": "plumbers_sql_list",
        "sms_fallback": true,
        "required_fields": ["building_address", "incident_type", "floor"]
      },

      "workflow_action": "send_email",
      "n8n_node_type": "email_sms"
    },

    {
      "step_id": 4,
      "step_order": 4,
      "action_type": "create_internal_ticket",
      "title": "Créer ticket de suivi",
      "description": "Créer un ticket dans le système de gestion",
      "requires_user_validation": false,
      "is_critical": false,
      "estimated_time_seconds": 10,

      "payload_template": {
        "ticket_title": "🚨 Dégât des eaux - {{building_name}} - Appt {{apartment_number}}",
        "ticket_description": "{{full_incident_report}}",
        "priority": "urgent",
        "category": "emergency_water"
      },

      "workflow_action": "create_ticket",
      "n8n_node_type": "ticket_creation"
    },

    {
      "step_id": 5,
      "step_order": 5,
      "action_type": "schedule_followup",
      "title": "Planifier suivi 24h",
      "description": "Programmer une relance automatique sous 24h",
      "requires_user_validation": false,
      "is_critical": false,
      "estimated_time_seconds": 5,

      "payload_template": {
        "task_text": "Vérifier avancement intervention plombier + état logement",
        "scheduled_delay_hours": 24,
        "assigned_to": "{{user_id}}"
      },

      "workflow_action": "schedule_action",
      "n8n_node_type": "scheduler"
    }
  ],

  "success_criteria": {
    "critical_steps_completed": [1, 3],
    "minimum_completion_rate": 0.8
  }
}
```

---

## 🚀 FLOW COMPLET - De la Détection à l'Exécution

### Scénario 1 : To-Do List Existante

```
USER: "Urgence ! Grosse fuite d'eau appartement 12, 3ème étage"
   ↓
[ORCHESTRATOR]
   → IntentClassifier: TRIGGER_WORKFLOW
   ↓
[WORKFLOW AGENT]
   → Classification LLM: "emergency_water_leak" (urgency: critical)
   → Query DB: SELECT * FROM emergency_workflows
               WHERE workflow_type = 'water_leak' AND is_active = true
   → To-Do trouvée ✅
   ↓
[ENRICHISSEMENT CONTEXTUEL]
   → RAG: Récupère infos copropriété, contacts, historique
   → SQL: Récupère owner, neighbors, professionals
   → LLM: Extrait détails de la demande utilisateur
   ↓
[GÉNÉRATION PAYLOAD ENRICHI]
   → Merge to-do template + données contextuelles
   → Génère previews des emails/SMS
   ↓
[UI - CONFIRMATION INTELLIGENTE]
   ┌────────────────────────────────────────────────┐
   │ 🚨 URGENCE DÉTECTÉE - Dégât des eaux          │
   │                                                 │
   │ Checklist "Dégât des eaux standard" (v2)      │
   │ Durée estimée : 15 min                         │
   │                                                 │
   │ ✅ 1. Notifier propriétaire (M. Dupont)       │
   │    📧 Email : "Urgence : Dégât des eaux..."   │
   │    [Voir détails ▼]                            │
   │                                                 │
   │ ✅ 2. Informer voisins (Étages 1-2)           │
   │    📧 2 emails + SMS                           │
   │    [Voir détails ▼]                            │
   │                                                 │
   │ ✅ 3. Contacter plombier (Plomberie Express)  │
   │    📧 Email + 📱 SMS de secours                │
   │    [Voir détails ▼]                            │
   │                                                 │
   │ ⚙️  4. Créer ticket URGENT-2024-XXX           │
   │ ⏰ 5. Planifier suivi 24h                      │
   │                                                 │
   │ [⚡ TOUT EXÉCUTER]  [✏️ MODIFIER]  [❌]       │
   └────────────────────────────────────────────────┘
   ↓
[EXÉCUTION N8N]
   → POST /webhook/emergency-water-leak
   → Payload standardisé avec trace.thought_stream_id
   ↓
[N8N WORKFLOW]
   → Step 1: Send Email Owner
       → Callback: "📧 Email envoyé à M. Dupont"
   → Step 2: Send Alerts Neighbors
       → Callback: "📧 2 emails envoyés aux voisins"
   → Step 3: Contact Plumber
       → Callback: "📧 Email + SMS envoyés au plombier"
   → Step 4: Create Ticket
       → Callback: "🎫 Ticket URGENT-2024-1234 créé"
   → Step 5: Schedule Follow-up
       → Callback: "⏰ Suivi programmé pour demain 14h30"
   ↓
[FRONTEND - THOUGHTSTREAM]
   💭 14:30:45 - Workflow "Dégât des eaux" démarré
   💭 14:30:46 - [N8N] 📧 Email envoyé à M. Dupont
   💭 14:30:48 - [N8N] 📧 2 emails envoyés aux voisins
   💭 14:30:50 - [N8N] 📧 Email + SMS envoyés au plombier
   💭 14:30:51 - [N8N] 🎫 Ticket URGENT-2024-1234 créé
   💭 14:30:52 - [N8N] ⏰ Suivi programmé pour demain
   ✅ 14:30:52 - Protocole urgence exécuté (5/5 actions)
```

---

### Scénario 2 : Pas de To-Do List (Génération Dynamique)

```
USER: "Urgence ! Le toit s'est effondré dans le hall"
   ↓
[ORCHESTRATOR]
   → IntentClassifier: TRIGGER_WORKFLOW
   ↓
[WORKFLOW AGENT]
   → Classification LLM: "emergency_structural" (urgency: critical)
   → Query DB: Aucune to-do pour "emergency_structural" ❌
   ↓
[GÉNÉRATION DYNAMIQUE LLM]
   → Prompt: "Génère une checklist d'urgence pour effondrement de toit"
   → LLM utilise:
       • Exemples de to-do existantes (few-shot learning)
       • Règles métier (sécurité, légal)
       • Contexte copropriété (RAG)
   → Génère structure JSON similaire
   ↓
[UI - VALIDATION + ÉDITION]
   ┌────────────────────────────────────────────────┐
   │ 🚨 URGENCE INCONNUE DÉTECTÉE                   │
   │                                                 │
   │ ⚠️ Aucune procédure préenregistrée.            │
   │ Checklist générée automatiquement :            │
   │                                                 │
   │ ✅ 1. Sécuriser zone (Appel pompiers)  [✏️]   │
   │ ✅ 2. Évacuer résidents si nécessaire  [✏️]   │
   │ ✅ 3. Contacter expert structure       [✏️]   │
   │ ✅ 4. Alerter assurance immeuble       [✏️]   │
   │ ✅ 5. Notifier tous copropriétaires    [✏️]   │
   │                                                 │
   │ [⚡ EXÉCUTER]  [+ AJOUTER ÉTAPE]  [💾 SAUVEGARDER MODÈLE] │
   └────────────────────────────────────────────────┘
   ↓
[EXÉCUTION + SAUVEGARDE OPTIONNELLE]
   → Si user clique "💾 Sauvegarder", la to-do est stockée en DB
   → Exécution N8N identique au scénario 1
```

---

## 🎨 COMPOSANTS UI/UX DÉTAILLÉS

### 1. Modal de Confirmation (Vue Complète)

```typescript
interface EmergencyWorkflowConfirmationModal {
  workflow_type: string;
  workflow_name: string;
  urgency: "critical" | "high" | "medium";
  estimated_duration_minutes: number;

  steps: Array<{
    step_id: number;
    title: string;
    description: string;
    is_critical: boolean;
    requires_validation: boolean;
    preview: {
      type: "email" | "sms" | "ticket" | "schedule";
      content: string;  // Preview du contenu
      recipients: string[];
    };
    is_expanded: boolean;  // UI state
    is_enabled: boolean;   // User can disable non-critical steps
  }>;

  actions: {
    execute_all: () => void;
    execute_selected: (step_ids: number[]) => void;
    modify_step: (step_id: number, changes: any) => void;
    save_as_template: () => void;
  };
}
```

### 2. Composant Step Detail (Expandable)

Quand user clique "Voir détails ▼" :

```
┌────────────────────────────────────────────────┐
│ ✅ 1. Notifier propriétaire (M. Dupont) [▲]   │
│                                                 │
│ 📧 Email                                        │
│ À : dupont.jean@email.com                      │
│ Objet : 🚨 Urgence : Dégât des eaux...         │
│                                                 │
│ Aperçu :                                        │
│ ┌──────────────────────────────────────────┐  │
│ │ Bonjour M. Dupont,                        │  │
│ │                                            │  │
│ │ Nous vous informons d'un dégât des eaux   │  │
│ │ dans votre logement n°12 situé au 3ème    │  │
│ │ étage.                                     │  │
│ │                                            │  │
│ │ Situation : Fuite importante provenant... │  │
│ │                                            │  │
│ │ Mesures prises : Coupure eau effectuée    │  │
│ │                                            │  │
│ │ Merci de nous contacter au 01 23 45 67 89 │  │
│ └──────────────────────────────────────────┘  │
│                                                 │
│ [✏️ Modifier email]  [👁️ Vue complète]        │
└────────────────────────────────────────────────┘
```

### 3. Mode Express (1-Click Execution)

Pour urgences absolues, option "Mode Express" dans settings :

```
┌────────────────────────────────────────────────┐
│ ⚙️  PARAMÈTRES WORKFLOW URGENCE                │
│                                                 │
│ ☑️ Mode Express activé                         │
│    Les workflows critiques s'exécutent         │
│    automatiquement après 10 secondes de        │
│    preview (annulable)                         │
│                                                 │
│ Workflows en mode express :                    │
│ • emergency_water_leak                         │
│ • emergency_fire                               │
│ • emergency_structural                         │
└────────────────────────────────────────────────┘
```

---

## 🛠️ IMPLÉMENTATION BACKEND

### 1. Nouveau Service : `EmergencyWorkflowService`

```python
# backend/app/services/emergency_workflow_service.py

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import structlog

from app.models.emergency_workflow import EmergencyWorkflow
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService

logger = structlog.get_logger()


class EmergencyWorkflowService:
    """
    Manages emergency workflow to-do lists

    Features:
    - CRUD operations on emergency workflows
    - Dynamic workflow generation when no template exists
    - Context enrichment (RAG + SQL)
    - Preview generation for UI
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_service = LLMService()
        self.rag_service = RAGService()

    async def get_workflow(
        self,
        workflow_type: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve active workflow template for given type

        Returns None if no template exists (→ trigger dynamic generation)
        """
        query = select(EmergencyWorkflow).where(
            and_(
                EmergencyWorkflow.tenant_id == tenant_id,
                EmergencyWorkflow.workflow_type == workflow_type,
                EmergencyWorkflow.is_active == True
            )
        ).order_by(EmergencyWorkflow.version.desc())

        result = await self.db.execute(query)
        workflow = result.scalar_one_or_none()

        if workflow:
            logger.info(
                "emergency_workflow_found",
                workflow_type=workflow_type,
                version=workflow.version
            )
            return workflow.checklist

        logger.info(
            "emergency_workflow_not_found",
            workflow_type=workflow_type,
            will_generate_dynamic=True
        )
        return None

    async def generate_dynamic_workflow(
        self,
        incident_description: str,
        workflow_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate workflow dynamically using LLM when no template exists

        Uses few-shot learning from existing workflows as examples
        """
        # Get 2-3 example workflows for few-shot learning
        examples = await self._get_example_workflows(limit=3)

        prompt = f"""Tu es un expert en gestion d'urgences pour copropriétés.

SITUATION D'URGENCE:
{incident_description}

TYPE D'URGENCE: {workflow_type}

CONTEXTE DISPONIBLE:
{context}

EXEMPLES DE WORKFLOWS EXISTANTS:
{examples}

RÈGLES MÉTIER:
1. Toujours prioriser la sécurité des personnes
2. Notifier propriétaire/locataire concerné en premier
3. Alerter professionnels qualifiés (pompiers, plombiers, etc.)
4. Créer traçabilité (tickets, logs)
5. Planifier suivi 24-48h

GÉNÈRE une checklist d'urgence au format JSON suivant:
{{
  "workflow_type": "{workflow_type}",
  "workflow_name": "Nom explicite",
  "metadata": {{
    "estimated_duration_minutes": <int>,
    "critical": true,
    "auto_execute": false
  }},
  "steps": [
    {{
      "step_id": 1,
      "step_order": 1,
      "action_type": "notify_xxx",
      "title": "Titre court",
      "description": "Description claire",
      "requires_user_validation": true,
      "is_critical": true,
      "payload_template": {{...}},
      "workflow_action": "send_email|send_sms|create_ticket|...",
      "n8n_node_type": "email|sms|ticket_creation|..."
    }}
  ],
  "success_criteria": {{...}}
}}

Génère UNIQUEMENT le JSON, sans explication."""

        response = await self.llm_service.generate_completion(
            prompt=prompt,
            temperature=0.3,  # Low for consistency
            max_tokens=2000
        )

        # Parse and validate JSON
        workflow = self._parse_and_validate_workflow(response)

        logger.info(
            "dynamic_workflow_generated",
            workflow_type=workflow_type,
            steps_count=len(workflow["steps"])
        )

        return workflow

    async def enrich_workflow_with_context(
        self,
        workflow: Dict[str, Any],
        user_input: str,
        context: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Enrich workflow steps with real data from RAG + SQL

        Example:
        - Template says "notify_owner" → Fetch owner email from SQL
        - Template says "contact_plumber" → Fetch preferred plumber from RAG
        """
        enriched_steps = []

        for step in workflow["steps"]:
            enriched_step = step.copy()

            # Extract required fields from user input using LLM
            extracted_data = await self._extract_step_data(
                user_input=user_input,
                required_fields=step["payload_template"].get("required_fields", []),
                context=context
            )

            # Fetch recipients from SQL if needed
            if "recipient_source" in step["payload_template"]:
                recipients = await self._fetch_recipients(
                    source=step["payload_template"]["recipient_source"],
                    context=context,
                    db=db
                )
                extracted_data["recipients"] = recipients

            # Generate email/SMS preview
            if step["workflow_action"] in ["send_email", "send_sms"]:
                preview = self._generate_message_preview(
                    template=step["payload_template"],
                    data=extracted_data
                )
                enriched_step["preview"] = preview

            enriched_step["extracted_data"] = extracted_data
            enriched_steps.append(enriched_step)

        workflow["steps"] = enriched_steps
        return workflow

    async def save_workflow_as_template(
        self,
        workflow: Dict[str, Any],
        tenant_id: str,
        created_by: str
    ) -> EmergencyWorkflow:
        """Save a dynamically generated workflow as reusable template"""
        new_workflow = EmergencyWorkflow(
            tenant_id=tenant_id,
            workflow_type=workflow["workflow_type"],
            workflow_name=workflow["workflow_name"],
            checklist=workflow,
            created_by=created_by,
            is_template=True
        )

        self.db.add(new_workflow)
        await self.db.commit()
        await self.db.refresh(new_workflow)

        logger.info(
            "workflow_saved_as_template",
            workflow_id=new_workflow.id,
            workflow_type=workflow["workflow_type"]
        )

        return new_workflow

    # ... (helper methods)
```

### 2. Enhanced WorkflowAgent

```python
# backend/app/services/agents/workflow_agent.py
# Ajout de la logique to-do list

async def process_request(
    self,
    user_input: str,
    context: Optional[Dict[str, Any]] = None,
    thought_stream: Optional[ThoughtStream] = None,
    conversation_id: Optional[str] = None,
    tenant_id: str = "default",
    user_id: str = "anonymous"
) -> Dict[str, Any]:
    """
    Enhanced with emergency workflow to-do list support
    """
    if thought_stream:
        thought_stream.add_thought(
            thought_type=ThoughtType.ANALYZING,
            title="Analyse de la demande de workflow",
            content="Classification du type d'urgence et recherche de procédure..."
        )

    # Step 1: Classify workflow type
    classification = await self._classify_workflow(user_input, context)
    workflow_action = classification["action"]
    urgency = classification["urgency"]

    if thought_stream:
        thought_stream.add_thought(
            thought_type=ThoughtType.PROCESSING,
            title=f"Workflow identifié: {workflow_action}",
            content=f"Urgence: {urgency}, Confiance: {classification['confidence']}"
        )

    # Step 2: Try to fetch emergency workflow template
    emergency_service = EmergencyWorkflowService(db=self.db)
    workflow_template = await emergency_service.get_workflow(
        workflow_type=workflow_action,
        tenant_id=tenant_id
    )

    if workflow_template:
        # Scenario 1: Template exists
        if thought_stream:
            thought_stream.add_thought(
                thought_type=ThoughtType.PROCESSING,
                title="Procédure préenregistrée trouvée",
                content=f"Checklist: {workflow_template['workflow_name']} (v{workflow_template.get('version', 1)})"
            )

        # Enrich with context
        enriched_workflow = await emergency_service.enrich_workflow_with_context(
            workflow=workflow_template,
            user_input=user_input,
            context=context,
            db=self.db
        )
    else:
        # Scenario 2: No template → Dynamic generation
        if thought_stream:
            thought_stream.add_thought(
                thought_type=ThoughtType.PROCESSING,
                title="Génération dynamique de la procédure",
                content="Aucun modèle préenregistré, création intelligente en cours..."
            )

        enriched_workflow = await emergency_service.generate_dynamic_workflow(
            incident_description=user_input,
            workflow_type=workflow_action,
            context=context
        )

        # Enrich
        enriched_workflow = await emergency_service.enrich_workflow_with_context(
            workflow=enriched_workflow,
            user_input=user_input,
            context=context,
            db=self.db
        )

    # Step 3: Return to frontend for confirmation
    if thought_stream:
        thought_stream.add_thought(
            thought_type=ThoughtType.COMPLETED,
            title="Procédure prête pour validation",
            content=f"{len(enriched_workflow['steps'])} étapes à valider"
        )

    return {
        "success": True,
        "requires_confirmation": True,
        "workflow": enriched_workflow,
        "message": "Procédure d'urgence prête. Veuillez valider les actions."
    }
```

---

## 📱 IMPLÉMENTATION FRONTEND

### Nouveau Composant React : `EmergencyWorkflowConfirmation`

```typescript
// frontend/src/components/workflow/EmergencyWorkflowConfirmation.tsx

import React, { useState } from 'react';

interface Step {
  step_id: number;
  title: string;
  description: string;
  is_critical: boolean;
  requires_validation: boolean;
  preview?: {
    type: string;
    content: string;
    recipients: string[];
  };
}

interface WorkflowConfirmationProps {
  workflow: {
    workflow_type: string;
    workflow_name: string;
    metadata: {
      estimated_duration_minutes: number;
      critical: boolean;
    };
    steps: Step[];
  };
  onExecute: (selectedSteps: number[]) => void;
  onCancel: () => void;
  onSaveAsTemplate?: () => void;
}

export const EmergencyWorkflowConfirmation: React.FC<WorkflowConfirmationProps> = ({
  workflow,
  onExecute,
  onCancel,
  onSaveAsTemplate
}) => {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [enabledSteps, setEnabledSteps] = useState<Set<number>>(
    new Set(workflow.steps.map(s => s.step_id))
  );

  const toggleExpand = (stepId: number) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  const toggleEnable = (stepId: number) => {
    setEnabledSteps(prev => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  const criticalSteps = workflow.steps.filter(s => s.is_critical);
  const executionTime = workflow.metadata.estimated_duration_minutes;

  return (
    <div className="emergency-workflow-modal">
      <div className="modal-header urgent">
        <span className="icon">🚨</span>
        <h2>URGENCE DÉTECTÉE - {workflow.workflow_name}</h2>
      </div>

      <div className="modal-meta">
        <span>Durée estimée : {executionTime} min</span>
        <span>{workflow.steps.length} étapes</span>
        <span className="critical">{criticalSteps.length} étapes critiques</span>
      </div>

      <div className="steps-list">
        {workflow.steps.map((step) => (
          <div
            key={step.step_id}
            className={`step ${step.is_critical ? 'critical' : ''} ${expandedSteps.has(step.step_id) ? 'expanded' : ''}`}
          >
            <div className="step-header">
              <input
                type="checkbox"
                checked={enabledSteps.has(step.step_id)}
                onChange={() => toggleEnable(step.step_id)}
                disabled={step.is_critical}
              />
              <span className="step-number">{step.step_id}.</span>
              <span className="step-title">{step.title}</span>
              {step.is_critical && <span className="badge critical">CRITIQUE</span>}
              <button
                className="expand-btn"
                onClick={() => toggleExpand(step.step_id)}
              >
                {expandedSteps.has(step.step_id) ? '▲' : '▼'} Détails
              </button>
            </div>

            {expandedSteps.has(step.step_id) && step.preview && (
              <div className="step-details">
                <p className="description">{step.description}</p>

                <div className="preview">
                  <strong>{step.preview.type === 'email' ? '📧' : '📱'} {step.preview.type}</strong>
                  <div className="recipients">
                    À : {step.preview.recipients.join(', ')}
                  </div>
                  <div className="content-preview">
                    {step.preview.content}
                  </div>
                </div>

                <button className="btn-secondary">✏️ Modifier</button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="modal-footer">
        <div className="footer-actions">
          <button
            className="btn-primary urgent"
            onClick={() => onExecute(Array.from(enabledSteps))}
          >
            ⚡ TOUT EXÉCUTER
          </button>

          {onSaveAsTemplate && (
            <button
              className="btn-secondary"
              onClick={onSaveAsTemplate}
            >
              💾 Sauvegarder comme modèle
            </button>
          )}

          <button
            className="btn-cancel"
            onClick={onCancel}
          >
            ❌ Annuler
          </button>
        </div>

        <div className="footer-info">
          <span className="info-text">
            Les étapes critiques ne peuvent pas être désactivées
          </span>
        </div>
      </div>
    </div>
  );
};
```

---

## 🎯 AVANTAGES DE CETTE APPROCHE

### 1. **Simplicité UX**
- ✅ Vue complète en 1 écran (pas de pagination)
- ✅ 1 clic pour tout exécuter (mode express)
- ✅ Édition inline possible
- ✅ Preview avant exécution

### 2. **Intelligence**
- ✅ LLM génère workflows si inexistants
- ✅ Apprentissage continu (save as template)
- ✅ Enrichissement contextuel automatique (RAG + SQL)

### 3. **Flexibilité**
- ✅ Templates réutilisables
- ✅ Versioning des workflows
- ✅ Customisation par tenant
- ✅ Désactivation d'étapes non-critiques

### 4. **Robustesse**
- ✅ Traçabilité complète (thought_stream_id)
- ✅ Rollback possible
- ✅ Validation utilisateur obligatoire
- ✅ Multi-tenant isolation

### 5. **Évolutivité**
- ✅ Ajout facile de nouveaux workflows
- ✅ Système de plugins pour actions custom
- ✅ API pour gestion externe (mobile app)

---

## 📋 PLAN D'IMPLÉMENTATION (Sprint 2)

### Phase 1 : Base de données et Backend (2-3h)
1. ✅ Créer table `emergency_workflows`
2. ✅ Créer modèle SQLAlchemy `EmergencyWorkflow`
3. ✅ Implémenter `EmergencyWorkflowService`
4. ✅ Créer API CRUD pour workflows
5. ✅ Enrichir `WorkflowAgent` avec logique to-do

### Phase 2 : Frontend (2-3h)
1. ✅ Créer composant `EmergencyWorkflowConfirmation`
2. ✅ Intégrer dans chat flow
3. ✅ Ajouter gestion d'état (enabled/expanded steps)
4. ✅ Styling urgent (couleurs, animations)

### Phase 3 : N8N Workflow Template (1-2h)
1. ✅ Créer workflow `emergency-water-leak` dans N8N UI
2. ✅ Implémenter logique step-by-step avec callbacks
3. ✅ Tester chaque node individuellement

### Phase 4 : E2E Testing (1h)
1. ✅ Test scenario 1 : To-do existante
2. ✅ Test scenario 2 : Génération dynamique
3. ✅ Test validation partielle (désactiver étapes)
4. ✅ Test mode express

### Phase 5 : Seed Data (30min)
1. ✅ Créer 3-5 templates de base :
   - `emergency_water_leak`
   - `emergency_fire`
   - `emergency_elevator`
   - `emergency_structural`

---

## 🚀 PROCHAINES ÉTAPES

### Immédiat (Tu dois faire)
1. **Valider cette spécification** - Dis-moi si tu approuves cette approche
2. **Ajustements souhaités** - Des points à modifier ?
3. **Priorisation** - On implémente tout ou MVP d'abord ?

### Sprint 2 (Après validation)
1. Je créerai les fichiers backend
2. Je créerai les composants frontend
3. Je créerai le workflow N8N dans l'UI
4. Tests E2E

---

## 📊 COMPARAISON AVEC PROPOSITION INITIALE

| Aspect | Proposition Initiale | Cette Spécification |
|--------|---------------------|---------------------|
| Stockage to-do | ❓ Incertain (RAG?) | ✅ Table dédiée PostgreSQL |
| UX validation | ⚠️ Étape par étape | ✅ Vue complète 1 écran |
| Génération dynamique | ⚠️ Vague | ✅ LLM + few-shot learning |
| Édition | ❌ Non mentionné | ✅ Édition inline |
| Sauvegarde | ❌ Non mentionné | ✅ Save as template |
| Mode express | ❌ Non mentionné | ✅ 1-click execution |
| Preview | ⚠️ Limité | ✅ Preview complet |
| Versioning | ❌ Non mentionné | ✅ Versionné |
| Multi-tenant | ❌ Non mentionné | ✅ Isolation tenant |

---

**Auteur** : Claude (Sonnet 4.5)
**Date** : 2025-11-23
**Statut** : ⏳ EN ATTENTE DE VALIDATION UTILISATEUR

---

## 🤔 QUESTIONS OUVERTES POUR TOI

1. **Approuves-tu cette architecture** ou préfères-tu des modifications ?
2. **Mode Express** (auto-execution après 10s) : trop risqué ou bon compromis ?
3. **Édition inline** : essentiel ou nice-to-have ?
4. **Génération dynamique** : confiance dans le LLM ou préfères-tu 100% templates ?
5. **Priorité** : On fait tout de suite ou MVP minimal d'abord (1 workflow seulement) ?

**Dis-moi ce que tu en penses ! 🚀**
