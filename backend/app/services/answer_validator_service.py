"""
Answer Validator Service - Validation anti-hallucination des réponses RAG
Phase RAG World-Class - DisruptIQ SMA

Ce module valide que les réponses générées sont bien fondées sur les sources:
1. Vérifie que chaque fait mentionné existe dans les chunks
2. Détecte les montants/dates inventés
3. Vérifie la cohérence avec les entités extraites

Approche ultra-légère:
- Pas d'appel LLM supplémentaire
- Extraction regex des faits de la réponse
- Vérification de présence dans les sources

Author: Claude Code - RAG World-Class
Date: December 2024
"""

import re
import structlog
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.services.entity_extraction_service import (
    EntityExtractionService,
    EntityType,
    get_entity_extraction_service
)

logger = structlog.get_logger()


class ValidationStatus(Enum):
    """Statut de validation"""
    VALID = "valid"                    # Tous les faits vérifiés
    PARTIAL = "partial"                # Certains faits non vérifiés
    SUSPICIOUS = "suspicious"          # Faits potentiellement hallucines
    INVALID = "invalid"                # Faits contredits par sources


@dataclass
class FactCheck:
    """Résultat de vérification d'un fait"""
    fact_type: str                     # "amount", "date", "person", "claim"
    fact_value: str                    # Valeur du fait
    found_in_source: bool              # Trouvé dans les sources?
    source_match: Optional[str] = None # Texte source correspondant
    confidence: float = 0.0


@dataclass
class ValidationResult:
    """Résultat complet de validation"""
    status: ValidationStatus
    fact_checks: List[FactCheck]
    grounded_ratio: float              # % de faits vérifiés
    suspicious_facts: List[str]        # Faits potentiellement hallucines
    warnings: List[str]                # Avertissements
    recommendations: List[str]         # Suggestions d'amélioration

    @property
    def is_reliable(self) -> bool:
        return self.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL] and self.grounded_ratio >= 0.7


class AnswerValidatorService:
    """
    Service de validation des réponses RAG.

    Vérifie que les faits mentionnés dans la réponse existent
    dans les sources (chunks) fournis.
    """

    # Patterns pour extraire les faits de la réponse
    FACT_PATTERNS = {
        "amount": [
            # Montants avec contexte
            r'(\d{1,3}(?:[\s\u00a0]\d{3})*(?:[,\.]\d{1,2})?)\s*(?:€|EUR|euros?)',
            r'(?:montant|prix|coût|total|somme)\s*(?:de|:)?\s*(\d+(?:[,\.]\d{1,2})?)\s*(?:€|EUR|euros?)?',
        ],
        "date": [
            r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
            r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
        ],
        "person": [
            r'(M\.|Mme|Monsieur|Madame)\s+([A-ZÀ-Ü][a-zà-ü\-]+)',
        ],
        "lot": [
            r'(?:lot|appartement)\s+([A-Z]?\d+[A-Z]?)',
        ],
        "percentage": [
            r'(\d+(?:[,\.]\d+)?)\s*%',
        ],
    }

    def __init__(self):
        self._entity_service = get_entity_extraction_service()
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}

        for fact_type, patterns in self.FACT_PATTERNS.items():
            self._compiled_patterns[fact_type] = [
                re.compile(p, re.IGNORECASE | re.UNICODE)
                for p in patterns
            ]

    def validate_answer(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
        query: str = ""
    ) -> ValidationResult:
        """
        Valide qu'une réponse est bien fondée sur les sources.

        Args:
            answer: Réponse générée par le LLM
            sources: Liste des chunks sources utilisés
            query: Requête originale (optionnel, pour contexte)

        Returns:
            ValidationResult avec statut et détails
        """
        if not answer or not sources:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                fact_checks=[],
                grounded_ratio=0.0,
                suspicious_facts=[],
                warnings=["Réponse ou sources vides"],
                recommendations=["Vérifier que des sources ont été récupérées"]
            )

        # Combine all source texts
        source_text = self._combine_sources(sources)

        # Extract entities from sources for comparison
        source_entities = self._entity_service.extract_entities(source_text)

        # Extract facts from answer
        answer_facts = self._extract_facts(answer)

        # Check each fact against sources
        fact_checks = []
        for fact_type, fact_values in answer_facts.items():
            for value in fact_values:
                check = self._verify_fact(
                    fact_type=fact_type,
                    fact_value=value,
                    source_text=source_text,
                    source_entities=source_entities
                )
                fact_checks.append(check)

        # Calculate grounded ratio
        verified_count = sum(1 for fc in fact_checks if fc.found_in_source)
        total_count = len(fact_checks)
        grounded_ratio = verified_count / total_count if total_count > 0 else 1.0

        # Identify suspicious facts
        suspicious = [
            fc.fact_value for fc in fact_checks
            if not fc.found_in_source and fc.fact_type in ["amount", "date"]
        ]

        # Determine status
        if total_count == 0:
            status = ValidationStatus.VALID  # No specific facts to verify
        elif grounded_ratio >= 0.9:
            status = ValidationStatus.VALID
        elif grounded_ratio >= 0.7:
            status = ValidationStatus.PARTIAL
        elif grounded_ratio >= 0.3:
            status = ValidationStatus.SUSPICIOUS
        else:
            status = ValidationStatus.INVALID

        # Generate warnings and recommendations
        warnings = []
        recommendations = []

        if suspicious:
            warnings.append(f"Faits non vérifiés: {', '.join(suspicious[:3])}")
            recommendations.append("Vérifier ces informations dans les documents originaux")

        if grounded_ratio < 0.7:
            recommendations.append("Reformuler la question pour plus de précision")

        result = ValidationResult(
            status=status,
            fact_checks=fact_checks,
            grounded_ratio=grounded_ratio,
            suspicious_facts=suspicious,
            warnings=warnings,
            recommendations=recommendations
        )

        logger.info("answer_validated",
                   status=status.value,
                   facts_checked=total_count,
                   verified=verified_count,
                   grounded_ratio=f"{grounded_ratio:.0%}")

        return result

    def _combine_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Combine les textes de toutes les sources"""
        texts = []
        for source in sources:
            text = (
                source.get("text") or
                source.get("content") or
                source.get("chunk") or
                ""
            )
            if text:
                texts.append(text)
        return "\n\n".join(texts)

    def _extract_facts(self, answer: str) -> Dict[str, List[str]]:
        """Extrait les faits vérifiables de la réponse"""
        facts: Dict[str, List[str]] = {}

        for fact_type, patterns in self._compiled_patterns.items():
            values = set()
            for pattern in patterns:
                for match in pattern.finditer(answer):
                    # Get the full match or first group
                    value = match.group(0)
                    values.add(value)
            if values:
                facts[fact_type] = list(values)

        return facts

    def _verify_fact(
        self,
        fact_type: str,
        fact_value: str,
        source_text: str,
        source_entities
    ) -> FactCheck:
        """Vérifie qu'un fait existe dans les sources"""
        # Normalize the fact value for comparison
        normalized_fact = self._normalize_for_search(fact_value)

        # Method 1: Direct text search
        found_direct = normalized_fact.lower() in source_text.lower()

        # Method 2: Fuzzy search (for amounts)
        found_fuzzy = False
        source_match = None

        if fact_type == "amount" and not found_direct:
            # Extract just the number
            amount_match = re.search(r'(\d+(?:[,\.]\d+)?)', fact_value)
            if amount_match:
                amount_num = self._normalize_amount(amount_match.group(1))
                # Check against source amounts
                source_amounts = source_entities.get_all_amounts_normalized()
                for src_amount in source_amounts:
                    if self._amounts_match(amount_num, src_amount):
                        found_fuzzy = True
                        source_match = src_amount
                        break

        # Method 3: Entity matching for persons/dates
        if fact_type == "person" and not found_direct:
            # Extract name part
            name_parts = fact_value.split()
            if len(name_parts) >= 2:
                name = name_parts[-1].lower()
                found_fuzzy = name in source_text.lower()

        found = found_direct or found_fuzzy

        return FactCheck(
            fact_type=fact_type,
            fact_value=fact_value,
            found_in_source=found,
            source_match=source_match,
            confidence=0.95 if found_direct else (0.8 if found_fuzzy else 0.0)
        )

    def _normalize_for_search(self, value: str) -> str:
        """Normalise une valeur pour la recherche"""
        # Remove extra spaces
        value = re.sub(r'\s+', ' ', value.strip())
        return value

    def _normalize_amount(self, amount: str) -> str:
        """Normalise un montant pour comparaison"""
        # Remove spaces and convert comma to dot
        amount = re.sub(r'[\s\u00a0]', '', amount)
        amount = amount.replace(',', '.')
        return amount

    def _amounts_match(self, amount1: str, amount2: str, tolerance: float = 0.01) -> bool:
        """Compare deux montants avec tolérance"""
        try:
            v1 = float(amount1)
            v2 = float(amount2)
            if v1 == 0 or v2 == 0:
                return v1 == v2
            return abs(v1 - v2) / max(v1, v2) <= tolerance
        except ValueError:
            return amount1 == amount2

    def quick_check(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> Tuple[bool, float]:
        """
        Vérification rapide de la fiabilité.

        Returns:
            Tuple (is_reliable, grounded_ratio)
        """
        result = self.validate_answer(answer, sources)
        return result.is_reliable, result.grounded_ratio

    def get_reliability_score(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> float:
        """
        Retourne un score de fiabilité 0-1.

        Utile pour afficher un indicateur de confiance à l'utilisateur.
        """
        result = self.validate_answer(answer, sources)
        return result.grounded_ratio


# Singleton
_answer_validator: Optional[AnswerValidatorService] = None


def get_answer_validator() -> AnswerValidatorService:
    """Retourne l'instance singleton du Answer Validator"""
    global _answer_validator
    if _answer_validator is None:
        _answer_validator = AnswerValidatorService()
    return _answer_validator
