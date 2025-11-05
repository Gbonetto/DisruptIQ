-- Migration: Conversational Intelligence
-- Tables pour l'intelligence conversationnelle et le machine learning

-- ==================== Conversation Sessions ====================

CREATE TABLE IF NOT EXISTS conversation_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,

    -- Timestamps
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,

    -- Summary
    turns_count INTEGER DEFAULT 0,
    topics JSONB DEFAULT '[]'::jsonb,
    intents_distribution JSONB DEFAULT '{}'::jsonb,

    -- Context
    current_topic VARCHAR(100),
    current_entities JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_conversation_sessions_session_id ON conversation_sessions(session_id);
CREATE INDEX idx_conversation_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX idx_conversation_sessions_started_at ON conversation_sessions(started_at);


-- ==================== Conversation Turns ====================

CREATE TABLE IF NOT EXISTS conversation_turns (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,

    -- Timestamp
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- User message
    user_message TEXT NOT NULL,
    user_message_cleaned TEXT,

    -- Intent detection
    detected_intent VARCHAR(100),
    intent_confidence FLOAT,
    all_intents JSONB DEFAULT '{}'::jsonb,
    sub_intents JSONB DEFAULT '[]'::jsonb,

    -- Entity extraction
    extracted_entities JSONB DEFAULT '{}'::jsonb,
    resolved_entities JSONB DEFAULT '{}'::jsonb,

    -- Assistant response
    assistant_message TEXT NOT NULL,
    response_type VARCHAR(50),
    sources_used JSONB DEFAULT '[]'::jsonb,

    -- Execution details
    agents_used JSONB DEFAULT '[]'::jsonb,
    execution_plan JSONB DEFAULT '{}'::jsonb,
    execution_time_ms INTEGER,
    orchestrator_mode VARCHAR(20),

    -- User feedback
    user_satisfied BOOLEAN,
    feedback_rating INTEGER CHECK (feedback_rating >= 1 AND feedback_rating <= 5),
    feedback_text TEXT,
    corrected_intent VARCHAR(100),

    -- Learning signals
    was_helpful BOOLEAN DEFAULT TRUE,
    led_to_action BOOLEAN DEFAULT FALSE,
    user_clicked_result BOOLEAN DEFAULT FALSE,
    user_refined_query BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_conversation_turns_session_id ON conversation_turns(session_id);
CREATE INDEX idx_conversation_turns_timestamp ON conversation_turns(timestamp);
CREATE INDEX idx_conversation_turns_detected_intent ON conversation_turns(detected_intent);
CREATE INDEX idx_conversation_turns_turn_number ON conversation_turns(turn_number);


-- ==================== User Profiles ====================

CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Learned preferences
    default_copropriete_id INTEGER REFERENCES coproprietes(id) ON DELETE SET NULL,
    preferred_date_range VARCHAR(50) DEFAULT 'last_30_days',
    preferred_response_style VARCHAR(20) DEFAULT 'detailed',
    preferred_language VARCHAR(10) DEFAULT 'fr',

    -- Usage patterns
    most_common_intents JSONB DEFAULT '{}'::jsonb,
    favorite_queries JSONB DEFAULT '[]'::jsonb,
    interaction_frequency VARCHAR(20),
    peak_usage_hours JSONB DEFAULT '[]'::jsonb,

    -- Personalization
    interests JSONB DEFAULT '[]'::jsonb,
    expertise_level VARCHAR(20) DEFAULT 'beginner',
    custom_preferences JSONB DEFAULT '{}'::jsonb,

    -- Statistics
    total_sessions INTEGER DEFAULT 0,
    total_turns INTEGER DEFAULT 0,
    avg_satisfaction FLOAT DEFAULT 0.0,
    avg_session_length FLOAT DEFAULT 0.0,

    -- Context memory
    recent_entities JSONB DEFAULT '{}'::jsonb,
    last_successful_queries JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    last_interaction_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);


-- ==================== Feedback Events ====================

CREATE TABLE IF NOT EXISTS feedback_events (
    id SERIAL PRIMARY KEY,
    turn_id INTEGER REFERENCES conversation_turns(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES conversation_sessions(id) ON DELETE SET NULL,

    -- Feedback type
    feedback_type VARCHAR(50) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,

    -- Implicit signals
    implicit_signal VARCHAR(50),
    signal_metadata JSONB DEFAULT '{}'::jsonb,

    -- Correction data
    original_intent VARCHAR(100),
    corrected_intent VARCHAR(100),
    original_entities JSONB DEFAULT '{}'::jsonb,
    corrected_entities JSONB DEFAULT '{}'::jsonb,

    -- Learning
    was_processed BOOLEAN DEFAULT FALSE,
    learning_impact VARCHAR(20),

    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_events_turn_id ON feedback_events(turn_id);
CREATE INDEX idx_feedback_events_feedback_type ON feedback_events(feedback_type);
CREATE INDEX idx_feedback_events_timestamp ON feedback_events(timestamp);


-- ==================== Comments ====================

COMMENT ON TABLE conversation_sessions IS 'Sessions de conversation avec historique complet';
COMMENT ON TABLE conversation_turns IS 'Tours de conversation individuels (user + assistant)';
COMMENT ON TABLE user_profiles IS 'Profils utilisateur avec préférences apprises automatiquement';
COMMENT ON TABLE feedback_events IS 'Événements de feedback utilisateur (explicite et implicite)';

COMMENT ON COLUMN conversation_sessions.session_id IS 'UUID unique de la session';
COMMENT ON COLUMN conversation_sessions.topics IS 'Liste des sujets abordés ["invoices", "suppliers"]';
COMMENT ON COLUMN conversation_sessions.intents_distribution IS 'Distribution des intents {"QUERY_INVOICE": 5}';

COMMENT ON COLUMN conversation_turns.detected_intent IS 'Intent principal détecté (QUERY_INVOICE, ACTION_CREATE, etc.)';
COMMENT ON COLUMN conversation_turns.all_intents IS 'Tous les intents détectés avec scores {"QUERY_INVOICE": 0.95}';
COMMENT ON COLUMN conversation_turns.sub_intents IS 'Sous-intents ["BY_AMOUNT", "BY_DATE"]';

COMMENT ON COLUMN user_profiles.most_common_intents IS 'Intents les plus fréquents {"QUERY_INVOICE": 0.45}';
COMMENT ON COLUMN user_profiles.expertise_level IS 'Niveau expertise: beginner, intermediate, expert';
COMMENT ON COLUMN user_profiles.interests IS 'Centres intérêt ["invoices", "duplicates"]';

COMMENT ON COLUMN feedback_events.feedback_type IS 'Type: thumbs_up, thumbs_down, correction, rating, implicit';
COMMENT ON COLUMN feedback_events.implicit_signal IS 'Signal implicite: clicked_result, refined_query, abandoned';


-- ==================== Sample Data (optional) ====================

-- Uncomment to insert sample user profiles for existing users
-- INSERT INTO user_profiles (user_id, preferred_response_style, expertise_level)
-- SELECT id, 'detailed', 'beginner'
-- FROM users
-- WHERE id NOT IN (SELECT user_id FROM user_profiles WHERE user_id IS NOT NULL);
