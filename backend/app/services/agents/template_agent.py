"""
Template Agent - Manages and fills document/email templates
"""

import structlog
from typing import Dict, Any, List, Optional
from app.services.llm_service import LLMService

logger = structlog.get_logger()


class TemplateAgent:
    """
    Template Agent - Fills templates with dynamic variables

    Capabilities:
    - Library of predefined templates
    - Dynamic variable filling
    - Template generation with LLM
    - Validation of required variables
    """

    # Predefined templates
    TEMPLATES = {
        "convocation_ag": {
            "name": "Convocation Assemblée Générale",
            "variables": ["date", "heure", "lieu", "ordre_du_jour"],
            "content": """Madame, Monsieur {nom},

Nous avons l'honneur de vous convoquer à l'Assemblée Générale qui se tiendra le {date} à {heure} au {lieu}.

ORDRE DU JOUR:
{ordre_du_jour}

Votre présence est importante pour les décisions concernant la copropriété.

Cordialement,
Le Syndic"""
        },

        "alerte_urgence": {
            "name": "Alerte Urgence Copropriété",
            "variables": ["type_urgence", "date", "actions_immediates"],
            "content": """URGENT - Madame, Monsieur {nom},

Nous vous informons qu'une situation urgente nécessite votre attention:

TYPE D'URGENCE: {type_urgence}
DATE: {date}

ACTIONS IMMÉDIATES À PRENDRE:
{actions_immediates}

Pour toute question, contactez immédiatement le syndic.

Cordialement,
Le Syndic"""
        },

        "demande_devis": {
            "name": "Demande de Devis Fournisseur",
            "variables": ["service", "deadline", "specifications"],
            "content": """Madame, Monsieur,

Nous souhaitons obtenir un devis pour le service suivant:

SERVICE DEMANDÉ: {service}
SPÉCIFICATIONS: {specifications}
DÉLAI DE RÉPONSE SOUHAITÉ: {deadline}

Merci de nous faire parvenir votre proposition dans les meilleurs délais.

Cordialement,
Le Syndic"""
        },

        "relance_paiement": {
            "name": "Relance Paiement Charges",
            "variables": ["nom", "montant_du", "date_echeance"],
            "content": """Madame, Monsieur {nom},

Nous vous rappelons que le paiement de vos charges de copropriété est en attente:

MONTANT DÛ: {montant_du} €
DATE D'ÉCHÉANCE: {date_echeance}

Nous vous remercions de régulariser votre situation dans les plus brefs délais.

Pour toute question, n'hésitez pas à nous contacter.

Cordialement,
Le Syndic"""
        }
    }

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("template_agent_initialized", template_count=len(self.TEMPLATES))

    async def fill_template(
        self,
        template_name: str,
        user_request: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Fill a template with variables extracted from user request

        Args:
            template_name: Name of the template to use
            user_request: User's original request
            context: Additional context data

        Returns:
            Dict with success, message (filled template), data
        """
        try:
            # Get template
            template = self.TEMPLATES.get(template_name)

            if not template:
                # Try to find best matching template
                template_name, template = await self._find_best_template(user_request)

            if not template:
                # Generate template dynamically
                return await self._generate_dynamic_template(user_request, context)

            # Extract variables from user request
            variables = await self._extract_variables(
                user_request=user_request,
                required_vars=template["variables"],
                context=context
            )

            # Fill template
            filled_content = template["content"]
            for var_name, var_value in variables.items():
                filled_content = filled_content.replace(f"{{{var_name}}}", str(var_value))

            return {
                "success": True,
                "message": filled_content,
                "data": {
                    "template_name": template_name,
                    "variables": variables
                }
            }

        except Exception as e:
            logger.error("template_filling_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"Erreur lors du remplissage du template: {str(e)}"
            }

    async def _find_best_template(self, user_request: str) -> tuple[Optional[str], Optional[Dict]]:
        """Find the best matching template for user request"""
        prompt = f"""
Quelle template correspond le mieux à cette demande?

DEMANDE:
{user_request}

TEMPLATES DISPONIBLES:
{', '.join(self.TEMPLATES.keys())}

Réponds avec UNIQUEMENT le nom de la template (ex: convocation_ag) ou "none" si aucune ne correspond.
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=50,
                temperature=0.1
            )

            template_name = response.strip().lower()

            if template_name in self.TEMPLATES:
                return template_name, self.TEMPLATES[template_name]

            return None, None

        except Exception as e:
            logger.error("template_matching_failed", error=str(e))
            return None, None

    async def _extract_variables(
        self,
        user_request: str,
        required_vars: List[str],
        context: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """Extract template variables from user request"""
        prompt = f"""
Extrait les variables suivantes de la demande utilisateur.

DEMANDE:
{user_request}

CONTEXTE ADDITIONNEL:
{context if context else "Aucun"}

VARIABLES REQUISES:
{', '.join(required_vars)}

Réponds en JSON avec chaque variable et sa valeur extraite.
Si une variable n'est pas trouvée, utilise "[À COMPLÉTER]".

JSON:
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=400,
                temperature=0.3
            )

            import json
            variables = json.loads(response.strip())

            # Ensure all required variables are present
            for var in required_vars:
                if var not in variables:
                    variables[var] = "[À COMPLÉTER]"

            return variables

        except Exception as e:
            logger.error("variable_extraction_failed", error=str(e))
            # Return placeholders
            return {var: "[À COMPLÉTER]" for var in required_vars}

    async def _generate_dynamic_template(
        self,
        user_request: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate a template dynamically with LLM"""
        prompt = f"""
Génère un template de message professionnel pour un syndic de copropriété.

DEMANDE:
{user_request}

CONTEXTE:
{context if context else "Aucun"}

Génère un message complet, structuré et professionnel.
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=600,
                temperature=0.6
            )

            return {
                "success": True,
                "message": response.strip(),
                "data": {
                    "template_name": "dynamic",
                    "generated": True
                }
            }

        except Exception as e:
            logger.error("dynamic_template_generation_failed", error=str(e))
            return {
                "success": False,
                "message": f"Erreur lors de la génération du template: {str(e)}"
            }

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates"""
        return [
            {
                "id": template_id,
                "name": template_data["name"],
                "variables": template_data["variables"]
            }
            for template_id, template_data in self.TEMPLATES.items()
        ]
