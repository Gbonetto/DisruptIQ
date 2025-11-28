"""
Classificateur Email Avancé - Classification intelligente des emails avec détection d'urgence
Classifie les emails en 5 niveaux d'urgence avec extraction d'entités et recommandation d'actions
"""

import structlog
import re
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

from app.services.llm_service import LLMService

logger = structlog.get_logger()


class NiveauUrgenceEmail(str, Enum):
    """Niveaux d'urgence détaillés pour classification emails"""
    CRITIQUE = "critique"        # 🚨 Action immédiate requise (< 1h) - Danger vie/dégâts majeurs
    URGENT = "urgent"            # ⚠️ Action rapide nécessaire (< 24h) - Problèmes importants
    IMPORTANT = "important"      # 📌 Action à prévoir (< 3 jours) - Critique business
    ROUTINIER = "routinier"      # 📋 Peut attendre (< 1 semaine) - Opérations normales
    FAIBLE = "faible"            # 📧 Informatif seulement - Pas d'action
    SPAM = "spam"                # 🗑️ Spam/commercial - Ignorer


class CategorieEmail(str, Enum):
    """Catégories fonctionnelles pour emails"""
    # Catégories urgences
    URGENCE_FUITE = "urgence_fuite"
    URGENCE_INCENDIE = "urgence_incendie"
    URGENCE_INTRUSION = "urgence_intrusion"
    URGENCE_ASCENSEUR = "urgence_ascenseur"
    URGENCE_ELECTRIQUE = "urgence_electrique"
    URGENCE_GAZ = "urgence_gaz"

    # Catégories opérationnelles
    PLAINTE = "plainte"
    FACTURE = "facture"
    CONVOCATION = "convocation"
    DEMANDE_INFO = "demande_info"
    TRAVAUX = "travaux"
    JURIDIQUE = "juridique"
    ADMINISTRATIF = "administratif"
    PAIEMENT = "paiement"
    DEVIS = "devis"

    # Catégories faible priorité
    COMMERCIAL = "commercial"
    NEWSLETTER = "newsletter"
    AUTRE = "autre"


class EmailClassifie(BaseModel):
    """Email classifié avec contexte enrichi"""
    id_message: str
    sujet: str
    expediteur: str
    recu_le: Optional[datetime] = None

    # Résultats classification
    urgence: NiveauUrgenceEmail
    categorie: CategorieEmail
    confiance: float  # 0.0-1.0

    # Enrichissement contextuel
    entites_detectees: Dict[str, Any] = {}  # {immeuble, appartement, proprietaire, montant, telephone}
    intention: str = ""                      # Intention utilisateur en une phrase
    action_requise: bool = False
    action_suggeree: str = ""                # Action recommandée à effectuer

    # Insights générés par IA
    resume: str = ""                         # Résumé en une phrase
    mots_cles: List[str] = []                # 3-5 termes clés
    sentiment: str = "neutre"                # positif, neutre, negatif, urgent

    # Métadonnées
    classifie_le: datetime = datetime.now()


class ClassificateurEmailAvance:
    """
    Classificateur email avancé avec détection d'urgence et enrichissement contextuel

    Workflow:
    1. Classification urgence (LLM) - critique, urgent, important, routinier, faible, spam
    2. Détection catégorie (LLM) - type urgence, catégorie opérationnelle
    3. Extraction entités (LLM) - immeuble, appartement, propriétaire, montants, dates
    4. Détection intention (LLM) - que veut l'expéditeur ?
    5. Recommandation action (LLM) - que devons-nous faire ?

    Fonctionnalités:
    - 6 niveaux d'urgence (critique à spam)
    - 20+ catégories fonctionnelles
    - Extraction entités (adresses, montants, noms, dates)
    - Analyse sentiment
    - Fallback classification par mots-clés
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("classificateur_email_avance_initialise")

    async def classifier(
        self,
        sujet: str,
        corps: str,
        expediteur: str,
        recu_le: Optional[datetime] = None,
        id_message: str = ""
    ) -> EmailClassifie:
        """
        Classifie un email avec enrichissement contextuel complet

        Args:
            sujet: Sujet de l'email
            corps: Corps de l'email
            expediteur: Adresse email expéditeur
            recu_le: Date/heure réception
            id_message: ID unique du message

        Returns:
            EmailClassifie avec urgence, catégorie, entités, actions
        """
        try:
            logger.info("classification_email_demarree",
                       sujet=sujet[:50],
                       expediteur=expediteur)

            # Tentative classification LLM d'abord
            try:
                classifie = await self._classification_llm(
                    sujet, corps, expediteur, recu_le, id_message
                )
                logger.info("classification_llm_reussie",
                           urgence=classifie.urgence.value,
                           categorie=classifie.categorie.value,
                           confiance=classifie.confiance)
                return classifie

            except Exception as erreur_llm:
                logger.warning("classification_llm_echouee_utilisation_fallback",
                             erreur=str(erreur_llm))

                # Fallback vers classification par mots-clés
                return self._classification_fallback(
                    sujet, corps, expediteur, recu_le, id_message
                )

        except Exception as e:
            logger.error("classification_email_echouee", erreur=str(e), exc_info=True)

            # Fallback ultime
            return EmailClassifie(
                id_message=id_message or "",
                sujet=sujet,
                expediteur=expediteur,
                recu_le=recu_le,
                urgence=NiveauUrgenceEmail.ROUTINIER,
                categorie=CategorieEmail.AUTRE,
                confiance=0.5,
                resume=sujet[:100],
                action_requise=False
            )

    async def _classification_llm(
        self,
        sujet: str,
        corps: str,
        expediteur: str,
        recu_le: Optional[datetime],
        id_message: str
    ) -> EmailClassifie:
        """
        Classification powered by LLM avec extraction contexte complète

        Returns:
            EmailClassifie avec tous les champs remplis
        """
        # Construction prompt complet
        prompt = f"""Tu es un expert en gestion immobilière et classification d'emails pour syndics de copropriété.

Analyse cet email et retourne un JSON structuré.

EMAIL:
Sujet: {sujet}
De: {expediteur}
Reçu le: {recu_le.strftime('%d/%m/%Y %H:%M') if recu_le else 'Inconnu'}

Corps:
{corps[:2000]}

Retourne ce JSON EXACT (tous les champs obligatoires):

{{
  "urgence": "<critique|urgent|important|routinier|faible|spam>",
  "categorie": "<voir catégories ci-dessous>",
  "confiance": <0.0-1.0>,
  "entites": {{
    "immeuble": "Nom immeuble ou adresse si mentionné",
    "appartement": "Numéro appartement si mentionné",
    "proprietaire": "Nom copropriétaire si mentionné",
    "montant": "Montant si mentionné (avec €)",
    "telephone": "Téléphone si mentionné",
    "date": "Date importante si mentionnée (format DD/MM/YYYY)"
  }},
  "intention": "Intention expéditeur en 1 phrase (ex: Signaler fuite d'eau urgente)",
  "action_requise": <true|false>,
  "action_suggeree": "Action recommandée (ex: Contacter plombier d'urgence)",
  "resume": "Résumé en 1 phrase",
  "mots_cles": ["mot1", "mot2", "mot3"],
  "sentiment": "<positif|neutre|negatif|urgent>"
}}

URGENCE:
- critique: Danger immédiat (fuite eau, incendie, intrusion, fuite gaz, danger vie)
- urgent: Problème grave (panne ascenseur, plainte sérieuse, urgence technique)
- important: Important mais pas urgent (facture, convocation AG, devis)
- routinier: Normal, peut attendre (demande info, confirmation)
- faible: Informatif uniquement (newsletter, FYI)
- spam: Commercial/publicité

CATÉGORIES:
Urgences: urgence_fuite, urgence_incendie, urgence_intrusion, urgence_ascenseur, urgence_electrique, urgence_gaz
Opérationnel: plainte, facture, convocation, demande_info, travaux, juridique, administratif, paiement, devis
Bas: commercial, newsletter, autre

RÈGLES CRITIQUES:
- Si mots "fuite", "inondation", "eau" → urgence=critique, categorie=urgence_fuite
- Si mots "incendie", "feu", "fumée" → urgence=critique, categorie=urgence_incendie
- Si mots "gaz", "odeur gaz" → urgence=critique, categorie=urgence_gaz
- Si "ascenseur bloqué", "panne ascenseur" → urgence=urgent, categorie=urgence_ascenseur
- Si "facture", "paiement", montant → urgence=important, categorie=facture

Retourne UNIQUEMENT le JSON, rien d'autre.

JSON:"""

        # Appel LLM
        reponse = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.0,
            max_tokens=800
        )

        # Parse JSON
        import json
        json_match = re.search(r'\{.*\}', reponse, re.DOTALL)
        if not json_match:
            raise ValueError("Pas de JSON valide dans réponse LLM")

        donnees_classification = json.loads(json_match.group())

        # Construction EmailClassifie
        classifie = EmailClassifie(
            id_message=id_message or "",
            sujet=sujet,
            expediteur=expediteur,
            recu_le=recu_le or datetime.now(),

            urgence=NiveauUrgenceEmail(donnees_classification.get("urgence", "routinier")),
            categorie=CategorieEmail(donnees_classification.get("categorie", "autre")),
            confiance=float(donnees_classification.get("confiance", 0.8)),

            entites_detectees=donnees_classification.get("entites", {}),
            intention=donnees_classification.get("intention", ""),
            action_requise=bool(donnees_classification.get("action_requise", False)),
            action_suggeree=donnees_classification.get("action_suggeree", ""),

            resume=donnees_classification.get("resume", sujet[:100]),
            mots_cles=donnees_classification.get("mots_cles", []),
            sentiment=donnees_classification.get("sentiment", "neutre"),

            classifie_le=datetime.now()
        )

        return classifie

    def _classification_fallback(
        self,
        sujet: str,
        corps: str,
        expediteur: str,
        recu_le: Optional[datetime],
        id_message: str
    ) -> EmailClassifie:
        """
        Classification fallback par mots-clés quand LLM échoue

        Args:
            sujet, corps, expediteur, recu_le, id_message

        Returns:
            EmailClassifie avec classification basique
        """
        texte_lower = (sujet + " " + corps).lower()

        # Initialisation classification
        urgence = NiveauUrgenceEmail.ROUTINIER
        categorie = CategorieEmail.AUTRE
        action = "Traiter selon priorité"
        confiance = 0.65  # Confiance moyenne pour mots-clés

        # Urgences CRITIQUES (priorité maximale)
        if any(mc in texte_lower for mc in ["fuite", "inondation", "dégât des eaux", "eau partout"]):
            urgence = NiveauUrgenceEmail.CRITIQUE
            categorie = CategorieEmail.URGENCE_FUITE
            action = "Contacter plombier d'urgence immédiatement"

        elif any(mc in texte_lower for mc in ["incendie", "feu", "fumée", "brûle", "flamme"]):
            urgence = NiveauUrgenceEmail.CRITIQUE
            categorie = CategorieEmail.URGENCE_INCENDIE
            action = "Appeler pompiers 18 immédiatement"

        elif any(mc in texte_lower for mc in ["gaz", "odeur de gaz", "fuite gaz"]):
            urgence = NiveauUrgenceEmail.CRITIQUE
            categorie = CategorieEmail.URGENCE_GAZ
            action = "Évacuer et appeler pompiers 18"

        elif any(mc in texte_lower for mc in ["cambriolage", "intrusion", "vol", "effraction", "voleur"]):
            urgence = NiveauUrgenceEmail.CRITIQUE
            categorie = CategorieEmail.URGENCE_INTRUSION
            action = "Contacter police 17 et sécurité"

        # URGENT (réponse 24h nécessaire)
        elif any(mc in texte_lower for mc in ["ascenseur", "bloqué dans", "coincé", "panne ascenseur"]):
            urgence = NiveauUrgenceEmail.URGENT
            categorie = CategorieEmail.URGENCE_ASCENSEUR
            action = "Appeler technicien ascenseur d'urgence"

        elif any(mc in texte_lower for mc in ["panne électrique", "coupure", "plus d'électricité", "noir"]):
            urgence = NiveauUrgenceEmail.URGENT
            categorie = CategorieEmail.URGENCE_ELECTRIQUE
            action = "Contacter électricien et vérifier compteur"

        elif any(mc in texte_lower for mc in ["plainte", "me plaindre", "inacceptable", "scandaleux"]):
            urgence = NiveauUrgenceEmail.URGENT
            categorie = CategorieEmail.PLAINTE
            action = "Répondre sous 24h et traiter la plainte"

        # IMPORTANT (réponse 3 jours)
        elif any(mc in texte_lower for mc in ["facture", "paiement", "montant", "€", "eur", "prix"]):
            urgence = NiveauUrgenceEmail.IMPORTANT
            categorie = CategorieEmail.FACTURE
            action = "Vérifier facture et valider paiement"

        elif any(mc in texte_lower for mc in ["assemblée générale", "ag ", "convocation", "réunion"]):
            urgence = NiveauUrgenceEmail.IMPORTANT
            categorie = CategorieEmail.CONVOCATION
            action = "Préparer convocation et documents AG"

        elif any(mc in texte_lower for mc in ["devis", "estimation", "cotation"]):
            urgence = NiveauUrgenceEmail.IMPORTANT
            categorie = CategorieEmail.DEVIS
            action = "Analyser devis et demander précisions si besoin"

        elif any(mc in texte_lower for mc in ["travaux", "rénovation", "réparation"]):
            urgence = NiveauUrgenceEmail.IMPORTANT
            categorie = CategorieEmail.TRAVAUX
            action = "Planifier travaux et informer copropriétaires"

        # ROUTINIER
        elif any(mc in texte_lower for mc in ["information", "demande", "question", "renseignement"]):
            urgence = NiveauUrgenceEmail.ROUTINIER
            categorie = CategorieEmail.DEMANDE_INFO
            action = "Répondre dans la semaine"

        # FAIBLE / SPAM
        elif any(mc in texte_lower for mc in ["newsletter", "abonnement", "désabonner", "unsubscribe"]):
            urgence = NiveauUrgenceEmail.FAIBLE
            categorie = CategorieEmail.NEWSLETTER
            action = "Archiver ou supprimer"

        elif any(mc in texte_lower for mc in ["publicité", "promotion", "offre spéciale", "réduction"]):
            urgence = NiveauUrgenceEmail.SPAM
            categorie = CategorieEmail.COMMERCIAL
            action = "Marquer comme spam"

        # Extraction entités basiques (regex)
        entites = self._extraire_entites_regex(sujet + " " + corps)

        # Construction EmailClassifie
        classifie = EmailClassifie(
            id_message=id_message or "",
            sujet=sujet,
            expediteur=expediteur,
            recu_le=recu_le or datetime.now(),

            urgence=urgence,
            categorie=categorie,
            confiance=confiance,

            entites_detectees=entites,
            intention=f"Classification automatique par mots-clés: {categorie.value}",
            action_requise=urgence in [NiveauUrgenceEmail.CRITIQUE, NiveauUrgenceEmail.URGENT],
            action_suggeree=action,

            resume=sujet[:100],
            mots_cles=self._extraire_mots_cles_regex(texte_lower),
            sentiment="urgent" if urgence in [NiveauUrgenceEmail.CRITIQUE, NiveauUrgenceEmail.URGENT] else "neutre",

            classifie_le=datetime.now()
        )

        logger.info("classification_fallback_reussie",
                   urgence=urgence.value,
                   categorie=categorie.value,
                   methode="mots-cles")

        return classifie

    def _extraire_entites_regex(self, texte: str) -> Dict[str, Any]:
        """Extrait les entités en utilisant patterns regex"""
        entites = {}

        # Extraction montants (€ ou EUR)
        pattern_montant = r'(\d+(?:[.,]\d{1,2})?)\s*(?:€|EUR|euros?)'
        montants = re.findall(pattern_montant, texte, re.IGNORECASE)
        if montants:
            entites["montant"] = montants[0] + " €"

        # Extraction numéros téléphone (format français)
        pattern_tel = r'0[1-9](?:[\s.-]?\d{2}){4}'
        telephones = re.findall(pattern_tel, texte)
        if telephones:
            entites["telephone"] = telephones[0]

        # Extraction dates (DD/MM/YYYY ou DD-MM-YYYY)
        pattern_date = r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b'
        dates = re.findall(pattern_date, texte)
        if dates:
            entites["date"] = dates[0]

        # Extraction numéros appartement (patterns courants)
        pattern_appt = r'(?:appartement|appt?\.?|n°)\s*(\d+[A-Z]?)'
        appartements = re.findall(pattern_appt, texte, re.IGNORECASE)
        if appartements:
            entites["appartement"] = appartements[0]

        return entites

    def _extraire_mots_cles_regex(self, texte_lower: str) -> List[str]:
        """Extrait 3-5 termes clés du texte"""
        # Extraction mots-clés simple: mots les plus fréquents
        mots = re.findall(r'\b[a-zàâäéèêëïîôùûü]{4,}\b', texte_lower)

        # Comptage fréquence
        from collections import Counter
        comptage_mots = Counter(mots)

        # Top 5 plus fréquents (exclusion stopwords)
        stopwords = {'pour', 'dans', 'avec', 'cette', 'plus', 'être', 'faire', 'tout', 'tous'}
        mots_cles = [
            mot for mot, _ in comptage_mots.most_common(10)
            if mot not in stopwords
        ][:5]

        return mots_cles

    async def classifier_batch(
        self,
        emails: List[Dict[str, str]],
        taille_batch: int = 20
    ) -> List[EmailClassifie]:
        """
        Classification batch de plusieurs emails efficacement

        Plus efficace que classifier un par un:
        - 50 emails individuellement = 50 appels LLM = 0.15€
        - 50 emails batch (20 par appel) = 3 appels LLM = 0.009€ (-94% coût!)

        Args:
            emails: Liste de dicts avec {sujet, corps, expediteur, id_message}
            taille_batch: Nombre d'emails par appel LLM (max 20 recommandé)

        Returns:
            Liste EmailClassifie dans même ordre que l'input
        """
        logger.info("classification_batch_demarree",
                   total_emails=len(emails),
                   taille_batch=taille_batch)

        resultats_classifies = []

        # Traiter par batches
        for i in range(0, len(emails), taille_batch):
            batch = emails[i:i + taille_batch]

            try:
                # Construction prompt batch (toujours indexer 1,2,3... par batch)
                donnees_batch = "\n\n".join([
                    f"EMAIL {idx}:\nSujet: {email.get('sujet', '')}\nDe: {email.get('expediteur', '')}\nCorps: {email.get('corps', '')[:500]}"
                    for idx, email in enumerate(batch, start=1)
                ])

                prompt = f"""Classifie ces {len(batch)} emails.

{donnees_batch}

Retourne un JSON array avec les classifications:

[
  {{
    "id_email": 1,
    "urgence": "critique",
    "categorie": "urgence_fuite",
    "confiance": 0.95,
    "resume": "...",
    "action_requise": true,
    "action_suggeree": "..."
  }},
  ...
]

Retourne UNIQUEMENT le JSON array.

JSON:"""

                reponse = await self.llm_service.generate_response(
                    prompt=prompt,
                    temperature=0.0,
                    max_tokens=2000
                )

                # Parse résultats batch
                import json
                json_match = re.search(r'\[.*\]', reponse, re.DOTALL)
                if json_match:
                    resultats_batch = json.loads(json_match.group())

                    # Vérifier cohérence nombre de résultats
                    if len(resultats_batch) != len(batch):
                        logger.warning("classification_batch_nombre_incoherent",
                                     attendu=len(batch),
                                     recu=len(resultats_batch),
                                     batch_index=i)

                        # Si plus de résultats que d'emails, tronquer
                        if len(resultats_batch) > len(batch):
                            logger.warning("batch_resultats_tronques",
                                         de=len(resultats_batch),
                                         a=len(batch))
                            resultats_batch = resultats_batch[:len(batch)]
                        # Si moins de résultats, lever erreur pour utiliser fallback
                        else:
                            raise ValueError(f"LLM a retourné {len(resultats_batch)} résultats au lieu de {len(batch)}")

                    # Mapper vers objets EmailClassifie complets
                    emails_traites_batch = 0
                    for email, resultat in zip(batch, resultats_batch):
                        classifie = EmailClassifie(
                            id_message=email.get('id_message', ''),
                            sujet=email.get('sujet', ''),
                            expediteur=email.get('expediteur', ''),
                            recu_le=email.get('recu_le'),
                            urgence=NiveauUrgenceEmail(resultat.get('urgence', 'routinier')),
                            categorie=CategorieEmail(resultat.get('categorie', 'autre')),
                            confiance=resultat.get('confiance', 0.8),
                            resume=resultat.get('resume', ''),
                            action_requise=resultat.get('action_requise', False),
                            action_suggeree=resultat.get('action_suggeree', ''),
                            classifie_le=datetime.now()
                        )
                        resultats_classifies.append(classifie)
                        emails_traites_batch += 1

                    logger.info("batch_traite_avec_succes",
                               batch_index=i,
                               emails_traites=emails_traites_batch)
                else:
                    raise ValueError("Pas de JSON array dans réponse batch")

            except Exception as e:
                logger.error("classification_batch_echouee_pour_batch",
                           debut_batch=i,
                           erreur=str(e))

                # Fallback: classifier chaque email individuellement
                for email in batch:
                    classifie = await self.classifier(
                        sujet=email.get('sujet', ''),
                        corps=email.get('corps', ''),
                        expediteur=email.get('expediteur', ''),
                        id_message=email.get('id_message', '')
                    )
                    resultats_classifies.append(classifie)

        logger.info("classification_batch_terminee",
                   total_classifies=len(resultats_classifies))

        return resultats_classifies
