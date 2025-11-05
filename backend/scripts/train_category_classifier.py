#!/usr/bin/env python3
"""
Train Category Classifier for Invoice Categorization

This script trains a machine learning model to classify invoices into categories
based on the raw OCR text extracted from invoices.

Process:
1. Load validated invoices from database
2. Extract text and categories
3. Train TF-IDF vectorizer + Naive Bayes classifier
4. Perform cross-validation
5. Generate evaluation metrics
6. Save model, vectorizer, and metrics

Usage:
    python scripts/train_category_classifier.py --min-samples 5
    python scripts/train_category_classifier.py --min-samples 10 --test-split 0.2
"""

import asyncio
import argparse
import pickle
import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)
import numpy as np

# Database imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_
from app.core.database import AsyncSessionLocal
from app.models.invoice import FactureGlobal, FactureStatut
import structlog

logger = structlog.get_logger()


async def load_training_data(
    min_samples_per_category: int = 5
) -> Tuple[List[str], List[str]]:
    """
    Load training data from validated invoices.

    Args:
        min_samples_per_category: Minimum samples required per category

    Returns:
        Tuple of (texts, labels) where:
        - texts: List of raw OCR text from invoices
        - labels: List of corresponding categories
    """
    logger.info("loading_training_data", min_samples=min_samples_per_category)

    async with AsyncSessionLocal() as db:
        # Query validated invoices with category and raw text
        query = select(FactureGlobal).where(
            and_(
                FactureGlobal.statut == FactureStatut.VALIDEE.value,
                FactureGlobal.categorie.isnot(None),
                FactureGlobal.metadata_json.isnot(None)
            )
        )

        result = await db.execute(query)
        invoices = result.scalars().all()

    logger.info("invoices_loaded", count=len(invoices))

    # Extract texts and labels
    texts = []
    labels = []

    for invoice in invoices:
        # Extract raw_text from metadata
        metadata = invoice.metadata_json or {}
        raw_text = metadata.get("raw_text", "")

        # Skip if no text available
        if not raw_text or not raw_text.strip():
            continue

        texts.append(raw_text)
        labels.append(invoice.categorie)

    logger.info(
        "data_extracted",
        total_samples=len(texts),
        unique_categories=len(set(labels))
    )

    # Count samples per category
    category_counts = Counter(labels)
    logger.info("category_distribution", counts=dict(category_counts))

    # Filter out categories with too few samples
    valid_categories = {
        cat for cat, count in category_counts.items()
        if count >= min_samples_per_category
    }

    if not valid_categories:
        logger.error(
            "insufficient_samples",
            min_samples=min_samples_per_category,
            categories=dict(category_counts)
        )
        raise ValueError(
            f"No categories have at least {min_samples_per_category} samples. "
            f"Current counts: {dict(category_counts)}"
        )

    # Filter data to only include valid categories
    filtered_texts = []
    filtered_labels = []

    for text, label in zip(texts, labels):
        if label in valid_categories:
            filtered_texts.append(text)
            filtered_labels.append(label)

    removed_count = len(texts) - len(filtered_texts)
    if removed_count > 0:
        logger.info(
            "filtered_categories",
            removed_samples=removed_count,
            remaining_samples=len(filtered_texts),
            valid_categories=sorted(valid_categories)
        )

    return filtered_texts, filtered_labels


def train_classifier(
    texts: List[str],
    labels: List[str],
    test_size: float = 0.2,
    random_state: int = 42
) -> Tuple[TfidfVectorizer, MultinomialNB, Dict]:
    """
    Train TF-IDF vectorizer and Naive Bayes classifier.

    Args:
        texts: List of training texts
        labels: List of corresponding labels
        test_size: Fraction of data to use for testing
        random_state: Random seed for reproducibility

    Returns:
        Tuple of (vectorizer, classifier, metrics)
    """
    logger.info("training_classifier", samples=len(texts), test_size=test_size)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels  # Maintain class distribution
    )

    logger.info(
        "data_split",
        train_samples=len(X_train),
        test_samples=len(X_test)
    )

    # Create and fit TF-IDF vectorizer
    vectorizer = TfidfVectorizer(
        max_features=5000,      # Limit vocabulary size
        ngram_range=(1, 2),     # Unigrams and bigrams
        min_df=2,               # Ignore terms that appear in < 2 documents
        max_df=0.8,             # Ignore terms that appear in > 80% of documents
        stop_words='french',    # Remove French stopwords
        lowercase=True,
        strip_accents='unicode'
    )

    logger.info("fitting_vectorizer")
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    logger.info(
        "vectorizer_fitted",
        vocabulary_size=len(vectorizer.vocabulary_),
        features=X_train_vec.shape[1]
    )

    # Train Naive Bayes classifier
    classifier = MultinomialNB(alpha=1.0)  # Laplace smoothing

    logger.info("fitting_classifier")
    classifier.fit(X_train_vec, y_train)

    # Make predictions
    y_pred = classifier.predict(X_test_vec)

    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    logger.info(
        "classifier_trained",
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1
    )

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred, labels=classifier.classes_)

    # Cross-validation (5-fold)
    logger.info("running_cross_validation")
    X_all_vec = vectorizer.transform(texts)
    cv_scores = cross_val_score(
        classifier,
        X_all_vec,
        labels,
        cv=5,
        scoring='accuracy'
    )

    logger.info(
        "cross_validation_complete",
        cv_mean=cv_scores.mean(),
        cv_std=cv_scores.std(),
        cv_scores=cv_scores.tolist()
    )

    # Detailed classification report
    report = classification_report(
        y_test,
        y_pred,
        labels=classifier.classes_,
        output_dict=True,
        zero_division=0
    )

    # Samples per category in test set
    test_category_counts = Counter(y_test)

    # Compile metrics
    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "cross_validation": {
            "mean": float(cv_scores.mean()),
            "std": float(cv_scores.std()),
            "scores": [float(s) for s in cv_scores]
        },
        "samples_per_category": dict(Counter(labels)),
        "test_samples_per_category": dict(test_category_counts),
        "categories": sorted(classifier.classes_.tolist()),
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "training_date": datetime.utcnow().isoformat(),
        "total_samples": len(texts),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "vocabulary_size": len(vectorizer.vocabulary_)
    }

    return vectorizer, classifier, metrics


def save_model(
    vectorizer: TfidfVectorizer,
    classifier: MultinomialNB,
    metrics: Dict,
    output_dir: Path
):
    """
    Save trained model, vectorizer, and metrics to disk.

    Args:
        vectorizer: Fitted TF-IDF vectorizer
        classifier: Trained classifier
        metrics: Training metrics
        output_dir: Directory to save files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save vectorizer
    vectorizer_path = output_dir / "category_vectorizer.pkl"
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)
    logger.info("vectorizer_saved", path=str(vectorizer_path))

    # Save classifier
    classifier_path = output_dir / "category_classifier.pkl"
    with open(classifier_path, 'wb') as f:
        pickle.dump(classifier, f)
    logger.info("classifier_saved", path=str(classifier_path))

    # Save metrics
    metrics_path = output_dir / "training_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info("metrics_saved", path=str(metrics_path))

    # Print summary
    print("\n" + "="*60)
    print("✅ MODEL TRAINING COMPLETE")
    print("="*60)
    print(f"\n📊 Performance Metrics:")
    print(f"  Accuracy:  {metrics['accuracy']:.3f}")
    print(f"  Precision: {metrics['precision']:.3f}")
    print(f"  Recall:    {metrics['recall']:.3f}")
    print(f"  F1 Score:  {metrics['f1_score']:.3f}")
    print(f"\n🔄 Cross-Validation (5-fold):")
    print(f"  Mean Accuracy: {metrics['cross_validation']['mean']:.3f}")
    print(f"  Std Dev:       {metrics['cross_validation']['std']:.3f}")
    print(f"\n📚 Training Data:")
    print(f"  Total Samples:      {metrics['total_samples']}")
    print(f"  Training Samples:   {metrics['train_samples']}")
    print(f"  Test Samples:       {metrics['test_samples']}")
    print(f"  Categories:         {len(metrics['categories'])}")
    print(f"  Vocabulary Size:    {metrics['vocabulary_size']}")
    print(f"\n📁 Files Saved:")
    print(f"  Vectorizer: {vectorizer_path}")
    print(f"  Classifier: {classifier_path}")
    print(f"  Metrics:    {metrics_path}")
    print("\n" + "="*60)

    # Print per-category performance
    print("\n📋 Per-Category Performance:\n")
    report = metrics['classification_report']
    for category in sorted(metrics['categories']):
        if category in report:
            cat_metrics = report[category]
            support = cat_metrics.get('support', 0)
            f1 = cat_metrics.get('f1-score', 0)
            print(f"  {category:20s} - F1: {f1:.3f}  (samples: {support})")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Train category classifier for invoice categorization"
    )
    parser.add_argument(
        '--min-samples',
        type=int,
        default=5,
        help='Minimum samples per category (default: 5)'
    )
    parser.add_argument(
        '--test-split',
        type=float,
        default=0.2,
        help='Test set size as fraction (default: 0.2)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='models',
        help='Output directory for model files (default: models)'
    )

    args = parser.parse_args()

    try:
        # Load training data
        texts, labels = await load_training_data(
            min_samples_per_category=args.min_samples
        )

        if len(texts) == 0:
            print("❌ ERROR: No training data available")
            print("   Please ensure you have validated invoices with:")
            print("   - statut = 'validee'")
            print("   - categorie set")
            print("   - metadata_json.raw_text present")
            return 1

        # Train classifier
        vectorizer, classifier, metrics = train_classifier(
            texts,
            labels,
            test_size=args.test_split
        )

        # Save model
        output_dir = Path(args.output_dir)
        save_model(vectorizer, classifier, metrics, output_dir)

        return 0

    except Exception as e:
        logger.error("training_failed", error=str(e), exc_info=True)
        print(f"\n❌ ERROR: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
