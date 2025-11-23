# N8N Integration for DisruptIQ

## Overview

N8N is integrated into DisruptIQ as a **workflow automation orchestration layer**. It enables sophisticated automation workflows triggered by the DisruptIQ Multi-Agent System (SMA-RAG).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ NIVEAU 1: ORCHESTRATOR AGENT                                │
│ → Analyzes user intent                                       │
│ → Routes to specialized agents                               │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ NIVEAU 2: WORKFLOW AGENT                                     │
│ → Classifies workflow family (COMMUNICATION, URGENCE, etc.)  │
│ → Prepares standardized payload                              │
│ → Sends to N8N with thought_stream_id                        │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ NIVEAU 3: N8N WORKFLOWS                                      │
│ → Executes automation (email, SMS, API calls)                │
│ → Sends real-time updates back to DisruptIQ ThoughtStream    │
│ → Returns final execution results                            │
└─────────────────────────────────────────────────────────────┘
```

## Access

- **Web UI**: http://localhost:5678
- **Credentials**:
  - Username: `admin` (configurable in `.env`)
  - Password: `disruptiq_n8n_2024` (configurable in `.env`)

## Configuration

### Environment Variables

Located in root `.env` file:

```env
# N8N Webhooks (from DisruptIQ → N8N)
N8N_WEBHOOK_BASE_URL=http://n8n:5678
N8N_WEBHOOK_AUTH_TOKEN=disruptiq_n8n_webhook_secret_2024_secure_token
N8N_TIMEOUT=30
N8N_MAX_RETRIES=3

# N8N Basic Auth (for Web UI access)
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=disruptiq_n8n_2024
```

### Docker Configuration

N8N runs as a service in `docker-compose.yml`:

```yaml
n8n:
  image: n8nio/n8n:latest
  container_name: disruptiq_n8n
  environment:
    # Uses PostgreSQL for persistence
    DB_TYPE: postgresdb
    DB_POSTGRESDB_DATABASE: n8n
    # Timezone: Europe/Paris
    GENERIC_TIMEZONE: Europe/Paris
  volumes:
    - n8n_data:/home/node/.n8n
    - ./n8n/workflows:/home/node/.n8n/workflows
  ports:
    - "5678:5678"
```

## Workflow Families

DisruptIQ organizes workflows into 4 main families:

### 1. COMMUNICATION
**Intent**: `SEND_EMAIL`
**Workflows**:
- Email to individual tenant
- Email to building residents
- Email to syndic professionals

### 2. URGENCE (Emergency)
**Intent**: `TRIGGER_WORKFLOW`
**Workflows**:
- Water leak emergency
- Fire detection alert
- Building lockdown protocol

### 3. GESTION (Management)
**Intent**: `TRIGGER_WORKFLOW`
**Workflows**:
- Cotisation payment reminder
- Document collection request
- AG meeting preparation

### 4. DIGEST
**Intent**: `SCHEDULE_ACTION`
**Workflows**:
- Daily syndic digest
- Weekly building report
- Monthly financial summary

## Workflow Development

### 1. Workflow Template Structure

Each workflow should:

1. **Start with Webhook node** - Receives payload from DisruptIQ
2. **Authenticate** - Verify `DISRUPTIQ_WEBHOOK_TOKEN`
3. **Extract data** - Parse standardized payload
4. **Send progress updates** - POST to DisruptIQ callback endpoint
5. **Execute automation** - Email, SMS, API calls, etc.
6. **Send final result** - POST completion status to DisruptIQ

### 2. Standardized Payload Format

DisruptIQ sends this structure to N8N webhooks:

```json
{
  "action": "emergency_water_leak",
  "tenant_id": "syndic_ABC",
  "user_id": "user_123",
  "urgency": "critical",
  "context": {
    "building_id": "copro_A",
    "floor": 3,
    "apartment": {
      "number": "3B",
      "owner": "M. Dupont",
      "phone": "+33612345678"
    },
    "professional": {
      "type": "plumber",
      "name": "SOS Plomberie",
      "phone": "+33612345679"
    }
  },
  "data": {
    "description": "Fuite d'eau importante au niveau du ballon d'eau chaude",
    "photos": ["https://..."]
  },
  "trace": {
    "conversation_id": "conv_123",
    "request_id": "req_456",
    "thought_stream_id": "stream_xyz"
  }
}
```

### 3. Callback to DisruptIQ

N8N workflows can send real-time updates to DisruptIQ:

**Endpoint**: `http://backend:8000/api/n8n/callback`

**Method**: `POST`

**Headers**:
```json
{
  "Authorization": "Bearer disruptiq_n8n_webhook_secret_2024_secure_token",
  "Content-Type": "application/json"
}
```

**Payload**:
```json
{
  "thought_stream_id": "stream_xyz",
  "thought_type": "EXECUTING",
  "title": "Envoi email à M. Dupont",
  "content": "Email envoyé avec succès à +33612345678",
  "agent": "N8N_WaterLeak",
  "progress": 0.5,
  "metadata": {
    "email_sent": true,
    "recipient": "dupont@example.com"
  }
}
```

## Development Workflow

### 1. Create New Workflow in N8N UI

1. Access http://localhost:5678
2. Create new workflow
3. Add "Webhook" trigger node
4. Configure webhook path (e.g., `/webhook/water-leak`)
5. Add authentication check
6. Build automation logic
7. Add DisruptIQ callback nodes
8. Test thoroughly
9. Activate workflow

### 2. Export Workflow

```bash
# Export from N8N UI as JSON
# Save to: n8n/workflows/water_leak_emergency.json
```

### 3. Register in WorkflowAgent

Update `backend/app/services/agents/workflow_agent.py` to recognize the new workflow.

## Priority Workflows (Sprint 0-1)

Based on SPECIFICATION_N8N_INTEGRATION.md, implement these 10 workflows first:

**COMMUNICATION**:
1. Email to tenant
2. Email to building residents
3. Email to professionals

**URGENCE**:
4. Water leak emergency
5. Fire detection alert

**GESTION**:
6. Cotisation reminder
7. Document collection
8. AG meeting preparation

**DIGEST**:
9. Daily syndic digest
10. Weekly building report

## Monitoring & Debugging

### Check N8N Logs
```bash
docker logs disruptiq_n8n -f
```

### Check Workflow Execution History
Access N8N UI → Executions tab

### Test Webhook Manually
```bash
curl -X POST http://localhost:5678/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

### Verify Connectivity from Backend
```bash
docker exec disruptiq_backend python -c \
  "import requests; print(requests.get('http://n8n:5678/healthz').json())"
```

## Database

N8N uses PostgreSQL for persistence:
- **Database**: `n8n`
- **Host**: `postgres:5432`
- **User**: `disruptiq`
- **Credentials**: Same as DisruptIQ main database

All workflows, executions, and credentials are stored persistently.

## Security

1. **Authentication**: All webhooks must validate `N8N_WEBHOOK_AUTH_TOKEN`
2. **Network Isolation**: N8N is only accessible within Docker network + localhost
3. **Basic Auth**: Web UI protected with username/password
4. **Credentials**: Sensitive data stored encrypted in PostgreSQL

## Resources

- N8N Documentation: https://docs.n8n.io/
- DisruptIQ N8N Specification: `SPECIFICATION_N8N_INTEGRATION.md`
- Workflow Examples: `n8n/workflows/`

## Troubleshooting

### N8N won't start
```bash
# Check logs
docker logs disruptiq_n8n

# Verify PostgreSQL is running
docker ps | grep postgres

# Verify database exists
docker exec disruptiq_postgres psql -U disruptiq -c "\l" | grep n8n
```

### Workflows not triggering
1. Check webhook URL is correct in WorkflowAgent
2. Verify workflow is activated in N8N UI
3. Check authentication token matches
4. Review N8N execution logs

### Database connection issues
```bash
# Test connection
docker exec disruptiq_n8n env | grep DB_POSTGRES

# Recreate container
docker-compose up -d n8n
```

---

**Version**: 1.0.0
**Last Updated**: 2025-11-23
**Maintainer**: DisruptIQ Development Team
