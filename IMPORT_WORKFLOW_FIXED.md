# 🔧 Import du Workflow N8N Corrigé

## 📋 **Étapes d'import (5 minutes)**

### 1. Supprimer l'ancien workflow

1. Accéder à N8N: http://localhost:5678
2. Login: `admin@disruptiq.local` / `BCaUC!@6Kschkbw`
3. Aller sur le workflow "emergency-water-leak"
4. Cliquer sur le menu (3 points) → Delete

### 2. Importer le nouveau workflow

1. Dans N8N, cliquer sur "Add workflow"
2. Cliquer sur le menu (3 points en haut à droite) → "Import from File"
3. Ouvrir le fichier: `n8n_workflows/emergency-water-leak-v1-WORKING.json`
4. Le workflow devrait s'afficher avec 6 nodes:
   - Webhook
   - Validate
   - Callback Init (HTTP Request)
   - Execute Steps
   - Callback Final (HTTP Request)
   - Response

### 3. Activer le workflow

1. Cliquer sur le toggle en haut à droite (doit passer à "Active")
2. Vérifier que le webhook est enregistré: l'URL devrait être affichée en bas

### 4. Tester depuis Python

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC2
python test_n8n_workflow.py
```

**Résultat attendu**:
```
✅ Response Status: 200
[N8N_START] emergency-water-leak
[N8N_EXEC] Processing 5 steps
[N8N_SUCCESS] step_id=1
...
[N8N_COMPLETE] status=success
```

### 5. Vérifier les callbacks

```bash
docker-compose logs backend --tail 50 | grep "n8n"
```

**Résultat attendu**:
```
n8n_thought_update_received stream_id=...
n8n_workflow_result_received workflow=emergency_water_leak status=success
```

---

## 🎯 **Différences avec l'ancien workflow**

### ❌ Ancien (ne fonctionnait pas)
```javascript
// Dans node Code
await $http.request({...})  // ❌ $http n'existe pas
```

### ✅ Nouveau (fonctionne)
- **Node HTTP Request dédié** pour chaque callback
- Utilise les expressions N8N natives `={{ ... }}`
- `continueOnFail: true` pour que les callbacks n'arrêtent pas le workflow

---

## 🧪 **Test E2E complet depuis DisruptIQ UI**

Une fois le workflow importé et actif, tester depuis l'UI:

### Scénario de test

1. **Ouvrir DisruptIQ UI**: http://localhost:3000
2. **Message à envoyer**:
   ```
   URGENT: Dégât des eaux détecté dans l'appartement 12,
   résidence Les Tilleuls, 3ème étage.
   Propriétaire: M. Dupont (dupont@example.com, 06 12 34 56 78).
   Eau coule du plafond, situation critique.
   ```

3. **Comportement attendu**:
   - WorkflowAgent détecte l'intent URGENCE:water_leak
   - Charge le template depuis PostgreSQL
   - Enrichit avec LLM (extraction des données)
   - Renvoie `requires_confirmation: true`
   - UI affiche modal avec preview des 5 steps
   - User clique "Exécuter"
   - Webhook N8N est appelé
   - 5 steps s'exécutent (simulation)
   - ThoughtStream updates en temps réel
   - Message final de succès

### Logs à surveiller

**Terminal 1 - N8N**:
```bash
docker-compose logs -f n8n | grep "\[N8N"
```

**Terminal 2 - Backend**:
```bash
docker-compose logs -f backend | grep "emergency\|n8n"
```

---

## 🐛 **Troubleshooting**

### Callbacks ne passent toujours pas

```bash
# Test connectivity N8N → Backend
docker-compose exec n8n curl -v http://backend:8000/api/n8n/callback/health
```

Si ça échoue:
```bash
# Redémarrer les services
docker-compose restart backend n8n
```

### Workflow ne se déclenche pas

```bash
# Vérifier que le workflow est actif
curl -H "X-N8N-API-KEY: n8n_api_disruptiq_2024_secure_key" \
  http://localhost:5678/api/v1/workflows | python -m json.tool
```

Le workflow doit avoir `"active": true`

### ThoughtStream ne s'affiche pas dans l'UI

Vérifier que le frontend écoute les events SSE:
```bash
# Dans le navigateur, ouvrir DevTools → Network → Filter "stream"
# Doit voir une connexion persistante à /api/chat/stream ou similar
```

---

## ✅ **Checklist finale**

- [ ] Ancien workflow supprimé
- [ ] Nouveau workflow importé avec 6 nodes
- [ ] Workflow activé (toggle ON)
- [ ] Test Python → Status 200
- [ ] Logs N8N → Voir `[N8N_COMPLETE] status=success`
- [ ] Logs Backend → Voir `n8n_thought_update_received`
- [ ] Test UI DisruptIQ → Modal s'affiche
- [ ] Test UI DisruptIQ → Workflow s'exécute après clic
- [ ] ThoughtStream → Updates en temps réel visibles

---

**Une fois tous les checks ✅, le système V1 est COMPLET et opérationnel !** 🎉
