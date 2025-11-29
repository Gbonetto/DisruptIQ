"""
RAG Test Fixtures for DisruptIQ E2E Tests

Provides realistic document content for testing the RAG system:
- Règlements de copropriété
- PV d'Assemblées Générales
- Contrats de syndic
- Contrats d'entretien
- Factures et devis

These documents match the SQL fixtures:
- Arc-en-Ciel (id=9) - Nice
- Le Clos des Oliviers (id=10) - Marseille
- Immeuble Haussmann Saint-Germain (id=11) - Paris

Usage:
    from tests.fixtures.rag_fixtures import RAGFixtures

    rag_fixtures = RAGFixtures()
    documents = rag_fixtures.get_all_documents()
    # Index documents into Qdrant
"""

from datetime import datetime
from typing import List, Dict, Any


class RAGFixtures:
    """
    RAG document fixtures for E2E testing.
    Provides realistic document content for the DisruptIQ copropriété system.
    """

    @staticmethod
    def get_all_documents() -> List[Dict[str, Any]]:
        """Get all RAG fixture documents"""
        return (
            RAGFixtures.get_arc_en_ciel_documents() +
            RAGFixtures.get_oliviers_documents() +
            RAGFixtures.get_haussmann_documents()
        )

    @staticmethod
    def get_arc_en_ciel_documents() -> List[Dict[str, Any]]:
        """Documents for Résidence Arc-en-Ciel copropriété"""
        return [
            RAGFixtures._reglement_arc_en_ciel(),
            RAGFixtures._pv_ag_arc_en_ciel_2024(),
            RAGFixtures._pv_ag_arc_en_ciel_2023(),
            RAGFixtures._contrat_syndic_arc_en_ciel(),
            RAGFixtures._devis_ravalement_arc_en_ciel(),
        ]

    @staticmethod
    def get_oliviers_documents() -> List[Dict[str, Any]]:
        """Documents for Le Clos des Oliviers copropriété"""
        return [
            RAGFixtures._reglement_oliviers(),
            RAGFixtures._pv_ag_oliviers_2024(),
            RAGFixtures._contrat_entretien_oliviers(),
        ]

    @staticmethod
    def get_haussmann_documents() -> List[Dict[str, Any]]:
        """Documents for Immeuble Haussmann Saint-Germain copropriété"""
        return [
            RAGFixtures._reglement_haussmann(),
            RAGFixtures._pv_ag_haussmann_2024(),
        ]

    # =========================================================================
    # RÉSIDENCE ARC-EN-CIEL - Documents
    # =========================================================================

    @staticmethod
    def _reglement_arc_en_ciel() -> Dict[str, Any]:
        return {
            "title": "Règlement de copropriété - Résidence Arc-en-Ciel",
            "doc_type": "reglement_copropriete",
            "copropriete_id": 9,
            "copropriete_name": "Résidence Arc-en-Ciel",
            "date": "1985-06-15",
            "chunks": [
                {
                    "page": 1,
                    "content": """RÈGLEMENT DE COPROPRIÉTÉ
RÉSIDENCE ARC-EN-CIEL
45 Boulevard Victor Hugo - 06000 NICE

Établi le 15 juin 1985

TITRE I - DÉSIGNATION DE L'IMMEUBLE

Article 1 - Description générale
L'immeuble est situé au 45 Boulevard Victor Hugo, 06000 Nice.
Il comprend 3 bâtiments (A, B, C) construits en 1985.
L'ensemble totalise 24 lots principaux répartis comme suit:
- 20 appartements
- 2 locaux commerciaux au rez-de-chaussée
- 2 studios

La copropriété dispose de:
- Un parking souterrain de 25 places
- Des espaces verts d'environ 400 m²
- Une loge de gardien"""
                },
                {
                    "page": 2,
                    "content": """TITRE II - PARTIES COMMUNES ET PARTIES PRIVATIVES

Article 2 - Parties communes générales
Sont des parties communes générales de l'immeuble:
- Le sol et le sous-sol
- Les fondations, les gros murs et les murs de soutènement
- Les toitures et terrasses
- Les halls d'entrée et escaliers
- Les canalisations principales (eau, gaz, électricité)
- Les ascenseurs
- Les espaces verts
- Le parking souterrain

Article 3 - Parties privatives
Sont des parties privatives:
- Les locaux composant chaque lot
- Les revêtements intérieurs (sols, murs, plafonds)
- Les portes palières et fenêtres
- Les installations sanitaires privatives
- Les compteurs individuels"""
                },
                {
                    "page": 3,
                    "content": """TITRE III - TRAVAUX

Article 10 - Travaux sur parties communes
Les travaux sur les parties communes doivent être votés en assemblée générale
selon les majorités prévues par la loi:
- Majorité simple (article 24) pour les travaux d'entretien courant
- Majorité absolue (article 25) pour les travaux d'amélioration
- Double majorité (article 26) pour les travaux de transformation

Article 11 - Travaux sur parties privatives
Les copropriétaires peuvent effectuer librement des travaux dans leurs
parties privatives, sous réserve de:
- Ne pas porter atteinte à la solidité de l'immeuble
- Ne pas nuire aux droits des autres copropriétaires
- Respecter la destination de l'immeuble

Travaux nécessitant une autorisation préalable de l'AG:
- Modification des façades (fenêtres, volets, climatiseurs)
- Percement de murs porteurs
- Modification des canalisations communes
- Installation d'antennes ou paraboles

Délai de déclaration: 30 jours minimum avant le début des travaux
pour les travaux mineurs ne nécessitant pas d'autorisation AG."""
                },
                {
                    "page": 4,
                    "content": """TITRE IV - CHARGES

Article 15 - Répartition des charges
Les charges sont réparties selon les tantièmes de copropriété:
- Charges générales: selon tantièmes généraux (entretien, assurance, honoraires syndic)
- Charges spéciales: selon utilité (ascenseur par bâtiment, chauffage)

Article 16 - Budget prévisionnel
Le budget prévisionnel annuel est voté en assemblée générale.
Les provisions sont appelées trimestriellement.
Le montant de la provision trimestrielle est égal au quart du budget.

Article 17 - Impayés
En cas de non-paiement des charges:
- Mise en demeure par lettre recommandée après 30 jours de retard
- Application des intérêts de retard au taux légal
- Procédure de recouvrement après 60 jours
- Le syndic peut faire inscrire une hypothèque légale

Article 18 - Fonds de travaux (Loi ALUR)
Un fonds de travaux est constitué conformément à la loi ALUR.
La cotisation annuelle est fixée à 5% du budget prévisionnel.
Ce fonds est destiné à financer les travaux prescrits par la loi
ou les travaux votés par l'assemblée générale."""
                },
                {
                    "page": 5,
                    "content": """TITRE V - ASSEMBLÉE GÉNÉRALE

Article 20 - Convocation
L'assemblée générale ordinaire se réunit au moins une fois par an.
La convocation est envoyée par le syndic au moins 21 jours avant la date.
Elle comprend:
- L'ordre du jour détaillé
- Les documents nécessaires aux décisions
- Les projets de résolutions

Article 21 - Quorum et majorités
Quorum: L'assemblée ne peut valablement délibérer que si les
copropriétaires présents ou représentés détiennent au moins 25%
des voix au premier tour, et sans condition au second tour.

Majorités:
- Article 24: Majorité des voix des copropriétaires présents ou représentés
- Article 25: Majorité des voix de tous les copropriétaires
- Article 26: Double majorité (2/3 des voix de tous les copropriétaires)

Article 22 - Procès-verbal
Le procès-verbal est rédigé par le secrétaire de séance.
Il est signé par le président, le secrétaire et les scrutateurs.
Il est envoyé aux copropriétaires absents dans les 2 mois.

TITRE VI - ANIMAUX

Article 30 - Animaux de compagnie
Les animaux de compagnie (chiens, chats, petits animaux) sont tolérés
dans les parties privatives sous réserve de ne pas causer de nuisances
aux autres copropriétaires.
Les chiens doivent être tenus en laisse dans les parties communes.
Les déjections doivent être ramassées immédiatement."""
                }
            ]
        }

    @staticmethod
    def _pv_ag_arc_en_ciel_2024() -> Dict[str, Any]:
        return {
            "title": "PV AG du 15 juin 2024 - Résidence Arc-en-Ciel",
            "doc_type": "pv_ag",
            "copropriete_id": 9,
            "copropriete_name": "Résidence Arc-en-Ciel",
            "date": "2024-06-15",
            "chunks": [
                {
                    "page": 1,
                    "content": """PROCÈS-VERBAL DE L'ASSEMBLÉE GÉNÉRALE ORDINAIRE
RÉSIDENCE ARC-EN-CIEL
45 Boulevard Victor Hugo - 06000 NICE

Tenue le 15 juin 2024 à 18h00
Salle de réunion - 45 Boulevard Victor Hugo

Présents et représentés: 10 copropriétaires sur 14
Tantièmes représentés: 7,850 sur 10,000 (78.5%)

Bureau de l'Assemblée:
- Président de séance: M. Pierre LEFEBVRE (Président du Conseil Syndical)
- Secrétaire: Mme Sophie MARTIN
- Scrutateurs: M. Michel BERNARD, Mme Isabelle MOREAU

Le quorum étant atteint, le Président déclare l'assemblée
régulièrement constituée."""
                },
                {
                    "page": 2,
                    "content": """RÉSOLUTION N°1 - APPROBATION DES COMPTES 2023
Le syndic présente les comptes de l'exercice 2023:
- Charges générales: 65,420 €
- Charges spéciales: 22,150 €
- Total des charges: 87,570 €
- Excédent de trésorerie: 5,230 €

Vote: Adopté à la majorité de l'article 24
Pour: 7,200 tantièmes / Contre: 450 tantièmes / Abstention: 200 tantièmes

RÉSOLUTION N°2 - QUITUS AU SYNDIC
L'assemblée donne quitus au syndic pour sa gestion de l'exercice 2023.
Vote: Adopté à la majorité de l'article 24
Pour: 6,800 tantièmes / Contre: 850 tantièmes / Abstention: 200 tantièmes

RÉSOLUTION N°3 - BUDGET PRÉVISIONNEL 2024-2025
Le syndic présente le budget prévisionnel: 95,000 €
Répartition:
- Entretien courant: 35,000 €
- Assurances: 10,000 €
- Honoraires syndic: 14,500 €
- Eau et énergie: 22,000 €
- Personnel: 10,500 €
- Provisions travaux: 3,000 €

Vote: Adopté à la majorité de l'article 24
Pour: 7,500 tantièmes / Contre: 150 tantièmes / Abstention: 200 tantièmes"""
                },
                {
                    "page": 3,
                    "content": """RÉSOLUTION N°4 - RAVALEMENT DE FAÇADE
Suite à l'injonction de la Mairie de Nice, l'assemblée doit se prononcer
sur les travaux de ravalement de la façade du bâtiment A.

Trois devis ont été présentés:
- Entreprise RAVALEMENT CÔTE D'AZUR: 38,000 € TTC
- Entreprise FACADES DE FRANCE: 42,500 € TTC
- Entreprise RENOVATION NICE: 45,200 € TTC

Le Conseil Syndical recommande l'entreprise RAVALEMENT CÔTE D'AZUR.

Vote: L'assemblée décide d'engager les travaux avec RAVALEMENT CÔTE D'AZUR
pour un montant de 38,000 € TTC.
Majorité de l'article 25 requise (5,001 tantièmes)
Pour: 6,200 tantièmes / Contre: 1,450 tantièmes / Abstention: 200 tantièmes
ADOPTÉ

Calendrier prévu: Travaux au printemps 2025
Financement: 50% sur fonds de travaux, 50% en appel de fonds spécial

RÉSOLUTION N°5 - RÉNOVATION ÉCLAIRAGE LED
L'assemblée se prononce sur le remplacement de l'éclairage des parties
communes par des LED basse consommation.

Devis retenu: ÉLECTRICITÉ VERTE NICE - 6,500 € TTC
Économie estimée: 40% sur la facture d'électricité

Vote: Adopté à la majorité de l'article 24
Pour: 7,100 tantièmes / Contre: 550 tantièmes / Abstention: 200 tantièmes"""
                },
                {
                    "page": 4,
                    "content": """RÉSOLUTION N°6 - INSTALLATION BORNES DE RECHARGE ÉLECTRIQUE
L'assemblée examine la proposition d'installation de bornes de recharge
pour véhicules électriques au parking souterrain.

Projet: Installation de 6 bornes de recharge
Coût total: 18,000 € TTC (incluant mise aux normes électriques)
Subvention ADVENIR obtenue: 6,000 €
Reste à charge copropriété: 12,000 €

Vote: L'assemblée décide de reporter cette décision à une AG extraordinaire
après étude complémentaire des besoins des copropriétaires.
Pour le report: 4,200 tantièmes / Contre le report: 3,450 tantièmes
REPORTÉ

RÉSOLUTION N°7 - MODIFICATION RÈGLEMENT (TRAVAUX PRIVATIFS)
L'assemblée propose de réduire le délai de déclaration des travaux
privatifs mineurs de 30 jours à 15 jours.

Vote: Adopté à la majorité de l'article 26 (2/3 = 6,667 tantièmes)
Pour: 6,800 tantièmes / Contre: 850 tantièmes / Abstention: 200 tantièmes
ADOPTÉ

Cette modification sera inscrite au registre de la copropriété."""
                },
                {
                    "page": 5,
                    "content": """RÉSOLUTION N°8 - CONTRAT DE SYNDIC 2024-2027
Le contrat de syndic avec SYNDIC CÔTE D'AZUR SA arrive à échéance.
L'assemblée doit se prononcer sur le renouvellement.

Proposition SYNDIC CÔTE D'AZUR SA:
- Honoraires annuels: 14,500 € TTC
- Durée: 3 ans (2024-2027)
- Prestations incluses: gestion courante, AG ordinaire, comptabilité

Vote: Adopté à la majorité de l'article 25
Pour: 5,800 tantièmes / Contre: 1,850 tantièmes / Abstention: 200 tantièmes
ADOPTÉ

RÉSOLUTION N°9 - ÉLECTION DU CONSEIL SYNDICAL
L'assemblée procède à l'élection des membres du conseil syndical:

Membres élus:
- M. Pierre LEFEBVRE (Président) - Lot B101
- M. Michel BERNARD - Lot A201
- Mme Carmen GARCIA - Lot B201
- Mme Isabelle MOREAU - Lot C301

Vote: Adopté à la majorité de l'article 25
Pour: 6,500 tantièmes

La séance est levée à 21h30.

Fait à Nice, le 15 juin 2024
[Signatures du Président, Secrétaire et Scrutateurs]"""
                }
            ]
        }

    @staticmethod
    def _pv_ag_arc_en_ciel_2023() -> Dict[str, Any]:
        return {
            "title": "PV AG du 20 juin 2023 - Résidence Arc-en-Ciel",
            "doc_type": "pv_ag",
            "copropriete_id": 9,
            "copropriete_name": "Résidence Arc-en-Ciel",
            "date": "2023-06-20",
            "chunks": [
                {
                    "page": 1,
                    "content": """PROCÈS-VERBAL DE L'ASSEMBLÉE GÉNÉRALE ORDINAIRE
RÉSIDENCE ARC-EN-CIEL

Tenue le 20 juin 2023 à 18h00

Présents et représentés: 11 copropriétaires sur 14
Tantièmes représentés: 7,200 sur 10,000 (72%)

RÉSOLUTION N°1 - APPROBATION DES COMPTES 2022
Comptes approuvés. Total des charges: 82,350 €
Vote: ADOPTÉ à l'unanimité

RÉSOLUTION N°2 - BUDGET PRÉVISIONNEL 2023-2024
Budget voté: 88,000 €
Vote: ADOPTÉ à la majorité de l'article 24

RÉSOLUTION N°3 - TRAVAUX URGENTS TOITURE BÂTIMENT C
Suite à des infiltrations signalées, l'assemblée vote des travaux
de réparation d'urgence de la toiture du bâtiment C.
Montant: 12,000 € TTC
Vote: ADOPTÉ à la majorité de l'article 25"""
                },
                {
                    "page": 2,
                    "content": """RÉSOLUTION N°4 - DIAGNOSTIC FAÇADE
La Mairie de Nice a notifié l'obligation de procéder au ravalement.
L'assemblée vote l'engagement d'un diagnostic façade.
Coût du diagnostic: 2,500 € TTC
Vote: ADOPTÉ à la majorité de l'article 24

RÉSOLUTION N°5 - MISE EN CONFORMITÉ ASCENSEUR
L'assemblée vote les travaux de mise en conformité de l'ascenseur
du bâtiment A selon les nouvelles normes de sécurité.
Montant: 18,000 € TTC
Vote: ADOPTÉ à la majorité de l'article 25

RÉSOLUTION N°6 - CONTRAT ENTRETIEN ESPACES VERTS
Renouvellement du contrat avec JARDINS MÉDITERRANÉE.
Montant annuel: 3,200 € TTC
Vote: ADOPTÉ à la majorité de l'article 24"""
                }
            ]
        }

    @staticmethod
    def _contrat_syndic_arc_en_ciel() -> Dict[str, Any]:
        return {
            "title": "Contrat de syndic 2024-2027 - Résidence Arc-en-Ciel",
            "doc_type": "contrat_syndic",
            "copropriete_id": 9,
            "copropriete_name": "Résidence Arc-en-Ciel",
            "date": "2024-07-01",
            "chunks": [
                {
                    "page": 1,
                    "content": """CONTRAT DE SYNDIC DE COPROPRIÉTÉ
Entre:
SYNDIC CÔTE D'AZUR SA
SIRET: 123 456 789 00012
25 Avenue Jean Médecin, 06000 NICE
Représenté par: M. Antoine DURAND, Gérant
Ci-après dénommé "le Syndic"

Et:
SYNDICAT DES COPROPRIÉTAIRES DE LA RÉSIDENCE ARC-EN-CIEL
45 Boulevard Victor Hugo, 06000 NICE
Représenté par: M. Pierre LEFEBVRE, Président du Conseil Syndical
Ci-après dénommé "le Syndicat"

ARTICLE 1 - OBJET DU CONTRAT
Le présent contrat a pour objet de définir les conditions dans lesquelles
le Syndic assure la gestion de la copropriété conformément aux dispositions
de la loi n° 65-557 du 10 juillet 1965 et du décret n° 67-223 du 17 mars 1967."""
                },
                {
                    "page": 2,
                    "content": """ARTICLE 2 - DURÉE DU CONTRAT
Le présent contrat est conclu pour une durée de 3 ans.
Date de début: 1er juillet 2024
Date de fin: 30 juin 2027

ARTICLE 3 - HONORAIRES
3.1 Forfait annuel de gestion courante: 14,500 € TTC
Comprenant:
- Administration courante de la copropriété
- Tenue de la comptabilité
- Organisation d'une assemblée générale ordinaire par an
- Visite de l'immeuble (4 par an minimum)
- Gestion des contrats d'entretien
- Recouvrement amiable des charges

3.2 Prestations particulières (tarif horaire: 75 € HT):
- Assemblée générale extraordinaire: 400 € HT
- Vacation pour travaux exceptionnels: 75 € HT/heure
- État daté: 350 € TTC
- Mise en demeure: 30 € HT
- Procédure de recouvrement contentieux: selon barème annexé"""
                },
                {
                    "page": 3,
                    "content": """ARTICLE 4 - OBLIGATIONS DU SYNDIC
Le syndic s'engage à:
- Exécuter les décisions de l'assemblée générale
- Établir le budget prévisionnel
- Appeler les fonds de charges
- Tenir la comptabilité du syndicat
- Conserver les archives
- Souscrire et gérer les contrats d'assurance
- Représenter le syndicat en justice (après autorisation AG)
- Établir et tenir à jour la fiche synthétique de copropriété
- Alimenter le registre des copropriétés

ARTICLE 5 - COMPTE SÉPARÉ
Conformément à la loi ALUR, le syndic ouvre un compte bancaire séparé
au nom du syndicat des copropriétaires.
Banque: CRÉDIT AGRICOLE NICE
IBAN: FR76 XXXX XXXX XXXX XXXX XXXX XXX

ARTICLE 6 - EXTRANET COPROPRIÉTÉ
Le syndic met à disposition un extranet permettant l'accès:
- Aux documents de la copropriété
- À l'état des comptes individuels
- Aux procès-verbaux d'assemblées générales
URL: https://arcenciel.syndic-coteazur.fr"""
                },
                {
                    "page": 4,
                    "content": """ARTICLE 7 - RESPONSABILITÉ
Le syndic est responsable des fautes de gestion dans l'exercice de ses fonctions.
Il souscrit une assurance responsabilité civile professionnelle.
Garantie financière: 90,000 € (CAISSE DES DÉPÔTS)

ARTICLE 8 - RÉSILIATION
Le contrat peut être résilié:
- À l'échéance, par vote de l'assemblée générale
- En cours de mandat, pour faute grave, par décision de justice
- Par le syndic, avec préavis de 3 mois

ARTICLE 9 - DONNÉES PERSONNELLES (RGPD)
Le syndic s'engage à respecter le Règlement Général sur la Protection
des Données. Les données des copropriétaires sont conservées pendant
la durée du mandat et 10 ans après la fin de la gestion.

ARTICLE 10 - LITIGES
Tout litige relatif au présent contrat sera soumis au Tribunal
Judiciaire de Nice.

Fait en deux exemplaires, à Nice, le 1er juillet 2024

[Signatures]
Pour le Syndic                    Pour le Syndicat
Antoine DURAND                    Pierre LEFEBVRE"""
                }
            ]
        }

    @staticmethod
    def _devis_ravalement_arc_en_ciel() -> Dict[str, Any]:
        return {
            "title": "Devis ravalement façade - Résidence Arc-en-Ciel",
            "doc_type": "devis",
            "copropriete_id": 9,
            "copropriete_name": "Résidence Arc-en-Ciel",
            "date": "2024-10-15",
            "chunks": [
                {
                    "page": 1,
                    "content": """DEVIS N° 2024-RAV-0542
RAVALEMENT CÔTE D'AZUR SARL
12 Rue des Artisans, 06200 NICE
SIRET: 987 654 321 00015
Tél: 04 93 45 67 89

Client: Copropriété Résidence Arc-en-Ciel
Adresse: 45 Boulevard Victor Hugo, 06000 Nice

Objet: Ravalement de façade - Bâtiment A

DESCRIPTIF DES TRAVAUX:
1. Installation échafaudage et protections
2. Nettoyage haute pression de la façade
3. Réparation des fissures et joints
4. Application d'un traitement anti-mousse
5. Peinture façade (2 couches Pliolite)
6. Reprise des encadrements de fenêtres
7. Nettoyage et remise en état du chantier

Surface traitée: 650 m²"""
                },
                {
                    "page": 2,
                    "content": """DÉTAIL DU DEVIS:

| Poste | Description | Quantité | Prix unitaire | Total HT |
|-------|-------------|----------|---------------|----------|
| 1 | Échafaudage | 650 m² | 8,50 € | 5,525 € |
| 2 | Nettoyage HP | 650 m² | 4,00 € | 2,600 € |
| 3 | Réparation fissures | Forfait | - | 2,000 € |
| 4 | Traitement anti-mousse | 650 m² | 2,50 € | 1,625 € |
| 5 | Peinture 2 couches | 650 m² | 15,00 € | 9,750 € |
| 6 | Encadrements | Forfait | - | 2,500 € |
| 7 | Nettoyage final | Forfait | - | 1,200 € |

TOTAL HT: 25,200 €
TVA 10%: 2,520 €
TOTAL TTC: 27,720 €

Option: Ravalement avec isolation thermique par l'extérieur (ITE)
Supplément: 22,000 € TTC

TOTAL AVEC ITE: 49,720 € TTC

Garantie: 10 ans sur l'étanchéité
Délai d'exécution: 5 semaines
Validité du devis: 90 jours

Fait à Nice, le 15 octobre 2024
[Signature]
Jean DUPUIS - Gérant RAVALEMENT CÔTE D'AZUR"""
                }
            ]
        }

    # =========================================================================
    # LE CLOS DES OLIVIERS - Documents
    # =========================================================================

    @staticmethod
    def _reglement_oliviers() -> Dict[str, Any]:
        return {
            "title": "Règlement de copropriété - Le Clos des Oliviers",
            "doc_type": "reglement_copropriete",
            "copropriete_id": 10,
            "copropriete_name": "Le Clos des Oliviers",
            "date": "1995-03-10",
            "chunks": [
                {
                    "page": 1,
                    "content": """RÈGLEMENT DE COPROPRIÉTÉ
LE CLOS DES OLIVIERS
128 Avenue du Prado - 13008 MARSEILLE

Établi le 10 mars 1995

TITRE I - DÉSIGNATION DE L'IMMEUBLE

Article 1 - Description générale
L'immeuble est situé au 128 Avenue du Prado, 13008 Marseille.
Il comprend 4 bâtiments (A, B, C et D) construits en 1995.
L'ensemble totalise 48 lots principaux:
- 44 appartements
- 4 locaux commerciaux au rez-de-chaussée

La copropriété dispose de:
- Un parking souterrain de 50 places
- Un local à vélos
- Un jardin privatif de 600 m²
- Une piscine collective"""
                },
                {
                    "page": 2,
                    "content": """TITRE II - DESTINATION DE L'IMMEUBLE

Article 5 - Usage des locaux
Les lots à usage d'habitation sont destinés exclusivement à l'habitation
bourgeoise. Toute activité professionnelle libérale peut être autorisée
par l'assemblée générale à la majorité de l'article 26.

Les locaux commerciaux (lots 1 à 4 du RDC) peuvent accueillir:
- Commerce de détail
- Activité de service
- Bureau professionnel

Sont interdits: Les activités bruyantes, polluantes ou dangereuses.

Article 6 - Animaux
Les animaux de compagnie sont tolérés dans les parties privatives,
sous réserve de ne pas troubler la tranquillité des voisins.
Les chiens doivent être tenus en laisse dans les parties communes.
Les animaux ne sont pas autorisés dans la piscine."""
                },
                {
                    "page": 3,
                    "content": """TITRE III - CHARGES

Article 12 - Répartition des charges
Les charges sont réparties selon les tantièmes:
- Charges générales: tantièmes généraux
- Charges de chauffage: au prorata des surfaces chauffées
- Charges d'ascenseur: par bâtiment, selon l'étage
- Charges de piscine: réparties entre tous les lots d'habitation

Article 13 - Chauffage collectif
La copropriété dispose d'un chauffage collectif au gaz.
La période de chauffe s'étend du 1er novembre au 31 mars.
Température de consigne: 19°C dans les logements

Article 14 - Compteurs individuels
Chaque lot dispose de compteurs individuels:
- Eau froide: relevé annuel
- Électricité: contrat individuel
- Chauffage: répartiteurs de frais"""
                }
            ]
        }

    @staticmethod
    def _pv_ag_oliviers_2024() -> Dict[str, Any]:
        return {
            "title": "PV AG du 20 septembre 2024 - Le Clos des Oliviers",
            "doc_type": "pv_ag",
            "copropriete_id": 10,
            "copropriete_name": "Le Clos des Oliviers",
            "date": "2024-09-20",
            "chunks": [
                {
                    "page": 1,
                    "content": """PROCÈS-VERBAL DE L'ASSEMBLÉE GÉNÉRALE ORDINAIRE
LE CLOS DES OLIVIERS
128 Avenue du Prado - 13008 MARSEILLE

Tenue le 20 septembre 2024 à 18h30
Salle de réunion - Local collectif de la copropriété

Présents et représentés: 3 copropriétaires sur 4
Tantièmes représentés: 8,200 sur 10,000 (82%)

Bureau de l'Assemblée:
- Président de séance: M. Jacques FAURE (Président du Conseil Syndical)
- Secrétaire: Mme Martine BLANC
- Scrutateurs: M. Philippe ROUSSEAU, M. Olivier GIRARD"""
                },
                {
                    "page": 2,
                    "content": """RÉSOLUTION N°1 - APPROBATION DES COMPTES 2023
Comptes présentés par le syndic:
- Total des charges: 128,500 €
- Solde de trésorerie: 15,300 €

Vote: ADOPTÉ à la majorité de l'article 24
Pour: 7,800 tantièmes

RÉSOLUTION N°2 - BUDGET PRÉVISIONNEL 2024-2025
Budget voté: 135,000 €
Hausse de 5% due à l'augmentation des coûts d'énergie.

Vote: ADOPTÉ à la majorité de l'article 24
Pour: 7,500 tantièmes

RÉSOLUTION N°3 - RÉNOVATION PISCINE
L'assemblée vote la rénovation du liner de la piscine collective.

Coût total: 25,000 € TTC
Calendrier: Travaux prévus pour avril 2025

Vote: ADOPTÉ à la majorité de l'article 25
Pour: 6,500 tantièmes"""
                },
                {
                    "page": 3,
                    "content": """RÉSOLUTION N°4 - AUDIT ÉNERGÉTIQUE
L'assemblée prend acte des résultats de l'audit énergétique:
- DPE actuel: Classe D
- DPE cible après travaux: Classe B
- Travaux recommandés: Isolation toiture, PAC, fenêtres

Calendrier proposé:
- 2025: Isolation toiture
- 2026: Remplacement chaudière par PAC
- 2027: Remplacement fenêtres parties communes

RÉSOLUTION N°5 - IMPAYÉS DE CHARGES
Le syndic fait état d'impayés pour un montant de 6,500 €.
Copropriétaires concernés: 3 lots
Actions engagées: Mises en demeure envoyées

L'assemblée autorise le syndic à engager des procédures
de recouvrement contentieux si nécessaire.

Vote: ADOPTÉ à la majorité de l'article 24
Pour: 8,000 tantièmes

RÉSOLUTION N°6 - RÉÉLECTION CONSEIL SYNDICAL
Membres réélus:
- M. Jacques FAURE (Président)
- M. Olivier GIRARD (Conseiller)
- Mme Sylvie BONNET (Conseillère)

Vote: ADOPTÉ"""
                }
            ]
        }

    @staticmethod
    def _contrat_entretien_oliviers() -> Dict[str, Any]:
        return {
            "title": "Contrat entretien chauffage - Le Clos des Oliviers",
            "doc_type": "contrat_entretien",
            "copropriete_id": 10,
            "copropriete_name": "Le Clos des Oliviers",
            "date": "2024-01-15",
            "chunks": [
                {
                    "page": 1,
                    "content": """CONTRAT D'ENTRETIEN DE CHAUDIÈRE COLLECTIVE
N° CE-2024-OLV-001

Entre:
CHALEUR SERVICES MARSEILLE
15 Rue de l'Industrie, 13012 MARSEILLE
SIRET: 456 789 123 00034

Et:
COPROPRIÉTÉ LE CLOS DES OLIVIERS
128 Avenue du Prado, 13008 MARSEILLE
Représentée par: GESTION IMMOBILIÈRE MARSEILLE (Syndic)

ARTICLE 1 - OBJET
Entretien annuel de la chaudière collective gaz de marque VIESSMANN
Type: Vitodens 200-W
Puissance: 200 kW
Année d'installation: 2015"""
                },
                {
                    "page": 2,
                    "content": """ARTICLE 2 - PRESTATIONS INCLUSES
2.1 Visite annuelle obligatoire:
- Nettoyage du brûleur
- Vérification des organes de sécurité
- Contrôle des émissions (CO, NOx)
- Réglage de la combustion
- Mesure du rendement

2.2 Interventions sur appel (délai 24h ouvrées):
- Diagnostic de panne
- Réparations courantes
- Pièces d'usure incluses (liste en annexe)

2.3 Astreinte hivernale (01/11 au 31/03):
- Disponibilité 7j/7
- Intervention sous 4h en cas d'urgence

ARTICLE 3 - TARIFICATION
Forfait annuel: 3,800 € HT (4,560 € TTC)
Pièces détachées hors forfait: selon devis
Main d'œuvre hors forfait: 70 € HT/heure

ARTICLE 4 - DURÉE
Contrat d'un an renouvelable par tacite reconduction.
Résiliation: préavis de 2 mois avant l'échéance.

Fait à Marseille, le 15 janvier 2024"""
                }
            ]
        }

    # =========================================================================
    # IMMEUBLE HAUSSMANN SAINT-GERMAIN - Documents
    # =========================================================================

    @staticmethod
    def _reglement_haussmann() -> Dict[str, Any]:
        return {
            "title": "Règlement de copropriété - Immeuble Haussmann Saint-Germain",
            "doc_type": "reglement_copropriete",
            "copropriete_id": 11,
            "copropriete_name": "Immeuble Haussmann Saint-Germain",
            "date": "1900-01-01",
            "chunks": [
                {
                    "page": 1,
                    "content": """RÈGLEMENT DE COPROPRIÉTÉ
IMMEUBLE HAUSSMANN SAINT-GERMAIN
67 Boulevard Saint-Germain - 75005 PARIS

Établi le 1er janvier 1900
Modifié le 15 mars 2020

TITRE I - DÉSIGNATION DE L'IMMEUBLE

Article 1 - Description générale
L'immeuble est situé au 67 Boulevard Saint-Germain, 75005 Paris.
Il s'agit d'un immeuble haussmannien construit en 1880.
L'ensemble totalise 12 lots principaux:
- 10 appartements
- 2 locaux commerciaux au rez-de-chaussée

La copropriété dispose de:
- Une loge de gardien (lot commun)
- Caves au sous-sol
- Coursive intérieure"""
                },
                {
                    "page": 2,
                    "content": """TITRE II - PARTIES COMMUNES ET PRIVATIVES

Article 2 - Parties communes générales
Sont des parties communes générales de l'immeuble:
- Le sol et le sous-sol
- Les fondations, les gros murs de façade haussmanniens
- La toiture en zinc
- Le hall d'entrée et l'escalier en pierre de taille
- La cour intérieure
- L'ascenseur (ajouté en 1970)
- Les canalisations principales

Article 3 - Caractère patrimonial
L'immeuble étant situé en secteur sauvegardé, toute modification
des façades ou des éléments architecturaux visibles depuis la rue
nécessite l'autorisation préalable de l'Architecte des Bâtiments de France."""
                },
                {
                    "page": 3,
                    "content": """TITRE III - ANIMAUX

Article 15 - Animaux de compagnie
Les animaux de compagnie sont tolérés dans les parties privatives.
Ils doivent être tenus en laisse ou transportés dans les parties communes.
Tout propriétaire est responsable des nuisances causées par son animal.

TITRE IV - TRAVAUX

Article 20 - Travaux sur parties communes
Les travaux sur parties communes requièrent:
- Article 24: Entretien courant
- Article 25: Travaux d'amélioration
- Article 26: Modification de l'aspect extérieur ou des parties communes

Article 21 - Contraintes patrimoniales
Toute intervention sur la façade ou la toiture doit respecter:
- Le cahier des charges du secteur sauvegardé
- Les prescriptions de l'ABF
- Les techniques et matériaux traditionnels haussmanniens"""
                }
            ]
        }

    @staticmethod
    def _pv_ag_haussmann_2024() -> Dict[str, Any]:
        return {
            "title": "PV AG du 10 mai 2024 - Immeuble Haussmann Saint-Germain",
            "doc_type": "pv_ag",
            "copropriete_id": 11,
            "copropriete_name": "Immeuble Haussmann Saint-Germain",
            "date": "2024-05-10",
            "chunks": [
                {
                    "page": 1,
                    "content": """PROCÈS-VERBAL DE L'ASSEMBLÉE GÉNÉRALE ORDINAIRE
IMMEUBLE HAUSSMANN SAINT-GERMAIN
67 Boulevard Saint-Germain - 75005 PARIS

Tenue le 10 mai 2024 à 19h00
Étude de Maître DUVAL, Notaire

Présents et représentés: 3 copropriétaires sur 3
Tantièmes représentés: 10,000 sur 10,000 (100%)

Bureau de l'Assemblée:
- Président de séance: Mme Catherine DUBOIS
- Secrétaire: M. François LAMBERT
- Scrutateur: M. Robert MARTIN"""
                },
                {
                    "page": 2,
                    "content": """RÉSOLUTION N°1 - APPROBATION DES COMPTES 2023
Comptes présentés par le syndic:
- Total des charges: 48,500 €
- Solde de trésorerie: 8,200 €

Vote: ADOPTÉ à l'unanimité

RÉSOLUTION N°2 - BUDGET PRÉVISIONNEL 2024-2025
Budget voté: 52,000 €
Répartition:
- Entretien courant: 20,000 €
- Assurances: 6,000 €
- Honoraires syndic: 12,000 €
- Eau et énergie: 8,000 €
- Gardien: 6,000 €

Vote: ADOPTÉ à l'unanimité

RÉSOLUTION N°3 - RAVALEMENT FAÇADE
Suite à l'injonction de la Ville de Paris, l'immeuble doit
procéder au ravalement de sa façade haussmannienne.

Devis retenu: ENTREPRISE PATRIMOINE PARIS - 85,000 € TTC
(entreprise agréée monuments historiques)

Calendrier: Travaux prévus printemps 2025
Financement: Emprunt collectif sur 5 ans

Vote: ADOPTÉ à la majorité de l'article 25 (unanimité)"""
                },
                {
                    "page": 3,
                    "content": """RÉSOLUTION N°4 - RÉNOVATION ASCENSEUR
L'assemblée vote la modernisation de l'ascenseur datant de 1970.

Travaux prévus:
- Remplacement de la cabine
- Mise aux normes de sécurité
- Nouveau système d'appel

Coût total: 45,000 € TTC
Subvention ANAH obtenue: 10,000 €
Reste à charge: 35,000 €

Vote: ADOPTÉ à la majorité de l'article 25 (unanimité)

RÉSOLUTION N°5 - RENOUVELLEMENT CONTRAT GARDIEN
L'assemblée vote le maintien du poste de gardien.
Coût annuel: 24,000 € (charges comprises)

Vote: ADOPTÉ à la majorité de l'article 25 (unanimité)

RÉSOLUTION N°6 - ÉLECTION CONSEIL SYNDICAL
Membres élus:
- Mme Catherine DUBOIS (Présidente)
- M. François LAMBERT
- M. Robert MARTIN

La séance est levée à 21h00.

Fait à Paris, le 10 mai 2024"""
                }
            ]
        }


# ============================================================================
# RAG Document Indexer Helper
# ============================================================================

class RAGDocumentIndexer:
    """
    Helper class to prepare documents for Qdrant indexing.
    """

    @staticmethod
    def prepare_for_indexing(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare documents for Qdrant indexing.
        Flattens chunks and adds necessary metadata.

        Returns:
            List of documents ready for embedding and indexing
        """
        indexed_docs = []

        for doc in documents:
            doc_id = 0
            for chunk in doc.get("chunks", []):
                doc_id += 1
                indexed_docs.append({
                    "id": f"{doc['doc_type']}_{doc['copropriete_id']}_{doc_id}",
                    "content": chunk["content"],
                    "metadata": {
                        "title": doc["title"],
                        "doc_type": doc["doc_type"],
                        "copropriete_id": doc["copropriete_id"],
                        "copropriete_name": doc["copropriete_name"],
                        "date": doc["date"],
                        "page": chunk.get("page", 1),
                        "source": "rag_fixture"
                    }
                })

        return indexed_docs

    @staticmethod
    def get_expected_answers() -> Dict[str, Dict[str, Any]]:
        """
        Returns expected answers for RAG-based test validation.
        """
        return {
            "reglement_travaux_arc_en_ciel": {
                "query": "Que dit le règlement sur les travaux privatifs à Arc-en-Ciel ?",
                "expected_keywords": [
                    "30 jours", "autorisation", "AG", "façade", "fenêtres"
                ],
                "expected_doc_type": "reglement_copropriete"
            },
            "budget_ag_arc_en_ciel_2024": {
                "query": "Quel est le budget voté à l'AG 2024 de Arc-en-Ciel ?",
                "expected_keywords": ["95,000", "budget", "2024"],
                "expected_doc_type": "pv_ag"
            },
            "ravalement_arc_en_ciel": {
                "query": "Qu'a décidé l'AG concernant le ravalement à Arc-en-Ciel ?",
                "expected_keywords": [
                    "RAVALEMENT", "38,000", "façade", "bâtiment A"
                ],
                "expected_doc_type": "pv_ag"
            },
            "honoraires_syndic_arc_en_ciel": {
                "query": "Quels sont les honoraires du syndic de Arc-en-Ciel ?",
                "expected_keywords": ["14,500", "forfait", "SYNDIC CÔTE D'AZUR"],
                "expected_doc_type": "contrat_syndic"
            },
            "piscine_oliviers": {
                "query": "Qu'a voté l'AG des Oliviers concernant la piscine ?",
                "expected_keywords": [
                    "piscine", "rénovation", "liner", "25,000"
                ],
                "expected_doc_type": "pv_ag"
            },
            "dpe_oliviers": {
                "query": "Quel est le DPE du Clos des Oliviers ?",
                "expected_keywords": ["Classe D", "Classe B", "audit"],
                "expected_doc_type": "pv_ag"
            },
            "ravalement_haussmann": {
                "query": "Qu'en est-il du ravalement de l'immeuble Haussmann ?",
                "expected_keywords": ["85,000", "façade", "haussmannienne", "PATRIMOINE PARIS"],
                "expected_doc_type": "pv_ag"
            },
            "animaux_copropriete": {
                "query": "Que disent les règlements sur les animaux ?",
                "expected_keywords": ["animaux", "compagnie", "laisse", "parties communes"],
                "expected_doc_type": "reglement_copropriete"
            }
        }
