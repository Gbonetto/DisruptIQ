# 📋 PRD - DisruptIQ v2.2+
## Product Requirements Document - Solution 100% Fonctionnelle et Scalable

**Version**: 2.2
**Date**: 3 Novembre 2025
**Status**: 🚀 Roadmap Actualisée
**Auteur**: Équipe Produit DisruptIQ

---

## 📌 EXECUTIVE SUMMARY

DisruptIQ est un assistant IA multi-agents pour la gestion de copropriétés, permettant aux syndics de:
- 📧 Traiter automatiquement les emails (classification URGENT/IMPORTANT/ROUTINE)
- 🔍 Rechercher dans les documents avec RAG (Retrieval Augmented Generation)
- 📊 Interroger les données en SQL via langage naturel
- 🤖 Générer et envoyer des emails contextualisés
- 🔗 Déclencher des workflows N8N automatisés

### État Actuel (v2.2)
- ✅ **Frontend**: Interface ChatGPT-style avec markdown, Chain of Thoughts temps réel
- ✅ **Backend**: 7 agents spécialisés (SQL, RAG, OCR, Email, Digest, Workflow, Orchestrator)
- ✅ **Infrastructure**: Docker Compose, PostgreSQL, Qdrant, Redis
- ✅ **Data**: Tables test complètes (67 professionnels, 25 copropriétaires, 29 emails, 11 copropriétés)
- ✅ **Innovations récentes**: Markdown rendering, action lists RAG, digest hybrid architecture

### Vision Produit 2026
**Mission**: Devenir l'assistant IA #1 pour les syndics de copropriété en France
**Objectif 12 mois**: 100+ clients, 1.2M€ ARR, plateforme enterprise-ready

---

## 🎯 PROBLÈMES À RÉSOUDRE

### Problème #1: Surcharge Administrative
**Impact**: 15-20h/semaine perdues en tâches répétitives
**Solution DisruptIQ**:
- Classification automatique emails → -60% temps de tri
- Génération emails contextualisés → -70% temps rédaction
- Recherche documentaire intelligente → -80% temps recherche

### Problème #2: Données Fragmentées
**Impact**: Informations éparpillées (emails, documents, base de données)
**Solution DisruptIQ**:
- Hub centralisé avec RAG + SQL en langage naturel
- Recherche unifiée multi-sources
- Historique conversations contextualisé

### Problème #3: Réactivité Urgences
**Impact**: Délais de réponse critiques (dégâts des eaux, pannes, etc.)
**Solution DisruptIQ**:
- Détection automatique urgences
- Génération listes d'actions procédurales
- Workflow automatisés (alertes, contacts professionnels)

### Problème #4: Conformité et Traçabilité
**Impact**: Risques juridiques, audits complexes
**Solution DisruptIQ**:
- Logs audit trail complets
- Historique décisions avec sources
- Chain of Thoughts transparents

---

## 👥 PERSONAS & USE CASES

### Persona 1: Julie - Syndic Indépendant
**Profile**:
- 35 ans, gère 15 copropriétés
- 150+ emails/jour
- Utilise Gmail + Excel + Papier
- Tech-savvy mais débordée

**Pain Points**:
- Noyée sous les emails
- Perd du temps à chercher infos
- Génère emails manuellement
- Oublie parfois des urgences

**Use Cases DisruptIQ**:
1. "Donne moi la liste des plombiers" → Réponse SQL instantanée
2. "Génère un digest des emails urgents" → Tri automatique
3. "Que faire en cas de dégât des eaux chez Mme Durant ?" → Action list + contacts
4. "Génère un email pour tous les copropriétaires" → Email contextuel

**Success Metrics**:
- -10h/semaine gagnées
- 0 urgence oubliée
- NPS 9+/10

### Persona 2: Marc - Cabinet Syndic 50+ Copropriétés
**Profile**:
- 45 ans, équipe de 5 personnes
- 500+ emails/jour
- Utilise logiciel métier legacy
- Besoin scalabilité + intégrations

**Pain Points**:
- Volume emails ingérable
- Onboarding nouveaux employés long
- Pas de vision consolidée
- Intégrations manuelles

**Use Cases DisruptIQ**:
1. Digest quotidien automatique → Priorisation intelligente
2. API publique → Intégration logiciel métier
3. Multi-tenant → Isolation par gestionnaire
4. Analytics dashboard → Vision 360° portefeuille

**Success Metrics**:
- +200% capacité traitement
- -50% temps onboarding
- ROI 10x en 6 mois

### Persona 3: Sophie - Conseil Syndical Bénévole
**Profile**:
- 52 ans, membre conseil syndical
- Non-tech, accès occasionnel
- Besoin simplicité + mobile

**Pain Points**:
- Interface complexe logiciels pros
- Pas d'accès mobile
- Informations opaques

**Use Cases DisruptIQ**:
1. Interface ChatGPT ultra-simple
2. Mobile app (iOS/Android)
3. Questions en langage naturel
4. Notifications push urgences

**Success Metrics**:
- Adoption 100% conseil syndical
- Satisfaction 9+/10
- 0 formation requise

---

## 🏗️ ARCHITECTURE TECHNIQUE

### Stack Actuel (v2.2)

#### Frontend
- **Framework**: React 18 + TypeScript + Vite
- **UI**: Shadcn/UI + Tailwind CSS
- **State**: React Query + Context API
- **Markdown**: react-markdown + remark-gfm
- **Router**: React Router v6
- **Build**: Vite (bundle <200 KB gzipped)

#### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Async**: asyncio + asyncpg
- **ORM**: SQLAlchemy 2.0 (async)
- **LLM**: OpenAI GPT-4 + Anthropic Claude (fallback)
- **Vector DB**: Qdrant (embeddings OpenAI)
- **Cache**: Redis
- **Task Queue**: Scheduler (APScheduler)

#### Infrastructure
- **Containers**: Docker Compose
- **DB**: PostgreSQL 15
- **Reverse Proxy**: Nginx (production)
- **Monitoring**: Structlog + Health endpoints

### Architecture Multi-Agents

```
┌────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                      │
│          (Intent Classification + Routing)                 │
└────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  SQL AGENT   │    │  RAG AGENT   │    │ EMAIL AGENT  │
│              │    │              │    │              │
│ Text-to-SQL  │    │ Vector       │    │ Generation   │
│ + Execute    │    │ Search       │    │ + Sending    │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │   Qdrant     │    │    Gmail     │
│              │    │              │    │  SMTP/OAuth  │
└──────────────┘    └──────────────┘    └──────────────┘

        Additional Agents:
        ├─ OCR Agent (Tesseract + PyPDF2)
        ├─ Digest Agent (Email classification)
        └─ Workflow Agent (N8N webhooks)
```

### Base de Données Schema

**Core Tables**:
```sql
-- Copropriétés (Buildings)
coproprietes (id, nom, adresse, ville, code_postal, nombre_lots, ...)

-- Copropriétaires (Residents)
coproprietaires (id, nom, prenom, email, copropriete_id, numero_lot, ...)

-- Professionnels (Service Providers)
professionnels (id, name, company_name, category, email, phone, rating, ...)

-- Emails
emails (id, message_id, sender, subject, body, urgency, received_at, ...)

-- Documents
documents (id, title, file_path, file_type, indexed_at, ...)
```

**Indexes Optimisés**:
- Composite indexes (copropriete_id + statut)
- Full-text search (title, description)
- Urgency + received_at (emails)

---

## 🚀 ROADMAP ACTUALISÉE - SOLUTION 100% FONCTIONNELLE

### ✅ Phase 0: État Actuel (v2.2) - COMPLÉTÉ

**Réalisations Récentes** (Nov 2-3, 2025):
- ✅ Markdown rendering (react-markdown + remarkGfm)
- ✅ Action lists RAG (détection procédurale + LLM formatting)
- ✅ Documentation digest hybrid architecture
- ✅ SQL Agent fast formatting (suppression appel LLM)
- ✅ Test data complètes (67 professionnels, 25 résidents, 29 emails)
- ✅ Frontend restart avec nouvelles features

**Stack Stable**:
- 7 agents fonctionnels
- Interface ChatGPT-style
- Chain of Thoughts temps réel (SSE)
- Multi-modal (texte + documents)

---

### 🔧 Phase 1: STABILITÉ & PRODUCTION-READY (2 semaines)
**Date**: 4-18 Novembre 2025
**Objectif**: Zero bugs critiques, production-grade

#### 1.1 - Corrections Critiques Prioritaires ⚠️

**Document Upload Functionality** (Urgent - Bloquant UX)
- [ ] Fix drag & drop upload in MainChatPage
- [ ] Implement file attachment button handler
- [ ] OCR Agent integration avec frontend
- [ ] Progress bar upload
- [ ] Error handling (file size, type, upload failed)

**Admin Panel SQL/RAG Management** (Urgent - Manque fonctionnalité clé)
- [ ] Right panel component pour données
- [ ] CRUD SQL tables (copropriétés, copropriétaires, professionnels)
- [ ] CRUD RAG documents (view, delete, re-index)
- [ ] Bulk operations (CSV import, delete multiple)
- [ ] Search & filters

**N8N Workflow Confirmations** (Important - Sécurité)
- [ ] Confirmation dialog avant exécution workflow
- [ ] Preview actions workflow
- [ ] Dry-run mode
- [ ] Rollback capability

**Complex SQL Queries** (Nice-to-have)
- [ ] Support INFORMATION_SCHEMA queries
- [ ] Schema introspection endpoint
- [ ] Query history & favorites

#### 1.2 - Sécurité 🔒

**SQL Injection Prevention**
- [ ] Whitelist tables autorisées (orchestrator + SQL agent)
- [ ] Validation paramètres utilisateur
- [ ] Sanitization inputs
- [ ] Rate limiting queries (100/hour)

**Upload Security**
- [ ] File type validation (PDF, DOCX, TXT, PNG, JPG uniquement)
- [ ] File size limits (25 MB max)
- [ ] Antivirus scan (ClamAV intégration)
- [ ] Rate limiting upload (10/hour)

**Production Hardening**
- [ ] SECRET_KEY validation stricte (.env.production)
- [ ] CORS whitelist domaines autorisés
- [ ] Error masking en production (pas de stack traces)
- [ ] HTTPS enforcement
- [ ] CSP headers

#### 1.3 - Tests & Qualité 🧪

**Backend Tests**
- [ ] Tests unitaires email_processor (90%+ coverage)
- [ ] Tests unitaires llm_service (85%+ coverage)
- [ ] Tests intégration RAG service (80%+ coverage)
- [ ] Tests intégration SQL agent (80%+ coverage)
- [ ] Tests orchestrator routing logic

**Frontend Tests**
- [ ] Tests E2E Playwright (user flows critiques)
  - Upload document → Query RAG
  - Ask SQL question → Get results
  - Generate email → Preview → Send
  - Generate digest → View by urgency
- [ ] Tests composants React (Vitest)
- [ ] Tests hooks custom

**Quality Gates**
- [ ] Coverage backend >80%
- [ ] Coverage frontend >60%
- [ ] 0 vulnérabilités critiques (npm audit / safety)
- [ ] Lighthouse score >85

#### 1.4 - Documentation 📚

**User Documentation**
- [ ] Quick start guide (5 min)
- [ ] FAQ (20+ questions)
- [ ] Video tutorials (3-5 use cases)
- [ ] Troubleshooting guide

**Developer Documentation**
- [ ] Architecture decision records (ADRs)
- [ ] API documentation complète (OpenAPI/Swagger)
- [ ] Contributing guide
- [ ] Code review checklist

**Cleanup**
- [ ] Supprimer fichiers obsolètes racine
- [ ] Organiser /docs/ structure
- [ ] README simplifié (focus utilisateur)
- [ ] CHANGELOG maintenu

#### Livrables Phase 1
- ✅ Upload documents fonctionnel
- ✅ Admin panel opérationnel
- ✅ Aucune vulnérabilité critique
- ✅ Tests coverage >70%
- ✅ Documentation complète
- ✅ Production deployment guide

---

### ⚡ Phase 2: SCALABILITÉ & PERFORMANCE (4 semaines)
**Date**: 18 Nov - 16 Déc 2025
**Objectif**: Supporter 10+ clients, 1000+ req/jour

#### 2.1 - Backend Performance 🚀

**Message Queue** (Celery + Redis)
- [ ] Installer Celery worker
- [ ] Tâches async: email classification, OCR, digest
- [ ] Retry logic + dead letter queue
- [ ] Monitoring tasks (Flower dashboard)

**Database Optimization**
- [ ] Connection pooling (asyncpg pool size 20)
- [ ] Query optimization (EXPLAIN ANALYZE)
- [ ] Pagination stricte partout (max 100 items)
- [ ] Database indexes review
- [ ] Read replicas (future multi-region)

**Circuit Breaker Pattern**
- [ ] LLM service circuit breaker (fallback si timeout)
- [ ] Gmail API circuit breaker (fallback cache)
- [ ] N8N webhooks circuit breaker (retry queue)
- [ ] Graceful degradation UI

**Caching Strategy**
- [ ] Cache notifications (Redis, TTL 5min)
- [ ] Cache stats dashboard (Redis, TTL 1h)
- [ ] Cache RAG searches (LRU cache, 1000 items)
- [ ] Cache SQL common queries

**Monitoring & Observability**
- [ ] Sentry error tracking
- [ ] DataDog/Prometheus metrics
- [ ] Structured logging partout
- [ ] APM (Application Performance Monitoring)
- [ ] Alerting (PagerDuty/Opsgenie)

#### 2.2 - Frontend Performance ⚡

**Code Splitting**
- [ ] React.lazy() pour pages (route-based splitting)
- [ ] Dynamic imports composants lourds
- [ ] Vendor chunking optimisé

**Bundle Optimization**
- [ ] Tree-shaking lucide-react (import icons individuellement)
- [ ] Remove unused dependencies
- [ ] Minimize bundle <150 KB gzipped

**Rendering Performance**
- [ ] Table virtualization (react-window) pour listes >100 items
- [ ] Memo/useMemo optimizations
- [ ] Debounce search inputs
- [ ] Lazy load images (react-lazy-load-image)

**PWA Features**
- [ ] Service worker (offline fallback)
- [ ] Cache static assets
- [ ] Manifest.json
- [ ] Add to home screen

#### 2.3 - UX/UI Enhancements 🎨

**Dark Mode**
- [ ] Tailwind dark mode (class strategy)
- [ ] Toggle component + persistence (localStorage)
- [ ] Dark mode preference sync

**Animations**
- [ ] Page transitions (framer-motion)
- [ ] Micro-interactions (button hover, loading states)
- [ ] Skeleton loaders partout

**Accessibility**
- [ ] WCAG AA compliance audit
- [ ] Keyboard navigation complète
- [ ] Screen reader optimization (ARIA labels)
- [ ] Focus management
- [ ] Color contrast >4.5:1

**Empty & Error States**
- [ ] Designs custom vides (illustrations)
- [ ] Error states explicites avec actions
- [ ] 404 page custom
- [ ] Offline state

#### Livrables Phase 2
- ✅ Backend scalable 1000+ req/jour
- ✅ Frontend Lighthouse >90
- ✅ Bundle <150 KB gzipped
- ✅ Dark mode + accessibilité WCAG AA
- ✅ Monitoring production complet
- ✅ Circuit breakers opérationnels

---

### 🏢 Phase 3: FEATURES ENTERPRISE (3 mois)
**Date**: Déc 2025 - Mars 2026
**Objectif**: Enterprise-ready, 30+ clients

#### 3.1 - Multi-Tenancy 🏗️

**Architecture**
- [ ] Tenant isolation DB (tenant_id partout)
- [ ] JWT avec tenant_id claim
- [ ] Middleware tenant resolution
- [ ] Tenant-specific config

**UI Branding**
- [ ] Logo personnalisable par tenant
- [ ] Couleurs thème custom
- [ ] Domain custom (client.disruptiq.fr)

**Data Isolation**
- [ ] Row-level security PostgreSQL
- [ ] Separate Qdrant collections par tenant
- [ ] Backup/restore par tenant

#### 3.2 - Nouvelles Features Majeures 🆕

**OCR Factures Avancé**
- [ ] Extraction champs structurés (montant, date, fournisseur)
- [ ] Validation comptable
- [ ] Export vers Sage/QuickBooks
- [ ] ML pour amélioration continue

**Analytics Dashboard**
- [ ] KPIs syndic (charges, incidents, entretien)
- [ ] Prédictions budget (ML forecasting)
- [ ] Comparaisons benchmarks secteur
- [ ] Exports PDF/Excel personnalisables

**Gestion Urgences Avancée**
- [ ] Workflow automatisé (détection → notification → suivi)
- [ ] Escalade automatique si pas de réponse
- [ ] SLA tracking par type urgence
- [ ] Historique incidents avec analytics

**API Publique RESTful**
- [ ] Documentation OpenAPI/Swagger interactive
- [ ] Rate limiting par API key (1000 req/hour)
- [ ] Webhooks sortants configurables
- [ ] SDK JavaScript + Python

#### 3.3 - Intégrations Tierces 🔗

**CRM**
- [ ] Salesforce
- [ ] HubSpot
- [ ] Pipedrive

**Comptabilité**
- [ ] Sage
- [ ] QuickBooks
- [ ] Xero

**Messagerie**
- [ ] Gmail (déjà fait)
- [ ] Outlook/Exchange
- [ ] Slack notifications

**Stockage**
- [ ] Google Drive
- [ ] Dropbox
- [ ] OneDrive

**Signature Électronique**
- [ ] DocuSign
- [ ] Adobe Sign

#### 3.4 - Sécurité & Compliance 🛡️

**Certifications**
- [ ] ISO 27001 preparation
- [ ] SOC 2 Type II audit
- [ ] GDPR advanced compliance

**Features Sécurité**
- [ ] 2FA/MFA (TOTP + SMS)
- [ ] SSO (SAML 2.0, OAuth 2.0)
- [ ] Logs audit trail complets (immutables)
- [ ] Droit à l'oubli GDPR
- [ ] Export données portabilité

**Backup & DR**
- [ ] Backup automatique quotidien
- [ ] Point-in-time recovery
- [ ] Disaster recovery plan
- [ ] RTO <1h, RPO <15min

#### Livrables Phase 3
- ✅ Multi-tenant production
- ✅ 5+ nouvelles features majeures
- ✅ API publique + SDK
- ✅ 10+ intégrations tierces
- ✅ Certifications sécurité en cours
- ✅ 30+ clients actifs

---

### 🚀 Phase 4: SCALE GLOBAL (6 mois)
**Date**: Mars - Sept 2026
**Objectif**: 100+ clients, expansion internationale

#### 4.1 - Infrastructure Scale 🌍

**Kubernetes Migration**
- [ ] Migration Docker Compose → Kubernetes
- [ ] Helm charts
- [ ] Horizontal pod autoscaling
- [ ] Load balancing
- [ ] Zero-downtime deployments

**Multi-Region**
- [ ] Déploiement EU (Francfort)
- [ ] Déploiement US (Virginie)
- [ ] Déploiement APAC (Tokyo) si besoin
- [ ] CDN global (CloudFront/Cloudflare)
- [ ] Latence <100ms mondiale

**Database Sharding**
- [ ] Sharding par tenant_id
- [ ] Read replicas multi-zones
- [ ] Automatic failover

#### 4.2 - Mobile App 📱

**React Native**
- [ ] iOS app (TestFlight)
- [ ] Android app (Play Store beta)
- [ ] Push notifications (Firebase)
- [ ] Offline mode + sync
- [ ] Scan QR codes équipements

#### 4.3 - IA Avancée 🧠

**Prédictive Analytics**
- [ ] Prédiction pannes équipements (ML)
- [ ] Optimisation budgets (forecasting)
- [ ] Détection fraudes automatique
- [ ] Scoring fournisseurs

**Génération Avancée**
- [ ] Documents juridiques (modèles)
- [ ] Résumés AG automatiques
- [ ] Chatbot vocal (téléphone)
- [ ] Vision ordinateur (photos dégâts)

#### 4.4 - Marketplace Workflows 🛒

**Store N8N**
- [ ] Templates workflows communautaires
- [ ] Ratings & reviews
- [ ] Monétisation workflows premium (10-50€/workflow)
- [ ] Analytics usage

#### Livrables Phase 4
- ✅ Infrastructure mondiale K8s
- ✅ Mobile app iOS + Android
- ✅ IA prédictive opérationnelle
- ✅ Marketplace workflows
- ✅ 100+ clients actifs
- ✅ 1.2M€ ARR

---

## 📊 MÉTRIQUES DE SUCCÈS

### KPIs Techniques

| Métrique | Actuel (v2.2) | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|---------------|---------|---------|---------|---------|
| **Uptime SLA** | N/A | 99% | 99.5% | 99.9% | 99.99% |
| **API p95 latency** | ~2s | <2s | <1s | <500ms | <200ms |
| **Frontend bundle** | 200KB | 180KB | 150KB | 130KB | 100KB |
| **Lighthouse score** | 75 | 85 | 90 | 95 | 100 |
| **Tests coverage** | 0% | 70% | 85% | 90% | 95% |
| **Vulnérabilités** | ? | 0 critical | 0 high | 0 | 0 |

### KPIs Produit

| Métrique | Actuel | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|--------|---------|---------|---------|---------|
| **Features core** | 10 | 12 | 15 | 25 | 40 |
| **Intégrations** | 2 (Gmail, N8N) | 3 | 5 | 15 | 25 |
| **Endpoints API** | 30 | 35 | 40 | 60 | 100+ |
| **Emails/jour** | 29 test | 100 | 500 | 2000 | 10000 |
| **Documents indexés** | 0 | 100 | 500 | 5000 | 50000 |

### KPIs Business

| Métrique | Actuel | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|--------|---------|---------|---------|---------|
| **Clients actifs** | 0 | 1 pilote | 5 | 30 | 100+ |
| **MRR** | 0€ | 500€ | 3k€ | 25k€ | 100k€+ |
| **ARR** | 0€ | 6k€ | 36k€ | 300k€ | 1.2M€+ |
| **NPS** | N/A | 8+ | 9+ | 9+ | 10 |
| **Churn** | N/A | 0% | <5% | <3% | <2% |
| **Team size** | 1-2 | 2 | 3 | 7 | 15 |

---

## 🎯 PRIORITÉS IMMÉDIATES (7 PROCHAINS JOURS)

### Jour 1-2: Upload Documents + Admin Panel
**Bloquant UX - Priorité MAX**
1. [ ] Fix drag & drop upload MainChatPage
2. [ ] Implémenter upload handler backend
3. [ ] OCR integration
4. [ ] Admin panel right sidebar (CRUD SQL)
5. [ ] Tests E2E upload flow

### Jour 3-4: Sécurité Critique
**Bloquant Production - Priorité MAX**
1. [ ] SQL tables whitelist
2. [ ] Upload file validation
3. [ ] Rate limiting
4. [ ] CORS configuration stricte
5. [ ] Error masking production

### Jour 5-6: Tests & Documentation
**Confiance Déploiement**
1. [ ] Tests email_processor
2. [ ] Tests llm_service
3. [ ] Tests E2E Playwright (3 flows)
4. [ ] Documentation API (Swagger)
5. [ ] Quick start guide utilisateur

### Jour 7: Release Candidate v2.3
1. [ ] Merge PRs
2. [ ] Tag v2.3-rc1
3. [ ] Deploy staging
4. [ ] Smoke tests
5. [ ] Go/No-Go decision

---

## 💰 MODÈLE ÉCONOMIQUE

### Pricing Tiers

**Starter** - 299€/mois
- 1 syndic
- 5 copropriétés max
- 1000 emails/mois
- 100 documents
- Support email 48h

**Professional** - 749€/mois (Most Popular)
- 1 syndic
- 20 copropriétés
- 5000 emails/mois
- 500 documents
- Support email 24h
- API access

**Enterprise** - Custom (1500€+/mois)
- Syndics illimités
- Copropriétés illimitées
- Emails illimités
- Documents illimités
- Support prioritaire <4h
- API + webhooks
- Multi-tenant
- White-label
- SLA 99.9%
- Custom intégrations

### Unit Economics (Professionnel)

**Revenue**:
- Prix: 749€/mois
- ARR: 8,988€

**Costs**:
- Infrastructure: ~150€/mois/client (DB, compute, storage)
- LLM API: ~100€/mois/client (5000 emails × 0.02€)
- Support: ~50€/mois/client (allocation temps)
- **Total COGS**: ~300€/mois

**Gross Margin**: 60% (449€/mois)

**CAC**: 2000€ (sales + marketing)
**LTV**: 20k€ (24 mois retention × 60% margin × 749€)
**LTV/CAC**: 10x ✅

---

## 🚨 RISQUES & MITIGATIONS

### Risques Techniques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Scalabilité DB** | Moyenne | Élevé | Sharding + read replicas Phase 3 |
| **LLM API costs explosion** | Élevée | Moyen | Circuit breaker + batch processing |
| **Gmail API rate limits** | Moyenne | Moyen | Hybrid cache + pagination |
| **Security breach** | Faible | Très élevé | Audits réguliers + penetration testing |
| **Data loss** | Faible | Très élevé | Backups 3-2-1 + DR plan |

### Risques Business

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Concurrence (Yooz, etc.)** | Élevée | Élevé | Time-to-market + differentiation IA |
| **Adoption lente IA** | Moyenne | Élevé | UX ultra-simple + onboarding guidé |
| **Churn élevé** | Moyenne | Élevé | Customer success proactif + NPS tracking |
| **Funding gap** | Faible | Moyen | Bootstrap + profitabilité rapide |

### Risques Produit

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Complexité features** | Élevée | Moyen | User research + MVP approach |
| **Tech debt** | Moyenne | Moyen | Refactoring continu + reviews |
| **Bugs critiques** | Moyenne | Élevé | Tests automatisés + staging env |

---

## 📝 ANNEXES

### Technologies Considérées (Rejected)

**Pourquoi pas LangChain ?**
- Trop abstrait, difficile à débugger
- Préférence: logique custom orchestrator

**Pourquoi pas Vercel AI SDK ?**
- Lock-in vendor
- Préférence: OpenAI SDK direct

**Pourquoi pas Supabase ?**
- Besoin contrôle infrastructure
- Préférence: PostgreSQL self-hosted

### Références

- **Multi-Agent Systems**: AutoGPT, SuperAGI, BabyAGI
- **RAG Architecture**: LlamaIndex docs, Pinecone guides
- **FastAPI Best Practices**: Sebastián Ramírez (creator)
- **React Performance**: Web.dev Performance guides

---

*Document vivant - Dernière mise à jour: 3 Novembre 2025*
*Version: 2.2*
*Prochaine révision: 18 Novembre 2025 (post-Phase 1)*
