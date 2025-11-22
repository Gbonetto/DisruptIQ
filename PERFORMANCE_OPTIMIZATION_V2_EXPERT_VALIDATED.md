# Plan d'Optimisation V2 - Expert Validated
## DisruptIQ SMA-RAG - Performance Optimization

**Date:** 22 Novembre 2025, 16:20 CET
**Version:** V0 → V1 (First Production Optimization)
**Approche:** Pragmatique, Progressive, Mesurée

---

## ⚠️ DEPLOYMENT STATUS

**Sprint 1**: ✅ **DEPLOYED & OPERATIONAL** (v5.1_sprint1)
- Level 0 Bypass implemented and tested
- 81.2% bypass rate achieved (target was 40%)
- 21/21 Sprint 1 tests passing (100%)
- 23/24 comprehensive tests passing (95.8%)
- Backend restarted and operational

**Sprint 2-4**: 🔜 **DEFERRED TO FUTURE VERSION**
- Per user request, only Sprint 1 deployed for V1
- Remaining sprints scheduled for stabilization phase or future releases
- See `SPRINT1_DEPLOYMENT_SUMMARY.md` for full details

---

## 🎯 Philosophie d'Optimisation

### Principe Directeur

> **"Optimiser d'abord ce qui évite le travail, puis ce qui accélère le travail"**

**Hiérarchie d'optimisation:**
1. 🥇 **Bypass** - Ne pas faire de classification du tout (0ms, $0)
2. 🥈 **Cache** - Réutiliser une classification existante (0ms, $0)
3. 🥉 **Quick Rules** - Classification heuristique (0.05ms, $0)
4. 🎖️ **LLM Optimisé** - Classification intelligente (1s, $0.001)

### Objectifs V0 → V1

| Métrique | V0 (Actuel) | V1 (Cible) | Méthode |
|----------|-------------|------------|---------|
| **Temps moyen** | 0.63s | **0.20s** | Bypass + Cache + Quick Rules |
| **P95 latence** | 3.0s | **0.8s** | Quick Rules enrichies |
| **Classification évitée** | 0% | **40%** | Bypass UX + Templates |
| **Quick rules** | 70% | **85%** | Keywords enrichis + scoring |
| **LLM usage** | 30% | **15%** | Tout ce qui précède |
| **Coût LLM/jour** | $X | **$0.4X** | -60% appels LLM |
| **Précision** | 100% | **≥98%** | Scoring multi-critères |

---

## 🏗️ Architecture Optimisée

### Flux de Classification V1

```
Requête Utilisateur
    ↓
┌─────────────────────────────────────────┐
│ NIVEAU 0: PRÉ-FILTRAGE UX (40%)        │
│ - Templates fréquents ("Bonjour")      │
│ - Intent imposé par UI (bouton, onglet)│
│ → 0ms, pas de classification           │
└─────────────────────────────────────────┘
    ↓ (60% des requêtes)
┌─────────────────────────────────────────┐
│ NIVEAU 1: CACHE (20% de 60% = 12%)    │
│ - Requêtes identiques récentes          │
│ - Clé: user+tenant+query+context        │
│ → 0ms, classification réutilisée        │
└─────────────────────────────────────────┘
    ↓ (48% des requêtes)
┌─────────────────────────────────────────┐
│ NIVEAU 2: QUICK RULES (85% de 48% = 41%)│
│ - Scoring multi-critères               │
│ - Détection contextualisée             │
│ → 0.05ms, heuristiques                 │
└─────────────────────────────────────────┘
    ↓ (7% des requêtes)
┌─────────────────────────────────────────┐
│ NIVEAU 3: LLM OPTIMISÉ (7%)            │
│ - Prompt intermédiaire (150 tokens)    │
│ - Cas vraiment ambigus                 │
│ → 1.2s, Mistral API                    │
└─────────────────────────────────────────┘

RÉSULTAT:
- 40% bypass (0ms)
- 12% cache (0ms)
- 41% quick rules (0.05ms)
- 7% LLM (1200ms)

Temps moyen = 0.4*0 + 0.12*0 + 0.41*0.05 + 0.07*1200
            = 0 + 0 + 0.02 + 84
            = 84ms ≈ 0.08s

MAIS: temps moyen PERÇU incluant orchestrator + agents ≈ 0.20s
```

---

## 📦 Implémentation par Niveaux

### NIVEAU 0: Pré-Filtrage UX (Nouveau!)

**Objectif:** Court-circuiter 40% des classifications

#### 0.1. Templates Fréquents (10% bypass)

**Fichier:** `backend/app/services/template_filter.py` (NOUVEAU)

```python
"""
Template Filter - Bypass classification for common patterns
"""

class TemplateFilter:
    """Pre-filter common templates before classification"""

    # Canned responses (no SMA needed)
    CANNED_RESPONSES = {
        # Greetings
        r'^(bonjour|salut|hello|hi|hey)[\s\!\.]*$': {
            'response': 'Bonjour ! Comment puis-je vous aider avec votre copropriété ?',
            'bypass': True
        },
        r'^(merci|thank you|thanks)[\s\!\.]*$': {
            'response': 'De rien ! N\'hésitez pas si vous avez d\'autres questions.',
            'bypass': True
        },
        r'^(ok|d\'accord|compris)[\s\!\.]*$': {
            'response': 'Parfait ! Autre chose ?',
            'bypass': True
        },

        # Help requests (no classification needed)
        r'^(aide|help|\?)[\s\!\.]*$': {
            'intent': IntentType.GENERAL_QUESTION,
            'confidence': 1.0,
            'bypass_sma': False,  # Need SMA but not classification
        },
    }

    def check(self, user_input: str) -> Optional[Dict]:
        """
        Check if query matches a template

        Returns:
            None if no match (continue to classification)
            Dict with response/intent if match
        """
        query_normalized = user_input.lower().strip()

        for pattern, config in self.CANNED_RESPONSES.items():
            if re.match(pattern, query_normalized, re.IGNORECASE):
                logger.info("template_matched",
                           pattern=pattern,
                           bypass=config.get('bypass', False))
                return config

        return None
```

**Intégration dans Orchestrator:**

```python
# orchestrator_agent.py - DÉBUT de process()
async def process(self, user_input: str, ...):
    """Process with template filter"""

    # LEVEL 0: Template filter
    template_result = self.template_filter.check(user_input)

    if template_result:
        if template_result.get('bypass'):
            # Return canned response directly
            return AgentResponse(
                success=True,
                message=template_result['response'],
                agents_used=['TemplateFilter'],
                sources_used=[],
            )
        elif template_result.get('intent'):
            # Skip classification, use provided intent
            intent = template_result['intent']
            classification = IntentClassification(
                intent=intent,
                confidence=template_result.get('confidence', 1.0),
                reasoning="Template matched"
            )
            # Continue to handler...

    # LEVEL 1-3: Continue normal flow...
```

**Gain:** 10% des requêtes @ 0ms + 0 appel API

#### 0.2. UI Context Bypass (30% bypass)

**Principe:** Quand l'UI impose l'intent, ne pas classifier

**Exemples:**

```python
# Context venant du frontend
context = {
    'ui_mode': 'sql_query_builder',  # L'utilisateur est sur l'onglet SQL
    'action_button': 'generate_email',  # L'utilisateur a cliqué "Générer Email"
    'selected_document_id': 123,  # Un document est sélectionné
}

# Dans orchestrator
if context.get('ui_mode') == 'sql_query_builder':
    # Bypass classification
    intent = IntentType.QUERY_DATA
    classification = IntentClassification(
        intent=intent,
        confidence=1.0,
        reasoning="UI mode: sql_query_builder"
    )

elif context.get('action_button') == 'generate_email':
    intent = IntentType.SEND_EMAIL
    classification = IntentClassification(
        intent=intent,
        confidence=1.0,
        reasoning="UI action: generate_email button"
    )

elif context.get('selected_document_id'):
    # Document sélectionné → probable recherche doc
    intent = IntentType.SEARCH_DOCUMENTS
    classification = IntentClassification(
        intent=intent,
        confidence=0.95,
        reasoning="Document pre-selected in UI"
    )
```

**Gain:** 30% des requêtes @ 0ms quand UI donne le contexte

**Total NIVEAU 0:** 40% bypass (0ms, $0)

---

### NIVEAU 1: Cache Intelligent (Corrigé selon expert)

**Objectif:** Cacher 20% des requêtes post-bypass

#### 1.1. Clé de Cache Enrichie

**Problème identifié par expert:**
- Clé actuelle trop simple: `query + has_documents`
- Manque: `user_id`, `tenant_id`, `source_mode`, version

**Solution:**

```python
class IntentClassifierV5:
    """Enhanced caching with context-aware keys"""

    CLASSIFIER_VERSION = "v5.1"  # Increment to invalidate cache

    def _get_cache_key(
        self,
        user_input: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Generate cache key with ALL relevant context

        Key components:
        - user_id or tenant_id (multi-tenant isolation)
        - query normalized
        - has_documents
        - source_mode (auto/rag_only/sql_only/web_off)
        - classifier_version (easy invalidation)
        """

        # Extract context
        user_id = context.get('user_id', 'anonymous')
        tenant_id = context.get('tenant_id', 'default')
        has_documents = context.get('has_uploaded_documents', False) or \
                       context.get('has_active_documents', False)
        source_mode = context.get('source_mode', 'auto')  # From UI settings

        # Normalize query
        query_normalized = user_input.lower().strip()
        query_normalized = re.sub(r'\s+', ' ', query_normalized)  # Multiple spaces → 1

        # Build key
        key_data = {
            'v': self.CLASSIFIER_VERSION,
            't': tenant_id,  # Tenant isolation
            'u': user_id,    # User-specific preferences
            'q': query_normalized,
            'd': has_documents,
            'm': source_mode,  # auto / rag_only / sql_only / web_off
        }

        # Serialize to deterministic JSON
        key_str = json.dumps(key_data, sort_keys=True, separators=(',', ':'))

        # Hash to fixed-length key
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
```

**Avantages:**
- ✅ Isolation tenant (multi-tenant safe)
- ✅ Préférences utilisateur respectées
- ✅ Invalidation facile (bump version)
- ✅ Gère source_mode (RAG only, SQL only, etc.)

#### 1.2. Cache avec TTL et LRU

```python
from datetime import datetime, timedelta
from collections import OrderedDict

class IntentClassifierV5:
    def __init__(self):
        # ...
        self.classification_cache = OrderedDict()
        self.cache_timestamps = {}
        self.cache_max_size = 1000
        self.cache_ttl_seconds = 3600  # 1 hour

    def _get_cached_classification(
        self,
        cache_key: str
    ) -> Optional[IntentClassification]:
        """Get from cache with TTL check"""

        if cache_key not in self.classification_cache:
            return None

        # Check TTL
        cached_time = self.cache_timestamps.get(cache_key)
        if cached_time:
            age = (datetime.now() - cached_time).total_seconds()
            if age > self.cache_ttl_seconds:
                # Expired
                del self.classification_cache[cache_key]
                del self.cache_timestamps[cache_key]
                logger.info("cache_expired", cache_key=cache_key[:8], age_seconds=age)
                return None

        # Cache hit
        return self.classification_cache[cache_key]

    def _store_in_cache(
        self,
        cache_key: str,
        classification: IntentClassification
    ):
        """Store with LRU eviction"""

        # LRU eviction
        if len(self.classification_cache) >= self.cache_max_size:
            # Remove oldest (first inserted)
            oldest_key = next(iter(self.classification_cache))
            del self.classification_cache[oldest_key]
            del self.cache_timestamps[oldest_key]
            logger.info("cache_evicted_lru", evicted_key=oldest_key[:8])

        # Store
        self.classification_cache[cache_key] = classification
        self.cache_timestamps[cache_key] = datetime.now()

        # Move to end (mark as recently used)
        self.classification_cache.move_to_end(cache_key)

    def invalidate_cache(self, tenant_id: Optional[str] = None):
        """
        Invalidate cache for a tenant or all

        Usage:
        - When tenant changes preferences: invalidate_cache(tenant_id="tenant123")
        - When deploying new classifier: bump CLASSIFIER_VERSION
        """
        if tenant_id:
            # Invalidate only for this tenant
            keys_to_remove = [
                k for k in self.classification_cache.keys()
                if tenant_id in k  # Simplistic, could parse key_data
            ]
            for k in keys_to_remove:
                del self.classification_cache[k]
                del self.cache_timestamps[k]
            logger.info("cache_invalidated_tenant", tenant_id=tenant_id, count=len(keys_to_remove))
        else:
            # Invalidate all
            self.classification_cache.clear()
            self.cache_timestamps.clear()
            logger.info("cache_invalidated_all")
```

**Gain:** 20% des requêtes (post-bypass) @ 0ms

---

### NIVEAU 2: Quick Rules Enrichies avec Scoring

**Objectif:** Capturer 85% des requêtes (post-cache)

#### 2.1. Scoring Multi-Critères (Résout faux positifs)

**Problème identifié par expert:**
- Ajouter plein de keywords → risque faux positifs
- "combien" seul peut être ambigu

**Solution: Scoring basé sur plusieurs signaux**

```python
def _quick_rules_classification_v2(
    self,
    query_lower: str,
    has_documents: bool
) -> Optional[IntentClassification]:
    """
    Enhanced quick rules with multi-criteria scoring

    Scoring approach:
    - Keyword match: +points
    - Entity match (copropriétaire, professionnel): +points
    - Position (début de phrase): +points
    - Context (has_documents): +points
    - Total score → confidence
    """

    # SQL Detection with scoring
    sql_score = 0.0
    sql_keywords_matched = []

    # 1. Keyword detection
    sql_keywords_weighted = {
        # Strong SQL indicators
        "combien de": 0.40,
        "nombre de": 0.40,
        "liste des": 0.35,
        "liste-moi": 0.35,
        "affiche-moi": 0.30,
        "montre-moi": 0.30,

        # Weak SQL indicators (alone)
        "combien": 0.15,
        "nombre": 0.10,
        "tous les": 0.10,
        "toutes les": 0.10,

        # Aggregations
        "moyenne": 0.35,
        "total": 0.30,
        "somme": 0.30,
        "minimum": 0.25,
        "maximum": 0.25,
    }

    for keyword, weight in sql_keywords_weighted.items():
        if keyword in query_lower:
            sql_score += weight
            sql_keywords_matched.append(keyword)

    # 2. Entity detection (database entities)
    sql_entities = [
        "copropriétaire", "copropriétaires", "copropriété", "copropriétés",
        "professionnel", "professionnels", "prestataire", "prestataires",
        "syndic", "lots", "lot", "bâtiment", "immeuble",
        "assemblée générale", "ag", "pv", "procès-verbal"
    ]

    for entity in sql_entities:
        if entity in query_lower:
            sql_score += 0.25  # Strong boost
            sql_keywords_matched.append(f"entity:{entity}")
            break  # Only count once

    # 3. Position bonus (beginning of sentence)
    sql_starters = ["combien", "liste", "affiche", "montre", "quels sont", "quelles sont"]
    for starter in sql_starters:
        if query_lower.startswith(starter):
            sql_score += 0.10
            break

    # 4. Thresholds
    if sql_score >= 0.55:  # High confidence
        confidence = min(0.95, 0.70 + sql_score * 0.3)
        return IntentClassification(
            intent=IntentType.QUERY_DATA,
            domain=Domain.PROPERTY_MGMT,
            confidence=confidence,
            suggested_sources=[DataSource.SQL],
            reasoning=f"SQL scoring: {sql_score:.2f} (keywords: {', '.join(sql_keywords_matched)})",
            keywords_matched=sql_keywords_matched
        )

    # Repeat for LEGAL, SEARCH_DOCUMENTS, etc.
    # ...
```

**Avantages:**
- ✅ Moins de faux positifs ("combien" seul = score faible)
- ✅ Confiance proportionnelle au score
- ✅ Logging détaillé (debugging facile)
- ✅ Ajustable sans coder (poids dans dict)

#### 2.2. Keywords Enrichis par Intent

**SQL (optimisé avec scoring):**
```python
sql_keywords_enriched = {
    # Questions
    "combien": 0.15, "combien de": 0.40, "combien y a-t-il": 0.40,
    "nombre": 0.10, "nombre de": 0.40, "nombre total": 0.35,
    "quantité": 0.25, "quantité de": 0.35,

    # Listes
    "liste": 0.15, "liste des": 0.35, "liste de": 0.35,
    "liste-moi": 0.35, "liste moi": 0.35,
    "affiche": 0.15, "affiche-moi": 0.30, "affiche les": 0.30,
    "montre": 0.15, "montre-moi": 0.30, "montre les": 0.30,
    "tous les": 0.10, "toutes les": 0.10,

    # Agrégations
    "moyenne": 0.35, "moyenne de": 0.40,
    "total": 0.30, "total de": 0.35, "total des": 0.35,
    "somme": 0.30, "somme de": 0.35,
    "minimum": 0.25, "maximum": 0.25,
    "statistiques": 0.35, "stats": 0.30,
}
```

**LEGAL (optimisé avec scoring):**
```python
legal_keywords_enriched = {
    # High confidence
    "jurisprudence": 0.50, "légifrance": 0.50,
    "clause abusive": 0.50, "clauses abusives": 0.50,

    # Medium confidence
    "conformité": 0.35, "légalité": 0.35,
    "loi 1965": 0.40, "loi du": 0.25,
    "code civil": 0.40, "code de": 0.20,
    "décret": 0.30, "arrêté": 0.30,
    "règlement": 0.25,  # Peut être ambigü

    # Actions légales
    "vérifier la légalité": 0.40,
    "est-ce légal": 0.35,
    "droits et obligations": 0.35,
}
```

**SEARCH_DOCUMENTS (optimisé avec scoring):**
```python
document_keywords_enriched = {
    # Explicit search
    "dans les documents": 0.40, "dans le document": 0.40,
    "dans les fichiers": 0.40, "dans le fichier": 0.40,
    "dans mes documents": 0.40,

    # Search verbs
    "recherche dans": 0.35, "cherche dans": 0.35,
    "trouve dans": 0.35, "extrait de": 0.35,
    "consulte le": 0.30, "consulte les": 0.30,
    "vérifie dans": 0.30, "lis le": 0.30,

    # Content queries
    "que dit": 0.25, "selon le document": 0.40,
    "d'après le": 0.30, "d'après les": 0.30,

    # Requires has_documents = True for high confidence
}
```

**REQUEST_QUOTES:**
```python
quote_keywords_enriched = {
    # Devis
    "devis": 0.35, "demande de devis": 0.45,
    "obtenir un devis": 0.40, "faire un devis": 0.40,

    # Prix
    "prix": 0.15, "tarif": 0.15, "coût": 0.15,
    "combien coûte": 0.35, "quel est le prix": 0.35,
    "estimation": 0.30,

    # Professionnels (requires additional entity context)
    "trouver un plombier": 0.40,
    "chercher un électricien": 0.40,
    "recommander un professionnel": 0.35,
    "besoin d'un artisan": 0.35,
}
```

**Gain:** 85% coverage (post-cache) @ 0.05ms

---

### NIVEAU 3: LLM Optimisé (Prompt Intermédiaire)

**Objectif:** Classifier les 7% restants en 1.2s

#### 3.1. Prompt Intermédiaire (Expert-Validated)

**Recommandation expert:**
- Pas ultra-court (perte précision)
- Pas verbeux (trop lent/cher)
- **Version intermédiaire: 1 ligne + 1 exemple par intent**

```python
async def _llm_classification_v2(
    self,
    user_input: str,
    context: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, str]]]
) -> IntentClassification:
    """LLM classification with intermediate prompt"""

    # Build minimal context
    context_str = ""
    if context.get("has_uploaded_documents"):
        context_str += "Documents: uploaded\n"
    if conversation_history and len(conversation_history) > 0:
        context_str += f"History: {len(conversation_history)} msgs\n"

    # Intermediate prompt (150 tokens vs 400 avant)
    prompt = f"""Classify user intent.

Query: "{user_input}"
{context_str}
Intents (pick ONE):
1. query_data: SQL queries for counts, lists, stats (ex: "Combien de copropriétaires?")
2. search_documents: Semantic search in uploaded docs (ex: "Que dit le contrat sur...")
3. web_search: Internet search (ex: "Cherche sur internet...")
4. send_email: Generate/send emails (ex: "Envoie un mail au syndic...")
5. request_quotes: Request quotes from vendors (ex: "Devis pour réparation...")
6. trigger_workflow: Trigger N8N workflow (ex: "Lance le workflow relance...")
7. legal: Legal analysis, jurisprudence (ex: "Y a-t-il des clauses abusives?")
8. general_question: General assistant queries (ex: "Qu'est-ce que tu peux faire?")

Domains: legal, plumbing, property_mgmt, vendor_mgmt, general

JSON (no markdown):
{{"intent":"...","domain":"...","confidence":0.X,"sources":["..."]}}"""

    try:
        response = await self.llm_service.generate_response(
            prompt,
            max_tokens=100,  # Limite sortie
            temperature=0.1   # Déterministe
        )

        # Parse JSON (same as before)
        # ...
```

**Avantages:**
- ✅ Tokens entrée: 400 → 150 (-62%)
- ✅ Tokens sortie: 150 → 50 (-67%)
- ✅ Temps: 2.1s → 1.2s (-43%)
- ✅ Coût: -65%
- ✅ Précision maintenue (≥95% grâce aux exemples)

**Gain:** 7% usage LLM @ 1.2s (au lieu de 30% @ 2.1s)

---

## 📊 Performance Globale Attendue

### Distribution Post-Optimisation

```
100 requêtes:
├─ 40 → NIVEAU 0 (Bypass UX/Templates)      @ 0ms
├─ 12 → NIVEAU 1 (Cache)                    @ 0ms
├─ 41 → NIVEAU 2 (Quick Rules)              @ 0.05ms
└─ 7  → NIVEAU 3 (LLM)                      @ 1200ms

Temps moyen classification:
= (40*0 + 12*0 + 41*0.05 + 7*1200) / 100
= (0 + 0 + 2.05 + 8400) / 100
= 84ms

Temps moyen TOTAL (avec orchestrator + agents):
≈ 84ms (classification) + 100ms (orchestrator) + 50ms (agent)
≈ 234ms ≈ 0.23s

OBJECTIF ATTEINT: 0.63s → 0.23s (-63%)
```

### Métriques Détaillées

| Métrique | V0 | V1 | Amélioration |
|----------|----|----|--------------|
| **Temps moyen** | 0.63s | 0.23s | **-63%** ✅ |
| **P50 latence** | 0.5s | 0.10s | **-80%** ✅ |
| **P95 latence** | 3.0s | 0.80s | **-73%** ✅ |
| **P99 latence** | 5.0s | 1.50s | **-70%** ✅ |
| **Bypass %** | 0% | 40% | **+40pp** 🚀 |
| **Cache hit %** | 0% | 20% | **+20pp** 🚀 |
| **Quick rules %** | 70% | 85% | **+15pp** ✅ |
| **LLM usage %** | 30% | 7% | **-77%** 💰 |
| **Coût LLM/jour** | $10 | $2 | **-80%** 💰 |
| **Précision** | 100% | ≥98% | **-2%** ⚠️ |

---

## 🚀 Plan d'Implémentation Progressif

### Sprint 1: Fondations (3 jours)

**Jour 1: Template Filter**
- ✅ Créer `template_filter.py`
- ✅ Intégrer dans orchestrator
- ✅ Tests avec "Bonjour", "Merci", "Aide"
- ✅ Métriques: bypass_rate

**Jour 2: UI Context Bypass**
- ✅ Ajouter `ui_mode` et `action_button` au contexte
- ✅ Bypass classification quand intent évident
- ✅ Tests avec différents modes UI
- ✅ Métriques: ui_bypass_rate

**Jour 3: Cache Enrichi**
- ✅ Implémenter clé enrichie (tenant, user, source_mode)
- ✅ Ajouter TTL + LRU
- ✅ Tests de cache hit/miss
- ✅ Métriques: cache_hit_rate, cache_size

**Validation Sprint 1:** Bypass + Cache = 50% requêtes @ 0ms

### Sprint 2: Quick Rules V2 (3 jours)

**Jour 4: Scoring Multi-Critères**
- ✅ Implémenter scoring pour SQL
- ✅ Implémenter scoring pour LEGAL
- ✅ Tests de faux positifs
- ✅ Ajuster poids

**Jour 5: Keywords Enrichis**
- ✅ Ajouter variantes SQL (liste-moi, affiche-moi, etc.)
- ✅ Ajouter variantes DOCUMENTS
- ✅ Ajouter variantes REQUEST_QUOTES
- ✅ Tests de coverage

**Jour 6: Réorganisation Ordre**
- ✅ Analyser fréquence réelle
- ✅ Réordonner SQL → LEGAL → DOCUMENTS → EMAIL → WEB
- ✅ Benchmark avant/après

**Validation Sprint 2:** Quick rules 70% → 85% coverage

### Sprint 3: LLM Optimisé (2 jours)

**Jour 7: Prompt Intermédiaire**
- ✅ Créer prompt V2 (150 tokens)
- ✅ A/B test 100 requêtes (V1 vs V2)
- ✅ Comparer précision (≥95% requis)
- ✅ Comparer temps/coût

**Jour 8: Monitoring**
- ✅ Dashboard métriques
- ✅ Alertes si précision < 95%
- ✅ Logs détaillés par niveau
- ✅ Coût tracking

**Validation Sprint 3:** LLM 2.1s → 1.2s, coût -65%

### Sprint 4: Tests & Rollout (2 jours)

**Jour 9: Tests Complets**
- ✅ Relancer test_all_major_features.py (100% requis)
- ✅ Tests de charge (100 req/s)
- ✅ Tests de régression
- ✅ Valider métriques cibles

**Jour 10: Rollout Progressif**
- ✅ Déployer en staging
- ✅ A/B test 10% trafic production
- ✅ Monitorer 24h
- ✅ Rollout 100% si OK

**Validation Sprint 4:** Production @ 0.23s, précision ≥98%

---

## 📈 Métriques de Suivi

### Dashboard Real-Time

```python
# À ajouter dans logging
logger.info("classification_complete",
           level=0-3,  # 0=bypass, 1=cache, 2=quick, 3=llm
           method="template|ui_context|cache|quick_rule|llm",
           time_ms=elapsed,
           intent=result.intent.value,
           confidence=result.confidence,
           cache_hit=is_cache_hit,
           bypass_reason="greeting|ui_mode|action_button|...",
           user_id=user_id,
           tenant_id=tenant_id)
```

### KPIs à Monitorer

**Performance:**
- ✅ Temps moyen par niveau (0, 1, 2, 3)
- ✅ P50, P95, P99 latence
- ✅ Throughput (req/s)

**Efficacité:**
- ✅ Bypass rate (NIVEAU 0)
- ✅ Cache hit rate (NIVEAU 1)
- ✅ Quick rules coverage (NIVEAU 2)
- ✅ LLM usage % (NIVEAU 3)

**Qualité:**
- ✅ Précision globale (≥98%)
- ✅ Précision par intent
- ✅ Faux positifs rate
- ✅ Faux négatifs rate

**Coût:**
- ✅ Appels LLM/jour
- ✅ Tokens consommés
- ✅ Coût $ par jour
- ✅ Coût $ par requête

### Alertes

```yaml
alerts:
  - name: precision_drop
    condition: precision < 0.95
    action: rollback + notify

  - name: latency_spike
    condition: p95_latency > 1.5s
    action: investigate + notify

  - name: llm_usage_high
    condition: llm_usage_rate > 15%
    action: check_quick_rules + notify

  - name: cache_hit_low
    condition: cache_hit_rate < 15%
    action: check_ttl + notify
```

---

## ⚠️ Risques & Mitigations

### Risque 1: Bypass trop agressif

**Risque:** Templates/UI bypass créent des réponses incorrectes
**Indicateur:** User complaints, low satisfaction
**Mitigation:**
- Logs détaillés de tous les bypass
- Review manuel 100 premiers cas
- Feature flag pour désactiver si problème
- Fallback vers classification normale

### Risque 2: Cache stale

**Risque:** Cache retourne classification obsolète
**Indicateur:** Comportement incohérent
**Mitigation:**
- TTL 1h max
- Invalidation par tenant
- Version dans clé
- Monitoring cache age

### Risque 3: Faux positifs quick rules

**Risque:** Scoring trop permissif
**Indicateur:** Precision < 95%
**Mitigation:**
- Tests de régression systématiques
- Scoring conservateur (seuils élevés)
- Logging des cas limites (0.50 < confidence < 0.70)
- Ajustement poids progressif

### Risque 4: Prompt court perd précision

**Risque:** LLM moins précis avec prompt intermédiaire
**Indicateur:** Precision < 95% pour cas LLM
**Mitigation:**
- A/B test obligatoire
- Rollback automatique si < 95%
- Garder prompt long en fallback
- Feature flag

### Risque 5: Coût explosion

**Risque:** Optimisations ne réduisent pas le coût
**Indicateur:** Coût/jour identique ou pire
**Mitigation:**
- Monitoring coût en temps réel
- Budget alertes ($X/jour max)
- Rollback si explosion
- Feature flags par niveau

---

## 🎯 Critères de Succès V0 → V1

### Must Have (Blockers)

- ✅ **Temps moyen ≤ 0.25s** (cible: 0.23s)
- ✅ **Précision ≥ 98%** (tolérance: -2%)
- ✅ **Tests 100%** (23/23)
- ✅ **Pas de régression fonctionnelle**

### Should Have (Strongly Desired)

- ✅ **Bypass ≥ 35%** (cible: 40%)
- ✅ **Cache hit ≥ 15%** (cible: 20%)
- ✅ **LLM usage ≤ 10%** (cible: 7%)
- ✅ **Coût -60%** (cible: -80%)

### Could Have (Nice to Have)

- ✅ P95 latence ≤ 1s (cible: 0.8s)
- ✅ Dashboard temps réel
- ✅ Documentation complète
- ✅ Feature flags pour rollback

---

## 📚 Documentation

### Pour Développeurs

- ✅ Architecture document (ce fichier)
- ✅ Code comments détaillés
- ✅ Tests unitaires complets
- ✅ Guide troubleshooting

### Pour Ops

- ✅ Runbook monitoring
- ✅ Alertes configuration
- ✅ Rollback procedures
- ✅ Cost tracking guide

### Pour Product

- ✅ Performance improvements summary
- ✅ User-facing changes (none expected)
- ✅ Cost savings report
- ✅ Future roadmap

---

## 🚀 Roadmap V1 → V2 (Future)

### V2: Advanced Optimizations

**Quand:** Après V1 stable en production (3+ mois)

**Candidats:**
1. ✅ Parallel LLM (5% requêtes ambiguës)
2. ✅ ML classifier léger (remplace quick rules)
3. ✅ Streaming classification (résultats partiels)
4. ✅ Multi-model ensemble (LLM + ML)
5. ✅ Intent prédiction proactive (basé historique)

**Objectifs V2:**
- Temps moyen: 0.23s → 0.10s
- LLM usage: 7% → 3%
- Précision: 98% → 99.5%

---

## 🎯 Conclusion

**Plan V2 intègre tous les feedbacks expert:**
- ✅ Cache enrichi (tenant, user, source_mode, version)
- ✅ Scoring multi-critères (évite faux positifs)
- ✅ Prompt intermédiaire (balance perf/précision)
- ✅ Bypass UX (court-circuite classification)
- ✅ Templates fréquents (0ms pour "Bonjour")
- ✅ Progressive rollout (risques maîtrisés)

**Gains attendus:**
- **Temps:** 0.63s → 0.23s (-63%)
- **Coût:** -80%
- **Précision:** ≥98% (tolérance -2%)

**Prêt pour implémentation Sprint 1.**

---

**Auteur:** Claude Code + Expert Feedback Integration
**Date:** 22 Novembre 2025
**Version:** V2 (Expert-Validated)
**Status:** Ready for Implementation
