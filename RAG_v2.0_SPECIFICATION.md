# 🚀 DisruptIQ RAG v2.0 - Specification Technique

**Date**: 4 Novembre 2025
**Version**: 2.0.0
**Objectif**: Créer le RAG le plus performant et intelligent du marché

---

## 🎯 OBJECTIFS STRATÉGIQUES

### Performance
- ✅ **Précision** : >95% de pertinence sur les top-3 résultats
- ✅ **Citations** : Traçabilité complète (inline citations avec sources exactes)
- ✅ **Conversationnel** : Support multi-tours avec mémoire contextuelle
- ✅ **Latence** : <2s pour réponse complète (p95)
- ✅ **Scalabilité** : 10,000+ documents indexés sans dégradation

### Intelligence
- ✅ **Multi-hop reasoning** : Chaîne plusieurs docs pour réponses complexes
- ✅ **Query understanding** : Reformulation automatique des questions ambiguës
- ✅ **Self-correction** : Détection des réponses incertaines + demande de clarification
- ✅ **Contextual memory** : Résolution de références ("le doc", "ce point", "pourquoi")

---

## 🏗️ ARCHITECTURE MULTI-AGENTS

```
┌──────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                            │
│                  (Entry point - routing)                         │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  QUERY ANALYZER  │  ⭐ NOUVEAU
                    │  - Intent detect │
                    │  - Query rewrite │
                    │  - Ambiguity det │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐         ┌─────────▼──────────┐
     │ CONV MANAGER    │         │  RETRIEVAL AGENT   │  ⭐ NOUVEAU
     │ - Memory store  │◄────────┤  - Hybrid search   │
     │ - Context track │         │  - Multi-strategy  │
     │ - Ref resolution│         │  - Semantic chunking│
     └─────────────────┘         └─────────┬──────────┘
                                           │
                                 ┌─────────▼──────────┐
                                 │  RERANKER AGENT    │  ⭐ NOUVEAU
                                 │  - Cross-encoder   │
                                 │  - Relevance boost │
                                 │  - Confidence score│
                                 └─────────┬──────────┘
                                           │
                                 ┌─────────▼──────────┐
                                 │  SYNTHESIS AGENT   │  ⭐ AMÉLIORÉ
                                 │  - Multi-doc merge │
                                 │  - Inline citations│
                                 │  - Quality check   │
                                 └─────────┬──────────┘
                                           │
                                 ┌─────────▼──────────┐
                                 │  VALIDATOR AGENT   │  ⭐ NOUVEAU
                                 │  - Fact checking   │
                                 │  - Hallucination det│
                                 │  - Confidence meter│
                                 └────────────────────┘
```

---

## 📦 AGENTS DÉTAILLÉS

### 1. **Query Analyzer Agent** (NOUVEAU)

**Rôle** : Comprendre et améliorer la requête utilisateur

**Capacités** :
- ✅ **Intent Classification** : Factual / Procedural / Comparative / Conversational
- ✅ **Query Expansion** : Ajouter synonymes et termes connexes
- ✅ **Query Rewriting** : Reformuler pour meilleure recherche
- ✅ **Ambiguity Detection** : Détecter questions floues → demander clarification

**Fichier** : `backend/app/services/agents/query_analyzer_agent.py`

**Exemple** :
```python
Input: "combien coute le plombier ?"
Output: {
    "intent": "factual",
    "rewritten_query": "tarif horaire plombier intervention",
    "expansions": ["prix", "coût", "facture", "devis"],
    "needs_clarification": False
}

Input: "c'est quoi ça ?"
Output: {
    "intent": "conversational",
    "needs_clarification": True,
    "question": "De quoi parlez-vous exactement ?",
    "context_needed": True
}
```

---

### 2. **Conversational Memory Manager** (NOUVEAU)

**Rôle** : Gérer le contexte multi-tours et résoudre les références

**Capacités** :
- ✅ **Short-term memory** : 5 derniers tours de conversation
- ✅ **Entity tracking** : Suivi des entités mentionnées (docs, personnes, dates)
- ✅ **Coreference resolution** : "le doc" → "Règlement_copro.pdf"
- ✅ **Context injection** : Enrichir query avec contexte pertinent

**Fichier** : `backend/app/services/agents/conversational_memory.py`

**Structure mémoire** :
```python
class ConversationState(BaseModel):
    session_id: str
    turns: List[Turn]  # Historique
    entities: Dict[str, Entity]  # {"last_document": {...}, "last_person": {...}}
    active_context: Optional[str]  # Contexte actif

class Turn(BaseModel):
    user_query: str
    resolved_query: str  # Après résolution de références
    assistant_response: str
    sources_used: List[Source]
    timestamp: datetime
```

**Exemple** :
```python
Turn 1:
User: "quel est le délai d'intervention du plombier ?"
Memory: entities["profession"] = "plombier"

Turn 2:
User: "et le tarif ?"
Resolved: "quel est le tarif du plombier ?" (injection contexte)

Turn 3:
User: "détaille le point 2"
Resolved: "détaille le point 2 concernant le tarif du plombier" (contexte)
```

---

### 3. **Retrieval Agent** (NOUVEAU - Multi-Strategy)

**Rôle** : Récupération intelligente de documents avec stratégies multiples

**Stratégies disponibles** :

#### 3.1 Dense Retrieval (Semantic Search)
- Utilise embeddings OpenAI (1536 dims)
- Cosine similarity dans Qdrant
- **Avantage** : Capture sémantique profonde
- **Désavantage** : Peut manquer keywords exacts

#### 3.2 Sparse Retrieval (BM25 / Keyword)
- Utilise BM25 algorithm (TF-IDF amélioré)
- Index avec Elasticsearch ou implémentation custom
- **Avantage** : Trouve correspondances exactes
- **Désavantage** : Pas de compréhension sémantique

#### 3.3 Hybrid Retrieval (Combinaison)
- Combine dense + sparse avec weighted fusion
- Formula: `final_score = α * dense_score + (1-α) * sparse_score`
- **α = 0.7** (privilégie sémantique mais considère keywords)

**Fichier** : `backend/app/services/agents/retrieval_agent.py`

**Code structure** :
```python
class RetrievalAgent:
    async def retrieve(
        self,
        query: str,
        strategy: RetrievalStrategy = "hybrid",
        top_k: int = 20  # Récupère plus pour re-ranking
    ) -> List[Chunk]:

        if strategy == "hybrid":
            # Étape 1 : Dense retrieval
            dense_results = await self.dense_search(query, top_k=top_k)

            # Étape 2 : Sparse retrieval
            sparse_results = await self.sparse_search(query, top_k=top_k)

            # Étape 3 : Fusion avec RRF (Reciprocal Rank Fusion)
            fused_results = self.reciprocal_rank_fusion(
                dense_results,
                sparse_results,
                k=60
            )

            return fused_results[:top_k]
```

**Reciprocal Rank Fusion (RRF)** :
```python
def reciprocal_rank_fusion(self, lists: List[List[Chunk]], k=60):
    """
    RRF est plus robuste que weighted average

    Formula: score(chunk) = Σ (1 / (k + rank_i))
    où rank_i est le rang du chunk dans la liste i
    """
    scores = defaultdict(float)

    for result_list in lists:
        for rank, chunk in enumerate(result_list, start=1):
            scores[chunk.id] += 1.0 / (k + rank)

    # Sort by aggregated score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

---

### 4. **Reranker Agent** (NOUVEAU - Cross-Encoder)

**Rôle** : Affiner le classement avec modèle cross-encoder

**Pourquoi un reranker ?**
- Embeddings bi-encoder (search) : encode query et docs séparément → rapide mais imprécis
- Cross-encoder : encode query+doc ensemble → lent mais très précis
- **Solution** : Retrieve avec bi-encoder (top 20), puis rerank avec cross-encoder (top 5)

**Modèle recommandé** :
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (rapide, 80MB)
- Ou `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (multilingual)

**Fichier** : `backend/app/services/agents/reranker_agent.py`

**Code** :
```python
from sentence_transformers import CrossEncoder

class RerankerAgent:
    def __init__(self):
        self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    async def rerank(
        self,
        query: str,
        chunks: List[Chunk],
        top_k: int = 5
    ) -> List[RankedChunk]:
        """
        Rerank chunks using cross-encoder

        Returns:
            Chunks with refined scores (0-1 range)
        """
        # Prepare pairs
        pairs = [[query, chunk.text] for chunk in chunks]

        # Get scores (run in thread pool to avoid blocking)
        scores = await asyncio.to_thread(self.model.predict, pairs)

        # Combine chunks with scores
        ranked = [
            RankedChunk(
                chunk=chunk,
                original_score=chunk.score,
                reranked_score=float(score),
                boost_factor=float(score) / chunk.score if chunk.score > 0 else 1.0
            )
            for chunk, score in zip(chunks, scores)
        ]

        # Sort by reranked score
        ranked.sort(key=lambda x: x.reranked_score, reverse=True)

        return ranked[:top_k]
```

**Exemple** :
```
Query: "délai d'intervention plombier"

AVANT reranking (cosine similarity):
1. "Le plombier doit..." (score: 0.82)
2. "Délai de livraison 48h" (score: 0.79)  ← Faux positif !
3. "Intervention sous 24h" (score: 0.76)

APRÈS reranking (cross-encoder):
1. "Le plombier doit..." (score: 0.95)
2. "Intervention sous 24h" (score: 0.89)  ← Correctement remonté
3. "Délai de livraison 48h" (score: 0.43)  ← Filtré
```

---

### 5. **Synthesis Agent** (AMÉLIORÉ)

**Rôle** : Générer réponse cohérente avec citations inline précises

**Nouveautés v2.0** :
- ✅ **Inline citations** : Chaque affirmation est sourcée `[1]`
- ✅ **Multi-document synthesis** : Fusionne infos de plusieurs docs
- ✅ **Contradiction detection** : Signale si sources se contredisent
- ✅ **Confidence scoring** : Score de confiance par phrase

**Fichier** : `backend/app/services/agents/synthesis_agent.py`

**Format de sortie** :
```markdown
Le délai d'intervention du plombier est de **24 heures maximum**[1].
Le tarif horaire est fixé à **80€/h en semaine**[2] et **120€/h les week-ends**[2].

⚠️ Note : Le document [3] mentionne un tarif de 75€/h, mais cette information
date de 2023 et a été mise à jour par le contrat actuel[2].

---
📚 **Sources** :
[1] Règlement_copropriété.pdf (page 12) - Confidence: 95%
[2] Contrat_plombier_2025.pdf (page 1) - Confidence: 98%
[3] Archive_tarifs_2023.pdf (page 5) - Confidence: 65%
```

**Implémentation** :
```python
class SynthesisAgent:
    async def synthesize_with_citations(
        self,
        query: str,
        ranked_chunks: List[RankedChunk],
        conversation_context: Optional[ConversationState] = None
    ) -> SynthesizedResponse:

        # Étape 1 : Numéroter les sources
        sources = []
        for i, chunk in enumerate(ranked_chunks, start=1):
            sources.append({
                "id": i,
                "title": chunk.metadata.get("title"),
                "page": chunk.metadata.get("page"),
                "excerpt": chunk.text[:200],
                "confidence": chunk.reranked_score
            })

        # Étape 2 : Construire le prompt avec instructions de citation
        prompt = self._build_citation_prompt(query, sources, conversation_context)

        # Étape 3 : Générer avec LLM
        response = await self.llm.generate(
            prompt,
            temperature=0.2,  # Bas pour précision
            max_tokens=1000
        )

        # Étape 4 : Parser et valider citations
        parsed = self._parse_citations(response, sources)

        # Étape 5 : Détecter contradictions
        contradictions = self._detect_contradictions(sources)
        if contradictions:
            parsed["warnings"] = contradictions

        return parsed

    def _build_citation_prompt(self, query, sources, context):
        return f"""Tu es un assistant expert qui répond avec des CITATIONS PRÉCISES.

SOURCES NUMÉROTÉES :
{self._format_sources(sources)}

CONTEXTE CONVERSATIONNEL :
{context.get_summary() if context else "Aucun"}

RÈGLES IMPÉRATIVES :
1. Chaque affirmation factuelle DOIT être suivie de [N]
2. Format : "Le délai est de 24h[1]. Le coût est 80€[2]."
3. Si plusieurs sources confirment, liste-les : [1,2]
4. Si contradiction entre sources, SIGNALE-LA explicitement
5. Si information absente, DIS "Je n'ai pas trouvé cette information"
6. N'invente JAMAIS d'information non présente dans les sources

QUESTION : {query}

Réponds en français, de manière claire et professionnelle."""

    def _detect_contradictions(self, sources: List[Dict]) -> Optional[str]:
        """
        Utilise LLM pour détecter contradictions entre sources
        """
        if len(sources) < 2:
            return None

        prompt = f"""Analyse ces extraits de documents et détecte s'ils se contredisent :

{self._format_sources(sources)}

Si contradiction : explique-la brièvement.
Si cohérent : réponds "COHERENT"
"""
        result = await self.llm.generate(prompt, max_tokens=200)
        return None if "COHERENT" in result else result
```

---

### 6. **Validator Agent** (NOUVEAU)

**Rôle** : Valider la qualité de la réponse finale et détecter hallucinations

**Checks effectués** :
- ✅ **Citation coverage** : Toutes les affirmations sont sourcées ?
- ✅ **Factual accuracy** : Infos correspondent aux sources ?
- ✅ **Hallucination detection** : Rien d'inventé ?
- ✅ **Confidence threshold** : Score global >70% ?

**Fichier** : `backend/app/services/agents/validator_agent.py`

**Code** :
```python
class ValidatorAgent:
    async def validate(
        self,
        response: SynthesizedResponse,
        original_chunks: List[RankedChunk]
    ) -> ValidationResult:

        checks = []

        # Check 1: Citation coverage
        checks.append(self._check_citation_coverage(response))

        # Check 2: Factual grounding
        checks.append(await self._check_factual_grounding(response, original_chunks))

        # Check 3: Confidence threshold
        checks.append(self._check_confidence_threshold(response))

        # Aggregate
        all_passed = all(check.passed for check in checks)

        if not all_passed:
            # Generate warning message
            warnings = [check.message for check in checks if not check.passed]
            response.add_warnings(warnings)

        return ValidationResult(
            passed=all_passed,
            checks=checks,
            overall_confidence=self._compute_confidence(checks)
        )

    def _check_citation_coverage(self, response: SynthesizedResponse) -> Check:
        """
        Vérifie que chaque phrase factuelle a une citation
        """
        sentences = response.get_factual_sentences()
        cited = [s for s in sentences if s.has_citation]

        coverage = len(cited) / len(sentences) if sentences else 1.0

        return Check(
            name="citation_coverage",
            passed=coverage >= 0.9,
            score=coverage,
            message=f"Citation coverage: {coverage:.0%}"
        )

    async def _check_factual_grounding(
        self,
        response: SynthesizedResponse,
        chunks: List[RankedChunk]
    ) -> Check:
        """
        Utilise LLM pour vérifier que les affirmations sont fondées sur les sources
        """
        prompt = f"""Vérifie si cette RÉPONSE est ENTIÈREMENT basée sur les SOURCES.

RÉPONSE :
{response.text}

SOURCES :
{self._format_chunks(chunks)}

Réponds :
- "GROUNDED" si toutes les infos viennent des sources
- "HALLUCINATION: [phrase problématique]" si invention
"""
        result = await self.llm.generate(prompt, temperature=0.0)

        is_grounded = "GROUNDED" in result

        return Check(
            name="factual_grounding",
            passed=is_grounded,
            score=1.0 if is_grounded else 0.0,
            message="Factual grounding OK" if is_grounded else f"Hallucination détectée: {result}"
        )
```

---

## 🔄 FLUX COMPLET (End-to-End)

### Exemple : "quel est le délai d'intervention du plombier ?"

```
┌─────────────────────────────────────────────────────────────┐
│ USER: "quel est le délai d'intervention du plombier ?"     │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────▼────────────┐
              │  1. QUERY ANALYZER    │
              │  - Intent: factual    │
              │  - Rewrite: "délai... │
              │  - Expand: [urgent]   │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │  2. CONV MANAGER      │
              │  - Check context: ✓   │
              │  - Inject: "plombier" │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │  3. RETRIEVAL AGENT   │
              │  - Dense: 20 results  │
              │  - Sparse: 20 results │
              │  - Hybrid: fuse → 20  │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │  4. RERANKER AGENT    │
              │  - Cross-encode 20    │
              │  - Keep top 5         │
              │  - Boost relevance    │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │  5. SYNTHESIS AGENT   │
              │  - Generate answer    │
              │  - Add citations [N]  │
              │  - Format markdown    │
              └──────────┬────────────┘
                         │
              ┌──────────▼────────────┐
              │  6. VALIDATOR AGENT   │
              │  - Check citations ✓  │
              │  - Check facts ✓      │
              │  - Confidence: 92%    │
              └──────────┬────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ ASSISTANT:                                                  │
│ Le délai d'intervention du plombier est de **24 heures     │
│ maximum pour les urgences**[1] et de **48-72 heures pour   │
│ les interventions non urgentes**[2].                        │
│                                                              │
│ ---                                                          │
│ 📚 **Sources** :                                            │
│ [1] Règlement_copropriété.pdf (page 12) - 95%              │
│ [2] Contrat_plombier_2025.pdf (page 1) - 98%               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 MÉTRIQUES & MONITORING

### KPIs à tracker

| Métrique | Target | Actuel v1.0 | v2.0 Goal |
|----------|--------|-------------|-----------|
| **Precision@3** | >90% | ~75% | >95% |
| **Citation rate** | 100% | 0% | 100% |
| **Latency p95** | <2s | ~1.5s | <2s |
| **User satisfaction** | >4.5/5 | 3.8/5 | >4.7/5 |
| **Hallucination rate** | <2% | ~8% | <1% |

### Logging structure
```python
logger.info("rag_query_completed",
    query_id=uuid,
    query=query[:50],
    num_chunks_retrieved=20,
    num_chunks_reranked=5,
    synthesis_tokens=tokens,
    total_latency_ms=latency,
    confidence_score=0.92,
    sources_used=[1,2],
    hallucination_detected=False
)
```

---

## 🧪 PLAN DE TESTS

### Test Suite v2.0

#### 1. Unit Tests (agents individuels)
```bash
pytest tests/agents/test_query_analyzer.py
pytest tests/agents/test_retrieval_agent.py
pytest tests/agents/test_reranker_agent.py
pytest tests/agents/test_synthesis_agent.py
pytest tests/agents/test_validator_agent.py
```

#### 2. Integration Tests (end-to-end)
```python
# test_rag_e2e.py
async def test_factual_query_with_citation():
    response = await rag_service.query("quel est le tarif du plombier ?")

    assert "[1]" in response.text or "[2]" in response.text
    assert len(response.sources) > 0
    assert response.confidence > 0.7

async def test_conversational_followup():
    # Tour 1
    r1 = await rag_service.query("parle moi du règlement de copropriété")

    # Tour 2 (référence contextuelle)
    r2 = await rag_service.query("résume le point 3")

    assert r2.resolved_query contains "règlement de copropriété point 3"
    assert r2.sources_used is not empty
```

#### 3. Evaluation Dataset

Créer dataset de 100 questions avec réponses attendues :
```json
{
  "test_cases": [
    {
      "id": 1,
      "query": "Quel est le délai d'intervention du plombier ?",
      "expected_answer": "24 heures pour urgences",
      "expected_sources": ["Règlement_copro.pdf"],
      "difficulty": "easy"
    },
    {
      "id": 2,
      "query": "Compare les tarifs entre plombier et électricien",
      "expected_answer": "Plombier: 80€/h, Électricien: 75€/h",
      "expected_sources": ["Contrat_plombier.pdf", "Contrat_electricien.pdf"],
      "difficulty": "hard"
    }
  ]
}
```

---

## 📁 STRUCTURE DES FICHIERS

```
backend/app/services/agents/
├── orchestrator_agent.py          # (EXISTANT - modifications mineures)
├── query_analyzer_agent.py        # ⭐ NOUVEAU
├── conversational_memory.py       # ⭐ NOUVEAU
├── retrieval_agent.py             # ⭐ NOUVEAU (remplace rag_service partiellement)
├── reranker_agent.py              # ⭐ NOUVEAU
├── synthesis_agent.py             # ⭐ NOUVEAU
├── validator_agent.py             # ⭐ NOUVEAU
└── rag_orchestrator.py            # ⭐ NOUVEAU (coordonne le flux)

backend/app/services/
├── rag_service.py                 # (EXISTANT - devient legacy, migration progressive)
├── rag_service_v2.py              # ⭐ NOUVEAU (nouvelle API unifiée)
└── llm_service.py                 # (EXISTANT - utilisé par tous les agents)

backend/tests/agents/
├── test_query_analyzer.py         # ⭐ NOUVEAU
├── test_retrieval_agent.py        # ⭐ NOUVEAU
├── test_reranker_agent.py         # ⭐ NOUVEAU
├── test_synthesis_agent.py        # ⭐ NOUVEAU
├── test_validator_agent.py        # ⭐ NOUVEAU
└── test_rag_e2e.py                # ⭐ NOUVEAU
```

---

## 🚀 PLAN D'IMPLÉMENTATION PROGRESSIF

### **Phase 1 : Citations Inline (PRIORITÉ IMMÉDIATE)** - 4h
**Impact** : Résout 50% du problème

- ✅ Créer `synthesis_agent.py`
- ✅ Implémenter système de citations `[N]`
- ✅ Modifier `orchestrator_agent.py` pour utiliser nouveau synthesis
- ✅ Tester avec queries existantes

**Fichiers touchés** :
- `backend/app/services/agents/synthesis_agent.py` (NOUVEAU)
- `backend/app/services/agents/orchestrator_agent.py` (modification ligne 1197-1276)

**Tests** :
```bash
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "quel est le délai du plombier ?"}'

# Expected output avec [1], [2], etc.
```

---

### **Phase 2 : Retrieval Multi-Strategy** - 6h
**Impact** : Améliore précision de 20%

- ✅ Implémenter BM25 sparse retrieval
- ✅ Implémenter Reciprocal Rank Fusion
- ✅ Intégrer dans `retrieval_agent.py`
- ✅ Benchmarker vs version actuelle

**Dépendances** :
```bash
pip install rank-bm25 elasticsearch  # Pour BM25
```

**Tests comparatifs** :
```python
# Compare precision@3 entre stratégies
results = {
    "dense_only": evaluate(strategy="dense"),
    "sparse_only": evaluate(strategy="sparse"),
    "hybrid": evaluate(strategy="hybrid")
}
# Expected: hybrid > dense > sparse
```

---

### **Phase 3 : Reranker avec Cross-Encoder** - 4h
**Impact** : Améliore précision de 15% supplémentaires

- ✅ Installer cross-encoder model
- ✅ Créer `reranker_agent.py`
- ✅ Intégrer dans pipeline retrieval
- ✅ Mesurer amélioration du score

**Dépendances** :
```bash
pip install sentence-transformers
```

**Benchmark** :
```
AVANT reranking:
- Precision@3: 78%
- Top result relevance: 82%

APRÈS reranking:
- Precision@3: 93% (+15%)
- Top result relevance: 96% (+14%)
```

---

### **Phase 4 : Conversational Memory** - 5h
**Impact** : Permet conversations multi-tours

- ✅ Créer `conversational_memory.py`
- ✅ Implémenter entity tracking
- ✅ Résolution de coréférences ("le doc", "ça")
- ✅ Intégrer dans orchestrator

**Tests** :
```python
# Test multi-turn conversation
session = ConversationSession()

r1 = await session.query("parle moi du règlement")
assert "règlement" in r1.entities

r2 = await session.query("résume le point 3")
assert "règlement" in r2.resolved_query  # Context injection

r3 = await session.query("et le point 4 ?")
assert "règlement" in r3.resolved_query
```

---

### **Phase 5 : Query Analyzer** - 3h
**Impact** : Meilleure compréhension des questions

- ✅ Créer `query_analyzer_agent.py`
- ✅ Intent classification
- ✅ Query expansion
- ✅ Ambiguity detection

---

### **Phase 6 : Validator Agent** - 3h
**Impact** : Détection hallucinations

- ✅ Créer `validator_agent.py`
- ✅ Checks de qualité
- ✅ Hallucination detection
- ✅ Confidence scoring

---

### **Phase 7 : Testing & Optimization** - 4h
**Impact** : Solidité production

- ✅ Tests end-to-end
- ✅ Benchmarking performance
- ✅ Optimisation latence
- ✅ Monitoring & alerting

---

## 💰 COÛTS ESTIMÉS

### Infra
- **Qdrant** : Gratuit (self-hosted) ou 49$/mois (cloud)
- **Cross-encoder inference** : CPU only, pas de GPU nécessaire
- **Storage** : ~10GB pour 10k documents

### LLM API (OpenAI)
- **Embeddings** : $0.00013 / 1K tokens
  - 10,000 docs × 500 tokens avg = 5M tokens = **$0.65 one-time**
  - Cache réduit coûts récurrents de 80%
- **Generation (GPT-4o-mini)** : $0.15 / 1M input tokens
  - 1000 queries/jour × 2000 tokens avg = 2M tokens/jour = **$0.30/jour = $9/mois**

**Total mensuel** : ~$60-80 (Qdrant cloud) ou ~$10 (self-hosted)

---

## 🎯 ROADMAP COMPLÈTE

| Phase | Durée | Priorité | Impact |
|-------|-------|----------|--------|
| Phase 1: Citations inline | 4h | 🔴 CRITIQUE | 50% |
| Phase 2: Retrieval multi-strategy | 6h | 🟠 HIGH | 20% |
| Phase 3: Reranker | 4h | 🟠 HIGH | 15% |
| Phase 4: Conversational memory | 5h | 🟡 MEDIUM | 10% |
| Phase 5: Query analyzer | 3h | 🟡 MEDIUM | 3% |
| Phase 6: Validator | 3h | 🟢 LOW | 2% |
| Phase 7: Testing | 4h | 🟠 HIGH | - |

**Total : 29 heures** (3-4 jours de dev)

---

## ✅ CHECKLIST DE LIVRAISON

### Minimum Viable RAG (Phase 1-3)
- [ ] Citations inline fonctionnelles `[1]`, `[2]`
- [ ] Sources affichées avec titre, page, score
- [ ] Retrieval hybride (dense + sparse)
- [ ] Reranking avec cross-encoder
- [ ] Tests end-to-end passent
- [ ] Latence <2s

### Full-Featured RAG (Phase 1-7)
- [ ] Conversations multi-tours
- [ ] Résolution de références ("le doc")
- [ ] Query rewriting automatique
- [ ] Détection d'ambiguïté
- [ ] Validation hallucinations
- [ ] Confidence scoring
- [ ] Monitoring complet
- [ ] Documentation utilisateur

---

## 🎊 RÉSULTAT ATTENDU

Avec RAG v2.0, vos utilisateurs pourront :

### ✅ Exemple 1 : Question simple avec sources précises
```
User: "Quel est le tarif du plombier ?"