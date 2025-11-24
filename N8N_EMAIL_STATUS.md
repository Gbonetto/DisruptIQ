# Statut de l'Intégration N8N Email

## ✅ Ce qui est prêt

### 1. Infrastructure
- ✅ **N8N** : En cours d'exécution sur http://localhost:5678
- ✅ **Mailhog** : SMTP de test sur localhost:1025 (UI: http://localhost:8025)
- ✅ **Backend DisruptIQ** : API prête
- ✅ **Webhook existant** : `emergency-water-leak` fonctionne

### 2. Fichiers créés

| Fichier | Description | Statut |
|---------|-------------|--------|
| `n8n_workflows/email_sender_workflow.json` | Workflow N8N complet | ✅ Prêt |
| `test_n8n_email_integration.py` | Tests automatisés complets (4 tests) | ✅ Prêt |
| `test_n8n_simple.py` | Tests de connectivité basiques | ✅ Testé |
| `setup_n8n_complete.py` | Script d'import automatique | ⚠️ Nécessite API key |
| `IMPORT_EMAIL_WORKFLOW_MANUAL.md` | Guide d'import manuel | ✅ Prêt |
| `N8N_EMAIL_INTEGRATION_GUIDE.md` | Documentation complète | ✅ Prêt |

### 3. Tests de Connectivité

**Résultats du test (`test_n8n_simple.py`):**
```
✅ PASS - n8n_connectivity (N8N accessible)
✅ PASS - existing_webhook (Webhook emergency-water-leak fonctionne)
❌ FAIL - email_webhook (Workflow email pas encore importé)
✅ PASS - mailhog (SMTP test prêt)

Score: 3/4 (75%)
```

## 🔧 Action Manuelle Requise

### Import du Workflow Email dans N8N

**Option 1 : Import via UI (Recommandé - 5 minutes)**

1. **Ouvrir N8N**
   ```
   http://localhost:5678
   ```
   - Username: `admin`
   - Password: `disruptiq_n8n_2024`

2. **Importer le workflow**
   - Menu **Workflows** → **Add workflow** → **Import from file**
   - Sélectionner : `n8n_workflows/email_sender_workflow.json`
   - Cliquer sur **Import**

3. **Configurer SMTP**
   - Dans le workflow, cliquer sur le nœud **"Send Email"**
   - Cliquer sur **Select Credential** → **Create New Credential**
   - Remplir :
     ```
     Name: SMTP Mailhog
     Host: host.docker.internal
     Port: 1025
     SSL/TLS: None
     User: (vide)
     Password: (vide)
     ```
   - **Save**

4. **Activer le workflow**
   - Toggle en haut à droite : **Inactive** → **Active**

5. **Vérifier**
   ```bash
   curl -X POST http://localhost:5678/webhook/send-email \
     -H "Content-Type: application/json" \
     -d '{"data":{"subject":"Test","body":"Test","recipients":[{"email":"test@test.com"}]}}'
   ```

**Option 2 : Import via CLI (Alternative)**

Si vous avez configuré une API Key N8N :
```bash
python setup_n8n_complete.py
```

## 🧪 Validation Finale

Une fois le workflow importé et actif :

```bash
# Tests complets
python test_n8n_email_integration.py
```

**Tests inclus :**
1. ✅ Envoi email à un seul destinataire
2. ✅ Envoi email à plusieurs destinataires
3. ✅ Gestion d'erreur (pas de destinataires)
4. ✅ Intégration EmailAgent complète

**Résultat attendu :**
```
Total Tests: 4
✅ Passed: 4
❌ Failed: 0
Success Rate: 100%
```

## 📊 Architecture du Workflow Email

```
Webhook Trigger (/webhook/send-email)
    ↓
Parse Email Data (extract recipients, subject, body)
    ↓
Check Recipients (validation)
    ├─→ [YES] Split Recipients
    │       ↓
    │   Send Email (SMTP via Mailhog)
    │       ↓
    │   Aggregate Results
    │       ↓
    │   Callback Success → DisruptIQ Backend
    │       ↓
    │   Response 200
    │
    └─→ [NO] Error - No Recipients
            ↓
        Callback Error → DisruptIQ Backend
            ↓
        Response 400
```

## 🎯 Cas d'Usage

### 1. Envoi Email Simple

**Depuis DisruptIQ Chat :**
```
User: "Envoie un email à test@example.com pour confirmer le rendez-vous"

DisruptIQ:
  → EmailAgent détecte la demande
  → Génère le contenu
  → Appelle N8N webhook
  → Email envoyé via Mailhog
  → Confirmation affichée
```

**Payload envoyé :**
```json
{
  "action": "send_email",
  "data": {
    "subject": "Confirmation de rendez-vous",
    "body": "Madame, Monsieur,\n\nVotre rendez-vous est confirmé...",
    "recipients": [
      {"email": "test@example.com", "name": "Client"}
    ]
  }
}
```

### 2. Email Urgent (Emergency Workflow)

**Depuis DisruptIQ Chat :**
```
User: "Alerte fuite d'eau appartement 305, prévenir le plombier"

DisruptIQ:
  → WorkflowAgent détecte urgence
  → Enrichit avec contexte (building, floor, etc.)
  → EmailAgent génère email urgent
  → N8N envoie à plombier@pro.com
  → Callback mis à jour en temps réel
```

**Email généré :**
```
Sujet: 🚨 URGENT - Intervention Plomberie - Résidence Les Oliviers

Madame, Monsieur,

Nous faisons appel à vos services pour une intervention URGENTE...

Détails:
- Bâtiment: Les Oliviers
- Appartement: 305
- Nature: Fuite d'eau
- Gravité: CRITIQUE

Cordialement,
Le Syndic
```

## 🔗 Ressources

### URLs Importantes
- **N8N UI** : http://localhost:5678
- **Mailhog UI** : http://localhost:8025
- **DisruptIQ Backend** : http://localhost:8000
- **DisruptIQ Frontend** : http://localhost:3000

### Documentation
- [IMPORT_EMAIL_WORKFLOW_MANUAL.md](./IMPORT_EMAIL_WORKFLOW_MANUAL.md) - Guide d'import
- [N8N_EMAIL_INTEGRATION_GUIDE.md](./N8N_EMAIL_INTEGRATION_GUIDE.md) - Doc complète
- [N8N Docs officielles](https://docs.n8n.io/)

### Scripts Disponibles
```bash
# Tests simples (connectivité)
python test_n8n_simple.py

# Tests complets (après import workflow)
python test_n8n_email_integration.py

# Setup automatique (si API key)
python setup_n8n_complete.py
```

## 🚀 Prochaines Étapes

### Phase 2 : Router Multi-Actions

Créer un router centralisé pour gérer plusieurs types d'actions :

```
Webhook Router (/webhook/router)
    ↓
Switch (action_type)
    ├─→ send_email
    ├─→ send_sms
    ├─→ create_task
    ├─→ update_crm
    └─→ generate_report
```

### Phase 3 : SMTP Production

Remplacer Mailhog par un vrai service SMTP :
- **Brevo** (gratuit 300 emails/jour)
- **SendGrid** (gratuit 100 emails/jour)
- **Gmail** (avec mot de passe d'application)
- **AWS SES** (payant mais fiable)

### Phase 4 : Templates Avancés

- Templates HTML responsive
- Variables dynamiques depuis DB
- Pièces jointes
- Tracking de lecture
- Webhooks de retour (bounces, opens, clicks)

## 📝 Notes

- **Mailhog** capture tous les emails sans les envoyer réellement (parfait pour dev/test)
- Le workflow supporte **plusieurs destinataires** en parallèle
- Les **callbacks** permettent le suivi en temps réel dans DisruptIQ
- Le format du payload est **compatible** avec l'architecture existante
- L'authentification webhook utilise le **Bearer token** défini dans `.env`

## ✅ Checklist de Validation

Avant de passer en production :

- [ ] Workflow email importé et actif dans N8N
- [ ] Credentials SMTP configurées (Mailhog ou production)
- [ ] Tests automatisés passent (4/4)
- [ ] Test manuel depuis DisruptIQ Chat fonctionne
- [ ] Emails visibles dans Mailhog UI
- [ ] Callbacks reçus par DisruptIQ
- [ ] ThoughtStream mis à jour en temps réel
- [ ] Logs N8N sans erreurs
- [ ] Documentation à jour

---

**Créé le :** 2024-11-24
**Version :** 1.0
**Auteur :** DisruptIQ Team + Claude Code
