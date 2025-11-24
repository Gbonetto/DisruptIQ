# 📚 Index - Documentation Emergency Workflows

**Date**: 2025-11-23
**Version**: 1.0

---

## 🎯 Par où commencer ?

### 🔥 Tu veux déployer MAINTENANT ?
➡️ **`NEXT_STEPS_IMMEDIATE.md`** - Guide pas-à-pas (2-3h)

### 🤔 Tu veux comprendre l'architecture ?
➡️ **`README_EMERGENCY_WORKFLOWS.md`** - Vue d'ensemble rapide

### 📖 Tu veux la stratégie complète ?
➡️ **`STRATEGIE_V1_V2.md`** - Roadmap V1 → V2

---

## 📂 Documents par Thème

### 🚀 Déploiement & Quick Start

| Document | Description | Durée lecture | Quand lire |
|----------|-------------|---------------|------------|
| **NEXT_STEPS_IMMEDIATE.md** | Guide de déploiement étape par étape | 10 min | 🔥 MAINTENANT |
| **README_EMERGENCY_WORKFLOWS.md** | Vue d'ensemble et quick start | 5 min | Avant déploiement |

### 🏗️ Architecture & Implémentation

| Document | Description | Durée lecture | Quand lire |
|----------|-------------|---------------|------------|
| **N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md** | Spec complète V1 + V2+ (architecture, UX, roadmap) | 30 min | Pour comprendre le système complet |
| **N8N_EMERGENCY_V1_IMPLEMENTATION_COMPLETE.md** | Détails d'implémentation backend + guide N8N | 20 min | Après déploiement backend |
| **N8N_V1_PRAGMATIC_IMPLEMENTATION.md** | 🌟 Guide N8N V1 pragmatique (simulation) | 15 min | 🔥 Avant créer workflow N8N |

### 🔒 Contrats & Standards

| Document | Description | Durée lecture | Quand lire |
|----------|-------------|---------------|------------|
| **N8N_API_CONTRACT_V1.md** | 🔒 Contrat API FIGÉ (DisruptIQ ↔ N8N) | 15 min | Avant modifier payloads |

### 🛡️ Production & Robustesse

| Document | Description | Durée lecture | Quand lire |
|----------|-------------|---------------|------------|
| **N8N_PRODUCTION_HARDENING_GUIDE.md** | Guide V2 (idempotence, retry, monitoring) | 30 min | Avant passer en prod (V2) |
| **STRATEGIE_V1_V2.md** | Stratégie et roadmap V1 → V2 | 10 min | Pour planifier V2 |

---

## 📊 Par Niveau de Complexité

### Niveau 1 : Débutant / Quick Start

**Objectif** : Faire tourner le système rapidement

1. **README_EMERGENCY_WORKFLOWS.md** (5 min)
2. **NEXT_STEPS_IMMEDIATE.md** (10 min lecture + 2-3h implémentation)
3. **N8N_V1_PRAGMATIC_IMPLEMENTATION.md** (15 min + 1-2h N8N)

**Résultat** : Workflow opérationnel en simulation

---

### Niveau 2 : Intermédiaire / Production Pilote

**Objectif** : Déployer sur clients pilotes, observer

1. **N8N_EMERGENCY_V1_IMPLEMENTATION_COMPLETE.md** (20 min)
2. **N8N_API_CONTRACT_V1.md** (15 min)
3. **STRATEGIE_V1_V2.md** (10 min)

**Résultat** : Système stable en conditions réelles, métriques collectées

---

### Niveau 3 : Avancé / Production Scale

**Objectif** : Passer en V2 production-grade

1. **N8N_PRODUCTION_HARDENING_GUIDE.md** (30 min)
2. **N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md** (30 min - section V2+)
3. **STRATEGIE_V1_V2.md** (relire section V2)

**Résultat** : Système production-ready avec monitoring, idempotence, retry

---

## 🎓 Par Rôle

### 👨‍💻 Développeur Backend

**Doit lire** :
1. ✅ N8N_EMERGENCY_V1_IMPLEMENTATION_COMPLETE.md
2. ✅ N8N_API_CONTRACT_V1.md
3. ⏳ N8N_PRODUCTION_HARDENING_GUIDE.md (pour V2)

**Fichiers code concernés** :
- `backend/app/models/emergency_workflow.py`
- `backend/app/services/emergency_workflow_service.py`
- `backend/app/services/agents/workflow_agent.py`
- `backend/app/services/agents/orchestrator_agent.py`

---

### 🔧 Développeur N8N / DevOps

**Doit lire** :
1. ✅ N8N_V1_PRAGMATIC_IMPLEMENTATION.md (PRIORITÉ)
2. ✅ N8N_API_CONTRACT_V1.md
3. ✅ NEXT_STEPS_IMMEDIATE.md (section N8N)
4. ⏳ N8N_PRODUCTION_HARDENING_GUIDE.md (pour V2)

**Tâches** :
- Créer workflow N8N dans l'UI
- Configurer webhooks et callbacks
- Tester E2E
- (V2) Implémenter retry, timeout, Redis

---

### 📊 Product Manager / Tech Lead

**Doit lire** :
1. ✅ README_EMERGENCY_WORKFLOWS.md
2. ✅ STRATEGIE_V1_V2.md
3. ✅ N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md (sections architecture & roadmap)

**Décisions à prendre** :
- Validation scope V1
- Go/No-go V2 (basé sur métriques V1)
- Priorisation features V2+

---

### 🎨 Frontend Developer

**Doit lire** :
1. ✅ N8N_API_CONTRACT_V1.md (section Callbacks)
2. ✅ README_EMERGENCY_WORKFLOWS.md
3. ⏳ N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md (section UI/UX)

**Tâches** (V1.1+) :
- Créer modal `EmergencyWorkflowConfirmation`
- Détecter `requires_confirmation: true`
- Afficher previews emails/SMS
- Bouton "Exécuter" → Trigger N8N

---

## 🔍 Par Type de Question

### "Comment déployer rapidement ?"
➡️ **NEXT_STEPS_IMMEDIATE.md**

### "Quel est le contrat API entre DisruptIQ et N8N ?"
➡️ **N8N_API_CONTRACT_V1.md**

### "Comment créer un workflow N8N ?"
➡️ **N8N_V1_PRAGMATIC_IMPLEMENTATION.md**

### "Quelles sont les améliorations V2 ?"
➡️ **N8N_PRODUCTION_HARDENING_GUIDE.md**

### "Quelle est l'architecture complète ?"
➡️ **N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md**

### "Quelle est la stratégie produit ?"
➡️ **STRATEGIE_V1_V2.md**

### "Comment ça marche en résumé ?"
➡️ **README_EMERGENCY_WORKFLOWS.md**

---

## 📅 Timeline de Lecture

### Jour 1 (Déploiement)
**Temps** : 3-4h
1. README_EMERGENCY_WORKFLOWS.md (5 min)
2. NEXT_STEPS_IMMEDIATE.md (10 min)
3. N8N_V1_PRAGMATIC_IMPLEMENTATION.md (15 min)
4. **Action** : Déployer backend + créer workflow N8N

### Semaine 1 (Compréhension)
**Temps** : 2h
1. N8N_EMERGENCY_V1_IMPLEMENTATION_COMPLETE.md (20 min)
2. N8N_API_CONTRACT_V1.md (15 min)
3. STRATEGIE_V1_V2.md (10 min)
4. **Action** : Tester E2E, déployer sur client pilote

### Semaines 2-4 (Observation)
**Temps** : 1h/semaine
1. Monitorer logs
2. Collecter métriques V1
3. Noter problèmes identifiés
4. **Action** : Décider go/no-go V2

### Mois 2 (V2 si nécessaire)
**Temps** : 40h
1. N8N_PRODUCTION_HARDENING_GUIDE.md (30 min)
2. **Action** : Implémenter features V2 selon priorités

---

## 🎯 Checklist par Phase

### Phase 1 : Backend Déployé ✅

- [x] Migration appliquée
- [x] Workflow seedé
- [x] Backend redémarré
- [x] Tests unitaires backend

**Documents utiles** :
- NEXT_STEPS_IMMEDIATE.md (étape 1)

---

### Phase 2 : N8N V1 Créé ⏳

- [ ] Workflow N8N créé dans l'UI
- [ ] Webhooks configurés
- [ ] Auth token configuré
- [ ] Test manuel webhook OK
- [ ] Callbacks reçus par backend

**Documents utiles** :
- N8N_V1_PRAGMATIC_IMPLEMENTATION.md ⭐
- NEXT_STEPS_IMMEDIATE.md (étape 2)

---

### Phase 3 : E2E Validé ⏳

- [ ] Test via DisruptIQ UI OK
- [ ] Template chargé et enrichi
- [ ] Workflow exécuté
- [ ] ThoughtStream updates en temps réel
- [ ] Status final correct

**Documents utiles** :
- NEXT_STEPS_IMMEDIATE.md (étape 3-4)

---

### Phase 4 : Clients Pilotes ⏳

- [ ] 2-3 clients pilotes déployés
- [ ] 50+ exécutions réelles
- [ ] Métriques V1 collectées
- [ ] Problèmes identifiés et documentés
- [ ] Décision V2 prise

**Documents utiles** :
- STRATEGIE_V1_V2.md
- N8N_PRODUCTION_HARDENING_GUIDE.md (référence)

---

### Phase 5 : V2 Production ⏳

- [ ] Features V2 priorisées (selon métriques V1)
- [ ] Implémentation V2 complète
- [ ] Tests de charge
- [ ] Monitoring déployé
- [ ] Runbooks créés

**Documents utiles** :
- N8N_PRODUCTION_HARDENING_GUIDE.md ⭐
- N8N_API_CONTRACT_V1.md (vérifier backward compatibility)

---

## 📚 Fichiers Code Backend

### Modèles
- `backend/app/models/emergency_workflow.py` - Modèle SQLAlchemy

### Services
- `backend/app/services/emergency_workflow_service.py` - Logique métier to-do lists
- `backend/app/services/agents/workflow_agent.py` - Agent orchestration workflows
- `backend/app/services/agents/orchestrator_agent.py` - Routing vers WorkflowAgent

### API
- `backend/app/api/endpoints/n8n_callback.py` - Endpoints callbacks N8N → DisruptIQ

### Migrations
- `backend/alembic/versions/20251123_add_emergency_workflows.py` - Migration table

### Scripts
- `backend/scripts/seed_emergency_workflows.py` - Seed template water_leak

---

## 🔗 Liens Externes

### N8N
- Documentation : https://docs.n8n.io
- UI locale : http://localhost:5678
- Credentials : admin / disruptiq_n8n_2024

### DisruptIQ
- Frontend : http://localhost:3000
- Backend API : http://localhost:8000
- Callback health : http://localhost:8000/api/n8n/callback/health

---

## 🆘 Troubleshooting Rapide

### "Je ne sais pas par où commencer"
➡️ Lis **README_EMERGENCY_WORKFLOWS.md** puis **NEXT_STEPS_IMMEDIATE.md**

### "Le backend ne démarre pas"
➡️ Voir section Troubleshooting dans **NEXT_STEPS_IMMEDIATE.md**

### "N8N ne reçoit pas le webhook"
➡️ Vérifier auth token et URL dans **N8N_V1_PRAGMATIC_IMPLEMENTATION.md**

### "Les callbacks ne passent pas"
➡️ Test connectivity : `docker-compose exec n8n curl http://backend:8000/health`

### "Je veux implémenter une feature V2"
➡️ Consulter **N8N_PRODUCTION_HARDENING_GUIDE.md**

### "Je veux modifier le contrat API"
➡️ ⚠️ Lire d'abord **N8N_API_CONTRACT_V1.md** section "Règles de Stabilité"

---

## 📝 Glossaire

| Terme | Définition |
|-------|------------|
| **Emergency Workflow** | Template préenregistré d'actions à exécuter en urgence |
| **To-Do List** | Liste d'étapes (steps) d'un workflow |
| **Step** | Action individuelle dans un workflow (email, SMS, ticket, etc.) |
| **Critical Step** | Étape dont l'échec arrête le workflow |
| **Non-Critical Step** | Étape dont l'échec n'empêche pas la suite |
| **Callback** | Message de N8N vers DisruptIQ (progress ou result) |
| **ThoughtStream** | Flux temps réel d'updates affichées dans l'UI |
| **Idempotence** | Garantie qu'un workflow n'est jamais exécuté deux fois |
| **Request ID** | Identifiant unique de chaque requête (pour idempotence) |
| **Thought Stream ID** | Identifiant du flux temps réel (pour callbacks) |

---

## 🎯 Résumé Ultra-Rapide

**V1** = Make it work
- Backend : ✅ Fait
- N8N : ⏳ 1-2h de création
- Tests : ⏳ 30 min
- **Total** : 2-3h

**Documents V1** :
1. NEXT_STEPS_IMMEDIATE.md (déploiement)
2. N8N_V1_PRAGMATIC_IMPLEMENTATION.md (N8N)
3. README_EMERGENCY_WORKFLOWS.md (vue d'ensemble)

**V2** = Make it production-grade
- Quand : Après 2-4 semaines observation V1
- Si : Problèmes identifiés (doublons, callbacks ratés, etc.)
- Durée : 3-4 semaines

**Documents V2** :
1. N8N_PRODUCTION_HARDENING_GUIDE.md (robustesse)
2. STRATEGIE_V1_V2.md (roadmap)

---

## 📞 Support

**Questions architecture** : Consulter N8N_EMERGENCY_WORKFLOW_SPECIFICATION.md
**Questions déploiement** : Consulter NEXT_STEPS_IMMEDIATE.md
**Questions N8N** : Consulter N8N_V1_PRAGMATIC_IMPLEMENTATION.md
**Questions stratégie** : Consulter STRATEGIE_V1_V2.md

---

**Auteur** : Claude (Sonnet 4.5)
**Date** : 2025-11-23
**Version** : 1.0
**Status** : Index complet et à jour

🚀 **Commence par** : `README_EMERGENCY_WORKFLOWS.md` ou `NEXT_STEPS_IMMEDIATE.md`
