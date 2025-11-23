# 🌟 SPECIFICATION - DisruptIQ SMA-RAG + N8N Integration

**Version**: 1.0
**Date**: 2025-11-22
**Objectif**: Architecture world-class pour workflow automation via N8N

---

## 📐 ARCHITECTURE GLOBALE

### Principes Fondamentaux

```
┌─────────────────────────────────────────────────────────────────┐
│                  SEPARATION OF CONCERNS                          │
├─────────────────────────────────────────────────────────────────┤
│  DisruptIQ (INTELLIGENCE)  │  N8N (EXECUTION)                   │
│  ─────────────────────────  │  ──────────────                   │
│  • Comprend l'intention     │  • Exécute les actions            │
│  • Analyse contexte (RAG)   │  • Gère les intégrations          │
│  • Prend décisions          │  • Gère erreurs/retries           │
│  • Génère instructions      │  • Scale les workflows            │
└─────────────────────────────────────────────────────────────────┘
```

### Flow de Traitement

```
USER INPUT
    ↓
┌─────────────────────────────────────────┐
│ NIVEAU 1: ORCHESTRATOR (Décide QUI)    │
│ ─────────────────────────────────────── │
│ • IntentClassifierV5                    │
│ • 9 IntentTypes stables                 │
│ • Route vers agents spécialisés         │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│ NIVEAU 2: WORKFLOW AGENT (Décide QUOI) │
│ ─────────────────────────────────────── │
│ • Classifie en FAMILLE                  │
│ • Sélectionne ACTION N8N                │
│ • Build payload enrichi                 │
│ • Human-in-the-Loop si requis           │
└──────────────────┬──────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│ NIVEAU 3: N8N (Exécute COMMENT)        │
│ ─────────────────────────────────────── │
│ • Reçoit payload standardisé            │
│ • Dispatche aux workflows               │
│ • Exécute actions multi-services        │
│ • Callback vers DisruptIQ               │
└─────────────────────────────────────────┘
```

---

## 🏗️ FAMILLES DE WORKFLOWS N8N

### Architecture en 4 Familles Principales

```python
WORKFLOW_FAMILIES = {
    "COMMUNICATION": {
        "description": "Communications directes aux parties prenantes",
        "actions": [
            "send_email",
            "send_sms",
            "send_multi_channel_alert",
            "send_whatsapp"
        ],
        "requires_confirmation": True,
        "urgency_levels": ["low", "medium", "high"]
    },

    "URGENCE": {
        "description": "Incidents urgents nécessitant intervention immédiate",
        "actions": [
            "emergency_water_leak",
            "emergency_fire_alert",
            "emergency_elevator_stuck",
            "emergency_security_breach"
        ],
        "requires_confirmation": False,  # Action immédiate
        "urgency_levels": ["high", "critical"]
    },

    "GESTION": {
        "description": "Tâches administratives et gestion quotidienne",
        "actions": [
            "payment_reminder",
            "document_request",
            "meeting_schedule",
            "quote_request_bulk",
            "contract_renewal_reminder"
        ],
        "requires_confirmation": True,
        "urgency_levels": ["low", "medium"]
    },

    "DIGEST": {
        "description": "Résumés et synthèses périodiques",
        "actions": [
            "daily_digest",
            "weekly_summary",
            "urgent_alerts_only",
            "monthly_report"
        ],
        "requires_confirmation": False,  # Automatique
        "urgency_levels": ["low"]
    }
}
```

---

## 📋 LES 10 WORKFLOWS PRIORITAIRES

### 1️⃣ EMERGENCY_WATER_LEAK (Famille: URGENCE)

**Cas d'usage**: Fuite d'eau détectée, intervention urgente requise

**Phrases utilisateur**:
- "Urgence fuite d'eau copropriété A, étage 3, appart 12"
- "Alerte : grosse fuite au 3ème étage, appartement de M. Dupont"
- "Fuite d'eau importante, contacter plombier d'urgence"

**Payload DisruptIQ → N8N**:
```json
{
  "action": "emergency_water_leak",
  "tenant_id": "syndic_ABC",
  "user_id": "user_123",
  "urgency": "critical",
  "context": {
    "building_id": "copro_A",
    "building_name": "Résidence des Tilleuls",
    "floor": 3,
    "apartment": {
      "number": 12,
      "owner_name": "M. Dupont",
      "owner_phone": "+33612345678",
      "owner_email": "dupont@email.com"
    },
    "professional": {
      "name": "Plomberie Express 24/7",
      "phone": "+33687654321",
      "email": "urgent@plomberie-express.fr",
      "contract": "Contrat annuel n°2024-PL-001"
    },
    "incident_time": "2025-11-22T14:30:00Z",
    "reported_by": "Gardien - M. Martin"
  },
  "data": {
    "severity": "high",
    "description": "Fuite importante provenant de la salle de bain, risque dégât des eaux étages inférieurs",
    "immediate_actions_taken": [
      "Coupure eau appartement effectuée",
      "Prévenu copropriétaires étages inférieurs"
    ]
  },
  "trace": {
    "conversation_id": "conv_20251122_143045",
    "request_id": "req_abc123",
    "thought_stream_id": "stream_xyz789"
  }
}
```

**Actions N8N**:
1. Email URGENT plombier (template spécial urgence)
2. SMS plombier (confirmation envoi requis)
3. SMS copropriétaire concerné
4. SMS copropriétaires étages inférieurs (si impact)
5. Création ticket Jira "URGENT - Fuite"
6. Notification Slack canal #urgences
7. Log incident dans base DisruptIQ
8. Callbacks ThoughtStream pour chaque étape

**UI Avant Exécution**:
```
🚨 URGENCE DÉTECTÉE

Je vais déclencher le protocole d'urgence "Fuite d'eau" :

✅ Contacter le plombier Plomberie Express 24/7
   • Email + SMS d'alerte urgente

✅ Alerter M. Dupont (propriétaire appart 12)
   • SMS avec instructions

✅ Prévenir copropriétaires étages 1 et 2
   • SMS d'information préventive

✅ Créer ticket intervention urgent

⚠️ Actions déclenchées IMMÉDIATEMENT sans confirmation
(protocole urgence activé)

[EXECUTER MAINTENANT] [ANNULER]
```

**UI Après Exécution** (ThoughtStream):
```
✅ 14:30:45 - Email urgence envoyé à Plomberie Express
✅ 14:30:46 - SMS confirmé au plombier (+336876...)
✅ 14:30:47 - SMS envoyé à M. Dupont
✅ 14:30:48 - SMS envoyés à 2 copropriétaires étages inf.
✅ 14:30:50 - Ticket URGENT-2024-1234 créé
✅ 14:30:51 - Notification Slack postée
✅ 14:30:52 - Incident logué

🎯 Protocole urgence exécuté avec succès
   Temps total : 7 secondes
```

---

### 2️⃣ PAYMENT_REMINDER (Famille: GESTION)

**Cas d'usage**: Relance copropriétaires en retard de paiement

**Phrases utilisateur**:
- "Relance les copropriétaires en retard de paiement"
- "Envoie un rappel aux impayés du trimestre"
- "Fais une relance amiable pour les charges en retard"

**Payload DisruptIQ → N8N**:
```json
{
  "action": "payment_reminder",
  "tenant_id": "syndic_ABC",
  "user_id": "user_123",
  "urgency": "medium",
  "context": {
    "building_id": "copro_A",
    "building_name": "Résidence des Tilleuls",
    "period": "Q4 2024",
    "due_date": "2024-10-31",
    "days_overdue": 22
  },
  "data": {
    "recipients": [
      {
        "owner_id": "owner_45",
        "name": "M. Dubois",
        "email": "dubois@email.com",
        "apartment": "B12",
        "amount_due": 450.00,
        "currency": "EUR",
        "invoice_ref": "FAC-2024-Q4-045"
      },
      {
        "owner_id": "owner_78",
        "name": "Mme Lefebvre",
        "email": "lefebvre@email.com",
        "apartment": "C05",
        "amount_due": 520.00,
        "currency": "EUR",
        "invoice_ref": "FAC-2024-Q4-078"
      }
    ],
    "total_recipients": 2,
    "total_amount": 970.00,
    "reminder_type": "first",  // first, second, final
    "tone": "courteous"
  },
  "trace": {
    "conversation_id": "conv_20251122_150000",
    "request_id": "req_def456",
    "thought_stream_id": "stream_abc123"
  }
}
```

**Actions N8N**:
1. Génération emails personnalisés (template relance)
2. Envoi emails via Gmail API
3. Log envois dans CRM (optionnel)
4. Création rappel follow-up (J+7)
5. Mise à jour statut relance dans DB
6. Callbacks ThoughtStream

**UI Avant Exécution**:
```
📧 RELANCE PAIEMENTS

Je vais envoyer une relance amiable à 2 copropriétaires :

• M. Dubois (Appart B12) - 450,00 € - 22 jours retard
• Mme Lefebvre (Appart C05) - 520,00 € - 22 jours retard

Total à recouvrer : 970,00 €

Type de relance : Première relance (ton courtois)

Aperçu email :
─────────────────────────────────────
Objet : Rappel charges copropriété Q4 2024

Madame, Monsieur,

Nous constatons que le paiement des charges...
[Voir email complet]
─────────────────────────────────────

Confirmez-vous l'envoi ?

[ENVOYER] [MODIFIER] [ANNULER]
```

**UI Après Exécution**:
```
✅ 15:02:12 - Email envoyé à M. Dubois
✅ 15:02:13 - Email envoyé à Mme Lefebvre
✅ 15:02:14 - 2 relances logguées
✅ 15:02:15 - Rappel J+7 programmé

📊 Relance terminée
   • 2 emails envoyés
   • 100% succès
   • Prochain suivi : 29/11/2024
```

---

### 3️⃣ DAILY_DIGEST (Famille: DIGEST)

**Cas d'usage**: Génération et envoi du digest quotidien

**Phrases utilisateur**:
- "Génère le digest du jour"
- "Envoie le résumé quotidien des emails"
- *Automatique à 8h00 via scheduler*

**Payload DisruptIQ → N8N**:
```json
{
  "action": "daily_digest",
  "tenant_id": "syndic_ABC",
  "user_id": "scheduler",  // Déclenché automatiquement
  "urgency": "low",
  "context": {
    "date": "2024-11-22",
    "period": "last_24h",
    "recipients": [
      {
        "name": "Syndic Principal",
        "email": "syndic@copro.fr",
        "role": "admin"
      }
    ]
  },
  "data": {
    "email_stats": {
      "total": 47,
      "urgent": 3,
      "important": 12,
      "routine": 32
    },
    "urgent_emails": [
      {
        "from": "gardien@copro.fr",
        "subject": "Fuite d'eau étage 3",
        "time": "2024-11-22T14:30:00Z",
        "category": "URGENCE",
        "summary": "Fuite importante appartement 12..."
      }
    ],
    "important_emails": [
      // 12 emails importants
    ],
    "actions_required": [
      {
        "type": "decision",
        "description": "Validation devis travaux toiture",
        "deadline": "2024-11-25",
        "priority": "high"
      }
    ],
    "digest_html": "<html>...</html>",  // Généré par DigestAgent
    "digest_text": "Résumé textuel..."
  },
  "trace": {
    "conversation_id": "scheduler_daily",
    "request_id": "req_digest_221124",
    "thought_stream_id": null  // Pas de stream pour scheduler
  }
}
```

**Actions N8N**:
1. Envoi email digest HTML
2. Envoi SMS si urgences critiques (> 5)
3. Post Slack résumé court
4. Archive digest dans Google Drive
5. Log envoi dans DB

**UI Avant Exécution** (Scheduler - pas d'UI):
*Exécution automatique*

**UI Après Exécution** (Logs):
```
✅ 08:00:05 - Digest quotidien généré
✅ 08:00:07 - Email envoyé au syndic
✅ 08:00:08 - 3 urgences détectées (alerte SMS envoyée)
✅ 08:00:09 - Digest archivé Drive
```

---

### 4️⃣ SEND_MULTI_CHANNEL_ALERT (Famille: COMMUNICATION)

**Cas d'usage**: Notification importante via tous canaux

**Phrases utilisateur**:
- "Préviens tous les copropriétaires de la coupure d'eau demain"
- "Alerte générale : AG extraordinaire jeudi"
- "Envoie une notification à tout le monde pour les travaux"

**Payload DisruptIQ → N8N**:
```json
{
  "action": "send_multi_channel_alert",
  "tenant_id": "syndic_ABC",
  "user_id": "user_123",
  "urgency": "high",
  "context": {
    "building_id": "copro_A",
    "building_name": "Résidence des Tilleuls",
    "event_type": "planned_maintenance",
    "event_date": "2024-11-25T09:00:00Z"
  },
  "data": {
    "subject": "Coupure d'eau programmée - 25/11/2024",
    "message": "Nous vous informons d'une coupure d'eau planifiée le lundi 25 novembre de 9h à 17h pour travaux de maintenance sur le réseau.",
    "channels": ["email", "sms"],  // WhatsApp optionnel
    "recipients": "all_owners",  // ou liste spécifique
    "priority": "high",
    "requires_confirmation_receipt": true
  },
  "trace": {
    "conversation_id": "conv_20251122_160000",
    "request_id": "req_ghi789",
    "thought_stream_id": "stream_mno456"
  }
}
```

**Actions N8N**:
1. Envoi emails à tous copropriétaires
2. Envoi SMS (pour urgence high)
3. Post annonce Slack/Teams (si configuré)
4. Suivi confirmations de lecture
5. Relance J-1 pour non-lecteurs
6. Callbacks ThoughtStream

**UI Avant Exécution**:
```
📢 ALERTE MULTI-CANAL

Destinataires : 45 copropriétaires (Résidence des Tilleuls)

Canaux :
✅ Email
✅ SMS

Message :
─────────────────────────────────────
Objet : Coupure d'eau programmée - 25/11/2024

Nous vous informons d'une coupure d'eau...
─────────────────────────────────────

Coût estimé :
• Emails : Gratuit
• SMS : 45 × 0,05€ = 2,25€

⚠️ Suivi des confirmations de lecture activé

[ENVOYER] [MODIFIER] [ANNULER]
```

**UI Après Exécution**:
```
✅ 16:05:23 - 45 emails envoyés
✅ 16:05:45 - 45 SMS envoyés
✅ 16:05:46 - Notification Slack postée
✅ 16:05:47 - Suivi confirmations activé

📊 Notification multi-canal terminée
   • 45 copropriétaires contactés
   • 2 canaux utilisés
   • Coût SMS : 2,25€
   • Confirmations reçues : 12/45 (après 2 min)
```

---

### 5️⃣ QUOTE_REQUEST_BULK (Famille: GESTION)

**Cas d'usage**: Demande de devis à plusieurs professionnels

**Phrases utilisateur**:
- "Demande des devis pour travaux toiture"
- "Contacte 3 entreprises de peinture pour devis façade"
- "Envoie une demande de devis aux électriciens"

**Payload DisruptIQ → N8N**:
```json
{
  "action": "quote_request_bulk",
  "tenant_id": "syndic_ABC",
  "user_id": "user_123",
  "urgency": "medium",
  "context": {
    "building_id": "copro_A",
    "building_name": "Résidence des Tilleuls",
    "project_type": "roofing_repair",
    "deadline_response": "2024-12-10"
  },
  "data": {
    "project": {
      "title": "Réparation toiture suite infiltrations",
      "description": "Réparation urgente de la toiture suite à infiltrations constatées. Surface environ 150m². Travaux à planifier avant fin d'année.",
      "specifications": [
        "Diagnostic complet de la toiture",
        "Réparation des zones endommagées",
        "Traitement anti-mousse",
        "Garantie décennale requise"
      ],
      "budget_range": "10000-25000",
      "currency": "EUR"
    },
    "professionals": [
      {
        "id": "prof_12",
        "name": "Toiture Expert SARL",
        "email": "contact@toiture-expert.fr",
        "phone": "+33123456789",
        "specialty": "Couverture"
      },
      {
        "id": "prof_34",
        "name": "Artisan Couvreur Pro",
        "email": "devis@couvreur-pro.fr",
        "phone": "+33987654321",
        "specialty": "Couverture"
      },
      {
        "id": "prof_56",
        "name": "Rénovation Toiture & Co",
        "email": "contact@renov-toiture.fr",
        "phone": "+33567891234",
        "specialty": "Couverture"
      }
    ],
    "attachments": [
      {
        "name": "Photos_infiltrations.pdf",
        "url": "https://storage.disruptiq.com/files/abc123.pdf",
        "type": "application/pdf"
      }
    ]
  },
  "trace": {
    "conversation_id": "conv_20251122_170000",
    "request_id": "req_jkl012",
    "thought_stream_id": "stream_pqr789"
  }
}
```

**Actions N8N**:
1. Génération emails personnalisés par professionnel
2. Ajout pièces jointes (photos, plans)
3. Envoi emails
4. Création dossier Google Drive pour ce projet
5. Création tableau suivi devis (Google Sheets)
6. Programmation rappels J+7 (si pas réponse)
7. Callbacks ThoughtStream

**UI Avant Exécution**:
```
📋 DEMANDE DE DEVIS MULTIPLE

Projet : Réparation toiture suite infiltrations
Budget estimé : 10 000€ - 25 000€
Délai réponse : 10/12/2024

Professionnels contactés (3) :
• Toiture Expert SARL
• Artisan Couvreur Pro
• Rénovation Toiture & Co

Pièces jointes :
📎 Photos_infiltrations.pdf (2.3 MB)

Email type :
─────────────────────────────────────
Objet : Demande de devis - Réparation toiture

Madame, Monsieur,

Dans le cadre de la gestion de la Résidence des Tilleuls...
[Voir email complet]
─────────────────────────────────────

[ENVOYER] [MODIFIER LISTE] [ANNULER]
```

**UI Après Exécution**:
```
✅ 17:08:12 - Email envoyé à Toiture Expert SARL
✅ 17:08:13 - Email envoyé à Artisan Couvreur Pro
✅ 17:08:14 - Email envoyé à Rénovation Toiture & Co
✅ 17:08:16 - Dossier Drive créé
✅ 17:08:17 - Tableau suivi créé
✅ 17:08:18 - Rappels J+7 programmés

📊 Demandes de devis envoyées
   • 3 professionnels contactés
   • Dossier suivi : [Voir Drive]
   • Tableau : [Voir Sheets]
```

---

### 6️⃣ MEETING_SCHEDULE (Famille: GESTION)

**Cas d'usage**: Planification et convocation AG

**Phrases utilisateur**:
- "Convoque tous les copropriétaires pour l'AG du 15 décembre"
- "Envoie les convocations pour la réunion du conseil syndical"
- "Planifie l'AG extraordinaire et préviens tout le monde"

**Payload**: *(Format similaire aux précédents)*

---

### 7️⃣ EMERGENCY_ELEVATOR_STUCK (Famille: URGENCE)

**Cas d'usage**: Personne bloquée dans l'ascenseur

**Phrases utilisateur**:
- "Urgence ascenseur bloqué avec personne à l'intérieur"
- "Alerte : quelqu'un coincé dans l'ascenseur, étage 5"

**Payload**: *(Format similaire EMERGENCY_WATER_LEAK)*

---

### 8️⃣ DOCUMENT_REQUEST (Famille: GESTION)

**Cas d'usage**: Demande de documents administratifs

**Phrases utilisateur**:
- "Demande aux copropriétaires de renvoyer l'attestation d'assurance"
- "Envoie une demande de justificatif aux locataires"

---

### 9️⃣ CONTRACT_RENEWAL_REMINDER (Famille: GESTION)

**Cas d'usage**: Rappel renouvellement contrats fournisseurs

**Phrases utilisateur**:
- "Rappelle-moi le renouvellement du contrat ascenseur dans 30 jours"
- "Alerte renouvellement contrat plombier"

---

### 🔟 WEEKLY_SUMMARY (Famille: DIGEST)

**Cas d'usage**: Résumé hebdomadaire pour conseil syndical

**Phrases utilisateur**:
- "Génère le résumé de la semaine"
- *Automatique chaque lundi 8h00*

---

## 🔧 PAYLOAD STANDARD DISRUPTIQ → N8N

Tous les payloads suivent cette structure :

```typescript
interface N8NPayload {
  // Métadonnées action
  action: string;              // Nom workflow N8N
  tenant_id: string;           // Isolation multi-tenant
  user_id: string;             // Utilisateur déclencheur
  urgency: "low" | "medium" | "high" | "critical";

  // Contexte copropriété
  context: {
    building_id?: string;
    building_name?: string;
    [key: string]: any;        // Données métier variables
  };

  // Données spécifiques au workflow
  data: {
    [key: string]: any;        // Payload métier
  };

  // Traçabilité
  trace: {
    conversation_id: string;   // ID conversation DisruptIQ
    request_id: string;        // ID unique requête
    thought_stream_id?: string;// Pour callbacks ThoughtStream
  };
}
```

---

## 🔄 CALLBACKS N8N → DISRUPTIQ

N8N peut envoyer des updates pendant l'exécution :

```typescript
// Endpoint: POST /api/n8n/thought
interface ThoughtCallback {
  thought_stream_id: string;
  thought_type: "ANALYZING" | "EXECUTING" | "PROCESSING" | "COMPLETED" | "ERROR";
  message: string;
  workflow_id: string;
  progress?: number;          // 0.0 - 1.0
  metadata?: {
    [key: string]: any;
  };
}
```

**Exemple**:
```bash
# N8N Node "HTTP Request" vers DisruptIQ
POST http://backend:8000/api/n8n/thought
Content-Type: application/json

{
  "thought_stream_id": "stream_xyz789",
  "thought_type": "EXECUTING",
  "message": "📧 Envoi email à Plomberie Express",
  "workflow_id": "emergency_water_leak",
  "progress": 0.3
}
```

---

## 🎨 UI/UX PATTERNS

### Pattern 1: Confirmation Pre-Execution

```
[Icon Action] TITRE ACTION

Description claire de ce qui va être fait

Détails :
• Point 1
• Point 2
• Point 3

[Aperçu] si applicable

Coût estimé / Impact

[BUTTON PRIMARY] [BUTTON SECONDARY] [BUTTON CANCEL]
```

### Pattern 2: Execution Progress (ThoughtStream)

```
✅ HH:MM:SS - Action 1 complétée
✅ HH:MM:SS - Action 2 complétée
⏳ HH:MM:SS - Action 3 en cours...
```

### Pattern 3: Post-Execution Summary

```
[Icon Success] TITRE RESULTAT

📊 Statistiques :
   • Métrique 1
   • Métrique 2

🔗 Liens utiles :
   • Lien 1
   • Lien 2
```

---

## 📦 PROCHAINES ETAPES D'IMPLEMENTATION

### Phase 1: Setup Infrastructure (Sprint 0)
1. ✅ Ajouter N8N à docker-compose.yml
2. ✅ Créer .env avec variables N8N
3. ✅ Setup réseau Docker backend ↔ N8N

### Phase 2: WorkflowAgent Enhanced (Sprint 1)
1. ✅ Implémenter classification par familles
2. ✅ Créer payload builder standardisé
3. ✅ Ajouter Human-in-the-Loop logic
4. ✅ Callbacks ThoughtStream

### Phase 3: N8N Workflows (Sprint 2)
1. ✅ Créer 10 workflows JSON
2. ✅ Tester chaque workflow individuellement
3. ✅ Implémenter callbacks

### Phase 4: E2E Tests (Sprint 3)
1. ✅ Tests automatisés par workflow
2. ✅ Tests intégration complète
3. ✅ Documentation utilisateur

---

**Auteur** : Claude + Équipe DisruptIQ
**Statut** : SPECIFICATION APPROVED - READY FOR IMPLEMENTATION 🚀
