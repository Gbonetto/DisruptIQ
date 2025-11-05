#!/usr/bin/env python3
"""
Generate Sample Invoices for ML Training

Creates sample validated invoices in the database for testing
the category classifier training.

Usage:
    python scripts/generate_sample_invoices.py --count 100
"""

import asyncio
import argparse
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models.invoice import FactureGlobal, FactureStatut, ExtractionMethod
import structlog

logger = structlog.get_logger()


# Sample texts for each category
CATEGORY_SAMPLES = {
    "Plomberie": [
        "Réparation fuite robinet cuisine. Remplacement joint. Intervention plombier.",
        "Débouchage canalisation évier. Détartrage siphon. Plomberie urgence.",
        "Installation nouveau cumulus 200L. Chauffe-eau électrique. Raccordement eau chaude.",
        "Changement robinetterie salle de bain. Mitigeur thermostatique douche.",
        "Réparation fuite WC. Remplacement mécanisme chasse d'eau. Plomberie sanitaire.",
        "Détection fuite eau sous évier. Réparation tuyauterie. Intervention plombier agréé.",
        "Installation lave-vaisselle. Raccordement arrivée eau et évacuation.",
        "Rénovation installation sanitaire. Remplacement tuyaux cuivre. Plomberie complète.",
    ],
    "Électricité": [
        "Mise aux normes tableau électrique. Installation disjoncteurs différentiels.",
        "Réparation panne électrique parties communes. Intervention électricien urgence.",
        "Installation éclairage LED couloirs. Remplacement ampoules et interrupteurs.",
        "Vérification installation électrique. Contrôle conformité. Rapport sécurité.",
        "Réparation court-circuit. Changement fusibles tableau. Électricité urgence.",
        "Installation prises électriques supplémentaires. Câblage mural.",
        "Remplacement compteur électrique. Mise en service EDF. Raccordement.",
        "Dépannage panne générale. Réparation ligne principale. Électricien certifié.",
    ],
    "Chauffage": [
        "Entretien annuel chaudière gaz. Nettoyage brûleurs. Contrôle combustion.",
        "Réparation chauffage central. Remplacement circulateur. Chauffagiste.",
        "Installation thermostat programmable. Régulation température. Économie énergie.",
        "Dépannage chaudière panne. Réparation vanne trois voies. Urgence chauffage.",
        "Purge radiateurs immeuble. Rééquilibrage installation. Chauffage collectif.",
        "Remplacement chaudière fioul par chaudière condensation gaz.",
        "Installation pompe à chaleur air/eau. Chauffage écologique. PAC.",
        "Ramonage conduit cheminée. Nettoyage fumées. Certificat ramonage.",
    ],
    "Jardinage": [
        "Tonte pelouse espaces verts. Entretien jardin copropriété.",
        "Taille haies et arbustes. Élagage branches. Paysagiste professionnel.",
        "Désherbage allées parking. Traitement végétaux. Entretien extérieur.",
        "Plantation massifs fleurs. Aménagement paysager. Jardin espaces communs.",
        "Entretien espaces verts mensuel. Tonte, taille, arrosage.",
        "Élagage arbres haute tige. Sécurisation branches. Paysagiste grimpeur.",
        "Installation arrosage automatique. Programmateur jardin.",
        "Nettoyage automne feuilles mortes. Ramassage déchets verts.",
    ],
    "Nettoyage": [
        "Nettoyage parties communes hebdomadaire. Sols, escaliers, ascenseur.",
        "Lavage vitres copropriété. Nettoyage façades vitrées. Société spécialisée.",
        "Désinfection poubelles locaux. Hygiène déchets. Nettoyage containers.",
        "Nettoyage après travaux. Dépoussièrage, lavage sols. Prestation complète.",
        "Entretien quotidien hall entrée. Ménage parties communes.",
        "Nettoyage parking sous-sol. Balayage, lavage haute pression.",
        "Désinfection COVID espaces communs. Protocole sanitaire. Hygiène.",
        "Nettoyage moquettes couloirs. Shampouinage professionnel.",
    ],
    "Ascenseur": [
        "Maintenance ascenseur mensuelle. Contrôle sécurité. Société OTIS.",
        "Réparation panne ascenseur. Dépannage urgence 24/7. Ascensoriste.",
        "Contrôle technique ascenseur annuel. Vérification conforme règlement.",
        "Modernisation cabine ascenseur. Remplacement portes automatiques.",
        "Contrat entretien ascenseur. Maintenance préventive. Dépannage inclus.",
        "Remplacement câbles ascenseur. Mise aux normes sécurité.",
        "Installation miroir et main courante cabine. Accessibilité PMR.",
        "Dépannage blocage ascenseur. Libération personnes bloquées. Urgence.",
    ],
    "Assurance": [
        "Prime assurance multirisque immeuble. Contrat annuel copropriété.",
        "Assurance responsabilité civile syndic. Garantie dommages.",
        "Cotisation assurance dommages ouvrage. Protection construction.",
        "Assurance protection juridique copropriété. Défense litiges.",
        "Renouvellement contrat assurance habitation parties communes.",
        "Franchise assurance sinistre dégât des eaux. Remboursement.",
        "Assurance tous risques chantier. Couverture travaux rénovation.",
        "Prime assurance loyers impayés. Garantie propriétaire.",
    ],
    "Juridique": [
        "Honoraires avocat contentieux voisinage. Procédure tribunal.",
        "Frais notaire acte copropriété. Modification règlement.",
        "Consultation juridique litige syndic. Conseil avocat spécialisé.",
        "Honoraires huissier constat dégradations. Procès-verbal officiel.",
        "Frais procédure judiciaire. Assignation tribunal grande instance.",
        "Consultation avocat droit immobilier. Conseil copropriété.",
        "Honoraires expert judiciaire. Évaluation dommages sinistre.",
        "Frais avocat assemblée générale contestation. Recours justice.",
    ],
    "Comptabilité": [
        "Honoraires expert-comptable. Tenue comptabilité annuelle copropriété.",
        "Audit comptable exercice. Vérification comptes. Cabinet comptable.",
        "Établissement bilan financier. Comptes annuels copropriété.",
        "Honoraires commissaire aux comptes. Certification comptes.",
        "Révision comptable exercice clos. Expert-comptable diplômé.",
        "Consultation fiscale copropriété. Optimisation charges déductibles.",
        "Établissement déclarations fiscales. TVA travaux copropriété.",
        "Honoraires comptable clôture comptes. Bilan exercice.",
    ],
    "Divers": [
        "Frais administratifs gestion copropriété. Fournitures bureau.",
        "Abonnement internet parties communes. Wi-Fi hall entrée.",
        "Frais postaux courriers copropriétaires. Envoi convocations AG.",
        "Achat matériel entretien. Produits nettoyage, balais, seaux.",
        "Abonnement eau parties communes. Consommation arrosage.",
        "Frais bancaires compte copropriété. Commission gestion.",
        "Achat panneau affichage parties communes. Signalétique.",
        "Fournitures diverses copropriété. Petit matériel maintenance.",
    ]
}


async def generate_invoices(count: int):
    """
    Generate sample validated invoices.

    Args:
        count: Number of invoices to generate
    """
    logger.info("generating_sample_invoices", count=count)

    async with AsyncSessionLocal() as db:
        categories = list(CATEGORY_SAMPLES.keys())
        invoices_per_category = count // len(categories)

        total_created = 0

        for category in categories:
            samples = CATEGORY_SAMPLES[category]

            for i in range(invoices_per_category):
                # Generate realistic invoice data
                montant_ht = Decimal(random.uniform(50, 5000)).quantize(Decimal('0.01'))
                taux_tva = Decimal('20.00')
                montant_tva = (montant_ht * taux_tva / 100).quantize(Decimal('0.01'))
                montant_ttc = montant_ht + montant_tva

                # Random date in last 2 years
                days_ago = random.randint(0, 730)
                invoice_date = date.today() - timedelta(days=days_ago)

                # Random sample text for this category
                raw_text = random.choice(samples)

                # Create invoice
                invoice = FactureGlobal(
                    numero=f"{category[:3].upper()}-{random.randint(1000, 9999)}",
                    date_facture=invoice_date,
                    montant_ht=montant_ht,
                    montant_tva=montant_tva,
                    montant_ttc=montant_ttc,
                    categorie=category,
                    statut=FactureStatut.VALIDEE.value,
                    extraction_method=ExtractionMethod.OCR.value,
                    needs_review=False,
                    metadata_json={
                        "raw_text": raw_text,
                        "generated": True
                    }
                )

                db.add(invoice)
                total_created += 1

        await db.commit()

        logger.info("sample_invoices_created", count=total_created)

        print("\n" + "="*60)
        print("✅ SAMPLE INVOICES GENERATED")
        print("="*60)
        print(f"\n📊 Summary:")
        print(f"  Total Invoices:     {total_created}")
        print(f"  Categories:         {len(categories)}")
        print(f"  Per Category:       ~{invoices_per_category}")
        print(f"\n📚 Categories:")
        for cat in sorted(categories):
            print(f"  - {cat}")
        print("\n" + "="*60)
        print("\n💡 Next Steps:")
        print("  1. Train the classifier:")
        print("     python scripts/train_category_classifier.py --min-samples 5")
        print("\n  2. The trained model will be saved in models/")
        print("\n" + "="*60)


async def main():
    parser = argparse.ArgumentParser(
        description="Generate sample invoices for ML training"
    )
    parser.add_argument(
        '--count',
        type=int,
        default=100,
        help='Number of invoices to generate (default: 100)'
    )

    args = parser.parse_args()

    await generate_invoices(args.count)


if __name__ == "__main__":
    asyncio.run(main())
