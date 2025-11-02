-- Script d'insertion de données de test pour les professionnels
-- Pour tester les requêtes SQL de l'assistant

INSERT INTO professionnels (name, company_name, email, phone, category, address, city, postal_code, rating, statut, siret, description, is_indexed, created_at)
VALUES
    ('Jean Dubois', 'Dubois Plomberie', 'j.dubois@plomberie-dubois.fr', '06 12 34 56 78', 'plombier', '12 Rue de la Fontaine', 'Paris', '75015', 4.5, 'active', '12345678901234', 'Plomberie générale, dépannage urgence 24/7', false, NOW()),
    ('Marie Martin', 'Martin & Fils Plomberie', 'contact@martin-plomberie.fr', '06 23 45 67 89', 'plombier', '45 Avenue des Champs', 'Paris', '75008', 4.8, 'active', '23456789012345', 'Spécialiste chauffage et sanitaire', false, NOW()),
    ('Pierre Leclerc', 'Leclerc Plomberie Services', 'p.leclerc@gmail.com', '06 34 56 78 90', 'plombier', '78 Boulevard Victor Hugo', 'Neuilly-sur-Seine', '92200', 4.2, 'active', '34567890123456', 'Rénovation salle de bain, installation cuisine', false, NOW()),

    ('Sophie Bernard', 'Bernard Électricité', 's.bernard@electricite-bernard.fr', '06 45 67 89 01', 'électricien', '23 Rue de la République', 'Paris', '75011', 4.6, 'active', '45678901234567', 'Installation électrique, mise aux normes', false, NOW()),
    ('Luc Petit', 'Électricité Petit', 'luc.petit@elec-petit.fr', '06 56 78 90 12', 'électricien', '56 Rue du Commerce', 'Paris', '75015', 4.4, 'active', '56789012345678', 'Domotique, alarmes, vidéosurveillance', false, NOW()),

    ('André Garcia', 'Garcia Peinture', 'a.garcia@garcia-peinture.fr', '06 67 89 01 23', 'peintre', '89 Avenue de la Liberté', 'Boulogne-Billancourt', '92100', 4.7, 'active', '67890123456789', 'Peinture intérieure et extérieure, ravalement', false, NOW()),
    ('Isabelle Moreau', 'Moreau Décoration', 'i.moreau@moreau-deco.fr', '06 78 90 12 34', 'peintre', '12 Place de l''Église', 'Issy-les-Moulineaux', '92130', 4.9, 'active', '78901234567890', 'Peinture décorative, papier peint, enduits', false, NOW()),

    ('François Laurent', 'Laurent Jardins', 'f.laurent@laurent-jardins.fr', '06 89 01 23 45', 'jardinier', '34 Chemin des Roses', 'Versailles', '78000', 4.3, 'active', '89012345678901', 'Entretien espaces verts, taille, tonte', false, NOW()),
    ('Nathalie Simon', 'Simon Paysage', 'n.simon@simon-paysage.fr', '06 90 12 34 56', 'jardinier', '67 Route de Saint-Cloud', 'Sèvres', '92310', 4.8, 'active', '90123456789012', 'Création jardins, élagage, débroussaillage', false, NOW()),

    ('Thomas Lefebvre', 'Lefebvre Serrurerie', 't.lefebvre@serrurier-lefebvre.fr', '06 01 23 45 67', 'serrurier', '90 Boulevard Haussmann', 'Paris', '75009', 4.5, 'active', '01234567890123', 'Ouverture porte, changement serrures 24/7', false, NOW());

-- Afficher le résultat
SELECT COUNT(*) as total_professionnels FROM professionnels;
SELECT category, COUNT(*) as count FROM professionnels GROUP BY category ORDER BY count DESC;
