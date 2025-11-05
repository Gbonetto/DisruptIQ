# Conversational Intelligence - Deployment Guide

## Overview

This guide covers the deployment of the Conversational Intelligence system that has been fully integrated into the DisruptIQ chat endpoints.

## Architecture Summary

The system consists of:

1. **Database Models** - Store conversation sessions, turns, user profiles, and feedback
2. **SessionManager** - Manages conversation lifecycle and context
3. **IntentClassifier** - Classifies user intents with context awareness
4. **Enhanced Chat Endpoints** - Integrated intelligence into `/api/chat/with-plan`
5. **Feedback System** - Collect user feedback for learning
6. **User Profiling** - Automatic personalization

## Deployment Steps

### Step 1: Database Migration

Run the SQL migration to create the conversational intelligence tables:

```bash
cd /home/user/DisruptIQ/backend

# Using psql
psql -U disruptiq -d disruptiq -f migrations/conversational_intelligence.sql

# Or using Docker
docker exec -i disruptiq-postgres psql -U disruptiq -d disruptiq < migrations/conversational_intelligence.sql
```

This creates 4 tables:
- `conversation_sessions` - Session tracking
- `conversation_turns` - Individual message exchanges
- `user_profiles` - User preferences and learning
- `feedback_events` - Explicit feedback collection

### Step 2: Verify Integration

The conversational intelligence has been integrated into the existing chat endpoint:

**Endpoint**: `POST /api/chat/with-plan`

**New Features**:
- ✅ Automatic session creation and context loading
- ✅ Intent classification with 12 primary intents
- ✅ Context-aware responses using conversation history
- ✅ Clarification flow for ambiguous queries
- ✅ Conversation turn persistence
- ✅ User profiling for personalization

### Step 3: Test the Integration

Run the automated tests:

```bash
# Unit and integration tests
pytest tests/api/test_chat_conversational_intelligence.py -v

# Manual test script
python scripts/test_conversational_intelligence.py
```

### Step 4: Test with API Calls

Test the enhanced chat endpoint:

```bash
# Example 1: Create a conversation
curl -X POST http://localhost:8000/api/chat/with-plan \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Montre-moi les factures",
    "conversation_history": [],
    "session_id": null
  }'

# Response includes session_id for subsequent calls

# Example 2: Continue conversation with context
curl -X POST http://localhost:8000/api/chat/with-plan \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Seulement celles qui nécessitent révision",
    "conversation_history": [],
    "session_id": "session-abc123"
  }'

# Example 3: Get conversation history
curl -X GET http://localhost:8000/api/chat/history/session-abc123

# Example 4: Submit feedback
curl -X POST http://localhost:8000/api/chat/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "turn_id": 1,
    "satisfied": true,
    "rating": 5,
    "feedback_text": "Perfect response!"
  }'
```

## New API Endpoints

### 1. Enhanced Chat with Intelligence

**`POST /api/chat/with-plan`**

Enhanced with:
- Session management
- Context retention (last 10 turns)
- Intent classification
- Clarification flow
- Turn persistence

Request:
```json
{
  "message": "Montre-moi les factures",
  "conversation_history": [],
  "session_id": "session-abc123"  // Optional, creates new if null
}
```

Response:
```json
{
  "message": "Voici les factures...",
  "sources": [...],
  "session_id": "session-abc123",
  "observability": {...},
  "evaluation": {...},
  "agents_used": ["sql_agent"],
  "confidence": 0.95
}
```

### 2. Get Conversation History

**`GET /api/chat/history/{session_id}`**

Returns complete conversation history with:
- All turns (user + assistant messages)
- Detected intents and confidence
- Timestamps
- Feedback ratings

Response:
```json
{
  "session_id": "session-abc123",
  "started_at": "2025-01-15T10:00:00Z",
  "turns_count": 5,
  "topics": ["invoices", "suppliers"],
  "messages": [
    {
      "turn_number": 1,
      "timestamp": "2025-01-15T10:00:00Z",
      "user_message": "Montre-moi les factures",
      "assistant_message": "Voici les factures...",
      "detected_intent": "QUERY_INVOICE",
      "intent_confidence": 0.95,
      "response_type": "answer",
      "user_satisfied": true,
      "feedback_rating": 5
    },
    ...
  ]
}
```

### 3. End Session

**`DELETE /api/chat/history/{session_id}`**

Marks session as ended (keeps data for analytics).

### 4. Submit Feedback

**`POST /api/chat/feedback`**

Submit user feedback for learning:

Request:
```json
{
  "turn_id": 123,
  "satisfied": true,           // Optional: thumbs up/down
  "rating": 5,                 // Optional: 1-5 stars
  "feedback_text": "Great!",   // Optional: text feedback
  "corrected_intent": null     // Optional: intent correction
}
```

### 5. Get User Profile

**`GET /api/chat/profile/{user_id}`**

Returns user's learned preferences:

Response:
```json
{
  "user_id": 1,
  "default_copropriete_id": 5,
  "preferred_date_range": "last_30_days",
  "preferred_response_style": "detailed",
  "most_common_intents": {"QUERY_INVOICE": 0.45, "QUERY_SUPPLIER": 0.30},
  "expertise_level": "intermediate",
  "total_sessions": 25,
  "total_turns": 150,
  "avg_satisfaction": 4.2
}
```

## Intent System

The system recognizes 12 primary intents:

1. **QUERY_INVOICE** - Search/list invoices
2. **QUERY_SUPPLIER** - Search/list suppliers
3. **QUERY_STATS** - Statistics and aggregations
4. **QUERY_DOCUMENT** - Document search (RAG)
5. **ACTION_CREATE** - Create new entities
6. **ACTION_UPDATE** - Update existing entities
7. **ACTION_DELETE** - Delete entities
8. **CLARIFICATION** - Ask for clarification
9. **FEEDBACK** - Provide feedback
10. **GREETING** - Greetings
11. **HELP** - Help requests
12. **OTHER** - Unclassified

### Sub-Intents for QUERY_INVOICE

- `BY_AMOUNT` - Filter by amount
- `BY_DATE` - Filter by date
- `BY_SUPPLIER` - Filter by supplier
- `NEEDS_REVIEW` - Only invoices needing review
- `DUPLICATES` - Find duplicates

## Context Retention Features

### Reference Resolution

The system understands references like:
- "celles" / "those"
- "il" / "elle" / "it"
- "la première" / "the first one"
- "ça" / "that"

Example:
```
User: "Montre-moi les factures"
Assistant: [Shows invoices]

User: "Seulement celles qui nécessitent révision"
Assistant: [Understands "celles" refers to invoices]
```

### Topic Tracking

The system tracks conversation topics across turns:
- Automatically detects topic changes
- Maintains current context
- Uses previous context for ambiguous queries

### Intent Inheritance

When user responds to a clarification:
- Inherits intent from previous turn
- Boosts confidence based on context
- Resolves entities from conversation history

## Clarification Flow

When the system detects ambiguous intent (confidence < 75%):

```
User: "Je veux voir ça"
Assistant: "Je n'ai pas compris. Voulez-vous voir les factures ou les fournisseurs ?"

User: "Les factures"
Assistant: [Shows invoices with high confidence]
```

## Learning System

### Implicit Signals

Automatically tracked:
- User clicked a result
- User refined query
- User asked follow-up questions
- Time spent on response

### Explicit Feedback

User can provide:
- Thumbs up/down
- 1-5 star rating
- Text feedback
- Intent corrections

### Continuous Improvement

Feedback is used to:
- Improve intent classification accuracy
- Personalize user experience
- Train ML models (future)
- Monitor system performance

## Monitoring and Analytics

### Key Metrics to Monitor

1. **Intent Accuracy**
   - Track corrected_intent feedback
   - Monitor confidence distributions
   - Identify low-confidence patterns

2. **User Satisfaction**
   - Average ratings per intent
   - Satisfaction trends over time
   - User satisfaction by expertise level

3. **Session Analytics**
   - Average session length
   - Turns per session
   - Topic distribution
   - Abandonment rate

### Query Analytics

```sql
-- Top intents
SELECT
    detected_intent,
    COUNT(*) as count,
    AVG(intent_confidence) as avg_confidence
FROM conversation_turns
GROUP BY detected_intent
ORDER BY count DESC;

-- User satisfaction by intent
SELECT
    detected_intent,
    AVG(CASE WHEN user_satisfied THEN 1.0 ELSE 0.0 END) as satisfaction_rate,
    AVG(feedback_rating) as avg_rating
FROM conversation_turns
WHERE user_satisfied IS NOT NULL
GROUP BY detected_intent;

-- Sessions by day
SELECT
    DATE(started_at) as date,
    COUNT(*) as sessions,
    AVG(turns_count) as avg_turns
FROM conversation_sessions
GROUP BY DATE(started_at)
ORDER BY date DESC;
```

## Troubleshooting

### Issue: Sessions not persisting

**Check:**
1. Database migration ran successfully
2. `conversation_sessions` table exists
3. Database connection is working

```bash
psql -U disruptiq -d disruptiq -c "SELECT COUNT(*) FROM conversation_sessions;"
```

### Issue: Intents always classify as OTHER

**Check:**
1. Intent patterns in `intent_classifier.py`
2. Message preprocessing (lowercase, accents)
3. Keyword matching logic

**Debug:**
```python
from app.services.conversation.intent_classifier import IntentClassifier

classifier = IntentClassifier()
scores = classifier.classify("Montre-moi les factures")
print(scores)  # Should show QUERY_INVOICE with high score
```

### Issue: Context not being used

**Check:**
1. Session history is loading correctly
2. Turn count is incrementing
3. `get_session_history` returns data

**Debug:**
```python
from app.services.conversation.session_manager import SessionManager
from app.core.database import AsyncSessionLocal

async with AsyncSessionLocal() as db:
    manager = SessionManager(db)
    history = await manager.get_session_history("session-abc123")
    print(f"Turns: {len(history)}")
```

### Issue: Feedback not saving

**Check:**
1. Turn ID exists
2. Rating is between 1-5
3. Database constraints

```bash
psql -U disruptiq -d disruptiq -c "SELECT id, user_satisfied, feedback_rating FROM conversation_turns WHERE id = 1;"
```

## Performance Considerations

### Database Indexing

The migration creates indexes on:
- `session_id` (for fast lookups)
- `user_id` (for user queries)
- `started_at` (for time-based queries)
- `detected_intent` (for analytics)

### Session Cleanup

Old inactive sessions should be cleaned periodically:

```python
from app.services.conversation.session_manager import SessionManager

async with AsyncSessionLocal() as db:
    manager = SessionManager(db)
    deleted_count = await manager.cleanup_old_sessions(days_old=30)
    print(f"Cleaned {deleted_count} old sessions")
```

Schedule this as a cron job:
```bash
# Add to crontab
0 2 * * * python /path/to/cleanup_sessions.py
```

## Security Considerations

### User Authentication

The system currently creates anonymous sessions. To add user authentication:

1. Extract user from auth context in chat endpoint
2. Update session with user_id
3. Filter history by user_id

```python
# In chat.py
from app.core.auth import get_current_user

@router.post("/with-plan")
async def ask_question_with_plan(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Add auth
):
    session = await session_manager.get_session(...)
    if session and not session.user_id:
        session.user_id = current_user.id
        await db.commit()
```

### Data Privacy

- Sessions contain full conversation history
- Apply data retention policies
- Consider GDPR right to erasure
- Implement session deletion endpoint

## Future Enhancements

1. **ML-Based Intent Classification**
   - Train neural network on conversation data
   - Replace keyword matching with ML model
   - Continuous learning from feedback

2. **Entity Extraction Service**
   - Extract amounts, dates, suppliers from text
   - Structured entity resolution
   - Entity linking to database records

3. **Proactive Suggestions**
   - Suggest common follow-up queries
   - Predict user needs based on patterns
   - Smart query completion

4. **Multi-Language Support**
   - Detect user language
   - Translate intents and entities
   - Language-specific patterns

5. **Voice Interface**
   - Speech-to-text integration
   - Voice-optimized responses
   - Audio feedback

## Support

For issues or questions:
- Review logs: `journalctl -u disruptiq-backend -f`
- Check database: `psql -U disruptiq -d disruptiq`
- Run tests: `pytest tests/api/test_chat_conversational_intelligence.py -v`
- Manual test: `python scripts/test_conversational_intelligence.py`

## Summary

The Conversational Intelligence system is now fully integrated and provides:

✅ **Context Retention** - Remember conversation history
✅ **Intent Classification** - Understand user needs with 12 intents
✅ **Clarification Flow** - Ask questions when uncertain
✅ **User Profiling** - Learn preferences automatically
✅ **Feedback Loop** - Continuous improvement from feedback
✅ **Analytics** - Track performance and satisfaction
✅ **Reference Resolution** - Understand pronouns and references
✅ **Sub-Intents** - Granular understanding of queries

The system is production-ready and will improve user interaction quality significantly.
