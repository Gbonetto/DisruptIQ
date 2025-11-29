"""
SQL Test Fixtures for DisruptIQ E2E Tests

Provides comprehensive test data for two copropriétés:
- Les Mimosas (50 lots, 5 bâtiments, construction 1975)
- Les Platanes (30 lots, 2 bâtiments, construction 1992)

Includes:
- Copropriétaires with diverse profiles
- Professionnels (plombiers, électriciens, etc.)
- Emails with various urgency levels
- Documents metadata

Usage:
    from tests.fixtures.sql_fixtures import SQLFixtures

    async def test_example(async_session):
        fixtures = SQLFixtures(async_session)
        await fixtures.load_all()
        # Test with loaded data
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SQLFixtures:
    """
    Comprehensive SQL fixtures for E2E testing.
    Loads realistic test data for the DisruptIQ system.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_all(self):
        """Load all fixtures in correct order (respecting FK constraints)"""
        await self.create_tables()
        await self.load_coproprietes()
        await self.load_coproprietaires()
        await self.load_professionnels()
        await self.load_emails()
        await self.load_documents()
        await self.session.commit()

    async def create_tables(self):
        """Create tables if they don't exist (for SQLite in-memory testing)"""
        # Copropriétés
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS coproprietes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom VARCHAR(255) NOT NULL,
                adresse TEXT,
                ville VARCHAR(100) NOT NULL,
                code_postal VARCHAR(10) NOT NULL,
                nombre_lots INTEGER,
                nombre_batiments INTEGER,
                annee_construction INTEGER,
                syndic VARCHAR(255),
                contact_syndic VARCHAR(255),
                reference_syndic VARCHAR(100),
                type_copropriete VARCHAR(50),
                surface_totale REAL,
                budget_annuel REAL,
                date_derniere_ag TIMESTAMP,
                is_indexed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Copropriétaires
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS coproprietaires (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom VARCHAR(255) NOT NULL,
                prenom VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                telephone VARCHAR(50),
                telephone_mobile VARCHAR(50),
                copropriete_id INTEGER NOT NULL,
                numero_lot VARCHAR(50) NOT NULL,
                type_lot VARCHAR(50),
                etage INTEGER,
                surface REAL,
                tantiemes INTEGER,
                statut VARCHAR(50) DEFAULT 'proprietaire',
                statut_special VARCHAR(50),
                est_resident BOOLEAN DEFAULT TRUE,
                date_acquisition TIMESTAMP,
                solde_compte REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id)
            )
        """))

        # Professionnels
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS professionnels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                company_name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(50),
                siret VARCHAR(14),
                description TEXT,
                statut VARCHAR(20) DEFAULT 'active',
                category VARCHAR(100),
                address TEXT,
                city VARCHAR(100),
                postal_code VARCHAR(10),
                rating REAL,
                total_jobs INTEGER DEFAULT 0,
                derniere_intervention TIMESTAMP,
                is_indexed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Junction table for professionnels <-> coproprietes
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS professionnels_coproprietes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professionnel_id INTEGER,
                copropriete_id INTEGER,
                date_premiere_intervention TIMESTAMP,
                nombre_interventions INTEGER DEFAULT 0,
                note_satisfaction REAL,
                FOREIGN KEY (professionnel_id) REFERENCES professionnels(id),
                FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id)
            )
        """))

        # Emails
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id VARCHAR(255) UNIQUE,
                thread_id VARCHAR(255),
                sender VARCHAR(255),
                recipient VARCHAR(255),
                subject VARCHAR(500),
                body TEXT,
                snippet TEXT,
                urgency VARCHAR(20) DEFAULT 'ROUTINE',
                category VARCHAR(100),
                copropriete_id INTEGER,
                coproprietaire_id INTEGER,
                received_at TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE,
                processed_at TIMESTAMP,
                response_sent BOOLEAN DEFAULT FALSE,
                attachments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id),
                FOREIGN KEY (coproprietaire_id) REFERENCES coproprietaires(id)
            )
        """))

        # Documents (metadata)
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre VARCHAR(500),
                type_document VARCHAR(100),
                copropriete_id INTEGER,
                date_document TIMESTAMP,
                chemin_fichier VARCHAR(500),
                taille_fichier INTEGER,
                hash_fichier VARCHAR(64),
                is_indexed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (copropriete_id) REFERENCES coproprietes(id)
            )
        """))

        await self.session.commit()

    async def load_coproprietes(self):
        """Load the two main copropriétés for testing"""
        coproprietes = [
            {
                "nom": "Les Mimosas",
                "adresse": "15 Rue des Mimosas",
                "ville": "Paris",
                "code_postal": "75015",
                "nombre_lots": 50,
                "nombre_batiments": 5,
                "annee_construction": 1975,
                "syndic": "Syndic Parisien SA",
                "contact_syndic": "contact@syndic-parisien.fr",
                "reference_syndic": "MIM-2020-001",
                "type_copropriete": "résidentiel",
                "surface_totale": 4250.5,
                "budget_annuel": 125000.0,
                "date_derniere_ag": datetime(2024, 6, 15),
                "is_indexed": True
            },
            {
                "nom": "Les Platanes",
                "adresse": "8 Avenue des Platanes",
                "ville": "Lyon",
                "code_postal": "69003",
                "nombre_lots": 30,
                "nombre_batiments": 2,
                "annee_construction": 1992,
                "syndic": "Gestion Immobilière Lyon",
                "contact_syndic": "contact@gi-lyon.fr",
                "reference_syndic": "PLT-2021-042",
                "type_copropriete": "mixte",
                "surface_totale": 2800.0,
                "budget_annuel": 85000.0,
                "date_derniere_ag": datetime(2024, 9, 20),
                "is_indexed": True
            }
        ]

        for copro in coproprietes:
            columns = ", ".join(copro.keys())
            placeholders = ", ".join([f":{k}" for k in copro.keys()])
            await self.session.execute(
                text(f"INSERT INTO coproprietes ({columns}) VALUES ({placeholders})"),
                copro
            )

    async def load_coproprietaires(self):
        """Load copropriétaires for both buildings"""
        # Les Mimosas (id=1) - 12 copropriétaires variés
        mimosas_owners = [
            {"nom": "Dupont", "prenom": "Jean-Pierre", "email": "jp.dupont@gmail.com",
             "telephone": "01 45 67 89 10", "telephone_mobile": "06 12 34 56 78",
             "copropriete_id": 1, "numero_lot": "A101", "type_lot": "Appartement",
             "etage": 1, "surface": 75.5, "tantiemes": 850, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Martin", "prenom": "Sophie", "email": "s.martin@orange.fr",
             "telephone": "01 45 67 89 11", "telephone_mobile": "06 98 76 54 32",
             "copropriete_id": 1, "numero_lot": "A102", "type_lot": "Appartement",
             "etage": 1, "surface": 65.0, "tantiemes": 720, "statut": "proprietaire",
             "est_resident": False, "solde_compte": -350.0},

            {"nom": "Bernard", "prenom": "Michel", "email": "m.bernard@free.fr",
             "telephone": "01 45 67 89 12",
             "copropriete_id": 1, "numero_lot": "A201", "type_lot": "Appartement",
             "etage": 2, "surface": 82.0, "tantiemes": 920, "statut": "proprietaire",
             "statut_special": "conseiller_syndical", "est_resident": True, "solde_compte": 125.0},

            {"nom": "Petit", "prenom": "Marie", "email": "marie.petit@yahoo.fr",
             "telephone_mobile": "06 11 22 33 44",
             "copropriete_id": 1, "numero_lot": "A202", "type_lot": "Appartement",
             "etage": 2, "surface": 55.0, "tantiemes": 610, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Lefebvre", "prenom": "Pierre", "email": "p.lefebvre@gmail.com",
             "telephone": "01 45 67 89 14", "telephone_mobile": "06 55 44 33 22",
             "copropriete_id": 1, "numero_lot": "B101", "type_lot": "Appartement",
             "etage": 1, "surface": 95.0, "tantiemes": 1050, "statut": "proprietaire",
             "statut_special": "president_cs", "est_resident": True, "solde_compte": 50.0},

            {"nom": "Garcia", "prenom": "Carmen", "email": "c.garcia@hotmail.com",
             "telephone_mobile": "06 77 88 99 00",
             "copropriete_id": 1, "numero_lot": "B201", "type_lot": "Appartement",
             "etage": 2, "surface": 70.0, "tantiemes": 780, "statut": "proprietaire",
             "est_resident": True, "solde_compte": -1200.0},  # Impayé

            {"nom": "Durand", "prenom": "François", "email": "f.durand@wanadoo.fr",
             "telephone": "01 45 67 89 16",
             "copropriete_id": 1, "numero_lot": "C101", "type_lot": "Local commercial",
             "etage": 0, "surface": 120.0, "tantiemes": 1500, "statut": "proprietaire",
             "est_resident": False, "solde_compte": 0.0},

            {"nom": "Moreau", "prenom": "Isabelle", "email": "i.moreau@gmail.com",
             "telephone_mobile": "06 22 33 44 55",
             "copropriete_id": 1, "numero_lot": "D301", "type_lot": "Appartement",
             "etage": 3, "surface": 88.0, "tantiemes": 980, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Laurent", "prenom": "Thomas", "email": "t.laurent@sfr.fr",
             "telephone": "01 45 67 89 18",
             "copropriete_id": 1, "numero_lot": "D302", "type_lot": "Appartement",
             "etage": 3, "surface": 62.0, "tantiemes": 690, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Simon", "prenom": "Nathalie", "email": "n.simon@gmail.com",
             "telephone_mobile": "06 33 44 55 66",
             "copropriete_id": 1, "numero_lot": "E101", "type_lot": "Studio",
             "etage": 1, "surface": 28.0, "tantiemes": 310, "statut": "proprietaire",
             "est_resident": False, "solde_compte": 0.0},

            {"nom": "Michel", "prenom": "Alain", "email": "a.michel@laposte.net",
             "telephone": "01 45 67 89 20",
             "copropriete_id": 1, "numero_lot": "E201", "type_lot": "Appartement",
             "etage": 2, "surface": 45.0, "tantiemes": 500, "statut": "proprietaire",
             "est_resident": True, "solde_compte": -600.0},  # Impayé

            {"nom": "Robert", "prenom": "Claire", "email": "c.robert@gmail.com",
             "telephone_mobile": "06 44 55 66 77",
             "copropriete_id": 1, "numero_lot": "E202", "type_lot": "Appartement",
             "etage": 2, "surface": 52.0, "tantiemes": 580, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},
        ]

        # Les Platanes (id=2) - 8 copropriétaires
        platanes_owners = [
            {"nom": "Faure", "prenom": "Jacques", "email": "j.faure@gmail.com",
             "telephone": "04 72 33 44 55", "telephone_mobile": "06 88 99 00 11",
             "copropriete_id": 2, "numero_lot": "101", "type_lot": "Appartement",
             "etage": 1, "surface": 85.0, "tantiemes": 1100, "statut": "proprietaire",
             "statut_special": "president_cs", "est_resident": True, "solde_compte": 0.0},

            {"nom": "Blanc", "prenom": "Martine", "email": "m.blanc@orange.fr",
             "telephone_mobile": "06 99 88 77 66",
             "copropriete_id": 2, "numero_lot": "102", "type_lot": "Appartement",
             "etage": 1, "surface": 72.0, "tantiemes": 950, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Rousseau", "prenom": "Philippe", "email": "p.rousseau@free.fr",
             "telephone": "04 72 33 44 58",
             "copropriete_id": 2, "numero_lot": "201", "type_lot": "Appartement",
             "etage": 2, "surface": 95.0, "tantiemes": 1250, "statut": "proprietaire",
             "est_resident": False, "solde_compte": -450.0},

            {"nom": "Vincent", "prenom": "Hélène", "email": "h.vincent@yahoo.fr",
             "telephone_mobile": "06 77 66 55 44",
             "copropriete_id": 2, "numero_lot": "202", "type_lot": "Appartement",
             "etage": 2, "surface": 68.0, "tantiemes": 890, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Girard", "prenom": "Olivier", "email": "o.girard@gmail.com",
             "telephone": "04 72 33 44 60", "telephone_mobile": "06 55 44 33 22",
             "copropriete_id": 2, "numero_lot": "301", "type_lot": "Appartement",
             "etage": 3, "surface": 110.0, "tantiemes": 1450, "statut": "proprietaire",
             "statut_special": "conseiller_syndical", "est_resident": True, "solde_compte": 75.0},

            {"nom": "Bonnet", "prenom": "Sylvie", "email": "s.bonnet@laposte.net",
             "telephone_mobile": "06 44 33 22 11",
             "copropriete_id": 2, "numero_lot": "302", "type_lot": "Appartement",
             "etage": 3, "surface": 78.0, "tantiemes": 1020, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},

            {"nom": "Dupuis", "prenom": "Laurent", "email": "l.dupuis@sfr.fr",
             "telephone": "04 72 33 44 62",
             "copropriete_id": 2, "numero_lot": "RDC-1", "type_lot": "Local commercial",
             "etage": 0, "surface": 150.0, "tantiemes": 1800, "statut": "proprietaire",
             "est_resident": False, "solde_compte": 0.0},

            {"nom": "Chevalier", "prenom": "Anne", "email": "a.chevalier@gmail.com",
             "telephone_mobile": "06 33 22 11 00",
             "copropriete_id": 2, "numero_lot": "401", "type_lot": "Appartement",
             "etage": 4, "surface": 92.0, "tantiemes": 1200, "statut": "proprietaire",
             "est_resident": True, "solde_compte": 0.0},
        ]

        all_owners = mimosas_owners + platanes_owners
        for owner in all_owners:
            columns = ", ".join(owner.keys())
            placeholders = ", ".join([f":{k}" for k in owner.keys()])
            await self.session.execute(
                text(f"INSERT INTO coproprietaires ({columns}) VALUES ({placeholders})"),
                owner
            )

    async def load_professionnels(self):
        """Load professionals (plumbers, electricians, etc.)"""
        professionnels = [
            # Plombiers
            {"name": "Jean-Marc Duval", "company_name": "Plomberie Duval & Fils",
             "email": "contact@plomberie-duval.fr", "phone": "01 45 78 90 12",
             "siret": "12345678901234", "category": "plombier",
             "description": "Plomberie générale, dépannage urgent 24h/24, chauffage",
             "statut": "active", "address": "25 rue de la Plomberie",
             "city": "Paris", "postal_code": "75015", "rating": 4.5,
             "total_jobs": 127, "is_indexed": True},

            {"name": "Marie Fontaine", "company_name": "Fontaine Services",
             "email": "m.fontaine@fontaine-services.fr", "phone": "01 45 78 90 13",
             "siret": "12345678901235", "category": "plombier",
             "description": "Spécialiste fuites et canalisations, diagnostic vidéo",
             "statut": "active", "address": "12 avenue Gambetta",
             "city": "Paris", "postal_code": "75020", "rating": 4.8,
             "total_jobs": 89, "is_indexed": True},

            # Électriciens
            {"name": "Philippe Leclerc", "company_name": "Électricité Leclerc",
             "email": "p.leclerc@elec-leclerc.fr", "phone": "01 45 78 90 14",
             "siret": "12345678901236", "category": "electricien",
             "description": "Dépannage électrique, mise aux normes, domotique",
             "statut": "active", "address": "8 rue Voltaire",
             "city": "Paris", "postal_code": "75011", "rating": 4.6,
             "total_jobs": 156, "is_indexed": True},

            {"name": "Sophie Ampère", "company_name": "Ampère Élec",
             "email": "contact@ampere-elec.fr", "phone": "04 72 33 44 15",
             "siret": "12345678901237", "category": "electricien",
             "description": "Installation électrique, interphonie, bornes de recharge",
             "statut": "active", "address": "45 cours Lafayette",
             "city": "Lyon", "postal_code": "69003", "rating": 4.7,
             "total_jobs": 78, "is_indexed": True},

            # Chauffagistes
            {"name": "Pierre Chaleur", "company_name": "Chaleur Services",
             "email": "contact@chaleur-services.fr", "phone": "01 45 78 90 16",
             "siret": "12345678901238", "category": "chauffagiste",
             "description": "Entretien chaudières, pompes à chaleur, climatisation",
             "statut": "active", "address": "15 rue du Chauffage",
             "city": "Paris", "postal_code": "75013", "rating": 4.4,
             "total_jobs": 234, "is_indexed": True},

            # Serruriers
            {"name": "Marc Clément", "company_name": "Serrurerie Clément",
             "email": "m.clement@serrurerie-clement.fr", "phone": "01 45 78 90 17",
             "siret": "12345678901239", "category": "serrurier",
             "description": "Ouverture de portes, changement de serrures, blindage",
             "statut": "active", "address": "3 rue des Clés",
             "city": "Paris", "postal_code": "75016", "rating": 4.3,
             "total_jobs": 312, "is_indexed": True},

            # Peintres
            {"name": "Alain Couleur", "company_name": "Peinture Couleur",
             "email": "a.couleur@peinture-couleur.fr", "phone": "01 45 78 90 18",
             "siret": "12345678901240", "category": "peintre",
             "description": "Peinture intérieure/extérieure, ravalement, décoration",
             "statut": "active", "address": "22 rue de la Palette",
             "city": "Paris", "postal_code": "75014", "rating": 4.6,
             "total_jobs": 67, "is_indexed": True},

            # Jardiniers
            {"name": "Paul Verdure", "company_name": "Jardins Verdure",
             "email": "p.verdure@jardins-verdure.fr", "phone": "01 45 78 90 19",
             "siret": "12345678901241", "category": "jardinier",
             "description": "Entretien espaces verts, élagage, aménagement paysager",
             "statut": "active", "address": "5 allée des Jardins",
             "city": "Paris", "postal_code": "75012", "rating": 4.5,
             "total_jobs": 45, "is_indexed": True},

            # Professionnel blacklisté (pour tests)
            {"name": "Robert Arnaque", "company_name": "Services Rapides",
             "email": "r.arnaque@services-rapides.fr", "phone": "01 00 00 00 00",
             "siret": "00000000000000", "category": "plombier",
             "description": "Services divers",
             "statut": "blacklisted", "address": "1 rue Douteuse",
             "city": "Paris", "postal_code": "75001", "rating": 1.2,
             "total_jobs": 3, "is_indexed": False},
        ]

        for pro in professionnels:
            columns = ", ".join(pro.keys())
            placeholders = ", ".join([f":{k}" for k in pro.keys()])
            await self.session.execute(
                text(f"INSERT INTO professionnels ({columns}) VALUES ({placeholders})"),
                pro
            )

        # Link some professionals to copropriétés
        links = [
            {"professionnel_id": 1, "copropriete_id": 1, "nombre_interventions": 15, "note_satisfaction": 4.5},
            {"professionnel_id": 2, "copropriete_id": 1, "nombre_interventions": 8, "note_satisfaction": 4.8},
            {"professionnel_id": 3, "copropriete_id": 1, "nombre_interventions": 12, "note_satisfaction": 4.6},
            {"professionnel_id": 5, "copropriete_id": 1, "nombre_interventions": 24, "note_satisfaction": 4.4},
            {"professionnel_id": 4, "copropriete_id": 2, "nombre_interventions": 6, "note_satisfaction": 4.7},
            {"professionnel_id": 5, "copropriete_id": 2, "nombre_interventions": 10, "note_satisfaction": 4.5},
        ]

        for link in links:
            await self.session.execute(
                text("""INSERT INTO professionnels_coproprietes
                        (professionnel_id, copropriete_id, nombre_interventions, note_satisfaction)
                        VALUES (:professionnel_id, :copropriete_id, :nombre_interventions, :note_satisfaction)"""),
                link
            )

    async def load_emails(self):
        """Load emails with various urgency levels"""
        now = datetime.now()
        emails = [
            # URGENT emails
            {
                "message_id": "msg_urgent_001",
                "thread_id": "thread_001",
                "sender": "jp.dupont@gmail.com",
                "recipient": "syndic@mimosas.fr",
                "subject": "URGENT - Fuite d'eau importante dans mon appartement",
                "body": """Bonjour,

J'ai une fuite d'eau importante sous mon évier de cuisine qui a commencé cette nuit.
L'eau coule en continu et commence à traverser le plafond du voisin du dessous.

J'ai coupé l'eau de l'appartement mais la fuite continue depuis les parties communes.

Merci d'intervenir en urgence.

Jean-Pierre Dupont
Appartement A101""",
                "snippet": "J'ai une fuite d'eau importante sous mon évier...",
                "urgency": "URGENT",
                "category": "incident",
                "copropriete_id": 1,
                "coproprietaire_id": 1,
                "received_at": now - timedelta(hours=2),
                "processed": False
            },
            {
                "message_id": "msg_urgent_002",
                "thread_id": "thread_002",
                "sender": "m.bernard@free.fr",
                "recipient": "syndic@mimosas.fr",
                "subject": "Panne ascenseur bâtiment A - Personne bloquée",
                "body": """Urgent !

L'ascenseur du bâtiment A est en panne depuis 30 minutes.
Mme Petit du 2ème est bloquée à l'intérieur.

Elle a 78 ans et semble très angoissée.

Michel Bernard
Conseiller syndical""",
                "snippet": "L'ascenseur du bâtiment A est en panne...",
                "urgency": "URGENT",
                "category": "incident",
                "copropriete_id": 1,
                "coproprietaire_id": 3,
                "received_at": now - timedelta(hours=1),
                "processed": True,
                "processed_at": now - timedelta(minutes=45)
            },

            # IMPORTANT emails
            {
                "message_id": "msg_important_001",
                "thread_id": "thread_003",
                "sender": "p.lefebvre@gmail.com",
                "recipient": "syndic@mimosas.fr",
                "subject": "Préparation AG 2025 - Points à inscrire",
                "body": """Bonjour,

En tant que président du conseil syndical, je souhaite proposer les points suivants
pour l'ordre du jour de la prochaine AG :

1. Ravalement de façade (devis à demander)
2. Installation de bornes de recharge électrique au parking
3. Mise aux normes de l'éclairage des parties communes (LED)
4. Audit énergétique du bâtiment

Pouvons-nous organiser une réunion préparatoire ?

Pierre Lefebvre
Président CS Les Mimosas""",
                "snippet": "En tant que président du conseil syndical...",
                "urgency": "IMPORTANT",
                "category": "assemblée_générale",
                "copropriete_id": 1,
                "coproprietaire_id": 5,
                "received_at": now - timedelta(days=3),
                "processed": True
            },
            {
                "message_id": "msg_important_002",
                "thread_id": "thread_004",
                "sender": "j.faure@gmail.com",
                "recipient": "syndic@platanes.fr",
                "subject": "Impayés de charges - Demande d'action",
                "body": """Bonjour,

En tant que président du conseil syndical des Platanes, je m'inquiète
des impayés de charges qui s'accumulent.

Pouvez-vous me faire un point sur la situation et les actions
de recouvrement en cours ?

Jacques Faure""",
                "snippet": "Je m'inquiète des impayés de charges...",
                "urgency": "IMPORTANT",
                "category": "finances",
                "copropriete_id": 2,
                "coproprietaire_id": 13,  # Premier copropriétaire Les Platanes
                "received_at": now - timedelta(days=2),
                "processed": False
            },

            # ROUTINE emails
            {
                "message_id": "msg_routine_001",
                "thread_id": "thread_005",
                "sender": "s.martin@orange.fr",
                "recipient": "syndic@mimosas.fr",
                "subject": "Changement de coordonnées bancaires",
                "body": """Bonjour,

Je souhaite vous informer de mon changement de coordonnées bancaires
pour le prélèvement des charges.

Nouveau RIB en pièce jointe.

Sophie Martin
Lot A102""",
                "snippet": "Je souhaite vous informer de mon changement...",
                "urgency": "ROUTINE",
                "category": "administratif",
                "copropriete_id": 1,
                "coproprietaire_id": 2,
                "received_at": now - timedelta(days=5),
                "processed": True
            },
            {
                "message_id": "msg_routine_002",
                "thread_id": "thread_006",
                "sender": "i.moreau@gmail.com",
                "recipient": "syndic@mimosas.fr",
                "subject": "Question sur les travaux privatifs",
                "body": """Bonjour,

Je souhaite changer mes fenêtres pour du double vitrage.
Dois-je demander une autorisation à l'AG ?

Merci pour votre réponse.

Isabelle Moreau
Lot D301""",
                "snippet": "Je souhaite changer mes fenêtres...",
                "urgency": "ROUTINE",
                "category": "travaux",
                "copropriete_id": 1,
                "coproprietaire_id": 8,
                "received_at": now - timedelta(days=7),
                "processed": True
            },
            {
                "message_id": "msg_routine_003",
                "thread_id": "thread_007",
                "sender": "h.vincent@yahoo.fr",
                "recipient": "syndic@platanes.fr",
                "subject": "Demande de relevé de charges",
                "body": """Bonjour,

Pourriez-vous m'envoyer mon relevé de charges de l'année 2024 ?
J'en ai besoin pour ma déclaration d'impôts.

Merci d'avance.

Hélène Vincent
Lot 202""",
                "snippet": "Pourriez-vous m'envoyer mon relevé de charges...",
                "urgency": "ROUTINE",
                "category": "administratif",
                "copropriete_id": 2,
                "coproprietaire_id": 16,
                "received_at": now - timedelta(days=4),
                "processed": False
            },
        ]

        for email in emails:
            columns = ", ".join(email.keys())
            placeholders = ", ".join([f":{k}" for k in email.keys()])
            await self.session.execute(
                text(f"INSERT INTO emails ({columns}) VALUES ({placeholders})"),
                email
            )

    async def load_documents(self):
        """Load document metadata for RAG testing"""
        documents = [
            # Les Mimosas documents
            {"titre": "Règlement de copropriété - Les Mimosas",
             "type_document": "reglement_copropriete",
             "copropriete_id": 1,
             "date_document": datetime(1975, 6, 15),
             "chemin_fichier": "/documents/mimosas/reglement_copropriete.pdf",
             "taille_fichier": 2500000,
             "is_indexed": True},

            {"titre": "PV AG du 15 juin 2024 - Les Mimosas",
             "type_document": "pv_ag",
             "copropriete_id": 1,
             "date_document": datetime(2024, 6, 15),
             "chemin_fichier": "/documents/mimosas/pv_ag_2024.pdf",
             "taille_fichier": 850000,
             "is_indexed": True},

            {"titre": "PV AG du 20 juin 2023 - Les Mimosas",
             "type_document": "pv_ag",
             "copropriete_id": 1,
             "date_document": datetime(2023, 6, 20),
             "chemin_fichier": "/documents/mimosas/pv_ag_2023.pdf",
             "taille_fichier": 920000,
             "is_indexed": True},

            {"titre": "Contrat syndic 2024-2027 - Les Mimosas",
             "type_document": "contrat_syndic",
             "copropriete_id": 1,
             "date_document": datetime(2024, 7, 1),
             "chemin_fichier": "/documents/mimosas/contrat_syndic_2024.pdf",
             "taille_fichier": 1200000,
             "is_indexed": True},

            {"titre": "Devis ravalement façade - Les Mimosas",
             "type_document": "devis",
             "copropriete_id": 1,
             "date_document": datetime(2024, 10, 15),
             "chemin_fichier": "/documents/mimosas/devis_ravalement.pdf",
             "taille_fichier": 350000,
             "is_indexed": True},

            # Les Platanes documents
            {"titre": "Règlement de copropriété - Les Platanes",
             "type_document": "reglement_copropriete",
             "copropriete_id": 2,
             "date_document": datetime(1992, 3, 10),
             "chemin_fichier": "/documents/platanes/reglement_copropriete.pdf",
             "taille_fichier": 1800000,
             "is_indexed": True},

            {"titre": "PV AG du 20 septembre 2024 - Les Platanes",
             "type_document": "pv_ag",
             "copropriete_id": 2,
             "date_document": datetime(2024, 9, 20),
             "chemin_fichier": "/documents/platanes/pv_ag_2024.pdf",
             "taille_fichier": 720000,
             "is_indexed": True},

            {"titre": "Contrat d'entretien chaudière - Les Platanes",
             "type_document": "contrat_entretien",
             "copropriete_id": 2,
             "date_document": datetime(2024, 1, 15),
             "chemin_fichier": "/documents/platanes/contrat_chaudiere.pdf",
             "taille_fichier": 450000,
             "is_indexed": True},
        ]

        for doc in documents:
            columns = ", ".join(doc.keys())
            placeholders = ", ".join([f":{k}" for k in doc.keys()])
            await self.session.execute(
                text(f"INSERT INTO documents ({columns}) VALUES ({placeholders})"),
                doc
            )


# ============================================================================
# EXPECTED ANSWERS for E2E Test Validation
# ============================================================================

EXPECTED_ANSWERS = {
    # SQL simple queries
    "combien_coproprietaires_mimosas": {
        "query": "Combien de copropriétaires aux Mimosas ?",
        "expected_source": "sql",
        "expected_count": 12,
        "validation_keywords": ["12", "copropriétaire", "Mimosas"]
    },
    "combien_coproprietaires_platanes": {
        "query": "Combien de copropriétaires aux Platanes ?",
        "expected_source": "sql",
        "expected_count": 8,
        "validation_keywords": ["8", "copropriétaire", "Platanes"]
    },
    "liste_plombiers": {
        "query": "Donne-moi la liste des plombiers disponibles",
        "expected_source": "sql",
        "expected_count": 2,  # 2 active, 1 blacklisted
        "validation_keywords": ["Duval", "Fontaine", "plombier"]
    },
    "emails_urgents": {
        "query": "Quels sont les emails urgents non traités ?",
        "expected_source": "sql",
        "expected_count": 1,  # 1 urgent non traité
        "validation_keywords": ["fuite", "urgent", "Dupont"]
    },
    "impayes": {
        "query": "Quels copropriétaires ont des impayés aux Mimosas ?",
        "expected_source": "sql",
        "expected_count": 2,  # Garcia et Michel ont des soldes négatifs
        "validation_keywords": ["Garcia", "Michel", "impayé"]
    },
    "president_cs_mimosas": {
        "query": "Qui est le président du conseil syndical des Mimosas ?",
        "expected_source": "sql",
        "expected_count": 1,
        "validation_keywords": ["Lefebvre", "Pierre", "président"]
    },

    # Hybrid queries (SQL + RAG)
    "travaux_budget_mimosas": {
        "query": "Quels sont les travaux prévus aux Mimosas et leur budget ?",
        "expected_sources": ["sql", "rag"],
        "validation_keywords": ["ravalement", "budget", "AG"]
    },
    "reglement_travaux_privatifs": {
        "query": "Que dit le règlement sur les travaux privatifs aux Mimosas ?",
        "expected_sources": ["rag"],
        "validation_keywords": ["règlement", "travaux", "autorisation"]
    },

    # Complex queries
    "situation_complete_mimosas": {
        "query": "Fais-moi un résumé complet de la situation des Mimosas : nombre de lots, copropriétaires, impayés, dernière AG",
        "expected_sources": ["sql", "rag"],
        "validation_keywords": ["50 lots", "12 copropriétaires", "impayés", "AG"]
    }
}


# ============================================================================
# Test Scenarios
# ============================================================================

E2E_TEST_SCENARIOS = [
    # Scenario 1: Urgence plomberie
    {
        "name": "urgency_water_leak",
        "description": "Gestion d'une fuite d'eau urgente",
        "queries": [
            "Il y a une fuite d'eau urgente au bâtiment A des Mimosas",
            "Trouve-moi un plombier disponible rapidement",
            "Envoie un email urgent au plombier Duval pour intervention"
        ],
        "expected_agents": ["sql", "workflow", "email"],
        "max_latency_ms": 10000
    },

    # Scenario 2: Cascade SQL → Legal → RAG
    {
        "name": "legal_compliance_check",
        "description": "Vérification de conformité légale",
        "queries": [
            "Combien de copropriétaires aux Mimosas ?",
            "Le quorum légal a-t-il été atteint à la dernière AG ?",
            "Que dit la loi ELAN sur les majorités en AG ?"
        ],
        "expected_agents": ["sql", "rag", "legal"],
        "max_latency_ms": 15000
    },

    # Scenario 3: Analyse contrat + PV
    {
        "name": "contract_analysis",
        "description": "Analyse de documents contractuels",
        "queries": [
            "Quelles sont les clauses importantes du contrat syndic des Mimosas ?",
            "Compare avec les décisions de la dernière AG"
        ],
        "expected_agents": ["rag", "legal"],
        "max_latency_ms": 12000
    },

    # Scenario 4: Long conversation (20+ turns simulation)
    {
        "name": "long_conversation",
        "description": "Conversation longue avec contexte maintenu",
        "queries": [
            "Bonjour, je suis le syndic des Mimosas",
            "Combien de copropriétaires ?",
            "Et aux Platanes ?",
            "Liste les impayés",
            "Qui est le président du CS ?",
            "Quand était la dernière AG ?",
            "Quels travaux ont été votés ?",
            "Quel budget total ?",
            "Y a-t-il des emails urgents ?",
            "Trouve-moi un plombier"
        ],
        "expected_agents": ["sql", "rag"],
        "max_latency_ms": 5000,  # Per query
        "context_retention": True
    },

    # Scenario 5: Edge cases
    {
        "name": "edge_cases",
        "description": "Cas limites et ambiguïtés",
        "queries": [
            "Combien ?",  # Ambiguous
            "Donne-moi tout sur tout",  # Vague
            "Trouve le document XYZ123",  # Missing document
            "Email urgent à personne@inconnu.fr"  # Unknown recipient
        ],
        "expected_behavior": "graceful_handling",
        "max_latency_ms": 5000
    }
]
