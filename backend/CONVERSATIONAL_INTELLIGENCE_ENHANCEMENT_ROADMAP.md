# Conversational Intelligence - Enhancement Roadmap

## Analysis of Current System vs Perfect Intelligence

### ✅ What's Already Implemented (Foundation)

1. **Session Management** - Context retention across conversation
2. **Intent Classification** - 12 primary intents with keyword/pattern matching
3. **Sub-Intent Detection** - Granular understanding (BY_AMOUNT, BY_DATE, etc.)
4. **Clarification Flow** - Asks questions when uncertain
5. **Feedback Collection** - Learning from user corrections
6. **User Profiling** - Basic preference tracking
7. **Reference Resolution** - Basic pronoun understanding

### ❌ What's Missing for Maximum Intelligence

## Phase 1: Entity Extraction (Critical) 🔴

**Current Issue**: `extracted_entities={},  # TODO: Extract entities from message`

The system doesn't extract structured information from user messages.

### Impact
- Can't filter by amounts automatically ("factures > 500€")
- Can't understand dates ("le mois dernier")
- Can't identify suppliers from text ("factures de Dupont")
- Can't resolve invoice numbers ("facture FAC-001")

### Implementation Needed

**Entity Types to Extract**:
- **Amounts**: 500€, 1000 euros, cinq cents euros
- **Dates**: le mois dernier, 2024-01-15, janvier, hier
- **Suppliers**: Plomberie Dupont, électricien Martin
- **Invoice Numbers**: FAC-001, invoice #123
- **Status**: en attente, payée, annulée
- **Categories**: plomberie, électricité, jardinage
- **Ranges**: entre 100 et 500€, de janvier à mars

**Solution**: Create `EntityExtractorService` using:
1. Regex patterns for amounts, dates, invoice numbers
2. spaCy/duckling for NER (Named Entity Recognition)
3. LLM-based extraction for complex entities
4. Entity linking to database records

**Priority**: **CRITICAL** - This is blocking many use cases

---

## Phase 2: LLM-Based Intent Understanding (High Priority) 🟠

**Current Issue**: Intent classification uses simple keyword matching

### Problem
```python
# Current approach
if "facture" in message.lower():
    scores["QUERY_INVOICE"] += 0.8
```

This fails for:
- Paraphrasing: "Je cherche mes notes de frais" → Should be QUERY_INVOICE
- Implicit intents: "C'est combien ?" → Needs context to understand
- Complex queries: "Montre moi les docs du plombier qui a fait l'intervention d'hier"

### Solution: Hybrid Approach

**Layer 1: Fast Pattern Matching** (current)
- For common, explicit queries
- 99% of cases, <5ms latency

**Layer 2: LLM-Based Understanding** (new)
- When confidence < 80%
- For complex/ambiguous queries
- Uses conversation context

**Implementation**:

```python
class AdvancedIntentClassifier:
    async def classify_with_llm(
        self,
        message: str,
        context: List[ConversationTurn]
    ) -> Dict[str, float]:
        """
        Use LLM to understand intent when patterns fail
        """
        prompt = f"""
        Analyse cette demande utilisateur dans le contexte d'un système de gestion de copropriété.

        Conversation précédente:
        {self._format_context(context)}

        Message actuel: "{message}"

        Détermine l'intention parmi:
        - QUERY_INVOICE: Recherche/liste de factures
        - QUERY_SUPPLIER: Recherche de fournisseurs
        - QUERY_STATS: Statistiques et agrégations
        - ACTION_CREATE: Créer une entité
        - ACTION_UPDATE: Modifier une entité
        - CLARIFICATION: Besoin de clarification
        - HELP: Demande d'aide

        Réponds en JSON avec scores de confiance:
        {{"QUERY_INVOICE": 0.9, "QUERY_SUPPLIER": 0.1}}
        """

        response = await self.llm_service.generate(prompt)
        return self._parse_intent_scores(response)
```

**Benefits**:
- Understands paraphrasing
- Better with ambiguity
- Learns from context
- Handles complex queries

**Priority**: **HIGH** - Significantly improves understanding

---

## Phase 3: Smart Query Rewriting (High Priority) 🟠

**Current Issue**: System doesn't reformulate queries with context

### Problem

User says: "Montre-moi seulement celles qui sont supérieures à 500€"

The orchestrator receives exactly this, without context:
- What is "celles"? (invoices from previous turn)
- Lacks explicit filtering

### Solution: Query Rewriter

```python
class QueryRewriter:
    async def rewrite_with_context(
        self,
        user_message: str,
        context: List[ConversationTurn]
    ) -> str:
        """
        Rewrites the query to be self-contained using context

        Example:
        Input: "seulement celles > 500€"
        Context: Previous query was "Montre les factures de plomberie"
        Output: "Montre les factures de plomberie avec montant > 500€"
        """
```

**Use Cases**:
1. **Reference Resolution**:
   - "celles-là" → "les factures"
   - "il" → "le fournisseur Dupont"

2. **Context Inheritance**:
   - Previous: "Factures de janvier"
   - Current: "Et février aussi"
   - Rewritten: "Factures de janvier et février"

3. **Filter Refinement**:
   - Previous: "Factures de plomberie"
   - Current: "Entre 100 et 500€"
   - Rewritten: "Factures de plomberie entre 100€ et 500€"

**Implementation Using LLM**:

```python
prompt = f"""
Contexte de conversation:
{previous_turns}

Message utilisateur: "{current_message}"

Réécris ce message pour qu'il soit auto-suffisant (self-contained) en incluant le contexte nécessaire.

Exemple:
Context: "Montre les factures"
Message: "Seulement celles > 500€"
Réécrit: "Montre les factures avec montant supérieur à 500€"
"""
```

**Priority**: **HIGH** - Essential for natural conversation flow

---

## Phase 4: Proactive Suggestions (Medium Priority) 🟡

**Current Issue**: System is purely reactive

### Vision: Intelligent Suggestions

After each response, suggest relevant follow-up actions:

```json
{
  "message": "Voici les 15 factures de plomberie...",
  "suggestions": [
    {
      "type": "filter",
      "text": "Voir seulement celles en attente",
      "action": "QUERY_INVOICE",
      "params": {"status": "pending"}
    },
    {
      "type": "analysis",
      "text": "Analyser les montants par mois",
      "action": "QUERY_STATS",
      "params": {"group_by": "month"}
    },
    {
      "type": "related",
      "text": "Voir le contact du plombier",
      "action": "QUERY_SUPPLIER",
      "params": {"category": "plomberie"}
    }
  ]
}
```

**Suggestion Types**:

1. **Next Steps**: Common follow-ups
2. **Drill-down**: More specific queries
3. **Roll-up**: Broader analysis
4. **Related Entities**: "Voir le fournisseur", "Voir les documents"
5. **Actions**: "Marquer comme payée", "Créer un doublon"

**Implementation**:

```python
class SuggestionEngine:
    def generate_suggestions(
        self,
        current_intent: str,
        query_result: Dict,
        user_profile: UserProfile
    ) -> List[Suggestion]:
        """
        Generates smart suggestions based on:
        - Current intent
        - Query results
        - User history (common follow-ups)
        - Business logic
        """

        suggestions = []

        # Intent-specific suggestions
        if current_intent == "QUERY_INVOICE":
            suggestions.extend(self._invoice_suggestions(query_result))

        # Personalized suggestions
        suggestions.extend(self._personalized_suggestions(user_profile))

        # Rank by relevance
        return self._rank_suggestions(suggestions)
```

**Priority**: **MEDIUM** - Great UX, not blocking

---

## Phase 5: Semantic Search for History (Medium Priority) 🟡

**Current Issue**: Can't search conversations semantically

### Problem

User asks: "Qu'est-ce qu'on avait dit sur les factures en retard ?"

Current system can only load last N turns by recency, not by semantic similarity.

### Solution: Vector-Based Search

```python
class SemanticConversationSearch:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def search_conversation_history(
        self,
        session_id: str,
        query: str,
        top_k: int = 5
    ) -> List[ConversationTurn]:
        """
        Search conversation history by semantic similarity

        Uses embeddings to find relevant turns even if
        different words are used
        """

        # Get query embedding
        query_embedding = await self.embedding_service.embed(query)

        # Search in vector DB (or compute similarity)
        similar_turns = await self._vector_search(
            session_id=session_id,
            embedding=query_embedding,
            top_k=top_k
        )

        return similar_turns
```

**Use Cases**:
- "Qu'est-ce qu'on avait dit sur X ?"
- "Rappelle-moi la conversation sur Y"
- "Combien coûtait la facture dont on parlait ?"

**Implementation Options**:
1. **Embedding + FAISS/Qdrant**: Fast vector search
2. **PostgreSQL pgvector**: Native vector support
3. **On-demand similarity**: Compute when needed

**Priority**: **MEDIUM** - Nice to have, enhances long conversations

---

## Phase 6: User Intent Prediction (Low Priority) 🟢

**Vision**: Predict what user will ask next

### Example

User just asked: "Montre les factures de plomberie"

System predicts (internally):
- 70% probability: Will filter by amount/date
- 20% probability: Will ask for supplier contact
- 10% probability: Will ask for total/stats

**Use Cases**:
1. **Pre-loading data**: Fetch likely next queries
2. **Smart suggestions**: Prioritize predicted intents
3. **Caching**: Cache predicted query results

**Priority**: **LOW** - Optimization, not essential

---

## Phase 7: Dynamic Response Adaptation (Medium Priority) 🟡

**Current Issue**: Responses don't adapt to user expertise level

### Solution: Adaptive Responses

```python
class ResponseAdapter:
    def adapt_response(
        self,
        base_response: str,
        user_profile: UserProfile,
        detected_intent: str
    ) -> str:
        """
        Adapts response based on:
        - User expertise level (beginner/intermediate/expert)
        - Preferred response style (concise/detailed)
        - Language preference
        """

        if user_profile.expertise_level == "beginner":
            # Add explanations
            return self._add_explanations(base_response)

        elif user_profile.preferred_response_style == "concise":
            # Shorter responses
            return self._make_concise(base_response)

        return base_response
```

**Adaptation Dimensions**:

1. **Expertise Level**:
   - Beginner: More explanations, tooltips
   - Expert: Direct answers, technical terms

2. **Response Style**:
   - Concise: Bullet points, short sentences
   - Detailed: Full explanations, examples

3. **Language**:
   - Formal: "Voici les résultats"
   - Casual: "J'ai trouvé ça"

**Priority**: **MEDIUM** - Good UX improvement

---

## Phase 8: Multi-turn Planning (Low Priority) 🟢

**Vision**: Plan multiple steps ahead

### Example

User: "Je veux traiter toutes les factures en attente"

System plans:
1. Query factures en attente
2. Present list with options
3. Wait for selection
4. Execute action on selected items
5. Confirm completion

**Current**: Each turn is independent
**Target**: Maintain execution plans across turns

**Priority**: **LOW** - Complex, nice to have

---

## Phase 9: Sentiment & Frustration Detection (Low Priority) 🟢

**Vision**: Detect user emotions in real-time

### Use Cases

```python
# Detect frustration
if sentiment_analyzer.is_frustrated(message):
    # Offer human escalation
    # Simplify response
    # Ask if needs help
```

**Signals**:
- Negative words: "ça marche pas", "c'est nul"
- Repetition: Same query 3+ times
- Exclamation: "!!!"
- Short responses: "non", "pas ça"

**Actions**:
- Apologize: "Désolé, je vais faire mieux"
- Offer help: "Voulez-vous que je simplifie ?"
- Escalate: "Voulez-vous parler à un humain ?"

**Priority**: **LOW** - Nice UX touch

---

## Recommended Implementation Order

### Immediate (Week 1) 🔴
1. **Entity Extraction Service** - Unblocks many features
2. **LLM-Enhanced Intent Classification** - Better understanding

### Short-term (Week 2-3) 🟠
3. **Smart Query Rewriting** - Natural conversation flow
4. **Dynamic Response Adaptation** - Better UX

### Mid-term (Month 1) 🟡
5. **Proactive Suggestions** - Guided experience
6. **Semantic History Search** - Long conversations

### Long-term (Month 2+) 🟢
7. **Intent Prediction** - Optimization
8. **Multi-turn Planning** - Complex workflows
9. **Sentiment Detection** - Emotional intelligence

---

## Technical Architecture for Enhanced System

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INPUT                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              ENTITY EXTRACTOR                                │
│  - Amounts, Dates, Suppliers, Invoice Numbers               │
│  - Regex + spaCy + LLM                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              QUERY REWRITER                                  │
│  - Resolves references with context                         │
│  - Makes query self-contained                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         ADVANCED INTENT CLASSIFIER                           │
│  Layer 1: Pattern matching (fast)                           │
│  Layer 2: LLM-based (accurate)                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR                                    │
│  - Routes to SQL/RAG agents                                 │
│  - Uses enriched query + entities                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         RESPONSE ADAPTER                                     │
│  - Adapts to user expertise                                 │
│  - Applies preferred style                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         SUGGESTION ENGINE                                    │
│  - Generates smart follow-ups                               │
│  - Based on intent + results + profile                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              SESSION MANAGER                                 │
│  - Saves turn with entities + suggestions                   │
│  - Updates user profile                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Expected Impact

### Before Enhancements
- ❌ "Factures > 500€" → Doesn't understand "500€"
- ❌ "Celles du mois dernier" → Can't resolve "celles"
- ❌ "Je cherche mes notes de frais" → Doesn't map to QUERY_INVOICE
- ❌ No suggestions for next steps
- ❌ Same response for beginners and experts
- ❌ Can't search past conversations semantically

### After Enhancements ✨
- ✅ "Factures > 500€" → Extracts amount: 500, applies filter
- ✅ "Celles du mois dernier" → Resolves to "factures de plomberie du mois dernier"
- ✅ "Je cherche mes notes de frais" → LLM understands → QUERY_INVOICE
- ✅ Shows 3 smart suggestions after each response
- ✅ Adapts explanation depth to user level
- ✅ "Qu'est-ce qu'on disait sur X ?" → Semantic search finds it

---

## Metrics to Track

### Intelligence Metrics
- **Entity Extraction Accuracy**: % entities correctly extracted
- **Intent Classification Accuracy**: % intents correctly classified
- **Reference Resolution Rate**: % references correctly resolved
- **Suggestion Click Rate**: % users clicking suggestions
- **Multi-turn Success Rate**: % conversations achieving goal

### User Experience Metrics
- **Average Conversation Length**: Fewer turns = better understanding
- **Clarification Rate**: Lower = better intelligence
- **User Satisfaction**: Higher = better responses
- **Task Completion Rate**: % users completing their goal
- **Frustration Detection**: Catch and fix issues early

---

## Cost/Benefit Analysis

### Phase 1: Entity Extraction
- **Development**: 3-5 days
- **Impact**: HIGH - Unblocks filtering, search
- **ROI**: IMMEDIATE

### Phase 2: LLM-Enhanced Intent
- **Development**: 2-3 days
- **Impact**: HIGH - Better understanding
- **ROI**: IMMEDIATE
- **Cost**: +$0.002 per query (only when needed)

### Phase 3: Query Rewriting
- **Development**: 3-4 days
- **Impact**: HIGH - Natural conversations
- **ROI**: IMMEDIATE

### Phase 4: Suggestions
- **Development**: 4-6 days
- **Impact**: MEDIUM - Better UX
- **ROI**: Short-term

### Phase 5: Semantic Search
- **Development**: 5-7 days (with vector DB)
- **Impact**: MEDIUM - Long conversations
- **ROI**: Long-term

---

## Next Steps

**Option A: Maximum Intelligence (Recommended) 🚀**
Implement Phases 1-4 immediately for dramatic improvement:
1. Entity Extraction
2. LLM-Enhanced Intent
3. Query Rewriting
4. Dynamic Adaptation + Suggestions

**Timeline**: 2-3 weeks
**Impact**: 10x better intelligence

**Option B: Essential First**
Implement only Phase 1-2:
1. Entity Extraction
2. LLM-Enhanced Intent

**Timeline**: 1 week
**Impact**: 3x better intelligence

**Option C: Full Roadmap**
Implement all 9 phases over 2 months for perfect intelligence.

---

## Conclusion

The current system provides a **solid foundation** with:
- Session management
- Basic intent classification
- Context retention
- Feedback collection

To achieve **maximum intelligence**, we need:
1. **Entity Extraction** (critical)
2. **LLM-based Understanding** (high impact)
3. **Query Rewriting** (natural flow)
4. **Proactive Suggestions** (guided UX)
5. **Response Adaptation** (personalization)

The gap is real but achievable. Phases 1-3 would give you 80% of the value in 1-2 weeks.

**Ready to implement?** I recommend starting with **Entity Extraction** as it's blocking many advanced features.
