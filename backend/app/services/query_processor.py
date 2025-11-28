"""
Query Processing Service - Normalize queries before embedding

Improves RAG retrieval by removing stopwords and normalizing queries.
"""

import re
from typing import List, Set
import structlog

logger = structlog.get_logger()


class QueryProcessor:
    """
    Preprocess queries for better RAG retrieval

    Features:
    - Removes French stopwords
    - Lowercases text
    - Removes punctuation (keeps hyphens)
    - Normalizes whitespace

    Example:
        >>> processor = QueryProcessor()
        >>> processor.normalize("Quelle est la couleur des volets roulants ?")
        'couleur volets roulants'
    """

    # French stopwords - common words with little semantic value
    FRENCH_STOPWORDS: Set[str] = {
        # Articles
        "le", "la", "les", "un", "une", "des", "du", "de", "d",
        # Demonstratives
        "ce", "cette", "ces", "cet",
        # Possessives
        "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes",
        "notre", "nos", "votre", "vos", "leur", "leurs",
        # Prepositions
        "au", "aux", "à", "dans", "sur", "pour", "par", "avec", "sans",
        "sous", "vers", "chez", "en",
        # Verbs
        "est", "sont", "être", "avoir", "a", "ont", "était", "étaient",
        "sera", "seront", "fait", "faire",
        # Question words (keep some for context)
        "quel", "quelle", "quels", "quelles", "comment",
        # Others
        "que", "qui", "dont", "où", "quand", "pourquoi",
        "si", "ne", "pas", "plus", "aussi", "très", "tout", "tous",
        "autre", "autres", "même", "mêmes", "tel", "tels", "telle", "telles"
    }

    @staticmethod
    def normalize(query: str, keep_question_words: bool = False) -> str:
        """
        Normalize query for better embedding quality

        Steps:
        1. Lowercase
        2. Remove punctuation (keep hyphens for compound words)
        3. Remove stopwords
        4. Remove extra whitespace

        Args:
            query: Original user query
            keep_question_words: If True, keeps "quelle", "quel", etc. (default False)

        Returns:
            Normalized query string

        Example:
            >>> QueryProcessor.normalize("Quelle est la couleur des volets ?")
            'couleur volets'
        """
        if not query or not query.strip():
            return query

        original_query = query

        # Step 1: Lowercase
        query = query.lower()

        # Step 2: Remove punctuation (keep hyphens and apostrophes for French)
        # Pattern: Keep alphanumeric, spaces, hyphens, and apostrophes
        query = re.sub(r'[^\w\s\'-]', ' ', query)

        # Step 3: Tokenize and remove stopwords
        tokens = query.split()

        # Filter stopwords
        stopwords = QueryProcessor.FRENCH_STOPWORDS
        if keep_question_words:
            # Remove question words from stopwords set
            stopwords = stopwords - {"quel", "quelle", "quels", "quelles", "comment", "pourquoi"}

        tokens = [t for t in tokens if t not in stopwords and len(t) > 1]

        # Step 4: Rejoin and normalize whitespace
        normalized = ' '.join(tokens)

        # Fallback: if normalized is empty, return original (avoid losing all context)
        if not normalized or len(normalized) < 2:
            logger.warning("query_normalization_too_aggressive",
                          original=original_query[:50],
                          normalized=normalized)
            return original_query

        # Log normalization
        if normalized != original_query:
            logger.debug("query_normalized",
                        original=original_query[:50],
                        normalized=normalized[:50],
                        tokens_removed=len(original_query.split()) - len(tokens))

        return normalized

    @staticmethod
    def expand_synonyms(query: str) -> List[str]:
        """
        Expand query with synonyms (future enhancement)

        Args:
            query: Normalized query

        Returns:
            List of query variations

        Example:
            >>> QueryProcessor.expand_synonyms("couleur volets")
            ['couleur volets', 'teinte volets', 'coloris volets']
        """
        # TODO: Implement synonym expansion
        # For now, return original query
        return [query]

    @staticmethod
    def extract_keywords(query: str, max_keywords: int = 5) -> str:
        """
        Extract key terms from long/complex queries for better BM25 matching

        Useful for narrative queries like:
        "Si j'ai une urgence de plomberie la nuit, qui dois-je appeler ?"
        -> "urgence plomberie nuit appeler"

        Args:
            query: Original query (can be long/narrative)
            max_keywords: Maximum number of keywords to keep

        Returns:
            Simplified query with only key terms

        Strategy:
        1. Normalize to remove stopwords
        2. Score tokens by:
           - Length (longer = more specific)
           - Position (later = more important in questions)
           - Capitalization (proper nouns)
        3. Keep top N scored terms
        """
        if not query or len(query.split()) <= max_keywords:
            return QueryProcessor.normalize(query)

        # Normalize first
        normalized = QueryProcessor.normalize(query)
        tokens = normalized.split()

        # If already short enough, return
        if len(tokens) <= max_keywords:
            return normalized

        # Score each token
        scored_tokens = []
        for i, token in enumerate(tokens):
            score = 0

            # Length score (longer = more specific)
            score += len(token) * 0.5

            # Position score (later = more important in French questions)
            score += (i / len(tokens)) * 3

            # Bonus for numbers (dates, phone numbers, etc.)
            if re.search(r'\d', token):
                score += 5

            scored_tokens.append((token, score))

        # Sort by score and take top N
        top_tokens = sorted(scored_tokens, key=lambda x: x[1], reverse=True)[:max_keywords]

        # Preserve original order
        top_tokens_ordered = sorted(top_tokens, key=lambda x: tokens.index(x[0]))

        result = ' '.join(t[0] for t in top_tokens_ordered)

        logger.debug("keywords_extracted",
                    original=query[:60],
                    keywords=result,
                    compression=f"{len(query.split())}->{len(result.split())}")

        return result

    @staticmethod
    def remove_accents(text: str) -> str:
        """
        Remove French accents (optional, use with caution)

        Args:
            text: Text with accents

        Returns:
            Text without accents

        Example:
            >>> QueryProcessor.remove_accents("règlement copropriété")
            'reglement copropriete'
        """
        import unicodedata
        nfd = unicodedata.normalize('NFD', text)
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
