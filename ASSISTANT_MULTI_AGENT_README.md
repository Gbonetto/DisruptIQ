# 🤖 Assistant Multi-Agent DisruptIQ

## Vue d'ensemble

L'assistant multi-agent est un système intelligent orchestré qui route automatiquement les requêtes utilisateur vers les agents spécialisés appropriés.

## Architecture

```
User Query → Orchestrator Agent → Specialized Agents → Response
```

### Agents Disponibles

1. **Orchestrator Agent** (Cerveau)
   - Classifie les intentions utilisateur
   - Route vers les bons agents
   - Coordonne les workflows multi-agents

2. **SQL Agent**
   - Text-to-SQL intelligent
   - Requêtes sur copropriétaires, copropriétés, vendors
   - Formatage des résultats en langage naturel

3. **Email Agent**
   - Génération d'emails personnalisés
   - Adaptation du ton (urgent, professionnel, amical)
   - Support des templates

4. **Template Agent**
   - Bibliothèque de templates prédéfinis
   - Remplissage dynamique de variables
   - Génération de templates avec LLM

5. **Workflow Agent**
   - Déclenchement de workflows N8N
   - Passage de données contextuelles
   - Gestion des webhooks

## API Endpoints

### POST `/api/assistant-v2/chat`

Endpoint principal pour interagir avec l'assistant.

**Request:**
```json
{
  "message": "Envoyer email aux copropriétaires pour dégât des eaux",
  "conversation_history": [],
  "session_id": "optional-session-id",
  "context": {}
}
```

**Response:**
```json
{
  "success": true,
  "message": "J'ai généré un brouillon d'email pour 45 destinataires...",
  "data": {
    "email_draft": {...},
    "workflow_result": {...}
  },
  "agents_used": ["email_agent", "workflow_agent"],
  "suggestions": [
    "Voulez-vous modifier le brouillon?",
    "Dois-je l'envoyer maintenant?"
  ],
  "session_id": "session-123"
}
```

### GET `/api/assistant-v2/capabilities`

Liste toutes les capacités de l'assistant.

### GET `/api/assistant-v2/templates`

Liste tous les templates disponibles.

## Exemples d'utilisation

### 1. Requête SQL

```
User: "Combien de copropriétaires dans l'Immeuble A?"

Flow:
1. Orchestrator classifie: query_data
2. Route vers SQL Agent
3. SQL Agent génère: SELECT COUNT(*) FROM coproprietaires WHERE copropriete_id = ...
4. Exécute la requête
5. Formate: "L'Immeuble A compte 23 copropriétaires."
```

### 2. Email d'urgence

```
User: "Envoyer email urgent pour dégât des eaux Immeuble B"

Flow:
1. Orchestrator classifie: send_email
2. SQL Agent: Récupère copropriétaires Immeuble B
3. RAG Agent: Cherche procédure dégât des eaux
4. Template Agent: Template "alerte_urgence"
5. Email Agent: Génère emails personnalisés
6. Workflow Agent: Déclenche N8N → Crée brouillons Gmail

Response: "✅ 32 brouillons créés dans Gmail"
```

### 3. Demande de devis

```
User: "Demander devis à tous les jardiniers pour taille des haies"

Flow:
1. Orchestrator classifie: request_quotes
2. SQL Agent: SELECT * FROM vendors WHERE category='Jardinier'
3. Template Agent: Remplit template "demande_devis"
4. Workflow Agent: Déclenche N8N "bulk_devis_request"

Response: "✅ Demande envoyée à 5 jardiniers"
```

## Configuration

### Variables d'environnement (.env)

```env
# N8N Webhooks
N8N_WEBHOOK_BASE_URL=https://your-n8n-instance.com
N8N_WEBHOOK_AUTH_TOKEN=your-secret-token
N8N_TIMEOUT=30
N8N_MAX_RETRIES=3

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

### Workflows N8N requis

1. **create-gmail-draft**: Crée brouillons Gmail
2. **bulk-devis-request**: Envoie demandes de devis
3. **emergency-sms-email**: Alertes urgentes
4. **ocr-classify-store**: Traitement documents

## Tests

### Lancer les tests

```bash
# Backend doit être running
docker-compose up -d backend

# Lancer les tests
python test_assistant_v2.py
```

### Test manuel avec curl

```bash
# Test capabilities
curl http://localhost:8000/api/assistant-v2/capabilities

# Test chat
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Combien de copropriétaires avons-nous?",
    "conversation_history": []
  }'
```

## Prochaines étapes

### À implémenter

1. **OCR Agent** (analyse factures, contrats)
2. **Historique des conversations** (persistance DB)
3. **Streaming responses** (Server-Sent Events)
4. **Voice input** (Whisper API)
5. **Multi-modal** (images, PDFs)

### Améliorations futures

- Cache intelligent (Redis)
- Rate limiting par user
- Analytics & monitoring
- Fine-tuning du LLM pour le contexte syndic
- Templates personnalisables par utilisateur

## Troubleshooting

### L'assistant ne répond pas

1. Vérifier que le backend est démarré
2. Vérifier les logs: `docker-compose logs backend`
3. Vérifier la clé OpenAI dans `.env`

### N8N workflows ne se déclenchent pas

1. Vérifier `N8N_WEBHOOK_BASE_URL` dans `.env`
2. Vérifier que les workflows N8N sont actifs
3. Vérifier les logs: `docker-compose logs backend | grep workflow`

### Erreurs SQL

1. Vérifier la connexion DB: `docker-compose ps postgres`
2. Les requêtes SQL sont validées pour la sécurité
3. Seuls les SELECT sont autorisés

## Support

Pour toute question ou problème, consulter:
- Logs backend: `docker-compose logs -f backend`
- API docs: http://localhost:8000/api/docs
- Tests: `python test_assistant_v2.py`
