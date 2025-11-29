#!/usr/bin/env python
"""
Load SQL Fixtures into PostgreSQL Database

This script loads test fixtures from tests/fixtures/sql_fixtures.py
into the PostgreSQL database for E2E testing and demo purposes.

Usage:
    cd backend
    python scripts/load_sql_fixtures.py [--force]

Options:
    --force  Drop and recreate data even if it exists
"""

import asyncio
import argparse
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from typing import Dict, Any, List
import structlog

logger = structlog.get_logger()


async def load_fixtures(force: bool = False) -> Dict[str, Any]:
    """
    Load all SQL fixtures into PostgreSQL.

    Args:
        force: If True, delete existing data first

    Returns:
        Dict with loading statistics
    """
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal as async_session_maker

    stats = {
        "coproprietes": 0,
        "coproprietaires": 0,
        "professionnels": 0,
        "emails": 0,
        "documents": 0,
        "errors": []
    }

    async with async_session_maker() as session:
        try:
            # Check if data already exists
            result = await session.execute(text("SELECT COUNT(*) FROM coproprietes"))
            existing_count = result.scalar()

            if existing_count > 0 and not force:
                print(f"Database already has {existing_count} copropriétés.")
                print("Use --force to reload fixtures.")
                return stats

            if force and existing_count > 0:
                print("Force mode: Deleting existing fixtures...")
                # Delete in reverse FK order
                await session.execute(text("DELETE FROM documents WHERE copropriete_id IN (SELECT id FROM coproprietes WHERE nom IN ('Les Mimosas', 'Les Platanes'))"))
                await session.execute(text("DELETE FROM emails WHERE copropriete_id IN (SELECT id FROM coproprietes WHERE nom IN ('Les Mimosas', 'Les Platanes'))"))
                await session.execute(text("DELETE FROM professionnels_coproprietes WHERE copropriete_id IN (SELECT id FROM coproprietes WHERE nom IN ('Les Mimosas', 'Les Platanes'))"))
                await session.execute(text("DELETE FROM coproprietaires WHERE copropriete_id IN (SELECT id FROM coproprietes WHERE nom IN ('Les Mimosas', 'Les Platanes'))"))
                await session.execute(text("DELETE FROM coproprietes WHERE nom IN ('Les Mimosas', 'Les Platanes')"))
                # Don't delete professionnels as they might be shared
                await session.commit()
                print("Existing fixture data deleted.")

            # ================================================================
            # Load Copropriétés
            # ================================================================
            print("Loading copropriétés...")
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
                    "reference_syndic": "MIM-2020-001"
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
                    "reference_syndic": "PLT-2021-042"
                }
            ]

            for copro in coproprietes:
                await session.execute(
                    text("""
                        INSERT INTO coproprietes (nom, adresse, ville, code_postal, nombre_lots, nombre_batiments, annee_construction, syndic, contact_syndic, reference_syndic)
                        VALUES (:nom, :adresse, :ville, :code_postal, :nombre_lots, :nombre_batiments, :annee_construction, :syndic, :contact_syndic, :reference_syndic)
                        ON CONFLICT (nom) DO UPDATE SET
                            adresse = EXCLUDED.adresse,
                            nombre_lots = EXCLUDED.nombre_lots
                    """),
                    copro
                )
                stats["coproprietes"] += 1

            await session.commit()

            # Get IDs
            result = await session.execute(text("SELECT id FROM coproprietes WHERE nom = 'Les Mimosas'"))
            mimosas_id = result.scalar()
            result = await session.execute(text("SELECT id FROM coproprietes WHERE nom = 'Les Platanes'"))
            platanes_id = result.scalar()

            print(f"  Les Mimosas: id={mimosas_id}")
            print(f"  Les Platanes: id={platanes_id}")

            # ================================================================
            # Load Copropriétaires
            # ================================================================
            print("Loading copropriétaires...")

            # Les Mimosas owners
            mimosas_owners = [
                {"nom": "Dupont", "prenom": "Jean-Pierre", "email": "jp.dupont@gmail.com",
                 "telephone": "0145678910", "copropriete_id": mimosas_id, "numero_lot": "A101",
                 "type_lot": "Appartement", "etage": 1, "surface": 75.5, "statut": "proprietaire"},
                {"nom": "Martin", "prenom": "Sophie", "email": "s.martin@orange.fr",
                 "telephone": "0145678911", "copropriete_id": mimosas_id, "numero_lot": "A102",
                 "type_lot": "Appartement", "etage": 1, "surface": 65.0, "statut": "proprietaire"},
                {"nom": "Bernard", "prenom": "Michel", "email": "m.bernard@free.fr",
                 "telephone": "0145678912", "copropriete_id": mimosas_id, "numero_lot": "A201",
                 "type_lot": "Appartement", "etage": 2, "surface": 82.0, "statut": "proprietaire"},
                {"nom": "Petit", "prenom": "Marie", "email": "marie.petit@yahoo.fr",
                 "telephone": "0611223344", "copropriete_id": mimosas_id, "numero_lot": "A202",
                 "type_lot": "Appartement", "etage": 2, "surface": 55.0, "statut": "proprietaire"},
                {"nom": "Lefebvre", "prenom": "Pierre", "email": "p.lefebvre@gmail.com",
                 "telephone": "0145678914", "copropriete_id": mimosas_id, "numero_lot": "B101",
                 "type_lot": "Appartement", "etage": 1, "surface": 95.0, "statut": "proprietaire"},
                {"nom": "Garcia", "prenom": "Carmen", "email": "c.garcia@hotmail.com",
                 "telephone": "0677889900", "copropriete_id": mimosas_id, "numero_lot": "B201",
                 "type_lot": "Appartement", "etage": 2, "surface": 70.0, "statut": "proprietaire"},
                {"nom": "Durand", "prenom": "François", "email": "f.durand@wanadoo.fr",
                 "telephone": "0145678916", "copropriete_id": mimosas_id, "numero_lot": "C101",
                 "type_lot": "Local commercial", "etage": 0, "surface": 120.0, "statut": "proprietaire"},
                {"nom": "Moreau", "prenom": "Isabelle", "email": "i.moreau@gmail.com",
                 "telephone": "0622334455", "copropriete_id": mimosas_id, "numero_lot": "D301",
                 "type_lot": "Appartement", "etage": 3, "surface": 88.0, "statut": "proprietaire"},
                {"nom": "Laurent", "prenom": "Thomas", "email": "t.laurent@sfr.fr",
                 "telephone": "0145678918", "copropriete_id": mimosas_id, "numero_lot": "D302",
                 "type_lot": "Appartement", "etage": 3, "surface": 62.0, "statut": "proprietaire"},
                {"nom": "Simon", "prenom": "Nathalie", "email": "n.simon@gmail.com",
                 "telephone": "0633445566", "copropriete_id": mimosas_id, "numero_lot": "E101",
                 "type_lot": "Studio", "etage": 1, "surface": 28.0, "statut": "proprietaire"},
                {"nom": "Michel", "prenom": "Alain", "email": "a.michel@laposte.net",
                 "telephone": "0145678920", "copropriete_id": mimosas_id, "numero_lot": "E201",
                 "type_lot": "Appartement", "etage": 2, "surface": 45.0, "statut": "proprietaire"},
                {"nom": "Robert", "prenom": "Claire", "email": "c.robert@gmail.com",
                 "telephone": "0644556677", "copropriete_id": mimosas_id, "numero_lot": "E202",
                 "type_lot": "Appartement", "etage": 2, "surface": 52.0, "statut": "proprietaire"},
            ]

            # Les Platanes owners
            platanes_owners = [
                {"nom": "Faure", "prenom": "Jacques", "email": "j.faure@gmail.com",
                 "telephone": "0478123456", "copropriete_id": platanes_id, "numero_lot": "A101",
                 "type_lot": "Appartement", "etage": 1, "surface": 85.0, "statut": "proprietaire"},
                {"nom": "Blanc", "prenom": "Martine", "email": "m.blanc@orange.fr",
                 "telephone": "0478123457", "copropriete_id": platanes_id, "numero_lot": "A102",
                 "type_lot": "Appartement", "etage": 1, "surface": 72.0, "statut": "proprietaire"},
                {"nom": "Rousseau", "prenom": "Philippe", "email": "p.rousseau@free.fr",
                 "telephone": "0612345678", "copropriete_id": platanes_id, "numero_lot": "A201",
                 "type_lot": "Appartement", "etage": 2, "surface": 90.0, "statut": "proprietaire"},
                {"nom": "Girard", "prenom": "Olivier", "email": "o.girard@gmail.com",
                 "telephone": "0478123459", "copropriete_id": platanes_id, "numero_lot": "B101",
                 "type_lot": "Appartement", "etage": 1, "surface": 78.0, "statut": "proprietaire"},
                {"nom": "Bonnet", "prenom": "Sylvie", "email": "s.bonnet@hotmail.com",
                 "telephone": "0698765432", "copropriete_id": platanes_id, "numero_lot": "B201",
                 "type_lot": "Appartement", "etage": 2, "surface": 65.0, "statut": "proprietaire"},
                {"nom": "Dubois", "prenom": "André", "email": "a.dubois@wanadoo.fr",
                 "telephone": "0478123461", "copropriete_id": platanes_id, "numero_lot": "B202",
                 "type_lot": "Appartement", "etage": 2, "surface": 58.0, "statut": "proprietaire"},
                {"nom": "Mercier", "prenom": "Céline", "email": "c.mercier@gmail.com",
                 "telephone": "0687654321", "copropriete_id": platanes_id, "numero_lot": "C01",
                 "type_lot": "Local commercial", "etage": 0, "surface": 95.0, "statut": "proprietaire"},
                {"nom": "Fournier", "prenom": "Luc", "email": "l.fournier@sfr.fr",
                 "telephone": "0478123463", "copropriete_id": platanes_id, "numero_lot": "C02",
                 "type_lot": "Local commercial", "etage": 0, "surface": 80.0, "statut": "proprietaire"},
            ]

            for owner in mimosas_owners + platanes_owners:
                await session.execute(
                    text("""
                        INSERT INTO coproprietaires (nom, prenom, email, telephone, copropriete_id, numero_lot, type_lot, etage, surface, statut)
                        VALUES (:nom, :prenom, :email, :telephone, :copropriete_id, :numero_lot, :type_lot, :etage, :surface, :statut)
                    """),
                    owner
                )
                stats["coproprietaires"] += 1

            await session.commit()
            print(f"  {stats['coproprietaires']} copropriétaires loaded")

            # ================================================================
            # Load Professionnels
            # ================================================================
            print("Loading professionnels...")

            professionnels = [
                {"name": "Jean Plombier", "company_name": "Plomberie Express", "category": "plombier",
                 "email": "contact@plomberie-express.fr", "phone": "0145678901", "city": "Paris",
                 "postal_code": "75015", "statut": "active", "rating": 4.5},
                {"name": "Marie Électricien", "company_name": "Élec Plus", "category": "électricien",
                 "email": "contact@elec-plus.fr", "phone": "0145678902", "city": "Paris",
                 "postal_code": "75015", "statut": "active", "rating": 4.8},
                {"name": "Paul Serrurier", "company_name": "Serrurerie 24h", "category": "serrurier",
                 "email": "contact@serrurerie24h.fr", "phone": "0145678903", "city": "Paris",
                 "postal_code": "75015", "statut": "active", "rating": 4.2},
                {"name": "Sophie Jardinier", "company_name": "Jardins Verdure", "category": "jardinier",
                 "email": "contact@jardins-verdure.fr", "phone": "0145678904", "city": "Paris",
                 "postal_code": "75016", "statut": "active", "rating": 4.7},
                {"name": "Luc Chauffagiste", "company_name": "Chauff Expert", "category": "chauffagiste",
                 "email": "contact@chauff-expert.fr", "phone": "0478123400", "city": "Lyon",
                 "postal_code": "69003", "statut": "active", "rating": 4.6},
                {"name": "Anne Peintre", "company_name": "Peinture Pro", "category": "peintre",
                 "email": "contact@peinture-pro.fr", "phone": "0145678906", "city": "Paris",
                 "postal_code": "75015", "statut": "active", "rating": 4.4},
                {"name": "Marc Menuisier", "company_name": "Menuiserie Moderne", "category": "menuisier",
                 "email": "contact@menuiserie-moderne.fr", "phone": "0145678907", "city": "Paris",
                 "postal_code": "75014", "statut": "active", "rating": 4.3},
                {"name": "Pierre Maçon", "company_name": "Maçonnerie BTP", "category": "maçon",
                 "email": "contact@maconnerie-btp.fr", "phone": "0478123408", "city": "Lyon",
                 "postal_code": "69003", "statut": "active", "rating": 4.1},
                {"name": "Julie Ascensoriste", "company_name": "Ascenseurs Plus", "category": "ascensoriste",
                 "email": "contact@ascenseurs-plus.fr", "phone": "0145678909", "city": "Paris",
                 "postal_code": "75017", "statut": "active", "rating": 4.9},
            ]

            for pro in professionnels:
                await session.execute(
                    text("""
                        INSERT INTO professionnels (name, company_name, category, email, phone, city, postal_code, statut, rating)
                        VALUES (:name, :company_name, :category, :email, :phone, :city, :postal_code, :statut, :rating)
                        ON CONFLICT DO NOTHING
                    """),
                    pro
                )
                stats["professionnels"] += 1

            await session.commit()
            print(f"  {stats['professionnels']} professionnels loaded")

            # ================================================================
            # Load Emails
            # ================================================================
            print("Loading emails...")

            now = datetime.now()
            emails = [
                {"message_id": f"fix-{now.timestamp()}-1", "sender": "jp.dupont@gmail.com",
                 "subject": "Fuite d'eau urgente appartement A101",
                 "body": "Bonjour, j'ai une fuite d'eau importante dans ma salle de bain. L'eau commence à couler chez le voisin du dessous. Merci de m'envoyer un plombier en urgence.",
                 "urgency": "URGENT", "copropriete_id": mimosas_id,
                 "received_at": now - timedelta(hours=2)},
                {"message_id": f"fix-{now.timestamp()}-2", "sender": "s.martin@orange.fr",
                 "subject": "Question sur les charges du 3ème trimestre",
                 "body": "Bonjour, je souhaiterais avoir des précisions sur l'appel de charges du 3ème trimestre. Le montant me semble plus élevé que d'habitude.",
                 "urgency": "ROUTINE", "copropriete_id": mimosas_id,
                 "received_at": now - timedelta(days=3)},
                {"message_id": f"fix-{now.timestamp()}-3", "sender": "p.lefebvre@gmail.com",
                 "subject": "Convocation conseil syndical",
                 "body": "En tant que président du conseil syndical, je souhaite convoquer une réunion pour discuter du ravalement de façade. Pouvez-vous m'envoyer les derniers devis reçus ?",
                 "urgency": "IMPORTANT", "copropriete_id": mimosas_id,
                 "received_at": now - timedelta(days=1)},
                {"message_id": f"fix-{now.timestamp()}-4", "sender": "j.faure@gmail.com",
                 "subject": "Problème de chauffage bâtiment A",
                 "body": "Bonjour, plusieurs copropriétaires du bâtiment A signalent des radiateurs froids depuis hier. Pouvez-vous envoyer un chauffagiste ?",
                 "urgency": "IMPORTANT", "copropriete_id": platanes_id,
                 "received_at": now - timedelta(hours=5)},
                {"message_id": f"fix-{now.timestamp()}-5", "sender": "c.garcia@hotmail.com",
                 "subject": "Demande d'échelonnement de paiement",
                 "body": "Bonjour, suite à des difficultés financières temporaires, je souhaiterais mettre en place un échelonnement de paiement pour régulariser ma situation.",
                 "urgency": "ROUTINE", "copropriete_id": mimosas_id,
                 "received_at": now - timedelta(days=7)},
            ]

            for email in emails:
                await session.execute(
                    text("""
                        INSERT INTO emails (message_id, sender, subject, body, urgency, copropriete_id, received_at, processed)
                        VALUES (:message_id, :sender, :subject, :body, :urgency, :copropriete_id, :received_at, false)
                        ON CONFLICT (message_id) DO NOTHING
                    """),
                    email
                )
                stats["emails"] += 1

            await session.commit()
            print(f"  {stats['emails']} emails loaded")

            print("\nFixtures loaded successfully!")
            return stats

        except Exception as e:
            logger.error("fixture_loading_failed", error=str(e))
            stats["errors"].append(str(e))
            await session.rollback()
            raise


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load SQL fixtures into PostgreSQL")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reload even if data exists"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("DisruptIQ SQL Fixtures Loader")
    print("=" * 60)
    print()

    try:
        stats = await load_fixtures(force=args.force)

        print()
        print("-" * 60)
        print("LOADING RESULTS")
        print("-" * 60)
        print(f"Copropriétés: {stats['coproprietes']}")
        print(f"Copropriétaires: {stats['coproprietaires']}")
        print(f"Professionnels: {stats['professionnels']}")
        print(f"Emails: {stats['emails']}")

        if stats["errors"]:
            print()
            print("ERRORS:")
            for error in stats["errors"]:
                print(f"  - {error}")
            return 1

        print()
        print("SUCCESS: All fixtures loaded!")
        return 0

    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
