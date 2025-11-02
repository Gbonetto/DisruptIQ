# Email Digest Architecture - Hybrid Gmail + Database

## Overview

The DisruptIQ email digest system implements a **hybrid architecture** that combines real-time Gmail API fetching with local database caching for maximum resilience and offline capability.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  POST /api/digest/generate                                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 1: Gmail API Fetch (60s timeout)                 │ │
│  │  - OAuth2 authentication                              │ │
│  │  - Fetch unread emails from last N hours             │ │
│  │  - Timeout protection prevents hanging               │ │
│  └───────────────────────────────────────────────────────┘ │
│                           │                                 │
│                           ▼                                 │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 2: LLM Classification (90s timeout)              │ │
│  │  - Parallel processing of emails                      │ │
│  │  - Classify: URGENT, IMPORTANT, ROUTINE               │ │
│  │  - Semantic analysis of subject + body                │ │
│  └───────────────────────────────────────────────────────┘ │
│                           │                                 │
│                           ▼                                 │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 3: Database Persistence (bulk insert)            │ │
│  │  - Store in `emails` table                            │ │
│  │  - Cache for offline access                           │ │
│  │  - Enable historical queries                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                           │                                 │
│                           ▼                                 │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Step 4: Generate Digest from DB (always succeeds)     │ │
│  │  - Query cached/fresh emails                          │ │
│  │  - Group by urgency                                   │ │
│  │  - Return structured digest                           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  If Gmail fails → Fallback to database cache              │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Gmail API Integration

**File:** `backend/app/services/email_processor.py`

**Responsibilities:**
- OAuth2 authentication and token management
- Fetch unread emails from Gmail
- Automatic token refresh
- Retry logic with exponential backoff
- Base64 email decoding

**Key Methods:**
- `fetch_unread_emails(since_hours, max_results)` - Main fetch function
- `classify_emails(emails)` - LLM-based classification
- `_authenticate()` - OAuth2 flow
- `_get_email_message(message_id)` - Fetch single email

**Authentication:**
- Uses `credentials/credentials.json` (Gmail API credentials)
- Generates `credentials/token.json` (OAuth2 access token)
- Token auto-refreshes when expired

### 2. LLM Classification

**Model:** OpenAI (primary) / Anthropic (fallback)

**Classification Logic:**
```python
URGENT criteria:
- "urgent", "emergency", "asap", "critical"
- Damage reports (water, fire, gas)
- Safety issues
- Legal deadlines

IMPORTANT criteria:
- Invoice notifications
- Maintenance requests
- Meeting confirmations
- Regulatory notices

ROUTINE criteria:
- Newsletters
- Marketing
- General information
- Routine updates
```

**Performance:**
- Parallel processing with `asyncio.gather()`
- Batch classification reduces API calls
- Temperature: 0.2 (consistent results)

### 3. Database Schema

**Table:** `emails`

```sql
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR UNIQUE NOT NULL,
    sender VARCHAR NOT NULL,
    subject VARCHAR,
    body TEXT,
    urgency emailurgency NOT NULL,  -- URGENT, IMPORTANT, ROUTINE
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    copropriete_id INTEGER REFERENCES coproprietes(id),
    coproprietaire_id INTEGER REFERENCES coproprietaires(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Indexes:**
- `ix_emails_message_id` (unique)
- `ix_emails_urgency`
- `ix_emails_received_at`

### 4. Digest Endpoint

**File:** `backend/app/api/endpoints/digest.py`

**Endpoint:** `POST /api/digest/generate`

**Request:**
```json
{
  "since_hours": 24,
  "max_emails": 100
}
```

**Response:**
```json
{
  "urgent": [
    {
      "id": 123,
      "subject": "URGENT: Dégât des eaux",
      "sender": "resident@example.com",
      "received_at": "2025-11-02T10:30:00Z",
      "preview": "Il y a une fuite importante..."
    }
  ],
  "important": [...],
  "routine": [...],
  "total": 15,
  "gmail_sync_status": "success"
}
```

## Benefits of Hybrid Approach

### ✅ Resilience
- Digest always succeeds, even if Gmail is down
- Timeout protection prevents hanging requests
- Graceful degradation to cached data

### ✅ Performance
- Database queries are instant (<50ms)
- Parallel LLM classification
- Cached results for historical queries

### ✅ Offline Capability
- Works without internet connection
- Can generate digest from database alone
- Historical email access

### ✅ Docker-Safe
- Handles container networking issues
- Timeout prevents Docker DNS hangs
- No dependency on external services for basic functionality

## Setup Instructions

### Prerequisites

1. **Gmail API Credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download `credentials.json`

2. **Place Credentials**
   ```bash
   mkdir -p backend/credentials
   cp /path/to/credentials.json backend/credentials/credentials.json
   ```

### One-Time Authentication

```bash
cd backend
python scripts/gmail_auth.py
```

This will:
1. Open browser for Google OAuth consent
2. Request permissions: `gmail.readonly`
3. Generate `credentials/token.json`
4. Store refresh token for automatic renewal

### Verify Setup

```bash
# Check token exists
ls -la backend/credentials/token.json

# Test digest generation
curl -X POST http://localhost:8000/api/digest/generate \
  -H "Content-Type: application/json" \
  -d '{"since_hours": 24, "max_emails": 10}'
```

## Troubleshooting

### Issue: "Timeout fetching emails"

**Cause:** Gmail API taking >60s to respond

**Solutions:**
1. Check internet connection
2. Reduce `since_hours` parameter
3. Use cached digest from database
4. Check Docker DNS resolution

### Issue: "Invalid credentials"

**Cause:** Missing or expired `credentials.json`

**Solutions:**
1. Re-download credentials from Google Cloud Console
2. Verify file exists at `backend/credentials/credentials.json`
3. Re-run `gmail_auth.py` to refresh token

### Issue: "Token refresh failed"

**Cause:** Refresh token expired (rare, ~6 months)

**Solutions:**
1. Delete `credentials/token.json`
2. Re-run `gmail_auth.py`
3. Grant permissions again

### Issue: "No emails found"

**Cause:** All emails already processed or no unread emails

**Solutions:**
1. Check Gmail inbox for unread emails
2. Increase `since_hours` parameter
3. Query database directly: `SELECT * FROM emails;`

## Monitoring

### Metrics to Track

1. **Gmail Sync Success Rate**
   ```sql
   SELECT
     COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 day') as emails_today,
     COUNT(DISTINCT DATE(created_at)) as days_active
   FROM emails;
   ```

2. **Urgency Distribution**
   ```sql
   SELECT urgency, COUNT(*)
   FROM emails
   WHERE received_at > NOW() - INTERVAL '7 days'
   GROUP BY urgency;
   ```

3. **Response Times**
   - Gmail fetch: <60s
   - LLM classification: <90s
   - Database query: <50ms

### Logs

Key log events:
- `gmail_fetch_started`
- `gmail_fetch_succeeded` / `gmail_fetch_timeout`
- `llm_classification_completed`
- `emails_persisted`
- `digest_generated`

```bash
# View digest-related logs
docker-compose logs backend | grep digest
```

## Future Enhancements

1. **Scheduled Digest**
   - Daily/weekly automatic generation
   - Email delivery via SMTP
   - Custom scheduling per user

2. **Smart Filtering**
   - Machine learning-based urgency detection
   - Sender reputation scoring
   - Automatic categorization by topic

3. **Real-Time Notifications**
   - WebSocket push for urgent emails
   - Browser notifications
   - SMS alerts for critical emails

4. **Multi-Account Support**
   - Multiple Gmail accounts
   - Unified digest across accounts
   - Per-account authentication

## References

- **Gmail API Docs:** https://developers.google.com/gmail/api
- **OAuth2 Flow:** https://developers.google.com/identity/protocols/oauth2
- **FastAPI Async:** https://fastapi.tiangolo.com/async/
