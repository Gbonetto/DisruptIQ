"""
Entity Extractor - Extract structured information from user input

Extracts:
- Person names (first name, last name)
- Groups (copropriétaires, chauffagistes, etc.)
- Locations (property names, addresses)
- Actions (send email, call, schedule)
"""

import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()


class PersonEntity(BaseModel):
    """Extracted person entity"""
    prenom: Optional[str] = None
    nom: Optional[str] = None
    full_name: str
    titles: List[str] = []  # Mme, M, Madame, Monsieur


class GroupEntity(BaseModel):
    """Extracted group entity"""
    type: str  # copropriétaire, chauffagiste, plombier, etc.
    modifier: Optional[str] = None  # tous, des mimosas, du parc, etc.
    location: Optional[str] = None  # Les Mimosas, Résidence du Parc


class ActionEntity(BaseModel):
    """Extracted action"""
    action_type: str  # send_email, call, schedule, request_quote
    target: Optional[str] = None  # who to contact
    subject: Optional[str] = None  # what it's about


class ExtractedEntities(BaseModel):
    """All extracted entities from user input"""
    persons: List[PersonEntity] = []
    groups: List[GroupEntity] = []
    actions: List[ActionEntity] = []
    locations: List[str] = []
    raw_text: str


class EntityExtractor:
    """
    Intelligent entity extraction from natural language

    Uses regex patterns and NLP-like rules to extract structured data
    """

    def __init__(self, state_manager=None):
        # French titles
        self.titles = ["madame", "monsieur", "mme", "m", "mr", "mlle", "mademoiselle"]

        # State manager for context resolution
        self.state_manager = state_manager

        # Group keywords
        self.group_keywords = {
            "copropriétaire": ["copropriétaire", "copropriétaires", "copro", "copros", "propriétaire", "propriétaires"],
            "chauffagiste": ["chauffagiste", "chauffagistes"],
            "plombier": ["plombier", "plombiers"],
            "électricien": ["électricien", "électriciens", "electricien", "electriciens"],
            "menuisier": ["menuisier", "menuisiers"],
            "peintre": ["peintre", "peintres"],
            "jardinier": ["jardinier", "jardiniers"],
            "serrurier": ["serrurier", "serruriers"],
            "maçon": ["maçon", "maçons", "macon", "macons"],
            "professionnel": ["professionnel", "professionnels"]
        }

        # Action keywords
        self.action_keywords = {
            "send_email": ["envoyer", "envoie", "envoyer un mail", "envoyer un email", "mail", "email", "écrire"],
            "call": ["appeler", "appelle", "téléphoner", "contacter par téléphone"],
            "schedule": ["programmer", "planifier", "organiser", "prévoir"],
            "request_quote": ["demander un devis", "devis", "demande de devis"]
        }

        # Known property names (could be loaded from database)
        self.known_properties = [
            "les mimosas", "mimosas",
            "résidence du parc", "du parc",
            "résidence harmonie", "harmonie",
            "villa des roses", "des roses",
            "le clos saint-martin", "saint-martin",
            "les palmiers", "palmiers"
        ]

        logger.info("entity_extractor_initialized")

    def extract(self, user_input: str) -> ExtractedEntities:
        """
        Extract all entities from user input

        Args:
            user_input: Natural language user input

        Returns:
            ExtractedEntities with all extracted information
        """
        logger.info("extracting_entities", input=user_input[:100])

        entities = ExtractedEntities(raw_text=user_input)

        # Check for contextual references FIRST
        text_lower = user_input.lower()
        has_reference = any(ref in text_lower for ref in ["contacte les", "contact les", "contacte ces", "envoie leur", "informe les", "avertir les", "préviens les"])

        # If we have a reference pronoun and no explicit names, try to resolve from context
        if has_reference and self.state_manager:
            entities = self._resolve_contextual_reference(user_input, entities)

        # Extract persons (if not already resolved from context)
        if not entities.persons:
            entities.persons = self._extract_persons(user_input)

        # Extract groups (if not already resolved from context)
        if not entities.groups:
            entities.groups = self._extract_groups(user_input)

        # Extract actions
        entities.actions = self._extract_actions(user_input)

        # Extract locations
        entities.locations = self._extract_locations(user_input)

        logger.info("entities_extracted",
                   persons=len(entities.persons),
                   groups=len(entities.groups),
                   actions=len(entities.actions),
                   locations=len(entities.locations))

        return entities

    def _extract_persons(self, text: str) -> List[PersonEntity]:
        """
        Extract person names from text

        Patterns:
        - "nathalie girard"
        - "Mme Girard"
        - "M. Olivier Bonnet"
        - "marie faure et sophie durant"
        """
        persons = []

        # Blacklist of words that are NOT names (pronouns and common verbs)
        blacklist = ["les", "ces", "leur", "lui", "elle", "ils", "elles", "nous", "vous",
                     "avertir", "informer", "contacter", "prévenir", "envoyer", "dire", "demander"]

        # Pattern 1: Title + Full Name (e.g., "Mme Nathalie Girard")
        title_pattern = r'\b(madame|monsieur|mme|m\.?|mr\.?|mlle)\s+([A-Z][a-zéèêëàâäôöûüç]+(?:\s+[A-Z][a-zéèêëàâäôöûüç]+)*)'
        for match in re.finditer(title_pattern, text, re.IGNORECASE):
            title = match.group(1).lower()
            full_name = match.group(2)
            persons.append(self._parse_person_name(full_name, [title]))

        # Pattern 2: Standalone capitalized names (e.g., "nathalie girard")
        # Look for "à/a [Name] [Name]" or names after prepositions
        # BUT exclude pronouns and verbs
        name_after_prep_pattern = r'\b(?:à|a|aux|de)\s+([a-z][a-zéèêëàâäôöûüç]+\s+[a-z][a-zéèêëàâäôöûüç]+)'
        for match in re.finditer(name_after_prep_pattern, text, re.IGNORECASE):
            full_name = match.group(1)

            # Skip if first word is in blacklist
            first_word = full_name.split()[0].lower()
            if first_word in blacklist:
                continue

            # Capitalize properly
            full_name = ' '.join(word.capitalize() for word in full_name.split())
            person = self._parse_person_name(full_name, [])
            if person and person not in persons:
                persons.append(person)

        # Pattern 3: "et" separator (e.g., "nathalie girard et olivier bonnet")
        if " et " in text.lower():
            # Split by "et" and try to extract names from each part
            parts = re.split(r'\s+et\s+', text, flags=re.IGNORECASE)
            for part in parts:
                # Try to find name pattern in each part
                name_pattern = r'\b([A-Z][a-zéèêëàâäôöûüç]+\s+[A-Z][a-zéèêëàâäôöûüç]+)\b'
                for match in re.finditer(name_pattern, part):
                    person = self._parse_person_name(match.group(1), [])
                    if person and person not in persons:
                        persons.append(person)

        return persons

    def _parse_person_name(self, full_name: str, titles: List[str]) -> Optional[PersonEntity]:
        """
        Parse a full name into first name and last name

        Assumes format: "Prenom Nom" or "Prenom Deuxieme-Prenom Nom"
        """
        parts = full_name.strip().split()

        if len(parts) < 2:
            # Need at least first and last name
            return None

        # Simple heuristic: Last word is nom, everything else is prenom
        nom = parts[-1]
        prenom = ' '.join(parts[:-1])

        return PersonEntity(
            prenom=prenom,
            nom=nom,
            full_name=full_name,
            titles=titles
        )

    def _extract_groups(self, text: str) -> List[GroupEntity]:
        """
        Extract group mentions (copropriétaires, chauffagistes, etc.)

        Patterns:
        - "copropriétaires des mimosas"
        - "tous les chauffagistes"
        - "les plombiers"
        """
        groups = []
        text_lower = text.lower()

        for group_type, keywords in self.group_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Found a group mention
                    modifier = None
                    location = None

                    # Look for modifiers
                    if "tous" in text_lower or "toutes" in text_lower:
                        modifier = "tous"

                    # Look for location context
                    for prop in self.known_properties:
                        if prop in text_lower:
                            location = prop
                            modifier = f"de {prop}" if not modifier else modifier
                            break

                    # Check for "des [location]" pattern
                    location_pattern = rf'{keyword}\s+(?:de |des |du |de la )([a-zéèêëàâäôöûüç\s]+)'
                    match = re.search(location_pattern, text_lower)
                    if match:
                        location = match.group(1).strip()
                        modifier = f"de {location}"

                    group = GroupEntity(
                        type=group_type,
                        modifier=modifier,
                        location=location
                    )

                    if group not in groups:
                        groups.append(group)

                    break  # Found this group type, move to next

        return groups

    def _extract_actions(self, text: str) -> List[ActionEntity]:
        """
        Extract action intents from text

        Examples:
        - "envoie un mail" → send_email
        - "demande un devis" → request_quote
        """
        actions = []
        text_lower = text.lower()

        for action_type, keywords in self.action_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Extract subject if possible
                    subject = self._extract_action_subject(text, keyword)

                    actions.append(ActionEntity(
                        action_type=action_type,
                        subject=subject
                    ))
                    break

        return actions

    def _extract_action_subject(self, text: str, action_keyword: str) -> Optional[str]:
        """
        Extract what the action is about

        E.g., "envoie mail pour problème de chauffage" → "problème de chauffage"
        """
        text_lower = text.lower()

        # Look for "pour [subject]" pattern after action keyword
        pour_pattern = rf'{action_keyword}.*?pour\s+(.+?)(?:\.|$|,)'
        match = re.search(pour_pattern, text_lower)
        if match:
            return match.group(1).strip()

        # Look for "concernant [subject]" pattern
        concernant_pattern = rf'{action_keyword}.*?concernant\s+(.+?)(?:\.|$|,)'
        match = re.search(concernant_pattern, text_lower)
        if match:
            return match.group(1).strip()

        return None

    def _extract_locations(self, text: str) -> List[str]:
        """Extract property/location names from text"""
        locations = []
        text_lower = text.lower()

        for prop in self.known_properties:
            if prop in text_lower:
                # Capitalize properly
                prop_capitalized = ' '.join(word.capitalize() for word in prop.split())
                if prop_capitalized not in locations:
                    locations.append(prop_capitalized)

        return locations

    def to_sql_conditions(self, entities: ExtractedEntities) -> Dict[str, Any]:
        """
        Convert extracted entities to SQL query conditions

        Returns dict with table-specific conditions for query building
        """
        conditions = {
            "coproprietaires": [],
            "professionnels": [],
            "coproprietes": []
        }

        # Person conditions
        for person in entities.persons:
            if person.prenom and person.nom:
                conditions["coproprietaires"].append({
                    "type": "person",
                    "prenom": person.prenom,
                    "nom": person.nom
                })

        # Group conditions
        for group in entities.groups:
            if group.type in ["chauffagiste", "plombier", "électricien", "menuisier", "peintre", "jardinier", "serrurier", "maçon"]:
                conditions["professionnels"].append({
                    "type": "profession",
                    "category": group.type
                })
            elif group.type == "copropriétaire":
                cond = {"type": "group"}
                if group.location:
                    cond["copropriete"] = group.location
                if group.modifier == "tous":
                    cond["all"] = True
                conditions["coproprietaires"].append(cond)

        # Location conditions
        for location in entities.locations:
            conditions["coproprietes"].append({
                "type": "location",
                "name": location
            })

        return conditions

    def _resolve_contextual_reference(self, user_input: str, entities: ExtractedEntities) -> ExtractedEntities:
        """
        Resolve contextual references like 'les', 'ces', 'leur' using conversation state

        Args:
            user_input: User input with reference pronoun
            entities: Partially extracted entities

        Returns:
            Entities enriched with context-resolved persons/groups
        """
        if not self.state_manager:
            logger.warning("contextual_reference_detected_but_no_state_manager")
            return entities

        state = self.state_manager.get_state()

        # Check if we have last_query_entities
        if not state.last_query_entities:
            logger.info("contextual_reference_detected_but_no_last_query")
            return entities

        logger.info("resolving_contextual_reference",
                   query_type=state.last_query_type,
                   entities_count=len(state.last_query_entities))

        # Resolve based on query type
        if state.last_query_type == "people":
            # Convert query results to PersonEntity
            for entity_dict in state.last_query_entities:
                if "nom" in entity_dict and "prenom" in entity_dict:
                    person = PersonEntity(
                        prenom=entity_dict.get("prenom"),
                        nom=entity_dict.get("nom"),
                        full_name=f"{entity_dict.get('prenom')} {entity_dict.get('nom')}",
                        titles=[]
                    )
                    entities.persons.append(person)

            logger.info("resolved_people_from_context", count=len(entities.persons))

        elif state.last_query_type == "professionals":
            # Create a group entity for professionals
            # Try to infer profession from context
            profession = state.business_context.get("profession_requested", "professionnel")
            group = GroupEntity(
                type=profession,
                modifier="ces",
                location=None
            )
            entities.groups.append(group)

            logger.info("resolved_professionals_from_context", profession=profession)

        return entities
