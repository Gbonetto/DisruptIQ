-- Comprehensive test data for all DisruptIQ SQL tables
-- Execute with: docker exec -i disruptiq_postgres psql -U disruptiq -d disruptiq < backend/seed_all_tables.sql

-- ============================================
-- 1. COPROPRIÉTÉS (Buildings/Residences)
-- ============================================
INSERT INTO coproprietes (nom, adresse, ville, code_postal, nombre_lots, nombre_batiments, created_at)
VALUES
    ('Les Mimosas', '15 Avenue des Mimosas', 'Paris', '75016', 45, 1, NOW() - INTERVAL '6 months'),
    ('Résidence du Parc', '42 Rue du Parc', 'Boulogne-Billancourt', '92100', 62, 2, NOW() - INTERVAL '5 months'),
    ('Le Clos Saint-Martin', '8 Place Saint-Martin', 'Versailles', '78000', 28, 1, NOW() - INTERVAL '4 months'),
    ('Villa des Roses', '23 Allée des Roses', 'Neuilly-sur-Seine', '92200', 34, 1, NOW() - INTERVAL '3 months'),
    ('Résidence Harmonie', '56 Boulevard de l''Harmonie', 'Paris', '75015', 52, 3, NOW() - INTERVAL '2 months')
ON CONFLICT DO NOTHING;

-- ============================================
-- 2. COPROPRIÉTAIRES (Co-owners/Residents)
-- ============================================
-- Les Mimosas residents
INSERT INTO coproprietaires (nom, prenom, email, telephone, copropriete_id, numero_lot, type_lot, etage, surface, created_at)
SELECT
    'Durant', 'Sophie', 'sophie.durant@gmail.com', '06 12 34 56 78',
    id, '302', 'Appartement', 3, 75.50, NOW() - INTERVAL '6 months'
FROM coproprietes WHERE nom = 'Les Mimosas'
UNION ALL
SELECT
    'Bertrand', 'Michel', 'michel.bertrand@yahoo.fr', '06 23 45 67 89',
    id, '105', 'Appartement', 1, 58.30, NOW() - INTERVAL '6 months'
FROM coproprietes WHERE nom = 'Les Mimosas'
UNION ALL
SELECT
    'Leroy', 'Catherine', 'c.leroy@hotmail.com', '06 34 56 78 90',
    id, '204', 'Appartement', 2, 82.00, NOW() - INTERVAL '5 months'
FROM coproprietes WHERE nom = 'Les Mimosas'

UNION ALL

-- Résidence du Parc residents
SELECT
    'Dubois', 'Pierre', 'pierre.dubois@orange.fr', '06 45 67 89 01',
    id, 'A301', 'Appartement', 3, 92.50, NOW() - INTERVAL '5 months'
FROM coproprietes WHERE nom = 'Résidence du Parc'
UNION ALL
SELECT
    'Moreau', 'Anne', 'anne.moreau@gmail.com', '06 56 78 90 12',
    id, 'B102', 'Appartement', 1, 65.20, NOW() - INTERVAL '5 months'
FROM coproprietes WHERE nom = 'Résidence du Parc'
UNION ALL
SELECT
    'Lambert', 'François', 'f.lambert@free.fr', '06 67 89 01 23',
    id, 'A205', 'Appartement', 2, 78.40, NOW() - INTERVAL '4 months'
FROM coproprietes WHERE nom = 'Résidence du Parc'

UNION ALL

-- Le Clos Saint-Martin residents
SELECT
    'Roux', 'Isabelle', 'isabelle.roux@wanadoo.fr', '06 78 90 12 34',
    id, '12', 'Maison', 0, 125.00, NOW() - INTERVAL '4 months'
FROM coproprietes WHERE nom = 'Le Clos Saint-Martin'
UNION ALL
SELECT
    'Garnier', 'Jean', 'jean.garnier@gmail.com', '06 89 01 23 45',
    id, '8', 'Maison', 0, 110.50, NOW() - INTERVAL '3 months'
FROM coproprietes WHERE nom = 'Le Clos Saint-Martin'

UNION ALL

-- Villa des Roses residents
SELECT
    'Faure', 'Marie', 'marie.faure@outlook.com', '06 90 12 34 56',
    id, '501', 'Appartement', 5, 95.00, NOW() - INTERVAL '3 months'
FROM coproprietes WHERE nom = 'Villa des Roses'
UNION ALL
SELECT
    'Blanc', 'Patrick', 'p.blanc@yahoo.fr', '06 01 23 45 67',
    id, '203', 'Appartement', 2, 72.30, NOW() - INTERVAL '2 months'
FROM coproprietes WHERE nom = 'Villa des Roses'

UNION ALL

-- Résidence Harmonie residents
SELECT
    'Girard', 'Nathalie', 'nathalie.girard@gmail.com', '06 12 45 78 90',
    id, '401', 'Appartement', 4, 88.50, NOW() - INTERVAL '2 months'
FROM coproprietes WHERE nom = 'Résidence Harmonie'
UNION ALL
SELECT
    'Bonnet', 'Olivier', 'o.bonnet@free.fr', '06 23 56 89 01',
    id, '102', 'Appartement', 1, 62.00, NOW() - INTERVAL '1 month'
FROM coproprietes WHERE nom = 'Résidence Harmonie';

-- ============================================
-- 3. PROFESSIONNELS (Service Providers)
-- ============================================
-- Already seeded in seed_professionnels.sql, but adding more variety
INSERT INTO professionnels (name, company_name, email, phone, category, address, city, postal_code, rating, statut, siret, description, is_indexed, created_at)
VALUES
    -- Additional plombiers
    ('Robert Durand', 'Durand Plomberie Pro', 'r.durand@plomberie-pro.fr', '06 11 22 33 44', 'plombier', '101 Rue de Vaugirard', 'Paris', '75015', 4.6, 'active', '11223344556677', 'Spécialiste fuites et débouchage', false, NOW()),

    -- Menuisiers
    ('Alain Carpentier', 'Carpentier Menuiserie', 'a.carpentier@menuiserie.fr', '06 22 33 44 55', 'menuisier', '45 Rue des Artisans', 'Paris', '75011', 4.7, 'active', '22334455667788', 'Portes, fenêtres, parquet', false, NOW()),
    ('Claire Boisvert', 'Boisvert & Fils', 'c.boisvert@boisvert.fr', '06 33 44 55 66', 'menuisier', '78 Avenue du Bois', 'Versailles', '78000', 4.5, 'active', '33445566778899', 'Aménagement sur-mesure, escaliers', false, NOW()),

    -- Chauffagistes
    ('Marc Thermostat', 'Thermostat Chauffage', 'm.thermostat@chauffage.fr', '06 44 55 66 77', 'chauffagiste', '12 Rue du Chauffage', 'Paris', '75012', 4.8, 'active', '44556677889900', 'Installation chaudières, radiateurs', false, NOW()),
    ('Sylvie Chaleur', 'Chaleur Confort', 's.chaleur@confort.fr', '06 55 66 77 88', 'chauffagiste', '34 Boulevard Thermal', 'Boulogne-Billancourt', '92100', 4.6, 'active', '55667788990011', 'Climatisation, pompes à chaleur', false, NOW()),

    -- Maçons
    ('Denis Pierrefort', 'Pierrefort Maçonnerie', 'd.pierrefort@maconnerie.fr', '06 66 77 88 99', 'maçon', '56 Rue des Bâtisseurs', 'Neuilly-sur-Seine', '92200', 4.4, 'active', '66778899001122', 'Rénovation façades, gros œuvre', false, NOW()),
    ('Éric Ciment', 'Ciment & Pierre SARL', 'e.ciment@ciment-pierre.fr', '06 77 88 99 00', 'maçon', '89 Avenue Masséna', 'Paris', '75013', 4.7, 'active', '77889900112233', 'Murs porteurs, fondations', false, NOW())
ON CONFLICT DO NOTHING;

-- ============================================
-- 4. EMAILS (Test emails for digest feature)
-- ============================================
INSERT INTO emails (message_id, sender, subject, body, urgency, received_at, processed)
VALUES
    -- Urgent emails
    ('msg-urgent-001', 'sophie.durant@gmail.com', 'URGENT: Dégât des eaux appartement 302',
     'Bonjour, il y a un dégât des eaux important dans mon appartement. L''eau coule du plafond depuis ce matin. J''ai besoin d''une intervention immédiate. Merci de me contacter au plus vite.',
     'URGENT', NOW() - INTERVAL '2 hours', false),

    ('msg-urgent-002', 'michel.bertrand@yahoo.fr', 'Fuite gaz - Urgent',
     'J''ai détecté une odeur de gaz dans mon appartement. J''ai coupé l''arrivée mais il faut intervenir rapidement. Appartement 105, Les Mimosas.',
     'URGENT', NOW() - INTERVAL '4 hours', false),

    ('msg-urgent-003', 'syndic@residence-parc.fr', 'Panne ascenseur - Personne bloquée',
     'Une personne est bloquée dans l''ascenseur de la Résidence du Parc. Les pompiers ont été appelés. Merci de contacter le réparateur en urgence.',
     'URGENT', NOW() - INTERVAL '1 hour', false),

    -- Important emails
    ('msg-important-001', 'marie.faure@outlook.com', 'Demande devis rénovation salle de bain',
     'Bonjour, je souhaiterais obtenir un devis pour la rénovation complète de ma salle de bain. Surface environ 8m². Merci de me contacter pour organiser une visite.',
     'IMPORTANT', NOW() - INTERVAL '6 hours', false),

    ('msg-important-002', 'j.dubois@plomberie-dubois.fr', 'Confirmation intervention mardi',
     'Bonjour, je confirme mon intervention pour le mardi 5 novembre à 14h pour la réparation de la fuite au 3ème étage. Cordialement.',
     'IMPORTANT', NOW() - INTERVAL '8 hours', false),

    ('msg-important-003', 'nathalie.girard@gmail.com', 'Problème chauffage collectif',
     'Le chauffage ne fonctionne pas dans les appartements du 4ème étage depuis hier. La température est descendue à 16°C. Pouvez-vous faire intervenir le chauffagiste ?',
     'IMPORTANT', NOW() - INTERVAL '5 hours', false),

    ('msg-important-004', 'conseil-syndical@mimosas.fr', 'Ordre du jour AG du 15 novembre',
     'Veuillez trouver ci-joint l''ordre du jour de l''assemblée générale qui se tiendra le 15 novembre à 18h30. Points principaux: vote travaux, budget 2025, élection conseil syndical.',
     'IMPORTANT', NOW() - INTERVAL '12 hours', false),

    -- Routine emails
    ('msg-routine-001', 'entretien@espaces-verts.fr', 'Passage tonte hebdomadaire',
     'Bonjour, nous passerons comme prévu jeudi matin pour l''entretien des espaces verts. Cordialement.',
     'ROUTINE', NOW() - INTERVAL '1 day', false),

    ('msg-routine-002', 'factures@edf.fr', 'Votre facture électricité - Novembre 2025',
     'Votre facture d''électricité de novembre 2025 est disponible. Montant: 145.50€. Prélèvement prévu le 15 novembre.',
     'ROUTINE', NOW() - INTERVAL '1 day', false),

    ('msg-routine-003', 'assurance@copro-assur.fr', 'Rappel échéance assurance',
     'Votre contrat d''assurance copropriété arrive à échéance le 31 décembre. Nous vous ferons parvenir votre proposition de renouvellement début décembre.',
     'ROUTINE', NOW() - INTERVAL '2 days', false),

    ('msg-routine-004', 'info@mairie-paris16.fr', 'Newsletter municipale - Novembre',
     'Découvrez les événements culturels et sportifs du mois de novembre dans votre arrondissement. Programme complet sur notre site.',
     'ROUTINE', NOW() - INTERVAL '3 days', false),

    ('msg-routine-005', 'p.blanc@yahoo.fr', 'Demande coordonnées plombier',
     'Bonjour, pourriez-vous me transmettre les coordonnées du plombier habituel de la résidence ? J''ai un petit robinet qui fuit. Merci.',
     'ROUTINE', NOW() - INTERVAL '10 hours', false)
ON CONFLICT (message_id) DO NOTHING;

-- ============================================
-- Display summary
-- ============================================
SELECT '=== RÉSUMÉ DES DONNÉES INSÉRÉES ===' as info;

SELECT 'Copropriétés:' as table_name, COUNT(*) as count FROM coproprietes
UNION ALL
SELECT 'Copropriétaires:', COUNT(*) FROM coproprietaires
UNION ALL
SELECT 'Professionnels:', COUNT(*) FROM professionnels
UNION ALL
SELECT 'Emails:', COUNT(*) FROM emails;

SELECT '=== EMAILS PAR URGENCE ===' as info;
SELECT urgency, COUNT(*) as count FROM emails GROUP BY urgency ORDER BY
    CASE urgency
        WHEN 'URGENT' THEN 1
        WHEN 'IMPORTANT' THEN 2
        WHEN 'ROUTINE' THEN 3
    END;

SELECT '=== PROFESSIONNELS PAR CATÉGORIE ===' as info;
SELECT category, COUNT(*) as count FROM professionnels
GROUP BY category
ORDER BY count DESC;

SELECT '=== COPROPRIÉTAIRES PAR COPROPRIÉTÉ ===' as info;
SELECT c.nom as copropriete, COUNT(cp.id) as nb_coproprietaires
FROM coproprietes c
LEFT JOIN coproprietaires cp ON c.id = cp.copropriete_id
GROUP BY c.nom
ORDER BY nb_coproprietaires DESC;
