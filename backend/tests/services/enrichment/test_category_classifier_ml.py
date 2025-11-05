"""
Tests for CategoryClassifier with ML model
"""

import pytest
import pickle
import tempfile
from pathlib import Path

from app.services.enrichment.category_classifier import CategoryClassifier
from app.models.enrichment import ClassificationMethod


class TestCategoryClassifierKeyword:
    """Test keyword-based classification (fallback mode)"""

    def test_classify_plomberie(self):
        """Should classify plomberie text correctly"""
        classifier = CategoryClassifier()  # No model loaded

        text = "Réparation fuite robinet cuisine. Intervention plombier urgence."
        result = classifier.classify(text)

        assert result.predicted_category == "Plomberie"
        assert result.method == ClassificationMethod.KEYWORD
        assert result.confidence > 0.6

    def test_classify_electricite(self):
        """Should classify electricité text correctly"""
        classifier = CategoryClassifier()

        text = "Mise aux normes tableau électrique. Installation disjoncteurs."
        result = classifier.classify(text)

        assert result.predicted_category == "Électricité"
        assert result.method == ClassificationMethod.KEYWORD

    def test_classify_chauffage(self):
        """Should classify chauffage text correctly"""
        classifier = CategoryClassifier()

        text = "Entretien annuel chaudière gaz. Contrôle combustion chauffagiste."
        result = classifier.classify(text)

        assert result.predicted_category == "Chauffage"
        assert result.method == ClassificationMethod.KEYWORD

    def test_classify_nettoyage(self):
        """Should classify nettoyage text correctly"""
        classifier = CategoryClassifier()

        text = "Nettoyage parties communes. Lavage sols escaliers. Ménage."
        result = classifier.classify(text)

        assert result.predicted_category == "Nettoyage"
        assert result.method == ClassificationMethod.KEYWORD

    def test_classify_assurance(self):
        """Should classify assurance text correctly"""
        classifier = CategoryClassifier()

        text = "Prime assurance multirisque immeuble. Cotisation annuelle."
        result = classifier.classify(text)

        assert result.predicted_category == "Assurance"
        assert result.method == ClassificationMethod.KEYWORD

    def test_classify_ambiguous_defaults_to_divers(self):
        """Should default to Divers for ambiguous text"""
        classifier = CategoryClassifier()

        text = "Facture pour prestations diverses"
        result = classifier.classify(text)

        assert result.predicted_category == "Divers"
        assert result.confidence < 0.7  # Low confidence

    def test_top_predictions_returned(self):
        """Should return top predictions"""
        classifier = CategoryClassifier()

        text = "Réparation plomberie robinet fuite eau"
        result = classifier.classify(text)

        assert len(result.top_predictions) > 0
        assert result.top_predictions[0][0] == "Plomberie"
        # Scores should be in descending order
        scores = [score for _, score in result.top_predictions]
        assert scores == sorted(scores, reverse=True)

    def test_case_insensitive(self):
        """Should be case insensitive"""
        classifier = CategoryClassifier()

        text1 = "PLOMBIER ROBINET FUITE"
        text2 = "plombier robinet fuite"

        result1 = classifier.classify(text1)
        result2 = classifier.classify(text2)

        assert result1.predicted_category == result2.predicted_category

    def test_empty_text_defaults_to_divers(self):
        """Should handle empty text"""
        classifier = CategoryClassifier()

        result = classifier.classify("")

        assert result.predicted_category == "Divers"
        assert result.method == ClassificationMethod.KEYWORD


class TestCategoryClassifierML:
    """Test ML-based classification"""

    def test_load_model_from_path(self, mock_ml_model):
        """Should load ML model from specified paths"""
        model_path, vectorizer_path = mock_ml_model

        classifier = CategoryClassifier(
            model_path=str(model_path),
            vectorizer_path=str(vectorizer_path)
        )

        # Model should be loaded
        assert classifier.model is not None
        assert classifier.vectorizer is not None

    def test_classify_with_ml_model(self, mock_ml_model):
        """Should use ML model when available"""
        model_path, vectorizer_path = mock_ml_model

        classifier = CategoryClassifier(
            model_path=str(model_path),
            vectorizer_path=str(vectorizer_path)
        )

        text = "Réparation plomberie robinet fuite"
        result = classifier.classify(text)

        # Should use ML method
        assert result.method == ClassificationMethod.ML
        assert result.confidence > 0.0
        assert len(result.top_predictions) == 3  # Top 3

    def test_ml_failure_falls_back_to_keyword(self, broken_ml_model):
        """Should fall back to keywords if ML fails"""
        model_path, vectorizer_path = broken_ml_model

        classifier = CategoryClassifier(
            model_path=str(model_path),
            vectorizer_path=str(vectorizer_path)
        )

        text = "Réparation plomberie robinet fuite"
        result = classifier.classify(text)

        # Should fall back to keyword method
        assert result.method == ClassificationMethod.KEYWORD

    def test_nonexistent_model_uses_keyword(self):
        """Should use keyword method if model files don't exist"""
        classifier = CategoryClassifier(
            model_path="/nonexistent/model.pkl",
            vectorizer_path="/nonexistent/vectorizer.pkl"
        )

        assert classifier.model is None
        assert classifier.vectorizer is None

        text = "Réparation plomberie"
        result = classifier.classify(text)

        assert result.method == ClassificationMethod.KEYWORD

    def test_get_default_instance(self):
        """Should create default instance"""
        classifier = CategoryClassifier.get_default_instance()

        assert classifier is not None
        # Model may or may not be loaded depending on whether
        # models/ directory has trained models


# Pytest fixtures

@pytest.fixture
def mock_ml_model():
    """
    Create a mock ML model and vectorizer for testing.

    Returns:
        Tuple of (model_path, vectorizer_path)
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB

    # Create sample data
    texts = [
        "plombier robinet fuite eau",
        "plomberie tuyau canalisation",
        "électricien tableau disjoncteur",
        "électricité prise interrupteur",
        "chauffage chaudière radiateur",
        "chauffagiste pompe chaleur"
    ]
    labels = [
        "Plomberie",
        "Plomberie",
        "Électricité",
        "Électricité",
        "Chauffage",
        "Chauffage"
    ]

    # Train vectorizer
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(texts)

    # Train classifier
    classifier = MultinomialNB()
    classifier.fit(X, labels)

    # Save to temp files
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as f:
        pickle.dump(classifier, f)
        model_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as f:
        pickle.dump(vectorizer, f)
        vectorizer_path = Path(f.name)

    yield model_path, vectorizer_path

    # Cleanup
    model_path.unlink()
    vectorizer_path.unlink()


@pytest.fixture
def broken_ml_model():
    """
    Create broken ML model files that will fail on load.

    Returns:
        Tuple of (model_path, vectorizer_path)
    """
    # Create files with invalid pickle data
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pkl') as f:
        f.write("INVALID PICKLE DATA")
        model_path = Path(f.name)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pkl') as f:
        f.write("INVALID PICKLE DATA")
        vectorizer_path = Path(f.name)

    yield model_path, vectorizer_path

    # Cleanup
    model_path.unlink()
    vectorizer_path.unlink()
