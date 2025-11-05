"""
Email Category Enum
Extended categorization for intelligent email classification
"""

import enum


class EmailCategory(str, enum.Enum):
    """
    Email category classification

    Catégories multi-dimension pour classification intelligente
    Utilisé dans Email.category et Email.llm_analysis['category']
    """

    # Fournisseurs / Prestataires
    DEVIS_FOURNISSEUR = "devis_fournisseur"
    FACTURE_FOURNISSEUR = "facture_fournisseur"
    TRAVAUX_PLANIFICATION = "travaux_planification"
    INTERVENTION_URGENTE = "intervention_urgente"

    # Copropriétaires
    RECLAMATION_COPROPRIETAIRE = "reclamation_coproprietaire"
    QUESTION_COPROPRIETAIRE = "question_coproprietaire"
    PAIEMENT_CHARGES = "paiement_charges"

    # Administration
    ASSEMBLEE_GENERALE = "assemblee_generale"
    VOTE_DECISION = "vote_decision"
    DOCUMENT_ADMINISTRATIF = "document_administratif"

    # Finances
    COMPTABILITE = "comptabilite"
    BUDGET = "budget"
    PAIEMENT = "paiement"

    # Autres
    INFORMATION = "information"
    SPAM = "spam"
    AUTRE = "autre"


class EmailSentiment(str, enum.Enum):
    """Sentiment analysis for emails"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ANGRY = "angry"
