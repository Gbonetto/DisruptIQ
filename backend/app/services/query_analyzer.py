"""
Query Analyzer - Analyse légère des requêtes pour routage intelligent
Phase RAG World-Class - DisruptIQ SMA

Ce module analyse les requêtes utilisateur et retourne 4 flags:
- is_table_query: Requête demandant un tableau ou liste structurée
- is_amount_query: Requête sur des montants précis (€, euros, prix)
- is_legal_query: Requête sur des procédures légales (AG, vote, règlement)
- needs_hybrid: Requête nécessitant RAG + SQL

Ces flags activent/désactivent les services appropriés:
- Multi-Query → activé si is_amount_query (reformulations pour montants)
- Table Service → activé si is_table_query
- SQL-RAG Bridge → activé si needs_hybrid

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import re
import structlog
from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

logger = structlog.get_logger()


class QueryComplexity(Enum):
    """Niveau de complexité de la requête"""
    SIMPLE = "simple"           # Recherche directe
    MODERATE = "moderate"       # Reformulations utiles
    COMPLEX = "complex"         # Multi-source nécessaire


@dataclass
class QueryAnalysis:
    """
    Résultat de l'analyse de requête - Version enrichie avec scores

    Phase Core-First: Ajout de scores de confiance pour routing intelligent
    et détection de requêtes "pures" (Legal/Web sans entités métier)
    """
    original_query: str

    # 4 flags principaux (legacy, conservés pour compatibilité)
    is_table_query: bool = False
    is_amount_query: bool = False
    is_legal_query: bool = False
    needs_hybrid: bool = False

    # NOUVEAUX: Scores de confiance (0.0 à 1.0)
    legal_confidence: float = 0.0      # Probabilité que la requête nécessite Legal
    web_confidence: float = 0.0        # Probabilité que la requête nécessite Web
    core_confidence: float = 1.0       # Probabilité que Core (SQL+RAG) suffise

    # NOUVEAUX: Détection de requêtes "pures" (sans entités métier)
    pure_legal_query: bool = False     # Requête purement légale (article X, loi Y)
    pure_web_query: bool = False       # Requête purement web (prix 2025, actualités)
    has_business_entities: bool = False  # Contient copro/lot/personne/etc.

    # Métadonnées supplémentaires
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    detected_entities: List[str] = None
    suggested_filters: dict = None
    confidence: float = 0.0

    def __post_init__(self):
        if self.detected_entities is None:
            self.detected_entities = []
        if self.suggested_filters is None:
            self.suggested_filters = {}

    @property
    def should_shortcircuit_legal(self) -> bool:
        """Short-circuit vers Legal si requête purement légale avec haute confiance"""
        return self.pure_legal_query and self.legal_confidence >= 0.85 and not self.has_business_entities

    @property
    def should_shortcircuit_web(self) -> bool:
        """Short-circuit vers Web si requête purement web avec haute confiance"""
        return self.pure_web_query and self.web_confidence >= 0.85 and not self.has_business_entities

    @property
    def should_suggest_legal(self) -> bool:
        """Suggérer Legal en follow-up si confiance modérée"""
        return self.legal_confidence >= 0.5 and not self.should_shortcircuit_legal

    @property
    def should_suggest_web(self) -> bool:
        """Suggérer Web en follow-up si confiance modérée"""
        return self.web_confidence >= 0.5 and not self.should_shortcircuit_web

    @property
    def needs_multi_query(self) -> bool:
        """Active Multi-Query si montants ou complexité moderate+"""
        return self.is_amount_query or self.complexity != QueryComplexity.SIMPLE

    @property
    def needs_table_service(self) -> bool:
        """Active Table Service si tableau demandé"""
        return self.is_table_query

    @property
    def needs_sql_rag_bridge(self) -> bool:
        """Active SQL-RAG Bridge si hybride nécessaire"""
        return self.needs_hybrid

    @property
    def needs_extended_retrieval(self) -> bool:
        """Active retrieval étendu (30 chunks) si complexe"""
        return self.is_amount_query or self.is_table_query or self.needs_hybrid


class QueryAnalyzer:
    """
    Analyseur de requêtes léger et rapide.

    Détecte les caractéristiques de la requête pour activer
    les bons services sans surcharger le système.
    """

    # Patterns pour détection de tableaux
    TABLE_PATTERNS = [
        r"\btableau\b",
        r"\bliste\b.*\b(tous|toutes|chaque)\b",
        r"\brécapitulatif\b",
        r"\bsynthèse\b.*\b(de|des)\b",
        r"\bpar\s+(lot|copropriétaire|résolution)\b",
        r"\bdétail\b.*\b(par|des)\b",
        r"\bventilation\b",
        r"\brépartition\b",
        r"\bpour chaque\b",
        r"\bcolonne\b",
        r"\bligne\b.*\bde\b",
    ]

    # Patterns pour montants
    AMOUNT_PATTERNS = [
        r"\b\d+[\s,.]?\d*\s*€",
        r"\beuros?\b",
        r"\bmontant\b",
        r"\bprix\b",
        r"\btarif\b",
        r"\bcoût\b",
        r"\bfacture\b",
        r"\bdevis\b",
        r"\bcharges?\b",
        r"\bbudget\b",
        r"\btotal\s*(ttc|ht)?\b",
        r"\bredevance\b",
        r"\bforfait\b",
        r"\bestimation\b",
        r"\bcombien\b",
        r"\bquel\s+(est|était)\s+le\s+(prix|montant|coût)\b",
        # Agrégats métier copropriété
        r"\b(total|somme|récapitulatif|cumul)\s+(des|de)\s+(charges?|paiements?|appels?|factures?|montants?)",
    ]

    # Patterns légaux
    LEGAL_PATTERNS = [
        r"\bassemblée\s+générale\b",
        r"\bag\b",
        r"\bprocès[- ]verbal\b",
        r"\bpv\b",
        r"\brésolution\b",
        r"\bvote\b",
        r"\btantièmes?\b",
        r"\bmajorité\b",
        r"\brèglement\b.*\bcopropriété\b",
        r"\barticle\s+\d+\b",
        r"\badopt[ée]+\b",
        r"\brejet[ée]+\b",
        r"\bsyndic\b",
        r"\bconseil\s+syndical\b",
    ]

    # NOUVEAUX: Patterns pour détection Web (prix marché, actualités)
    WEB_PATTERNS = [
        r"\bprix\s+(moyen|actuel|du\s+marché)\b",
        r"\btarif\s+(moyen|actuel|standard)\b",
        r"\ben\s+202[4-9]\b",  # Années récentes
        r"\bactualité[s]?\b",
        r"\bévolution[s]?\s+récente[s]?\b",
        r"\bdernier[s]?\s+(chiffre|donnée|statistique)\b",
        r"\btendance[s]?\s+(actuelle|du\s+marché)\b",
        r"\bcompar(er|aison)\s+.*\s+marché\b",
        r"\bbenchmark\b",
        r"\baide[s]?\s+(de\s+l'état|gouvernement|maprimerénov)\b",
        r"\bsubvention[s]?\s+(actuelle|disponible|202)\b",
        r"\brecherche[r]?\s+(sur\s+)?(internet|le\s+web)\b",
    ]

    # NOUVEAUX: Patterns pour Legal "pur" (sans contexte métier)
    PURE_LEGAL_PATTERNS = [
        r"\bque\s+dit\s+la\s+loi\b",
        r"\bloi\s+du\s+\d+\s+\w+\s+\d{4}\b",  # "loi du 10 juillet 1965"
        r"\bcode\s+civil\b",
        r"\bjurisprudence\b",
        r"\blégifrance\b",
        r"\barticle\s+\d+\s+(de\s+la\s+loi|du\s+code)\b",
        r"\bquelle\s+majorité\s+(pour|requise|nécessaire)\b",
        r"\bobligations?\s+légales?\b",
        r"\bprocédure\s+(légale|juridique)\b",
    ]

    # Patterns hybrides (nécessitent SQL + RAG)
    # Agile: patterns bidirectionnels pour capturer les deux ordres de mots
    HYBRID_PATTERNS = [
        # Copropriétaire + charges (dans les deux sens)
        r"\bcopropriétaire\b.*\b(charges?|doit|dette|paiement)\b",
        r"\b(charges?|doit|dette|paiement)\b.*\bcopropriétaire\b",
        # Lot + charges/montant (dans les deux sens)
        r"\blot\b.*\b(montant|charges?)\b",
        r"\b(montant|charges?)\b.*\blot\b",
        # Copropriétaire + lot ensemble (requiert données SQL + contexte)
        r"\bcopropriétaire\b.*\blot\b",
        r"\blot\b.*\bcopropriétaire\b",
        # Professionnels et prestataires
        r"\bprofessionnel\b.*\b(intervention|travaux|facture)\b",
        r"\bprestataire\b.*\b(a\s+fait|réalisé|effectué)\b",
        r"\bqui\s+(doit|a\s+payé|est\s+en\s+retard)\b",
        r"\bdétail\b.*\bcopropriétaire\b",
        r"\bhistorique\b.*\b(paiement|intervention)\b",
        # Liste avec qualificatifs
        r"\bliste\b.*\b(copropriétaires?|lots?|prestataires?)\b.*\b(avec|et)\b",
    ]

    # Entités à détecter
    ENTITY_PATTERNS = {
        "copropriete": r"(?:copropriété|résidence|immeuble)\s+(?:de\s+)?[«\"']?([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*)[»\"']?",
        "lot": r"\blot\s+([A-Z]?\d+)\b",
        "date": r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})\b",
        "montant": r"(\d+[\s,.]?\d*(?:\s*€|\s*euros?))",
        "personne": r"(?:M\.|Mme|Monsieur|Madame)\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)?)",
    }

    def __init__(self):
        # Compiler les patterns pour performance
        self._table_re = [re.compile(p, re.IGNORECASE) for p in self.TABLE_PATTERNS]
        self._amount_re = [re.compile(p, re.IGNORECASE) for p in self.AMOUNT_PATTERNS]
        self._legal_re = [re.compile(p, re.IGNORECASE) for p in self.LEGAL_PATTERNS]
        self._hybrid_re = [re.compile(p, re.IGNORECASE) for p in self.HYBRID_PATTERNS]
        self._entity_re = {k: re.compile(v, re.IGNORECASE) for k, v in self.ENTITY_PATTERNS.items()}
        # NOUVEAUX patterns
        self._web_re = [re.compile(p, re.IGNORECASE) for p in self.WEB_PATTERNS]
        self._pure_legal_re = [re.compile(p, re.IGNORECASE) for p in self.PURE_LEGAL_PATTERNS]

    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyse une requête et retourne les flags + scores de confiance.

        Phase Core-First: Cette analyse détermine si la requête doit:
        - Passer par le Core (SQL+RAG) - par défaut
        - Short-circuit vers Legal/Web (rare, haute confiance)
        - Suggérer Legal/Web en follow-up (confiance modérée)

        Args:
            query: Requête utilisateur

        Returns:
            QueryAnalysis avec flags, scores et détection pure_legal/pure_web
        """
        if not query or not query.strip():
            return QueryAnalysis(original_query=query, confidence=0.0)

        query_lower = query.lower()

        # Détection des 4 flags legacy
        is_table = self._detect_table_query(query_lower)
        is_amount = self._detect_amount_query(query_lower)
        is_legal = self._detect_legal_query(query_lower)
        needs_hybrid = self._detect_hybrid_need(query_lower)

        # Extraction des entités
        entities = self._extract_entities(query)

        # NOUVEAU: Détection entités métier (copro, lot, personne)
        has_business_entities = any(
            e.startswith(("copropriete:", "lot:", "personne:"))
            for e in entities
        )

        # NOUVEAU: Calcul des scores de confiance
        legal_confidence, pure_legal = self._calculate_legal_score(query_lower, has_business_entities)
        web_confidence, pure_web = self._calculate_web_score(query_lower, has_business_entities)

        # Core confidence = inverse des autres (si pas legal ni web, c'est Core)
        core_confidence = 1.0 - max(legal_confidence * 0.5, web_confidence * 0.5)

        # Déterminer la complexité
        complexity = self._determine_complexity(
            is_table, is_amount, is_legal, needs_hybrid, len(entities)
        )

        # Suggérer des filtres basés sur les entités
        filters = self._suggest_filters(entities)

        # Calculer la confiance globale (legacy)
        confidence = self._calculate_confidence(
            is_table, is_amount, is_legal, needs_hybrid
        )

        result = QueryAnalysis(
            original_query=query,
            # Legacy flags
            is_table_query=is_table,
            is_amount_query=is_amount,
            is_legal_query=is_legal,
            needs_hybrid=needs_hybrid,
            # NOUVEAUX scores
            legal_confidence=legal_confidence,
            web_confidence=web_confidence,
            core_confidence=core_confidence,
            pure_legal_query=pure_legal,
            pure_web_query=pure_web,
            has_business_entities=has_business_entities,
            # Metadata
            complexity=complexity,
            detected_entities=entities,
            suggested_filters=filters,
            confidence=confidence
        )

        logger.info("query_analyzed",
                   query=query[:50],
                   is_table=is_table,
                   is_amount=is_amount,
                   is_legal=is_legal,
                   needs_hybrid=needs_hybrid,
                   legal_conf=f"{legal_confidence:.0%}",
                   web_conf=f"{web_confidence:.0%}",
                   pure_legal=pure_legal,
                   pure_web=pure_web,
                   has_biz_entities=has_business_entities,
                   complexity=complexity.value,
                   entities_count=len(entities))

        return result

    def _detect_table_query(self, query: str) -> bool:
        """Détecte si la requête demande un tableau"""
        return any(pattern.search(query) for pattern in self._table_re)

    def _detect_amount_query(self, query: str) -> bool:
        """Détecte si la requête concerne des montants"""
        # Au moins 2 patterns pour être sûr (évite faux positifs)
        matches = sum(1 for pattern in self._amount_re if pattern.search(query))
        return matches >= 1

    def _detect_legal_query(self, query: str) -> bool:
        """Détecte si la requête concerne des procédures légales"""
        return any(pattern.search(query) for pattern in self._legal_re)

    def _detect_hybrid_need(self, query: str) -> bool:
        """Détecte si la requête nécessite RAG + SQL"""
        # Hybrid si pattern explicite OU si mention d'entité SQL + contexte doc
        explicit_hybrid = any(pattern.search(query) for pattern in self._hybrid_re)

        # Ou si on demande des infos sur une personne/lot avec des documents
        has_sql_entity = bool(
            self._entity_re["lot"].search(query) or
            self._entity_re["personne"].search(query)
        )
        has_doc_context = any(word in query for word in [
            "contrat", "facture", "devis", "document", "pv", "rapport"
        ])

        return explicit_hybrid or (has_sql_entity and has_doc_context)

    def _extract_entities(self, query: str) -> List[str]:
        """Extrait les entités de la requête"""
        entities = []

        for entity_type, pattern in self._entity_re.items():
            matches = pattern.findall(query)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match and len(match) > 1:
                    entities.append(f"{entity_type}:{match}")

        return entities

    def _determine_complexity(
        self,
        is_table: bool,
        is_amount: bool,
        is_legal: bool,
        needs_hybrid: bool,
        entity_count: int
    ) -> QueryComplexity:
        """Détermine la complexité de la requête"""
        score = 0

        if is_table:
            score += 2
        if is_amount:
            score += 1
        if is_legal:
            score += 1
        if needs_hybrid:
            score += 2
        if entity_count > 2:
            score += 1

        if score >= 4:
            return QueryComplexity.COMPLEX
        elif score >= 2:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE

    def _suggest_filters(self, entities: List[str]) -> dict:
        """Suggère des filtres basés sur les entités détectées"""
        filters = {}

        for entity in entities:
            if ":" in entity:
                entity_type, value = entity.split(":", 1)

                if entity_type == "copropriete":
                    filters["copropriete_name"] = value
                elif entity_type == "lot":
                    filters["lot_number"] = value
                elif entity_type == "date":
                    filters["date_context"] = value
                elif entity_type == "personne":
                    filters["person_name"] = value

        return filters

    def _calculate_confidence(
        self,
        is_table: bool,
        is_amount: bool,
        is_legal: bool,
        needs_hybrid: bool
    ) -> float:
        """Calcule la confiance de l'analyse"""
        # Si aucun flag détecté, confiance basse
        flags_detected = sum([is_table, is_amount, is_legal, needs_hybrid])

        if flags_detected == 0:
            return 0.5  # Requête simple standard
        elif flags_detected == 1:
            return 0.8
        elif flags_detected >= 2:
            return 0.9
        else:
            return 0.7

    def _calculate_legal_score(self, query: str, has_business_entities: bool) -> Tuple[float, bool]:
        """
        Calcule le score de confiance Legal et détecte si requête purement légale.

        Returns:
            (legal_confidence, pure_legal_query)
        """
        # Compter les patterns legal matchés
        legal_pattern_count = sum(1 for p in self._legal_re if p.search(query))
        pure_legal_count = sum(1 for p in self._pure_legal_re if p.search(query))

        # Score basé sur le nombre de patterns
        if pure_legal_count >= 2:
            score = 0.95
        elif pure_legal_count >= 1:
            score = 0.85
        elif legal_pattern_count >= 2:
            score = 0.7
        elif legal_pattern_count >= 1:
            score = 0.5
        else:
            score = 0.0

        # Pure legal = patterns legal forts ET pas d'entités métier
        pure_legal = pure_legal_count >= 1 and not has_business_entities

        return score, pure_legal

    def _calculate_web_score(self, query: str, has_business_entities: bool) -> Tuple[float, bool]:
        """
        Calcule le score de confiance Web et détecte si requête purement web.

        Returns:
            (web_confidence, pure_web_query)
        """
        # Compter les patterns web matchés
        web_pattern_count = sum(1 for p in self._web_re if p.search(query))

        # Score basé sur le nombre de patterns
        if web_pattern_count >= 2:
            score = 0.9
        elif web_pattern_count >= 1:
            score = 0.7
        else:
            score = 0.0

        # Pure web = patterns web forts ET pas d'entités métier
        pure_web = web_pattern_count >= 1 and not has_business_entities

        return score, pure_web


# Singleton
_query_analyzer: Optional[QueryAnalyzer] = None


def get_query_analyzer() -> QueryAnalyzer:
    """Retourne l'instance singleton du Query Analyzer"""
    global _query_analyzer
    if _query_analyzer is None:
        _query_analyzer = QueryAnalyzer()
    return _query_analyzer
