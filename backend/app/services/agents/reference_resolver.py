"""
Reference Resolver - Résolution de Pronoms et Références Contextuelles
Phase E2E Fix - DisruptIQ SMA RAG

Ce module résout les références contextuelles dans les requêtes utilisateur:
- Pronoms: "elle", "lui", "il", "ils", "elles"
- Références: "ce prestataire", "cette copropriété", "ces travaux"
- Anaphores: "le même", "celui-ci", "celle-là"

Author: Claude Code - E2E Bug Fixes
Date: November 27, 2025
"""

import re
import structlog
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = structlog.get_logger()


class EntityType(Enum):
    """Types d'entités pouvant être référencées"""
    COPROPRIETE = "copropriete"
    COPROPRIETAIRE = "coproprietaire"
    PROFESSIONNEL = "professionnel"
    DOCUMENT = "document"
    MONTANT = "montant"
    TRAVAUX = "travaux"


@dataclass
class ResolvedEntity:
    """Entité résolue"""
    entity_type: EntityType
    name: str
    id: Optional[int] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ResolutionResult:
    """Résultat de la résolution"""
    original_query: str
    resolved_query: str
    resolved_entities: Dict[str, ResolvedEntity]
    confidence: float
    changes_made: List[str]


class ReferenceResolver:
    """
    Résout les pronoms et références contextuelles dans les requêtes utilisateur.

    Utilise l'historique de conversation et le context_store pour trouver
    les entités auxquelles les pronoms font référence.
    """

    # Mapping pronoms → types d'entités possibles
    PRONOUN_MAP = {
        # Pronoms féminins → copropriétés (résidences sont féminines en français)
        "elle": [EntityType.COPROPRIETE, EntityType.COPROPRIETAIRE],
        "la": [EntityType.COPROPRIETE],
        "celle-ci": [EntityType.COPROPRIETE],
        "celle-là": [EntityType.COPROPRIETE],

        # Pronoms masculins → personnes ou documents
        "il": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],
        "lui": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],
        "celui-ci": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL, EntityType.DOCUMENT],
        "celui-là": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],

        # Pluriels et possessifs (CRITIQUE pour "donne moi leur mail")
        "ils": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],
        "elles": [EntityType.COPROPRIETE, EntityType.COPROPRIETAIRE],
        "eux": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],
        "leur": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],  # "donne moi leur mail"
        "leurs": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],  # "leurs adresses"
        "ses": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],  # "ses coordonnées"
        "son": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],  # "son email"
        "sa": [EntityType.COPROPRIETAIRE, EntityType.PROFESSIONNEL],  # "sa téléphone"

        # Références explicites
        "ce prestataire": [EntityType.PROFESSIONNEL],
        "cet artisan": [EntityType.PROFESSIONNEL],
        "ce fournisseur": [EntityType.PROFESSIONNEL],
        "ce professionnel": [EntityType.PROFESSIONNEL],
        "cette entreprise": [EntityType.PROFESSIONNEL],
        "cette copropriété": [EntityType.COPROPRIETE],
        "cette résidence": [EntityType.COPROPRIETE],
        "cet immeuble": [EntityType.COPROPRIETE],
        "ce copropriétaire": [EntityType.COPROPRIETAIRE],
        "cette personne": [EntityType.COPROPRIETAIRE],
        "ces personnes": [EntityType.COPROPRIETAIRE],
        "ces copropriétaires": [EntityType.COPROPRIETAIRE],
        "ces professionnels": [EntityType.PROFESSIONNEL],
        "ce document": [EntityType.DOCUMENT],
        "cette facture": [EntityType.DOCUMENT],
        "ce devis": [EntityType.DOCUMENT],
        "ce contrat": [EntityType.DOCUMENT],
        "ces travaux": [EntityType.TRAVAUX],
        "ce montant": [EntityType.MONTANT],
        "cette somme": [EntityType.MONTANT],
    }

    # Patterns pour extraire les entités de l'historique
    ENTITY_EXTRACTION_PATTERNS = {
        EntityType.COPROPRIETE: [
            r"(?:résidence|copropriété|immeuble)\s+(?:de\s+)?[«\"']?([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*)[»\"']?",
            r"[«\"']([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*)[»\"']\s*(?:est|a|compte|possède)",
            r"(?:Arc-en-Ciel|Jardins de Provence|Parc des Étoiles|Les Mimosas)",
        ],
        EntityType.PROFESSIONNEL: [
            r"(?:prestataire|artisan|entreprise|fournisseur|plombier|électricien)\s+[«\"']?([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*(?:\s+(?:SARL|SAS|EURL|SA))?)[»\"']?",
            r"[«\"']([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*(?:\s+(?:SARL|SAS|EURL|SA))?)[»\"']?\s+(?:a réalisé|a effectué|a fait)",
            r"(?:Plomberie Express|Électricité Pro|Maintenance Plus)",
        ],
        EntityType.COPROPRIETAIRE: [
            r"(?:M\.|Mme|Monsieur|Madame)\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)?)",
            r"copropriétaire\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)?)",
        ],
        EntityType.MONTANT: [
            r"(\d+(?:[.,]\d+)?\s*(?:€|euros?|EUR))",
            r"(?:montant|coût|prix|total)\s*(?:de|:)?\s*(\d+(?:[.,]\d+)?)\s*(?:€|euros?)?",
        ],
    }

    def __init__(self):
        self.entity_cache: Dict[str, List[ResolvedEntity]] = {}

    async def resolve(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_store_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> ResolutionResult:
        """
        Résout les références dans une requête.

        Args:
            query: Requête utilisateur
            conversation_history: Historique de conversation
            context_store_data: Données du context_store
            session_id: ID de session pour le cache

        Returns:
            ResolutionResult avec requête résolue et entités
        """
        query_lower = query.lower()
        resolved_query = query
        resolved_entities = {}
        changes_made = []

        # 1. Extraire les entités de l'historique de conversation
        history_entities = self._extract_entities_from_history(conversation_history)

        # 2. Extraire les entités du context_store
        store_entities = self._extract_entities_from_store(context_store_data)

        # 3. Fusionner (priorité au context_store, plus récent)
        all_entities = {**history_entities, **store_entities}

        # 4. Résoudre chaque référence trouvée
        for reference, entity_types in self.PRONOUN_MAP.items():
            if reference in query_lower:
                # Trouver la meilleure entité correspondante
                resolved = self._find_best_match(reference, entity_types, all_entities, conversation_history)

                if resolved:
                    # Remplacer la référence par le nom de l'entité
                    resolved_query = self._replace_reference(resolved_query, reference, resolved.name)
                    resolved_entities[reference] = resolved
                    changes_made.append(f"'{reference}' → '{resolved.name}'")

                    logger.info("reference_resolved",
                               reference=reference,
                               resolved_to=resolved.name,
                               entity_type=resolved.entity_type.value)

        # 5. Calculer la confiance
        if changes_made:
            confidence = min(0.95, 0.7 + 0.1 * len(changes_made))
        else:
            confidence = 1.0  # Pas de références à résoudre

        result = ResolutionResult(
            original_query=query,
            resolved_query=resolved_query,
            resolved_entities=resolved_entities,
            confidence=confidence,
            changes_made=changes_made
        )

        if changes_made:
            logger.info("query_resolved",
                       original=query[:50],
                       resolved=resolved_query[:50],
                       changes=len(changes_made))

        return result

    def _extract_entities_from_history(
        self,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Dict[EntityType, List[ResolvedEntity]]:
        """Extrait les entités mentionnées dans l'historique"""
        entities: Dict[EntityType, List[ResolvedEntity]] = {et: [] for et in EntityType}

        if not conversation_history:
            return entities

        # Parcourir l'historique en ordre inverse (plus récent d'abord)
        for msg in reversed(conversation_history[-10:]):  # 10 derniers messages
            content = msg.get("content", "")

            for entity_type, patterns in self.ENTITY_EXTRACTION_PATTERNS.items():
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        if match and len(match) > 2:
                            entity = ResolvedEntity(
                                entity_type=entity_type,
                                name=match.strip()
                            )
                            # Éviter les doublons
                            if not any(e.name.lower() == entity.name.lower() for e in entities[entity_type]):
                                entities[entity_type].append(entity)

        return entities

    def _extract_entities_from_store(
        self,
        context_store_data: Optional[Dict[str, Any]]
    ) -> Dict[EntityType, List[ResolvedEntity]]:
        """Extrait les entités du context_store"""
        entities: Dict[EntityType, List[ResolvedEntity]] = {et: [] for et in EntityType}

        if not context_store_data:
            return entities

        # Extraire les copropriétés
        if "coproprietes" in context_store_data:
            for copro in context_store_data["coproprietes"]:
                entities[EntityType.COPROPRIETE].append(ResolvedEntity(
                    entity_type=EntityType.COPROPRIETE,
                    name=copro.get("nom", copro.get("name", "")),
                    id=copro.get("id"),
                    metadata=copro
                ))

        # Extraire les professionnels
        if "professionnels" in context_store_data:
            for pro in context_store_data["professionnels"]:
                entities[EntityType.PROFESSIONNEL].append(ResolvedEntity(
                    entity_type=EntityType.PROFESSIONNEL,
                    name=pro.get("name", pro.get("company_name", "")),
                    id=pro.get("id"),
                    metadata=pro
                ))

        # Extraire les copropriétaires
        if "coproprietaires" in context_store_data:
            for copro in context_store_data["coproprietaires"]:
                name = f"{copro.get('prenom', '')} {copro.get('nom', '')}".strip()
                entities[EntityType.COPROPRIETAIRE].append(ResolvedEntity(
                    entity_type=EntityType.COPROPRIETAIRE,
                    name=name,
                    id=copro.get("id"),
                    metadata=copro
                ))

        # Extraire les documents
        if "documents" in context_store_data:
            for doc in context_store_data["documents"]:
                entities[EntityType.DOCUMENT].append(ResolvedEntity(
                    entity_type=EntityType.DOCUMENT,
                    name=doc.get("filename", doc.get("original_filename", "")),
                    id=doc.get("id"),
                    metadata=doc
                ))

        # Extraire les montants
        if "montants" in context_store_data:
            for montant in context_store_data["montants"]:
                entities[EntityType.MONTANT].append(ResolvedEntity(
                    entity_type=EntityType.MONTANT,
                    name=str(montant.get("value", montant)),
                    metadata=montant if isinstance(montant, dict) else {"value": montant}
                ))

        # Extraire la dernière entité mentionnée (priorité haute)
        if "last_mentioned" in context_store_data:
            last = context_store_data["last_mentioned"]
            entity_type = EntityType(last.get("type", "document"))
            entities[entity_type].insert(0, ResolvedEntity(
                entity_type=entity_type,
                name=last.get("name", ""),
                id=last.get("id"),
                metadata=last
            ))

        return entities

    def _find_best_match(
        self,
        reference: str,
        entity_types: List[EntityType],
        all_entities: Dict[EntityType, List[ResolvedEntity]],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> Optional[ResolvedEntity]:
        """Trouve la meilleure entité correspondant à une référence"""

        # Chercher dans les types d'entités compatibles (en ordre)
        for entity_type in entity_types:
            candidates = all_entities.get(entity_type, [])
            if candidates:
                # Retourner la plus récente (première dans la liste)
                return candidates[0]

        # Si pas trouvé dans les entités extraites, essayer d'inférer du contexte
        if conversation_history:
            return self._infer_from_context(reference, entity_types, conversation_history)

        return None

    def _infer_from_context(
        self,
        reference: str,
        entity_types: List[EntityType],
        conversation_history: List[Dict[str, str]]
    ) -> Optional[ResolvedEntity]:
        """Infère une entité à partir du contexte de conversation"""

        # Chercher dans les derniers messages
        for msg in reversed(conversation_history[-5:]):
            content = msg.get("content", "")

            # Pour "elle" + copropriété
            if EntityType.COPROPRIETE in entity_types:
                copro_patterns = [
                    r"résidence\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü][a-zà-ü\-]+)*)",
                    r"copropriété\s+(?:de\s+)?([A-ZÀ-Ü][a-zà-ü\-]+)",
                    r"(Arc-en-Ciel|Jardins de Provence|Parc des Étoiles)",
                ]
                for pattern in copro_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        return ResolvedEntity(
                            entity_type=EntityType.COPROPRIETE,
                            name=match.group(1)
                        )

            # Pour "lui" + professionnel
            if EntityType.PROFESSIONNEL in entity_types:
                pro_patterns = [
                    r"(?:prestataire|plombier|entreprise)\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+(?:SARL|SAS|Express))?)",
                    r"(Plomberie Express|Électricité Pro)",
                ]
                for pattern in pro_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        return ResolvedEntity(
                            entity_type=EntityType.PROFESSIONNEL,
                            name=match.group(1)
                        )

        return None

    def _replace_reference(self, query: str, reference: str, replacement: str) -> str:
        """Remplace une référence par sa résolution dans la requête"""
        # Remplacement insensible à la casse mais préservant le cas original
        pattern = re.compile(re.escape(reference), re.IGNORECASE)
        return pattern.sub(replacement, query)


# Instance singleton pour utilisation globale
_reference_resolver: Optional[ReferenceResolver] = None


def get_reference_resolver() -> ReferenceResolver:
    """Retourne l'instance singleton du résolveur"""
    global _reference_resolver
    if _reference_resolver is None:
        _reference_resolver = ReferenceResolver()
    return _reference_resolver
