/*
 * Migration: Refonte BDD Syndic - DisruptIQ v2.0
 * Date: 2025-11-01
 * Description:
 *   - Renomme vendors → professionnels
 *   - Crée tables coproprietes, coproprietaires, professionnels_coproprietes
 *   - Ajoute relations et FK vers documents et emails
 *
 * IMPORTANT: Cette migration nécessite un downtime de 5-10 minutes
 *
 * Étapes:
 *   1. Création des nouvelles tables
 *   2. Renommage vendors → professionnels
 *   3. Ajout des nouvelles colonnes
 *   4. Migration des données
 *   5. Ajout des FK et contraintes
 *   6. Création des index
 */

BEGIN;

-- ============================================================================
-- ÉTAPE 1: Création des nouvelles tables
-- ============================================================================

-- Table Copropriétés
CREATE TABLE IF NOT EXISTS coproprietes (
    id SERIAL PRIMARY KEY,

    -- Identification
    nom VARCHAR NOT NULL,
    adresse TEXT NOT NULL,
    ville VARCHAR NOT NULL,
    code_postal VARCHAR(10) NOT NULL,

    -- Caractéristiques
    nombre_lots INTEGER,
    nombre_batiments INTEGER DEFAULT 1,
    annee_construction INTEGER,

    -- Gestion
    syndic VARCHAR,
    contact_syndic VARCHAR,
    reference_syndic VARCHAR,

    -- Informations complémentaires
    type_copropriete VARCHAR,
    surface_totale NUMERIC(10,2),
    equipements JSONB DEFAULT '[]'::jsonb,

    -- Notes
    notes TEXT,
    documents_path VARCHAR,

    -- Indexation RAG
    is_indexed BOOLEAN DEFAULT FALSE NOT NULL,
    last_indexed_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Table Copropriétaires
CREATE TABLE IF NOT EXISTS coproprietaires (
    id SERIAL PRIMARY KEY,

    -- Informations personnelles
    nom VARCHAR NOT NULL,
    prenom VARCHAR NOT NULL,
    email VARCHAR,
    telephone VARCHAR,
    telephone_mobile VARCHAR,

    -- Relation copropriété (FK)
    copropriete_id INTEGER NOT NULL,

    -- Informations lot
    numero_lot VARCHAR NOT NULL,
    type_lot VARCHAR,
    etage INTEGER,
    surface NUMERIC(8,2),

    -- Statut
    statut VARCHAR DEFAULT 'proprietaire',
    statut_special VARCHAR,  -- président, syndic, gardien, etc.
    est_resident BOOLEAN DEFAULT TRUE,
    date_acquisition DATE,

    -- Quotes-parts
    tantiemes INTEGER,

    -- Contact
    adresse_postale TEXT,
    preferences_contact JSONB DEFAULT '{"email": true, "sms": false}'::jsonb,

    -- Notes
    notes TEXT,

    -- Indexation RAG
    is_indexed BOOLEAN DEFAULT FALSE NOT NULL,
    last_indexed_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Contraintes
    CONSTRAINT unique_lot_per_copropriete UNIQUE(copropriete_id, numero_lot),
    CONSTRAINT fk_copropriete FOREIGN KEY (copropriete_id)
        REFERENCES coproprietes(id) ON DELETE CASCADE
);

-- ============================================================================
-- ÉTAPE 2: Renommage vendors → professionnels
-- ============================================================================

-- Renommer la table
ALTER TABLE vendors RENAME TO professionnels;

-- Renommer la séquence
ALTER SEQUENCE vendors_id_seq RENAME TO professionnels_id_seq;

-- ============================================================================
-- ÉTAPE 3: Ajout des nouvelles colonnes sur professionnels
-- ============================================================================

-- Nouvelles colonnes
ALTER TABLE professionnels
ADD COLUMN IF NOT EXISTS siret VARCHAR(14),
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS statut VARCHAR(20) DEFAULT 'active';

-- ============================================================================
-- ÉTAPE 4: Table de liaison Many-to-Many
-- ============================================================================

CREATE TABLE IF NOT EXISTS professionnels_coproprietes (
    professionnel_id INTEGER NOT NULL,
    copropriete_id INTEGER NOT NULL,

    -- Métadonnées
    date_debut DATE DEFAULT CURRENT_DATE,
    date_fin DATE,
    est_prestataire_principal BOOLEAN DEFAULT FALSE,

    -- Historique
    nombre_interventions INTEGER DEFAULT 0,
    derniere_intervention TIMESTAMPTZ,
    note_moyenne NUMERIC(3,2),

    -- Notes
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Clé primaire composite
    PRIMARY KEY (professionnel_id, copropriete_id),

    -- FK
    CONSTRAINT fk_professionnel FOREIGN KEY (professionnel_id)
        REFERENCES professionnels(id) ON DELETE CASCADE,
    CONSTRAINT fk_copropriete_liaison FOREIGN KEY (copropriete_id)
        REFERENCES coproprietes(id) ON DELETE CASCADE
);

-- ============================================================================
-- ÉTAPE 5: Ajout des nouvelles colonnes sur documents
-- ============================================================================

-- Nouvelles colonnes (sans FK pour l'instant)
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS professionnel_id INTEGER,
ADD COLUMN IF NOT EXISTS copropriete_id INTEGER,
ADD COLUMN IF NOT EXISTS coproprietaire_id INTEGER;

-- Migration des données vendor_id → professionnel_id
UPDATE documents SET professionnel_id = vendor_id WHERE vendor_id IS NOT NULL;

-- Ajout des FK
ALTER TABLE documents
DROP CONSTRAINT IF EXISTS fk_documents_professionnel,
DROP CONSTRAINT IF EXISTS fk_documents_copropriete,
DROP CONSTRAINT IF EXISTS fk_documents_coproprietaire;

ALTER TABLE documents
ADD CONSTRAINT fk_documents_professionnel
    FOREIGN KEY (professionnel_id) REFERENCES professionnels(id) ON DELETE SET NULL,
ADD CONSTRAINT fk_documents_copropriete
    FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id) ON DELETE SET NULL,
ADD CONSTRAINT fk_documents_coproprietaire
    FOREIGN KEY (coproprietaire_id) REFERENCES coproprietaires(id) ON DELETE SET NULL;

-- ============================================================================
-- ÉTAPE 6: Ajout des nouvelles colonnes sur emails
-- ============================================================================

-- Nouvelles colonnes
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS professionnel_id INTEGER,
ADD COLUMN IF NOT EXISTS copropriete_id INTEGER,
ADD COLUMN IF NOT EXISTS coproprietaire_id INTEGER;

-- Ajout des FK
ALTER TABLE emails
DROP CONSTRAINT IF EXISTS fk_emails_professionnel,
DROP CONSTRAINT IF EXISTS fk_emails_copropriete,
DROP CONSTRAINT IF EXISTS fk_emails_coproprietaire;

ALTER TABLE emails
ADD CONSTRAINT fk_emails_professionnel
    FOREIGN KEY (professionnel_id) REFERENCES professionnels(id) ON DELETE SET NULL,
ADD CONSTRAINT fk_emails_copropriete
    FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id) ON DELETE SET NULL,
ADD CONSTRAINT fk_emails_coproprietaire
    FOREIGN KEY (coproprietaire_id) REFERENCES coproprietaires(id) ON DELETE SET NULL;

-- ============================================================================
-- ÉTAPE 7: Création des index pour performances
-- ============================================================================

-- Index sur professionnels
CREATE INDEX IF NOT EXISTS idx_professionnels_email ON professionnels(email);
CREATE INDEX IF NOT EXISTS idx_professionnels_category ON professionnels(category);
CREATE INDEX IF NOT EXISTS idx_professionnels_city ON professionnels(city);
CREATE INDEX IF NOT EXISTS idx_professionnels_is_indexed ON professionnels(is_indexed);
CREATE INDEX IF NOT EXISTS idx_professionnels_statut ON professionnels(statut);
CREATE INDEX IF NOT EXISTS idx_professionnels_category_city ON professionnels(category, city);
CREATE INDEX IF NOT EXISTS idx_professionnels_not_indexed ON professionnels(is_indexed) WHERE is_indexed = FALSE;
CREATE INDEX IF NOT EXISTS idx_professionnels_created ON professionnels(created_at DESC);

-- Index sur coproprietes
CREATE INDEX IF NOT EXISTS idx_coproprietes_ville ON coproprietes(ville);
CREATE INDEX IF NOT EXISTS idx_coproprietes_code_postal ON coproprietes(code_postal);
CREATE INDEX IF NOT EXISTS idx_coproprietes_syndic ON coproprietes(syndic);
CREATE INDEX IF NOT EXISTS idx_coproprietes_is_indexed ON coproprietes(is_indexed);
CREATE INDEX IF NOT EXISTS idx_coproprietes_ville_code_postal ON coproprietes(ville, code_postal);
CREATE INDEX IF NOT EXISTS idx_coproprietes_not_indexed ON coproprietes(is_indexed) WHERE is_indexed = FALSE;
CREATE INDEX IF NOT EXISTS idx_coproprietes_created ON coproprietes(created_at DESC);

-- Index sur coproprietaires
CREATE INDEX IF NOT EXISTS idx_coproprietaires_copropriete ON coproprietaires(copropriete_id);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_email ON coproprietaires(email);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_nom ON coproprietaires(nom);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_prenom ON coproprietaires(prenom);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_nom_prenom ON coproprietaires(nom, prenom);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_statut ON coproprietaires(statut);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_numero_lot ON coproprietaires(numero_lot);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_is_indexed ON coproprietaires(is_indexed);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_copro_statut ON coproprietaires(copropriete_id, statut);
CREATE INDEX IF NOT EXISTS idx_coproprietaires_not_indexed ON coproprietaires(is_indexed) WHERE is_indexed = FALSE;

-- Index sur professionnels_coproprietes
CREATE INDEX IF NOT EXISTS idx_prof_copro_professionnel ON professionnels_coproprietes(professionnel_id);
CREATE INDEX IF NOT EXISTS idx_prof_copro_copropriete ON professionnels_coproprietes(copropriete_id);
CREATE INDEX IF NOT EXISTS idx_prof_copro_actif ON professionnels_coproprietes(date_fin) WHERE date_fin IS NULL;

-- Index sur documents (nouvelles colonnes)
CREATE INDEX IF NOT EXISTS idx_documents_professionnel ON documents(professionnel_id);
CREATE INDEX IF NOT EXISTS idx_documents_copropriete ON documents(copropriete_id);
CREATE INDEX IF NOT EXISTS idx_documents_coproprietaire ON documents(coproprietaire_id);

-- Index sur emails (nouvelles colonnes)
CREATE INDEX IF NOT EXISTS idx_emails_professionnel ON emails(professionnel_id);
CREATE INDEX IF NOT EXISTS idx_emails_copropriete ON emails(copropriete_id);
CREATE INDEX IF NOT EXISTS idx_emails_coproprietaire ON emails(coproprietaire_id);

-- ============================================================================
-- ÉTAPE 8: Mise à jour des statistiques PostgreSQL
-- ============================================================================

ANALYZE professionnels;
ANALYZE coproprietes;
ANALYZE coproprietaires;
ANALYZE professionnels_coproprietes;
ANALYZE documents;
ANALYZE emails;

COMMIT;

-- ============================================================================
-- Migration terminée ✅
-- ============================================================================

/*
 * NOTES POST-MIGRATION:
 *
 * 1. Les anciennes colonnes documents.vendor_id et documents.property_id sont conservées
 *    mais deprecated. Elles peuvent être supprimées après confirmation que tout fonctionne:
 *
 *    ALTER TABLE documents DROP COLUMN vendor_id, DROP COLUMN property_id;
 *
 * 2. Tous les vendors existants ont été migrés vers professionnels avec statut='active'
 *
 * 3. Pour réindexer toutes les nouvelles entités dans Qdrant:
 *    - Professionnels: POST /api/admin/vendors/reindex (endpoint existe déjà)
 *    - Copropriétés: POST /api/admin/coproprietes/reindex (à créer)
 *    - Copropriétaires: POST /api/admin/coproprietaires/reindex (à créer)
 *
 * 4. Test de la migration:
 *    - Vérifier que les professionnels sont accessibles
 *    - Vérifier que les FK fonctionnent
 *    - Vérifier que les index sont utilisés
 *
 * 5. Pour rollback (si nécessaire):
 *    - Exécuter migrations/rollback_refonte_bdd_syndic.sql
 */
