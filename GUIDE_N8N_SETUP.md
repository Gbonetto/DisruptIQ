# 🚀 Guide Configuration N8N pour DisruptIQ

## 📋 Prérequis

- Compte N8N Cloud (innoflow.app.n8n.cloud)
- DisruptIQ backend opérationnel
- Script de test Python (`test_n8n_integration.py`)

---

## 🎯 Option 1 : Workflow Simple de Test (Recommandé pour débuter)

### Étape 1 : Créer un Workflow dans N8N

1. Connectez-vous à https://innoflow.app.n8n.cloud
2. Cliquez sur **"New Workflow"**
3. Nommez le workflow : `DisruptIQ Test Integration`

### Étape 2 : Ajouter un Webhook Node

1. Cliquez sur le **"+"** pour ajouter un node
2. Recherchez **"Webhook"**
3. Sélectionnez **"Webhook"**

### Étape 3 : Configurer le Webhook

Dans les paramètres du Webhook :
- **HTTP Method** : `POST`
- **Path** : `fef6db21-e46a-4789-b263-cc7360132edc`
- **Authentication** : `None`
- **Response Mode** : `Using 'Respond to Webhook' Node`

### Étape 4 : Ajouter un Node de Réponse

1. Connectez le Webhook à un node **"Respond to Webhook"**
2. Configuration :
   - **Respond With** : `JSON`
   - **Response Body** :
   ```json
   {
     "status": "success",
     "message": "Webhook received from DisruptIQ",
     "received_at": "{{ $now }}",
     "data": "{{ $json.body }}"
   }
   ```

### Étape 5 : Activer le Workflow

1. Cliquez sur le bouton **"Active"** en haut à droite
2. Le workflow est maintenant **en production**

---

## 🧪 Option 2 : Mode Test (Pour Développement)

Si vous voulez tester temporairement :

### Dans N8N :
1. **NE PAS** activer le workflow
2. Cliquez sur **"Listen for Test Event"** (ou "Execute Workflow")
3. N8N attend maintenant **UNE seule** requête

### Depuis DisruptIQ :
```bash
# Exécutez immédiatement (dans les 2 minutes)
python test_n8n_integration.py
```

⚠️ **Important** : En mode test, le webhook n'accepte qu'**une seule requête**, puis se désactive.

---

## 🎨 Option 3 : Workflow Complet (Pour Production)

### Structure du Workflow

```
[Webhook]
    ↓
[Switch by Workflow Type]
    ├─ notify_neighbors → [Email Node] → [Slack Notification]
    ├─ send_vendor_emails → [Email Node] → [Google Sheets Log]
    ├─ daily_digest → [Email Node] → [Archive]
    └─ default → [Log to Console]
    ↓
[Respond to Webhook]
```

### Configuration Switch Node

```javascript
{
  "notify_neighbors": "{{ $json.body.workflow === 'notify_neighbors' }}",
  "send_vendor_emails": "{{ $json.body.workflow === 'send_vendor_emails' }}",
  "daily_digest": "{{ $json.body.workflow === 'daily_digest' }}"
}
```

---

## 📦 Import Rapide

### Méthode 1 : Import du Workflow JSON

1. Dans N8N, cliquez sur **"Menu" (3 points)** → **"Import from File"**
2. Sélectionnez le fichier : `n8n_workflow_disruptiq.json`
3. Cliquez sur **"Import"**
4. Activez le workflow

### Méthode 2 : Création Manuelle

Suivez les étapes de l'**Option 1** ci-dessus.

---

## ✅ Vérification de la Configuration

### Test 1 : Vérifier l'URL du Webhook

Dans N8N, une fois le webhook configuré :
1. Cliquez sur le node Webhook
2. Vérifiez l'URL affichée :
   ```
   https://innoflow.app.n8n.cloud/webhook-test/fef6db21-e46a-4789-b263-cc7360132edc
   ```
3. Cette URL doit correspondre à celle dans DisruptIQ `.env`

### Test 2 : Exécuter le Script de Test

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC
python test_n8n_integration.py
```

**Résultat attendu** :
```
✅ Simple Ping          : PASSED
✅ Vendor Emails        : PASSED
✅ Notify Neighbors     : PASSED
✅ Digest Summary       : PASSED

🎉 All tests passed! N8N integration is working correctly.
```

### Test 3 : Vérifier les Exécutions dans N8N

1. Dans N8N, allez dans **"Executions"**
2. Vous devriez voir 4 exécutions récentes
3. Cliquez sur chacune pour voir les données reçues

---

## 🔧 Workflows N8N Recommandés

### 1. Notify Neighbors Workflow

**Trigger** : Webhook DisruptIQ
**Actions** :
1. Extraire la liste des voisins
2. Personnaliser l'email pour chaque voisin
3. Envoyer via Gmail/SendGrid
4. Logger dans Google Sheets
5. Envoyer notification Slack au syndic

### 2. Send Vendor Emails Workflow

**Trigger** : Webhook DisruptIQ
**Actions** :
1. Récupérer la liste des fournisseurs
2. Personnaliser l'email avec {{name}}, {{company}}
3. Envoyer les emails en batch
4. Tracker les ouvertures (si SendGrid)
5. Créer une tâche de suivi dans Notion/Airtable

### 3. Daily Digest Workflow

**Trigger** : Webhook DisruptIQ
**Actions** :
1. Formater le digest en HTML
2. Envoyer au syndic par email
3. Archiver dans Google Drive
4. Poster résumé dans Slack
5. Créer tâches urgentes dans gestionnaire de projet

---

## 🐛 Dépannage

### Erreur : "Webhook not registered"

**Cause** : Le workflow n'est pas activé

**Solution** :
1. Dans N8N, activez le workflow (bouton "Active")
2. OU cliquez sur "Listen for Test Event" pour le mode test

### Erreur : "Connection timeout"

**Cause** : Firewall ou problème réseau

**Solution** :
1. Vérifiez que l'URL est correcte
2. Testez avec `curl` :
   ```bash
   curl -X POST https://innoflow.app.n8n.cloud/webhook-test/fef6db21-e46a-4789-b263-cc7360132edc \
     -H "Content-Type: application/json" \
     -d '{"test": "hello"}'
   ```

### Erreur : "Invalid JSON"

**Cause** : Payload mal formaté

**Solution** :
1. Vérifiez que le Content-Type est `application/json`
2. Validez votre JSON avec https://jsonlint.com

---

## 🎯 Prochaines Étapes

1. **Tester** : Exécutez `python test_n8n_integration.py`
2. **Implémenter** : Créez vos workflows métier dans N8N
3. **Connecter** : Liez DisruptIQ aux vrais services (Gmail, Slack, etc.)
4. **Monitorer** : Surveillez les exécutions dans N8N

---

## 📞 Besoin d'Aide ?

- Documentation N8N : https://docs.n8n.io/
- Exemples de workflows : https://n8n.io/workflows/
- Support DisruptIQ : Vérifiez les logs backend avec `docker-compose logs backend`

---

**Créé le** : 1er novembre 2025
**Version** : 1.0
**Testé avec** : N8N Cloud, DisruptIQ v1.0
