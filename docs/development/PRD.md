# DisruptIQ - PRD V2 Complete
## Product Requirements Document - Solution RAG-SMA pour Syndics

**Version**: 2.0  
**Date**: Octobre 2024  
**Statut**: Prêt pour implémentation Claude Code

---

## 🎯 EXECUTIVE SUMMARY

### Vision Produit
**DisruptIQ** - L'assistant IA qui automatise 80% du travail administratif des syndics de copropriété.

### Proposition de Valeur
- **Pour qui**: Syndics de copropriété (10 000+ en France)
- **Problème**: Surcharge administrative, gestion manuelle des urgences, recherche fastidieuse dans les documents
- **Solution**: Système RAG multi-agents avec intégration N8N native
- **Résultat**: 10-15h économisées par semaine, ROI en 2 mois

### Différenciateurs Clés
1. **Souveraineté des données** - Déploiement on-premise/VPS client
2. **Automation native N8N** - Pas juste du chat, mais des actions concrètes
3. **Architecture évolutive** - Base solide, amélioration continue

---

## 📊 STRATÉGIE PRODUIT

### Approche de Développement
```
Phase 1 (V1.0) - MVP Quick Win [2-3 semaines]
├─ Smart Digest emails quotidien
├─ Générateur emails professionnels  
└─ Intégration N8N sortante

Phase 2 (V1.5) - Production Ready [Semaines 4-6]
├─ OCR factures + extraction
├─ Multi-agents (3 agents)
├─ Webhooks bidirectionnels N8N
└─ Interface admin complète

Phase 3 (V2.0) - Scale & Polish [Semaines 7-12]
├─ BDD relationnelles complètes
├─ Gestion urgences avancée
├─ Analytics & reporting
└─ Multi-tenant SaaS
```

### Marché Cible
- **Initial**: Syndics 5-20 copropriétés
- **Expansion**: Cabinets juridiques, experts-comptables
- **Pricing**: 499€/mois (Essential) → 1499€/mois (Pro)

---

## 🏗️ ARCHITECTURE TECHNIQUE

### Stack Technique V1
```yaml
Backend:
  - Framework: FastAPI 0.115+ (Python 3.11)
  - LLM Orchestration: LangChain 0.2+
  - Vector DB: Qdrant 1.9+ (hybrid search)
  - Database: PostgreSQL 15 (métadonnées)
  - Cache/Queue: Redis 7+
  - OCR: Tesseract + pytesseract (V1.5)
  
Frontend:
  - Framework: React 18 + Vite 5
  - UI Library: Shadcn/ui + Tailwind CSS
  - State: Zustand 4+
  - Icons: Lucide React
  
Infrastructure:
  - Container: Docker + Docker Compose
  - Reverse Proxy: Nginx
  - SSL: Let's Encrypt
  - Monitoring: Logs JSON → stdout

LLM Providers:
  - Primary: OpenAI GPT-4-turbo
  - Fallback: Claude 3 Opus
  - Local Option: Ollama (V2)
```

### Architecture Système
```
┌─────────────────────────────────────────────┐
│            DisruptIQ Frontend               │
│  ┌─────────┬─────────┬─────────────────┐  │
│  │Dashboard│  Chat   │     Admin       │  │
│  └─────────┴─────────┴─────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────┐
│            FastAPI Backend                  │
│  ┌─────────────────────────────────────┐  │
│  │   Core Services                      │  │
│  ├─────────────────────────────────────┤  │
│  │ • Email Processor (IMAP/Gmail API)  │  │
│  │ • Document Ingestion (PDF/DOCX)     │  │
│  │ • LLM Service (Chain Management)    │  │
│  │ • Webhook Service (N8N Integration) │  │
│  └─────────────────────────────────────┘  │
└──────────┬────────────┬─────────────────────┘
           │            │
    ┌──────▼─────┐ ┌───▼────┐  ┌─────────┐
    │  Qdrant    │ │  PG    │  │   N8N   │
    │ (Vectors)  │ │ (Meta) │  │(Actions)│
    └────────────┘ └────────┘  └─────────┘
```

---

## 🔧 FONCTIONNALITÉS DÉTAILLÉES V1

### Use Case 1: Smart Digest Quotidien
```typescript
interface SmartDigest {
  // Entrée
  emails: Email[];          // Via IMAP/Gmail API
  attachments: File[];      // PDF, images
  
  // Traitement
  classification: {
    urgent: Email[];        // 🔴 Dégâts, incidents
    important: Email[];     // 🟠 Devis, relances
    routine: Email[];       // 🟢 Info, confirmations
  };
  
  // Sortie
  digest: {
    format: "HTML";
    delivery: "8:00 AM daily";
    actions: Action[];      // Boutons N8N intégrés
  };
}
```

**Implémentation Backend**:
```python
# services/email_processor.py
class EmailProcessor:
    async def process_daily_emails(self):
        # 1. Récupération emails
        emails = await self.gmail_service.fetch_unread()
        
        # 2. Classification par LLM
        classified = await self.llm_service.classify_urgency(
            emails,
            few_shot_examples=SYNDIC_EXAMPLES
        )
        
        # 3. Extraction PJ importantes
        attachments = await self.extract_key_attachments(emails)
        
        # 4. Génération digest HTML
        digest = await self.generate_digest(
            classified, 
            attachments
        )
        
        # 5. Envoi email
        await self.send_digest(digest)
        
        # 6. Log analytics
        await self.analytics.log_digest(classified)
```

### Use Case 2: Générateur Emails Professionnels
```python
# api/endpoints/email_generator.py
@router.post("/generate-email")
async def generate_email(request: EmailRequest):
    # 1. Comprendre le besoin
    intent = await llm_service.extract_intent(request.prompt)
    
    # 2. Rechercher destinataires
    if intent.needs_vendors:
        vendors = await db.search_vendors(intent.vendor_type)
    
    # 3. Générer email
    email_content = await llm_service.generate_email(
        intent=intent,
        context={
            "property_address": intent.address,
            "budget": intent.budget,
            "timeline": intent.timeline
        },
        tone="professional"
    )
    
    # 4. Préparer réponse
    return {
        "draft": email_content,
        "recipients": [v.email for v in vendors],
        "n8n_action": {
            "available": True,
            "webhook_id": "send_vendor_emails"
        }
    }
```

---

## 🎨 UX/UI SPECIFICATIONS

### Design System
```scss
// Tokens de design
$colors: (
  danger: #EF4444,    // Urgences
  warning: #F59E0B,   // Important  
  success: #10B981,   // Routine
  primary: #3B82F6,   // Actions
  neutral: #64748B,   // Secondaire
);

$typography: (
  font-family: 'Inter',
  sizes: (
    h1: 2rem,
    h2: 1.5rem,
    body: 1rem,
    small: 0.875rem
  )
);

$spacing: (
  xs: 0.25rem,
  sm: 0.5rem,
  md: 1rem,
  lg: 1.5rem,
  xl: 2rem
);
```

### Composants Clés (Shadcn/ui)
```tsx
// components/EmailCard.tsx
import { Card, CardHeader, CardContent, CardFooter } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export function EmailCard({ email, urgency }) {
  const urgencyColors = {
    urgent: "destructive",
    important: "warning",
    routine: "default"
  };

  return (
    <Card className="hover:shadow-lg transition-all">
      <CardHeader>
        <div className="flex justify-between items-start">
          <Badge variant={urgencyColors[urgency]}>
            {urgency === 'urgent' && '🔴'} 
            {urgency === 'important' && '🟠'}
            {urgency === 'routine' && '🟢'}
            {email.subject}
          </Badge>
          <span className="text-sm text-muted-foreground">
            {email.timeAgo}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm">{email.preview}</p>
        {email.attachments?.length > 0 && (
          <div className="flex gap-2 mt-2">
            {email.attachments.map(att => (
              <Badge variant="outline" key={att.id}>
                📎 {att.name}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
      <CardFooter className="gap-2">
        {email.actions?.map(action => (
          <Button 
            key={action.id}
            size="sm"
            onClick={() => triggerN8N(action)}
          >
            {action.label}
          </Button>
        ))}
      </CardFooter>
    </Card>
  );
}
```

### Wireframes Principaux
```
1. Dashboard (Mobile First)
┌──────────────────────┐
│  DisruptIQ      🔔3  │
├──────────────────────┤
│                      │
│ 📅 Jeudi 31 Oct      │
│                      │
│ ┌──────────────────┐ │
│ │ 🔴 URGENCES (3)  │ │
│ └──────────────────┘ │
│                      │
│ [Card Urgence 1]     │
│ ├─ Swipe → Archive   │
│ └─ Tap → Actions     │
│                      │
│ [Card Urgence 2]     │
│                      │
│ ▼ Plus d'urgences    │
│                      │
│ ┌──────────────────┐ │
│ │ 🟠 IMPORTANT (5) │ │
│ └──────────────────┘ │
│                      │
└──────────────────────┘

2. Chat Interface
┌──────────────────────┐
│ 💬 Assistant         │
├──────────────────────┤
│                      │
│ [Historique chat]    │
│                      │
│ ┌──────────────────┐ │
│ │ Votre message... │ │
│ └──────────────────┘ │
│        [Envoyer →]   │
│                      │
│ Suggestions:         │
│ • Devis ravalement   │
│ • Email AG           │
│ • Urgence plombier   │
└──────────────────────┘
```

---

## 🔗 INTÉGRATION N8N

### Webhooks V1 (Sortants)
```yaml
Workflows fournis:
  1. notify_neighbors:
     trigger: DisruptIQ webhook
     actions:
       - Recherche contacts voisins
       - Envoi emails personnalisés
       - Log Google Sheets
       - SMS confirmation syndic
       
  2. send_vendor_emails:
     trigger: DisruptIQ webhook
     actions:
       - Parse liste fournisseurs
       - Personnalisation emails
       - Envoi batch Gmail
       - Tracking ouvertures
       
  3. archive_documents:
     trigger: DisruptIQ webhook
     actions:
       - Upload Google Drive
       - Tagging automatique
       - Notification Slack
```

### Configuration N8N
```python
# config/n8n_settings.py
N8N_CONFIG = {
    "base_url": os.getenv("N8N_WEBHOOK_URL"),
    "api_key": os.getenv("N8N_API_KEY"),
    "timeout": 30,
    "retry": 3,
    "workflows": {
        "notify_neighbors": {
            "endpoint": "/webhook/notify-neighbors",
            "method": "POST",
            "headers": {"Content-Type": "application/json"}
        },
        "send_vendor_emails": {
            "endpoint": "/webhook/send-vendor-emails",
            "method": "POST"
        }
    }
}
```

### Sécurité
```python
# services/webhook_service.py
import hmac
import hashlib

class WebhookService:
    def sign_payload(self, payload: dict) -> str:
        """Signe le payload avec HMAC-SHA256"""
        message = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def send_to_n8n(self, workflow: str, data: dict):
        """Envoie sécurisé vers N8N avec retry"""
        signature = self.sign_payload(data)
        
        for attempt in range(self.max_retries):
            try:
                response = await self.http_client.post(
                    f"{self.base_url}/{workflow}",
                    json=data,
                    headers={
                        "X-Signature": signature,
                        "X-Timestamp": str(time.time())
                    },
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                    
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
```

---

## 📱 RESPONSIVE DESIGN

### Breakpoints
```css
/* Mobile First Approach */
/* Mobile: 320px - 768px */
@media (max-width: 768px) {
  .container { padding: 1rem; }
  .card-grid { grid-template-columns: 1fr; }
  .sidebar { display: none; }
}

/* Tablet: 768px - 1024px */
@media (min-width: 768px) {
  .container { padding: 2rem; }
  .card-grid { grid-template-columns: repeat(2, 1fr); }
  .sidebar { width: 240px; }
}

/* Desktop: 1024px+ */
@media (min-width: 1024px) {
  .container { max-width: 1200px; }
  .card-grid { grid-template-columns: repeat(3, 1fr); }
  .sidebar { width: 280px; }
}
```

---

## 🚀 DÉPLOIEMENT

### Configuration Docker
```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/disruptiq
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - N8N_WEBHOOK_URL=${N8N_WEBHOOK_URL}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - qdrant
      
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://backend:8000
      
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=disruptiq
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
      
  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
      
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

### Script d'Installation
```bash
#!/bin/bash
# install.sh - Installation automatisée DisruptIQ

echo "🚀 Installation DisruptIQ pour Syndic"

# 1. Vérification prérequis
command -v docker >/dev/null 2>&1 || { 
    echo "❌ Docker requis. Installation..."; 
    curl -fsSL https://get.docker.com | sh
}

# 2. Clone repository
git clone https://github.com/your-org/disruptiq.git
cd disruptiq

# 3. Configuration
cp .env.example .env
echo "📝 Configurez vos clés API dans .env"
read -p "Appuyez sur Enter quand prêt..."

# 4. Build et lancement
docker-compose up -d

# 5. Initialisation BDD
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py init_vectors

# 6. Test santé
curl http://localhost:8000/health

echo "✅ DisruptIQ installé sur http://localhost"
echo "📧 Le premier digest sera envoyé demain 8h"
```

---

## 📊 MÉTRIQUES DE SUCCÈS

### KPIs V1 (2 semaines)
```yaml
Techniques:
  - Uptime: > 99%
  - Temps réponse API: < 2s (p95)
  - Taux classification emails: > 85% précision
  - Génération email: < 5s
  
Business:
  - 1 syndic pilote déployé
  - 50+ emails traités/jour
  - 20+ emails générés/semaine
  - NPS: > 8/10
  
Usage:
  - Adoption: 100% équipe syndic
  - Actions N8N déclenchées: > 10/jour
  - Temps économisé: > 1h/jour
```

### Roadmap Post-V1
```
V1.5 (Mois 2):
  ✓ OCR factures avancé
  ✓ 3 agents spécialisés
  ✓ BDD relationnelles
  ✓ Webhooks bidirectionnels
  → Objectif: 3 clients payants

V2.0 (Mois 3):
  ✓ Multi-tenant
  ✓ Analytics dashboard
  ✓ API publique
  ✓ Intégrations CRM
  → Objectif: 10 clients, 25k€ MRR

V3.0 (Mois 6):
  ✓ SaaS self-service
  ✓ Marketplace workflows
  ✓ Mobile app
  ✓ IA prédictive
  → Objectif: 50 clients, 100k€ MRR
```

---

## 💰 MODÈLE ÉCONOMIQUE

### Pricing
```
Essential (499€/mois):
  - 1 syndic utilisateur
  - 500 documents
  - 1000 requêtes/mois
  - Smart Digest quotidien
  - 3 workflows N8N
  
Professional (999€/mois):
  - 5 utilisateurs
  - 5000 documents
  - Requêtes illimitées
  - Multi-agents
  - 10 workflows custom
  - Support prioritaire
  
Enterprise (Sur devis):
  - Utilisateurs illimités
  - Multi-tenant
  - SLA 99.9%
  - Formation équipe
  - Workflows illimités
  - API dédiée
  
Setup: 799€ (installation + formation 2h)
```

---

## 🔒 SÉCURITÉ & COMPLIANCE

### RGPD & Souveraineté
```yaml
Principes:
  - Données hébergées en France (OVH/Scaleway)
  - Aucune donnée envoyée aux LLM (sauf prompts)
  - Encryption at rest (AES-256)
  - Encryption in transit (TLS 1.3)
  - Logs anonymisés
  - Droit à l'oubli implémenté
  
Certifications cibles:
  - ISO 27001 (Année 2)
  - SOC 2 Type II (Année 2)
  - HDS (si expansion santé)
```

---

## 📝 INSTRUCTIONS POUR CLAUDE CODE

### Prompt Optimal
```markdown
Créez DisruptIQ, un système RAG multi-agents pour syndics de copropriété avec:

**Architecture**:
- Backend: FastAPI + LangChain + Qdrant + PostgreSQL
- Frontend: React + Vite + Shadcn/ui + Tailwind
- Intégration: Webhooks N8N natifs
- Déploiement: Docker Compose

**Fonctionnalités V1**:
1. Smart Digest emails quotidien (IMAP/Gmail API)
2. Générateur emails avec recherche fournisseurs
3. Chat interface avec actions N8N intégrées
4. Upload/indexation documents (PDF, DOCX)

**Structure projet**:
```
disruptiq/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── models/
│   │   └── core/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── lib/
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

**Priorités**:
1. Code production-ready avec gestion erreurs
2. UI/UX intuitive pour non-tech users
3. Tests unitaires critiques
4. Documentation API complète
5. Script installation one-click
```

### Checklist Pré-développement
- [ ] Valider accès Gmail API du syndic
- [ ] Obtenir fichier Excel fournisseurs
- [ ] Confirmer URL N8N instance
- [ ] Définir VPS cible (specs min: 4GB RAM, 2 CPU)
- [ ] Backup clés API (OpenAI, etc.)

---

## 📞 SUPPORT & CONTACT

**Équipe Projet**:
- Product Owner: [Votre nom]
- Tech Lead: Claude Code
- Client Pilote: [Syndic contact]

**Resources**:
- Documentation: `/docs`
- Support: support@disruptiq.ai
- Urgences: +33 X XX XX XX XX

---

*Ce document est la base de travail pour le développement avec Claude Code. Il sera mis à jour itérativement selon les retours du pilote.*
