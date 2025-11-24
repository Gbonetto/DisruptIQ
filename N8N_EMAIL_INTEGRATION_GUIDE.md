# Guide d'Intégration N8N - Envoi d'Emails

## 📋 Vue d'ensemble

Ce guide documente l'intégration fonctionnelle entre DisruptIQ et N8N pour l'envoi réel d'emails.

### Architecture

```
DisruptIQ Backend (EmailAgent)
    ↓ HTTP POST
N8N Webhook (send-email)
    ↓ Parse & Validate
N8N Email Node (SMTP)
    ↓ Send emails
N8N Callback
    ↓ HTTP POST
DisruptIQ Backend (/api/n8n/callback)
    ↓ Update ThoughtStream
Frontend (Real-time update)
```

## 🚀 Installation Rapide

### 1. Importer le Workflow

```bash
# Depuis le dossier DisruptIQ_CC2
python setup_n8n_email_workflow.py
```

Ou manuellement :
1. Ouvrir N8N UI : http://localhost:5678
2. Aller dans **Workflows** → **Import from File**
3. Sélectionner : `n8n_workflows/email_sender_workflow.json`
4. Activer le workflow

### 2. Configurer SMTP

**Option A : Gmail (Recommandé pour tests)**

1. Aller dans **Settings** → **Credentials** → **Add Credential**
2. Type : `SMTP`
3. Paramètres :
   ```
   Name: SMTP Account
   Host: smtp.gmail.com
   Port: 587
   Security: TLS
   User: votre-email@gmail.com
   Password: [Mot de passe d'application Gmail]
   ```

**Option B : Mailhog (Dev local - pas d'envoi réel)**

```bash
docker run -d -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

Credentials :
```
Host: mailhog
Port: 1025
Security: None
User: (vide)
Password: (vide)
```

UI Mailhog : http://localhost:8025

**Option C : Services professionnels**
- **Brevo** (ex-Sendinblue) : Gratuit 300 emails/jour
- **SendGrid** : Gratuit 100 emails/jour
- **Mailgun** : Gratuit 5000 emails/mois (3 premiers mois)

### 3. Tester l'Intégration

```bash
# Lancer les tests automatisés
python test_n8n_email_integration.py
```

**Tests inclus :**
1. ✅ Envoi à un seul destinataire
2. ✅ Envoi à plusieurs destinataires
3. ✅ Gestion d'erreur (pas de destinataires)
4. ✅ Intégration complète EmailAgent

## 📝 Format du Payload

### Payload Standard

```json
{
  "action": "send_email",
  "tenant_id": "syndic_001",
  "user_id": "manager_123",
  "urgency": "medium",
  "data": {
    "subject": "Objet de l'email",
    "body": "Corps du message\n\nCordialement,\nLe Syndic",
    "recipients": [
      {
        "email": "destinataire@example.com",
        "name": "Nom du Destinataire",
        "id": "optional_user_id"
      }
    ],
    "tone": "professional",
    "urgency": "medium"
  },
  "trace": {
    "request_id": "req_12345",
    "thought_stream_id": "stream_001",
    "conversation_id": "conv_001"
  }
}
```

### Champs Obligatoires

- `data.subject` : Objet de l'email
- `data.body` : Corps du message (texte ou HTML)
- `data.recipients` : Liste des destinataires (minimum 1)
  - `email` : Adresse email (obligatoire)
  - `name` : Nom (optionnel)

### Champs Optionnels

- `urgency` : "low", "medium", "high", "critical"
- `tone` : "professional", "urgent", "friendly"
- `trace.*` : Pour le suivi et les callbacks

## 🔧 Workflow N8N Détaillé

### Nœuds du Workflow

1. **Webhook Trigger** (`/webhook/send-email`)
   - Reçoit le payload de DisruptIQ
   - Valide l'authentification (Bearer token)

2. **Parse Email Data** (Code Node)
   - Extrait les destinataires, sujet, corps
   - Prépare les données de trace

3. **Check Recipients** (IF Node)
   - Vérifie que la liste de destinataires n'est pas vide
   - Branche vers succès ou erreur

4. **Split Recipients** (Code Node)
   - Divise la liste pour envoyer un email par destinataire
   - Permet la personnalisation par destinataire

5. **Send Email** (Email Node)
   - Envoie l'email via SMTP
   - Gère les erreurs d'envoi

6. **Aggregate Results** (Code Node)
   - Collecte les résultats de tous les envois
   - Prépare la réponse de succès

7. **Callback Success** (HTTP Request)
   - Notifie DisruptIQ du succès
   - Endpoint : `http://backend:8000/api/n8n/callback`

8. **Response Success** (Webhook Response)
   - Retourne la confirmation à DisruptIQ

9. **Error Handling** (branches d'erreur)
   - Gère les cas d'erreur (pas de destinataires, SMTP failed, etc.)
   - Envoie callback d'erreur à DisruptIQ

### Exemple de Réponse (Succès)

```json
{
  "success": true,
  "message": "Email sent successfully to 3 recipient(s)",
  "emails_sent": [
    {
      "recipient": "user1@example.com",
      "name": "Alice Smith",
      "status": "sent",
      "sentAt": "2024-01-15T10:30:45.123Z"
    },
    {
      "recipient": "user2@example.com",
      "name": "Bob Johnson",
      "status": "sent",
      "sentAt": "2024-01-15T10:30:46.456Z"
    }
  ],
  "request_id": "req_12345",
  "thought_stream_id": "stream_001",
  "subject": "Objet de l'email",
  "timestamp": "2024-01-15T10:30:46.789Z"
}
```

### Exemple de Réponse (Erreur)

```json
{
  "success": false,
  "error": "No recipients provided",
  "message": "Cannot send email without recipients",
  "request_id": "req_12345",
  "thought_stream_id": "stream_001",
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

## 🧪 Tests et Validation

### Test Manuel via cURL

```bash
# Test simple
curl -X POST http://localhost:5678/webhook/send-email \
  -H "Authorization: Bearer disruptiq_n8n_webhook_secret_2024_secure_token" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "subject": "Test Email",
      "body": "Ceci est un test",
      "recipients": [
        {
          "email": "test@example.com",
          "name": "Test User"
        }
      ]
    },
    "trace": {
      "request_id": "test_001"
    }
  }'
```

### Test via DisruptIQ Chat

```
User: "Envoie un email urgent au plombier pour une fuite d'eau au 3ème étage"

DisruptIQ:
  1. EmailAgent détecte la demande
  2. Extrait les informations du contexte
  3. Génère le contenu de l'email
  4. Envoie via N8N webhook
  5. Affiche confirmation en temps réel
```

### Tests Automatisés

```bash
# Lancer tous les tests
python test_n8n_email_integration.py

# Résultats attendus
# ✅ Total Tests: 4
# ✅ Passed: 4
# ✅ Failed: 0
# ✅ Success Rate: 100%
```

## 🔐 Sécurité

### Authentification Webhook

Le webhook N8N utilise un Bearer token pour l'authentification :

```
Authorization: Bearer disruptiq_n8n_webhook_secret_2024_secure_token
```

**Configuration :**
- Défini dans `.env` : `N8N_WEBHOOK_AUTH_TOKEN`
- Vérifié côté DisruptIQ avant l'envoi
- Validé côté N8N dans le workflow

### SMTP Sécurisé

**Bonnes pratiques :**
- ✅ Utiliser TLS/SSL (port 587 ou 465)
- ✅ Stocker les credentials dans N8N (chiffrés)
- ✅ Utiliser des mots de passe d'application (pas le mot de passe principal)
- ✅ Limiter les permissions SMTP (send only)
- ❌ Ne JAMAIS committer les credentials dans git

### Protection contre le Spam

**Recommandations :**
1. Rate limiting sur le webhook
2. Validation des adresses email
3. Whitelist des domaines autorisés
4. Logs d'envoi pour audit

## 📊 Monitoring et Logs

### Logs N8N

```bash
# Voir les logs du workflow
docker-compose logs -f n8n

# Filtrer les erreurs
docker-compose logs n8n | grep ERROR
```

### Logs DisruptIQ

```bash
# Voir les logs EmailAgent
docker-compose logs -f backend | grep email_agent

# Voir les callbacks N8N
docker-compose logs backend | grep n8n_callback
```

### Métriques à Surveiller

- Taux de succès d'envoi (target: >99%)
- Latence moyenne (target: <5s)
- Taux d'erreur SMTP
- Nombre d'emails par heure

## 🛠️ Troubleshooting

### Problème : "Cannot connect to N8N"

**Cause :** N8N n'est pas démarré ou pas accessible

**Solution :**
```bash
docker-compose ps n8n
docker-compose up -d n8n
docker-compose logs n8n
```

### Problème : "SMTP Authentication Failed"

**Cause :** Credentials SMTP incorrects

**Solution :**
1. Vérifier les credentials dans N8N UI
2. Tester avec Telnet : `telnet smtp.gmail.com 587`
3. Vérifier que le mot de passe d'application Gmail est correct
4. Alternative : utiliser Mailhog pour les tests

### Problème : "Webhook not found"

**Cause :** Workflow pas activé ou webhook path incorrect

**Solution :**
1. Vérifier que le workflow est **ACTIF** dans N8N
2. Vérifier l'URL : `http://localhost:5678/webhook/send-email`
3. Réimporter le workflow si nécessaire

### Problème : "No recipients provided"

**Cause :** Le payload ne contient pas de destinataires

**Solution :**
- Vérifier que `data.recipients` est un tableau non vide
- Chaque recipient doit avoir au minimum `email`

### Problème : Emails ne partent pas (pas d'erreur)

**Cause :** SMTP credentials pointent vers Mailhog ou serveur test

**Solution :**
- Vérifier la configuration SMTP dans N8N
- Si Mailhog : consulter l'UI http://localhost:8025
- Si Gmail : vérifier les "Paramètres de sécurité" du compte

## 🎯 Prochaines Étapes

### Phase 2 : Router Multi-Use Cases

Créer un **Router Webhook** centralisé :

```
DisruptIQ → /webhook/router
    ↓ Switch (action_type)
    ├─→ send-email
    ├─→ send-sms
    ├─→ create-task
    └─→ update-crm
```

**Avantages :**
- Un seul webhook pour toutes les actions
- Logique de routing simple (pas de LLM)
- Facile à étendre

### Phase 3 : Callbacks Avancés

Enrichir les callbacks avec :
- Statut de lecture des emails
- Liens de tracking
- Réponses automatiques
- Webhooks tiers (SendGrid, Mailgun)

### Phase 4 : Templates Avancés

- Templates Mustache/Handlebars dans N8N
- Variables dynamiques depuis DB
- Pièces jointes
- Emails HTML responsive

## 📚 Ressources

### Documentation
- [N8N Webhook Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [N8N Email Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.emailsend/)
- [DisruptIQ EmailAgent](backend/app/services/agents/email_agent.py)

### Outils Utiles
- **Mailhog** : http://localhost:8025 (test emails local)
- **N8N UI** : http://localhost:5678 (workflow editor)
- **Webhook.site** : https://webhook.site (debug webhooks)

### Support
- Issues GitHub : [DisruptIQ Issues](https://github.com/your-repo/issues)
- N8N Community : https://community.n8n.io/

---

**Version :** 1.0
**Dernière mise à jour :** 2024-01-15
**Auteur :** DisruptIQ Team
