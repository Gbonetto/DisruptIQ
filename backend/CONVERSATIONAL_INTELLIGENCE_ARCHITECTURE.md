# Architecture d'Intelligence Conversationnelle

Ce document décrit l'architecture complète du système d'intelligence conversationnelle avancée pour DisruptIQ.

---

## 🎯 Objectifs

Transformer l'assistant IA en un système capable de :
1. **Comprendre parfaitement** les besoins utilisateur
2. **Mémoriser** le contexte conversationnel
3. **S'adapter** à chaque utilisateur
4. **Apprendre** continuellement
5. **Anticiper** les besoins futurs

---

## 🏗️ Architecture Globale

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER INTERACTION                             │
│                   (Message texte / vocal)                        │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               1. CONVERSATIONAL MEMORY                           │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ Session Manager                                     │       │
│   │ - Load conversation history (last 10 turns)         │       │
│   │ - Load user profile                                 │       │
│   │ - Context window management                         │       │
│   └─────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               2. INTENT RECOGNITION                              │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ Intent Classifier (Multi-label)                     │       │
│   │                                                       │       │
│   │ Primary Intents:                                     │       │
│   │ - QUERY_INVOICE (chercher factures)                 │       │
│   │ - QUERY_SUPPLIER (infos fournisseurs)               │       │
│   │ - QUERY_STATS (statistiques)                         │       │
│   │ - QUERY_DOCUMENT (chercher docs)                     │       │
│   │ - ACTION_CREATE (créer entité)                       │       │
│   │ - ACTION_UPDATE (modifier)                           │       │
│   │ - ACTION_DELETE (supprimer)                          │       │
│   │ - CLARIFICATION (question de clarification)         │       │
│   │ - FEEDBACK (retour utilisateur)                      │       │
│   │ - GREETING (salutation)                              │       │
│   │ - HELP (demande d'aide)                              │       │
│   │ - OTHER (autre)                                       │       │
│   │                                                       │       │
│   │ Sub-Intents (per primary):                           │       │
│   │ - QUERY_INVOICE:                                     │       │
│   │   * BY_AMOUNT (montant)                              │       │
│   │   * BY_DATE (période)                                │       │
│   │   * BY_SUPPLIER (fournisseur)                        │       │
│   │   * BY_STATUS (statut)                               │       │
│   │   * NEEDS_REVIEW (révision)                          │       │
│   │   * DUPLICATES (doublons)                            │       │
│   └─────────────────────────────────────────────────────┘       │
│                                                                   │
│   Confidence Threshold: 0.75                                     │
│   Multi-intent detection: Yes                                    │
│   Ambiguity resolution: Clarification questions                  │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               3. ENTITY EXTRACTION                               │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ NER (Named Entity Recognition)                       │       │
│   │                                                       │       │
│   │ Entities:                                             │       │
│   │ - MONEY (montants)                                    │       │
│   │ - DATE (dates, périodes)                              │       │
│   │ - SUPPLIER_NAME (noms fournisseurs)                  │       │
│   │ - INVOICE_NUMBER (numéros factures)                  │       │
│   │ - CATEGORY (catégories)                               │       │
│   │ - COPROPRIETE (copropriétés)                         │       │
│   │ - STATUS (statuts)                                    │       │
│   │                                                       │       │
│   │ Resolution:                                           │       │
│   │ - Resolve references ("il", "ça")                     │       │
│   │ - Map to database IDs                                 │       │
│   │ - Validate existence                                  │       │
│   └─────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               4. CONTEXT ENRICHMENT                              │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ User Context Loader                                  │       │
│   │                                                       │       │
│   │ From User Profile:                                   │       │
│   │ - Preferred copropriete_id                           │       │
│   │ - Favorite queries                                    │       │
│   │ - Recent interactions (last 5)                        │       │
│   │ - Learned preferences                                 │       │
│   │                                                       │       │
│   │ From Conversation:                                   │       │
│   │ - Last entities mentioned                             │       │
│   │ - Current topic/task                                  │       │
│   │ - Unresolved ambiguities                              │       │
│   └─────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               5. INTELLIGENT ROUTING                             │
│         (Enhanced Orchestrator with Context)                     │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ Decision Tree:                                       │       │
│   │                                                       │       │
│   │ if QUERY_* intent:                                   │       │
│   │   if needs_database → SQL Agent                      │       │
│   │   if needs_documents → RAG Agent                     │       │
│   │   if needs_both → HYBRID                             │       │
│   │                                                       │       │
│   │ if ACTION_* intent:                                  │       │
│   │   if has_all_entities → Execute Action              │       │
│   │   else → Ask Clarification                           │       │
│   │                                                       │       │
│   │ if CLARIFICATION:                                    │       │
│   │   → Update context, re-route previous intent         │       │
│   │                                                       │       │
│   │ Context-aware routing:                               │       │
│   │ - Auto-apply user's default filters                  │       │
│   │ - Pre-fill copropriete from profile                  │       │
│   │ - Use recent entities as defaults                    │       │
│   └─────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               6. EXECUTION (Agents)                              │
│                                                                   │
│   SQL Agent / RAG Agent / HYBRID / Action Agent                 │
│   (Existing orchestrator logic)                                  │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               7. RESPONSE GENERATION                             │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ Context-Aware Response Formatter                     │       │
│   │                                                       │       │
│   │ Enhancements:                                        │       │
│   │ - Personalized tone (formal vs casual)               │       │
│   │ - Reference previous context                         │       │
│   │ - Suggest follow-up actions                          │       │
│   │ - Add proactive insights                             │       │
│   │                                                       │       │
│   │ Example:                                             │       │
│   │ User: "Montre-moi les factures"                     │       │
│   │ Context: user.copropriete_id = 5                     │       │
│   │ Response: "Voici les factures pour [Copro 5 name]: │       │
│   │           - Facture #123 (500€)                      │       │
│   │           - ...                                       │       │
│   │           💡 Suggestion: 3 factures nécessitent     │       │
│   │           une révision."                             │       │
│   └─────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               8. LEARNING & FEEDBACK                             │
│                                                                   │
│   ┌─────────────────────────────────────────────────────┐       │
│   │ Feedback Collector                                   │       │
│   │                                                       │       │
│   │ Implicit Feedback:                                   │       │
│   │ - User clicked on result → Relevant                  │       │
│   │ - User asked again → Not satisfied                   │       │
│   │ - User modified query → Misunderstood                │       │
│   │                                                       │       │
│   │ Explicit Feedback:                                   │       │
│   │ - 👍 / 👎 buttons                                    │       │
│   │ - Correction ("Non, je voulais...")                  │       │
│   │ - Rating (1-5 stars)                                 │       │
│   │                                                       │       │
│   │ Learning Actions:                                    │       │
│   │ - Update user profile preferences                    │       │
│   │ - Fine-tune intent classifier                        │       │
│   │ - Adjust context weights                             │       │
│   │ - Store successful patterns                          │       │
│   └─────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│               9. PERSISTENCE                                     │
│                                                                   │
│   Save to Database:                                              │
│   - Conversation turn (message + response)                       │
│   - User profile updates                                         │
│   - Feedback events                                              │
│   - Learned patterns                                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 Modèles de Données

### 1. ConversationSession

```python
class ConversationSession(Base):
    """
    Session conversationnelle utilisateur
    """
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String, unique=True, index=True)  # UUID

    started_at = Column(DateTime, server_default=func.now())
    last_activity_at = Column(DateTime, onupdate=func.now())
    ended_at = Column(DateTime, nullable=True)

    # Summary
    turns_count = Column(Integer, default=0)
    topics = Column(JSONB, default=[])  # ["invoices", "suppliers"]
    intents_distribution = Column(JSONB, default={})  # {"QUERY_INVOICE": 5}

    # Relations
    turns = relationship("ConversationTurn", back_populates="session")
```

### 2. ConversationTurn

```python
class ConversationTurn(Base):
    """
    Un tour de conversation (user message + assistant response)
    """
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"))

    turn_number = Column(Integer)  # 1, 2, 3, ...
    timestamp = Column(DateTime, server_default=func.now())

    # User message
    user_message = Column(Text)
    user_message_cleaned = Column(Text)  # Preprocessed

    # Intent & entities
    detected_intent = Column(String)  # Primary intent
    intent_confidence = Column(Float)
    all_intents = Column(JSONB, default={})  # {"QUERY_INVOICE": 0.95, ...}
    extracted_entities = Column(JSONB, default={})  # {"amount": 500, ...}

    # Assistant response
    assistant_message = Column(Text)
    response_type = Column(String)  # "answer", "clarification", "error"
    sources_used = Column(JSONB, default=[])

    # Execution
    agents_used = Column(JSONB, default=[])  # ["sql_agent", "rag_agent"]
    execution_plan = Column(JSONB, default={})
    execution_time_ms = Column(Integer)

    # Feedback
    user_satisfied = Column(Boolean, nullable=True)
    feedback_rating = Column(Integer, nullable=True)  # 1-5
    feedback_text = Column(Text, nullable=True)
    corrected_intent = Column(String, nullable=True)  # If user corrected

    # Learning
    was_helpful = Column(Boolean, default=True)
    led_to_action = Column(Boolean, default=False)

    # Relations
    session = relationship("ConversationSession", back_populates="turns")
```

### 3. UserProfile

```python
class UserProfile(Base):
    """
    Profil utilisateur avec préférences apprises
    """
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    # Preferences (learned automatically)
    default_copropriete_id = Column(Integer, ForeignKey("coproprietes.id"))
    preferred_date_range = Column(String, default="last_30_days")
    preferred_response_style = Column(String, default="detailed")  # detailed/concise

    # Usage patterns
    most_common_intents = Column(JSONB, default={})  # {"QUERY_INVOICE": 45%}
    favorite_queries = Column(JSONB, default=[])  # Recent successful queries
    interaction_frequency = Column(String)  # daily/weekly/monthly

    # Personalization
    interests = Column(JSONB, default=[])  # ["invoices", "suppliers"]
    expertise_level = Column(String, default="beginner")  # beginner/intermediate/expert

    # Statistics
    total_sessions = Column(Integer, default=0)
    total_turns = Column(Integer, default=0)
    avg_satisfaction = Column(Float, default=0.0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### 4. FeedbackEvent

```python
class FeedbackEvent(Base):
    """
    Événement de feedback utilisateur
    """
    id = Column(Integer, primary_key=True)
    turn_id = Column(Integer, ForeignKey("conversation_turns.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    feedback_type = Column(String)  # "thumbs_up", "thumbs_down", "correction", "rating"
    rating = Column(Integer, nullable=True)  # 1-5
    feedback_text = Column(Text, nullable=True)

    # Correction data
    original_intent = Column(String, nullable=True)
    corrected_intent = Column(String, nullable=True)

    timestamp = Column(DateTime, server_default=func.now())
```

---

## 🧠 Intelligence Components

### 1. Intent Classifier

**Approche** : Multi-label classification avec LLM + règles

```python
class IntentClassifier:
    """
    Classifie les intentions utilisateur
    """

    INTENTS = {
        "QUERY_INVOICE": ["facture", "invoice", "factures", "montant"],
        "QUERY_SUPPLIER": ["fournisseur", "supplier", "plombier", "electricien"],
        "QUERY_STATS": ["statistique", "combien", "total", "moyenne"],
        "QUERY_DOCUMENT": ["document", "doc", "fichier", "pdf"],
        "ACTION_CREATE": ["créer", "créé", "ajouter", "nouveau"],
        "ACTION_UPDATE": ["modifier", "changer", "mettre à jour"],
        "ACTION_DELETE": ["supprimer", "effacer", "annuler"],
        "CLARIFICATION": ["oui", "non", "plutôt", "en fait"],
        "FEEDBACK": ["merci", "parfait", "non ce n'est pas ça"],
        "GREETING": ["bonjour", "salut", "hello"],
        "HELP": ["aide", "help", "comment"],
    }

    def classify(
        self,
        message: str,
        conversation_context: List[ConversationTurn]
    ) -> Dict[str, float]:
        """
        Returns: {"QUERY_INVOICE": 0.95, "QUERY_STATS": 0.40, ...}
        """

        # 1. Keyword matching (fast)
        keyword_scores = self._keyword_matching(message)

        # 2. Context enhancement
        if conversation_context:
            # If previous turn was clarification, inherit intent
            last_turn = conversation_context[-1]
            if last_turn.response_type == "clarification":
                keyword_scores[last_turn.detected_intent] += 0.3

        # 3. LLM classification (for ambiguous cases)
        if max(keyword_scores.values()) < 0.7:
            llm_scores = self._llm_classify(message, conversation_context)
            # Blend scores
            scores = self._blend_scores(keyword_scores, llm_scores)
        else:
            scores = keyword_scores

        return scores
```

### 2. Entity Extractor

```python
class EntityExtractor:
    """
    Extrait les entités des messages utilisateur
    """

    def extract(
        self,
        message: str,
        conversation_context: List[ConversationTurn]
    ) -> Dict[str, Any]:
        """
        Returns: {
            "amount": 500.0,
            "date_range": ("2024-01-01", "2024-12-31"),
            "supplier_name": "Plomberie Dupont",
            "invoice_number": "FAC-2024-001"
        }
        """

        entities = {}

        # 1. Regex patterns
        entities.update(self._extract_with_regex(message))

        # 2. Resolve references ("il", "cette facture")
        entities.update(self._resolve_references(message, conversation_context))

        # 3. LLM extraction (for complex cases)
        entities.update(self._llm_extract(message))

        # 4. Validate against database
        entities = self._validate_entities(entities)

        return entities
```

### 3. Context Manager

```python
class ContextManager:
    """
    Gère le contexte conversationnel
    """

    async def build_context(
        self,
        session_id: str,
        db: AsyncSession
    ) -> ConversationContext:
        """
        Construit le contexte depuis:
        - Session history (last 10 turns)
        - User profile
        - Current topic
        """

        # Load session
        session = await self._load_session(session_id, db)

        # Load user profile
        profile = await self._load_profile(session.user_id, db)

        # Build context
        context = ConversationContext(
            session_id=session_id,
            user_id=session.user_id,
            profile=profile,
            history=session.turns[-10:],  # Last 10 turns
            current_topic=self._infer_topic(session.turns),
            pending_clarifications=self._get_pending_clarifications(session.turns)
        )

        return context
```

### 4. Proactive Assistant

```python
class ProactiveAssistant:
    """
    Génère des suggestions proactives
    """

    def generate_suggestions(
        self,
        context: ConversationContext,
        query_result: Dict
    ) -> List[str]:
        """
        Returns: [
            "💡 3 factures nécessitent une révision",
            "💡 Vous avez 2 doublons potentiels",
            "💡 Le fournisseur X a soumis 5 factures ce mois"
        ]
        """

        suggestions = []

        # 1. Based on query result
        if "needs_review_count" in query_result and query_result["needs_review_count"] > 0:
            suggestions.append(f"💡 {query_result['needs_review_count']} factures nécessitent une révision")

        # 2. Based on user profile
        if context.profile.interests and "duplicates" in context.profile.interests:
            # User is interested in duplicates, check
            duplicates = await self._check_duplicates(context.user_id)
            if duplicates > 0:
                suggestions.append(f"💡 Vous avez {duplicates} doublons potentiels")

        # 3. Based on patterns
        suggestions.extend(self._pattern_based_suggestions(context))

        return suggestions
```

---

## 🔄 Workflow Example

**Conversation** :

```
User: "Montre-moi les factures"
→ Intent: QUERY_INVOICE (0.95)
→ Entities: {} (nothing specific)
→ Context: user.copropriete_id = 5
→ Auto-apply filter: copropriete_id = 5
→ Execute SQL query
Response: "Voici les 15 factures pour Résidence Beausoleil:
           - FAC-001 (500€, Plomberie, needs review)
           - FAC-002 (1200€, Électricité)
           ...
           💡 3 factures nécessitent une révision"

User: "Montre seulement celles qui nécessitent révision"
→ Intent: QUERY_INVOICE (0.98)
→ Sub-Intent: NEEDS_REVIEW (0.90)
→ Context: Refine previous query
→ Execute SQL with needs_review = true
Response: "3 factures nécessitent une révision:
           - FAC-001 (500€, Plomberie) - Doublon possible
           - FAC-008 (15000€, Chauffage) - Montant anormal
           - FAC-012 (350€, Nettoyage) - Fournisseur non matché
           💡 Voulez-vous que je vous aide à les valider?"

User: "Oui aide-moi pour la première"
→ Intent: ACTION_UPDATE (0.85) + CLARIFICATION (0.70)
→ Entity: invoice_number = FAC-001 (resolved from "la première")
→ Context: Load FAC-001 details
Response: "FAC-001 - Plomberie Dupont - 500€

           🔍 Problème détecté: Doublon possible avec FAC-003

           Options:
           1. Marquer comme doublon et archiver
           2. Confirmer que c'est légitime
           3. Voir les détails comparatifs

           Que souhaitez-vous faire?"
```

---

## 📈 Metrics & Learning

### Metrics Tracked

1. **Intent Accuracy**
   - % of correctly classified intents
   - Confusion matrix (intent A misclassified as B)

2. **User Satisfaction**
   - Avg rating per session
   - Thumbs up/down ratio
   - Correction rate

3. **Context Effectiveness**
   - % queries where context helped
   - Reference resolution success rate

4. **Proactive Value**
   - % users who acted on suggestions
   - Avg suggestions per session

### Learning Mechanisms

1. **Intent Classifier Fine-tuning**
   - Collect misclassified examples
   - Re-train classifier monthly

2. **Profile Learning**
   - Update preferences based on actions
   - Adjust default filters

3. **Pattern Recognition**
   - Identify successful query patterns
   - Store as templates

---

## 🚀 Implementation Phases

**Phase 1: Foundation** (Week 1)
- Database models (ConversationSession, ConversationTurn, UserProfile)
- Session manager
- Basic context building

**Phase 2: Intelligence** (Week 2)
- Intent classifier
- Entity extractor
- Reference resolution

**Phase 3: Personalization** (Week 3)
- User profile system
- Preference learning
- Context-aware routing

**Phase 4: Proactive** (Week 4)
- Suggestion engine
- Pattern recognition
- Feedback loop

**Phase 5: Polish** (Week 5)
- UI integration
- Analytics dashboard
- Performance optimization

---

## 🎓 Next Steps

1. Create database models
2. Implement session manager
3. Build intent classifier
4. Integrate with existing orchestrator
5. Add user profile system
6. Implement learning loop
