# 🎯 Stratégie V1 → V2 - Emergency Workflows

**Date**: 2025-11-23
**Approche**: Pragmatique et itérative

---

## 🏁 Philosophie

> "Make it work (V1), learn from real usage, then make it production-grade (V2)"

**Principe clé** : Ne pas sur-engineering une V1 qui n'a pas encore de trafic réel.

---

## 📊 V1 : "Ça tourne vraiment"

### Objectifs V1

1. ✅ **Valider le pattern** : User → Backend → Template → N8N → Callbacks
2. ✅ **1 workflow opérationnel** : `water_leak` E2E
3. ✅ **Identifier les vrais problèmes** : Doublons ? Callbacks ratés ? Timeouts ?
4. ✅ **2-3 clients pilotes** : Retours terrain réels

### Scope V1

**Ce qu'on fait** :
- ✅ Contrat API figé et respecté
- ✅ Exécution steps correcte (ordre, skip, critique/non-critique)
- ✅ Callbacks best effort (try/catch simple)
- ✅ Logs structurés pour debug
- ✅ Simulation actions (pas vrais emails)

**Ce qu'on ne fait PAS** :
- ❌ Idempotence forte (Redis)
- ❌ Retry sophistiqué (exponential backoff)
- ❌ Monitoring avancé (Prometheus/Grafana)
- ❌ Error tracking externe (Sentry)
- ❌ Timeout management complexe

### Métriques V1 (Manuelles)

**Surveillance** :
```bash
# Logs Docker
docker-compose logs n8n | grep "\[N8N_"

# Doublons
docker-compose logs n8n | grep "N8N_START" | sort | uniq -c

# Échecs
docker-compose logs n8n | grep "N8N_FAIL"

# Callbacks ratés
docker-compose logs n8n | grep "CALLBACK_FAIL"
```

**Questions à répondre en V1** :
1. Combien de doublons détectés ?
2. Combien de callbacks ratés ?
3. Timeouts observés ?
4. Erreurs non catchées ?
5. UX : Les utilisateurs valident-ils bien les workflows ?

### Durée V1

**Temps de dev** : 2-3 heures
**Temps d'observation** : 2-4 semaines en conditions réelles
**Nombre d'exécutions cible** : 50-100 workflows réels

---

## 🚀 V2 : "Production-grade"

### Déclencheurs V2

**Passer en V2 si** :

1. **Doublons > 5%** → Priorité P0 : Idempotence Redis
2. **Callbacks ratés > 10%** → Priorité P1 : Retry logic
3. **Timeouts observés** → Priorité P1 : Timeout management
4. **Besoin monitoring temps réel** → Priorité P2 : Grafana
5. **Erreurs non tracées** → Priorité P2 : Sentry
6. **Scale : 10+ workflows/jour** → Priorité P1 : Toute la robustesse

### Scope V2

**Robustesse** :
- ✅ Idempotence avec Redis (check `request_id`)
- ✅ Retry callbacks (3 attempts, exponential backoff)
- ✅ Timeout management (5min workflow, 30sec actions)
- ✅ Graceful degradation avancée

**Monitoring** :
- ✅ Prometheus metrics export
- ✅ Grafana dashboards (executions, success rate, latency)
- ✅ Sentry error tracking
- ✅ Alertes (critical failures)

**Testing** :
- ✅ Tests de charge (100 workflows simultanés)
- ✅ Tests de résilience (backend down, network slow)
- ✅ Tests d'idempotence (doublons détectés et bloqués)

### Checklist V2

#### Infrastructure
- [ ] Déployer Redis
- [ ] Configurer Prometheus
- [ ] Configurer Grafana dashboards
- [ ] Configurer Sentry

#### Code N8N
- [ ] Implémenter Redis check (idempotence)
- [ ] Implémenter retry logic callbacks
- [ ] Ajouter timeout handlers
- [ ] Exporter metrics Prometheus
- [ ] Structured error logging (Sentry format)

#### Backend
- [ ] Monitoring callbacks reçus/perdus
- [ ] Alertes sur erreurs critiques
- [ ] Dashboard admin (workflows status)

#### Tests
- [ ] Load test (100 workflows simultanés)
- [ ] Chaos test (backend down, Redis down)
- [ ] Idempotence test (double trigger)
- [ ] Callback retry test

#### Documentation
- [ ] Runbook incidents
- [ ] Playbook alertes
- [ ] Procédure rollback

### Durée V2

**Temps de dev** : 1-2 semaines
**Temps de test** : 1 semaine
**Déploiement progressif** : 2-3 semaines (canary deployment)

---

## 📋 Roadmap Complète

### Phase 0 : Backend (✅ FAIT)
**Durée** : Fait
- [x] Modèle `EmergencyWorkflow`
- [x] Service `EmergencyWorkflowService`
- [x] WorkflowAgent enrichi
- [x] Migration + Seed
- [x] Documentation

### Phase 1 : V1 Pragmatique (🔄 EN COURS)
**Durée** : 2-3 heures + 2-4 semaines observation
- [ ] Créer workflow N8N (simulation)
- [ ] Tests manuels E2E
- [ ] Déployer sur 2-3 clients pilotes
- [ ] Observer et noter problèmes

**Livrable** : Workflow opérationnel, logs analysables, liste de problèmes identifiés

### Phase 2 : V2 Production (⏳ FUTURE)
**Durée** : 3-4 semaines
**Dépend de** : Retours V1 + décision go/no-go

**Sous-phases** :
1. **V2.0 - Robustesse critique** (1 semaine)
   - Idempotence Redis
   - Retry callbacks
   - Timeout management

2. **V2.1 - Monitoring** (1 semaine)
   - Prometheus + Grafana
   - Sentry
   - Alertes

3. **V2.2 - Scale** (1 semaine)
   - Load testing
   - Optimisations performance
   - Chaos engineering

4. **V2.3 - Polish** (1 semaine)
   - Documentation finale
   - Runbooks
   - Formation équipe

**Livrable** : Système production-ready, monitoré, testé sous charge

### Phase 3 : Scale Horizontal (⏳ V3+)
**Durée** : TBD
**Dépend de** : Trafic réel > 100 workflows/jour

- Multi-types urgences (fire, elevator, structural)
- Workflows dynamiques (LLM generation)
- Frontend modal React
- API publique pour clients
- Multi-région / HA

---

## 🎯 Décision Tree

```
[Backend V1 déployé]
    ↓
[Créer workflow N8N V1]
    ↓
[Tests E2E OK ?]
    ├─ Non → Debug logs, ajuster, re-tester
    └─ Oui ↓
[Déployer sur 2-3 clients pilotes]
    ↓
[Observer pendant 2-4 semaines]
    ↓
[Analyser métriques V1]
    ├─ Doublons < 5% ET Callbacks OK ET Pas de timeouts
    │   → Continuer V1, scale progressif
    │
    └─ Doublons > 5% OU Callbacks > 10% fail OU Timeouts
        → GO V2
        ↓
        [Prioriser selon problèmes identifiés]
        ├─ Doublons élevés → P0 : Redis idempotence
        ├─ Callbacks ratés → P1 : Retry logic
        ├─ Timeouts → P1 : Timeout management
        └─ Besoin monitoring → P2 : Grafana
        ↓
        [Implémenter V2 par priorité]
        ↓
        [Tests V2]
        ↓
        [Déploiement canary (10% trafic)]
        ↓
        [Validation 1 semaine]
        ↓
        [Rollout 100%]
        ↓
        [Production-grade ✅]
```

---

## 📊 Comparaison V1 vs V2

| Feature | V1 Pragmatique | V2 Production | Impact |
|---------|----------------|---------------|---------|
| **Idempotence** | Log manual | Redis check | Bloque doublons |
| **Retry callbacks** | None | 3 attempts, backoff | +90% delivery |
| **Timeout** | Basic (5s) | Advanced (5min workflow) | Fail safe |
| **Monitoring** | Logs Docker | Grafana dashboards | Visibilité temps réel |
| **Error tracking** | Console.log | Sentry | Debug facile |
| **Load capacity** | 10-20/jour | 100+/jour | Scale 10x |
| **Incident response** | Manual | Runbook + alertes | MTTR -50% |
| **Dev time** | 3h | 3-4 semaines | - |
| **Maintenance** | Ad-hoc | Proactive | Stabilité |

---

## 🎓 Lessons Learned (à compléter après V1)

### Ce qui a bien marché en V1

*À remplir après 2-4 semaines d'usage*

- [ ] Pattern général validé
- [ ] Contrat API stable
- [ ] ...

### Problèmes identifiés en V1

*À remplir pendant l'observation*

- [ ] Nombre de doublons : X%
- [ ] Callbacks ratés : X%
- [ ] Timeouts observés : X fois
- [ ] Bugs critiques : ...
- [ ] UX : Retours utilisateurs ...

### Ajustements V1 → V1.1 (Quick wins)

*Petits ajustements avant V2 complète*

- [ ] Ajuster timeouts HTTP (3s → 10s)
- [ ] Améliorer logs (ajouter champs)
- [ ] Simplifier payloads
- [ ] ...

---

## 💡 Recommandations Stratégiques

### 1. Ne pas précipiter V2

**Attendre** :
- ✅ 50+ exécutions réelles
- ✅ 2-3 clients pilotes satisfaits
- ✅ Problèmes réels identifiés

**Éviter** :
- ❌ Implémenter Redis sans avoir observé de doublons
- ❌ Implémenter retry sans avoir vu de callbacks ratés
- ❌ Monitoring avant d'avoir du trafic

### 2. Prioriser selon l'impact

**P0 (Bloquant prod)** :
- Doublons > 5%
- Perte de données
- Crash systémique

**P1 (Dégradé)** :
- Callbacks ratés > 10%
- Timeouts fréquents
- UX confusante

**P2 (Nice-to-have)** :
- Monitoring avancé
- Optimisations perf
- Features additionnelles

### 3. Documenter les décisions

**À chaque étape, documenter** :
- Pourquoi V2 ? (Quels problèmes observés ?)
- Quelles features V2 ? (Basées sur quelles métriques ?)
- Quel ROI attendu ? (Temps dev vs impact)

**Exemple** :
```
Décision V2 - 2025-12-15
Problème : 12% de callbacks ratés en V1 (observation 4 semaines)
Solution : Retry logic avec exponential backoff
ROI : 3 jours de dev → 90% delivery → -80% tickets support
GO : Validé
```

---

## 🚀 Prochaines Actions Immédiates

### Aujourd'hui (2-3h)
1. Créer workflow N8N V1 selon `N8N_V1_PRAGMATIC_IMPLEMENTATION.md`
2. Tests E2E manuels
3. Valider que tout tourne

### Cette semaine
1. Déployer sur 1 client pilote (usage interne)
2. Former l'équipe à l'usage
3. Monitorer logs quotidiennement

### Dans 2 semaines
1. Déployer sur 2-3 clients pilotes externes
2. Collecter feedback
3. Analyser métriques V1

### Dans 1 mois
1. Décision V2 go/no-go
2. Si go : Planifier sprints V2
3. Si no-go : Scale V1 progressif

---

## 📖 Références

| Document | Usage |
|----------|-------|
| `N8N_V1_PRAGMATIC_IMPLEMENTATION.md` | Guide V1 (MAINTENANT) |
| `N8N_PRODUCTION_HARDENING_GUIDE.md` | Référence V2 (PLUS TARD) |
| `N8N_API_CONTRACT_V1.md` | Contrat stable (TOUJOURS) |
| `NEXT_STEPS_IMMEDIATE.md` | Déploiement rapide |
| `README_EMERGENCY_WORKFLOWS.md` | Vue d'ensemble |

---

## 🎯 TL;DR

**V1** : Make it work → 2-3h dev + 2-4 semaines observation
**V2** : Make it production-grade → 3-4 semaines dev (SI problèmes identifiés)

**Approche** : Pragmatique et data-driven

**Ne pas** : Sur-engineer V1 sans avoir de données réelles

**Faire** : Déployer V1, observer, décider V2 basé sur les faits

---

**Auteur** : Claude (Sonnet 4.5)
**Date** : 2025-11-23
**Status** : Stratégie validée - Prêt pour V1
**Next** : Créer workflow N8N V1 et observer !
