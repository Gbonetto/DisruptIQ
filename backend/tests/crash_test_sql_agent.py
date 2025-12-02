"""
Crash Test SQL Agent - Test complet pour un syndic de copropriété
================================================================

Ce script simule un syndic qui gère 8 copropriétés avec:
- 50+ copropriétaires répartis dans différentes villes
- 25+ professionnels de différentes catégories
- Des scénarios de requêtes réalistes du quotidien

Objectif: Tester que l'agent SQL répond correctement à toutes les questions
lorsque l'information existe dans la base de données.
"""

import asyncio
import sys
import os
from datetime import date, datetime
from decimal import Decimal
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Database connection
DATABASE_URL = settings.DATABASE_URL.replace("+asyncpg", "")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# =============================================================================
# DONNÉES DE TEST RÉALISTES
# =============================================================================

COPROPRIETES = [
    {
        "nom": "Résidence Les Mimosas",
        "adresse": "12 avenue des Fleurs",
        "ville": "Lyon",
        "code_postal": "69003",
        "nombre_lots": 45,
        "nombre_batiments": 2,
        "annee_construction": 1975,
        "syndic": "Cabinet Durand",
        "type_copropriete": "résidentiel",
        "equipements": ["ascenseur", "parking", "local vélos", "gardien"],
        "notes": "Ravalement prévu 2025. Problèmes récurrents chaudière bâtiment B."
    },
    {
        "nom": "Le Clos du Parc",
        "adresse": "8 rue du Parc",
        "ville": "Villeurbanne",
        "code_postal": "69100",
        "nombre_lots": 30,
        "nombre_batiments": 1,
        "annee_construction": 1988,
        "syndic": "Cabinet Durand",
        "type_copropriete": "résidentiel",
        "equipements": ["parking souterrain", "interphone"],
        "notes": "Copropriété calme, bon payeurs."
    },
    {
        "nom": "Domaine Saint-Jean",
        "adresse": "45 boulevard Saint-Jean",
        "ville": "Lyon",
        "code_postal": "69005",
        "nombre_lots": 120,
        "nombre_batiments": 4,
        "annee_construction": 1962,
        "syndic": "Cabinet Durand",
        "type_copropriete": "mixte",
        "equipements": ["ascenseur", "parking", "piscine", "tennis", "gardien"],
        "notes": "Grande copropriété avec commerces en RDC. AG difficiles."
    },
    {
        "nom": "Les Jardins de Provence",
        "adresse": "3 impasse des Oliviers",
        "ville": "Marseille",
        "code_postal": "13008",
        "nombre_lots": 25,
        "nombre_batiments": 1,
        "annee_construction": 2005,
        "syndic": "Cabinet Durand",
        "type_copropriete": "résidentiel",
        "equipements": ["parking", "jardin privatif", "piscine"],
        "notes": "Copropriété récente, peu de travaux."
    },
    {
        "nom": "Résidence Arc-en-Ciel",
        "adresse": "22 rue de la République",
        "ville": "Lyon",
        "code_postal": "69001",
        "nombre_lots": 18,
        "nombre_batiments": 1,
        "annee_construction": 1930,
        "syndic": "Cabinet Durand",
        "type_copropriete": "résidentiel",
        "equipements": ["cave"],
        "notes": "Immeuble ancien, façade classée. Travaux soumis à ABF."
    },
    {
        "nom": "Le Hameau des Cerisiers",
        "adresse": "15 chemin des Cerisiers",
        "ville": "Écully",
        "code_postal": "69130",
        "nombre_lots": 12,
        "nombre_batiments": 6,
        "annee_construction": 1995,
        "syndic": "Cabinet Durand",
        "type_copropriete": "résidentiel",
        "equipements": ["parking privatif", "jardin"],
        "notes": "Petites maisons de ville. Communauté soudée."
    },
    {
        "nom": "Tour Montchat",
        "adresse": "1 place Montchat",
        "ville": "Lyon",
        "code_postal": "69003",
        "nombre_lots": 80,
        "nombre_batiments": 1,
        "annee_construction": 1970,
        "syndic": "Cabinet Durand",
        "type_copropriete": "mixte",
        "equipements": ["ascenseur", "parking", "gardien", "local poubelles"],
        "notes": "Tour de 15 étages. Travaux ascenseur en cours."
    },
    {
        "nom": "Villa Marguerite",
        "adresse": "5 rue Marguerite",
        "ville": "Caluire-et-Cuire",
        "code_postal": "69300",
        "nombre_lots": 8,
        "nombre_batiments": 1,
        "annee_construction": 2018,
        "syndic": "Cabinet Durand",
        "type_copropriete": "résidentiel",
        "equipements": ["parking", "local vélos", "bornes de recharge"],
        "notes": "Immeuble BBC. Charges très basses."
    },
]

# Copropriétaires avec données variées
COPROPRIETAIRES = [
    # Résidence Les Mimosas (id=1)
    {"nom": "Moussu", "prenom": "Fafa", "email": "fafa.moussu@gmail.com", "telephone": "06 12 34 56 78", "copropriete_id": 1, "numero_lot": "A12", "type_lot": "appartement", "etage": 3, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Martin", "prenom": "Jean", "email": "jean.martin@orange.fr", "telephone": "06 23 45 67 89", "copropriete_id": 1, "numero_lot": "A05", "type_lot": "appartement", "etage": 1, "statut": "proprietaire"},
    {"nom": "Dubois", "prenom": "Marie", "email": "m.dubois@yahoo.fr", "telephone": "07 11 22 33 44", "copropriete_id": 1, "numero_lot": "B08", "type_lot": "appartement", "etage": 2, "statut": "locataire"},
    {"nom": "Lefebvre", "prenom": "Pierre", "email": "pierre.lefebvre@gmail.com", "telephone": "06 99 88 77 66", "copropriete_id": 1, "numero_lot": "A15", "type_lot": "appartement", "etage": 4, "statut": "proprietaire", "statut_special": "conseil_syndical"},
    {"nom": "Bernard", "prenom": "Sophie", "email": "sophie.bernard@laposte.net", "telephone": "06 55 44 33 22", "copropriete_id": 1, "numero_lot": "B12", "type_lot": "appartement", "etage": 3, "statut": "proprietaire"},
    {"nom": "Petit", "prenom": "Alain", "email": "alain.petit@free.fr", "telephone": "06 77 88 99 00", "copropriete_id": 1, "numero_lot": "A20", "type_lot": "appartement", "etage": 5, "statut": "proprietaire"},

    # Le Clos du Parc (id=2)
    {"nom": "Moreau", "prenom": "Catherine", "email": "c.moreau@gmail.com", "telephone": "06 10 20 30 40", "copropriete_id": 2, "numero_lot": "101", "type_lot": "appartement", "etage": 1, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Laurent", "prenom": "Michel", "email": "michel.laurent@sfr.fr", "telephone": "07 20 30 40 50", "copropriete_id": 2, "numero_lot": "205", "type_lot": "appartement", "etage": 2, "statut": "proprietaire"},
    {"nom": "Simon", "prenom": "Françoise", "email": "f.simon@wanadoo.fr", "telephone": "06 30 40 50 60", "copropriete_id": 2, "numero_lot": "308", "type_lot": "appartement", "etage": 3, "statut": "locataire"},
    {"nom": "Garcia", "prenom": "Antonio", "email": "a.garcia@gmail.com", "telephone": "06 40 50 60 70", "copropriete_id": 2, "numero_lot": "102", "type_lot": "appartement", "etage": 1, "statut": "proprietaire"},

    # Domaine Saint-Jean (id=3)
    {"nom": "Roux", "prenom": "Isabelle", "email": "isabelle.roux@gmail.com", "telephone": "06 50 60 70 80", "copropriete_id": 3, "numero_lot": "A101", "type_lot": "appartement", "etage": 1, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Fournier", "prenom": "David", "email": "david.fournier@hotmail.com", "telephone": "07 60 70 80 90", "copropriete_id": 3, "numero_lot": "B205", "type_lot": "appartement", "etage": 2, "statut": "proprietaire"},
    {"nom": "Girard", "prenom": "Nathalie", "email": "n.girard@gmail.com", "telephone": "06 70 80 90 00", "copropriete_id": 3, "numero_lot": "C310", "type_lot": "appartement", "etage": 3, "statut": "proprietaire", "statut_special": "conseil_syndical"},
    {"nom": "Bonnet", "prenom": "Patrick", "email": "patrick.bonnet@orange.fr", "telephone": "06 80 90 00 11", "copropriete_id": 3, "numero_lot": "D102", "type_lot": "commerce", "etage": 0, "statut": "proprietaire"},
    {"nom": "Dupont", "prenom": "Hélène", "email": "helene.dupont@gmail.com", "telephone": "07 90 00 11 22", "copropriete_id": 3, "numero_lot": "A405", "type_lot": "appartement", "etage": 4, "statut": "locataire"},
    {"nom": "Mercier", "prenom": "Christophe", "email": "c.mercier@yahoo.fr", "telephone": "06 00 11 22 33", "copropriete_id": 3, "numero_lot": "B508", "type_lot": "appartement", "etage": 5, "statut": "proprietaire"},

    # Les Jardins de Provence (id=4) - Marseille
    {"nom": "Vincent", "prenom": "Sylvie", "email": "sylvie.vincent@gmail.com", "telephone": "06 11 22 33 44", "copropriete_id": 4, "numero_lot": "01", "type_lot": "appartement", "etage": 0, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Faure", "prenom": "Olivier", "email": "olivier.faure@laposte.net", "telephone": "07 22 33 44 55", "copropriete_id": 4, "numero_lot": "05", "type_lot": "appartement", "etage": 1, "statut": "proprietaire"},
    {"nom": "Robin", "prenom": "Céline", "email": "celine.robin@gmail.com", "telephone": "06 33 44 55 66", "copropriete_id": 4, "numero_lot": "12", "type_lot": "appartement", "etage": 2, "statut": "locataire"},
    {"nom": "Blanc", "prenom": "Thierry", "email": "thierry.blanc@free.fr", "telephone": "06 44 55 66 77", "copropriete_id": 4, "numero_lot": "18", "type_lot": "appartement", "etage": 3, "statut": "proprietaire"},

    # Résidence Arc-en-Ciel (id=5)
    {"nom": "Guerin", "prenom": "Martine", "email": "martine.guerin@gmail.com", "telephone": "06 55 66 77 88", "copropriete_id": 5, "numero_lot": "1A", "type_lot": "appartement", "etage": 1, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Muller", "prenom": "Jean-Pierre", "email": "jp.muller@orange.fr", "telephone": "07 66 77 88 99", "copropriete_id": 5, "numero_lot": "2B", "type_lot": "appartement", "etage": 2, "statut": "proprietaire"},
    {"nom": "Leroy", "prenom": "Sandrine", "email": "s.leroy@hotmail.com", "telephone": "06 77 88 99 00", "copropriete_id": 5, "numero_lot": "3A", "type_lot": "appartement", "etage": 3, "statut": "locataire"},

    # Le Hameau des Cerisiers (id=6) - Écully
    {"nom": "Thomas", "prenom": "Valérie", "email": "valerie.thomas@gmail.com", "telephone": "06 88 99 00 11", "copropriete_id": 6, "numero_lot": "M1", "type_lot": "maison", "etage": None, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Robert", "prenom": "Fabrice", "email": "fabrice.robert@sfr.fr", "telephone": "07 99 00 11 22", "copropriete_id": 6, "numero_lot": "M2", "type_lot": "maison", "etage": None, "statut": "proprietaire"},
    {"nom": "Richard", "prenom": "Aurélie", "email": "aurelie.richard@gmail.com", "telephone": "06 00 11 22 33", "copropriete_id": 6, "numero_lot": "M3", "type_lot": "maison", "etage": None, "statut": "proprietaire"},
    {"nom": "Durand", "prenom": "Philippe", "email": "philippe.durand@yahoo.fr", "telephone": "06 11 22 33 44", "copropriete_id": 6, "numero_lot": "M4", "type_lot": "maison", "etage": None, "statut": "proprietaire", "statut_special": "conseil_syndical"},

    # Tour Montchat (id=7)
    {"nom": "Bertrand", "prenom": "Corinne", "email": "corinne.bertrand@gmail.com", "telephone": "06 22 33 44 55", "copropriete_id": 7, "numero_lot": "501", "type_lot": "appartement", "etage": 5, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Morel", "prenom": "Jacques", "email": "jacques.morel@orange.fr", "telephone": "07 33 44 55 66", "copropriete_id": 7, "numero_lot": "802", "type_lot": "appartement", "etage": 8, "statut": "proprietaire"},
    {"nom": "Henry", "prenom": "Brigitte", "email": "brigitte.henry@laposte.net", "telephone": "06 44 55 66 77", "copropriete_id": 7, "numero_lot": "1003", "type_lot": "appartement", "etage": 10, "statut": "locataire"},
    {"nom": "Lemoine", "prenom": "Yves", "email": "yves.lemoine@free.fr", "telephone": "06 55 66 77 88", "copropriete_id": 7, "numero_lot": "1204", "type_lot": "appartement", "etage": 12, "statut": "proprietaire"},
    {"nom": "Marchand", "prenom": "Danielle", "email": "d.marchand@gmail.com", "telephone": "07 66 77 88 99", "copropriete_id": 7, "numero_lot": "1401", "type_lot": "appartement", "etage": 14, "statut": "proprietaire"},

    # Villa Marguerite (id=8) - Caluire-et-Cuire
    {"nom": "David", "prenom": "Stéphane", "email": "stephane.david@gmail.com", "telephone": "06 77 88 99 00", "copropriete_id": 8, "numero_lot": "T2-A", "type_lot": "appartement", "etage": 1, "statut": "proprietaire", "statut_special": "président"},
    {"nom": "Chevalier", "prenom": "Laurence", "email": "laurence.chevalier@orange.fr", "telephone": "07 88 99 00 11", "copropriete_id": 8, "numero_lot": "T3-B", "type_lot": "appartement", "etage": 2, "statut": "proprietaire"},
    {"nom": "Perrin", "prenom": "Sébastien", "email": "sebastien.perrin@hotmail.com", "telephone": "06 99 00 11 22", "copropriete_id": 8, "numero_lot": "T4-C", "type_lot": "appartement", "etage": 3, "statut": "locataire"},
]

PROFESSIONNELS = [
    # Plombiers
    {"name": "Marcel Dupuis", "company_name": "Plomberie Express", "email": "contact@plomberie-express.fr", "phone": "04 78 12 34 56", "category": "plombier", "city": "Lyon", "postal_code": "69003", "rating": 4.5, "total_jobs": 45, "specialties": ["dépannage urgence", "rénovation salle de bain", "chauffe-eau"], "statut": "active"},
    {"name": "Jean-Marc Rousseau", "company_name": "SOS Plomberie Lyon", "email": "jm.rousseau@sosplomberie.fr", "phone": "04 78 23 45 67", "category": "plombier", "city": "Villeurbanne", "postal_code": "69100", "rating": 4.2, "total_jobs": 32, "specialties": ["fuite d'eau", "débouchage"], "statut": "active"},
    {"name": "Pierre Fontaine", "company_name": "Fontaine Plomberie", "email": "pierre@fontaine-plomberie.com", "phone": "04 72 34 56 78", "category": "plombier", "city": "Lyon", "postal_code": "69001", "rating": 3.8, "total_jobs": 18, "specialties": ["installation sanitaire"], "statut": "active"},

    # Électriciens
    {"name": "André Martin", "company_name": "Électricité Plus", "email": "contact@electricite-plus.fr", "phone": "04 78 45 67 89", "category": "électricien", "city": "Lyon", "postal_code": "69003", "rating": 4.8, "total_jobs": 67, "specialties": ["mise aux normes", "dépannage", "domotique"], "statut": "active"},
    {"name": "Fabien Leclerc", "company_name": "Leclerc Élec", "email": "fabien@leclerc-elec.fr", "phone": "04 78 56 78 90", "category": "électricien", "city": "Caluire-et-Cuire", "postal_code": "69300", "rating": 4.3, "total_jobs": 28, "specialties": ["installation électrique", "tableau électrique"], "statut": "active"},
    {"name": "Lucas Bernard", "company_name": "Élec Services", "email": "lucas.bernard@elec-services.com", "phone": "04 72 67 89 01", "category": "électricien", "city": "Écully", "postal_code": "69130", "rating": 4.0, "total_jobs": 15, "specialties": ["éclairage", "prises"], "statut": "active"},

    # Jardiniers / Espaces verts
    {"name": "Claude Verdier", "company_name": "Jardins et Paysages", "email": "claude@jardins-paysages.fr", "phone": "06 12 34 56 78", "category": "jardinier", "city": "Lyon", "postal_code": "69005", "rating": 4.6, "total_jobs": 52, "specialties": ["entretien jardins", "taille haies", "tonte"], "statut": "active"},
    {"name": "Henri Vert", "company_name": "Vert Espace", "email": "contact@vert-espace.fr", "phone": "06 23 45 67 89", "category": "jardinier", "city": "Écully", "postal_code": "69130", "rating": 4.4, "total_jobs": 38, "specialties": ["création jardins", "arrosage automatique"], "statut": "active"},
    {"name": "Julie Fleur", "company_name": "Fleur et Jardin", "email": "julie@fleur-jardin.com", "phone": "06 34 56 78 90", "category": "jardinier", "city": "Villeurbanne", "postal_code": "69100", "rating": 4.7, "total_jobs": 41, "specialties": ["entretien copropriété", "élagage"], "statut": "active"},

    # Chauffagistes
    {"name": "Robert Chaleur", "company_name": "Chaleur Services", "email": "robert@chaleur-services.fr", "phone": "04 78 78 90 12", "category": "chauffagiste", "city": "Lyon", "postal_code": "69003", "rating": 4.5, "total_jobs": 55, "specialties": ["chaudière gaz", "pompe à chaleur", "contrat entretien"], "statut": "active"},
    {"name": "Marc Thermo", "company_name": "Thermo Expert", "email": "marc.thermo@thermoexpert.fr", "phone": "04 78 89 01 23", "category": "chauffagiste", "city": "Lyon", "postal_code": "69007", "rating": 4.1, "total_jobs": 22, "specialties": ["dépannage chaudière", "radiateurs"], "statut": "active"},

    # Serruriers
    {"name": "Paul Clef", "company_name": "Clef Minute", "email": "paul@clef-minute.fr", "phone": "04 78 90 12 34", "category": "serrurier", "city": "Lyon", "postal_code": "69001", "rating": 4.0, "total_jobs": 89, "specialties": ["ouverture porte", "changement serrure", "blindage"], "statut": "active"},
    {"name": "Denis Verrou", "company_name": "Sécurité Verrou", "email": "denis@securite-verrou.com", "phone": "04 78 01 23 45", "category": "serrurier", "city": "Lyon", "postal_code": "69003", "rating": 4.3, "total_jobs": 34, "specialties": ["porte blindée", "interphone", "digicode"], "statut": "active"},

    # Peintres
    {"name": "Vincent Couleur", "company_name": "Couleur et Déco", "email": "vincent@couleur-deco.fr", "phone": "06 45 67 89 01", "category": "peintre", "city": "Lyon", "postal_code": "69006", "rating": 4.6, "total_jobs": 31, "specialties": ["peinture intérieure", "ravalement", "décoration"], "statut": "active"},
    {"name": "Émile Pinceau", "company_name": "Pinceau d'Or", "email": "emile@pinceau-or.com", "phone": "06 56 78 90 12", "category": "peintre", "city": "Villeurbanne", "postal_code": "69100", "rating": 4.4, "total_jobs": 27, "specialties": ["façade", "parties communes"], "statut": "active"},

    # Ascensoristes
    {"name": "Philippe Ascenseur", "company_name": "Ascenseurs Rhône-Alpes", "email": "contact@ascenseurs-ra.fr", "phone": "04 78 12 45 78", "category": "ascensoriste", "city": "Lyon", "postal_code": "69003", "rating": 4.2, "total_jobs": 120, "specialties": ["maintenance", "dépannage", "modernisation"], "statut": "active"},

    # Nettoyage
    {"name": "Marie Propre", "company_name": "Net'Immeuble", "email": "marie@net-immeuble.fr", "phone": "06 67 89 01 23", "category": "nettoyage", "city": "Lyon", "postal_code": "69003", "rating": 4.5, "total_jobs": 200, "specialties": ["parties communes", "vitres", "nettoyage après travaux"], "statut": "active"},
    {"name": "Ali Brahim", "company_name": "Propreté Services", "email": "ali@proprete-services.com", "phone": "06 78 90 12 34", "category": "nettoyage", "city": "Villeurbanne", "postal_code": "69100", "rating": 4.3, "total_jobs": 85, "specialties": ["ménage copropriété", "sortie poubelles"], "statut": "active"},

    # Couvreurs
    {"name": "Jacques Toit", "company_name": "Toiture Expert", "email": "jacques@toiture-expert.fr", "phone": "04 78 23 56 89", "category": "couvreur", "city": "Lyon", "postal_code": "69005", "rating": 4.7, "total_jobs": 42, "specialties": ["réparation toiture", "gouttières", "étanchéité"], "statut": "active"},

    # Vitriers
    {"name": "Thomas Verre", "company_name": "Vitrerie Lyon", "email": "thomas@vitrerie-lyon.fr", "phone": "04 78 34 67 90", "category": "vitrier", "city": "Lyon", "postal_code": "69002", "rating": 4.1, "total_jobs": 56, "specialties": ["remplacement vitres", "double vitrage", "miroirs"], "statut": "active"},

    # Menuisiers
    {"name": "Bruno Bois", "company_name": "Menuiserie Bois & Co", "email": "bruno@bois-co.fr", "phone": "04 78 45 78 01", "category": "menuisier", "city": "Caluire-et-Cuire", "postal_code": "69300", "rating": 4.4, "total_jobs": 29, "specialties": ["portes", "fenêtres", "parquet"], "statut": "active"},

    # Marseille - pour Les Jardins de Provence
    {"name": "Antoine Méridional", "company_name": "Plomberie du Sud", "email": "antoine@plomberie-sud.fr", "phone": "04 91 12 34 56", "category": "plombier", "city": "Marseille", "postal_code": "13008", "rating": 4.3, "total_jobs": 38, "specialties": ["dépannage", "installation"], "statut": "active"},
    {"name": "Sophie Soleil", "company_name": "Jardins du Midi", "email": "sophie@jardins-midi.com", "phone": "06 91 23 45 67", "category": "jardinier", "city": "Marseille", "postal_code": "13008", "rating": 4.8, "total_jobs": 62, "specialties": ["entretien piscine", "jardin méditerranéen"], "statut": "active"},

    # Professionnel inactif pour tester les filtres
    {"name": "Pierre Ancien", "company_name": "Ancienne Plomberie", "email": "pierre.ancien@gmail.com", "phone": "04 78 00 00 00", "category": "plombier", "city": "Lyon", "postal_code": "69003", "rating": 2.5, "total_jobs": 5, "specialties": ["dépannage"], "statut": "inactive", "notes": "A cessé son activité en 2023"},
]


# =============================================================================
# FONCTIONS D'IMPORT
# =============================================================================

def clear_all_data():
    """Supprime toutes les données existantes et réinitialise les séquences"""
    print("\n🗑️  Suppression des données existantes...")
    with SessionLocal() as session:
        session.execute(text("DELETE FROM coproprietaires"))
        session.execute(text("DELETE FROM professionnels"))
        session.execute(text("DELETE FROM coproprietes"))
        # Réinitialiser les séquences pour avoir des IDs prévisibles (1, 2, 3...)
        session.execute(text("ALTER SEQUENCE coproprietes_id_seq RESTART WITH 1"))
        session.execute(text("ALTER SEQUENCE coproprietaires_id_seq RESTART WITH 1"))
        session.execute(text("ALTER SEQUENCE professionnels_id_seq RESTART WITH 1"))
        session.commit()
    print("   ✅ Données supprimées et séquences réinitialisées")


def import_coproprietes():
    """Importe les copropriétés"""
    print("\n🏢 Import des copropriétés...")
    with SessionLocal() as session:
        for copro in COPROPRIETES:
            equipements_json = json.dumps(copro.get("equipements", []))
            session.execute(text("""
                INSERT INTO coproprietes
                (nom, adresse, ville, code_postal, nombre_lots, nombre_batiments,
                 annee_construction, syndic, type_copropriete, equipements, notes, is_indexed)
                VALUES (:nom, :adresse, :ville, :code_postal, :nombre_lots, :nombre_batiments,
                        :annee_construction, :syndic, :type_copropriete, CAST(:equipements AS jsonb), :notes, false)
            """), {
                "nom": copro["nom"],
                "adresse": copro["adresse"],
                "ville": copro["ville"],
                "code_postal": copro["code_postal"],
                "nombre_lots": copro.get("nombre_lots"),
                "nombre_batiments": copro.get("nombre_batiments", 1),
                "annee_construction": copro.get("annee_construction"),
                "syndic": copro.get("syndic"),
                "type_copropriete": copro.get("type_copropriete"),
                "equipements": equipements_json,
                "notes": copro.get("notes")
            })
        session.commit()
    print(f"   ✅ {len(COPROPRIETES)} copropriétés importées")


def import_coproprietaires():
    """Importe les copropriétaires"""
    print("\n👥 Import des copropriétaires...")
    with SessionLocal() as session:
        for copro in COPROPRIETAIRES:
            session.execute(text("""
                INSERT INTO coproprietaires
                (nom, prenom, email, telephone, copropriete_id, numero_lot,
                 type_lot, etage, statut, statut_special, is_indexed)
                VALUES (:nom, :prenom, :email, :telephone, :copropriete_id, :numero_lot,
                        :type_lot, :etage, :statut, :statut_special, false)
            """), {
                "nom": copro["nom"],
                "prenom": copro["prenom"],
                "email": copro["email"],
                "telephone": copro["telephone"],
                "copropriete_id": copro["copropriete_id"],
                "numero_lot": copro["numero_lot"],
                "type_lot": copro["type_lot"],
                "etage": copro.get("etage"),
                "statut": copro.get("statut", "proprietaire"),
                "statut_special": copro.get("statut_special")
            })
        session.commit()
    print(f"   ✅ {len(COPROPRIETAIRES)} copropriétaires importés")


def import_professionnels():
    """Importe les professionnels"""
    print("\n🔧 Import des professionnels...")
    with SessionLocal() as session:
        for pro in PROFESSIONNELS:
            specialties_json = json.dumps(pro.get("specialties", []))
            session.execute(text("""
                INSERT INTO professionnels
                (name, company_name, email, phone, category, city, postal_code,
                 rating, total_jobs, specialties, statut, notes, is_indexed)
                VALUES (:name, :company_name, :email, :phone, :category, :city, :postal_code,
                        :rating, :total_jobs, CAST(:specialties AS jsonb), :statut, :notes, false)
            """), {
                "name": pro["name"],
                "company_name": pro.get("company_name"),
                "email": pro["email"],
                "phone": pro.get("phone"),
                "category": pro["category"],
                "city": pro.get("city"),
                "postal_code": pro.get("postal_code"),
                "rating": pro.get("rating", 0),
                "total_jobs": pro.get("total_jobs", 0),
                "specialties": specialties_json,
                "statut": pro.get("statut", "active"),
                "notes": pro.get("notes")
            })
        session.commit()
    print(f"   ✅ {len(PROFESSIONNELS)} professionnels importés")


def verify_data():
    """Vérifie les données importées"""
    print("\n📊 Vérification des données...")
    with SessionLocal() as session:
        copro_count = session.execute(text("SELECT COUNT(*) FROM coproprietes")).scalar()
        copro_count_detail = session.execute(text("SELECT COUNT(*) FROM coproprietaires")).scalar()
        pro_count = session.execute(text("SELECT COUNT(*) FROM professionnels")).scalar()

        print(f"   - Copropriétés: {copro_count}")
        print(f"   - Copropriétaires: {copro_count_detail}")
        print(f"   - Professionnels: {pro_count}")

        # Quelques stats
        print("\n   📈 Répartition par ville:")
        villes = session.execute(text("""
            SELECT ville, COUNT(*) as nb FROM coproprietes GROUP BY ville ORDER BY nb DESC
        """)).fetchall()
        for ville, nb in villes:
            print(f"      - {ville}: {nb} copropriété(s)")

        print("\n   📈 Professionnels par catégorie:")
        cats = session.execute(text("""
            SELECT category, COUNT(*) as nb FROM professionnels WHERE statut = 'active'
            GROUP BY category ORDER BY nb DESC
        """)).fetchall()
        for cat, nb in cats:
            print(f"      - {cat}: {nb}")


# =============================================================================
# TESTS DE L'AGENT SQL
# =============================================================================

async def test_sql_agent(query: str, expected_info: str = None, session_id: str = None) -> dict:
    """
    Teste une requête via l'agent SQL et affiche le résultat
    """
    import httpx

    if session_id is None:
        session_id = f"test-crash-{datetime.now().strftime('%H%M%S')}"

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/assistant-v2/chat",
                json={
                    "message": query,
                    "session_id": session_id,
                    "use_world_class_router": True  # Enable smart routing
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": data.get("success", False),
                    "query": query,
                    "response": data.get("message", ""),
                    "agents_used": data.get("agents_used", []),
                    "data": data.get("data", {}),
                    "expected": expected_info,
                    "session_id": session_id
                }
            else:
                return {
                    "success": False,
                    "query": query,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "expected": expected_info
                }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "expected": expected_info
            }


async def run_test_suite():
    """
    Exécute la suite de tests complète
    """
    print("\n" + "="*80)
    print("🧪 CRASH TEST SQL AGENT - Scénarios Syndic de Copropriété")
    print("="*80)

    tests = [
        # =================================================================
        # NIVEAU 1: RECHERCHES SIMPLES
        # =================================================================
        {
            "category": "🔍 RECHERCHES SIMPLES - Personnes",
            "tests": [
                ("Qui est Fafa Moussu ?", "Devrait trouver le copropriétaire Fafa Moussu aux Mimosas, président"),
                ("Qui est Marcel Dupuis ?", "Devrait trouver le professionnel Marcel Dupuis, plombier chez Plomberie Express"),
                ("Qui est Jean Martin ?", "Devrait trouver Jean Martin, copropriétaire aux Mimosas lot A05"),
                ("C'est qui Sophie Bernard ?", "Devrait trouver Sophie Bernard, copropriétaire aux Mimosas"),
                ("Connais-tu André Martin ?", "Devrait trouver André Martin, électricien chez Électricité Plus"),
            ]
        },
        {
            "category": "🏢 RECHERCHES SIMPLES - Copropriétés",
            "tests": [
                ("Où se trouve la Résidence Les Mimosas ?", "12 avenue des Fleurs, Lyon 69003"),
                ("Combien de lots a le Domaine Saint-Jean ?", "120 lots"),
                ("Quelle est l'adresse de Villa Marguerite ?", "5 rue Marguerite, Caluire-et-Cuire"),
                ("La Tour Montchat a combien d'étages ?", "Devrait mentionner 15 étages (via notes ou calcul lots)"),
            ]
        },

        # =================================================================
        # NIVEAU 2: RECHERCHES PAR CRITÈRES
        # =================================================================
        {
            "category": "📍 RECHERCHES PAR VILLE/LIEU",
            "tests": [
                ("Quelles copropriétés sont à Lyon ?", "Devrait lister: Mimosas, Saint-Jean, Arc-en-Ciel, Tour Montchat"),
                ("Quelles sont les copropriétés à Marseille ?", "Devrait trouver: Les Jardins de Provence"),
                ("Y a-t-il des copropriétés à Écully ?", "Devrait trouver: Le Hameau des Cerisiers"),
                ("Quels professionnels travaillent à Lyon ?", "Devrait lister plusieurs professionnels lyonnais"),
                ("Qui sont les jardiniers à Marseille ?", "Devrait trouver Sophie Soleil - Jardins du Midi"),
            ]
        },
        {
            "category": "📅 RECHERCHES PAR DATE/ANNÉE",
            "tests": [
                ("Quelles copropriétés ont été construites avant 1980 ?", "Mimosas (1975), Saint-Jean (1962), Arc-en-Ciel (1930), Tour Montchat (1970)"),
                ("Quels immeubles sont les plus récents ?", "Villa Marguerite (2018), Jardins de Provence (2005)"),
                ("Y a-t-il des bâtiments des années 60 ?", "Domaine Saint-Jean (1962)"),
            ]
        },
        {
            "category": "👷 RECHERCHES PROFESSIONNELS PAR MÉTIER",
            "tests": [
                ("Qui sont les plombiers ?", "Devrait lister: Plomberie Express, SOS Plomberie, Fontaine Plomberie, Plomberie du Sud"),
                ("Donne-moi la liste des électriciens", "Électricité Plus, Leclerc Élec, Élec Services"),
                ("Quels jardiniers connais-tu ?", "Jardins et Paysages, Vert Espace, Fleur et Jardin, Jardins du Midi"),
                ("Qui peut réparer un ascenseur ?", "Ascenseurs Rhône-Alpes"),
                ("Y a-t-il des couvreurs ?", "Toiture Expert - Jacques Toit"),
            ]
        },

        # =================================================================
        # NIVEAU 3: RECHERCHES MULTI-CRITÈRES
        # =================================================================
        {
            "category": "🔗 RECHERCHES MULTI-CRITÈRES",
            "tests": [
                ("Qui sont les présidents de copropriété ?", "Devrait lister tous les copropriétaires avec statut_special='président'"),
                ("Quels copropriétaires habitent aux Mimosas ?", "Devrait lister les 6 copropriétaires des Mimosas"),
                ("Qui sont les locataires ?", "Devrait filtrer ceux avec statut='locataire'"),
                ("Quels professionnels ont plus de 50 interventions ?", "Devrait filtrer par total_jobs > 50"),
                ("Quels sont les plombiers bien notés ?", "Devrait filtrer plombiers avec rating > 4"),
            ]
        },

        # =================================================================
        # NIVEAU 4: REQUÊTES COMPLEXES
        # =================================================================
        {
            "category": "🎯 REQUÊTES COMPLEXES",
            "tests": [
                ("Comment contacter le président des Mimosas ?", "Devrait retourner Fafa Moussu + email/téléphone"),
                ("Quel est le mail d'Électricité Plus ?", "contact@electricite-plus.fr - TEST COMPANY_NAME"),
                ("Donne-moi le téléphone de Plomberie Express", "04 78 12 34 56"),
                ("Qui habite au 5ème étage de la Tour Montchat ?", "Corinne Bertrand, lot 501"),
                ("Quelles copropriétés ont un ascenseur ?", "Mimosas, Saint-Jean, Tour Montchat"),
                ("Quelles copropriétés ont une piscine ?", "Saint-Jean, Jardins de Provence"),
            ]
        },

        # =================================================================
        # NIVEAU 5: CONTEXTE CONVERSATIONNEL
        # =================================================================
        {
            "category": "💬 CONTEXTE CONVERSATIONNEL (tests séquentiels)",
            "tests": [
                # Ces tests doivent être exécutés dans l'ordre avec le même session_id
            ]
        },

        # =================================================================
        # NIVEAU 6: EDGE CASES
        # =================================================================
        {
            "category": "⚠️ EDGE CASES",
            "tests": [
                ("Qui est Zorro ?", "Devrait indiquer qu'aucune personne de ce nom n'existe"),
                ("Quelles copropriétés sont à Tokyo ?", "Devrait indiquer aucune copropriété à Tokyo"),
                ("Y a-t-il des astronautes parmi les professionnels ?", "Devrait indiquer aucun astronaute"),
                ("Quel est le mail de quelqu'un qui n'existe pas ?", "Devrait gérer gracieusement l'absence de résultat"),
            ]
        },
    ]

    results = {"passed": 0, "failed": 0, "tests": []}

    for category_data in tests:
        category = category_data["category"]
        print(f"\n{category}")
        print("-" * 60)

        for query, expected in category_data["tests"]:
            result = await test_sql_agent(query, expected)
            results["tests"].append(result)

            if result["success"]:
                # Afficher un résumé
                response_preview = result["response"][:200] + "..." if len(result["response"]) > 200 else result["response"]
                print(f"\n  ✅ {query}")
                print(f"  📝 Attendu: {expected}")
                print(f"  🤖 Agents: {', '.join(result.get('agents_used', ['unknown']))}")
                print(f"  💬 Réponse: {response_preview}")
                results["passed"] += 1
            else:
                print(f"\n  ❌ {query}")
                print(f"  ⚠️ Erreur: {result.get('error', 'Unknown error')}")
                results["failed"] += 1

            # Petite pause pour ne pas surcharger
            await asyncio.sleep(0.5)

    # Tests conversationnels séquentiels
    print("\n💬 TESTS CONTEXTUELS (même session)")
    print("-" * 60)

    session_id = f"test-context-{datetime.now().strftime('%H%M%S')}"
    context_tests = [
        ("Qui habite aux Mimosas ?", "Liste des résidents des Mimosas"),
        ("Donne-moi leur email", "Devrait retourner les emails des copropriétaires Mimosas UNIQUEMENT"),
        ("Qui est le président ?", "Devrait comprendre 'président des Mimosas' = Fafa Moussu"),
    ]

    for query, expected in context_tests:
        result = await test_sql_agent(query, expected, session_id=session_id)
        results["tests"].append(result)

        if result["success"]:
            response_preview = result["response"][:200] + "..." if len(result["response"]) > 200 else result["response"]
            print(f"\n  ✅ {query}")
            print(f"  📝 Attendu: {expected}")
            print(f"  🤖 Agents: {', '.join(result.get('agents_used', ['unknown']))}")
            print(f"  💬 Réponse: {response_preview}")
            results["passed"] += 1
        else:
            print(f"\n  ❌ {query}: {result.get('error', 'Unknown error')}")
            results["failed"] += 1

        await asyncio.sleep(1)  # Plus de temps pour le contexte

    # Résumé final
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    print(f"  ✅ Réussis: {results['passed']}")
    print(f"  ❌ Échoués: {results['failed']}")
    print(f"  📈 Taux de réussite: {results['passed']/(results['passed']+results['failed'])*100:.1f}%")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*80)
    print("🚀 CRASH TEST SQL AGENT - Données Syndic de Copropriété")
    print("="*80)

    # Étape 1: Nettoyer et importer les données
    clear_all_data()
    import_coproprietes()
    import_coproprietaires()
    import_professionnels()
    verify_data()

    print("\n" + "="*80)
    print("✅ DONNÉES IMPORTÉES AVEC SUCCÈS")
    print("="*80)
    print("\nPour lancer les tests de l'agent SQL, exécutez:")
    print("  python -c \"import asyncio; from tests.crash_test_sql_agent import run_test_suite; asyncio.run(run_test_suite())\"")
    print("\nOu appelez run_test_suite() depuis ce module.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Mode test: importer données puis lancer les tests
        main()
        print("\n🧪 Lancement des tests...")
        asyncio.run(run_test_suite())
    else:
        # Mode import seulement
        main()
