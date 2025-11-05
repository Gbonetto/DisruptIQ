# ML Category Classifier - Guide Complet

Ce guide explique comment entraîner et utiliser le classifieur ML pour la catégorisation automatique des factures.

---

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Installation](#installation)
4. [Génération de données d'entraînement](#génération-de-données-dentraînement)
5. [Entraînement du modèle](#entraînement-du-modèle)
6. [Évaluation des performances](#évaluation-des-performances)
7. [Utilisation du modèle](#utilisation-du-modèle)
8. [Amélioration continue](#amélioration-continue)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Vue d'ensemble

Le **ML Category Classifier** utilise un pipeline de machine learning pour classifier automatiquement les factures en catégories.

### Architecture

```
Facture OCR (raw_text)
         ↓
    TF-IDF Vectorizer
    (text → features)
         ↓
   Naive Bayes Classifier
    (features → category)
         ↓
    Catégorie prédite
  (avec score de confiance)
```

### Catégories Supportées

- **Plomberie** - Réparations, installations sanitaires
- **Électricité** - Travaux électriques, tableaux
- **Chauffage** - Chaudières, radiateurs, PAC
- **Jardinage** - Espaces verts, tonte, élagage
- **Nettoyage** - Parties communes, entretien
- **Ascenseur** - Maintenance, dépannage
- **Serrurerie** - Portes, serrures, clés
- **Peinture** - Ravalement, décoration
- **Toiture** - Couverture, étanchéité
- **Assurance** - Primes, cotisations
- **Juridique** - Avocats, notaires, huissiers
- **Comptabilité** - Expert-comptable, audit
- **Divers** - Autres prestations

---

## 🔧 Prérequis

### Base de données

Minimum requis pour l'entraînement :

- **5 factures validées par catégorie** (minimum absolu)
- **10+ factures par catégorie** (recommandé pour qualité)
- **50+ factures par catégorie** (optimal pour précision)

Chaque facture doit avoir :
- `statut = 'validee'`
- `categorie` définie (non NULL)
- `metadata_json.raw_text` présent (texte OCR)

### Dépendances Python

```bash
pip install scikit-learn==1.5.1
```

---

## 📦 Installation

### 1. Installer les dépendances

```bash
cd backend/
pip install -r requirements.txt
```

### 2. Créer le répertoire models

```bash
mkdir -p models/
```

Fichiers qui seront générés :
- `models/category_classifier.pkl` - Modèle Naive Bayes
- `models/category_vectorizer.pkl` - Vectorizer TF-IDF
- `models/training_metrics.json` - Métriques de performance

---

## 🎲 Génération de données d'entraînement

Si vous n'avez pas encore de factures validées, utilisez le générateur :

### Script de génération

```bash
cd backend/
python scripts/generate_sample_invoices.py --count 100
```

**Options** :
- `--count N` - Nombre de factures à générer (défaut: 100)

**Ce que fait le script** :
- Crée ~10 factures par catégorie
- Génère du texte réaliste pour chaque catégorie
- Marque les factures comme `validee`
- Remplit `metadata_json.raw_text`

**Output** :
```
✅ SAMPLE INVOICES GENERATED
============================================================

📊 Summary:
  Total Invoices:     100
  Categories:         10
  Per Category:       ~10

📚 Categories:
  - Plomberie
  - Électricité
  - Chauffage
  ...
```

---

## 🚀 Entraînement du modèle

### Commande de base

```bash
cd backend/
python scripts/train_category_classifier.py --min-samples 5
```

### Options

| Option | Description | Défaut |
|--------|-------------|--------|
| `--min-samples N` | Minimum de samples par catégorie | 5 |
| `--test-split X` | Fraction pour test set (0.0-1.0) | 0.2 |
| `--output-dir DIR` | Répertoire de sortie | `models` |

### Exemples

**Entraînement standard** :
```bash
python scripts/train_category_classifier.py --min-samples 5
```

**Entraînement avec plus de validation** :
```bash
python scripts/train_category_classifier.py --min-samples 10 --test-split 0.3
```

**Sortie personnalisée** :
```bash
python scripts/train_category_classifier.py --output-dir /path/to/models
```

---

## 📊 Évaluation des performances

### Métriques affichées

Après l'entraînement, vous verrez :

```
✅ MODEL TRAINING COMPLETE
============================================================

📊 Performance Metrics:
  Accuracy:  0.892
  Precision: 0.887
  Recall:    0.892
  F1 Score:  0.888

🔄 Cross-Validation (5-fold):
  Mean Accuracy: 0.885
  Std Dev:       0.023

📚 Training Data:
  Total Samples:      100
  Training Samples:   80
  Test Samples:       20
  Categories:         10
  Vocabulary Size:    324

📁 Files Saved:
  Vectorizer: models/category_vectorizer.pkl
  Classifier: models/category_classifier.pkl
  Metrics:    models/training_metrics.json

📋 Per-Category Performance:

  Plomberie            - F1: 0.923  (samples: 8)
  Électricité          - F1: 0.875  (samples: 7)
  Chauffage            - F1: 0.900  (samples: 9)
  ...
```

### Interprétation

**Accuracy (précision globale)** :
- `> 0.90` : Excellent ✅
- `0.80 - 0.90` : Bon ✔️
- `0.70 - 0.80` : Acceptable ⚠️
- `< 0.70` : Nécessite plus de données ❌

**F1-Score par catégorie** :
- Identifie les catégories difficiles à classifier
- Cibles pour amélioration (ajout de samples)

**Cross-Validation** :
- Valide la robustesse du modèle
- Faible std dev = modèle stable

### Fichier metrics.json

Détails complets dans `models/training_metrics.json` :

```json
{
  "accuracy": 0.892,
  "precision": 0.887,
  "recall": 0.892,
  "f1_score": 0.888,
  "cross_validation": {
    "mean": 0.885,
    "std": 0.023,
    "scores": [0.90, 0.85, 0.91, 0.87, 0.89]
  },
  "samples_per_category": {
    "Plomberie": 12,
    "Électricité": 10,
    ...
  },
  "confusion_matrix": [...],
  "classification_report": {...},
  "training_date": "2024-11-05T14:30:00",
  "vocabulary_size": 324
}
```

---

## 🔌 Utilisation du modèle

### Intégration automatique

Le modèle est **automatiquement chargé** par le `CategoryClassifier` :

```python
# Dans enrichment_pipeline.py (déjà intégré)
from app.services.enrichment.category_classifier import CategoryClassifier

# Charge le modèle depuis models/ automatiquement
classifier = CategoryClassifier.get_default_instance()

# Classify
result = classifier.classify(raw_text)
# → result.predicted_category = "Plomberie"
# → result.confidence = 0.92
# → result.method = "ml"
```

### Workflow complet

```
Upload Facture
      ↓
  OCR Extraction
      ↓
Save to Database
      ↓
Enrichment Pipeline
      ↓
  Category Classifier ← Utilise le modèle ML
      ↓
Auto-set category (si confidence > 0.80)
```

### Fallback sur keywords

Si le modèle ML n'est pas disponible :
- Le classifier utilise automatiquement les **keywords**
- Pas d'erreur, juste une confiance plus faible
- Méthode = `"keyword"` au lieu de `"ml"`

---

## 🔄 Amélioration continue

### Re-entraînement

À mesure que vous validez de nouvelles factures, **re-entraînez le modèle** :

```bash
# Tous les mois, par exemple
python scripts/train_category_classifier.py --min-samples 10
```

**Le modèle s'améliore avec** :
- Plus de factures validées
- Diversité de vocabulaire
- Nouvelles catégories

### Monitoring

Surveillez dans `metadata_json` :

```json
{
  "enrichment": {
    "category_classification": {
      "predicted": "Plomberie",
      "confidence": 0.92,
      "method": "ml"
    }
  }
}
```

**Indicateurs à suivre** :
- % de factures avec `method = "ml"` (vs "keyword")
- Moyenne de `confidence` pour prédictions ML
- Taux de corrections manuelles

### Ajout de catégories

Pour ajouter une nouvelle catégorie :

1. **Ajouter des keywords** dans `category_classifier.py` :
   ```python
   CATEGORY_KEYWORDS = {
       ...
       "Sécurité": [
           "gardien", "sécurité", "surveillance", "alarme", "vigile"
       ]
   }
   ```

2. **Valider des factures** avec cette catégorie

3. **Re-entraîner** le modèle :
   ```bash
   python scripts/train_category_classifier.py --min-samples 5
   ```

---

## 🛠️ Troubleshooting

### Erreur : "No categories have at least X samples"

**Problème** : Pas assez de factures validées

**Solutions** :
1. Réduire `--min-samples` :
   ```bash
   python scripts/train_category_classifier.py --min-samples 3
   ```

2. Générer des données de test :
   ```bash
   python scripts/generate_sample_invoices.py --count 100
   ```

3. Valider plus de factures existantes

---

### Erreur : "No training data available"

**Problème** : Aucune facture ne remplit les critères

**Vérifications** :

```sql
-- Compter les factures validées avec raw_text
SELECT
    categorie,
    COUNT(*) as count
FROM factures_global
WHERE statut = 'validee'
  AND categorie IS NOT NULL
  AND metadata_json->'raw_text' IS NOT NULL
GROUP BY categorie;
```

**Solutions** :
- Assurer que `metadata_json.raw_text` est rempli par l'OCR
- Valider des factures (statut = 'validee')
- Assigner des catégories manuellement

---

### Performance faible (accuracy < 0.70)

**Causes possibles** :

1. **Pas assez de samples** → Ajouter plus de factures
2. **Catégories trop similaires** → Fusionner ou clarifier
3. **Texte de mauvaise qualité** → Améliorer OCR

**Actions** :

- Analyser la **confusion matrix** dans `training_metrics.json`
- Identifier les catégories confondues
- Ajouter des samples ciblés pour ces catégories

---

### Modèle non chargé dans l'API

**Vérifications** :

1. Fichiers présents :
   ```bash
   ls -la backend/models/
   # Doit contenir:
   # - category_classifier.pkl
   # - category_vectorizer.pkl
   ```

2. Permissions :
   ```bash
   chmod 644 backend/models/*.pkl
   ```

3. Logs :
   ```python
   # Dans les logs, chercher:
   # "ml_model_loaded" → OK
   # "ml_model_not_loaded" → Fallback keywords
   ```

---

## 📈 Benchmarks

### Performances typiques

| Nb Samples | Accuracy | Training Time |
|------------|----------|---------------|
| 50         | 0.75     | 2s            |
| 100        | 0.85     | 3s            |
| 500        | 0.92     | 8s            |
| 1000+      | 0.95+    | 15s           |

### Amélioration vs Keywords

| Méthode | Accuracy | Use Case |
|---------|----------|----------|
| Keywords | 0.70 | Fallback, pas de data |
| ML (50 samples) | 0.75 | Démarrage |
| ML (100+ samples) | 0.85+ | Production |

---

## 🔮 Évolutions Futures

### Phase 2 : Deep Learning

- **BERT** pour extraction d'entités nommées
- **Transformers** pour classification contextuelle
- **Transfer learning** depuis modèles pré-entraînés

### Phase 3 : Active Learning

- Suggérer des factures à valider pour maximiser l'apprentissage
- Prioriser les cas ambigus
- Réduction du travail de validation

### Phase 4 : Multi-label Classification

- Catégories multiples par facture
- Hiérarchie de catégories (parent/child)
- Tags personnalisés

---

## 📚 Références

### Algorithmes utilisés

- **TF-IDF** (Term Frequency - Inverse Document Frequency)
  - Convertit texte en features numériques
  - Pondère l'importance des mots

- **Naive Bayes Multinomial**
  - Probabiliste, rapide
  - Excellent pour classification de texte
  - Peu de risque d'overfitting

### Documentation

- [scikit-learn TfidfVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
- [scikit-learn MultinomialNB](https://scikit-learn.org/stable/modules/generated/sklearn.naive_bayes.MultinomialNB.html)
- [Text Classification Tutorial](https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html)

---

## ✅ Checklist de Production

Avant de déployer en production :

- [ ] Modèle entraîné avec ≥ 100 samples
- [ ] Accuracy ≥ 0.85
- [ ] Cross-validation std < 0.05
- [ ] Fichiers .pkl dans `models/`
- [ ] Permissions correctes (644)
- [ ] Tests passent (`pytest tests/services/enrichment/test_category_classifier_ml.py`)
- [ ] Monitoring en place (logs, métriques)
- [ ] Plan de re-entraînement (mensuel/trimestriel)

---

## 🆘 Support

**Logs utiles** :
```python
logger.info("ml_model_loaded")  # Modèle chargé OK
logger.warning("ml_model_not_loaded_using_keyword_fallback")  # Fallback
logger.error("ml_classification_failed")  # Erreur classification
```

**Debug mode** :
```python
# Dans category_classifier.py, augmenter logs
import structlog
logger = structlog.get_logger(__name__)
logger.setLevel("DEBUG")
```
