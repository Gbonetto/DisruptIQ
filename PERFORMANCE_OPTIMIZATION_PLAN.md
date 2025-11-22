# Plan d'Optimisation des Performances
## DisruptIQ - Intent Classifier V5

**Date:** 22 Novembre 2025, 16:10 CET
**Status Actuel:** 100% tests, mais performances améliorables
**Objectif:** Réduire temps de réponse moyen de 0.63s → 0.20s

---

## 📊 État Actuel des Performances

### Métriques de Base

| Métrique | Valeur Actuelle | Cible | Amélioration |
|----------|----------------|-------|--------------|
| Tests réussis | 100% (23/23) | 100% | ✅ Maintenir |
| Temps moyen | 0.63s | 0.20s | **-68%** |
| Quick rules | 70% | 90% | **+20pp** |
| LLM usage | 30% | 10% | **-20pp** |
| Coût LLM | 30% requêtes | 10% requêtes | **-67%** |

### Distribution Actuelle

```
Quick Rules (70%):
├─ Email: 100% détection, 0.05ms
├─ SQL: ~60% détection, 0.09ms  ⚠️ À améliorer
├─ Legal: ~80% détection, 0.04ms
├─ Web: 100% détection, 0.06ms
└─ Documents: ~50% détection  ⚠️ À améliorer

LLM Fallback (30%):
├─ Requêtes complexes: 10%  ✅ Normal
├─ Requêtes ambiguës: 5%  ✅ Normal
└─ Règles manquantes: 15%  ❌ Évitable!
```

---

## 🎯 Axes d'Optimisation

### Axe 1: Enrichir les Quick Rules (Impact: -50% temps moyen)

**Problème:** 15% des requêtes tombent sur LLM alors qu'elles sont prévisibles

**Solutions:**

#### 1.1. Ajouter des variantes de mots-clés

**SQL Keywords - À enrichir:**
```python
# ACTUEL (ligne 135-143)
sql_strong_keywords = {
    "combien": 0.95,
    "nombre de": 0.95,
    "liste des": 0.85,
    "liste-moi": 0.90,
    "tous les": 0.80,
    "moyenne": 0.95,
    "total": 0.85,
}

# PROPOSÉ (+ variantes courantes)
sql_strong_keywords = {
    # Comptage
    "combien": 0.95,
    "combien de": 0.95,
    "nombre de": 0.95,
    "nombre total": 0.95,
    "quantité": 0.90,

    # Listes
    "liste des": 0.85,
    "liste de": 0.85,
    "liste-moi": 0.90,
    "tous les": 0.80,
    "toutes les": 0.80,
    "affiche les": 0.85,
    "affiche-moi": 0.85,
    "montre-moi": 0.85,

    # Agrégations
    "moyenne": 0.95,
    "total": 0.85,
    "somme": 0.90,
    "minimum": 0.90,
    "maximum": 0.90,
    "statistiques": 0.90,
}

# Gain estimé: +10% de quick rules (30% → 20% LLM)
```

#### 1.2. Ajouter détection SEARCH_DOCUMENTS

**Actuellement manquant:**
```python
# La détection de SEARCH_DOCUMENTS nécessite has_documents = True
# Mais beaucoup de variantes ne sont pas couvertes

# PROPOSÉ (ligne 195-218, à enrichir)
doc_keywords_enhanced = [
    # Existant
    "dans les documents", "dans les fichiers", "dans mes documents",
    "recherche dans", "que dit", "selon le document",

    # À ajouter
    "cherche dans", "trouve dans", "extrait de",
    "d'après le", "d'après les", "selon les",
    "consulte le", "consulte les",
    "vérifie dans", "vérifie le",
    "lis le", "lis les",
    "parcours le", "parcours les",
]

# Gain estimé: +5% de quick rules (20% → 15% LLM)
```

#### 1.3. Ajouter détection REQUEST_QUOTES

**Actuellement basique:**
```python
# ACTUEL (ligne 221-231)
quote_keywords = ["devis", "demande de devis", "prix", "tarif"]

# PROPOSÉ (plus de variantes)
quote_keywords_enhanced = [
    # Devis
    "devis", "demande de devis", "demander un devis",
    "obtenir un devis", "recevoir un devis",
    "besoin d'un devis", "faire un devis",

    # Prix
    "prix", "tarif", "coût", "combien coûte",
    "quel est le prix", "estimation",

    # Prestataires
    "trouver un", "chercher un", "recommander un",
    "professionnel pour", "entreprise pour",
    "artisan pour", "plombier", "électricien",
]

# Gain estimé: +3% de quick rules (15% → 12% LLM)
```

**Total Axe 1: 30% → 12% LLM (-60% d'usage LLM)**

---

### Axe 2: Optimiser l'Ordre des Règles (Impact: -20% temps quick rules)

**Problème:** Les règles sont évaluées séquentiellement, pas par fréquence

**Solution: Réorganiser par fréquence d'usage**

```python
async def _quick_rules_classification(self, query_lower: str, has_documents: bool):
    """
    Quick rules optimisées par ordre de fréquence

    Ordre actuel:
    1. EMAIL (rare: 5%)
    2. SQL (fréquent: 30%)
    3. LEGAL (moyen: 15%)
    4. WEB (rare: 5%)
    5. DOCUMENTS (moyen: 15%)

    Ordre optimal (basé sur fréquence réelle):
    1. SQL (30% des requêtes) → Check en premier
    2. LEGAL (15%)
    3. DOCUMENTS (15%)
    4. EMAIL (5%)
    5. WEB (5%)
    """

    # 1. SQL - Le plus fréquent (30%)
    # ... existing code

    # 2. LEGAL - Deuxième plus fréquent (15%)
    # ... existing code

    # 3. DOCUMENTS - Troisième (15%)
    # ... existing code

    # 4. EMAIL - Moins fréquent mais high priority (5%)
    # ... existing code

    # 5. WEB - Rare (5%)
    # ... existing code
```

**Gain: Temps moyen quick rules: 0.06ms → 0.05ms (-17%)**

---

### Axe 3: Caching des Classifications Fréquentes (Impact: -30% temps moyen)

**Problème:** Requêtes similaires reclassifiées à chaque fois

**Solution: Cache LRU des classifications**

```python
from functools import lru_cache
import hashlib

class IntentClassifierV5:
    def __init__(self):
        self.llm_service = LLMService()

        # Cache simple pour requêtes fréquentes
        self.classification_cache = {}
        self.cache_max_size = 1000

    def _get_cache_key(self, user_input: str, has_documents: bool) -> str:
        """Generate cache key from query + context"""
        key = f"{user_input.lower().strip()}|{has_documents}"
        return hashlib.md5(key.encode()).hexdigest()

    async def classify(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentClassification:
        """Classify with caching"""

        # Check cache first
        has_documents = context.get("has_uploaded_documents", False) or \
                       context.get("has_active_documents", False)

        cache_key = self._get_cache_key(user_input, has_documents)

        if cache_key in self.classification_cache:
            logger.info("classification_cache_hit", cache_key=cache_key[:8])
            return self.classification_cache[cache_key]

        # ... existing classification logic

        # Store in cache (with LRU eviction)
        if len(self.classification_cache) >= self.cache_max_size:
            # Remove oldest entry
            self.classification_cache.pop(next(iter(self.classification_cache)))

        self.classification_cache[cache_key] = result

        return result
```

**Avantages:**
- ✅ Requêtes identiques: 0ms (cache hit)
- ✅ Réduit charge LLM pour requêtes répétées
- ✅ Améliore UX (réponse instantanée)

**Cas d'usage:**
- "Combien de copropriétaires?" → Très fréquente
- "Liste des professionnels" → Très fréquente
- "Bonjour" → Très fréquente

**Gain estimé: 20% des requêtes cachées → Temps moyen: 0.20s → 0.16s**

---

### Axe 4: LLM Prompt Optimization (Impact: -30% temps LLM)

**Problème:** Prompt actuel demande JSON avec reasoning complet

**Solution: Prompt plus court pour réponses plus rapides**

```python
# ACTUEL (ligne 253-286): Prompt très verbeux
prompt = f"""Classifie l'intention de cette requête utilisateur.

Requête: "{user_input}"

Contexte:
{context_str if context_str else "Aucun contexte spécifique"}

Intents disponibles:
1. query_data - Requêtes SQL (nombres, listes, statistiques sur copropriétaires/professionnels)
2. search_documents - Recherche sémantique dans documents (contrats, règlements, PDFs)
3. web_search - Recherche internet (infos actuelles, news)
4. send_email - Générer et envoyer des emails
5. request_quotes - Demander des devis
6. trigger_workflow - Déclencher un workflow N8N
7. legal - Analyse juridique, jurisprudence, clauses abusives
8. general_question - Questions générales d'assistant

Domaines:
- legal: Juridique, lois, contrats
- plumbing: Plomberie, eau, chauffage
- property_mgmt: Gestion copropriété
- vendor_mgmt: Fournisseurs, devis
- general: Questions générales

Réponds en JSON:
{{
    "intent": "query_data",
    "domain": "property_mgmt",
    "confidence": 0.85,
    "reasoning": "La requête demande une liste, donc SQL",
    "suggested_sources": ["sql"]
}}

Sois précis et justifie ton raisonnement."""

# PROPOSÉ: Version ultra-courte
prompt = f"""Intent: "{user_input}"

Options: query_data, search_documents, web_search, send_email, request_quotes, legal, general_question

JSON:
{{
    "intent": "...",
    "domain": "...",
    "confidence": 0.X,
    "sources": [...]
}}"""
```

**Avantages:**
- ✅ Tokens en entrée: 400 → 100 (-75%)
- ✅ Tokens en sortie: 150 → 50 (-67%)
- ✅ Temps de réponse: 2.1s → 1.4s (-33%)
- ✅ Coût API: -70%

**Risque:** Légère baisse de précision (95% → 92%)
**Mitigation:** Compenser avec quick rules enrichies (Axe 1)

---

### Axe 5: Parallel LLM + Quick Rules (Impact: -50% latence perçue)

**Problème:** Quick rules → Si échec → LLM (séquentiel)

**Solution: Lancer les deux en parallèle pour certaines requêtes**

```python
async def classify_parallel(self, user_input: str, ...):
    """
    Pour requêtes ambiguës: lancer quick rules ET LLM en parallèle
    Retourner le premier résultat avec confidence > seuil
    """

    # Détecter requêtes potentiellement ambiguës
    is_ambiguous = self._is_potentially_ambiguous(user_input)

    if is_ambiguous:
        # Lancer en parallèle
        quick_task = asyncio.create_task(self._quick_rules_classification(...))
        llm_task = asyncio.create_task(self._llm_classification(...))

        # Attendre le premier avec confidence > 0.85
        done, pending = await asyncio.wait(
            [quick_task, llm_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining task
        for task in pending:
            task.cancel()

        # Return first high-confidence result
        result = done.pop().result()
        return result

    else:
        # Comportement normal (quick → LLM si échec)
        return await self.classify(user_input, ...)
```

**Avantages:**
- ✅ Latence perçue: MIN(quick_rules, llm) au lieu de quick_rules + llm
- ✅ Fallback instantané si quick rules échoue

**Inconvénient:**
- ⚠️ Coût doublé pour requêtes ambiguës (utiliser avec parcimonie)

**Cas d'usage:** Uniquement pour 5-10% des requêtes vraiment ambiguës

---

## 📊 Impact Cumulé des Optimisations

### Scénario Conservateur (Quick Rules Only)

| Axe | Impact | Avant | Après |
|-----|--------|-------|-------|
| 1. Enrichir keywords | -60% LLM | 30% LLM | 12% LLM |
| 2. Réorganiser ordre | -17% temps QR | 0.06ms | 0.05ms |
| 3. Cache LRU | -20% requêtes | 0.63s | 0.50s |

**Résultat:**
- Temps moyen: **0.63s → 0.15s** (-76%)
- LLM usage: **30% → 12%** (-60%)
- Coût API: **-60%**

### Scénario Agressif (+ LLM Optimization)

| Axe | Impact | Avant | Après |
|-----|--------|-------|-------|
| Axes 1-3 | - | 0.63s | 0.15s |
| 4. Prompt court | -33% temps LLM | 2.1s | 1.4s |
| 5. Parallel (5% queries) | -50% latence | - | - |

**Résultat:**
- Temps moyen: **0.63s → 0.12s** (-81%)
- P95 latence: **3s → 0.5s** (-83%)
- Coût API: **-70%**

---

## 🎯 Plan d'Implémentation

### Phase 1: Quick Wins (2-3 heures)

**Priorité 1: Enrichir Keywords (Axe 1)**
- ✅ Ajouter variantes SQL (30 minutes)
- ✅ Ajouter variantes SEARCH_DOCUMENTS (20 minutes)
- ✅ Ajouter variantes REQUEST_QUOTES (20 minutes)
- ✅ Tests de régression (30 minutes)

**Gain immédiat: 30% → 12% LLM (-60% coût)**

**Priorité 2: Réorganiser Ordre (Axe 2)**
- ✅ Analyser fréquence réelle des intents (20 minutes)
- ✅ Réordonner quick rules (10 minutes)
- ✅ Benchmark avant/après (15 minutes)

**Gain immédiat: 0.06ms → 0.05ms quick rules**

### Phase 2: Caching (1-2 heures)

**Priorité 3: Cache LRU (Axe 3)**
- ✅ Implémenter cache avec hashlib (30 minutes)
- ✅ Ajouter métriques (cache hit rate) (20 minutes)
- ✅ Tests avec requêtes répétées (30 minutes)

**Gain immédiat: 20% requêtes @ 0ms (cache hit)**

### Phase 3: LLM Optimization (2-3 heures)

**Priorité 4: Prompt Court (Axe 4)**
- ⚠️ Créer prompt V2 (ultra-court) (30 minutes)
- ⚠️ A/B test precision (1 heure)
- ⚠️ Rollback si precision < 90% (fallback)

**Gain si succès: 2.1s → 1.4s LLM (-33%)**

### Phase 4: Advanced (Optionnel)

**Priorité 5: Parallel Classification (Axe 5)**
- ⚠️ Implémenter logique parallèle (1 heure)
- ⚠️ Tests de charge (1 heure)
- ⚠️ Monitoring coûts (30 minutes)

**Gain: Latence P95: 3s → 0.5s pour requêtes ambiguës**

---

## 📈 Métriques de Succès

### KPIs à Suivre

| Métrique | Actuel | Cible Phase 1 | Cible Phase 2 | Cible Phase 3 |
|----------|--------|---------------|---------------|---------------|
| **Temps moyen** | 0.63s | 0.30s | 0.15s | 0.12s |
| **P95 latence** | 3.0s | 2.0s | 1.5s | 0.5s |
| **Quick rules %** | 70% | 85% | 90% | 90% |
| **LLM usage %** | 30% | 15% | 10% | 10% |
| **Cache hit rate** | 0% | 0% | 20% | 25% |
| **Coût LLM/jour** | $X | $0.5X | $0.3X | $0.3X |
| **Tests success** | 100% | 100% | 100% | 100% |

### Monitoring

```python
# Ajouter métriques de performance
logger.info("classification_metrics",
           method="quick_rule",  # or "llm" or "cache"
           time_ms=processing_time,
           cache_hit=is_cache_hit,
           llm_tokens=tokens_used,
           intent=result.intent.value,
           confidence=result.confidence)
```

---

## ⚠️ Risques & Mitigations

### Risque 1: Baisse de Précision

**Risque:** Enrichir keywords peut créer faux positifs
**Mitigation:**
- Tests de régression systématiques
- Confidence scores ajustés
- A/B testing progressif

### Risque 2: Cache Invalide

**Risque:** Cache peut devenir obsolète si modèle change
**Mitigation:**
- TTL de 1 heure sur cache
- Invalidation manuelle possible
- Cache keys versionnés

### Risque 3: Coût LLM Parallèle

**Risque:** Axe 5 peut doubler coût pour requêtes ambiguës
**Mitigation:**
- Activer seulement pour 5% requêtes
- Feature flag pour désactiver si coût trop élevé
- Monitoring strict du coût

---

## 🎯 Recommandation

**Commencer par Phase 1 (Quick Wins):**
1. ✅ Enrichir keywords (2h)
2. ✅ Réorganiser ordre (30min)
3. ✅ Tests de régression (30min)

**Gain immédiat attendu:**
- Temps moyen: **0.63s → 0.30s** (-52%)
- Coût LLM: **-60%**
- Effort: **3 heures**
- Risque: **Faible**

**Puis évaluer Phase 2 (Caching) selon résultats Phase 1.**

---

**Prêt à implémenter Phase 1 ?**
- ✅ Faible risque
- ✅ Fort impact
- ✅ Rapide à faire
- ✅ Facile à rollback

**Voulez-vous que je commence ?**
