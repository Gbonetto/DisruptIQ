# Architecture du Pipeline d'Enrichissement de Factures

## 🎯 Objectif

Automatiser l'enrichissement post-OCR des factures pour réduire la validation manuelle et améliorer la qualité des données.

## 📊 Architecture Globale

```
┌─────────────────────────────────────────────────────────────────┐
│                      OCR Upload Endpoint                         │
│                    POST /api/invoices/upload                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │   OCR Extraction      │
          │   (Tesseract/Azure)   │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  Save to Database     │
          │  (FactureGlobal)      │
          └───────────┬───────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              ENRICHMENT PIPELINE (Async)                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. Supplier Matching                                     │   │
│  │    - SIRET exact match                                   │   │
│  │    - Fuzzy name matching (Levenshtein)                   │   │
│  │    - Auto-link fournisseur_id                            │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 2. Duplicate Detection                                   │   │
│  │    - Same numero + fournisseur                           │   │
│  │    - Same montant_ttc + date (±7 days)                   │   │
│  │    - Flag needs_review if duplicate                      │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 3. Category Classification (ML)                          │   │
│  │    - TF-IDF vectorization of article text               │   │
│  │    - Naive Bayes classifier                              │   │
│  │    - Auto-set categorie if confidence > 0.8              │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 4. Anomaly Detection                                     │   │
│  │    - Statistical outliers (Z-score > 3)                  │   │
│  │    - Historical average comparison                       │   │
│  │    - Flag needs_review if anomaly                        │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       ▼                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 5. Observability                                         │   │
│  │    - Log all enrichment actions                          │   │
│  │    - Track enrichment success rate                       │   │
│  │    - Store enrichment metadata                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  Update Invoice       │
          │  with enriched data   │
          └───────────────────────┘
```

## 🧩 Composants

### 1. **EnrichmentPipeline** (`app/services/enrichment_pipeline.py`)

**Responsabilité**: Orchestrateur principal

```python
class EnrichmentPipeline:
    """Orchestrateur d'enrichissement de factures"""

    async def enrich_invoice(
        self,
        facture_id: int,
        db: AsyncSession,
        config: EnrichmentConfig
    ) -> EnrichmentResult:
        """
        Enrichit une facture avec tous les processus activés

        Process:
        1. Load invoice from DB
        2. Run supplier matching
        3. Run duplicate detection
        4. Run category classification
        5. Run anomaly detection
        6. Update invoice with enriched data
        7. Log all actions
        """
```

**Configuration**:
```python
class EnrichmentConfig(BaseModel):
    enable_supplier_matching: bool = True
    enable_duplicate_detection: bool = True
    enable_category_classification: bool = True
    enable_anomaly_detection: bool = True
    supplier_matching_threshold: float = 0.85  # Fuzzy match threshold
    category_confidence_threshold: float = 0.80
    anomaly_zscore_threshold: float = 3.0
```

### 2. **SupplierMatcher** (`app/services/enrichment/supplier_matcher.py`)

**Responsabilité**: Match automatique des fournisseurs

**Stratégies**:
1. **Exact SIRET match** (priorité 1)
   - Si SIRET extrait, cherche dans `professionnels.siret`
   - Match exact → confiance 1.0

2. **Fuzzy name match** (priorité 2)
   - Levenshtein distance sur `name` + `company_name`
   - Normalisation (lowercase, remove accents, trim)
   - Threshold configurable (défaut: 0.85)

**Output**:
```python
class SupplierMatchResult(BaseModel):
    matched: bool
    fournisseur_id: Optional[int]
    confidence: float
    method: str  # "siret_exact", "name_fuzzy", "none"
    candidates: List[Dict]  # Top 3 matches with scores
```

### 3. **DuplicateDetector** (`app/services/enrichment/duplicate_detector.py`)

**Responsabilité**: Détecte les factures dupliquées

**Critères de détection**:

1. **Critère strict** (duplicate certain):
   - Même `numero` + même `fournisseur_id`
   - → Flag `needs_review = True`
   - → Add note: "Doublon détecté: facture #{existing_id}"

2. **Critère fuzzy** (duplicate probable):
   - Même `montant_ttc` (±0.50€) + date (±7 jours) + même fournisseur
   - → Flag `needs_review = True`
   - → Add note: "Doublon possible: facture #{existing_id}"

**Output**:
```python
class DuplicateResult(BaseModel):
    is_duplicate: bool
    duplicate_type: str  # "strict", "fuzzy", "none"
    existing_facture_ids: List[int]
    confidence: float
```

### 4. **CategoryClassifier** (`app/services/enrichment/category_classifier.py`)

**Responsabilité**: Classification ML des catégories

**Approche**:
1. **Training data** (initial):
   - Utilise les factures validées existantes
   - Extrait texte depuis `metadata_json.raw_text`
   - Entraîne un modèle Naive Bayes

2. **Features**:
   - TF-IDF vectorization du texte
   - N-grams (1-2)
   - Stopwords français

3. **Categories**:
   - Plomberie
   - Électricité
   - Chauffage
   - Jardinage
   - Nettoyage
   - Assurance
   - Juridique
   - Autre

**Output**:
```python
class CategoryPrediction(BaseModel):
    predicted_category: str
    confidence: float
    top_predictions: List[Tuple[str, float]]  # Top 3 with scores
```

**Fallback**: Si pas assez de données d'entraînement, utilise keyword matching (règles)

### 5. **AnomalyDetector** (`app/services/enrichment/anomaly_detector.py`)

**Responsabilité**: Détecte les montants anormaux

**Méthodes**:

1. **Z-Score Analysis**:
   - Calcule moyenne et std dev par catégorie
   - Détecte outliers: `|montant - mean| / std > threshold`
   - Threshold par défaut: 3.0 (99.7% confidence interval)

2. **Historical Comparison**:
   - Compare au même fournisseur (si connu)
   - Alerte si montant > 2x historique moyen

3. **Business Rules**:
   - Montant > 10,000€ → always flag for review
   - Montant > 50,000€ → critical alert

**Output**:
```python
class AnomalyResult(BaseModel):
    is_anomaly: bool
    anomaly_type: str  # "zscore", "historical", "threshold", "none"
    zscore: Optional[float]
    severity: str  # "low", "medium", "high", "critical"
    message: str
```

## 📦 Structure de Code

```
backend/
├── app/
│   ├── services/
│   │   ├── enrichment_pipeline.py         # Orchestrateur principal
│   │   ├── enrichment/
│   │   │   ├── __init__.py
│   │   │   ├── supplier_matcher.py        # Matching fournisseurs
│   │   │   ├── duplicate_detector.py      # Détection doublons
│   │   │   ├── category_classifier.py     # Classification ML
│   │   │   └── anomaly_detector.py        # Détection anomalies
│   ├── api/endpoints/
│   │   └── invoices.py                    # UPDATE: Ajouter auto-enrichment
│   └── models/
│       └── enrichment.py                  # Pydantic models
├── tests/
│   └── services/
│       └── enrichment/
│           ├── test_supplier_matcher.py
│           ├── test_duplicate_detector.py
│           ├── test_category_classifier.py
│           └── test_anomaly_detector.py
└── scripts/
    ├── train_category_classifier.py       # Script d'entraînement ML
    └── enrich_existing_invoices.py        # Batch enrichment
```

## 🔄 Intégration dans l'API

### Modification de `POST /api/invoices/upload`

```python
@router.post("/upload")
async def upload_and_extract_invoice(...):
    # 1. Existing: OCR extraction
    extracted_invoice = await ocr_service.extract_from_file(...)

    # 2. Existing: Save to database
    facture_id = await ocr_service.save_to_database(...)

    # 3. NEW: Automatic enrichment
    enrichment_pipeline = EnrichmentPipeline(db=db)
    enrichment_result = await enrichment_pipeline.enrich_invoice(
        facture_id=facture_id,
        db=db,
        config=EnrichmentConfig()  # Use default config
    )

    # 4. Return with enrichment metadata
    return InvoiceUploadResponse(
        facture_id=facture_id,
        extracted_invoice=extracted_invoice,
        enrichment=enrichment_result  # NEW
    )
```

### Nouvel endpoint: `POST /api/invoices/{id}/re-enrich`

```python
@router.post("/{facture_id}/re-enrich")
async def re_enrich_invoice(
    facture_id: int,
    config: EnrichmentConfig,
    db: AsyncSession = Depends(get_db)
):
    """Re-exécute l'enrichissement sur une facture existante"""
    enrichment_pipeline = EnrichmentPipeline(db=db)
    result = await enrichment_pipeline.enrich_invoice(
        facture_id=facture_id,
        db=db,
        config=config
    )
    return result
```

## 📊 Métadonnées Stockées

Toutes les actions d'enrichissement sont stockées dans `metadata_json`:

```json
{
  "ocr_backend": "tesseract",
  "raw_text": "...",
  "enrichment": {
    "timestamp": "2024-11-05T12:00:00Z",
    "config": {...},
    "supplier_matching": {
      "matched": true,
      "method": "siret_exact",
      "confidence": 1.0,
      "fournisseur_id": 42
    },
    "duplicate_detection": {
      "is_duplicate": false
    },
    "category_classification": {
      "predicted": "Plomberie",
      "confidence": 0.92,
      "method": "ml"
    },
    "anomaly_detection": {
      "is_anomaly": false,
      "zscore": 1.2
    },
    "actions_taken": [
      "Linked supplier #42 (SIRET match)",
      "Set category to 'Plomberie' (ML confidence: 0.92)"
    ]
  }
}
```

## 🎓 Entraînement du Modèle ML

### Script: `scripts/train_category_classifier.py`

```python
"""
Entraîne le classifieur de catégories depuis les factures validées

Usage:
    python scripts/train_category_classifier.py --min-samples 10

Output:
    - Modèle sauvegardé: models/category_classifier.pkl
    - Vectorizer: models/category_vectorizer.pkl
    - Métriques: models/training_metrics.json
"""
```

**Process**:
1. Charge toutes les factures validées (`statut = 'validee'`)
2. Extrait texte depuis `metadata_json.raw_text`
3. Entraîne TF-IDF + Naive Bayes
4. Validation croisée (5-fold)
5. Sauvegarde modèle et métriques

**Minimum data**: 10 samples par catégorie (sinon fallback sur rules)

## ⚙️ Configuration via Environment

```bash
# .env
ENRICHMENT_ENABLED=true
ENRICHMENT_SUPPLIER_MATCHING=true
ENRICHMENT_DUPLICATE_DETECTION=true
ENRICHMENT_CATEGORY_ML=true
ENRICHMENT_ANOMALY_DETECTION=true

# Thresholds
ENRICHMENT_SUPPLIER_FUZZY_THRESHOLD=0.85
ENRICHMENT_CATEGORY_CONFIDENCE_THRESHOLD=0.80
ENRICHMENT_ANOMALY_ZSCORE_THRESHOLD=3.0
```

## 🚀 Benefits

1. **Réduction validation manuelle**: ~60% des factures auto-enrichies
2. **Qualité données**: Fournisseurs liés automatiquement
3. **Détection doublons**: Évite les paiements en double
4. **Alertes intelligentes**: Montants anormaux détectés
5. **Amélioration continue**: ML apprend depuis nouvelles validations

## 📈 Métriques de Succès

- **Supplier match rate**: % factures avec fournisseur auto-lié
- **Category prediction accuracy**: Précision ML sur validation set
- **Duplicate detection rate**: % doublons détectés
- **False positive rate**: % false flags needs_review
- **Processing time**: Temps moyen enrichissement (target: <2s)

## 🔮 Évolutions Futures

1. **Email extraction** (IMAP): Auto-import factures depuis emails
2. **Deep learning**: BERT pour extraction entités nommées
3. **Active learning**: Suggestions de validation pour améliorer ML
4. **Multi-model ensemble**: Combine plusieurs classifiers
5. **Explainability**: SHAP values pour expliquer prédictions
