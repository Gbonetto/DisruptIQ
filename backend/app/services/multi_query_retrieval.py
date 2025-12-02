"""
Multi-Query Retrieval Service - Génération de reformulations pour meilleur recall
Phase RAG World-Class - DisruptIQ SMA

Ce module génère 3-5 reformulations de la requête utilisateur pour:
- Capturer différentes façons de formuler la même question
- Utiliser des synonymes (prix ↔ tarif ↔ coût ↔ montant)
- Varier la structure (question → affirmation → mots-clés)

Exemple:
  Input: "prix maintenance ascenseur"
  Output: [
    "tarif annuel contrat ascenseur",
    "coût maintenance ascenseur TTC",
    "redevance ascenseur forfaitaire",
    "montant contrat ascenseur euros"
  ]

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import re
import structlog
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class MultiQueryResult:
    """Résultat de la génération multi-query"""
    original_query: str
    reformulations: List[str]
    all_queries: List[str]  # Original + reformulations
    strategy_used: str


class MultiQueryRetrieval:
    """
    Service de génération de reformulations de requêtes.

    Utilise des règles linguistiques et synonymes pour générer
    des variantes de la requête sans appel LLM (rapide et fiable).
    """

    # Synonymes pour les termes courants en syndic
    SYNONYMS = {
        # Montants
        "prix": ["tarif", "coût", "montant", "valeur"],
        "montant": ["prix", "somme", "total", "coût"],
        "coût": ["prix", "tarif", "montant", "dépense"],
        "tarif": ["prix", "coût", "redevance", "forfait"],
        "budget": ["prévisionnel", "montant", "enveloppe"],
        "charges": ["frais", "dépenses", "cotisations"],
        "facture": ["note", "facture", "relevé"],
        "devis": ["estimation", "proposition", "offre"],

        # Documents
        "contrat": ["convention", "accord", "engagement"],
        "règlement": ["statuts", "charte", "règles"],
        "pv": ["procès-verbal", "compte-rendu", "rapport"],
        "rapport": ["compte-rendu", "bilan", "synthèse"],

        # Actions
        "maintenance": ["entretien", "réparation", "service"],
        "travaux": ["rénovation", "réparation", "intervention"],
        "intervention": ["opération", "travaux", "action"],
        "vote": ["décision", "délibération", "résolution"],

        # Entités
        "copropriétaire": ["propriétaire", "résident", "occupant"],
        "prestataire": ["fournisseur", "entreprise", "artisan"],
        "syndic": ["gestionnaire", "administrateur"],

        # Temporel
        "annuel": ["par an", "année", "annuellement"],
        "mensuel": ["par mois", "mois", "mensuellement"],
        "trimestriel": ["par trimestre", "trimestre"],

        # Légal
        "assemblée générale": ["ag", "réunion générale"],
        "conseil syndical": ["cs", "conseil"],
        "résolution": ["décision", "vote", "délibération"],
    }

    # Templates de reformulation
    TEMPLATES = {
        "amount": [
            "{entity} {amount_word} {context}",
            "quel est le {amount_word} de {entity}",
            "{amount_word} {entity} ttc ht",
            "combien coûte {entity}",
        ],
        "document": [
            "{doc_type} {entity} {year}",
            "contenu {doc_type} {entity}",
            "que dit le {doc_type} sur {topic}",
        ],
        "person": [
            "qui est {person}",
            "{person} {role} {entity}",
            "informations {person}",
        ],
        "general": [
            "{keywords}",
            "{entity} {action}",
            "{context} {entity}",
        ]
    }

    def __init__(self, max_reformulations: int = 4):
        self.max_reformulations = max_reformulations

    def generate_reformulations(
        self,
        query: str,
        is_amount_query: bool = False,
        is_table_query: bool = False,
        is_legal_query: bool = False
    ) -> MultiQueryResult:
        """
        Génère des reformulations de la requête.

        Args:
            query: Requête originale
            is_amount_query: Flag du QueryAnalyzer
            is_table_query: Flag du QueryAnalyzer
            is_legal_query: Flag du QueryAnalyzer

        Returns:
            MultiQueryResult avec toutes les variantes
        """
        query_lower = query.lower()
        reformulations = []
        strategy = "general"

        # Stratégie selon le type de requête
        if is_amount_query:
            reformulations = self._generate_amount_reformulations(query_lower)
            strategy = "amount_focused"

        elif is_table_query:
            reformulations = self._generate_table_reformulations(query_lower)
            strategy = "table_focused"

        elif is_legal_query:
            reformulations = self._generate_legal_reformulations(query_lower)
            strategy = "legal_focused"

        else:
            reformulations = self._generate_general_reformulations(query_lower)
            strategy = "general"

        # Toujours ajouter une version keywords-only
        keywords = self._extract_keywords(query_lower)
        if keywords and keywords not in reformulations:
            reformulations.append(keywords)

        # Limiter et dédupliquer
        reformulations = self._deduplicate(reformulations)[:self.max_reformulations]

        # Construire la liste complète (original + reformulations)
        all_queries = [query] + reformulations

        result = MultiQueryResult(
            original_query=query,
            reformulations=reformulations,
            all_queries=all_queries,
            strategy_used=strategy
        )

        logger.info("multi_query_generated",
                   original=query[:40],
                   reformulations_count=len(reformulations),
                   strategy=strategy)

        return result

    def _generate_amount_reformulations(self, query: str) -> List[str]:
        """Génère des reformulations axées sur les montants"""
        reformulations = []

        # Trouver les termes de montant dans la requête
        amount_terms = ["prix", "montant", "coût", "tarif", "total", "budget", "charges"]
        found_term = None
        for term in amount_terms:
            if term in query:
                found_term = term
                break

        if found_term:
            # Remplacer par les synonymes
            for synonym in self.SYNONYMS.get(found_term, [])[:3]:
                variant = query.replace(found_term, synonym)
                reformulations.append(variant)

        # Ajouter variantes avec TTC/HT
        if "ttc" not in query and "ht" not in query:
            reformulations.append(query + " ttc")
            reformulations.append(query + " ht euros")

        # Ajouter "quel est le montant"
        if not query.startswith("quel"):
            reformulations.append(f"quel est le montant {query}")

        # Version avec "combien"
        reformulations.append(f"combien {query}")

        return reformulations

    def _generate_table_reformulations(self, query: str) -> List[str]:
        """Génère des reformulations pour requêtes tableau"""
        reformulations = []

        # Variantes de "tableau"
        table_variants = ["liste", "récapitulatif", "synthèse", "détail"]
        for variant in table_variants:
            if variant not in query:
                reformulations.append(query.replace("tableau", variant) if "tableau" in query else f"{variant} {query}")

        # Ajouter "tous les" ou "chaque"
        reformulations.append(f"tous les {query}")
        reformulations.append(f"détail par {query}")

        return reformulations

    def _generate_legal_reformulations(self, query: str) -> List[str]:
        """Génère des reformulations pour requêtes légales"""
        reformulations = []

        # Synonymes légaux
        legal_mappings = {
            "ag": ["assemblée générale", "réunion"],
            "assemblée générale": ["ag", "réunion générale"],
            "pv": ["procès-verbal", "compte-rendu"],
            "procès-verbal": ["pv", "compte-rendu"],
            "résolution": ["vote", "décision", "délibération"],
            "vote": ["résolution", "adoption", "décision"],
        }

        for term, synonyms in legal_mappings.items():
            if term in query:
                for syn in synonyms[:2]:
                    reformulations.append(query.replace(term, syn))

        # Ajouter contexte copropriété
        if "copropriété" not in query and "résidence" not in query:
            reformulations.append(f"{query} copropriété")

        return reformulations

    def _generate_general_reformulations(self, query: str) -> List[str]:
        """Génère des reformulations générales"""
        reformulations = []

        # Remplacer chaque mot par ses synonymes
        words = query.split()
        for i, word in enumerate(words):
            if word in self.SYNONYMS:
                for syn in self.SYNONYMS[word][:2]:
                    new_words = words.copy()
                    new_words[i] = syn
                    reformulations.append(" ".join(new_words))

        # Version question
        if not query.startswith(("quel", "qui", "où", "quand", "comment", "combien")):
            reformulations.append(f"quel est {query}")

        return reformulations

    def _extract_keywords(self, query: str) -> str:
        """Extrait les mots-clés principaux"""
        # Mots à ignorer (stop words)
        stop_words = {
            "le", "la", "les", "un", "une", "des", "du", "de", "à", "au", "aux",
            "et", "ou", "est", "sont", "a", "ont", "pour", "par", "sur", "dans",
            "en", "que", "qui", "quoi", "quel", "quelle", "quels", "quelles",
            "ce", "cette", "ces", "mon", "ma", "mes", "son", "sa", "ses",
            "notre", "nos", "votre", "vos", "leur", "leurs",
            "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
            "me", "te", "se", "lui", "y", "dont", "où",
            "ne", "pas", "plus", "moins", "très", "bien", "mal",
            "être", "avoir", "faire", "dire", "aller", "voir", "vouloir", "pouvoir",
        }

        words = query.split()
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]

        return " ".join(keywords)

    def _deduplicate(self, items: List[str]) -> List[str]:
        """Déduplique en préservant l'ordre"""
        seen = set()
        result = []
        for item in items:
            item_normalized = item.lower().strip()
            if item_normalized and item_normalized not in seen:
                seen.add(item_normalized)
                result.append(item)
        return result


# Singleton
_multi_query_service: Optional[MultiQueryRetrieval] = None


def get_multi_query_service() -> MultiQueryRetrieval:
    """Retourne l'instance singleton du Multi-Query Service"""
    global _multi_query_service
    if _multi_query_service is None:
        _multi_query_service = MultiQueryRetrieval()
    return _multi_query_service
