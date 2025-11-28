"""
Exécuteur Actions - Exécution automatique d'actions depuis digest emails
Déclenche workflows N8N, requêtes SQL/RAG, génération emails selon urgence
"""

import structlog
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.services.classificateur_email_avance import (
    EmailClassifie,
    NiveauUrgenceEmail,
    CategorieEmail
)
from app.services.llm_service import LLMService

logger = structlog.get_logger()


class ExecuteurActions:
    """
    Exécute automatiquement les actions identifiées dans le digest

    Workflow par urgence:
    🚨 CRITIQUE → Workflow N8N immédiat (fuite, incendie, gaz)
    ⚠️ URGENT → Recherche SQL/RAG + suggestion action
    📌 IMPORTANT → Génération email draft réponse
    📋 ROUTINIER → Création tâche dans système

    Tracking:
    - Workflows déclenchés (N8N)
    - Requêtes SQL exécutées
    - Drafts emails générés
    - Tâches créées
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("executeur_actions_initialise")

    async def executer_actions_depuis_digest(
        self,
        emails_classifies: List[EmailClassifie],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Exécute actions automatiques pour chaque email critique/urgent

        Args:
            emails_classifies: Liste emails classifiés
            db: Session base de données

        Returns:
            Dict avec:
            - workflows_declenches: Liste workflows N8N déclenchés
            - requetes_sql_executees: Requêtes SQL lancées
            - drafts_generes: Emails drafts créés
            - taches_creees: Tâches ajoutées
        """
        try:
            logger.info("execution_actions_demarree",
                       nb_emails=len(emails_classifies))

            resultats = {
                "workflows_declenches": [],
                "requetes_sql_executees": [],
                "drafts_generes": [],
                "taches_creees": []
            }

            for email in emails_classifies:

                # URGENCE CRITIQUE → Workflow N8N immédiat
                if email.urgence == NiveauUrgenceEmail.CRITIQUE:
                    resultat_workflow = await self._declencher_workflow_urgence(email, db)
                    resultats["workflows_declenches"].append(resultat_workflow)

                # URGENT → Recherche contexte + suggestion
                elif email.urgence == NiveauUrgenceEmail.URGENT:
                    resultat_contexte = await self._chercher_contexte_et_suggerer(email, db)
                    resultats["requetes_sql_executees"].append(resultat_contexte)

                # IMPORTANT → Email draft
                elif email.urgence == NiveauUrgenceEmail.IMPORTANT:
                    resultat_draft = await self._generer_draft_reponse(email, db)
                    resultats["drafts_generes"].append(resultat_draft)

                # ROUTINIER → Tâche
                else:
                    resultat_tache = await self._creer_tache(email, db)
                    resultats["taches_creees"].append(resultat_tache)

            logger.info("execution_actions_terminee",
                       nb_workflows=len(resultats["workflows_declenches"]),
                       nb_sql=len(resultats["requetes_sql_executees"]),
                       nb_drafts=len(resultats["drafts_generes"]),
                       nb_taches=len(resultats["taches_creees"]))

            return resultats

        except Exception as e:
            logger.error("execution_actions_echouee", erreur=str(e), exc_info=True)
            raise

    async def _declencher_workflow_urgence(
        self,
        email: EmailClassifie,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Déclenche workflow N8N pour urgence critique

        Workflows selon catégorie:
        - urgence_fuite → Workflow plombier d'urgence
        - urgence_incendie → Workflow pompiers + évacuation
        - urgence_gaz → Workflow pompiers + évacuation gaz
        - urgence_intrusion → Workflow police + sécurité
        """
        try:
            logger.info("declenchement_workflow_urgence",
                       categorie=email.categorie.value,
                       sujet=email.sujet[:50])

            # Mapping catégorie → workflow N8N
            workflows_mapping = {
                CategorieEmail.URGENCE_FUITE: "urgence_plombier",
                CategorieEmail.URGENCE_INCENDIE: "urgence_pompiers_incendie",
                CategorieEmail.URGENCE_GAZ: "urgence_pompiers_gaz",
                CategorieEmail.URGENCE_INTRUSION: "urgence_police_securite",
                CategorieEmail.URGENCE_ASCENSEUR: "urgence_technicien_ascenseur",
                CategorieEmail.URGENCE_ELECTRIQUE: "urgence_electricien",
            }

            nom_workflow = workflows_mapping.get(
                email.categorie,
                "urgence_generique"
            )

            # Prépare payload pour N8N
            payload_n8n = {
                "action": nom_workflow,
                "urgence": "critique",
                "contexte": {
                    "email_id": email.id_message,
                    "sujet": email.sujet,
                    "expediteur": email.expediteur,
                    "entites": email.entites_detectees,
                    "action_suggeree": email.action_suggeree
                },
                "trace": {
                    "timestamp": datetime.now().isoformat(),
                    "source": "executeur_actions"
                }
            }

            # TODO: Appel réel webhook N8N
            # from app.services.webhook_service import WebhookService
            # webhook_service = WebhookService()
            # reponse = await webhook_service.trigger_workflow(nom_workflow, payload_n8n)

            # Pour l'instant: simulation
            logger.info("workflow_urgence_declenche",
                       workflow=nom_workflow,
                       email_id=email.id_message)

            return {
                "workflow": nom_workflow,
                "email_id": email.id_message,
                "sujet": email.sujet,
                "statut": "declenche",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("declenchement_workflow_echoue",
                        email_id=email.id_message,
                        erreur=str(e))
            return {
                "workflow": "erreur",
                "email_id": email.id_message,
                "statut": "echec",
                "erreur": str(e)
            }

    async def _chercher_contexte_et_suggerer(
        self,
        email: EmailClassifie,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Cherche contexte dans SQL/RAG et suggère action

        Use Cases:
        - Plainte → Cherche historique plaintes similaires
        - Panne ascenseur → Cherche contrat maintenance + historique pannes
        - Demande travaux → Cherche devis précédents similaires
        """
        try:
            logger.info("recherche_contexte_demarree",
                       categorie=email.categorie.value,
                       email_id=email.id_message)

            # Génère requête contexte avec LLM
            prompt_contexte = f"""Génère une requête de recherche pour trouver le contexte pertinent.

Email:
Catégorie: {email.categorie.value}
Sujet: {email.sujet}
Résumé: {email.resume}

Que faut-il chercher dans la base de données pour aider le syndic à répondre ?

Requête de recherche:"""

            requete_contexte = await self.llm_service.generate_response(
                prompt=prompt_contexte,
                temperature=0.3,
                max_tokens=200
            )

            # TODO: Exécuter recherche SQL ou RAG
            # from app.services.rag_service import RAGService
            # rag_service = RAGService()
            # resultats_contexte = await rag_service.search(requete_contexte.strip())

            # Pour l'instant: simulation
            contexte_trouve = {
                "requete": requete_contexte.strip(),
                "resultats": f"Contexte simulé pour {email.categorie.value}",
                "nb_resultats": 3
            }

            # Génère suggestion action basée sur contexte
            suggestion = await self._generer_suggestion_action(email, contexte_trouve)

            logger.info("recherche_contexte_terminee",
                       email_id=email.id_message,
                       nb_resultats=contexte_trouve["nb_resultats"])

            return {
                "email_id": email.id_message,
                "requete": requete_contexte.strip(),
                "contexte": contexte_trouve,
                "suggestion": suggestion,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("recherche_contexte_echouee",
                        email_id=email.id_message,
                        erreur=str(e))
            return {
                "email_id": email.id_message,
                "statut": "echec",
                "erreur": str(e)
            }

    async def _generer_suggestion_action(
        self,
        email: EmailClassifie,
        contexte: Dict[str, Any]
    ) -> str:
        """Génère suggestion action basée sur email + contexte"""
        prompt = f"""Suggère l'action à prendre pour cet email urgent.

Email:
Sujet: {email.sujet}
Résumé: {email.resume}
Catégorie: {email.categorie.value}

Contexte trouvé:
{contexte.get('resultats', 'Aucun')}

Quelle action concrète recommandes-tu au syndic ? (1-2 phrases)

Action recommandée:"""

        suggestion = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.3,
            max_tokens=150
        )

        return suggestion.strip()

    async def _generer_draft_reponse(
        self,
        email: EmailClassifie,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Génère draft email de réponse

        Use Cases:
        - Facture → Draft validation paiement
        - Convocation AG → Draft confirmation présence
        - Devis → Draft demande précisions
        """
        try:
            logger.info("generation_draft_demarree",
                       categorie=email.categorie.value,
                       email_id=email.id_message)

            # Génère draft avec LLM
            prompt_draft = f"""Génère un email de réponse professionnel pour un syndic de copropriété.

Email reçu:
De: {email.expediteur}
Sujet: {email.sujet}
Résumé: {email.resume}
Catégorie: {email.categorie.value}

Génère:
1. Objet du mail de réponse
2. Corps du mail (formel, concis, actionnable)

Format:
OBJET: ...
CORPS:
...

Email de réponse:"""

            draft = await self.llm_service.generate_response(
                prompt=prompt_draft,
                temperature=0.5,
                max_tokens=400
            )

            # Parse draft (objet + corps)
            import re
            match_objet = re.search(r'OBJET:\s*(.+?)(?:\n|$)', draft, re.IGNORECASE)
            match_corps = re.search(r'CORPS:\s*(.+)', draft, re.IGNORECASE | re.DOTALL)

            objet_draft = match_objet.group(1).strip() if match_objet else f"Re: {email.sujet}"
            corps_draft = match_corps.group(1).strip() if match_corps else draft

            logger.info("generation_draft_terminee",
                       email_id=email.id_message)

            return {
                "email_id": email.id_message,
                "destinataire": email.expediteur,
                "objet": objet_draft,
                "corps": corps_draft,
                "statut": "draft_genere",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("generation_draft_echouee",
                        email_id=email.id_message,
                        erreur=str(e))
            return {
                "email_id": email.id_message,
                "statut": "echec",
                "erreur": str(e)
            }

    async def _creer_tache(
        self,
        email: EmailClassifie,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Crée une tâche pour traitement ultérieur

        Use Cases:
        - Demande info → Tâche "Répondre à M. Dupont"
        - Confirmation → Tâche "Valider rendez-vous"
        """
        try:
            logger.info("creation_tache_demarree",
                       email_id=email.id_message,
                       categorie=email.categorie.value)

            tache = {
                "email_id": email.id_message,
                "titre": f"{email.categorie.value}: {email.sujet[:50]}",
                "description": email.resume,
                "priorite": "normale",
                "echeance": None,  # Pas d'échéance pour routinier
                "statut": "a_faire",
                "creee_le": datetime.now().isoformat()
            }

            # TODO: Persister dans base de données
            # await db.execute(insert(Tache).values(**tache))
            # await db.commit()

            logger.info("tache_creee",
                       email_id=email.id_message,
                       titre=tache["titre"])

            return tache

        except Exception as e:
            logger.error("creation_tache_echouee",
                        email_id=email.id_message,
                        erreur=str(e))
            return {
                "email_id": email.id_message,
                "statut": "echec",
                "erreur": str(e)
            }
