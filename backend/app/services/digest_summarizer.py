"""
Digest Summarizer
Génère résumé exécutif intelligent du digest quotidien

Architecture:
- Analyse emails classifiés (urgency + category)
- Extraction highlights (top actions, faits marquants)
- Génération résumé LLM
- Métriques et analytics
"""

from typing import Dict, Any, List, Optional
import structlog
from datetime import datetime
import json
import re

from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class DigestSummarizer:
    """
    Générateur de résumés de digest

    Capacités:
    - Résumé exécutif du jour (3-5 bullet points)
    - Highlights par catégorie
    - Actions urgentes identifiées (top 3-5)
    - Métriques clés (volume, categories, amounts)
    - Format optimisé pour lecture rapide (<2 min)
    """

    MAX_URGENT_ACTIONS = 5
    MAX_HIGHLIGHTS = 5

    def __init__(self):
        self.llm_service = LLMService()

    async def generate_executive_summary(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]],
        analytics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Génère résumé exécutif du digest

        Args:
            classified_emails: Emails classifiés par urgence
                Format: {"urgent": [...], "important": [...], "routine": [...]}
            analytics: Métriques du digest (optionnel)

        Returns:
            Dict avec:
                - overview: str (vue d'ensemble)
                - urgent_actions: List[Dict] (actions urgentes)
                - highlights: List[str] (faits marquants)
                - by_category: Dict[str, str] (résumés par catégorie)
                - metrics: Dict (métriques clés)
        """
        try:
            # Calculer analytics si non fourni
            if analytics is None:
                analytics = self._calculate_analytics(classified_emails)

            # Préparer contexte pour LLM
            context = self._prepare_context(classified_emails, analytics)

            # Générer résumé via LLM
            llm_summary = await self._generate_llm_summary(context, classified_emails)

            # Extraire actions urgentes depuis emails urgents
            urgent_actions = self._extract_urgent_actions(classified_emails.get('urgent', []))

            # Assembler résultat final
            result = {
                "overview": llm_summary.get('overview', self._generate_fallback_overview(analytics)),
                "urgent_actions": urgent_actions[:self.MAX_URGENT_ACTIONS],
                "highlights": llm_summary.get('highlights', [])[:self.MAX_HIGHLIGHTS],
                "by_category": llm_summary.get('by_category', {}),
                "metrics": analytics,
                "generated_at": datetime.now().isoformat()
            }

            logger.info(
                "executive_summary_generated",
                total_emails=analytics.get('total_emails', 0),
                urgent_actions_count=len(result['urgent_actions']),
                highlights_count=len(result['highlights'])
            )

            return result

        except Exception as e:
            logger.error("summary_generation_failed", error=str(e), exc_info=True)
            # Fallback simple
            return self._generate_fallback_summary(classified_emails, analytics or {})

    def _calculate_analytics(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Calcule métriques du digest

        Returns:
            Dict avec total, urgents, categories breakdown, amounts, etc.
        """
        urgent = classified_emails.get('urgent', [])
        important = classified_emails.get('important', [])
        routine = classified_emails.get('routine', [])

        total = len(urgent) + len(important) + len(routine)

        # Compter par catégorie
        category_counts = {}
        for urgency_list in [urgent, important, routine]:
            for email in urgency_list:
                category = email.get('llm_analysis', {}).get('category', 'autre')
                category_counts[category] = category_counts.get(category, 0) + 1

        # Somme des montants trouvés
        total_amounts = 0
        amounts_count = 0
        for urgency_list in [urgent, important, routine]:
            for email in urgency_list:
                entities = email.get('llm_analysis', {}).get('entities', {})
                amounts = entities.get('amounts', [])
                for amount in amounts:
                    if isinstance(amount, dict) and 'value' in amount:
                        total_amounts += amount['value']
                        amounts_count += 1

        # Compter actions requises
        action_required_count = 0
        for urgency_list in [urgent, important]:
            for email in urgency_list:
                if email.get('llm_analysis', {}).get('action_required', False):
                    action_required_count += 1

        return {
            "total_emails": total,
            "urgent_count": len(urgent),
            "important_count": len(important),
            "routine_count": len(routine),
            "action_required_count": action_required_count,
            "category_breakdown": category_counts,
            "total_amounts_eur": round(total_amounts, 2) if total_amounts > 0 else None,
            "amounts_count": amounts_count
        }

    def _prepare_context(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]],
        analytics: Dict[str, Any]
    ) -> str:
        """Prépare le contexte pour le LLM"""

        urgent = classified_emails.get('urgent', [])
        important = classified_emails.get('important', [])

        context = f"""
MÉTRIQUES DU DIGEST:
- Total emails: {analytics.get('total_emails', 0)}
- Urgents: {analytics.get('urgent_count', 0)}
- Importants: {analytics.get('important_count', 0)}
- Actions requises: {analytics.get('action_required_count', 0)}
- Montants détectés: {analytics.get('amounts_count', 0)} ({analytics.get('total_amounts_eur', 0)}€)

RÉPARTITION PAR CATÉGORIE:
"""
        for category, count in analytics.get('category_breakdown', {}).items():
            context += f"- {category}: {count}\n"

        context += "\n--- EMAILS URGENTS ---\n"
        for i, email in enumerate(urgent[:5], 1):  # Top 5 urgents
            context += f"\n{i}. {email.get('subject', 'Sans objet')}\n"
            context += f"   Expéditeur: {email.get('sender', 'Inconnu')}\n"

            llm_analysis = email.get('llm_analysis', {})
            if llm_analysis:
                context += f"   Catégorie: {llm_analysis.get('category', 'N/A')}\n"
                if llm_analysis.get('action_required'):
                    context += f"   ⚠️ Action requise\n"
                if llm_analysis.get('deadline'):
                    context += f"   ⏰ Deadline: {llm_analysis.get('deadline')}\n"
                entities = llm_analysis.get('entities', {})
                if entities.get('amounts'):
                    context += f"   💰 Montants: {entities['amounts']}\n"

        context += "\n--- EMAILS IMPORTANTS ---\n"
        for i, email in enumerate(important[:3], 1):  # Top 3 importants
            context += f"\n{i}. {email.get('subject', 'Sans objet')}\n"
            context += f"   Expéditeur: {email.get('sender', 'Inconnu')}\n"
            llm_analysis = email.get('llm_analysis', {})
            if llm_analysis:
                context += f"   Catégorie: {llm_analysis.get('category', 'N/A')}\n"

        return context

    async def _generate_llm_summary(
        self,
        context: str,
        classified_emails: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Génère résumé via LLM"""

        prompt = f"""Tu es un assistant qui génère des résumés de digest d'emails pour un syndic de copropriété.

CONTEXTE DU DIGEST:
{context}

GÉNÈRE UN RÉSUMÉ EXÉCUTIF STRUCTURÉ:

1. **OVERVIEW** (2-3 phrases)
   Résumé global de l'activité du jour. Mentionne le total d'emails, les points clés.

2. **HIGHLIGHTS** (3-5 bullet points)
   Faits marquants du jour:
   - Nouveaux devis/factures avec montants
   - Réclamations importantes
   - Décisions à prendre
   - Événements notables (assemblée générale, travaux planifiés, etc.)

3. **BY_CATEGORY** (résumé par catégorie si >2 emails)
   Pour chaque catégorie avec 2+ emails, un résumé d'une ligne
   Ex: "devis_fournisseur": "2 devis reçus, total 3 450€"

RETOURNE UNIQUEMENT UN JSON VALIDE (pas de markdown):
{{
    "overview": "Activité soutenue aujourd'hui avec 15 emails...",
    "highlights": [
        "2 nouveaux devis reçus (total: 3 450€)",
        "Réclamation copropriétaire Apt 302 (fuite salle de bain)",
        "Assemblée générale confirmée pour 15/11"
    ],
    "by_category": {{
        "devis_fournisseur": "2 devis reçus, total 3 450€",
        "reclamation_coproprietaire": "1 réclamation en attente"
    }}
}}
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=600
            )

            # Parser JSON
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # Extraire JSON depuis markdown
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError("LLM response not valid JSON")

            return result

        except Exception as e:
            logger.error("llm_summary_generation_failed", error=str(e))
            return {
                "overview": self._generate_fallback_overview(
                    self._calculate_analytics(classified_emails)
                ),
                "highlights": [],
                "by_category": {}
            }

    def _extract_urgent_actions(
        self,
        urgent_emails: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extrait actions urgentes depuis emails urgents

        Returns:
            List[{"action": str, "description": str, "deadline": str, "email_subject": str}]
        """
        actions = []

        for email in urgent_emails:
            llm_analysis = email.get('llm_analysis', {})

            if not llm_analysis.get('action_required', False):
                continue

            action = {
                "action": llm_analysis.get('suggested_response', 'Traiter cet email'),
                "description": email.get('subject', 'Sans objet'),
                "sender": email.get('sender', 'Inconnu'),
                "deadline": llm_analysis.get('deadline'),
                "email_subject": email.get('subject', 'Sans objet'),
                "category": llm_analysis.get('category'),
                "priority_score": llm_analysis.get('priority_score', 50)
            }

            actions.append(action)

        # Trier par priority score (descendant)
        actions.sort(key=lambda x: x.get('priority_score', 0), reverse=True)

        return actions

    def _generate_fallback_overview(self, analytics: Dict[str, Any]) -> str:
        """Génère overview basique sans LLM"""
        total = analytics.get('total_emails', 0)
        urgent = analytics.get('urgent_count', 0)
        action_required = analytics.get('action_required_count', 0)

        return f"{total} emails reçus aujourd'hui. {urgent} emails urgents nécessitent votre attention. {action_required} actions requises."

    def _generate_fallback_summary(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]],
        analytics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Génère résumé fallback simple sans LLM"""
        urgent = classified_emails.get('urgent', [])

        urgent_actions = []
        for email in urgent[:self.MAX_URGENT_ACTIONS]:
            urgent_actions.append({
                "action": "Traiter cet email urgent",
                "description": email.get('subject', 'Sans objet'),
                "sender": email.get('sender', 'Inconnu'),
                "deadline": None,
                "email_subject": email.get('subject', 'Sans objet')
            })

        return {
            "overview": self._generate_fallback_overview(analytics),
            "urgent_actions": urgent_actions,
            "highlights": [],
            "by_category": {},
            "metrics": analytics,
            "generated_at": datetime.now().isoformat()
        }
