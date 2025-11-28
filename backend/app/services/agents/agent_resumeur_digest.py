"""
Agent Résumeur Digest - Génération de digest quotidien intelligent
Génère des résumés structurés d'emails avec statistiques, tendances et actions prioritaires
"""

import structlog
from typing import List, Dict, Any
from datetime import datetime

from app.services.llm_service import LLMService
from app.services.classificateur_email_avance import (
    EmailClassifie,
    NiveauUrgenceEmail
)

logger = structlog.get_logger()


class AgentResumeurDigest:
    """
    Agent spécialisé pour génération de digest quotidien intelligent

    Workflow:
    1. Groupe emails par urgence
    2. Résume chaque catégorie
    3. Identifie patterns et tendances
    4. Suggère actions prioritaires
    5. Formate en Markdown lisible

    Output:
    - Digest Markdown structuré
    - Statistiques clés
    - Top 10 actions prioritaires
    - Tendances identifiées
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("agent_resumeur_digest_initialise")

    async def generer_digest(
        self,
        emails: List[EmailClassifie],
        periode_heures: int = 24
    ) -> Dict[str, Any]:
        """
        Génère un digest structuré et intelligent

        Args:
            emails: Liste d'emails classifiés
            periode_heures: Période couverte (défaut 24h)

        Returns:
            Dict avec:
            - resume_markdown: Digest formaté en Markdown
            - statistiques: Statistiques clés
            - actions_urgentes: Actions urgentes à faire
            - tendances: Tendances identifiées
        """
        try:
            logger.info("generation_digest_demarree",
                       nb_emails=len(emails),
                       periode_heures=periode_heures)

            # Groupe par urgence
            par_urgence = self._grouper_par_urgence(emails)

            # Statistiques
            stats = self._calculer_statistiques(emails, par_urgence)

            # Génère résumé LLM pour chaque section
            sections = await self._generer_sections(par_urgence)

            # Identifie tendances
            tendances = await self._identifier_tendances(emails)

            # Actions urgentes
            actions_urgentes = self._extraire_actions_urgentes(par_urgence)

            # Formate Markdown final
            markdown = self._formater_digest_markdown(
                sections=sections,
                stats=stats,
                tendances=tendances,
                actions_urgentes=actions_urgentes,
                periode_heures=periode_heures
            )

            logger.info("generation_digest_terminee",
                       nb_emails=len(emails),
                       nb_actions_urgentes=len(actions_urgentes))

            return {
                "resume_markdown": markdown,
                "statistiques": stats,
                "actions_urgentes": actions_urgentes,
                "tendances": tendances,
                "nb_emails": len(emails),
                "genere_le": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("generation_digest_echouee", erreur=str(e), exc_info=True)
            raise

    def _grouper_par_urgence(
        self,
        emails: List[EmailClassifie]
    ) -> Dict[NiveauUrgenceEmail, List[EmailClassifie]]:
        """Groupe emails par niveau d'urgence"""
        groupes = {
            NiveauUrgenceEmail.CRITIQUE: [],
            NiveauUrgenceEmail.URGENT: [],
            NiveauUrgenceEmail.IMPORTANT: [],
            NiveauUrgenceEmail.ROUTINIER: [],
            NiveauUrgenceEmail.FAIBLE: [],
        }

        for email in emails:
            if email.urgence != NiveauUrgenceEmail.SPAM:
                groupes[email.urgence].append(email)

        return groupes

    def _calculer_statistiques(
        self,
        emails: List[EmailClassifie],
        par_urgence: Dict[NiveauUrgenceEmail, List[EmailClassifie]]
    ) -> Dict[str, Any]:
        """Calcule statistiques clés"""
        return {
            "total_emails": len(emails),
            "nb_critiques": len(par_urgence[NiveauUrgenceEmail.CRITIQUE]),
            "nb_urgents": len(par_urgence[NiveauUrgenceEmail.URGENT]),
            "nb_importants": len(par_urgence[NiveauUrgenceEmail.IMPORTANT]),
            "nb_routiniers": len(par_urgence[NiveauUrgenceEmail.ROUTINIER]),
            "nb_actions_requises": sum(1 for e in emails if e.action_requise),
            "confiance_moyenne": sum(e.confiance for e in emails) / len(emails) if emails else 0,
        }

    async def _generer_sections(
        self,
        par_urgence: Dict[NiveauUrgenceEmail, List[EmailClassifie]]
    ) -> Dict[str, str]:
        """Génère résumés LLM pour chaque section"""
        sections = {}

        for niveau_urgence, liste_emails in par_urgence.items():
            if not liste_emails:
                continue

            # Prépare contexte pour LLM
            contexte_emails = "\n".join([
                f"- {e.sujet} (de {e.expediteur}): {e.resume}"
                for e in liste_emails[:10]  # Limite 10 pour éviter trop de tokens
            ])

            prompt = f"""Résume ces {len(liste_emails)} emails de niveau {niveau_urgence.value} en 2-3 phrases concises.

Emails:
{contexte_emails}

Résumé:"""

            resume = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=200
            )

            sections[niveau_urgence.value] = resume.strip()

        return sections

    async def _identifier_tendances(
        self,
        emails: List[EmailClassifie]
    ) -> List[str]:
        """Identifie patterns et tendances"""
        if not emails:
            return []

        # Analyse catégories fréquentes
        comptage_categories = {}
        for email in emails:
            cat = email.categorie.value
            comptage_categories[cat] = comptage_categories.get(cat, 0) + 1

        # Top 3 catégories
        top_categories = sorted(
            comptage_categories.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        tendances = []
        for cat, compte in top_categories:
            if compte >= 3:
                tendances.append(f"Pic d'emails '{cat}' ({compte} reçus)")

        return tendances

    def _extraire_actions_urgentes(
        self,
        par_urgence: Dict[NiveauUrgenceEmail, List[EmailClassifie]]
    ) -> List[Dict[str, str]]:
        """Extrait actions urgentes à faire"""
        actions = []

        # Urgences critiques
        for email in par_urgence[NiveauUrgenceEmail.CRITIQUE]:
            actions.append({
                "priorite": "🚨 CRITIQUE",
                "sujet": email.sujet,
                "action": email.action_suggeree,
                "expediteur": email.expediteur
            })

        # Urgences normales
        for email in par_urgence[NiveauUrgenceEmail.URGENT]:
            actions.append({
                "priorite": "⚠️ URGENT",
                "sujet": email.sujet,
                "action": email.action_suggeree,
                "expediteur": email.expediteur
            })

        return actions[:10]  # Top 10 actions

    def _formater_digest_markdown(
        self,
        sections: Dict[str, str],
        stats: Dict[str, Any],
        tendances: List[str],
        actions_urgentes: List[Dict[str, str]],
        periode_heures: int
    ) -> str:
        """Formate digest final en Markdown"""

        md = f"""# 📧 Digest Emails - Dernières {periode_heures}h

**Généré le** : {datetime.now().strftime('%d/%m/%Y à %H:%M')}

---

## 📊 Résumé Statistique

- **Total emails** : {stats['total_emails']}
- 🚨 **Critiques** : {stats['nb_critiques']}
- ⚠️ **Urgents** : {stats['nb_urgents']}
- 📌 **Importants** : {stats['nb_importants']}
- 📋 **Routiniers** : {stats['nb_routiniers']}
- ✅ **Actions requises** : {stats['nb_actions_requises']}

---

"""

        # Actions urgentes
        if actions_urgentes:
            md += "## 🎯 Actions Prioritaires\n\n"
            for action in actions_urgentes:
                md += f"### {action['priorite']} {action['sujet']}\n"
                md += f"**De** : {action['expediteur']}  \n"
                md += f"**Action** : {action['action']}\n\n"
            md += "---\n\n"

        # Sections par urgence
        if NiveauUrgenceEmail.CRITIQUE.value in sections:
            md += f"## 🚨 URGENCES CRITIQUES ({stats['nb_critiques']})\n\n"
            md += sections[NiveauUrgenceEmail.CRITIQUE.value]
            md += "\n\n---\n\n"

        if NiveauUrgenceEmail.URGENT.value in sections:
            md += f"## ⚠️ URGENT ({stats['nb_urgents']})\n\n"
            md += sections[NiveauUrgenceEmail.URGENT.value]
            md += "\n\n---\n\n"

        if NiveauUrgenceEmail.IMPORTANT.value in sections:
            md += f"## 📌 IMPORTANT ({stats['nb_importants']})\n\n"
            md += sections[NiveauUrgenceEmail.IMPORTANT.value]
            md += "\n\n---\n\n"

        if NiveauUrgenceEmail.ROUTINIER.value in sections:
            md += f"## 📋 ROUTINIER ({stats['nb_routiniers']})\n\n"
            md += sections[NiveauUrgenceEmail.ROUTINIER.value]
            md += "\n\n"

        # Tendances
        if tendances:
            md += "## 📈 Tendances Identifiées\n\n"
            for tendance in tendances:
                md += f"- {tendance}\n"
            md += "\n"

        md += "---\n\n"
        md += "*Digest généré automatiquement par DisruptIQ AI*\n"

        return md

    async def generer_resume_personnalise(
        self,
        emails: List[EmailClassifie],
        question_utilisateur: str
    ) -> str:
        """
        Génère un résumé personnalisé basé sur question utilisateur

        Exemple: "Quels sont les problèmes de plomberie cette semaine?"

        Args:
            emails: Liste emails classifiés
            question_utilisateur: Question de l'utilisateur

        Returns:
            Réponse personnalisée en texte
        """
        try:
            # Filtre emails pertinents pour la question
            contexte_emails = "\n".join([
                f"- [{e.categorie.value}] {e.sujet}: {e.resume}"
                for e in emails[:20]  # Max 20 emails
            ])

            prompt = f"""Tu es un assistant intelligent pour syndics de copropriété.

L'utilisateur demande: "{question_utilisateur}"

Voici les emails récents:
{contexte_emails}

Réponds de manière concise et actionnable à la question de l'utilisateur.

Réponse:"""

            reponse = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=400
            )

            logger.info("resume_personnalise_genere",
                       question=question_utilisateur[:50])

            return reponse.strip()

        except Exception as e:
            logger.error("generation_resume_personnalise_echouee",
                        erreur=str(e),
                        exc_info=True)
            return "Désolé, impossible de générer le résumé personnalisé."
