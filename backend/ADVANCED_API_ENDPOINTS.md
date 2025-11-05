# Advanced Enrichment & ML API Endpoints

Documentation complète des endpoints API avancés pour l'enrichissement et le machine learning.

---

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Re-Enrichissement](#re-enrichissement)
3. [Enrichissement en Lot](#enrichissement-en-lot)
4. [Statistiques d'Enrichissement](#statistiques-denrichissement)
5. [Métriques ML](#métriques-ml)
6. [Re-Entraînement ML](#re-entraînement-ml)
7. [Exemples d'Utilisation](#exemples-dutilisation)

---

## 🎯 Vue d'ensemble

Les endpoints avancés permettent :
- **Re-enrichir** des factures existantes
- **Batch processing** pour traitement en masse
- **Monitoring** de l'enrichissement et du ML
- **Re-entraînement** du modèle ML à la demande

**Base URL** : `http://localhost:8000/api/enrichment`

---

## 🔄 Re-Enrichissement

### POST `/api/enrichment/{facture_id}/re-enrich`

Re-enrichit une facture existante avec une configuration personnalisée.

#### Paramètres URL

| Paramètre | Type | Description |
|-----------|------|-------------|
| `facture_id` | int | ID de la facture à re-enrichir |

#### Corps de Requête

```json
{
  "config": {
    "enable_supplier_matching": true,
    "enable_duplicate_detection": true,
    "enable_category_classification": true,
    "enable_anomaly_detection": true,
    "supplier_matching_threshold": 0.85,
    "category_confidence_threshold": 0.80,
    "anomaly_zscore_threshold": 3.0
  },
  "force": false
}
```

**Champs** :
- `config` (optionnel) - Configuration personnalisée d'enrichissement
- `force` (optionnel, défaut: `false`) - Forcer le re-enrichissement même si déjà enrichi

#### Réponse

```json
{
  "facture_id": 123,
  "timestamp": "2024-11-05T14:30:00",
  "config": {...},
  "supplier_matching": {
    "matched": true,
    "fournisseur_id": 42,
    "confidence": 1.0,
    "method": "siret_exact"
  },
  "duplicate_detection": {
    "is_duplicate": false
  },
  "category_classification": {
    "predicted_category": "Plomberie",
    "confidence": 0.92,
    "method": "ml"
  },
  "anomaly_detection": {
    "is_anomaly": false
  },
  "actions_taken": [
    "Linked supplier #42 (SIRET exact match)",
    "Set category to 'Plomberie' (ML confidence: 0.92)"
  ],
  "warnings": [],
  "needs_review_reasons": [],
  "success": true,
  "processing_time_ms": 1847
}
```

#### Exemples cURL

**Re-enrichissement basique** :
```bash
curl -X POST "http://localhost:8000/api/enrichment/123/re-enrich" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

**Re-enrichissement avec config personnalisée** :
```bash
curl -X POST "http://localhost:8000/api/enrichment/123/re-enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "force": true,
    "config": {
      "enable_supplier_matching": true,
      "category_confidence_threshold": 0.90
    }
  }'
```

**Avec désactivation de certains enrichissements** :
```bash
curl -X POST "http://localhost:8000/api/enrichment/123/re-enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "force": true,
    "config": {
      "enable_supplier_matching": false,
      "enable_duplicate_detection": false,
      "enable_category_classification": true,
      "enable_anomaly_detection": true
    }
  }'
```

#### Codes de Statut

- `200` - Succès
- `400` - Déjà enrichi (si `force=false`)
- `404` - Facture non trouvée
- `500` - Erreur interne

#### Cas d'Usage

1. **Après mise à jour du modèle ML** - Re-enrichir pour bénéficier du nouveau modèle
2. **Configuration différente** - Tester avec d'autres seuils
3. **Correction d'erreurs** - Re-enrichir après correction de données

---

## 📦 Enrichissement en Lot

### POST `/api/enrichment/batch-enrich`

Enrichit plusieurs factures en une seule requête avec contrôle de concurrence.

#### Corps de Requête

```json
{
  "facture_ids": [1, 2, 3, 4, 5],
  "config": {
    "enable_supplier_matching": true,
    "category_confidence_threshold": 0.85
  },
  "max_concurrent": 5
}
```

**Champs** :
- `facture_ids` (requis) - Liste des IDs de factures (max 1000)
- `config` (optionnel) - Configuration d'enrichissement
- `max_concurrent` (optionnel, défaut: 5) - Nombre de factures traitées en parallèle

#### Réponse

```json
{
  "total_invoices": 5,
  "successful": 4,
  "failed": 1,
  "results": [
    {
      "facture_id": 1,
      "success": true,
      "actions_taken": [...],
      ...
    },
    ...
  ],
  "errors": {
    "3": "Invoice not found"
  },
  "total_processing_time_ms": 8500,
  "average_processing_time_ms": 1700
}
```

#### Exemple cURL

```bash
curl -X POST "http://localhost:8000/api/enrichment/batch-enrich" \
  -H "Content-Type: application/json" \
  -d '{
    "facture_ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "config": {
      "enable_supplier_matching": true,
      "enable_category_classification": true
    },
    "max_concurrent": 3
  }'
```

#### Optimisation des Performances

**Recommandations de concurrence** :

| Nb Factures | max_concurrent | Temps Estimé |
|-------------|----------------|--------------|
| 1-10        | 5              | ~10s         |
| 11-50       | 10             | ~25s         |
| 51-100      | 15             | ~45s         |
| 101-500     | 20             | ~2-3 min     |

**Limites** :
- Maximum 1000 factures par batch
- Timeout : 5 minutes
- Si > 500 factures, considérer découpage en plusieurs batches

#### Codes de Statut

- `200` - Succès (même si certaines factures échouent)
- `400` - Paramètres invalides (liste vide, > 1000 factures)
- `500` - Erreur critique

#### Cas d'Usage

1. **Import initial** - Enrichir toutes les factures après migration
2. **Re-processing** - Re-enrichir après mise à jour du modèle
3. **Traitement nocturne** - Batch processing pendant heures creuses

---

## 📊 Statistiques d'Enrichissement

### GET `/api/enrichment/stats`

Retourne des statistiques complètes sur l'enrichissement.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `copropriete_id` | int | Filtrer par copropriété (optionnel) |

#### Réponse

```json
{
  "total_invoices": 1000,
  "enriched_invoices": 850,
  "enrichment_rate": 0.85,

  "supplier_matched_count": 720,
  "supplier_match_rate": 0.72,

  "duplicates_detected_count": 15,
  "duplicate_rate": 0.015,

  "category_auto_set_count": 780,
  "category_auto_set_rate": 0.78,

  "ml_used_count": 680,
  "ml_usage_rate": 0.68,

  "keyword_used_count": 100,

  "anomalies_detected_count": 45,
  "anomaly_rate": 0.045,

  "needs_review_count": 120,
  "needs_review_rate": 0.12,

  "avg_processing_time_ms": 1847.5
}
```

#### Exemples cURL

**Statistiques globales** :
```bash
curl "http://localhost:8000/api/enrichment/stats"
```

**Statistiques par copropriété** :
```bash
curl "http://localhost:8000/api/enrichment/stats?copropriete_id=1"
```

#### Interprétation des Métriques

**Taux d'enrichissement** (`enrichment_rate`) :
- `> 0.90` - Excellent ✅
- `0.70 - 0.90` - Bon ✔️
- `< 0.70` - À améliorer ⚠️

**Taux de matching fournisseur** (`supplier_match_rate`) :
- `> 0.80` - Excellent (SIRET bien rempli)
- `0.50 - 0.80` - Moyen (améliorer extraction SIRET)
- `< 0.50` - Faible (revoir OCR)

**Utilisation ML** (`ml_usage_rate`) :
- `> 0.80` - Modèle bien utilisé ✅
- `0.50 - 0.80` - Modèle partiellement utilisé
- `< 0.50` - Vérifier si modèle chargé ⚠️

**Taux de révision** (`needs_review_rate`) :
- `< 0.20` - Excellent (peu de validation manuelle)
- `0.20 - 0.40` - Normal
- `> 0.40` - Élevé (vérifier qualité OCR/enrichissement)

#### Codes de Statut

- `200` - Succès
- `500` - Erreur interne

#### Cas d'Usage

1. **Dashboard** - Afficher KPIs d'enrichissement
2. **Monitoring** - Surveiller performance du système
3. **Rapports** - Générer rapports d'activité

---

## 🤖 Métriques ML

### GET `/api/enrichment/ml/metrics`

Retourne les métriques du modèle ML de classification.

#### Réponse

```json
{
  "model_loaded": true,
  "model_path": "models/category_classifier.pkl",

  "training_metrics": {
    "accuracy": 0.892,
    "precision": 0.887,
    "recall": 0.892,
    "f1_score": 0.888,
    "cross_validation": {
      "mean": 0.885,
      "std": 0.023
    },
    "samples_per_category": {
      "Plomberie": 12,
      "Électricité": 10,
      ...
    },
    "training_date": "2024-11-05T12:00:00",
    "total_samples": 100,
    "vocabulary_size": 324
  },

  "predictions_count": 680,
  "avg_confidence": 0.87,
  "categories": [
    "Plomberie",
    "Électricité",
    "Chauffage",
    ...
  ]
}
```

#### Exemple cURL

```bash
curl "http://localhost:8000/api/enrichment/ml/metrics"
```

#### Interprétation

**Model Status** :
- `model_loaded: true` - Modèle ML actif ✅
- `model_loaded: false` - Fallback sur keywords ⚠️

**Training Metrics** :
- `accuracy > 0.85` - Modèle performant ✅
- `cross_validation.std < 0.05` - Modèle stable ✅

**Live Usage** :
- `predictions_count` - Nombre de prédictions ML réalisées
- `avg_confidence` - Confiance moyenne (>0.85 = excellent)

#### Codes de Statut

- `200` - Succès
- `500` - Erreur interne

#### Cas d'Usage

1. **Health Check** - Vérifier que le modèle est chargé
2. **Performance Monitoring** - Surveiller accuracy en production
3. **Debug** - Diagnostiquer problèmes de classification

---

## 🔧 Re-Entraînement ML

### POST `/api/enrichment/ml/retrain`

Déclenche un re-entraînement du modèle ML.

⚠️ **Attention** : Opération longue (10-60 secondes selon volume de données)

#### Corps de Requête

```json
{
  "min_samples": 10,
  "test_split": 0.2
}
```

**Champs** :
- `min_samples` (optionnel, défaut: 5) - Minimum samples par catégorie
- `test_split` (optionnel, défaut: 0.2) - Fraction pour test set

#### Réponse

```json
{
  "status": "completed",
  "message": "Model retrained successfully",
  "metrics": {
    "accuracy": 0.905,
    "precision": 0.898,
    "recall": 0.905,
    "f1_score": 0.901,
    "training_date": "2024-11-05T15:30:00",
    ...
  }
}
```

**Status possibles** :
- `"completed"` - Re-entraînement réussi ✅
- `"failed"` - Échec (message d'erreur fourni) ❌

#### Exemples cURL

**Re-entraînement standard** :
```bash
curl -X POST "http://localhost:8000/api/enrichment/ml/retrain" \
  -H "Content-Type: application/json" \
  -d '{
    "min_samples": 10,
    "test_split": 0.2
  }'
```

**Re-entraînement avec validation stricte** :
```bash
curl -X POST "http://localhost:8000/api/enrichment/ml/retrain" \
  -H "Content-Type: application/json" \
  -d '{
    "min_samples": 15,
    "test_split": 0.3
  }'
```

#### Codes de Statut

- `200` - Requête acceptée (vérifier `status` dans réponse)
- `500` - Erreur critique

#### Cas d'Usage

1. **Après import massif** - Re-entraîner avec nouvelles factures validées
2. **Amélioration continue** - Re-entraînement mensuel/hebdomadaire
3. **Nouvelle catégorie** - Re-entraîner après ajout de nouvelle catégorie

#### Recommandations

**Fréquence de re-entraînement** :
- **Hebdomadaire** : Si > 50 nouvelles factures/semaine
- **Mensuel** : Si 20-50 nouvelles factures/mois
- **Trimestriel** : Si < 20 nouvelles factures/mois

**Avant de re-entraîner** :
1. Vérifier nombre de factures validées par catégorie :
   ```sql
   SELECT categorie, COUNT(*)
   FROM factures_global
   WHERE statut = 'validee' AND categorie IS NOT NULL
   GROUP BY categorie;
   ```

2. S'assurer que `min_samples` ≤ MIN(count par catégorie)

---

## 💡 Exemples d'Utilisation

### Workflow 1 : Import et Enrichissement Initial

```bash
# 1. Uploader des factures (sans enrichissement immédiat)
for file in factures/*.pdf; do
    curl -X POST "http://localhost:8000/api/invoices/upload" \
      -F "file=@$file" \
      -F "copropriete_id=1"
done

# 2. Lister les factures non enrichies
facture_ids=$(curl "http://localhost:8000/api/invoices?needs_review=true&limit=100" \
  | jq '[.[] | .id]')

# 3. Enrichir en lot
curl -X POST "http://localhost:8000/api/enrichment/batch-enrich" \
  -H "Content-Type: application/json" \
  -d "{
    \"facture_ids\": $facture_ids,
    \"max_concurrent\": 10
  }"
```

### Workflow 2 : Re-Entraînement et Re-Enrichissement

```bash
# 1. Re-entraîner le modèle ML
curl -X POST "http://localhost:8000/api/enrichment/ml/retrain" \
  -H "Content-Type: application/json" \
  -d '{"min_samples": 10, "test_split": 0.2}'

# 2. Vérifier le nouveau modèle
curl "http://localhost:8000/api/enrichment/ml/metrics" | jq '.training_metrics.accuracy'

# 3. Re-enrichir toutes les factures pour bénéficier du nouveau modèle
facture_ids=$(curl "http://localhost:8000/api/invoices?limit=1000" | jq '[.[] | .id]')

curl -X POST "http://localhost:8000/api/enrichment/batch-enrich" \
  -H "Content-Type: application/json" \
  -d "{
    \"facture_ids\": $facture_ids,
    \"config\": {\"enable_category_classification\": true},
    \"max_concurrent\": 15
  }"
```

### Workflow 3 : Monitoring et Alertes

```bash
#!/bin/bash
# Script de monitoring quotidien

# Récupérer les stats
stats=$(curl -s "http://localhost:8000/api/enrichment/stats")

# Extraire les métriques
needs_review_rate=$(echo $stats | jq '.needs_review_rate')
ml_usage_rate=$(echo $stats | jq '.ml_usage_rate')
enrichment_rate=$(echo $stats | jq '.enrichment_rate')

# Alertes
if (( $(echo "$needs_review_rate > 0.4" | bc -l) )); then
    echo "⚠️ ALERT: Taux de révision élevé: $needs_review_rate"
fi

if (( $(echo "$ml_usage_rate < 0.5" | bc -l) )); then
    echo "⚠️ ALERT: Utilisation ML faible: $ml_usage_rate"
fi

if (( $(echo "$enrichment_rate < 0.7" | bc -l) )); then
    echo "⚠️ ALERT: Taux d'enrichissement faible: $enrichment_rate"
fi

# Rapport
echo "📊 Rapport d'enrichissement:"
echo "  - Enrichissement: ${enrichment_rate}%"
echo "  - Utilisation ML: ${ml_usage_rate}%"
echo "  - Révision nécessaire: ${needs_review_rate}%"
```

### Workflow 4 : Correction d'Erreurs en Masse

```bash
# Scénario : Le matching fournisseur était désactivé, on veut le réactiver

# 1. Identifier les factures sans fournisseur
facture_ids=$(curl "http://localhost:8000/api/invoices?limit=1000" \
  | jq '[.[] | select(.fournisseur_id == null) | .id]')

# 2. Re-enrichir avec supplier matching seulement
curl -X POST "http://localhost:8000/api/enrichment/batch-enrich" \
  -H "Content-Type: application/json" \
  -d "{
    \"facture_ids\": $facture_ids,
    \"config\": {
      \"enable_supplier_matching\": true,
      \"enable_duplicate_detection\": false,
      \"enable_category_classification\": false,
      \"enable_anomaly_detection\": false
    },
    \"max_concurrent\": 10
  }"
```

---

## 📈 Best Practices

### Performance

1. **Batch processing** : Préférer `/batch-enrich` pour > 5 factures
2. **Concurrence** : Ajuster `max_concurrent` selon charge serveur
3. **Filtrage** : Utiliser filtres dans `/stats` pour éviter calculs inutiles

### Sécurité

1. **Validation** : Toujours valider `facture_ids` côté client
2. **Timeouts** : Implémenter timeouts clients pour batch longs
3. **Rate limiting** : Respecter limites API (100 req/min)

### Monitoring

1. **Healthcheck** : Vérifier `/ml/metrics` régulièrement
2. **Stats** : Monitorer `/stats` quotidiennement
3. **Alertes** : Configurer alertes sur taux anormaux

### Re-Entraînement

1. **Planification** : Re-entraîner pendant heures creuses
2. **Validation** : Vérifier accuracy après re-entraînement
3. **Rollback** : Garder backup du modèle précédent

---

## 🔍 Troubleshooting

### Problème : Re-enrichissement échoue

**Symptôme** : `400 Bad Request` sur `/re-enrich`

**Solutions** :
1. Vérifier si facture existe
2. Ajouter `"force": true` si déjà enrichi
3. Vérifier configuration JSON valide

### Problème : Batch très lent

**Symptôme** : `/batch-enrich` prend > 5 minutes

**Solutions** :
1. Réduire `max_concurrent` (charge serveur)
2. Diviser en batches plus petits
3. Vérifier logs serveur pour erreurs

### Problème : ML metrics indique model_loaded: false

**Symptôme** : Modèle non chargé malgré training

**Solutions** :
1. Vérifier fichiers dans `models/` :
   ```bash
   ls -la models/
   # Doit contenir: category_classifier.pkl, category_vectorizer.pkl
   ```

2. Vérifier permissions :
   ```bash
   chmod 644 models/*.pkl
   ```

3. Redémarrer serveur :
   ```bash
   uvicorn app.main:app --reload
   ```

### Problème : Re-training échoue

**Symptôme** : `status: "failed"` sur `/ml/retrain`

**Solutions** :
1. Vérifier données d'entraînement suffisantes :
   ```sql
   SELECT categorie, COUNT(*)
   FROM factures_global
   WHERE statut = 'validee' AND categorie IS NOT NULL
   GROUP BY categorie;
   ```

2. Réduire `min_samples`
3. Vérifier logs serveur

---

## 📚 Références

- [Enrichment Pipeline Architecture](ENRICHMENT_PIPELINE_ARCHITECTURE.md)
- [ML Category Classifier Guide](ML_CATEGORY_CLASSIFIER_GUIDE.md)
- [OCR Invoice Guide](OCR_INVOICE_GUIDE.md)
- [API Documentation](http://localhost:8000/api/docs)
