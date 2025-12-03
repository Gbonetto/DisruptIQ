"""
Agent de génération de checklists d'urgence pour syndics.

Approche simplifiée "Conseiller" :
- Détecte le type d'urgence dans la requête utilisateur
- Retourne un template de checklist professionnel
- Utilise le LLM en fallback pour les urgences non couvertes
- NE déclenche PAS d'envoi d'emails ou de workflows automatiques

L'utilisateur reçoit une checklist et décide ensuite de ses actions.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.services.emergency_checklist_templates import (
    EmergencyTemplate,
    get_template_by_keywords,
    get_template_by_id,
    get_all_template_ids,
    LLM_FALLBACK_PROMPT,
    UrgencyLevel,
    EMERGENCY_TEMPLATES,
)
from app.core.dependencies import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class EmergencyChecklistResult:
    """Résultat de la génération de checklist d'urgence."""
    success: bool
    checklist_markdown: str
    template_id: Optional[str]  # None si généré par LLM
    template_name: str
    urgency_level: str
    category: str
    is_llm_generated: bool
    message: str


class EmergencyChecklistAgent:
    """
    Agent simplifié pour la gestion des urgences en copropriété.

    Fonctionnement :
    1. Analyse la requête utilisateur pour détecter une urgence
    2. Cherche un template correspondant dans les 12 templates prédéfinis
    3. Si pas de match, utilise le LLM pour générer une checklist personnalisée
    4. Retourne la checklist en Markdown pour affichage

    L'agent NE déclenche PAS d'actions automatiques (pas d'emails, pas de workflows).
    """

    def __init__(self):
        self.llm_service = None
        self._templates_loaded = False
        logger.info("EmergencyChecklistAgent initialisé")

    async def _get_llm_service(self):
        """Lazy loading du service LLM."""
        if self.llm_service is None:
            self.llm_service = get_llm_service()
        return self.llm_service

    def is_emergency_query(self, user_input: str) -> bool:
        """
        Détecte si la requête utilisateur est une DEMANDE D'AIDE pour une urgence.

        La détection requiert DEUX conditions :
        1. Un mot-clé d'urgence (fuite, incendie, panne...)
        2. + Une demande d'aide OU un signalement explicite

        Cela évite les faux positifs comme "combien de dégâts des eaux cette année?"
        """
        user_lower = user_input.lower()

        # =================================================================
        # GROUPE 1: Mots-clés d'URGENCE (situations/incidents)
        # =================================================================
        urgency_keywords = [
            # Eau
            "fuite", "dégât des eaux", "inondation", "infiltration",
            # Énergie
            "panne", "coupure", "chauffage en panne", "plus de chauffage",
            "plus d'électricité", "plus de courant",
            # Équipements
            "ascenseur en panne", "ascenseur bloqué", "coincé dans l'ascenseur",
            "interphone en panne", "digicode cassé",
            # Sécurité
            "incendie", "feu", "fumée", "odeur de gaz", "fuite de gaz",
            "cambriolage", "effraction", "vol", "intrusion",
            # Sanitaire
            "égout bouché", "refoulement", "rat", "cafard", "nuisible",
            # Structure
            "toiture", "tuile", "ardoise",
        ]

        # =================================================================
        # GROUPE 2: Demandes d'AIDE explicites
        # =================================================================
        help_keywords = [
            "que faire", "quoi faire", "que dois-je faire", "comment faire",
            "comment gérer", "comment réagir", "comment procéder",
            "aide", "help", "aidez", "au secours",
            "procédure", "checklist", "marche à suivre",
            "étapes à suivre", "conseils", "recommandations"
        ]

        # =================================================================
        # GROUPE 3: Patterns de SIGNALEMENT (indiquent une situation en cours)
        # =================================================================
        alert_patterns = [
            "il y a une", "il y a un", "il y a eu",
            "j'ai une", "j'ai un", "on a une", "on a un",
            "je déclare", "je signale", "nous avons",
            "urgence", "urgent",  # Si "urgent/urgence" = signalement direct
            "vient de se produire", "vient d'arriver",
            "en ce moment", "actuellement",
        ]

        # =================================================================
        # GROUPE 4: Questions EXCLUSIVES (ne pas déclencher)
        # =================================================================
        question_exclusions = [
            "combien", "liste", "historique", "statistique",
            "cette année", "ce mois", "dernier", "dernière",
            "recap", "résumé", "bilan",
        ]

        # =================================================================
        # LOGIQUE DE DÉTECTION
        # =================================================================

        # 1. Vérifier si c'est une question statistique/historique
        for exclusion in question_exclusions:
            if exclusion in user_lower:
                # C'est probablement une question sur les urgences, pas une urgence
                # Sauf si explicitement demande d'aide
                has_help = any(h in user_lower for h in help_keywords)
                if not has_help:
                    return False

        # 2. Vérifier présence d'un mot-clé d'urgence
        has_urgency_keyword = any(kw in user_lower for kw in urgency_keywords)

        # 3. Vérifier présence d'une demande d'aide
        has_help_request = any(h in user_lower for h in help_keywords)

        # 4. Vérifier présence d'un pattern de signalement
        has_alert_pattern = any(p in user_lower for p in alert_patterns)

        # =================================================================
        # DÉCISION FINALE
        # =================================================================

        # Cas 1: Mot-clé urgence + Demande d'aide explicite
        if has_urgency_keyword and has_help_request:
            return True

        # Cas 2: Pattern de signalement + Mot-clé urgence
        if has_alert_pattern and has_urgency_keyword:
            return True

        # Cas 3: "urgence" ou "urgent" seul avec contexte
        if ("urgence" in user_lower or "urgent" in user_lower):
            # Vérifier qu'il y a un minimum de contexte
            words = user_lower.split()
            if len(words) >= 3:  # Plus que juste "urgence ascenseur"
                return True

        return False

    async def generate_checklist(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EmergencyChecklistResult:
        """
        Génère une checklist d'urgence basée sur la requête utilisateur.

        Args:
            user_input: La requête de l'utilisateur décrivant l'urgence
            context: Contexte optionnel (copropriété, etc.)

        Returns:
            EmergencyChecklistResult avec la checklist en Markdown
        """
        logger.info(f"Génération checklist pour: {user_input[:100]}...")

        # 1. Chercher un template correspondant
        template = get_template_by_keywords(user_input)

        if template:
            # Template trouvé - utiliser directement
            logger.info(f"Template trouvé: {template.id}")

            checklist_md = template.to_markdown()

            # Ajouter un message d'introduction
            intro = self._generate_intro_message(template, context)
            full_response = f"{intro}\n\n{checklist_md}"

            return EmergencyChecklistResult(
                success=True,
                checklist_markdown=full_response,
                template_id=template.id,
                template_name=template.nom,
                urgency_level=template.niveau_urgence.value,
                category=template.categorie.value,
                is_llm_generated=False,
                message=f"Checklist générée pour: {template.nom}"
            )

        else:
            # Pas de template - fallback LLM
            logger.info("Aucun template trouvé, utilisation du LLM")
            return await self._generate_with_llm(user_input, context)

    async def _generate_with_llm(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EmergencyChecklistResult:
        """
        Génère une checklist personnalisée via le LLM pour les urgences non couvertes.
        """
        try:
            llm_service = await self._get_llm_service()

            # Construire le prompt
            prompt = LLM_FALLBACK_PROMPT.format(user_input=user_input)

            # Ajouter le contexte si disponible
            if context:
                context_str = "\n".join([f"- {k}: {v}" for k, v in context.items() if v])
                prompt += f"\n\nCONTEXTE SUPPLÉMENTAIRE :\n{context_str}"

            # Appel LLM
            response = await llm_service.generate(
                prompt=prompt,
                max_tokens=2500,
                temperature=0.3  # Peu de créativité, réponse structurée
            )

            if response and response.strip():
                # Ajouter un avertissement que c'est généré par IA
                intro = """**Note :** Cette checklist a été générée automatiquement par l'IA pour votre situation spécifique.
Elle est fournie à titre indicatif. En cas de doute, consultez un professionnel.

---

"""
                full_response = intro + response

                return EmergencyChecklistResult(
                    success=True,
                    checklist_markdown=full_response,
                    template_id=None,
                    template_name="Checklist personnalisée (IA)",
                    urgency_level="à évaluer",
                    category="non catégorisé",
                    is_llm_generated=True,
                    message="Checklist personnalisée générée par IA"
                )
            else:
                raise ValueError("Réponse LLM vide")

        except Exception as e:
            logger.error(f"Erreur génération LLM: {e}")

            # Fallback ultime - message générique
            return EmergencyChecklistResult(
                success=False,
                checklist_markdown=self._get_generic_emergency_advice(),
                template_id=None,
                template_name="Conseils génériques",
                urgency_level="à évaluer",
                category="non catégorisé",
                is_llm_generated=False,
                message=f"Impossible de générer une checklist spécifique: {str(e)}"
            )

    def _generate_intro_message(
        self,
        template: EmergencyTemplate,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Génère un message d'introduction pour la checklist."""

        urgency_emoji = {
            UrgencyLevel.CRITIQUE: "🚨",
            UrgencyLevel.HAUTE: "⚠️",
            UrgencyLevel.MOYENNE: "📋",
            UrgencyLevel.BASSE: "📝"
        }

        emoji = urgency_emoji.get(template.niveau_urgence, "📋")

        intro = f"""{emoji} **Situation détectée : {template.nom}**

Voici la checklist complète pour gérer cette situation.
Suivez les étapes dans l'ordre de priorité (les actions **[CRITIQUE]** sont à traiter en premier).

Une fois la situation stabilisée, vous pourrez utiliser l'assistant pour :
- Générer des emails aux parties concernées
- Rechercher des contacts de professionnels
- Consulter la documentation pertinente"""

        # Ajouter le contexte si disponible
        if context:
            if context.get("copropriete"):
                intro += f"\n\n**Copropriété concernée :** {context['copropriete']}"
            if context.get("adresse"):
                intro += f"\n**Adresse :** {context['adresse']}"

        return intro

    def _get_generic_emergency_advice(self) -> str:
        """Retourne des conseils génériques en cas d'échec de génération."""
        return """## Conseils d'urgence génériques

En cas de situation d'urgence dans votre copropriété :

### Actions immédiates

- [ ] **Évaluer le danger immédiat**
  _Y a-t-il un risque pour les personnes ? Si oui, évacuer._

- [ ] **Appeler les secours si nécessaire**
  _Pompiers : 18 | SAMU : 15 | Police : 17 | Urgences : 112_

- [ ] **Sécuriser la zone**
  _Couper les alimentations concernées (eau, gaz, électricité) si possible et sans danger._

- [ ] **Documenter la situation**
  _Prendre des photos/vidéos avant toute intervention._

### Contacts à prévenir

- [ ] **Syndic de copropriété**
  _Numéro d'urgence si disponible._

- [ ] **Assurance de l'immeuble**
  _Numéro sur l'attestation affichée en parties communes._

- [ ] **Professionnels concernés**
  _Plombier, électricien, serrurier selon la situation._

### Conseils

- Ne prenez aucun risque pour votre sécurité
- Conservez tous les documents et factures
- En cas de sinistre, déclarez sous 5 jours à l'assurance
- Le syndic peut engager des travaux urgents sans AG

---

Pour une checklist plus détaillée adaptée à votre situation, décrivez plus précisément le problème rencontré."""

    def get_available_templates(self) -> List[Dict[str, str]]:
        """Retourne la liste des templates disponibles pour information."""
        templates_info = []
        for template in EMERGENCY_TEMPLATES.values():
            templates_info.append({
                "id": template.id,
                "nom": template.nom,
                "categorie": template.categorie.value,
                "niveau_urgence": template.niveau_urgence.value,
                "description": template.description
            })
        return templates_info

    async def get_checklist_by_type(self, template_id: str) -> Optional[EmergencyChecklistResult]:
        """
        Récupère une checklist par son ID de template.
        Utile pour accès direct via boutons/UI.
        """
        template = get_template_by_id(template_id)

        if template:
            checklist_md = template.to_markdown()
            intro = self._generate_intro_message(template, None)
            full_response = f"{intro}\n\n{checklist_md}"

            return EmergencyChecklistResult(
                success=True,
                checklist_markdown=full_response,
                template_id=template.id,
                template_name=template.nom,
                urgency_level=template.niveau_urgence.value,
                category=template.categorie.value,
                is_llm_generated=False,
                message=f"Checklist: {template.nom}"
            )

        return None


# Instance singleton
_emergency_checklist_agent: Optional[EmergencyChecklistAgent] = None


def get_emergency_checklist_agent() -> EmergencyChecklistAgent:
    """Récupère l'instance singleton de l'agent."""
    global _emergency_checklist_agent
    if _emergency_checklist_agent is None:
        _emergency_checklist_agent = EmergencyChecklistAgent()
    return _emergency_checklist_agent


# Export
__all__ = [
    'EmergencyChecklistAgent',
    'EmergencyChecklistResult',
    'get_emergency_checklist_agent',
]
