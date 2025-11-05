/*
 * Migration: Tables Factures OCR
 * Date: 2025-11-05
 * Description:
 *   - Crée tables factures_global et factures_details
 *   - Liens vers documents (doc_id), fournisseurs, copropriétés
 *   - Support extraction OCR avec validation TVA
 *   - Index pour recherches et agrégations
 *
 * IMPORTANT: Cette migration est IDEMPOTENTE (peut être rejouée sans risque)
 */

BEGIN;

-- ============================================================================
-- ÉTAPE 1: Table factures_global (en-tête facture)
-- ============================================================================

CREATE TABLE IF NOT EXISTS factures_global (
    id SERIAL PRIMARY KEY,

    -- Identification facture
    numero VARCHAR(100) NOT NULL,
    date_facture DATE NOT NULL,
    date_echeance DATE,

    -- Relations (FK seront ajoutées après)
    fournisseur_id INTEGER,  -- FK vers professionnels.id
    copropriete_id INTEGER,  -- FK vers coproprietes.id
    doc_id INTEGER,          -- FK vers documents.id (traçabilité OCR)

    -- Montants
    montant_ht NUMERIC(12,2) NOT NULL,
    montant_tva NUMERIC(12,2) NOT NULL,
    montant_ttc NUMERIC(12,2) NOT NULL,
    devise VARCHAR(3) DEFAULT 'EUR',

    -- Catégorie et statut
    categorie VARCHAR(100),  -- travaux, maintenance, fournitures, etc.
    statut VARCHAR(50) DEFAULT 'a_valider',  -- a_valider, validee, payee, annulee
    mode_paiement VARCHAR(50),  -- virement, cheque, cb, prelevement

    -- Extraction OCR
    extraction_method VARCHAR(50) DEFAULT 'ocr',  -- ocr, manual, import
    ocr_confidence NUMERIC(4,3),  -- 0.000-1.000
    needs_review BOOLEAN DEFAULT FALSE,

    -- Validation
    validated_by INTEGER,  -- user_id qui a validé
    validated_at TIMESTAMPTZ,

    -- Paiement
    date_paiement DATE,
    reference_paiement VARCHAR(100),

    -- Notes
    notes TEXT,

    -- Métadonnées
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Contraintes
    CONSTRAINT check_montants_coherence CHECK (montant_ttc = montant_ht + montant_tva),
    CONSTRAINT check_ocr_confidence CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)),
    CONSTRAINT unique_facture_numero_fournisseur UNIQUE(numero, fournisseur_id)
);

COMMENT ON TABLE factures_global IS
'Factures globales extraites par OCR avec liens fournisseur/copropriété/document';

COMMENT ON COLUMN factures_global.doc_id IS
'Lien vers document source (traçabilité OCR)';

COMMENT ON COLUMN factures_global.ocr_confidence IS
'Score de confiance OCR (0-1). < 0.8 → needs_review = true';

COMMENT ON COLUMN factures_global.needs_review IS
'TRUE si facture nécessite révision manuelle (faible confiance, incohérences)';

-- ============================================================================
-- ÉTAPE 2: Table factures_details (lignes de facture)
-- ============================================================================

CREATE TABLE IF NOT EXISTS factures_details (
    id SERIAL PRIMARY KEY,

    -- Relation
    facture_id INTEGER NOT NULL,

    -- Ligne
    ligne_numero INTEGER NOT NULL,  -- Numéro de ligne (1, 2, 3, ...)

    -- Article/Prestation
    article VARCHAR(500) NOT NULL,
    description TEXT,

    -- Quantités
    quantite NUMERIC(12,3) NOT NULL DEFAULT 1,
    unite VARCHAR(50) DEFAULT 'pce',  -- pce, m2, h, kg, etc.

    -- Prix
    prix_unitaire_ht NUMERIC(12,2) NOT NULL,
    taux_tva NUMERIC(5,2) NOT NULL,  -- Pourcentage (20.00 pour 20%)
    montant_ht NUMERIC(12,2) NOT NULL,
    montant_tva NUMERIC(12,2) NOT NULL,
    montant_ttc NUMERIC(12,2) NOT NULL,

    -- Analytique (optionnel)
    centre_cout VARCHAR(100),
    code_analytique VARCHAR(100),
    compte_comptable VARCHAR(50),

    -- Métadonnées
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    -- Contraintes
    CONSTRAINT fk_facture_detail_global FOREIGN KEY (facture_id)
        REFERENCES factures_global(id) ON DELETE CASCADE,
    CONSTRAINT check_montant_ht_calcul CHECK (montant_ht = quantite * prix_unitaire_ht),
    CONSTRAINT check_montant_tva_calcul CHECK (ABS(montant_tva - (montant_ht * taux_tva / 100)) < 0.01),
    CONSTRAINT unique_facture_ligne UNIQUE(facture_id, ligne_numero)
);

COMMENT ON TABLE factures_details IS
'Lignes de détail des factures (articles, quantités, prix)';

COMMENT ON COLUMN factures_details.taux_tva IS
'Taux TVA en pourcentage (ex: 20.00 pour 20%)';

COMMENT ON COLUMN factures_details.centre_cout IS
'Centre de coût pour répartition analytique (ex: "Batiment A", "Espaces verts")';

-- ============================================================================
-- ÉTAPE 3: Ajout des FK vers tables existantes
-- ============================================================================

-- FK vers professionnels (fournisseurs)
ALTER TABLE factures_global
DROP CONSTRAINT IF EXISTS fk_facture_fournisseur,
ADD CONSTRAINT fk_facture_fournisseur
    FOREIGN KEY (fournisseur_id) REFERENCES professionnels(id) ON DELETE SET NULL;

-- FK vers coproprietes
ALTER TABLE factures_global
DROP CONSTRAINT IF EXISTS fk_facture_copropriete,
ADD CONSTRAINT fk_facture_copropriete
    FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id) ON DELETE SET NULL;

-- FK vers documents (traçabilité OCR)
ALTER TABLE factures_global
DROP CONSTRAINT IF EXISTS fk_facture_document,
ADD CONSTRAINT fk_facture_document
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE SET NULL;

-- FK vers users (validation)
ALTER TABLE factures_global
DROP CONSTRAINT IF EXISTS fk_facture_validated_by,
ADD CONSTRAINT fk_facture_validated_by
    FOREIGN KEY (validated_by) REFERENCES users(id) ON DELETE SET NULL;

-- ============================================================================
-- ÉTAPE 4: Index pour performances
-- ============================================================================

-- Index sur factures_global
CREATE INDEX IF NOT EXISTS idx_factures_global_fournisseur ON factures_global(fournisseur_id);
CREATE INDEX IF NOT EXISTS idx_factures_global_copropriete ON factures_global(copropriete_id);
CREATE INDEX IF NOT EXISTS idx_factures_global_doc ON factures_global(doc_id);
CREATE INDEX IF NOT EXISTS idx_factures_global_date_facture ON factures_global(date_facture DESC);
CREATE INDEX IF NOT EXISTS idx_factures_global_statut ON factures_global(statut);
CREATE INDEX IF NOT EXISTS idx_factures_global_needs_review ON factures_global(needs_review) WHERE needs_review = TRUE;
CREATE INDEX IF NOT EXISTS idx_factures_global_numero ON factures_global(numero);
CREATE INDEX IF NOT EXISTS idx_factures_global_fournisseur_date ON factures_global(fournisseur_id, date_facture DESC);
CREATE INDEX IF NOT EXISTS idx_factures_global_copro_date ON factures_global(copropriete_id, date_facture DESC);
CREATE INDEX IF NOT EXISTS idx_factures_global_categorie ON factures_global(categorie);
CREATE INDEX IF NOT EXISTS idx_factures_global_created ON factures_global(created_at DESC);

-- Index GIN sur JSONB metadata
CREATE INDEX IF NOT EXISTS idx_factures_global_metadata_gin ON factures_global USING GIN (metadata);

-- Index sur factures_details
CREATE INDEX IF NOT EXISTS idx_factures_details_facture ON factures_details(facture_id);
CREATE INDEX IF NOT EXISTS idx_factures_details_ligne ON factures_details(facture_id, ligne_numero);
CREATE INDEX IF NOT EXISTS idx_factures_details_article ON factures_details(article);
CREATE INDEX IF NOT EXISTS idx_factures_details_centre_cout ON factures_details(centre_cout);

-- Index GIN sur JSONB metadata
CREATE INDEX IF NOT EXISTS idx_factures_details_metadata_gin ON factures_details USING GIN (metadata);

-- ============================================================================
-- ÉTAPE 5: Vue pour reporting factures
-- ============================================================================

-- View agrégée pour reporting
CREATE OR REPLACE VIEW vw_factures_resume AS
SELECT
    fg.id,
    fg.numero,
    fg.date_facture,
    fg.montant_ttc,
    fg.statut,
    fg.categorie,

    -- Fournisseur
    p.name as fournisseur_nom,
    p.company_name as fournisseur_societe,
    p.category as fournisseur_categorie,

    -- Copropriété
    c.nom as copropriete_nom,
    c.ville as copropriete_ville,

    -- Indicateurs
    fg.needs_review,
    fg.ocr_confidence,
    fg.date_paiement IS NOT NULL as est_payee,

    -- Compteurs
    (SELECT COUNT(*) FROM factures_details WHERE facture_id = fg.id) as nb_lignes,

    fg.created_at,
    fg.updated_at
FROM factures_global fg
LEFT JOIN professionnels p ON fg.fournisseur_id = p.id
LEFT JOIN coproprietes c ON fg.copropriete_id = c.id
ORDER BY fg.date_facture DESC;

COMMENT ON VIEW vw_factures_resume IS
'Vue résumé des factures avec infos fournisseur/copropriété pour reporting';

-- View détaillée pour export comptable
CREATE OR REPLACE VIEW vw_factures_comptable AS
SELECT
    fg.id as facture_id,
    fg.numero as facture_numero,
    fg.date_facture,

    fd.ligne_numero,
    fd.article,
    fd.quantite,
    fd.unite,
    fd.prix_unitaire_ht,
    fd.montant_ht,
    fd.taux_tva,
    fd.montant_tva,
    fd.montant_ttc,

    fd.centre_cout,
    fd.code_analytique,
    fd.compte_comptable,

    -- Fournisseur
    p.name as fournisseur,
    p.siret as fournisseur_siret,

    -- Copropriété
    c.nom as copropriete,
    c.reference_syndic

FROM factures_details fd
JOIN factures_global fg ON fd.facture_id = fg.id
LEFT JOIN professionnels p ON fg.fournisseur_id = p.id
LEFT JOIN coproprietes c ON fg.copropriete_id = c.id
ORDER BY fg.date_facture DESC, fg.numero, fd.ligne_numero;

COMMENT ON VIEW vw_factures_comptable IS
'Vue détaillée pour export comptable (toutes lignes avec analytique)';

-- ============================================================================
-- ÉTAPE 6: Statistiques PostgreSQL
-- ============================================================================

ANALYZE factures_global;
ANALYZE factures_details;

-- ============================================================================
-- Migration terminée ✅
-- ============================================================================

COMMIT;

/*
 * NOTES POST-MIGRATION:
 *
 * 1. Tables créées:
 *    - factures_global: En-têtes de factures
 *    - factures_details: Lignes de détail
 *
 * 2. Views créées:
 *    - vw_factures_resume: Résumé pour dashboards
 *    - vw_factures_comptable: Export comptable détaillé
 *
 * 3. FK créées:
 *    - factures_global → professionnels (fournisseur)
 *    - factures_global → coproprietes
 *    - factures_global → documents (traçabilité OCR)
 *    - factures_global → users (validation)
 *    - factures_details → factures_global (CASCADE)
 *
 * 4. Index créés: 18 index (11 sur global, 5 sur details, 2 GIN JSONB)
 *
 * 5. Contraintes de validation:
 *    - Cohérence montants (HT + TVA = TTC)
 *    - OCR confidence range (0-1)
 *    - Unicité (numero, fournisseur)
 *    - Calculs lignes (quantité * PU = montant HT)
 *
 * 6. Prochaines étapes:
 *    - Créer modèles SQLAlchemy (FactureGlobal, FactureDetail)
 *    - Implémenter service OCR extraction
 *    - Implémenter validation TVA
 *    - Créer endpoints API CRUD factures
 *    - Indexation Qdrant pour RAG
 *
 * 7. Queries utiles:
 *
 *    -- Factures à valider
 *    SELECT * FROM vw_factures_resume
 *    WHERE statut = 'a_valider' OR needs_review = TRUE;
 *
 *    -- Total factures par fournisseur (année en cours)
 *    SELECT
 *      fournisseur_nom,
 *      COUNT(*) as nb_factures,
 *      SUM(montant_ttc) as total_ttc
 *    FROM vw_factures_resume
 *    WHERE EXTRACT(YEAR FROM date_facture) = EXTRACT(YEAR FROM CURRENT_DATE)
 *    GROUP BY fournisseur_nom
 *    ORDER BY total_ttc DESC;
 *
 *    -- Factures par catégorie (mois en cours)
 *    SELECT
 *      categorie,
 *      COUNT(*) as nb,
 *      SUM(montant_ttc) as total
 *    FROM factures_global
 *    WHERE date_facture >= DATE_TRUNC('month', CURRENT_DATE)
 *    GROUP BY categorie;
 *
 * 8. Pour rollback (si nécessaire):
 *    DROP VIEW IF EXISTS vw_factures_comptable CASCADE;
 *    DROP VIEW IF EXISTS vw_factures_resume CASCADE;
 *    DROP TABLE IF EXISTS factures_details CASCADE;
 *    DROP TABLE IF EXISTS factures_global CASCADE;
 */
