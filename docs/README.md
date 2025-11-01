# 📚 Documentation DisruptIQ

Bienvenue dans la documentation complète de DisruptIQ - Système RAG intelligent pour la gestion immobilière.

---

## 🔍 Navigation Rapide

### 📑 [**INDEX COMPLET DE LA DOCUMENTATION**](./INDEX.md)
→ **Nouveau!** Index détaillé de tous les documents avec guides de navigation par profil (Utilisateur, Développeur, Product Owner, Support)

### 🎯 [**AUDIT V1 - État du Projet**](./V1_COMPLETION_AUDIT.md)
→ **Score: 85/100** - Rapport complet sur toutes les fonctionnalités V1 (✅ Production Ready)

---

## 📖 Table des Matières

### 🚀 Démarrage Rapide
- [**QUICK_START.md**](./guides/QUICK_START.md) - Guide de démarrage rapide
- [**INSTALLATION.md**](./setup/INSTALLATION.md) - Installation détaillée

### ⚙️ Configuration
- [**GMAIL_OAUTH_SETUP.md**](./setup/GMAIL_OAUTH_SETUP.md) - Configuration Gmail OAuth 2.0
- [**Environment Variables**](./setup/ENVIRONMENT.md) - Variables d'environnement

### 📘 Guides d'Utilisation
- [**VENDOR_INDEXING_GUIDE.md**](./guides/VENDOR_INDEXING_GUIDE.md) - Guide d'indexation des fournisseurs
- [**TESTING_GUIDE.md**](./guides/TESTING_GUIDE.md) - Guide de tests
- [**TROUBLESHOOTING.md**](./guides/TROUBLESHOOTING.md) - Résolution de problèmes courants

### 🛠️ Développement
- [**PRD.md**](./development/PRD.md) - Product Requirements Document
- [**ARCHITECTURE.md**](./development/ARCHITECTURE.md) - Architecture du système
- [**PHASE1_IMPLEMENTATION_GUIDE.md**](./development/PHASE1_IMPLEMENTATION_GUIDE.md) - Guide d'implémentation Phase 1
- [**V1_RECOMMENDATIONS.md**](./development/V1_RECOMMENDATIONS.md) - Recommandations V1
- [**N8N_WORKFLOWS.md**](./development/N8N_WORKFLOWS.md) - Workflows N8N
- [**CONTRIBUTING.md**](./development/CONTRIBUTING.md) - Guide de contribution

### 📝 Changelog
- [**CHANGELOG_FIXES.md**](./changelog/CHANGELOG_FIXES.md) - Historique des corrections
- [**TESTS_MANUELS.md**](./changelog/TESTS_MANUELS.md) - Tests manuels effectués

---

## 🏗️ Architecture du Projet

```
DisruptIQ/
├── backend/              # API FastAPI
│   ├── app/
│   │   ├── api/         # Endpoints REST
│   │   ├── core/        # Configuration & DB
│   │   ├── models/      # Modèles SQLAlchemy
│   │   ├── schemas/     # Schémas Pydantic
│   │   ├── services/    # Logique métier
│   │   └── utils/       # Utilitaires
│   ├── migrations/      # Migrations SQL
│   └── scripts/         # Scripts utilitaires
├── frontend/            # Interface React
│   ├── src/
│   │   ├── components/  # Composants réutilisables
│   │   ├── pages/       # Pages de l'app
│   │   ├── hooks/       # Custom hooks
│   │   ├── lib/         # API client & utils
│   │   └── styles/      # Styles globaux
│   └── public/          # Assets statiques
├── docs/                # 📚 Documentation
└── docker-compose.yml   # Configuration Docker
```

---

## 🎯 Guides par Cas d'Usage

### Je veux... démarrer le projet
→ [QUICK_START.md](./guides/QUICK_START.md)

### Je veux... configurer Gmail
→ [GMAIL_OAUTH_SETUP.md](./setup/GMAIL_OAUTH_SETUP.md)

### Je veux... importer des fournisseurs
→ [VENDOR_INDEXING_GUIDE.md](./guides/VENDOR_INDEXING_GUIDE.md)

### Je veux... implémenter la Phase 1
→ [PHASE1_IMPLEMENTATION_GUIDE.md](./development/PHASE1_IMPLEMENTATION_GUIDE.md)

### Je veux... tester le système
→ [TESTING_GUIDE.md](./guides/TESTING_GUIDE.md)

### Je veux... comprendre l'architecture
→ [ARCHITECTURE.md](./development/ARCHITECTURE.md)

### Je veux... contribuer au projet
→ [CONTRIBUTING.md](./development/CONTRIBUTING.md)

### Je veux... résoudre un problème
→ [TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md)

---

## 📊 Statut du Projet V1

| Composant | Statut | Version | Notes |
|-----------|--------|---------|-------|
| Backend API | ✅ Stable | v1.0 | Production-ready |
| Frontend | ✅ Stable | v1.0 | UI professionnelle |
| PostgreSQL | ✅ Opérationnel | 15 | Avec migrations |
| Qdrant | ✅ Opérationnel | 1.9 | Indexation vendors |
| Digest Quotidien | ✅ Automatique | v1.0 | Scheduler toutes les heures |
| Gestion Vendors | ✅ Complet | v1.0 | Import CSV + RAG |
| Gmail OAuth | 📄 Documenté | - | Optionnel V1 |
| N8N Webhooks | 🟡 Partiel | - | Structure présente, tests requis |
| Tests E2E | ⏳ À venir | - | Planifié V1.1 |

**Voir** [V1_COMPLETION_AUDIT.md](./V1_COMPLETION_AUDIT.md) **pour le rapport détaillé**

---

## 🔗 Liens Rapides

- [Swagger API Docs](http://localhost:8000/api/docs) - Documentation API interactive
- [Qdrant Dashboard](http://localhost:6333/dashboard) - Interface Qdrant
- [Frontend](http://localhost:3000) - Application web

---

## 📧 Support

Pour toute question ou problème :
1. Consultez d'abord la documentation pertinente ci-dessus
2. Vérifiez les logs : `docker-compose logs -f backend`
3. Consultez le [TROUBLESHOOTING.md](./guides/TROUBLESHOOTING.md)

---

## 🔄 Mises à Jour de la Documentation

**Dernière mise à jour** : 31 octobre 2025

### Récentes Améliorations (31 octobre 2025) ⭐
- ✅ **INDEX.md complet** - Navigation par profil et recherche par sujet
- ✅ **V1_COMPLETION_AUDIT.md** - Audit détaillé de complétude V1 (85/100)
- ✅ **Documentation organisée** - Dossier archive/ créé, fichiers déplacés
- ✅ **UX_UI_DIGEST_IMPROVEMENTS.md** - Propositions améliorations UI
- ✅ **Scheduler digest automatique** - Génération toutes les heures
- ✅ **Filtrage spam** - 16+ patterns automatiques

### Améliorations Précédentes (30 octobre 2025)
- ✅ Guide Gmail OAuth complet
- ✅ Guide implémentation Phase 1
- ✅ Architecture documentation organisée
- ✅ Système d'indexation vendors documenté
- ✅ Guides de tests complets

---

## 🎯 Pour Commencer

**Nouveau sur le projet?** Suivez ce parcours:
1. Lisez [INDEX.md](./INDEX.md) pour comprendre la structure de la documentation
2. Consultez [V1_COMPLETION_AUDIT.md](./V1_COMPLETION_AUDIT.md) pour l'état du projet
3. Lancez l'application avec [QUICK_START.md](./guides/QUICK_START.md)

**📌 Note** : Cette documentation est vivante et mise à jour régulièrement. Si vous trouvez une information obsolète, n'hésitez pas à la signaler.
