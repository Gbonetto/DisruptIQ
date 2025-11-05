"""
Category Classifier Service

Classifies invoices into categories using:
1. ML model (TF-IDF + Naive Bayes) - preferred
2. Keyword-based rules - fallback
"""

import os
import pickle
from typing import Optional, List, Tuple, Dict
from pathlib import Path

from app.models.enrichment import (
    CategoryPrediction,
    ClassificationMethod
)
import structlog

logger = structlog.get_logger(__name__)


# Category keywords for rule-based classification
CATEGORY_KEYWORDS = {
    "Plomberie": [
        "plombier", "plomberie", "fuite", "robinet", "canalisation",
        "tuyau", "eau", "sanitaire", "wc", "chasse d'eau", "évier",
        "lavabo", "douche", "baignoire", "cumulus", "chauffe-eau"
    ],
    "Électricité": [
        "électricien", "électrique", "électricité", "tableau électrique",
        "disjoncteur", "prise", "interrupteur", "câblage", "luminaire",
        "lampe", "éclairage", "ampoule", "compteur", "fusible"
    ],
    "Chauffage": [
        "chauffage", "chaudière", "radiateur", "thermique", "climatisation",
        "clim", "ventilation", "vmc", "chauffagiste", "gaz", "fioul",
        "pompe à chaleur", "pac"
    ],
    "Jardinage": [
        "jardin", "jardinage", "jardinier", "paysagiste", "tondeuse",
        "tonte", "pelouse", "haie", "taille", "élagage", "arbre",
        "espaces verts", "végétaux", "plantation"
    ],
    "Nettoyage": [
        "nettoyage", "ménage", "entretien", "propreté", "balayage",
        "lavage", "vitre", "sol", "poubelle", "déchets", "désinfection",
        "hygiène"
    ],
    "Ascenseur": [
        "ascenseur", "monte-charge", "élévateur", "cabine", "maintenance ascenseur",
        "otis", "schindler", "kone", "thyssenkrupp"
    ],
    "Serrurerie": [
        "serrure", "serrurier", "porte", "clé", "verrou", "blindage",
        "cylindre", "cadenas", "portail", "gâche"
    ],
    "Peinture": [
        "peinture", "peintre", "ravalement", "façade", "crépi",
        "enduit", "papier peint", "tapisserie", "décoration"
    ],
    "Toiture": [
        "toiture", "couvreur", "toit", "tuile", "ardoise", "charpente",
        "gouttière", "zinguerie", "étanchéité", "isolation toiture"
    ],
    "Assurance": [
        "assurance", "prime", "cotisation", "contrat", "police",
        "sinistre", "garantie", "responsabilité civile", "multirisque",
        "dommages", "maif", "axa", "allianz", "groupama"
    ],
    "Juridique": [
        "avocat", "notaire", "juridique", "tribunal", "contentieux",
        "procès", "huissier", "assignation", "conseil syndical"
    ],
    "Comptabilité": [
        "comptable", "expert-comptable", "comptabilité", "bilan",
        "audit", "fiscalité", "honoraires", "cabinet"
    ],
    "Divers": [
        "autre", "divers", "frais", "prestation"
    ]
}


def normalize_text(text: str) -> str:
    """Normalize text for classification: lowercase and strip"""
    return text.lower().strip() if text else ""


class CategoryClassifier:
    """
    Service for classifying invoices into categories.

    Uses ML model if available, falls back to keyword matching.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        vectorizer_path: Optional[str] = None
    ):
        """
        Initialize category classifier.

        Args:
            model_path: Path to trained ML model (pickle file)
            vectorizer_path: Path to fitted TF-IDF vectorizer (pickle file)
        """
        self.logger = logger.bind(service="category_classifier")

        # Try to load ML model if paths provided
        self.model = None
        self.vectorizer = None

        if model_path and vectorizer_path:
            self._load_model(model_path, vectorizer_path)

        # If no model loaded, will use keyword fallback
        if self.model is None:
            self.logger.info("ml_model_not_loaded_using_keyword_fallback")

    def _load_model(self, model_path: str, vectorizer_path: str):
        """
        Load trained ML model and vectorizer from disk.

        Args:
            model_path: Path to model pickle file
            vectorizer_path: Path to vectorizer pickle file
        """
        try:
            if os.path.exists(model_path) and os.path.exists(vectorizer_path):
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)

                with open(vectorizer_path, 'rb') as f:
                    self.vectorizer = pickle.load(f)

                self.logger.info(
                    "ml_model_loaded",
                    model_path=model_path,
                    vectorizer_path=vectorizer_path
                )
            else:
                self.logger.warning(
                    "ml_model_files_not_found",
                    model_path=model_path,
                    vectorizer_path=vectorizer_path
                )
        except Exception as e:
            self.logger.error(
                "ml_model_load_failed",
                error=str(e),
                model_path=model_path
            )
            self.model = None
            self.vectorizer = None

    def classify(
        self,
        text: str,
        existing_category: Optional[str] = None
    ) -> CategoryPrediction:
        """
        Classify invoice text into a category.

        Args:
            text: Invoice text (raw OCR output or article descriptions)
            existing_category: Existing category if already set

        Returns:
            CategoryPrediction with predicted category and confidence
        """
        # If model is available, use ML
        if self.model and self.vectorizer:
            return self._classify_ml(text)
        else:
            # Fall back to keyword-based classification
            return self._classify_keywords(text)

    def _classify_ml(self, text: str) -> CategoryPrediction:
        """
        Classify using ML model (TF-IDF + Naive Bayes).

        Args:
            text: Invoice text

        Returns:
            CategoryPrediction with ML predictions
        """
        try:
            # Vectorize text
            text_vectorized = self.vectorizer.transform([normalize_text(text)])

            # Predict probabilities
            probabilities = self.model.predict_proba(text_vectorized)[0]
            classes = self.model.classes_

            # Get top predictions
            top_indices = probabilities.argsort()[::-1][:3]  # Top 3
            top_predictions = [
                (classes[i], float(probabilities[i]))
                for i in top_indices
            ]

            # Best prediction
            best_category = classes[top_indices[0]]
            best_confidence = float(probabilities[top_indices[0]])

            self.logger.info(
                "ml_classification",
                category=best_category,
                confidence=best_confidence
            )

            return CategoryPrediction(
                predicted_category=best_category,
                confidence=best_confidence,
                method=ClassificationMethod.ML,
                top_predictions=top_predictions,
                metadata={"model": "naive_bayes"}
            )

        except Exception as e:
            self.logger.error(
                "ml_classification_failed",
                error=str(e)
            )
            # Fall back to keywords
            return self._classify_keywords(text)

    def _classify_keywords(self, text: str) -> CategoryPrediction:
        """
        Classify using keyword matching (rule-based fallback).

        Args:
            text: Invoice text

        Returns:
            CategoryPrediction with keyword-based predictions
        """
        text_normalized = normalize_text(text)

        # Count keyword matches for each category
        category_scores: Dict[str, int] = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text_normalized:
                    score += 1

            if score > 0:
                category_scores[category] = score

        # If no matches, return "Divers"
        if not category_scores:
            self.logger.info(
                "keyword_classification_no_match",
                default_category="Divers"
            )
            return CategoryPrediction(
                predicted_category="Divers",
                confidence=0.5,  # Low confidence for default
                method=ClassificationMethod.KEYWORD,
                top_predictions=[("Divers", 0.5)],
                metadata={"matches": 0}
            )

        # Sort by score descending
        sorted_categories = sorted(
            category_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Calculate confidence based on score ratio
        best_category, best_score = sorted_categories[0]
        total_score = sum(category_scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.0

        # Normalize confidence to 0.6-0.9 range for keyword matching
        # (never 1.0 since it's not as reliable as ML)
        confidence = 0.6 + (confidence * 0.3)

        # Get top 3 predictions
        top_predictions = [
            (cat, (score / total_score * 0.3 + 0.6))
            for cat, score in sorted_categories[:3]
        ]

        self.logger.info(
            "keyword_classification",
            category=best_category,
            confidence=confidence,
            matches=best_score
        )

        return CategoryPrediction(
            predicted_category=best_category,
            confidence=confidence,
            method=ClassificationMethod.KEYWORD,
            top_predictions=top_predictions,
            metadata={
                "keyword_matches": best_score,
                "total_matches": total_score
            }
        )

    @classmethod
    def get_default_instance(cls) -> "CategoryClassifier":
        """
        Get default classifier instance with model loading from default paths.

        Returns:
            CategoryClassifier instance
        """
        # Default model paths
        base_dir = Path(__file__).parent.parent.parent.parent
        model_path = base_dir / "models" / "category_classifier.pkl"
        vectorizer_path = base_dir / "models" / "category_vectorizer.pkl"

        return cls(
            model_path=str(model_path) if model_path.exists() else None,
            vectorizer_path=str(vectorizer_path) if vectorizer_path.exists() else None
        )
