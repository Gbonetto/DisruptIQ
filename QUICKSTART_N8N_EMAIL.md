# 🚀 Quickstart - N8N Email Integration

## ⚡ Setup en 5 Minutes

### Étape 1 : Vérifier que tout tourne
```bash
docker-compose ps
# Vérifier que n8n et mailhog sont UP
```

### Étape 2 : Importer le workflow

**Via N8N UI (2 minutes) :**

1. Ouvrir http://localhost:5678
   - Login: `admin` / `disruptiq_n8n_2024`

2. **Workflows** → **Import from file**
   - Fichier: `n8n_workflows/email_sender_workflow.json`

3. Dans le workflow, configurer **Send Email** node :
   - Credential: **Create New**
   - Host: `host.docker.internal`
   - Port: `1025`
   - SSL/TLS: None
   - User/Pass: (vides)
   - Save

4. **Activer** le workflow (toggle en haut à droite)

### Étape 3 : Tester

```bash
# Test simple
curl -X POST http://localhost:5678/webhook/send-email \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "subject": "Test Email",
      "body": "Ceci est un test",
      "recipients": [{"email": "test@example.com", "name": "Test"}]
    }
  }'
```

**Voir l'email :**
- Ouvrir http://localhost:8025 (Mailhog UI)

### Étape 4 : Tests complets

```bash
python test_n8n_email_integration.py
```

**Attendu :** 4/4 tests passent ✅

---

## 📝 Commandes Utiles

### Vérifier les services
```bash
# Status des containers
docker-compose ps

# Logs N8N
docker-compose logs -f n8n

# Logs Backend
docker-compose logs -f backend
```

### Tests
```bash
# Test connectivité (rapide)
python test_n8n_simple.py

# Tests complets (après import workflow)
python test_n8n_email_integration.py
```

### Mailhog
```bash
# Démarrer Mailhog (si pas déjà fait)
docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog

# UI Mailhog
http://localhost:8025
```

---

## 🎯 Test Depuis DisruptIQ Chat

1. Ouvrir http://localhost:3000
2. Dans le chat :
   ```
   Envoie un email de test à test@example.com pour confirmer notre rendez-vous
   ```
3. DisruptIQ devrait :
   - ✅ Détecter la demande d'email
   - ✅ Générer le contenu
   - ✅ Envoyer via N8N
   - ✅ Afficher confirmation

4. Vérifier dans Mailhog : http://localhost:8025

---

## 🔧 Troubleshooting Rapide

### Webhook 404
→ Le workflow n'est pas actif
→ Vérifier le toggle dans N8N UI

### SMTP Error
→ Vérifier les credentials SMTP dans le node "Send Email"
→ Host doit être `host.docker.internal` (pas `localhost`)

### Mailhog inaccessible
```bash
docker ps | grep mailhog
# Si rien → le relancer
docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

---

## 📚 Documentation Complète

- **Setup détaillé** : [N8N_EMAIL_INTEGRATION_GUIDE.md](./N8N_EMAIL_INTEGRATION_GUIDE.md)
- **Import manuel** : [IMPORT_EMAIL_WORKFLOW_MANUAL.md](./IMPORT_EMAIL_WORKFLOW_MANUAL.md)
- **Statut actuel** : [N8N_EMAIL_STATUS.md](./N8N_EMAIL_STATUS.md)

---

## ✅ Checklist

- [ ] N8N accessible (http://localhost:5678)
- [ ] Mailhog accessible (http://localhost:8025)
- [ ] Workflow importé et **actif** dans N8N
- [ ] SMTP credentials configurées
- [ ] Test curl fonctionne
- [ ] Tests automatisés passent (4/4)
- [ ] Test depuis DisruptIQ Chat fonctionne

**Une fois tout coché → Intégration opérationnelle ! 🎉**
