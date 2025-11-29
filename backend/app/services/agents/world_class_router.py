"""
World Class Source Router - Perplexity-Style Multi-Source RAG

Architecture inspiree de:
- Perplexity AI: "Search first, filter later"
- Cohere: Cross-encoder reranking
- OpenAI: Parallel tool execution

Principes:
1. ALWAYS RETRIEVE - Ne jamais deviner, toujours chercher
2. PARALLEL EXECUTION - Toutes sources en meme temps
3. SMART RERANK - Filtrer apres, pas avant
4. CITE EVERYTHING - Tracabilite totale
"""

import asyncio
import structlog
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = structlog.get_logger()


class SourceType(Enum):
    """Types de sources disponibles."""
    SQL = "sql"
    RAG = "rag"
    WEB = "web"
    LEGAL = "legifrance"  # Match DataSource.LEGIFRANCE for consistency


class QueryComplexity(Enum):
    """Niveau de complexité de la requête - détermine le pipeline."""
    SIMPLE_SQL = "simple_sql"      # SQL direct → template response (no LLM)
    SIMPLE_RAG = "simple_rag"      # RAG direct → light LLM
    SIMPLE_WEB = "simple_web"      # Web direct → light LLM
    SIMPLE_LEGAL = "simple_legal"  # Legal direct → Légifrance API + synthesis
    HYBRID = "hybrid"              # Multi-source → full pipeline + rerank
    COMPLEX = "complex"            # Ambiguous → full pipeline + heavy LLM


@dataclass
class RetrievedDocument:
    """Document recupere depuis une source."""
    content: str
    source: SourceType
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    citation_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source.value,
            "score": self.score,
            "metadata": self.metadata,
            "citation_id": self.citation_id
        }


@dataclass
class RouterResult:
    """Resultat du routage et retrieval."""
    documents: List[RetrievedDocument]
    sources_used: List[SourceType]
    sources_queried: List[SourceType]
    prefilter_time_ms: float
    retrieval_time_ms: float
    rerank_time_ms: float
    total_time_ms: float
    complexity: QueryComplexity = QueryComplexity.HYBRID
    skip_synthesis: bool = False  # True if response is already formatted (template)

    # Legal query indicators (for orchestration decisions)
    is_legal_query: bool = False  # True if query involves legal content (any legal source)
    is_pure_legal: bool = False   # True if ONLY legal sources (no SQL/RAG/web mix)

    @property
    def top_documents(self) -> List[RetrievedDocument]:
        """Top 5 documents par score."""
        return sorted(self.documents, key=lambda d: d.score, reverse=True)[:5]

    @property
    def needs_heavy_llm(self) -> bool:
        """True if response needs heavy LLM (Mistral) vs light/template."""
        return self.complexity in (QueryComplexity.HYBRID, QueryComplexity.COMPLEX)


class FastPathDetector:
    """
    Étape 1: Détection des requêtes simples pour fast-path.

    Fast-paths:
    - SQL simple (combien, liste, qui) → Direct SQL → Template response
    - RAG simple (résume ce document) → Direct RAG → Light LLM
    - Web explicit (cherche sur internet) → Direct Web → Light LLM

    Performance: ~0.1ms
    Objectif: 60-70% des requêtes bypassen le full pipeline
    """

    # === SQL SIMPLE PATTERNS ===
    # Questions quantitatives simples (réponse = 1 nombre ou courte liste)
    SQL_SIMPLE_PATTERNS = [
        # Combien de X ?
        (r"combien\s+(de|d')\s*\w+", "count"),
        # Liste des X
        (r"liste\s+(des?|les?)\s*\w+", "list"),
        # Qui est/habite ?
        (r"qui\s+(est|habite|travaille)", "who"),
        # Quel est le/la ?
        (r"quel(le)?\s+(est|sont)", "what"),
        # Donne-moi le/la
        (r"donne[- ]moi\s+(le|la|les)", "give"),
        # Contact de X
        (r"contact\s+(de|du|des)", "contact"),
        # Email/téléphone de X
        (r"(email|mail|telephone|tel)\s+(de|du|des)", "contact"),
    ]

    # Entités qui confirment SQL (données structurées)
    SQL_ENTITIES = {
        "copropriétaire", "coproprietaire", "copropriétaires", "coproprietaires",
        "lot", "lots", "tantième", "tantieme", "tantiemes",
        "copropriété", "copropriete", "copropriétés", "coproprietes",
        "professionnel", "professionnels", "prestataire", "prestataires",
        "plombier", "électricien", "electricien", "gardien", "jardinier",
        "fournisseur", "fournisseurs", "charge", "charges", "impayé", "impayes",
    }

    # === RAG SIMPLE PATTERNS ===
    # Requêtes sur un document spécifique (élargi pour couvrir plus de cas)
    RAG_SIMPLE_PATTERNS = [
        # Résumé de documents
        (r"(résume|resume|résumer)\s+(ce|le|la|mon|notre)\s*(document|doc|fichier|pdf|pv|procès-verbal|proces-verbal)", "summarize"),
        (r"(résume|resume|résumer)\s+le\s+pv", "summarize_pv"),
        (r"(résume|resume|résumer)\s+le\s+(procès-verbal|proces-verbal)", "summarize_pv"),
        (r"(résume|resume|résumer)\s+l['']?(assemblée|assemblee)\s+g[ée]n[ée]rale", "summarize_ag"),
        # Contenu des documents
        (r"que\s+(dit|contient)\s+(ce|le|la|mon|notre)\s*(document|doc|fichier|contrat)", "content"),
        (r"que\s+(dit|contient)\s+(le|mon|notre)\s*(règlement|reglement)\s+(de\s+copropriété|de\s+copropriete)?", "content_reglement"),
        (r"que\s+(dit|contient)\s+(le|mon|notre)\s*pv", "content_pv"),
        # Lecture/affichage
        (r"(lis|lire|affiche)\s+(ce|le|la|mon)\s*(document|doc|fichier)", "read"),
        # Questions sur le règlement de copropriété spécifique
        (r"(dans|selon|d'après|d apres)\s+(le|mon|notre)\s*(règlement|reglement)", "reglement_content"),
        (r"(le|mon|notre)\s*(règlement|reglement)\s+(de\s+copropriété|de\s+copropriete)?\s+(dit|prévoit|prevoit|stipule|interdit|autorise)", "reglement_content"),
    ]

    # === WEB EXPLICIT PATTERNS ===
    # Demandes explicites de recherche web
    WEB_EXPLICIT_PATTERNS = [
        (r"(cherche|recherche)\s+(sur\s+)?(internet|le\s+web|google)", "web_search"),
        (r"(trouve|trouver)\s+sur\s+(internet|le\s+web)", "web_search"),
        (r"(prix|tarif|cout)\s+(moyen|actuel|du\s+marche)", "market_price"),
        (r"(actualité|actualite|news)\s+(sur|de|du)", "news"),
    ]

    # === LEGAL EXPLICIT PATTERNS ===
    # Pure legal queries that should go directly to LegalAgent
    LEGAL_EXPLICIT_PATTERNS = [
        # Questions directes sur la loi
        (r"que\s+dit\s+la\s+loi\s+(sur|concernant)", "law_question"),
        (r"(quelles?\s+sont\s+les\s+)?obligations?\s+(l[ée]gales?|du\s+syndic)", "legal_obligation"),
        (r"est[- ]ce\s+(l[ée]gal|conforme)\s+(de|d'|a la loi)", "legality_check"),
        (r"peut[- ]on\s+l[ée]galement", "legality_check"),
        # Références explicites
        (r"(code\s+civil|loi\s+de\s+1965|d[ée]cret\s+de\s+1967)", "legal_reference"),
        (r"l[ée]gifrance", "legal_search"),
        (r"jurisprudence\s+(sur|concernant)", "jurisprudence"),
        (r"article\s+(24|25|26)\s+(de\s+la\s+loi)?", "article_majority"),
        # Majorités
        (r"majorit[ée]\s+(requise|n[ée]cessaire|de\s+l'article)", "voting_majority"),
        (r"quelle\s+majorit[ée]\s+pour", "voting_majority"),
        # Procédures légales
        (r"proc[ée]dure\s+l[ée]gale", "legal_procedure"),
        (r"mise\s+en\s+demeure", "legal_procedure"),
        (r"responsabilit[ée]\s+(du\s+syndic|en\s+cas\s+de)", "legal_responsibility"),
    ]

    # Entités qui confirment LEGAL
    LEGAL_ENTITIES = {
        "code civil", "loi", "décret", "ordonnance", "arrêté",
        "jurisprudence", "tribunal", "cour", "cassation",
        "article 24", "article 25", "article 26",
        "majorité", "vote", "assemblée générale", "ag",
        "obligation", "responsabilité", "syndic",
    }

    def __init__(self):
        import re
        self._sql_patterns = [(re.compile(p, re.IGNORECASE), t) for p, t in self.SQL_SIMPLE_PATTERNS]
        self._rag_patterns = [(re.compile(p, re.IGNORECASE), t) for p, t in self.RAG_SIMPLE_PATTERNS]
        self._web_patterns = [(re.compile(p, re.IGNORECASE), t) for p, t in self.WEB_EXPLICIT_PATTERNS]
        self._legal_patterns = [(re.compile(p, re.IGNORECASE), t) for p, t in self.LEGAL_EXPLICIT_PATTERNS]

    def detect(self, query: str, context: Dict[str, Any] = None) -> Tuple[QueryComplexity, Set[SourceType], float]:
        """
        Détecte la complexité de la requête et les sources à utiliser.

        NOUVELLE APPROCHE EN DEUX TEMPS:
        1. Détecter indépendamment tous les signaux (SQL, RAG, Legal, Web)
        2. Construire candidate_sources et déterminer complexity

        Returns:
            Tuple[complexity, sources, confidence]
        """
        query_lower = query.lower()

        # ===================================================================
        # ÉTAPE 1: Détection indépendante de tous les signaux
        # ===================================================================
        candidate_sources: Set[SourceType] = set()
        signals = {
            "sql": False,
            "rag": False,
            "legal": False,
            "web": False,
            "sql_pattern": None,
            "rag_pattern": None,
            "legal_pattern": None,
            "web_pattern": None,
        }

        # --- Détection WEB ---
        for pattern, pattern_type in self._web_patterns:
            if pattern.search(query_lower):
                signals["web"] = True
                signals["web_pattern"] = pattern_type
                candidate_sources.add(SourceType.WEB)
                break

        # --- Détection SQL ---
        # Patterns SQL explicites
        for pattern, pattern_type in self._sql_patterns:
            if pattern.search(query_lower):
                signals["sql_pattern"] = pattern_type
                break

        # Entités SQL (copropriétaires, lots, charges, etc.)
        sql_entity_found = any(entity in query_lower for entity in self.SQL_ENTITIES)

        # Pattern lot + numéro (lot 12, lot 305, etc.) = SQL explicite
        import re
        lot_number_pattern = re.search(r'\blot\s+\d+', query_lower)

        # SQL confirmé si pattern + entité OU juste entité avec question quantitative OU lot+numéro
        if signals["sql_pattern"] and sql_entity_found:
            signals["sql"] = True
            candidate_sources.add(SourceType.SQL)
        elif lot_number_pattern:
            # "lot 12", "lot 305" etc. = référence explicite à un lot spécifique
            signals["sql"] = True
            candidate_sources.add(SourceType.SQL)
        elif sql_entity_found and any(kw in query_lower for kw in ["combien", "nombre", "liste", "quel", "donne"]):
            signals["sql"] = True
            candidate_sources.add(SourceType.SQL)

        # --- Détection RAG ---
        # Patterns RAG explicites
        strong_rag_patterns = ["summarize_pv", "summarize_ag", "content_reglement", "content_pv", "reglement_content"]
        for pattern, pattern_type in self._rag_patterns:
            if pattern.search(query_lower):
                signals["rag_pattern"] = pattern_type
                signals["rag"] = True
                candidate_sources.add(SourceType.RAG)
                break

        # Mots-clés RAG (documents spécifiques)
        # Note: "assemblée générale" retiré car dans contexte legal, c'est un concept juridique, pas un document
        rag_keywords = [
            "règlement de copropriété", "reglement de copropriete", "mon règlement", "mon reglement",
            "le règlement", "le reglement", "notre règlement", "notre reglement",
            "pv", "procès-verbal", "proces-verbal",
            "contrat", "mon contrat", "le contrat", "budget prévisionnel", "budget previsionnel",
            "ce document", "mon document", "le document",
            "résumé de l'ag", "resume de l'ag", "dernier pv", "pv de l'ag",
        ]
        if any(kw in query_lower for kw in rag_keywords):
            signals["rag"] = True
            candidate_sources.add(SourceType.RAG)

        # Patterns de comparaison (SQL + RAG)
        comparison_patterns = [
            "compare", "comparer", "par rapport à", "par rapport a",
            "avec ce qui est prévu", "avec ce qui est prevu",
            "versus", "vs", "différence entre", "difference entre",
        ]
        has_comparison = any(kw in query_lower for kw in comparison_patterns)
        if has_comparison and signals["sql"]:
            # Comparaison implique souvent RAG (document de référence)
            signals["rag"] = True
            candidate_sources.add(SourceType.RAG)

        # --- Détection LEGAL ---
        # Patterns Legal explicites
        for pattern, pattern_type in self._legal_patterns:
            if pattern.search(query_lower):
                signals["legal_pattern"] = pattern_type
                signals["legal"] = True
                candidate_sources.add(SourceType.LEGAL)
                break

        # Mots-clés Legal forts
        legal_high_keywords = [
            "loi", "légal", "legal", "juridique", "légifrance", "legifrance",
            "code civil", "article 24", "article 25", "article 26",
            "majorité", "majorite", "changer de syndic", "responsabilité du syndic",
            "obligation légale", "obligation legale", "que dit la loi",
            "selon la loi", "d'après la loi", "conforme à la loi",
        ]
        if any(kw in query_lower for kw in legal_high_keywords):
            signals["legal"] = True
            candidate_sources.add(SourceType.LEGAL)

        # Entités Legal
        legal_entity_count = sum(1 for e in self.LEGAL_ENTITIES if e in query_lower)
        if legal_entity_count >= 2:
            signals["legal"] = True
            candidate_sources.add(SourceType.LEGAL)

        # ===================================================================
        # SUPPRESSION SQL pour questions juridiques pures
        # ===================================================================
        # Si legal est détecté ET SQL n'a PAS de référence spécifique (lot X, copropriétaire X)
        # alors supprimer SQL car c'est une question juridique, pas une query de données
        if signals["legal"] and signals["sql"]:
            # Questions SQL explicites (combien, nombre, liste) = NE PAS supprimer
            explicit_sql_questions = any(kw in query_lower for kw in [
                "combien de", "nombre de", "liste des", "donne-moi les", "donne moi les"
            ])

            # Entités SQL spécifiques (qui nécessitent vraiment une query SQL)
            specific_sql_entities = ["lot ", "copropriétaire du", "coproprietaire du",
                                     "charges du", "email du", "contact du", "adresse du"]
            has_specific_entity = any(e in query_lower for e in specific_sql_entities)

            # Contexte purement juridique (majorité, vote, loi)
            pure_legal_context = any(kw in query_lower for kw in [
                "majorité de vote", "majorite de vote", "majorités de vote", "majorites de vote",
                "quorum", "article 24", "article 25", "article 26",
                "que dit la loi", "selon la loi", "d'après la loi"
            ])

            # Supprimer SQL SEULEMENT si:
            # - Contexte juridique pur ET
            # - Pas de question SQL explicite (combien, nombre) ET
            # - Pas d'entité spécifique ET
            # - Pas de lot + numéro
            if pure_legal_context and not explicit_sql_questions and not has_specific_entity and not lot_number_pattern:
                # Supprimer SQL - c'est une question juridique pure
                signals["sql"] = False
                candidate_sources.discard(SourceType.SQL)
                logger.info("sql_suppressed_for_pure_legal", query_preview=query[:50])

        # ===================================================================
        # ÉTAPE 2: Déterminer complexity et sources finales
        # ===================================================================
        num_sources = len(candidate_sources)

        # Cas spécial: Web explicite = priorité absolue (simple_web)
        if signals["web"] and num_sources == 1:
            logger.info("fast_path_detected", type="web_explicit", pattern=signals["web_pattern"])
            return QueryComplexity.SIMPLE_WEB, {SourceType.WEB}, 0.95

        # 1 source = SIMPLE_*
        if num_sources == 1:
            source = list(candidate_sources)[0]
            if source == SourceType.SQL:
                logger.info("fast_path_detected", type="sql_simple", pattern=signals["sql_pattern"])
                return QueryComplexity.SIMPLE_SQL, candidate_sources, 0.95
            elif source == SourceType.RAG:
                logger.info("fast_path_detected", type="rag_simple", pattern=signals["rag_pattern"])
                return QueryComplexity.SIMPLE_RAG, candidate_sources, 0.90
            elif source == SourceType.LEGAL:
                logger.info("fast_path_detected", type="legal_simple", pattern=signals["legal_pattern"])
                return QueryComplexity.SIMPLE_LEGAL, candidate_sources, 0.95
            elif source == SourceType.WEB:
                logger.info("fast_path_detected", type="web_simple", pattern=signals["web_pattern"])
                return QueryComplexity.SIMPLE_WEB, candidate_sources, 0.95

        # 2 sources = HYBRID
        if num_sources == 2:
            source_types = [s.value for s in candidate_sources]
            logger.info("fast_path_detected", type="hybrid", sources=source_types,
                       sql=signals["sql"], rag=signals["rag"], legal=signals["legal"])
            return QueryComplexity.HYBRID, candidate_sources, 0.85

        # 3+ sources = COMPLEX (multi-source)
        if num_sources >= 3:
            source_types = [s.value for s in candidate_sources]
            logger.info("fast_path_detected", type="complex_multi", sources=source_types,
                       sql=signals["sql"], rag=signals["rag"], legal=signals["legal"], web=signals["web"])
            return QueryComplexity.COMPLEX, candidate_sources, 0.80

        # 0 sources = fallback to prefilter
        logger.info("fast_path_no_match", query_preview=query[:50])
        return QueryComplexity.HYBRID, set(), 0.5


class FastPrefilter:
    """
    Pre-filtrage ultra-rapide base sur des regles.
    Performance: ~1ms, $0
    Precision: ~90% pour determiner les sources pertinentes
    """

    # Indicateurs SQL (donnees structurees)
    SQL_INDICATORS = {
        # Questions quantitatives
        "combien", "nombre", "total", "somme", "moyenne",
        "liste", "lister", "tous les", "toutes les",
        # Entites structurees
        "coproprietaire", "coproprietaires", "proprietaire",
        "lot", "lots", "tantieme", "tantiemes",
        "email", "mail", "telephone", "adresse",
        "professionnel", "professionnels", "prestataire",
        "plombier", "electricien", "gardien",
        # Questions sur des personnes
        "qui habite", "qui est", "contact de",
        # Charges et finances
        "charge", "charges", "impaye", "impayes",
        "appel de fonds", "budget",
    }

    # Indicateurs RAG (documents)
    RAG_INDICATORS = {
        # References aux documents
        "document", "documents", "fichier",
        "contrat", "contrats", "facture", "factures",
        "devis", "pv", "proces-verbal",
        "reglement", "reglements",
        # Actions sur documents
        "resume", "resumer", "analyse", "analyser",
        "que dit le", "que dit ce", "selon le",
        "extrait", "extraire", "cherche dans",
        # Types de documents specifiques
        "syndic", "convention", "bail",
    }

    # =============================================
    # LEGAL INDICATORS - Comprehensive Legal Keywords
    # =============================================
    # Weighted scoring: HIGH (3), MEDIUM (2), LOW (1)

    # HIGH PRIORITY (score=3) - Pure juridique, triggers direct
    LEGAL_HIGH_PRIORITY = {
        # Codes fondamentaux
        "code civil", "code de la construction", "code de la consommation",
        "code des assurances", "code de commerce",
        # Jurisprudence & decisions
        "jurisprudence", "arret de la cour de cassation", "arret cassation",
        "decision de justice", "autorite de la chose jugee",
        # Lois copropriete specifiques
        "loi de 1965", "decret de 1967", "loi elan", "loi climat", "loi alur",
        # Majorites AG (ultra pertinent syndic)
        "majorite de l'article 24", "majorite de l'article 25", "majorite de l'article 26",
        "majorite absolue", "majorite simple",
        # Obligations professionnelles
        "obligations du syndic", "obligations legales", "responsabilite du syndic",
        "responsabilite du coproprietaire",
        # Concepts juridiques forts
        "conformite legale", "mise en demeure", "recouvrement legal",
        # API Reference
        "legifrance",
    }

    # MEDIUM PRIORITY (score=2)
    LEGAL_MEDIUM_PRIORITY = {
        # References legales generales
        "loi", "lois", "legal", "legale", "legalement",
        "juridique", "juridiquement",
        # Codes et articles
        "article", "articles", "alinea", "decret", "ordonnance", "arrete",
        # Jurisprudence
        "arret", "arrets", "decision de la cour", "affaire",
        "tribunal", "cour", "cour d'appel",
        # Concepts juridiques
        "obligation", "obligations", "droit", "droits",
        "conforme", "conformite", "reglementation",
        "prescription", "sanctions", "nullite", "caducite",
        "conditions legales",
        # Copropriete
        "tantieme", "tantiemes", "delegation de vote",
        "convocation ag", "ordre du jour", "proces-verbal ag",
        "habitation decente",
        # Normes
        "obligation reglementaire", "normes", "dtu",
        "circulaire",
    }

    # LOW PRIORITY (score=1) - Context dependent
    LEGAL_LOW_PRIORITY = {
        # Termes generaux qui peuvent etre juridiques
        "litige", "contestation", "recours",
        # Termes syndic
        "reglement de copropriete",
    }

    # Combined for backward compatibility
    LEGAL_INDICATORS = LEGAL_HIGH_PRIORITY | LEGAL_MEDIUM_PRIORITY | LEGAL_LOW_PRIORITY

    # Indicateurs Web (recherche externe)
    WEB_INDICATORS = {
        # Prix et marche
        "prix moyen", "tarif moyen", "cout moyen",
        "tarif marche", "prix du marche",
        "estimation", "estimer le cout",
        # Recherche externe
        "cherche sur internet", "recherche internet",
        "trouve des entreprises", "trouver une entreprise",
        "prestataire externe", "entreprise de",
        # Actualites
        "actualite", "actualites", "news",
        "derniere nouvelle", "dernieres nouvelles",
        # Comparaison marche
        "comparer les prix", "devis en ligne",
    }

    # =============================================
    # FORCE PATTERNS - Direct triggers for sources
    # =============================================
    # These patterns ALWAYS trigger the specified source

    FORCE_PATTERNS = {
        # Force LEGAL - Expression patterns that are 100% legal
        SourceType.LEGAL: [
            # Questions explicites sur la loi
            "que dit la loi sur",
            "que dit la loi",
            "selon la loi",
            "est-ce conforme a la loi",
            "est-ce legal de",
            "peut-on legalement",
            "quelle est la reglementation concernant",
            "quelle est la reglementation",
            "quels textes s'appliquent",
            # Obligations specifiques
            "obligation legale",
            "obligations legales",
            "obligations du syndic",
            "obligation du coproprietaire",
            "obligation du syndic de",
            "obligation du coproprietaire de",
            # Procedures
            "procedure legale pour",
            "procedure legale",
            "majorite requise pour voter",
            "majorite requise",
            "responsabilite en cas de",
            # References directes
            "code civil",
            "code de la construction",
            "loi de 1965",
            "decret de 1967",
            "legifrance",
            # Jurisprudence
            "jurisprudence sur",
            "arret cassation",
            "arret de la cour de cassation",
            # Majorites AG
            "article 24", "article 25", "article 26",
        ],
        # Force WEB pour prix marche
        SourceType.WEB: [
            "prix moyen",
            "tarif moyen",
            "cout moyen",
            "tarif du marche",
            "prix du marche",
            "entreprise de ravalement",
            "cherche sur internet",
            "recherche internet",
        ],
        # Force RAG pour documents specifiques
        SourceType.RAG: [
            # Règlement de copropriété (document spécifique, pas la loi)
            "que dit le reglement",
            "que dit mon reglement",
            "que dit notre reglement",
            "selon le reglement de copropriete",
            "selon mon reglement",
            "selon notre reglement",
            "d'apres le reglement",
            "d'apres mon reglement",
            "le reglement de copropriete sur",
            "mon reglement de copropriete",
            "notre reglement de copropriete",
            # PV / Procès-verbaux
            "resume le pv",
            "que dit le pv",
            "selon le pv",
            "d'apres le pv",
            "le pv de l'assemblee",
            "le pv de l'ag",
            "le proces-verbal",
            # Documents spécifiques
            "ce document",
            "mon document",
            "mon contrat",
            "mon bail",
            "mon devis",
            "ma facture",
            "que contient le document",
            "dans le document",
            "selon le contrat",
            "d'apres le contrat",
            # Budget
            "budget previsionnel",
            "dans le budget",
        ],
    }

    # =============================================
    # LEGAL EXPRESSION PATTERNS - Regex triggers
    # =============================================
    # Full sentence patterns that imply legal intent

    LEGAL_EXPRESSION_PATTERNS = [
        r"que\s+dit\s+la\s+loi\s+sur",
        r"est[- ]ce\s+conforme\s+[àa]\s+la\s+loi",
        r"est[- ]ce\s+l[ée]gal\s+de",
        r"peut[- ]on\s+l[ée]galement",
        r"quelle\s+est\s+la\s+r[ée]glementation\s+concernant",
        r"obligation\s+du\s+(syndic|coproprietaire)\s+de",
        r"proc[ée]dure\s+l[ée]gale\s+pour",
        r"majorit[ée]\s+requise\s+pour\s+voter",
        r"responsabilit[ée]\s+en\s+cas\s+de",
        r"quels?\s+textes?\s+s'appliquent?\s+[àa]",
    ]

    def __init__(self):
        """Initialize prefilter with compiled regex patterns."""
        import re
        self._legal_patterns = [re.compile(p, re.IGNORECASE) for p in self.LEGAL_EXPRESSION_PATTERNS]

    def prefilter(self, query: str) -> Tuple[Set[SourceType], float]:
        """
        Pre-filtre la requete pour determiner les sources pertinentes.

        Uses weighted scoring for legal keywords:
        - HIGH (3 points): Pure juridique, direct triggers
        - MEDIUM (2 points): General legal references
        - LOW (1 point): Context-dependent legal terms

        Returns:
            Tuple[Set[SourceType], float]: (sources, confidence)
        """
        start_time = datetime.now()

        query_lower = query.lower()
        # Normalize accents for matching
        query_normalized = self._normalize_accents(query_lower)

        sources: Set[SourceType] = set()
        scores: Dict[SourceType, int] = {s: 0 for s in SourceType}

        # 1. Check legal expression patterns (regex) - HIGHEST PRIORITY
        for pattern in self._legal_patterns:
            if pattern.search(query_normalized):
                sources.add(SourceType.LEGAL)
                scores[SourceType.LEGAL] += 15  # Very high bonus for regex match
                logger.info("legal_expression_pattern_matched", pattern=pattern.pattern[:50])
                break  # One match is enough

        # 2. Check force patterns (priorite haute)
        for source, patterns in self.FORCE_PATTERNS.items():
            if any(p in query_normalized for p in patterns):
                sources.add(source)
                scores[source] += 10  # Bonus eleve

        # 3. Count indicator matches with WEIGHTED scoring for LEGAL
        for indicator in self.SQL_INDICATORS:
            if indicator in query_normalized:
                scores[SourceType.SQL] += 1

        for indicator in self.RAG_INDICATORS:
            if indicator in query_normalized:
                scores[SourceType.RAG] += 1

        # WEIGHTED legal scoring
        for indicator in self.LEGAL_HIGH_PRIORITY:
            if indicator in query_normalized:
                scores[SourceType.LEGAL] += 3  # HIGH = 3 points

        for indicator in self.LEGAL_MEDIUM_PRIORITY:
            if indicator in query_normalized:
                scores[SourceType.LEGAL] += 2  # MEDIUM = 2 points

        for indicator in self.LEGAL_LOW_PRIORITY:
            if indicator in query_normalized:
                scores[SourceType.LEGAL] += 1  # LOW = 1 point

        for indicator in self.WEB_INDICATORS:
            if indicator in query_normalized:
                scores[SourceType.WEB] += 1

        # 4. Select sources with score > 0
        for source, score in scores.items():
            if score > 0:
                sources.add(source)

        # 5. Default: SQL + RAG (most common)
        if not sources:
            sources = {SourceType.SQL, SourceType.RAG}

        # 6. Calculate confidence based on score distribution
        total_score = sum(scores.values())
        if total_score > 0:
            max_score = max(scores.values())
            confidence = min(max_score / total_score + 0.5, 1.0)
        else:
            confidence = 0.5  # Default confidence

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info("fast_prefilter_complete",
                   query_preview=query[:50],
                   sources=[s.value for s in sources],
                   scores={s.value: v for s, v in scores.items()},  # Convert enum keys to strings
                   confidence=confidence,
                   elapsed_ms=round(elapsed_ms, 2))

        return sources, confidence

    def _normalize_accents(self, text: str) -> str:
        """Remove accents for matching (loi élan → loi elan)."""
        import unicodedata
        normalized = unicodedata.normalize('NFKD', text)
        return ''.join(c for c in normalized if not unicodedata.combining(c))


class ParallelRetriever:
    """
    Recuperation parallele depuis plusieurs sources.
    Performance: ~200-400ms (depend de la source la plus lente)
    """

    def __init__(self):
        self._sql_agent = None
        self._rag_service = None
        self._web_agent = None
        self._legal_agent = None

    @property
    def sql_agent(self):
        """Lazy load SQL agent."""
        if self._sql_agent is None:
            from app.services.agents.sql_agent import SQLAgent
            self._sql_agent = SQLAgent()
        return self._sql_agent

    @property
    def rag_service(self):
        """Lazy load RAG service."""
        if self._rag_service is None:
            from app.services.rag_service import get_rag_service
            self._rag_service = get_rag_service()
        return self._rag_service

    @property
    def web_agent(self):
        """Lazy load Web agent."""
        if self._web_agent is None:
            from app.services.agents.web_agent import WebAgent
            self._web_agent = WebAgent()
        return self._web_agent

    @property
    def legal_agent(self):
        """Lazy load Legal agent."""
        if self._legal_agent is None:
            from app.services.agents.legal_agent import LegalAgent
            self._legal_agent = LegalAgent()
        return self._legal_agent

    async def retrieve_parallel(
        self,
        query: str,
        sources: Set[SourceType],
        db = None,
        context: Dict[str, Any] = None,
        limit_per_source: int = 5
    ) -> Tuple[List[RetrievedDocument], Dict[str, float]]:
        """
        Recupere depuis plusieurs sources en parallele.

        Args:
            query: La requete utilisateur
            sources: Les sources a interroger
            db: Session de base de donnees
            context: Contexte additionnel
            limit_per_source: Nombre max de resultats par source

        Returns:
            Tuple[documents, timings]: Documents et temps par source
        """
        start_time = datetime.now()

        # Create tasks for each source
        tasks = {}

        if SourceType.SQL in sources and db is not None:
            tasks[SourceType.SQL] = self._retrieve_sql(query, db, limit_per_source)

        if SourceType.RAG in sources:
            tasks[SourceType.RAG] = self._retrieve_rag(query, context, limit_per_source)

        if SourceType.WEB in sources:
            tasks[SourceType.WEB] = self._retrieve_web(query, limit_per_source)

        if SourceType.LEGAL in sources:
            tasks[SourceType.LEGAL] = self._retrieve_legal(query, limit_per_source)

        # Execute all tasks in parallel
        if not tasks:
            return [], {}

        results = await asyncio.gather(
            *[self._timed_task(source, task) for source, task in tasks.items()],
            return_exceptions=True
        )

        # Collect results
        all_documents: List[RetrievedDocument] = []
        timings: Dict[str, float] = {}  # Use string keys for JSON serialization

        for result in results:
            if isinstance(result, Exception):
                logger.warning("retrieval_task_failed", error=str(result))
                continue

            source, documents, elapsed_ms = result
            timings[source.value] = elapsed_ms  # Convert enum to string
            all_documents.extend(documents)

        total_elapsed = (datetime.now() - start_time).total_seconds() * 1000

        logger.info("parallel_retrieval_complete",
                   sources_queried=[s.value for s in tasks.keys()],
                   documents_retrieved=len(all_documents),
                   timings=timings,
                   total_ms=round(total_elapsed, 2))

        return all_documents, timings

    async def _timed_task(
        self,
        source: SourceType,
        task
    ) -> Tuple[SourceType, List[RetrievedDocument], float]:
        """Execute a task and measure time."""
        start = datetime.now()
        try:
            documents = await task
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return source, documents, elapsed
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            logger.error("retrieval_failed", source=source.value, error=str(e))
            return source, [], elapsed

    async def _retrieve_sql(
        self,
        query: str,
        db,
        limit: int
    ) -> List[RetrievedDocument]:
        """
        Retrieve from SQL database using LIGHT MODE (no LLM).

        OPTIMIZATION: Uses SQLAgent.retrieve_light() with SQL templates
        instead of SQLAgent.process() which calls LLM for SQL generation.
        """
        try:
            # Use light mode (template-based SQL, no LLM call)
            light_results = await self.sql_agent.retrieve_light(query, db, limit)

            if light_results:
                # Convert light results to RetrievedDocument
                documents = []
                for result in light_results:
                    documents.append(RetrievedDocument(
                        content=result.get("content", ""),
                        source=SourceType.SQL,
                        score=result.get("score", 0.8),
                        metadata=result.get("metadata", {})
                    ))
                logger.info("sql_light_retrieval_success", docs_count=len(documents))
                return documents

            # Light mode didn't match any template - fallback to full mode (with LLM)
            logger.debug("sql_light_no_match_fallback_full")
            result = await self.sql_agent.process(query, db)

            if not result or not result.get("success"):
                logger.debug("sql_retrieval_no_success", result_keys=list(result.keys()) if result else None)
                return []

            content = result.get("message", "")
            if not content:
                logger.debug("sql_retrieval_no_content", result_keys=list(result.keys()) if result else None)
                return []

            data = result.get("data", {})

            return [RetrievedDocument(
                content=content,
                source=SourceType.SQL,
                score=0.8,
                metadata={
                    "query_executed": result.get("sql_query", ""),
                    "row_count": data.get("row_count", 0),
                    "tables": data.get("tables", []),
                    "mode": "full"  # Flag that full mode was used
                }
            )]

        except Exception as e:
            logger.error("sql_retrieval_failed", error=str(e))
            return []

    async def _retrieve_rag(
        self,
        query: str,
        context: Dict[str, Any] = None,
        limit: int = 5
    ) -> List[RetrievedDocument]:
        """Retrieve from RAG (document search)."""
        try:
            # Check for selected documents in context
            document_ids = None
            if context:
                document_ids = context.get("active_document_ids") or context.get("selected_document_ids")

            results = await self.rag_service.search(
                query=query,
                limit=limit,
                document_ids=document_ids
            )

            documents = []
            for r in results:
                documents.append(RetrievedDocument(
                    content=r.get("content", r.get("text", "")),
                    source=SourceType.RAG,
                    score=r.get("score", 0.5),
                    metadata={
                        "document_id": r.get("document_id"),
                        "filename": r.get("filename", ""),
                        "chunk_index": r.get("chunk_index", 0)
                    }
                ))

            return documents

        except Exception as e:
            logger.error("rag_retrieval_failed", error=str(e))
            return []

    async def _retrieve_web(
        self,
        query: str,
        limit: int = 5
    ) -> List[RetrievedDocument]:
        """
        Retrieve from web search using LIGHT MODE (no LLM synthesis).

        OPTIMIZATION: Uses WebAgent.retrieve_light() which performs web search
        without LLM synthesis. Synthesis is done later by SynthesisAgent.
        """
        try:
            # Use light mode (web search without LLM synthesis)
            light_results = await self.web_agent.retrieve_light(query, limit)

            if light_results:
                documents = []
                for result in light_results:
                    documents.append(RetrievedDocument(
                        content=result.get("content", ""),
                        source=SourceType.WEB,
                        score=result.get("score", 0.7),
                        metadata=result.get("metadata", {})
                    ))
                logger.info("web_light_retrieval_success", docs_count=len(documents))
                return documents

            # No results from light mode
            return []

        except Exception as e:
            logger.error("web_retrieval_failed", error=str(e))
            return []

    async def _retrieve_legal(
        self,
        query: str,
        limit: int = 5
    ) -> List[RetrievedDocument]:
        """
        Retrieve from legal sources using LIGHT MODE (no LLM synthesis).

        OPTIMIZATION: Uses LegalAgent.retrieve_light() which queries Légifrance API
        directly without LLM classification or synthesis. Synthesis is done later.
        """
        try:
            # Use light mode (Légifrance API without LLM)
            light_results = await self.legal_agent.retrieve_light(query, limit)

            if light_results:
                documents = []
                for result in light_results:
                    documents.append(RetrievedDocument(
                        content=result.get("content", ""),
                        source=SourceType.LEGAL,
                        score=result.get("score", 0.8),
                        metadata=result.get("metadata", {})
                    ))
                logger.info("legal_light_retrieval_success", docs_count=len(documents))
                return documents

            # No results from light mode
            return []

        except Exception as e:
            logger.error("legal_retrieval_failed", error=str(e))
            return []


class CrossEncoderReranker:
    """
    Reranking avec Cross-Encoder pour scorer la pertinence.
    Performance: ~100ms pour 20 documents (après warmup)

    Étape 2 Optimisation:
    - Skip si < 3 documents ou 1 seule source
    - Lazy load une seule fois au startup
    - Fallback sur scoring simple si non nécessaire
    """

    # Seuils pour skip du cross-encoder
    MIN_DOCS_FOR_RERANK = 3      # Skip si moins de 3 docs
    MIN_SOURCES_FOR_RERANK = 2   # Skip si 1 seule source

    def __init__(self):
        self._model = None
        self._model_loaded = False
        self._use_fallback = False

    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model_loaded:
            return

        try:
            from sentence_transformers import CrossEncoder
            # Modele multilingual performant
            self._model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')
            self._model_loaded = True
            logger.info("cross_encoder_loaded", model="ms-marco-MiniLM-L-12-v2")
        except ImportError:
            logger.warning("cross_encoder_not_available",
                          reason="sentence-transformers not installed, using fallback")
            self._use_fallback = True
            self._model_loaded = True
        except Exception as e:
            logger.warning("cross_encoder_load_failed", error=str(e))
            self._use_fallback = True
            self._model_loaded = True

    def should_skip(self, documents: List[RetrievedDocument]) -> bool:
        """
        Étape 2: Détermine si on doit skip le cross-encoder.

        Skip si:
        - Moins de MIN_DOCS_FOR_RERANK documents
        - Seulement 1 source impliquée
        """
        if len(documents) < self.MIN_DOCS_FOR_RERANK:
            return True

        # Count distinct sources
        sources = set(doc.source for doc in documents)
        if len(sources) < self.MIN_SOURCES_FOR_RERANK:
            return True

        return False

    def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_k: int = 5,
        force_skip: bool = False
    ) -> List[RetrievedDocument]:
        """
        Rerank documents by relevance to query.

        Args:
            query: The user query
            documents: Documents to rerank
            top_k: Number of top documents to return
            force_skip: Force skip cross-encoder (for simple queries)

        Returns:
            Reranked documents (top_k)
        """
        if not documents:
            return []

        start_time = datetime.now()

        # Étape 2: Smart skip logic
        skip_rerank = force_skip or self.should_skip(documents)

        if skip_rerank:
            # Just sort by existing score and assign citation IDs
            documents.sort(key=lambda d: d.score, reverse=True)
            result = documents[:top_k]
            for i, doc in enumerate(result):
                doc.citation_id = i + 1

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info("rerank_skipped",
                       reason="skip_conditions_met" if not force_skip else "force_skip",
                       input_docs=len(documents),
                       output_docs=len(result),
                       elapsed_ms=round(elapsed_ms, 2))
            return result

        # Load model only when needed
        self._load_model()

        if self._use_fallback:
            # Fallback: simple keyword overlap scoring
            reranked = self._fallback_rerank(query, documents)
        else:
            # Cross-encoder scoring
            reranked = self._cross_encoder_rerank(query, documents)

        # Sort by score and take top_k
        reranked.sort(key=lambda d: d.score, reverse=True)
        result = reranked[:top_k]

        # Assign citation IDs
        for i, doc in enumerate(result):
            doc.citation_id = i + 1

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info("rerank_complete",
                   input_docs=len(documents),
                   output_docs=len(result),
                   method="cross_encoder" if not self._use_fallback else "fallback",
                   elapsed_ms=round(elapsed_ms, 2))

        return result

    def _cross_encoder_rerank(
        self,
        query: str,
        documents: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """Rerank using cross-encoder model."""
        # Prepare pairs for scoring
        pairs = [(query, doc.content[:512]) for doc in documents]  # Limit content length

        # Get scores
        scores = self._model.predict(pairs)

        # Update document scores
        for doc, score in zip(documents, scores):
            doc.score = float(score)

        return documents

    def _fallback_rerank(
        self,
        query: str,
        documents: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """Fallback reranking using keyword overlap."""
        query_words = set(query.lower().split())

        for doc in documents:
            doc_words = set(doc.content.lower().split())

            # Jaccard similarity
            intersection = len(query_words & doc_words)
            union = len(query_words | doc_words)

            if union > 0:
                similarity = intersection / union
            else:
                similarity = 0

            # Combine with existing score
            doc.score = 0.5 * doc.score + 0.5 * similarity

        return documents


class WorldClassRouter:
    """
    Routeur World-Class inspiré de Perplexity/Cohere.

    Pipeline OPTIMISÉ:
    0. Fast-Path Detection (~0.1ms) - Bypass pour requêtes simples
    1. Fast Pre-filter (~1ms) - Determine sources probables
    2. Parallel Retrieval (~200-400ms) - Recupere de toutes les sources
    3. Cross-Encoder Rerank (~100ms) - Skip si simple, sinon rerank

    Optimisations:
    - SQL simple → skip rerank + skip synthesis (template response)
    - RAG simple → skip rerank + light LLM
    - < 3 docs ou 1 source → skip cross-encoder

    Streaming (Option C):
    - Emits progress messages at each stage via thought_stream
    - NO LLM calls for progress messages (pre-defined)
    """

    def __init__(self):
        self.fast_path = FastPathDetector()
        self.prefilter = FastPrefilter()
        self.retriever = ParallelRetriever()
        self.reranker = CrossEncoderReranker()

    async def route_and_retrieve(
        self,
        query: str,
        db = None,
        context: Dict[str, Any] = None,
        top_k: int = 5,
        thought_stream = None  # Optional: for streaming progress
    ) -> RouterResult:
        """
        Route la requete et recupere les documents pertinents.

        Args:
            query: La requete utilisateur
            db: Session de base de donnees
            context: Contexte additionnel (documents selectionnes, etc.)
            top_k: Nombre de documents a retourner
            thought_stream: Optional thought stream for progress messages

        Returns:
            RouterResult avec les documents et metriques
        """
        total_start = datetime.now()

        # Import progress messages (no LLM call)
        from app.services.agents.thought_stream import PROGRESS_MESSAGES, ThoughtType

        # === PROGRESS: Routing ===
        if thought_stream:
            msg = PROGRESS_MESSAGES["routing"]
            await thought_stream.add_thought(
                msg["type"],
                title=msg["title"],
                content=msg["content"],
                agent="world_class_router",
                progress=msg["progress"]
            )

        # 0. FAST-PATH DETECTION (Étape 1)
        complexity, fast_path_sources, fp_confidence = self.fast_path.detect(query, context)

        # If fast-path detected, use those sources directly
        if fast_path_sources:
            sources = fast_path_sources
            prefilter_time = 0.0
            logger.info("fast_path_activated",
                       complexity=complexity.value,
                       sources=[s.value for s in sources],
                       confidence=fp_confidence)
        else:
            # 1. FAST PRE-FILTER (standard path)
            prefilter_start = datetime.now()
            sources, confidence = self.prefilter.prefilter(query)
            prefilter_time = (datetime.now() - prefilter_start).total_seconds() * 1000

        # === PROGRESS: Retrieval (emit progress for each source) ===
        if thought_stream and sources:
            # Map SourceType to progress message key
            source_to_progress_key = {
                SourceType.SQL: "retrieval_sql",
                SourceType.RAG: "retrieval_rag",
                SourceType.LEGAL: "retrieval_legal",
                SourceType.WEB: "retrieval_web",
            }
            for source in sources:
                progress_key = source_to_progress_key.get(source)
                if progress_key and progress_key in PROGRESS_MESSAGES:
                    msg = PROGRESS_MESSAGES[progress_key]
                    await thought_stream.add_thought(
                        msg["type"],
                        title=msg["title"],
                        content=msg["content"],
                        agent="world_class_router",
                        progress=msg["progress"]
                    )

        # 2. PARALLEL RETRIEVAL
        retrieval_start = datetime.now()
        documents, timings = await self.retriever.retrieve_parallel(
            query=query,
            sources=sources,
            db=db,
            context=context,
            limit_per_source=top_k
        )
        retrieval_time = (datetime.now() - retrieval_start).total_seconds() * 1000

        # Determine if we should skip synthesis (Étape 3)
        # Skip synthesis for SIMPLE_SQL (template response) and SIMPLE_WEB (already synthesized by WebAgent)
        skip_synthesis = complexity in (QueryComplexity.SIMPLE_SQL, QueryComplexity.SIMPLE_WEB)

        # 3. CROSS-ENCODER RERANK (with skip logic - Étape 2)
        # Force skip for simple queries (all SIMPLE_* types skip cross-encoder)
        force_skip_rerank = complexity in (QueryComplexity.SIMPLE_SQL, QueryComplexity.SIMPLE_RAG, QueryComplexity.SIMPLE_WEB, QueryComplexity.SIMPLE_LEGAL)

        # === PROGRESS: Reranking (only if not skipped) ===
        if thought_stream and not force_skip_rerank and len(documents) >= 3:
            msg = PROGRESS_MESSAGES["reranking"]
            await thought_stream.add_thought(
                msg["type"],
                title=msg["title"],
                content=msg["content"],
                agent="world_class_router",
                progress=msg["progress"]
            )

        rerank_start = datetime.now()
        reranked = self.reranker.rerank(query, documents, top_k=top_k, force_skip=force_skip_rerank)
        rerank_time = (datetime.now() - rerank_start).total_seconds() * 1000

        total_time = (datetime.now() - total_start).total_seconds() * 1000

        # Determine which sources actually returned results
        sources_used = list(set(doc.source for doc in reranked))

        # Determine legal query indicators
        is_legal_query = SourceType.LEGAL in sources or SourceType.LEGAL in sources_used
        is_pure_legal = complexity == QueryComplexity.SIMPLE_LEGAL

        logger.info("world_class_router_complete",
                   query_preview=query[:50],
                   complexity=complexity.value,
                   sources_queried=[s.value for s in sources],
                   sources_used=[s.value for s in sources_used],
                   documents_returned=len(reranked),
                   skip_synthesis=skip_synthesis,
                   prefilter_ms=round(prefilter_time, 2),
                   retrieval_ms=round(retrieval_time, 2),
                   rerank_ms=round(rerank_time, 2),
                   total_ms=round(total_time, 2))

        return RouterResult(
            documents=reranked,
            sources_used=sources_used,
            sources_queried=list(sources),
            prefilter_time_ms=prefilter_time,
            retrieval_time_ms=retrieval_time,
            rerank_time_ms=rerank_time,
            total_time_ms=total_time,
            complexity=complexity,
            skip_synthesis=skip_synthesis,
            is_legal_query=is_legal_query,
            is_pure_legal=is_pure_legal
        )


# Singleton instance
_router_instance: Optional[WorldClassRouter] = None


def get_world_class_router() -> WorldClassRouter:
    """Get or create the singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = WorldClassRouter()
        logger.info("world_class_router_initialized")
    return _router_instance
