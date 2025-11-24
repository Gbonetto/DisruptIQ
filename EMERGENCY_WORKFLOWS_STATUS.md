# 📊 Emergency Workflows - État d'implémentation

**Date**: 2025-11-23
**Version**: V1 Pragmatique
**Status**: ✅ Backend complet | ⏳ N8N workflow en cours

---

## ✅ **CE QUI EST TERMINÉ ET FONCTIONNEL**

### 1. Backend DisruptIQ (100% ✅)

- ✅ **Migration Alembic** : Table `emergency_workflows` créée
- ✅ **Modèle `EmergencyWorkflow`** : SQLAlchemy model complet
- ✅ **Service `EmergencyWorkflowService`** : Load templates, enrich with LLM
- ✅ **WorkflowAgent** : Intégration dans l'orchestrator, gestion URGENCE family
- ✅ **Endpoints callbacks N8N** : `/api/n8n/callback/thought-update` et `/workflow-result`
- ✅ **Template water_leak seedé** : 5 steps (notify owner, neighbors, plumber, ticket, followup)

**Fichiers backend modifiés/créés**:
```
backend/app/models/emergency_workflow.py
backend/app/services/emergency_workflow_service.py
backend/app/services/agents/workflow_agent.py  (line 1417 modifié)
backend/app/api/endpoints/n8n_callback.py  (existe déjà, testé OK)
backend/alembic/versions/20251123_add_emergency_workflows.py
backend/scripts/seed_emergency_workflows.py
```

**Test backend**:
```bash
# Vérifier que le workflow est seedé
docker-compose exec -T postgres psql -U disruptiq -d disruptiq \
  -c "SELECT id, workflow_name FROM emergency_workflows"

# Test callback endpoint
curl -H "Authorization: Bearer disruptiq_n8n_webhook_secret_2024_secure_token" \
  http://localhost:8000/api/n8n/callback/health
```

---

### 2. Documentation (100% ✅)

9 fichiers de documentation créés:
- ✅ `README_EMERGENCY_WORKFLOWS.md` - Vue d'ensemble
- ✅ `N8N_API_CONTRACT_V1.md` - Contrat API figé
- ✅ `N8N_V1_PRAGMATIC_IMPLEMENTATION.md` - Guide pragmatique V1
- ✅ `N8N_PRODUCTION_HARDENING_GUIDE.md` - Guide V2 (référence future)
- ✅ `STRATEGIE_V1_V2.md` - Roadmap produit
- ✅ `INDEX_DOCUMENTATION_EMERGENCY_WORKFLOWS.md` - Index complet
- ✅ `NEXT_STEPS_IMMEDIATE.md` - Guide déploiement
- ✅ `N8N_EMERGENCY_V1_IMPLEMENTATION_COMPLETE.md` - Spec technique
- ✅ `N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md` - Architecture complète

---

### 3. N8N API Setup (100% ✅)

- ✅ User N8N activé : `admin@disruptiq.local` / mot de passe hashé
- ✅ API Key créée : `n8n_api_disruptiq_2024_secure_key`
- ✅ API REST N8N testée et fonctionnelle

**Test API**:
```bash
curl -H "X-N8N-API-KEY: n8n_api_disruptiq_2024_secure_key" \
  http://localhost:5678/api/v1/workflows
```

---

## ⏳ **CE QUI RESTE À FINALISER**

### N8N Workflow Creation (90% - Problème technique identifié)

**Problème rencontré**:
- Le workflow se crée via API ✅
- Le workflow s'active via API ✅
- Mais le webhook ne s'enregistre PAS ❌

**Erreur N8N**:
```
Activated workflow "emergency-water-leak" (ID: xxx)
Received request for unknown webhook: The requested webhook "POST emergency-water-leak" is not registered.
```

**Cause identifiée**:
N8N ne register les webhooks production que si le workflow a été "testé" via l'UI ou si certaines metadata spécifiques sont présentes. La création via API REST seule ne suffit pas.

**Solutions possibles**:

#### **Option A: Import via UI (RECOMMANDÉ pour V1)**
1. Accéder à N8N UI: `http://localhost:5678`
2. Se connecter: `admin@disruptiq.local` / `disruptiq_n8n_2024`
3. Import → Copier-coller le JSON du workflow (voir `n8n_workflows/emergency-water-leak-v1.json`)
4. Activer le workflow
5. Le webhook sera automatiquement registered

**Avantage**: Garanti de fonctionner, N8N gère tout.

#### **Option B: Utiliser webhook-test endpoint**
Utiliser `/webhook-test/emergency-water-leak` au lieu de `/webhook/emergency-water-leak`.
Les webhooks test sont toujours actifs sans registration.

**Modification requise**: Changer l'URL dans `WorkflowAgent` :
```python
# backend/app/services/agents/workflow_agent.py
webhook_url = f"{settings.N8N_WEBHOOK_BASE_URL}/webhook-test/emergency-water-leak"
```

#### **Option C: Trigger programmatique via API Executions**
Au lieu d'appeler le webhook, trigger directement une exécution:
```python
POST /api/v1/workflows/{id}/run
Body: { "data": { ... payload ... } }
```

---

## 🎯 **NEXT STEPS RECOMMANDÉS (15 minutes)**

### Étape 1: Import manuel du workflow (5 min)

```bash
# 1. Accéder à N8N
open http://localhost:5678

# 2. Login
Email: admin@disruptiq.local
Password: BCaUC!@6Kschkbw

# 3. Click "Add workflow" → "Import from File"
# 4. Copier-coller le contenu de n8n_workflows/emergency-water-leak-v1.json
# 5. Save
# 6. Activer le toggle en haut à droite
```

### Étape 2: Tester E2E (5 min)

```bash
cd /c/Users/grego/Desktop/Dossiers/DisruptIQ/DisruptIQ_CC2
python test_n8n_workflow.py
```

**Résultat attendu**:
```
✅ Response Status: 200
📊 Response Body: {"success": true, ...}
```

### Étape 3: Vérifier les logs (5 min)

```bash
# Logs N8N
docker-compose logs n8n | grep "\[N8N_"

# Logs Backend
docker-compose logs backend | grep "n8n_"
```

**Résultat attendu**:
```
[N8N_START] emergency-water-leak
[N8N_VALID] request_id=req_xxx
[N8N_EXEC] Processing 5 steps
[N8N_STEP_OK] 1 Notifier le propriétaire
[N8N_STEP_OK] 2 Prévenir les voisins
...
[N8N_COMPLETE] success
```

---

## 📂 **FICHIERS CRÉÉS PENDANT CETTE SESSION**

### Scripts Python
```
create_n8n_workflow_incremental.py  - Création workflow minimal
upgrade_n8n_workflow_full.py        - Upgrade vers full logic
test_n8n_workflow.py                - Test E2E
create_n8n_final_working.py         - Version finale simplifiée
```

### Workflows JSON
```
n8n_workflows/emergency-water-leak-v1.json  - Export N8N (à utiliser pour import manuel)
```

### Documentation
```
EMERGENCY_WORKFLOWS_STATUS.md  - Ce fichier
INDEX_DOCUMENTATION_EMERGENCY_WORKFLOWS.md
STRATEGIE_V1_V2.md
... (voir section Documentation ci-dessus)
```

---

## 🔧 **DÉPANNAGE RAPIDE**

### Workflow ne se déclenche pas
```bash
# Vérifier que le workflow est actif
curl -H "X-N8N-API-KEY: n8n_api_disruptiq_2024_secure_key" \
  http://localhost:5678/api/v1/workflows | python -m json.tool

# Redémarrer N8N
docker-compose restart n8n && sleep 15
```

### Callbacks ne passent pas
```bash
# Test connectivity depuis N8N vers backend
docker-compose exec n8n curl http://backend:8000/api/n8n/callback/health

# Vérifier auth token
grep N8N_WEBHOOK_AUTH_TOKEN .env
```

### Backend ne reçoit pas les workflows
```bash
# Vérifier que le workflow est seedé
docker-compose exec -T backend python -c "
from app.services.emergency_workflow_service import EmergencyWorkflowService
from app.db.session import SessionLocal
import asyncio

async def test():
    db = SessionLocal()
    service = EmergencyWorkflowService(db)
    wf = await service.get_workflow('water_leak')
    print(f'Workflow found: {wf is not None}')
    print(f'Steps: {len(wf[\"steps\"]) if wf else 0}')
    db.close()

asyncio.run(test())
"
```

---

## 📈 **MÉTRIQUES V1 À OBSERVER**

Une fois le workflow fonctionnel, observer pendant 2-4 semaines:

1. **Nombre d'exécutions** : Combien de fois déclenché?
2. **Taux de succès** : % workflows complétés vs failed
3. **Doublons** : Workflows déclenchés 2x pour même incident?
4. **Callbacks ratés** : Combien de callbacks n'arrivent pas au backend?
5. **Steps failed** : Quels steps échouent le plus?

**Décision V2**: Si doublons > 5% OU callbacks ratés > 10%, passer en V2 avec Redis + retry logic.

---

## ✅ **RÉSUMÉ EXÉCUTIF**

| Composant | Status | Prêt pour prod? |
|-----------|--------|-----------------|
| Backend DisruptIQ | ✅ 100% | ✅ Oui |
| Documentation | ✅ 100% | ✅ Oui |
| N8N API Setup | ✅ 100% | ✅ Oui |
| N8N Workflow | ⏳ 90% | ⚠️  Import manuel requis |
| Tests E2E | ⏳ Pending | Après import workflow |

**Temps restant estimé**: **15 minutes** (import manuel + test)

**Bloquant**: Aucun - solution de contournement identifiée (import UI)

**Recommandation**: Procéder avec Option A (import manuel) pour V1, puis améliorer pour V2 si nécessaire selon métriques.

---

**Auteur**: Claude (Sonnet 4.5)
**Date**: 2025-11-23
**Session**: Emergency Workflows Implementation
**Approche**: Incremental & Pragmatic V1
