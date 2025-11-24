# 📧 Intégration N8N Email - DisruptIQ

## 🚀 Quick Start (2 minutes)

### 1. Importer le Workflow

1. Ouvrir : **http://localhost:5678** (admin / disruptiq_n8n_2024)
2. **Workflows** → **Add workflow** → **Import from file**
3. Sélectionner : `n8n_workflows/email_sender_workflow.json`
4. **Import**

### 2. Configurer SMTP

Dans le nœud **"Send Email"** :
- Credentials → **Create New**
- Host: `host.docker.internal`
- Port: `1025`
- Security: None
- Save

### 3. Activer

- Toggle **Inactive** → **Active** (en haut à droite)
- **Save** (Ctrl+S)

### 4. Tester

```bash
python test_n8n_email_integration.py
```

**Attendu :** 4/4 tests ✅

---

## 📁 Fichiers Créés

| Fichier | Description |
|---------|-------------|
| **QUICKSTART_N8N_EMAIL.md** | Démarrage rapide (5 min) |
| **IMPORT_WORKFLOW_ETAPES.md** | Guide visuel étape par étape |
| **GUIDE_AJOUT_EMAIL_WORKFLOW.md** | Ajouter email au workflow existant |
| **N8N_EMAIL_INTEGRATION_GUIDE.md** | Documentation technique complète |
| **N8N_EMAIL_STATUS.md** | État de l'intégration + roadmap |
| `n8n_workflows/email_sender_workflow.json` | Workflow N8N à importer |
| `test_n8n_email_integration.py` | Tests automatisés (4 scénarios) |
| `test_n8n_simple.py` | Tests de connectivité |

---

## 🎯 URLs Importantes

- **N8N UI** : http://localhost:5678
- **Mailhog UI** : http://localhost:8025 (voir les emails)
- **Webhook** : http://localhost:5678/webhook/send-email
- **DisruptIQ** : http://localhost:3000

---

## ✅ État Actuel

```
✅ N8N démarré et accessible
✅ Mailhog démarré (SMTP test)
✅ Workflow JSON prêt à importer
✅ Tests automatisés écrits
✅ Documentation complète
⏳ Action requise : Import manuel du workflow (2 min)
```

---

## 🧪 Test Depuis DisruptIQ Chat

Une fois le workflow importé :

```
User: "Envoie un email à test@example.com pour confirmer le rendez-vous"

DisruptIQ:
  1. EmailAgent détecte la demande
  2. Génère le contenu avec contexte
  3. Appelle N8N webhook
  4. Email envoyé
  5. Confirmation affichée en temps réel
```

Voir l'email dans : **http://localhost:8025**

---

## 📚 Documentation

**Pour démarrer rapidement :**
→ [QUICKSTART_N8N_EMAIL.md](./QUICKSTART_N8N_EMAIL.md)

**Guide d'import détaillé :**
→ [IMPORT_WORKFLOW_ETAPES.md](./IMPORT_WORKFLOW_ETAPES.md)

**Documentation technique :**
→ [N8N_EMAIL_INTEGRATION_GUIDE.md](./N8N_EMAIL_INTEGRATION_GUIDE.md)

---

## 🔧 Commandes Utiles

```bash
# Tests connectivité
python test_n8n_simple.py

# Tests complets (après import)
python test_n8n_email_integration.py

# Vérifier services
docker-compose ps

# Logs N8N
docker-compose logs -f n8n

# Redémarrer Mailhog
docker restart mailhog
```

---

## 💡 Architecture

```
DisruptIQ Chat
    ↓
EmailAgent (génère email avec contexte)
    ↓
N8N Webhook (/webhook/send-email)
    ↓
Parse & Validate
    ↓
Send Email (SMTP)
    ↓
Callback → DisruptIQ
    ↓
ThoughtStream (temps réel)
    ↓
Frontend (confirmation)
```

---

## 🎯 Prochaines Étapes

1. ✅ Importer le workflow (2 min)
2. ✅ Valider avec les tests (4/4)
3. ✅ Tester depuis DisruptIQ Chat
4. 🔄 Phase 2 : Router multi-actions (SMS, Tasks, CRM)
5. 🔄 Phase 3 : SMTP production (Brevo, Gmail, SendGrid)

---

**Besoin d'aide ?** Consulte [IMPORT_WORKFLOW_ETAPES.md](./IMPORT_WORKFLOW_ETAPES.md) pour un guide visuel complet ! 🚀
