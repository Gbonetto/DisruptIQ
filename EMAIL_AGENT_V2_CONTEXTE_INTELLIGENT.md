# EmailAgent V2 - Génération Contextuelle Intelligente

**Date**: 2025-11-23
**Status**: ✅ Implémenté et Déployé
**Version**: V2 - Contextual Intelligence

---

## 🎯 Objectif

Améliorer la génération d'emails pour qu'ils soient **riches, contextuels et pertinents** au lieu de génériques.

### Problème Résolu

**Avant (V1)**:
```
User: "envoyons leur un mail pour demande d'intervention en urgence pour degat des eaux au batiment les tilleuls"

EmailAgent générait:
- Objet: "Information Copropriété"
- Corps: "Nous évaluons la situation..."
```

❌ Email générique et inutile
❌ Contexte perdu (adresse, appartement, gravité, contacts)
❌ Pas d'urgence marquée

**Après (V2)**:
```
User: (après une to-do list workflow sur dégât des eaux)
      "envoyons leur un mail pour demande d'intervention"

EmailAgent génère:
- Objet: "🚨 URGENT - Intervention plomberie - Résidence Les Tilleuls"
- Corps: Email détaillé avec:
  • Adresse complète du bâtiment
  • Appartement 12, 3ème étage
  • Propriétaire: M. Dupont (coordonnées)
  • Nature de l'urgence
  • Action requise précise
```

✅ Email riche et contextuel
✅ Toutes les informations pertinentes
✅ Urgence clairement marquée

---

## 🏗️ Architecture V2

### 1. Signature Enrichie

```python
async def generate_email(
    self,
    user_request: str,
    db: AsyncSession,
    recipients: List[Dict[str, Any]] = None,
    conversation_history: List[Dict[str, Any]] = None,  # ✨ NOUVEAU
    workflow_context: Dict[str, Any] = None              # ✨ NOUVEAU
) -> Dict[str, Any]:
```

**Nouveaux paramètres**:
- `conversation_history`: Les 5 derniers messages pour capturer le contexte
- `workflow_context`: Données du workflow (to-do list, incident, contexte)

### 2. Extraction de Contexte Intelligent

**Méthode**: `_extract_context()`

Analyse:
1. **Historique conversationnel** (5 derniers messages)
2. **Workflow context** (building, apartment, severity, etc.)
3. **User request** actuel

Extraction:
```json
{
  "purpose": "Demander intervention urgente plombier",
  "tone": "urgent",
  "urgency": "high",
  "key_points": [
    "Dégât des eaux appartement 12",
    "Résidence Les Tilleuls",
    "Intervention immédiate requise"
  ],
  "extracted_data": {
    "building": "Résidence Les Tilleuls",
    "address": "123 rue des Fleurs",
    "apartment": "12",
    "owner": "M. Dupont",
    "incident_type": "fuite d'eau",
    "severity": "high"
  }
}
```

### 3. Génération d'Email Riche

**Méthode**: `_generate_content()`

Prompt LLM amélioré avec:
- Contexte détaillé du bâtiment/incident
- Points clés à inclure
- Règles strictes de qualité:
  - ✅ Utiliser TOUTES les infos disponibles
  - ✅ Être précis et détaillé
  - ✅ Marquer l'urgence avec emojis
  - ✅ Inclure coordonnées si disponibles
  - ⚠️ Ne PAS inventer d'informations

**Exemple de structure pour urgence**:
```
SUJET: 🚨 URGENT - [Type] - [Bâtiment]

CORPS:
Madame, Monsieur,

Nous faisons appel à vos services pour une intervention urgente...

**Détails de l'incident:**
- Bâtiment: [nom]
- Adresse: [adresse complète]
- Appartement: [numéro]
- Propriétaire: [nom + coordonnées]
- Nature: [description détaillée]

**Action requise:**
[Description claire]

**Contact sur place:**
[Coordonnées]

Cordialement,
Le Syndic
```

---

## 🔌 Intégration avec Orchestrator

### Modifications dans `orchestrator_agent.py`

**1. `_handle_send_email_intelligent()` - Ligne 855**

Accepte maintenant `conversation_history`:
```python
async def _handle_send_email_intelligent(
    self,
    user_input: str,
    db: AsyncSession,
    context: Dict[str, Any] = None,
    thought_stream = None,
    state_manager = None,
    conversation_history: List[Dict[str, Any]] = None  # ✨ NOUVEAU
) -> AgentResponse:
```

**2. `_handle_send_email()` - Ligne 1032**

Extraction du workflow_context depuis:
1. Le contexte immédiat (`context.get("workflow_data")`)
2. L'historique conversationnel (recherche dans les 5 derniers messages)

```python
# Extract workflow_context if available
workflow_context = context.get("workflow_data") if context else None

# If not in immediate context, search conversation history
if not workflow_context and conversation_history:
    for msg in reversed(conversation_history[-5:]):
        if msg.get("role") == "assistant":
            msg_metadata = msg.get("metadata", {})
            if "workflow_data" in msg_metadata:
                workflow_context = msg_metadata["workflow_data"]
                break
```

**3. Appel enrichi à EmailAgent**:
```python
email_draft = await email_agent.generate_email(
    user_request=enriched_input,
    db=db,
    recipients=None,
    conversation_history=conversation_history,  # ✨
    workflow_context=workflow_context           # ✨
)
```

---

## 📊 Flux Complet

### Scénario: Urgence Dégât des Eaux

```
1. User: "URGENT: Dégât des eaux appartement 12, résidence Les Tilleuls, M. Dupont..."
   ↓
2. WorkflowAgent V2 détecte urgence → génère to-do list détaillée
   ↓ (conversation_history contient maintenant la to-do + context_data)

3. User: "envoyons un mail aux plombiers pour intervention"
   ↓
4. Orchestrator détecte intent SEND_EMAIL
   ↓
5. _handle_send_email() extrait workflow_context depuis l'historique
   ↓
6. EmailAgent V2:
   - Analyse conversation_history (to-do list récente)
   - Extrait workflow_context (building, apartment, severity, etc.)
   - Génère email RICHE avec tous les détails
   ↓
7. Email généré:
   SUJET: "🚨 URGENT - Intervention plomberie - Résidence Les Tilleuls"
   CORPS: Email détaillé avec adresse, contact, nature urgence, etc.
```

---

## 🧪 Comment Tester

### Test 1: Email avec Workflow Context

```bash
# Dans l'UI (http://localhost:3000)

# Message 1: Créer workflow d'urgence
URGENT: Dégât des eaux détecté dans l'appartement 12,
résidence Les Tilleuls, 3ème étage.
Propriétaire: M. Dupont (dupont@example.com, 06 12 34 56 78).
Eau coule du plafond, situation critique.

# DisruptIQ génère une to-do list détaillée ✓

# Message 2: Demander email
Envoie un mail aux plombiers pour demande d'intervention urgente

# Vérifier l'email généré contient:
✓ Objet avec 🚨 URGENT
✓ Résidence Les Tilleuls
✓ Appartement 12
✓ Contact M. Dupont
✓ Description détaillée
```

### Test 2: Email sans Workflow (baseline)

```bash
# Message direct sans to-do list préalable
Envoie un mail aux plombiers pour une intervention

# Email devrait être plus générique (pas de contexte riche)
# Mais reste professionnel
```

---

## 📝 Logs pour Debugging

Les logs suivants sont émis:

```python
# Extraction de contexte
logger.info("context_extracted_with_history",
           purpose=...,
           urgency=...,
           has_conversation_history=True,
           has_workflow_context=True)

# Génération d'email
logger.info("email_content_generated",
           subject=...,
           body_length=...,
           urgency="high",
           has_context=True)

# Extraction depuis historique
logger.info("workflow_context_extracted_from_history")
```

**Commande de monitoring**:
```bash
docker-compose logs -f backend | grep -E "(context_extracted|email_content|workflow_context_extracted)"
```

---

## 🔄 Compatibilité

**Rétrocompatibilité**: ✅ Assurée

Les paramètres `conversation_history` et `workflow_context` sont optionnels:
- Si absents: EmailAgent fonctionne comme avant (V1)
- Si présents: EmailAgent génère des emails riches (V2)

**Anciens appels** (sans les nouveaux params):
```python
# Fonctionne toujours
email_draft = await email_agent.generate_email(user_request, db)
```

**Nouveaux appels** (avec contexte):
```python
# Génère des emails plus riches
email_draft = await email_agent.generate_email(
    user_request, db,
    conversation_history=history,
    workflow_context=workflow
)
```

---

## 🚀 Roadmap vers un Système Classe Mondiale

### 🏆 V1 - Production Ready (Actuel + Extensions Critiques)

#### 1. **Email Intelligence** ✅ Fait
- [x] Extraction contexte depuis conversation history
- [x] Enrichissement automatique depuis workflow data
- [x] Génération d'emails riches et détaillés
- [x] Marqueurs d'urgence visuels (🚨)

#### 2. **Email Sending & Tracking** 🚧 À Faire
- [ ] **Envoi réel via N8N** (actuellement = brouillon uniquement)
  - Intégration SMTP/SendGrid/Mailgun
  - Support CC/BCC automatique (copie au syndic)
  - Retry logic sur échec
- [ ] **Tracking des emails**
  - Status: `draft`, `sent`, `delivered`, `opened`, `replied`
  - Timestamps pour chaque état
  - Stockage en DB (table `emails`)
- [ ] **Confirmation utilisateur** avant envoi
  - Modal avec preview complet
  - Option éditer avant envoi
  - Historique des brouillons

#### 3. **Gestion de Destinataires Intelligente** 🚧 Critique
- [ ] **Auto-détection destinataires** depuis contexte
  - Extraction depuis SQL (propriétaires, voisins, syndic)
  - Résolution "les plombiers" → liste professionnels métier plomberie
  - Suggestions basées sur type incident
- [ ] **Groupes de destinataires**
  - Tous copropriétaires
  - Voisins étage concerné + étages inférieurs
  - Professionnels par spécialité
  - Conseil syndical
- [ ] **Validation contacts**
  - Vérification email valide
  - Détection doublons
  - Alerte si contacts manquants

#### 4. **Templates d'Email Professionnels** 📝 Important
- [ ] **Bibliothèque de templates** par type:
  - Urgence (fuite, incendie, sécurité)
  - Information (AG, travaux, règlement)
  - Relance (paiement charges, documents)
  - Demande devis
  - Compte-rendu intervention
- [ ] **Variables dynamiques**
  - `{{building_name}}`, `{{apartment}}`, `{{owner_name}}`
  - `{{incident_date}}`, `{{severity}}`
  - `{{professional_name}}`, `{{intervention_time}}`
- [ ] **Personnalisation par copropriété**
  - Logo/en-tête personnalisé
  - Signature syndic
  - Mentions légales

#### 5. **Workflows d'Urgence Complets** 🚨 Critique
- [ ] **Escalade automatique**
  - Si pas de réponse en X minutes → relancer
  - Si toujours pas de réponse → contacter backup
  - Notification SMS en parallèle pour urgences critiques
- [ ] **Checklist de suivi**
  - Confirmation intervention planifiée
  - Rappel avant RDV
  - Demande compte-rendu post-intervention
  - Validation résolution problème
- [ ] **SLA tracking**
  - Temps de réponse professionnel
  - Temps de résolution incident
  - Alertes si délais dépassés

---

### 🌟 V2 - Système Classe Mondiale

#### 1. **Intelligence Prédictive** 🤖
- [ ] **Détection proactive d'incidents**
  - Pattern analysis: "3 fuites en 2 mois → inspecter canalisation"
  - Corrélation météo/incidents: "pluie → infiltrations étage 5"
  - Alertes préventives avant sinistre
- [ ] **Suggestion automatique de professionnels**
  - Scoring basé sur historique (rapidité, qualité, prix)
  - Disponibilité en temps réel
  - Géolocalisation pour intervention rapide
- [ ] **Prévision de budget**
  - Estimation coût intervention
  - Comparaison devis automatique
  - Alertes dépassement budget prévisionnel

#### 2. **Communication Multi-Canal** 📱
- [ ] **SMS d'urgence**
  - Pour propriétaires sans email
  - Confirmation intervention
  - Alertes critiques
- [ ] **Notifications push** (app mobile)
  - Temps réel
  - Géolocalisation (arrivée technicien)
  - Photos avant/après intervention
- [ ] **Appels automatiques** (Text-to-Speech)
  - Pour personnes âgées
  - Urgences absolues (évacuation)
- [ ] **Chatbot pour suivi**
  - "Où en est mon dossier ?"
  - Mise à jour statut en temps réel

#### 3. **Coordination Multi-Acteurs** 🤝
- [ ] **Dashboard temps réel**
  - Statut de tous les incidents en cours
  - Localisation professionnels sur carte
  - Timeline d'intervention
- [ ] **Collaboration professionnels**
  - Partage photos/documents
  - Chat dédié par intervention
  - E-signature devis/compte-rendu
- [ ] **Transparence copropriétaires**
  - Portail suivi interventions
  - Historique complet par appartement
  - Notifications automatiques étapes clés

#### 4. **Analytics & Reporting** 📊
- [ ] **KPIs de performance**
  - Temps moyen résolution par type incident
  - Taux satisfaction propriétaires
  - Coût moyen par intervention
  - Taux récurrence problèmes
- [ ] **Rapports automatiques**
  - Hebdomadaire: incidents en cours
  - Mensuel: statistiques copropriété
  - Annuel: bilan + recommandations
- [ ] **Benchmarking**
  - Comparaison avec autres copropriétés
  - Identification best practices
  - Optimisation process

#### 5. **Conformité & Traçabilité** 🔒
- [ ] **Archive légale complète**
  - Tous emails envoyés/reçus
  - Timestamps horodatés
  - Preuve de lecture (accusé réception)
  - Export pour contentieux
- [ ] **RGPD-compliant**
  - Consentement explicite
  - Droit à l'oubli
  - Portabilité données
- [ ] **Audit trail**
  - Qui a fait quoi, quand
  - Modifications/suppressions tracées
  - Logs immuables

#### 6. **Intelligence Contextuelle Avancée** 🧠
- [ ] **Apprentissage du style utilisateur**
  - Ton (formel/informel)
  - Structure préférée
  - Expressions récurrentes
- [ ] **Adaptation au destinataire**
  - Propriétaire occupant vs bailleur
  - Français vs anglais auto-détecté
  - Niveau détail (technique vs vulgarisé)
- [ ] **Suggestions intelligentes**
  - "Vous avez oublié de mentionner [X]"
  - "Ce professionnel a mal noté dernièrement, voulez-vous en essayer un autre ?"
  - "Incident similaire résolu en 2h en octobre, voulez-vous répliquer ?"

#### 7. **Intégrations Ecosystème** 🔌
- [ ] **ERP Copropriété**
  - Synchronisation charges/comptabilité
  - Import/export données copropriétaires
- [ ] **Calendrier partagé**
  - Google Calendar / Outlook
  - Réservations espaces communs
  - Planning interventions
- [ ] **Outils métier professionnels**
  - API vers logiciels plombiers/électriciens
  - Synchronisation planning disponibilités
  - Devis électroniques automatiques
- [ ] **IoT / Capteurs**
  - Détecteurs fuite eau connectés
  - Capteurs température/humidité
  - Alertes automatiques anomalie

#### 8. **Workflow Automation Avancé** ⚙️
- [ ] **Workflows personnalisables**
  - Drag-and-drop builder
  - Conditions if/else
  - Déclencheurs multiples (temps, événement, seuil)
- [ ] **Actions automatiques**
  - Création ticket Jira/Trello
  - Envoi facture automatique
  - Mise à jour CRM
  - Génération rapport PDF
- [ ] **Orchestration complexe**
  - Workflows imbriqués
  - Parallélisation tâches
  - Rollback sur erreur

---

### 🎯 Priorités V1 Immédiate (Next Sprint)

#### Must-Have pour Production
1. ✅ **Email contextuel intelligent** → FAIT
2. 🚧 **Envoi email réel via N8N** → CRITIQUE
3. 🚧 **Auto-détection destinataires depuis workflow** → HAUTE
4. 🚧 **Tracking status emails** (sent/delivered) → HAUTE
5. 🚧 **Templates emails professionnels** → MOYENNE

#### Nice-to-Have V1
6. 🔵 **SMS d'urgence fallback** → BASSE (V1.5)
7. 🔵 **Dashboard suivi interventions** → BASSE (V1.5)
8. 🔵 **Notifications push** → BASSE (V2)

---

### 📋 Checklist "Classe Mondiale" V1

**Email Agent**:
- [x] Génération contextuelle intelligente
- [ ] Envoi réel SMTP
- [ ] Tracking complet (draft → sent → delivered → opened)
- [ ] Templates professionnels (5 types minimum)
- [ ] Auto-résolution destinataires
- [ ] Prévisualisation riche avant envoi
- [ ] Historique emails par conversation

**Workflow Urgences**:
- [x] Détection automatique urgences
- [x] Classification + extraction contexte
- [x] To-do list opérationnelle détaillée
- [ ] Envoi emails automatique post-confirmation
- [ ] Escalade si pas de réponse
- [ ] Tracking progression workflow
- [ ] SLA monitoring
- [ ] Notifications temps réel

**UX/UI**:
- [ ] Modal confirmation avant envoi email
- [ ] Edition inline brouillon
- [ ] Preview multi-formats (desktop/mobile)
- [ ] Historique conversations structuré
- [ ] Recherche rapide emails/workflows
- [ ] Filtres par status/urgence/date

**Backend/Infra**:
- [x] Architecture agents modulaire
- [x] ThoughtStream pour temps réel
- [ ] Queue jobs asynchrone (Celery/Bull)
- [ ] Redis cache pour perfs
- [ ] Monitoring (Sentry/Datadog)
- [ ] Tests E2E automatisés (Playwright)
- [ ] CI/CD pipeline

---

### 💡 Innovations Différenciantes

**Ce qui ferait de DisruptIQ un leader mondial**:

1. **AI-First Emergency Management**
   - Seul système avec LLM natif pour urgences copropriété
   - Compréhension naturelle vs formulaires rigides
   - Adaptabilité contexte français (loi Alur, règlements)

2. **Human-in-the-Loop Intelligent**
   - Automation là où utile, contrôle humain où critique
   - Pas de "boîte noire" : explications claires des décisions
   - Confiance par transparence

3. **Ecosystème Ouvert**
   - APIs publiques pour intégrations tierces
   - Webhooks pour événements custom
   - Plugin system pour extensions

4. **Obsession Utilisateur**
   - Onboarding 5 minutes
   - Interface intuitive (pas de formation)
   - Support temps réel via chat
   - Feedback loop continu

5. **Performance & Fiabilité**
   - SLA 99.9% uptime
   - Temps réponse < 200ms
   - Scalabilité horizontale (multi-copropriétés)
   - Backup temps réel + disaster recovery

---

## 📚 Fichiers Modifiés

### 1. `backend/app/services/agents/email_agent.py`

**Méthodes modifiées**:
- `generate_email()`: Nouveaux params `conversation_history`, `workflow_context`
- `_extract_context()`: Analyse historique + workflow
- `_generate_content()`: Prompt enrichi pour emails riches

**Lignes clés**:
- L93-203: `_extract_context()` - Extraction intelligente
- L237-404: `_generate_content()` - Génération riche

### 2. `backend/app/services/agents/orchestrator_agent.py`

**Méthodes modifiées**:
- `_handle_send_email_intelligent()`: Param `conversation_history`
- `_handle_send_email()`: Extraction workflow_context depuis historique

**Lignes clés**:
- L855-863: Signature avec `conversation_history`
- L1088-1108: Extraction workflow_context depuis historique
- L1110-1118: Appel enrichi à EmailAgent

---

## ✅ Checklist de Validation

- [x] EmailAgent accepte `conversation_history` et `workflow_context`
- [x] Extraction de contexte depuis historique conversationnel
- [x] Extraction de workflow_context depuis messages récents
- [x] Prompt LLM enrichi pour génération d'emails riches
- [x] Intégration dans Orchestrator
- [x] Rétrocompatibilité assurée
- [x] Backend redémarré et fonctionnel
- [ ] Tests E2E depuis UI (à faire par l'utilisateur)

---

**Contact**: Claude (Sonnet 4.5)
**Session**: EmailAgent V2 - Contextual Intelligence
**Date**: 2025-11-23
