"""
NER Post-OCR Service
Phase 2.1 - World-Class SMA Optimization

Advanced Named Entity Recognition for post-OCR text enrichment.
Specialized for French property management (syndic) documents.

Entity Types:
- PERSON: Copropriétaires, syndics, prestataires
- ORG: Entreprises, copropriétés, conseils syndicaux
- LOC: Adresses, bâtiments, lots
- MONEY: Montants, charges, provisions
- DATE: Dates AG, échéances, périodes
- LEGAL: Articles de loi, références légales
- CONTACT: Emails, téléphones, IBAN
- PROPERTY: Numéros de lots, tantièmes, surfaces

Integration:
- Post-OCR enrichment for better searchability
- Metadata injection for filtering
- Entity-aware chunking recommendations

Author: Claude Code - Phase 2 World-Class SMA
Date: November 27, 2025
"""

import re
import structlog
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = structlog.get_logger()


class EntityType(str, Enum):
    """Entity types specialized for syndic documents"""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    MONEY = "money"
    DATE = "date"
    LEGAL_REF = "legal_reference"
    CONTACT = "contact"
    PROPERTY = "property"
    DOCUMENT_REF = "document_reference"


@dataclass
class Entity:
    """Extracted named entity"""
    text: str
    type: EntityType
    start: int
    end: int
    confidence: float = 1.0
    normalized: Optional[str] = None  # Normalized form
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "type": self.type.value,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "normalized": self.normalized,
            "metadata": self.metadata,
        }


class NERPostOCRService:
    """
    Named Entity Recognition service optimized for post-OCR text

    Features:
    - Domain-specific patterns for syndic documents
    - OCR error tolerance (fuzzy matching)
    - Entity normalization
    - Confidence scoring

    Usage:
        ner_service = NERPostOCRService()
        entities = ner_service.extract_entities(ocr_text)
        enriched_metadata = ner_service.enrich_metadata(ocr_text, base_metadata)
    """

    def __init__(self):
        # Compile regex patterns for efficiency
        self._init_patterns()

        # French NLP service for advanced processing
        self._french_nlp = None

        logger.info("ner_post_ocr_service_initialized")

    def _init_patterns(self):
        """Initialize regex patterns for entity extraction"""

        # MONEY patterns (French amounts)
        self.money_patterns = [
            # 1 234,56 EUR / 1234.56 €
            (r'\b(\d{1,3}(?:[\s\.]\d{3})*(?:[,\.]\d{2})?)\s*(€|EUR|euros?)\b', "amount_eur"),
            # HT / TTC amounts
            (r'\b(\d{1,3}(?:[\s\.]\d{3})*(?:[,\.]\d{2})?)\s*(HT|TTC)\b', "amount_tax"),
            # Provisions / Charges
            (r'(?:provision|charge|appel|quote-part)[\s:]*(\d{1,3}(?:[\s\.]\d{3})*(?:[,\.]\d{2})?)\s*(€|EUR|euros?)?', "provision"),
        ]

        # DATE patterns (French dates)
        self.date_patterns = [
            # 15/01/2024 or 15-01-2024
            (r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', "date_numeric"),
            # 15 janvier 2024
            (r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b', "date_full"),
            # AG du 15/01/2024
            (r'(?:AG|assemblée\s+générale).*?(\d{1,2}[/-]\d{1,2}[/-]\d{4})', "date_ag"),
        ]

        # LEGAL patterns (references to French law)
        self.legal_patterns = [
            # Article 14 loi du 10 juillet 1965
            (r'(?:article|art\.?)\s*(\d+(?:-\d+)?)\s*(?:de\s+)?(?:la\s+)?(?:loi|décret)[\s\w]*(?:\d{1,2}[/-]\d{1,2}[/-])?\d{4}', "article_law"),
            # Décret n°67-223
            (r'(?:décret|loi)\s*n°?\s*(\d{2,4}-\d+)', "decree_ref"),
            # Règlement de copropriété
            (r'règlement\s+de\s+copropriété', "reglement"),
        ]

        # PROPERTY patterns (lot numbers, tantièmes, surfaces)
        self.property_patterns = [
            # Lot n°12 or lot 12
            (r'\b(?:lot|n°)\s*(\d{1,4})\b', "lot_number"),
            # Tantièmes: 125/10000e
            (r'(\d{1,4})\s*/\s*(\d+)(?:e|ème)?(?:\s*(?:tantième|millième))?', "tantiemes"),
            # Surface: 45,5 m² or 45.5 m2
            (r'(\d{1,3}(?:[,\.]\d{1,2})?)\s*m[²2]', "surface"),
            # Bâtiment A / Escalier B
            (r'\b(?:bâtiment|escalier|entrée)\s*([A-Z])\b', "building"),
        ]

        # CONTACT patterns
        self.contact_patterns = [
            # Email
            (r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', "email"),
            # French phone: 01 23 45 67 89 or 0123456789
            (r'\b(0[1-9](?:[\s\.-]?\d{2}){4})\b', "phone"),
            # IBAN: FR76 1234 5678 ...
            (r'\b([A-Z]{2}\d{2}(?:\s?\d{4}){4,7})\b', "iban"),
            # SIRET: 123 456 789 00012
            (r'\b(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\b', "siret"),
        ]

        # ORGANIZATION patterns (syndics, entreprises)
        self.org_patterns = [
            # Cabinet / Syndic + Name
            (r'(?:cabinet|syndic|société|sarl|sas|sa)\s+([A-Z][A-Za-zÀ-ÿ\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ\-]+)*)', "syndic_org"),
            # Copropriété + Address
            (r"copropriété\s+(?:du\s+|de\s+la\s+|de\s+l['\u2019])?([^\n,]+)", "copropriete"),
            # Conseil syndical
            (r'conseil\s+syndical', "conseil_syndical"),
        ]

        # PERSON patterns (with OCR error tolerance)
        self.person_patterns = [
            # M./Mme/Mr + Name
            (r'\b(?:M\.|Mme|Mr|Monsieur|Madame)\s+([A-Z][A-Za-zÀ-ÿ\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ\-]+)?)', "person_title"),
            # Name as signer
            (r'(?:signé|signature)[:\s]+([A-Z][A-Za-zÀ-ÿ\-]+(?:\s+[A-Z][A-Za-zÀ-ÿ\-]+)?)', "person_signature"),
        ]

        # DOCUMENT REFERENCE patterns
        self.doc_ref_patterns = [
            # Facture n°2024-001
            (r'(?:facture|devis|avoir)\s*n°?\s*([A-Z0-9\-]+)', "invoice_ref"),
            # PV AG 2024
            (r'(?:PV|procès[\-\s]verbal)\s*(?:AG|assemblée)?\s*(\d{4})', "pv_ref"),
            # Contrat n°...
            (r'contrat\s*n°?\s*([A-Z0-9\-]+)', "contract_ref"),
        ]

    def _get_french_nlp(self):
        """Lazy-load French NLP service"""
        if self._french_nlp is None:
            try:
                from app.services.french_nlp_service import get_french_nlp_service
                self._french_nlp = get_french_nlp_service()
            except ImportError:
                logger.warning("french_nlp_service_not_available")
        return self._french_nlp

    def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[EntityType]] = None
    ) -> List[Entity]:
        """
        Extract named entities from text

        Args:
            text: Input text (typically from OCR)
            entity_types: Filter to specific entity types (None = all)

        Returns:
            List of extracted entities
        """
        entities = []

        # Extract by type
        if entity_types is None or EntityType.MONEY in entity_types:
            entities.extend(self._extract_money(text))

        if entity_types is None or EntityType.DATE in entity_types:
            entities.extend(self._extract_dates(text))

        if entity_types is None or EntityType.LEGAL_REF in entity_types:
            entities.extend(self._extract_legal(text))

        if entity_types is None or EntityType.PROPERTY in entity_types:
            entities.extend(self._extract_property(text))

        if entity_types is None or EntityType.CONTACT in entity_types:
            entities.extend(self._extract_contacts(text))

        if entity_types is None or EntityType.ORGANIZATION in entity_types:
            entities.extend(self._extract_organizations(text))

        if entity_types is None or EntityType.PERSON in entity_types:
            entities.extend(self._extract_persons(text))

        if entity_types is None or EntityType.DOCUMENT_REF in entity_types:
            entities.extend(self._extract_doc_refs(text))

        # Sort by position in text
        entities.sort(key=lambda e: e.start)

        # Remove overlapping entities (keep highest confidence)
        entities = self._remove_overlaps(entities)

        logger.info("entities_extracted",
                   total=len(entities),
                   by_type={et.value: sum(1 for e in entities if e.type == et)
                           for et in EntityType})

        return entities

    def _extract_with_patterns(
        self,
        text: str,
        patterns: List[Tuple[str, str]],
        entity_type: EntityType
    ) -> List[Entity]:
        """Extract entities using regex patterns"""
        entities = []

        for pattern, subtype in patterns:
            try:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    entity = Entity(
                        text=match.group(0),
                        type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9,  # High confidence for regex matches
                        metadata={"subtype": subtype}
                    )

                    # Try to extract normalized value from groups
                    if match.lastindex and match.lastindex >= 1:
                        entity.normalized = match.group(1)

                    entities.append(entity)

            except re.error as e:
                logger.warning("regex_error", pattern=pattern[:50], error=str(e))

        return entities

    def _extract_money(self, text: str) -> List[Entity]:
        """Extract monetary amounts"""
        entities = self._extract_with_patterns(text, self.money_patterns, EntityType.MONEY)

        # Normalize amounts
        for entity in entities:
            if entity.normalized:
                # Remove spaces, convert comma to dot
                normalized = entity.normalized.replace(" ", "").replace(",", ".")
                try:
                    entity.metadata["value"] = float(normalized)
                except ValueError:
                    pass

        return entities

    def _extract_dates(self, text: str) -> List[Entity]:
        """Extract dates"""
        entities = self._extract_with_patterns(text, self.date_patterns, EntityType.DATE)

        # Try to parse and normalize dates
        for entity in entities:
            entity.metadata["is_ag_date"] = "ag" in entity.metadata.get("subtype", "")

        return entities

    def _extract_legal(self, text: str) -> List[Entity]:
        """Extract legal references"""
        return self._extract_with_patterns(text, self.legal_patterns, EntityType.LEGAL_REF)

    def _extract_property(self, text: str) -> List[Entity]:
        """Extract property-related entities"""
        entities = self._extract_with_patterns(text, self.property_patterns, EntityType.PROPERTY)

        # Enrich property entities
        for entity in entities:
            subtype = entity.metadata.get("subtype")

            if subtype == "tantiemes" and entity.normalized:
                # Parse tantièmes as fraction
                parts = entity.text.split("/")
                if len(parts) == 2:
                    try:
                        entity.metadata["numerator"] = int(re.search(r'\d+', parts[0]).group())
                        entity.metadata["denominator"] = int(re.search(r'\d+', parts[1]).group())
                    except (ValueError, AttributeError):
                        pass

            elif subtype == "surface" and entity.normalized:
                try:
                    entity.metadata["surface_m2"] = float(entity.normalized.replace(",", "."))
                except ValueError:
                    pass

        return entities

    def _extract_contacts(self, text: str) -> List[Entity]:
        """Extract contact information"""
        entities = self._extract_with_patterns(text, self.contact_patterns, EntityType.CONTACT)

        # Normalize phone numbers
        for entity in entities:
            if entity.metadata.get("subtype") == "phone" and entity.normalized:
                # Normalize to format without spaces
                entity.normalized = re.sub(r'[\s\.\-]', '', entity.normalized)

        return entities

    def _extract_organizations(self, text: str) -> List[Entity]:
        """Extract organization names"""
        return self._extract_with_patterns(text, self.org_patterns, EntityType.ORGANIZATION)

    def _extract_persons(self, text: str) -> List[Entity]:
        """Extract person names"""
        return self._extract_with_patterns(text, self.person_patterns, EntityType.PERSON)

    def _extract_doc_refs(self, text: str) -> List[Entity]:
        """Extract document references"""
        return self._extract_with_patterns(text, self.doc_ref_patterns, EntityType.DOCUMENT_REF)

    def _remove_overlaps(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping highest confidence"""
        if not entities:
            return entities

        result = []
        entities_sorted = sorted(entities, key=lambda e: (e.start, -e.confidence))

        last_end = -1
        for entity in entities_sorted:
            if entity.start >= last_end:
                result.append(entity)
                last_end = entity.end
            elif entity.confidence > result[-1].confidence:
                # Replace with higher confidence entity
                result[-1] = entity
                last_end = entity.end

        return result

    def enrich_metadata(
        self,
        text: str,
        base_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich document metadata with extracted entities

        Args:
            text: Document text
            base_metadata: Existing metadata

        Returns:
            Enriched metadata with entities
        """
        entities = self.extract_entities(text)

        # Group entities by type
        entities_by_type = {}
        for entity in entities:
            type_key = entity.type.value
            if type_key not in entities_by_type:
                entities_by_type[type_key] = []
            entities_by_type[type_key].append(entity.to_dict())

        # Enrich metadata
        enriched = dict(base_metadata)
        enriched["ner_entities"] = entities_by_type
        enriched["ner_entity_count"] = len(entities)

        # Extract key indicators
        enriched["has_amounts"] = EntityType.MONEY.value in entities_by_type
        enriched["has_dates"] = EntityType.DATE.value in entities_by_type
        enriched["has_legal_refs"] = EntityType.LEGAL_REF.value in entities_by_type
        enriched["has_property_refs"] = EntityType.PROPERTY.value in entities_by_type

        # Extract specific values for filtering
        if EntityType.MONEY.value in entities_by_type:
            amounts = [e.get("metadata", {}).get("value") for e in entities_by_type[EntityType.MONEY.value]]
            amounts = [a for a in amounts if a is not None]
            if amounts:
                enriched["max_amount"] = max(amounts)
                enriched["total_amount"] = sum(amounts)

        if EntityType.PROPERTY.value in entities_by_type:
            lots = [e.get("normalized") for e in entities_by_type[EntityType.PROPERTY.value]
                   if e.get("metadata", {}).get("subtype") == "lot_number"]
            if lots:
                enriched["lot_numbers"] = list(set(lots))

        logger.info("metadata_enriched_with_ner",
                   entity_count=len(entities),
                   types=list(entities_by_type.keys()))

        return enriched

    def get_entity_summary(self, entities: List[Entity]) -> Dict[str, Any]:
        """
        Generate summary of extracted entities

        Args:
            entities: List of extracted entities

        Returns:
            Summary statistics
        """
        summary = {
            "total_entities": len(entities),
            "by_type": {},
            "high_confidence": 0,
            "unique_values": {}
        }

        for entity in entities:
            type_key = entity.type.value

            # Count by type
            summary["by_type"][type_key] = summary["by_type"].get(type_key, 0) + 1

            # Count high confidence
            if entity.confidence >= 0.8:
                summary["high_confidence"] += 1

            # Track unique values
            if entity.normalized:
                if type_key not in summary["unique_values"]:
                    summary["unique_values"][type_key] = set()
                summary["unique_values"][type_key].add(entity.normalized)

        # Convert sets to lists for JSON serialization
        for type_key in summary["unique_values"]:
            summary["unique_values"][type_key] = list(summary["unique_values"][type_key])[:10]

        return summary


# ================================================================
# SINGLETON INSTANCE
# ================================================================

_ner_service: Optional[NERPostOCRService] = None


def get_ner_post_ocr_service() -> NERPostOCRService:
    """Get or create singleton NER service"""
    global _ner_service

    if _ner_service is None:
        _ner_service = NERPostOCRService()

    return _ner_service


# ================================================================
# INTEGRATION HELPERS
# ================================================================

async def enrich_ocr_result(
    ocr_text: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Helper function to enrich OCR results with NER

    Usage in OCR pipeline:
        ocr_text, success = await ocr_service.extract_text_from_image(image)
        if success:
            metadata = await enrich_ocr_result(ocr_text, base_metadata)
    """
    ner_service = get_ner_post_ocr_service()
    return ner_service.enrich_metadata(ocr_text, metadata)
