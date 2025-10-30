# 📚 Documentation DisruptIQ

Bienvenue dans la documentation complète de DisruptIQ - Système RAG intelligent pour la gestion immobilière.

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

## 📊 Statut du Projet

| Composant | Statut | Version | Notes |
|-----------|--------|---------|-------|
| Backend API | ✅ Stable | v0.9 | Production-ready |
| Frontend | ✅ Stable | v0.9 | UI fonctionnelle |
| PostgreSQL | ✅ Opérationnel | 15 | Avec migrations |
| Qdrant | ✅ Opérationnel | 1.9 | Indexation vendors |
| Gmail OAuth | 📄 Documenté | - | Guide disponible |
| N8N Workflows | 🚧 En cours | - | Structure présente |
| Tests E2E | ⏳ À venir | - | Planifié V1.5 |

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

**Dernière mise à jour** : 30 octobre 2025

### Récentes Améliorations
- ✅ Guide Gmail OAuth complet
- ✅ Guide implémentation Phase 1
- ✅ Architecture documentation organisée
- ✅ Système d'indexation vendors documenté
- ✅ Guides de tests complets

---

**📌 Note** : Cette documentation est vivante et mise à jour régulièrement. Si vous trouvez une information obsolète, n'hésitez pas à la signaler.
