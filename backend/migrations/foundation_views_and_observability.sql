/*
 * Migration: Foundation - Views Canoniques & Observabilité
 * Date: 2025-11-05
 * Description:
 *   - Crée les views SQL canoniques (read-only) pour SQL agent
 *   - Crée les tables agent_runs et agent_steps pour traçabilité
 *   - Ajoute les index pour performances
 *
 * IMPORTANT: Cette migration est IDEMPOTENTE (peut être rejouée sans risque)
 *
 * Objectifs:
 *   1. Sécuriser l'accès SQL agent via views-only
 *   2. Tracer chaque exécution d'agent avec cost_tokens
 *   3. Permettre audit et debugging des décisions
 */

BEGIN;

-- ============================================================================
-- ÉTAPE 1: Création des VIEWS SQL CANONIQUES (read-only pour SQL Agent)
-- ============================================================================

-- View Professionnels Minimale (pour queries fréquentes)
CREATE OR REPLACE VIEW vw_professionnels_min AS
SELECT
    id,
    name,
    company_name,
    category,
    email,
    phone,
    city,
    rating,
    statut,
    created_at,
    updated_at
FROM professionnels
WHERE statut = 'active' OR statut IS NULL;

COMMENT ON VIEW vw_professionnels_min IS
'View read-only pour SQL agent: professionnels actifs uniquement (champs essentiels)';

-- View Professionnels Complète (avec métadonnées RAG)
CREATE OR REPLACE VIEW vw_professionnels_full AS
SELECT
    p.id,
    p.name,
    p.company_name,
    p.category,
    p.email,
    p.phone,
    p.city,
    p.address,
    p.zip_code,
    p.rating,
    p.description,
    p.siret,
    p.statut,
    p.is_indexed,
    p.last_indexed_at,
    p.created_at,
    p.updated_at,
    -- Compte des relations
    COUNT(DISTINCT pc.copropriete_id) as nb_coproprietes,
    COUNT(DISTINCT d.id) as nb_documents,
    COUNT(DISTINCT e.id) as nb_emails
FROM professionnels p
LEFT JOIN professionnels_coproprietes pc ON p.id = pc.professionnel_id
LEFT JOIN documents d ON p.id = d.professionnel_id
LEFT JOIN emails e ON p.id = e.professionnel_id
WHERE p.statut = 'active' OR p.statut IS NULL
GROUP BY p.id;

COMMENT ON VIEW vw_professionnels_full IS
'View complète avec agrégations pour analyses complexes';

-- View Copropriétaires Contact (données de contact essentielles)
CREATE OR REPLACE VIEW vw_coproprietaires_contact AS
SELECT
    c.id,
    c.nom,
    c.prenom,
    c.email,
    c.telephone,
    c.telephone_mobile,
    c.copropriete_id,
    co.nom as copropriete_nom,
    co.adresse as copropriete_adresse,
    co.ville as copropriete_ville,
    c.numero_lot,
    c.etage,
    c.type_lot,
    c.statut,
    c.statut_special,
    c.est_resident,
    c.preferences_contact,
    c.created_at,
    c.updated_at
FROM coproprietaires c
LEFT JOIN coproprietes co ON c.copropriete_id = co.id;

COMMENT ON VIEW vw_coproprietaires_contact IS
'View pour contact des copropriétaires avec infos copropriété';

-- View Emails Urgents (pour dashboard et alertes)
CREATE OR REPLACE VIEW vw_emails_urgents AS
SELECT
    e.id,
    e.message_id,
    e.sender,
    e.recipient,
    e.subject,
    e.body,
    e.urgency,
    e.received_at,
    e.processed,
    e.included_in_digest,
    e.professionnel_id,
    p.name as professionnel_name,
    p.company_name as professionnel_company,
    e.copropriete_id,
    co.nom as copropriete_nom,
    e.created_at
FROM emails e
LEFT JOIN professionnels p ON e.professionnel_id = p.id
LEFT JOIN coproprietes co ON e.copropriete_id = co.id
WHERE e.urgency IN ('URGENT', 'IMPORTANT')
  AND e.processed = FALSE
ORDER BY
    CASE e.urgency
        WHEN 'URGENT' THEN 1
        WHEN 'IMPORTANT' THEN 2
        ELSE 3
    END,
    e.received_at DESC;

COMMENT ON VIEW vw_emails_urgents IS
'View des emails urgents et importants non traités (pour alertes)';

-- View Copropriétés avec Statistiques
CREATE OR REPLACE VIEW vw_coproprietes_stats AS
SELECT
    c.id,
    c.nom,
    c.adresse,
    c.ville,
    c.code_postal,
    c.nombre_lots,
    c.nombre_batiments,
    c.surface_totale,
    c.syndic,
    c.type_copropriete,
    c.is_indexed,
    c.created_at,
    c.updated_at,
    -- Statistiques
    COUNT(DISTINCT cp.id) as nb_coproprietaires,
    COUNT(DISTINCT pc.professionnel_id) as nb_professionnels,
    COUNT(DISTINCT d.id) as nb_documents,
    COUNT(DISTINCT e.id) as nb_emails
FROM coproprietes c
LEFT JOIN coproprietaires cp ON c.id = cp.copropriete_id
LEFT JOIN professionnels_coproprietes pc ON c.id = pc.copropriete_id
LEFT JOIN documents d ON c.id = d.copropriete_id
LEFT JOIN emails e ON c.id = e.copropriete_id
GROUP BY c.id;

COMMENT ON VIEW vw_coproprietes_stats IS
'View avec statistiques agrégées par copropriété';

-- View Documents Active (documents indexés seulement)
CREATE OR REPLACE VIEW vw_documents_active AS
SELECT
    d.id,
    d.filename,
    d.file_type,
    d.file_size,
    d.is_active,
    d.qdrant_id,
    d.professionnel_id,
    p.name as professionnel_name,
    d.copropriete_id,
    co.nom as copropriete_nom,
    d.coproprietaire_id,
    cp.nom as coproprietaire_nom,
    d.created_at,
    d.indexed_at
FROM documents d
LEFT JOIN professionnels p ON d.professionnel_id = p.id
LEFT JOIN coproprietes co ON d.copropriete_id = co.id
LEFT JOIN coproprietaires cp ON d.coproprietaire_id = cp.id
WHERE d.is_active = TRUE;

COMMENT ON VIEW vw_documents_active IS
'View des documents actifs uniquement (indexés dans Qdrant)';

-- ============================================================================
-- ÉTAPE 2: Création des TABLES D'OBSERVABILITÉ (agent_runs, agent_steps)
-- ============================================================================

-- Table agent_runs: trace chaque conversation/exécution
CREATE TABLE IF NOT EXISTS agent_runs (
    id SERIAL PRIMARY KEY,

    -- Identification
    conversation_id VARCHAR(100) NOT NULL,  -- UUID de la conversation
    user_id INTEGER,  -- FK vers users (optionnel pour l'instant)

    -- Classification
    intent VARCHAR(50),  -- "SQL_ONLY", "RAG_ONLY", "HYBRID", "EMAIL", "N8N", "WEB"
    source VARCHAR(50),  -- Source effective utilisée
    confidence NUMERIC(4,3),  -- Score de confiance (0.000-1.000)

    -- Plan d'exécution (JSON DAG)
    plan_json JSONB,  -- {"goal": "...", "steps": [...], "success": "..."}

    -- Résultats
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|running|success|failed|aborted
    error_message TEXT,
    output_summary TEXT,  -- Résumé de la réponse générée

    -- Métriques
    cost_tokens INTEGER,  -- Tokens total consommés
    cost_usd NUMERIC(10,6),  -- Coût USD estimé
    latency_ms INTEGER,  -- Latence totale en ms

    -- Sources utilisées
    sources_count INTEGER DEFAULT 0,  -- Nombre de sources (citations/rows)
    citations_json JSONB,  -- Array des citations avec IDs

    -- Conflits détectés
    has_conflicts BOOLEAN DEFAULT FALSE,
    conflicts_json JSONB,  -- Détails des conflits SQL vs RAG

    -- Évaluation
    evaluator_passed BOOLEAN,  -- TRUE si toutes les règles OK
    evaluator_rules_failed JSONB,  -- Array des règles échouées

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    -- Contraintes
    CONSTRAINT check_confidence_range CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT check_status_values CHECK (status IN ('pending', 'running', 'success', 'failed', 'aborted'))
);

COMMENT ON TABLE agent_runs IS
'Traçabilité des exécutions d''agents: plan, résultats, coûts, évaluation';

COMMENT ON COLUMN agent_runs.plan_json IS
'Plan d''exécution DAG au format: {"goal": str, "steps": [{"tool": str, "input": dict}], "success": str}';

COMMENT ON COLUMN agent_runs.citations_json IS
'Citations avec format: [{"id": str, "type": "rag"|"sql", "content": str, "confidence": float}]';

COMMENT ON COLUMN agent_runs.conflicts_json IS
'Conflits détectés: [{"field": str, "sql_value": any, "rag_value": any, "severity": "low"|"medium"|"high"}]';

-- Table agent_steps: trace chaque étape d'un run
CREATE TABLE IF NOT EXISTS agent_steps (
    id SERIAL PRIMARY KEY,

    -- Relation
    run_id INTEGER NOT NULL,

    -- Identification step
    step_number INTEGER NOT NULL,  -- Ordre dans le plan (0, 1, 2, ...)
    tool VARCHAR(100) NOT NULL,  -- "sql.plan", "sql.execute", "rag.search", etc.

    -- Input/Output
    input_json JSONB,  -- Paramètres d'entrée
    input_hash VARCHAR(64),  -- SHA256 de l'input (pour cache)
    output_json JSONB,  -- Résultat brut
    output_ref VARCHAR(200),  -- Référence externe (fichier, cache key, etc.)

    -- Résultat
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,

    -- Métriques
    latency_ms INTEGER,
    tokens_used INTEGER,
    evidence_count INTEGER DEFAULT 0,  -- Nombre d'éléments retournés (rows, chunks, etc.)

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    -- Contraintes
    CONSTRAINT fk_agent_run FOREIGN KEY (run_id)
        REFERENCES agent_runs(id) ON DELETE CASCADE,
    CONSTRAINT check_step_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped'))
);

COMMENT ON TABLE agent_steps IS
'Trace détaillée de chaque étape d''un agent run (plan → execution)';

COMMENT ON COLUMN agent_steps.tool IS
'Nom du skill exécuté: sql.plan, sql.execute, rag.search, rag.summarize, email.generate, etc.';

COMMENT ON COLUMN agent_steps.input_hash IS
'Hash SHA256 de l''input pour détecter queries identiques (cache, dedup)';

-- ============================================================================
-- ÉTAPE 3: Création des INDEX pour performances
-- ============================================================================

-- Index sur agent_runs
CREATE INDEX IF NOT EXISTS idx_agent_runs_conversation ON agent_runs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user ON agent_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_intent ON agent_runs(intent);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started ON agent_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_started ON agent_runs(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_has_conflicts ON agent_runs(has_conflicts) WHERE has_conflicts = TRUE;
CREATE INDEX IF NOT EXISTS idx_agent_runs_failed ON agent_runs(status) WHERE status IN ('failed', 'aborted');

-- Index GIN sur colonnes JSONB pour recherches dans le JSON
CREATE INDEX IF NOT EXISTS idx_agent_runs_plan_gin ON agent_runs USING GIN (plan_json);
CREATE INDEX IF NOT EXISTS idx_agent_runs_citations_gin ON agent_runs USING GIN (citations_json);
CREATE INDEX IF NOT EXISTS idx_agent_runs_conflicts_gin ON agent_runs USING GIN (conflicts_json);

-- Index sur agent_steps
CREATE INDEX IF NOT EXISTS idx_agent_steps_run ON agent_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_steps_tool ON agent_steps(tool);
CREATE INDEX IF NOT EXISTS idx_agent_steps_status ON agent_steps(status);
CREATE INDEX IF NOT EXISTS idx_agent_steps_run_step ON agent_steps(run_id, step_number);
CREATE INDEX IF NOT EXISTS idx_agent_steps_input_hash ON agent_steps(input_hash);
CREATE INDEX IF NOT EXISTS idx_agent_steps_started ON agent_steps(started_at DESC);

-- Index GIN pour recherches dans les inputs/outputs JSON
CREATE INDEX IF NOT EXISTS idx_agent_steps_input_gin ON agent_steps USING GIN (input_json);
CREATE INDEX IF NOT EXISTS idx_agent_steps_output_gin ON agent_steps USING GIN (output_json);

-- ============================================================================
-- ÉTAPE 4: Statistiques PostgreSQL
-- ============================================================================

ANALYZE agent_runs;
ANALYZE agent_steps;

-- ============================================================================
-- ÉTAPE 5: Grants (permissions read-only pour views)
-- ============================================================================

-- Les views sont accessible au même niveau que les tables sources
-- Pas de grants spécifiques nécessaires pour l'instant
-- TODO: Créer un rôle sql_agent_readonly avec accès views uniquement

-- ============================================================================
-- Migration terminée ✅
-- ============================================================================

COMMIT;

/*
 * NOTES POST-MIGRATION:
 *
 * 1. VIEWS SQL Canoniques:
 *    - vw_professionnels_min: Query fréquentes (liste, recherche)
 *    - vw_professionnels_full: Analyses avec agrégations
 *    - vw_coproprietaires_contact: Contacts avec infos copropriété
 *    - vw_emails_urgents: Dashboard alertes
 *    - vw_coproprietes_stats: Statistiques par copropriété
 *    - vw_documents_active: Documents indexés seulement
 *
 * 2. Tables Observabilité:
 *    - agent_runs: Trace conversation → plan → résultats → coûts
 *    - agent_steps: Trace chaque étape (tool) avec latence
 *
 * 3. Prochaines étapes:
 *    - Créer les modèles SQLAlchemy (AgentRun, AgentStep)
 *    - Implémenter le Planner DAG (génère plan_json)
 *    - Implémenter l'Evaluator (vérifie règles)
 *    - Mettre à jour l'orchestrateur pour logger dans ces tables
 *
 * 4. Queries utiles:
 *
 *    -- Top 10 queries par coût
 *    SELECT intent, AVG(cost_tokens), COUNT(*)
 *    FROM agent_runs
 *    WHERE status = 'success'
 *    GROUP BY intent
 *    ORDER BY AVG(cost_tokens) DESC
 *    LIMIT 10;
 *
 *    -- Taux de conflits SQL vs RAG
 *    SELECT
 *      COUNT(*) FILTER (WHERE has_conflicts) * 100.0 / COUNT(*) as conflict_rate_pct
 *    FROM agent_runs
 *    WHERE intent = 'HYBRID';
 *
 *    -- Latence moyenne par tool
 *    SELECT tool, AVG(latency_ms), COUNT(*)
 *    FROM agent_steps
 *    WHERE status = 'success'
 *    GROUP BY tool
 *    ORDER BY AVG(latency_ms) DESC;
 *
 *    -- Règles Evaluator échouées
 *    SELECT evaluator_rules_failed, COUNT(*)
 *    FROM agent_runs
 *    WHERE evaluator_passed = FALSE
 *    GROUP BY evaluator_rules_failed
 *    ORDER BY COUNT(*) DESC;
 *
 * 5. Sécurité SQL Agent:
 *    - TODO: Créer rôle PostgreSQL sql_agent_readonly
 *    - TODO: GRANT SELECT ONLY sur views (pas sur tables brutes)
 *    - TODO: REVOKE sur tables sensibles (users.hashed_password, etc.)
 *
 * 6. Pour rollback (si nécessaire):
 *    DROP VIEW IF EXISTS vw_professionnels_min CASCADE;
 *    DROP VIEW IF EXISTS vw_professionnels_full CASCADE;
 *    DROP VIEW IF EXISTS vw_coproprietaires_contact CASCADE;
 *    DROP VIEW IF EXISTS vw_emails_urgents CASCADE;
 *    DROP VIEW IF EXISTS vw_coproprietes_stats CASCADE;
 *    DROP VIEW IF EXISTS vw_documents_active CASCADE;
 *    DROP TABLE IF EXISTS agent_steps CASCADE;
 *    DROP TABLE IF EXISTS agent_runs CASCADE;
 */
