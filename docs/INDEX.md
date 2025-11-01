# 📚 Index de la Documentation DisruptIQ

**Dernière mise à jour**: 31 octobre 2025
**Version**: 1.0

---

## 🎯 Documents Essentiels (À lire en premier)

| Document | Description | Audience |
|----------|-------------|----------|
| [README.md](./README.md) | Vue d'ensemble du projet et navigation | Tous |
| [V1_COMPLETION_AUDIT.md](./V1_COMPLETION_AUDIT.md) | ⭐ **Audit complet V1** - État de toutes les fonctionnalités | Product Owner, Devs |
| [QUICK_START.md](./guides/QUICK_START.md) | Guide de démarrage rapide - Lancer l'app en 5 min | Nouveaux utilisateurs |

---

## 📖 Par Catégorie

### 🚀 Guides Utilisateurs (docs/guides/)

**Pour les utilisateurs finaux et les nouveaux développeurs**

| Document | Description | Durée lecture |
|----------|-------------|---------------|
| [QUICK_START.md](./guides/QUICK_START.md) | Démarrage rapide, commandes essentielles | 10 min |
| [TESTING_GUIDE.md](./guides/TESTING_GUIDE.md) | Guide de tests (manuels et automatisés) | 15 min |
| [VENDOR_INDEXING_GUIDE.md](./guides/VENDOR_INDEXING_GUIDE.md) | Système d'indexation des fournisseurs | 10 min |
| [TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md) | Résolution des problèmes courants | 10 min |

**Guides recommandés par profil:**
- 👤 **Utilisateur final (syndic)**: QUICK_START → Utilisation Dashboard
- 🧑‍💻 **Développeur**: QUICK_START → TESTING_GUIDE → ARCHITECTURE
- 🐛 **Support/Debug**: TROUBLESHOOTING → Logs backend

---

### 🔧 Setup & Configuration (docs/setup/)

**Pour l'installation et la configuration initiale**

| Document | Description | Prérequis |
|----------|-------------|-----------|
| [ENVIRONMENT.md](./setup/ENVIRONMENT.md) | Variables d'environnement (.env) | Docker installé |
| [GMAIL_OAUTH_SETUP.md](./setup/GMAIL_OAUTH_SETUP.md) | Configuration Gmail API (optionnel V1) | Google Cloud account |
| [DEPLOYMENT_NOTES.md](./setup/DEPLOYMENT_NOTES.md) | Notes de déploiement production | Serveur/VPS |

**Workflow d'installation typique:**
```
1. ENVIRONMENT.md → Configurer .env
2. docker-compose up -d → Lancer services
3. GMAIL_OAUTH_SETUP.md → (Optionnel) Activer Gmail
4. DEPLOYMENT_NOTES.md → (Si prod) Déployer sur VPS
```

---

### 🏗️ Documentation Développeur (docs/development/)

**Pour les développeurs contribuant au projet**

#### Documents Techniques

| Document | Description | Niveau |
|----------|-------------|--------|
| [ARCHITECTURE.md](./development/ARCHITECTURE.md) | Architecture technique complète | Intermédiaire |
| [PRD.md](./development/PRD.md) | Product Requirements Document V2 | Tous |
| [V1_RECOMMENDATIONS.md](./development/V1_RECOMMENDATIONS.md) | Recommandations UX/UI V1 Premium | Product/Design |
| [CONTRIBUTING.md](./development/CONTRIBUTING.md) | Guide de contribution au projet | Contributeurs |

#### Workflows & Intégrations

| Document | Description | Status |
|----------|-------------|--------|
| [N8N_WORKFLOWS.md](./development/N8N_WORKFLOWS.md) | Workflows N8N et webhooks | Structure présente |
| [PHASE1_IMPLEMENTATION_GUIDE.md](./development/PHASE1_IMPLEMENTATION_GUIDE.md) | Guide d'implémentation Phase 1 | Historique |

#### Améliorations & Roadmap

| Document | Description | Timeline |
|----------|-------------|----------|
| [UX_UI_DIGEST_IMPROVEMENTS.md](./development/UX_UI_DIGEST_IMPROVEMENTS.md) | Propositions améliorations UX/UI Digest | V1.1+ |

**Parcours développeur recommandé:**
```
1. PRD.md → Comprendre la vision produit
2. ARCHITECTURE.md → Comprendre la stack technique
3. CONTRIBUTING.md → Standards de code
4. PHASE1_IMPLEMENTATION_GUIDE.md → Historique de développement
```

---

### 📝 Changelog & Historique (docs/changelog/)

**Pour suivre l'évolution du projet**

| Document | Description | Dernière MAJ |
|----------|-------------|--------------|
| [CHANGELOG_FIXES.md](./changelog/CHANGELOG_FIXES.md) | Historique des bugs corrigés | 31 oct 2025 |
| [TESTS_MANUELS.md](./changelog/TESTS_MANUELS.md) | Rapports de tests manuels | 30 oct 2025 |

---

### 📦 Archive (docs/archive/)

**Documents historiques ou obsolètes**

| Document | Raison archivage | Date |
|----------|------------------|------|
| [IMPLEMENTATION_LOG_2025-10-30.md](./archive/IMPLEMENTATION_LOG_2025-10-30.md) | Log d'implémentation d'une session spécifique | 30 oct 2025 |
| [CODE_AUDIT_REPORT.md](./archive/CODE_AUDIT_REPORT.md) | Audit de code intermédiaire (remplacé par V1_COMPLETION_AUDIT) | Oct 2025 |
| [PRODUCT_FEATURES_ROADMAP.md](./archive/PRODUCT_FEATURES_ROADMAP.md) | Roadmap initiale (intégrée dans PRD) | Oct 2025 |

---

## 🗺️ Chemins de Navigation Recommandés

### Parcours 1: Nouveau Syndic (Utilisateur Final)
```
1. README.md → Vue d'ensemble
2. QUICK_START.md → Installation
3. TROUBLESHOOTING.md → Si problème
```
**Temps total**: ~20 minutes

### Parcours 2: Nouveau Développeur
```
1. README.md → Contexte
2. PRD.md → Vision produit
3. ARCHITECTURE.md → Stack technique
4. QUICK_START.md → Environnement local
5. CONTRIBUTING.md → Standards code
6. TESTING_GUIDE.md → Comment tester
```
**Temps total**: ~1h30

### Parcours 3: Product Owner / Manager
```
1. README.md → Overview
2. V1_COMPLETION_AUDIT.md → État des lieux V1
3. PRD.md → Fonctionnalités détaillées
4. V1_RECOMMENDATIONS.md → Roadmap UX/UI
5. CHANGELOG_FIXES.md → Historique corrections
```
**Temps total**: ~45 minutes

### Parcours 4: Support / Debugging
```
1. TROUBLESHOOTING.md → Problèmes courants
2. TESTING_GUIDE.md → Validation fonctionnalités
3. CHANGELOG_FIXES.md → Bugs connus résolus
4. docker-compose logs -f backend → Logs temps réel
```
**Temps total**: ~30 minutes

---

## 🔍 Rechercher un Sujet Spécifique

### Par Fonctionnalité

| Fonctionnalité | Documents Pertinents |
|----------------|---------------------|
| **Smart Digest** | QUICK_START, PRD, V1_COMPLETION_AUDIT, UX_UI_DIGEST_IMPROVEMENTS |
| **Gestion Vendors** | VENDOR_INDEXING_GUIDE, TESTING_GUIDE, V1_COMPLETION_AUDIT |
| **Assistant RAG** | ARCHITECTURE, VENDOR_INDEXING_GUIDE, PRD |
| **Gmail API** | GMAIL_OAUTH_SETUP, ENVIRONMENT, V1_COMPLETION_AUDIT |
| **N8N Webhooks** | N8N_WORKFLOWS, PRD, V1_COMPLETION_AUDIT |
| **Import CSV** | QUICK_START, VENDOR_INDEXING_GUIDE, TESTING_GUIDE |

### Par Problème Technique

| Problème | Document à Consulter |
|----------|---------------------|
| Docker ne démarre pas | TROUBLESHOOTING, QUICK_START |
| Frontend inaccessible | TROUBLESHOOTING (section --host 0.0.0.0) |
| Erreur import CSV | VENDOR_INDEXING_GUIDE, TROUBLESHOOTING |
| Assistant ne trouve pas vendors | VENDOR_INDEXING_GUIDE (section Réindexation) |
| Gmail OAuth erreur | GMAIL_OAUTH_SETUP, TROUBLESHOOTING |
| Erreur PostgreSQL | TROUBLESHOOTING, ENVIRONMENT |
| Erreur Qdrant | TROUBLESHOOTING, ARCHITECTURE |

### Par Composant Technique

| Composant | Documents |
|-----------|-----------|
| **Backend FastAPI** | ARCHITECTURE, CONTRIBUTING, PRD |
| **Frontend React** | ARCHITECTURE, CONTRIBUTING, PRD |
| **PostgreSQL** | ARCHITECTURE, ENVIRONMENT, TROUBLESHOOTING |
| **Qdrant** | ARCHITECTURE, VENDOR_INDEXING_GUIDE |
| **Redis** | ARCHITECTURE, ENVIRONMENT |
| **Docker** | QUICK_START, DEPLOYMENT_NOTES, TROUBLESHOOTING |
| **LLM (GPT-4)** | ARCHITECTURE, PRD, ENVIRONMENT |

---

## 📊 Statistiques Documentation

```
Total Documents:      21 fichiers
Documents Actifs:     18 fichiers
Documents Archivés:   3 fichiers
Catégories:           5 (guides, setup, development, changelog, archive)

Guides Utilisateurs:  4 docs
Guides Technique:     7 docs
Setup/Config:         3 docs
Changelog:            2 docs
Archive:              3 docs
Documents Racine:     2 docs (README, V1_AUDIT)
```

---

## 🔄 Maintenance de la Documentation

### Quand Mettre à Jour

| Document | Fréquence MAJ | Trigger |
|----------|---------------|---------|
| V1_COMPLETION_AUDIT.md | Chaque milestone V1.x | Nouvelle version |
| CHANGELOG_FIXES.md | Chaque bug fix | Correction déployée |
| QUICK_START.md | Changements installation | Modifications Docker/setup |
| TROUBLESHOOTING.md | Nouveau problème récurrent | 3+ tickets similaires |
| PRD.md | Nouvelles features majeures | Changement roadmap |

### Workflow de Documentation

```
1. Feature développée
   ↓
2. Tests passés
   ↓
3. Update CHANGELOG_FIXES.md (si bug fix)
   ↓
4. Update document technique pertinent
   ↓
5. Update V1_COMPLETION_AUDIT.md (si milestone)
   ↓
6. Update INDEX.md (si nouveau doc)
```

---

## 🎯 Checklist Documentation Complète

Pour vérifier que la documentation est à jour:

- [x] README.md décrit le projet clairement
- [x] V1_COMPLETION_AUDIT.md reflète l'état actuel
- [x] QUICK_START.md permet de lancer l'app en <10 min
- [x] TROUBLESHOOTING.md couvre les problèmes courants
- [x] ARCHITECTURE.md documente la stack technique
- [x] ENVIRONMENT.md liste toutes les variables .env
- [x] CHANGELOG_FIXES.md est à jour
- [x] Documents obsolètes sont archivés
- [x] INDEX.md (ce document) est à jour

---

## 💡 Bonnes Pratiques

### Pour les Contributeurs
1. **Lisez PRD.md** avant de coder
2. **Suivez CONTRIBUTING.md** pour les standards
3. **Testez avec TESTING_GUIDE.md** avant PR
4. **Mettez à jour CHANGELOG_FIXES.md** si bug fix

### Pour les Utilisateurs
1. **Commencez par QUICK_START.md**
2. **Consultez TROUBLESHOOTING.md** en cas de problème
3. **Référez-vous à V1_COMPLETION_AUDIT.md** pour les fonctionnalités disponibles

### Pour le Product Owner
1. **Lisez V1_COMPLETION_AUDIT.md** pour l'état du projet
2. **Consultez PRD.md** pour la vision à long terme
3. **Suivez CHANGELOG_FIXES.md** pour les corrections
4. **Planifiez avec V1_RECOMMENDATIONS.md** pour la roadmap UX/UI

---

## 📞 Support & Feedback

**Questions sur la documentation?**
- Consultez d'abord TROUBLESHOOTING.md
- Cherchez dans ce INDEX.md par sujet/problème
- Créez une issue GitHub si doc manquante

**Documentation manquante ou obsolète?**
- Créez un ticket avec label `documentation`
- Proposez une PR avec vos améliorations

---

**Dernière révision**: 31 octobre 2025
**Mainteneur**: Équipe DisruptIQ
**Version**: 1.0
