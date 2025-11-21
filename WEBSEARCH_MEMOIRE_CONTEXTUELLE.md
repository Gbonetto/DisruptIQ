# WebSearch avec Mémoire Contextuelle - Architecture

**Date** : 21 novembre 2025
**Objectif** : Permettre au WebSearchAgent de comprendre et utiliser le contexte conversationnel complet

---

## 🎯 Cas d'Usage

### Scénario 1 : Références Implicites

```
User: "Que dit la LOI n° 2024-322 sur la rénovation ?"
Assistant: [Recherche web + réponse sur la loi]

User: "Et pour les copropriétaires ?"
❌ AVANT: Recherche "Et pour les copropriétaires ?" → Résultats hors sujet
✅ APRÈS: Comprend contexte → Recherche "LOI 2024-322 copropriétaires rénovation"
```

### Scénario 2 : Raffinement de Recherche

```
User: "Trouve des plombiers à Paris"
Assistant: [Recherche web + résultats généraux]

User: "Non, je veux des plombiers spécialisés en copropriété"
❌ AVANT: Recherche "Non, je veux..." → Résultats invalides
✅ APRÈS: Comprend correction → Recherche "plombiers copropriété Paris"
```

### Scénario 3 : Recherche Itérative

```
User: "Cherche des informations sur la loi Elan"
Assistant: [Résultats loi Elan]

User: "Maintenant les décrets d'application"
❌ AVANT: Recherche "les décrets d'application" → Trop vague
✅ APRÈS: Comprend suite logique → Recherche "décrets application loi Elan"
```

---

## 🏗️ Architecture Proposée

### 1. Enrichissement Contextuel de la Requête

```python
class WebSearchAgent:
    def __init__(self):
        # ... existing init ...
        self.llm = get_mistral_client()

    async def search(
        self,
        query: str,
        num_results: int = 5,
        conversation_history: Optional[List[Dict[str, str]]] = None,  # NEW
        **kwargs
    ) -> SearchResults:
        """
        Search with conversational context awareness

        Args:
            query: User query (may contain implicit references)
            num_results: Number of results
            conversation_history: Recent conversation for context

        Returns:
            SearchResults
        """
        logger.info("websearch_with_context",
                   query=query[:50],
                   has_history=conversation_history is not None)

        # ✅ NEW: Enrich query with conversational context
        enriched_query = await self._enrich_query_with_context(
            query,
            conversation_history
        )

        # Search with enriched query
        if self.use_tavily:
            results = await self._search_tavily(enriched_query, num_results, ...)
        else:
            results = await self._search_duckduckgo(enriched_query, num_results, ...)

        return results
```

---

### 2. Enrichissement Intelligent avec LLM

```python
async def _enrich_query_with_context(
    self,
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Enrich query using conversation history for contextual understanding

    Handles:
    - Implicit references ("et pour les copropriétaires ?")
    - Follow-up questions ("maintenant les décrets")
    - Corrections/refinements ("non, je voulais...")

    Args:
        query: Current user query
        conversation_history: Last N messages

    Returns:
        Enriched, self-contained query
    """
    # No history → return query as-is
    if not conversation_history or len(conversation_history) == 0:
        logger.info("query_enrichment_skipped", reason="no_history")
        return query

    # Check if query needs context (heuristics)
    needs_context = self._query_needs_context(query)
    if not needs_context:
        logger.info("query_enrichment_skipped", reason="query_is_self_contained")
        return query

    # Use LLM to enrich query
    mistral = get_mistral_client()
    if not mistral:
        logger.warning("query_enrichment_failed", reason="llm_unavailable")
        return query

    try:
        # Build conversation context
        context_messages = []
        for msg in conversation_history[-6:]:  # Last 6 messages (3 turns)
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                context_messages.append(f"{role.upper()}: {content[:300]}")  # Truncate long messages

        context_str = "\n".join(context_messages)

        # LLM enrichment prompt
        enrichment_prompt = f"""Tu es un assistant qui reformule des requêtes de recherche web pour les rendre autonomes et complètes.

Contexte de la conversation:
{context_str}

Nouvelle requête de l'utilisateur: {query}

Instructions:
1. Si la requête fait référence au contexte précédent, reformule-la en incluant les éléments contextuels nécessaires
2. Si la requête est déjà complète et autonome, retourne-la telle quelle
3. Garde la requête concise (max 100 caractères)
4. Conserve les termes techniques et noms propres exacts
5. Réponds UNIQUEMENT avec la requête reformulée, sans explication

Requête reformulée:"""

        # Call LLM
        enriched = await asyncio.to_thread(
            lambda: mistral.invoke(enrichment_prompt).content.strip()
        )

        # Clean response (remove quotes, explanations)
        enriched = enriched.strip('"\'').split('\n')[0].strip()

        # Sanity check: If enriched is too different or too long, use original
        if len(enriched) > 200 or len(enriched) < 5:
            logger.warning("query_enrichment_rejected",
                          reason="invalid_length",
                          enriched=enriched[:100])
            return query

        logger.info("query_enriched",
                   original=query,
                   enriched=enriched)

        return enriched

    except Exception as e:
        logger.error("query_enrichment_failed",
                    query=query,
                    error=str(e),
                    exc_info=True)
        return query  # Fallback to original


def _query_needs_context(self, query: str) -> bool:
    """
    Heuristic to determine if query needs contextual enrichment

    Returns:
        True if query likely needs context, False otherwise
    """
    query_lower = query.lower()

    # Patterns indicating need for context
    context_indicators = [
        # Pronouns/references
        r'\b(il|elle|ils|elles|celui|celle|ceux|celles)\b',
        r'\b(le|la|les|leur|leurs)\b',
        r'\b(ça|cela|ce|cet|cette)\b',

        # Implicit references
        r'\b(aussi|également|pareillement)\b',
        r'\b(et pour|qu\'en est-il de|concernant)\b',
        r'\b(maintenant|ensuite|après)\b',

        # Corrections/refinements
        r'\b(non|pas|plutôt|en fait)\b',
        r'\b(précisément|exactement|spécifiquement)\b',

        # Follow-ups
        r'\b(plus d\'infos|plus de détails|approfondir)\b',
        r'\b(décrets|arrêtés|circulaires)\b\s+(d\')?application',

        # Incomplete queries
        r'^(et|ou|mais|donc)',
        r'\?$'  # Ends with question mark but very short
    ]

    for pattern in context_indicators:
        if re.search(pattern, query_lower):
            logger.info("query_needs_context_detected",
                       query=query[:50],
                       pattern=pattern)
            return True

    # Query is very short (< 20 chars) → likely needs context
    if len(query) < 20:
        logger.info("query_needs_context_detected",
                   query=query,
                   reason="query_too_short")
        return True

    return False
```

---

### 3. Intégration dans Orchestrator

```python
# orchestrator_agent.py

async def _handle_web_search(
    self,
    user_input: str,
    thought_stream: ThoughtStream = None,
    conversation_history: List[Dict] = None  # NEW
) -> AgentResponse:
    """Handle web search requests - WITH CONTEXT"""
    try:
        from .websearch_agent import WebSearchAgent

        web_agent = WebSearchAgent()

        # Thought 1: Starting search
        if thought_stream:
            await thought_stream.add_thought(
                ThoughtType.EXECUTING,
                title="Ok, je lance une recherche sur internet. J'analyse d'abord le contexte de la conversation pour mieux comprendre votre demande.",
                content="",
                agent="websearch",
                progress=0.4
            )

        # ✅ NEW: Pass conversation history
        search_results = await web_agent.search(
            query=user_input,
            num_results=5,
            search_depth="basic",
            region="fr-fr",
            conversation_history=conversation_history  # NEW
        )

        # ... rest of the method ...

# Also update _execute_hybrid_sources
async def _execute_hybrid_sources(
    self,
    user_input: str,
    db,
    selected_sources: List[str],
    thought_stream=None,
    state_manager=None,
    conversation_history: List[Dict] = None  # NEW
):
    # ...
    if has_web:
        async def run_web():
            web_agent = WebSearchAgent()

            # ... thoughts ...

            # ✅ NEW: Pass conversation history
            search_results = await web_agent.search(
                query=user_input,
                num_results=5,
                region="fr-fr",
                conversation_history=conversation_history  # NEW
            )

            return search_results
```

---

### 4. Propagation du Contexte depuis l'API

```python
# backend/app/api/chat.py

@router.post("/query")
async def process_query(
    query: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process user query with conversation history"""

    # Extract conversation history from request
    conversation_history = query.conversation_history or []

    # Pass to orchestrator
    response = await orchestrator.process(
        user_input=query.message,
        db=db,
        selected_sources=query.selected_sources,
        context=context,
        state_manager=state_manager,
        conversation_history=conversation_history,  # NEW
        thought_stream=thought_stream
    )

    return response
```

---

## 📊 Exemples Concrets

### Exemple 1 : Référence Implicite

**Conversation** :
```
User: "Que dit la LOI n° 2024-322 du 9 avril 2024 ?"
Assistant: [Réponse sur la loi rénovation habitat]

User: "Et pour les copropriétaires ?"
```

**Sans contexte** :
```
Requête envoyée à DuckDuckGo: "Et pour les copropriétaires ?"
Résultats: Articles généraux sur copropriété (non pertinents)
```

**Avec contexte** :
```
Détection: "Et pour" → Besoin de contexte
Enrichissement LLM:
  Input: "Et pour les copropriétaires ?"
  Context: "USER: Que dit la LOI n° 2024-322... ASSISTANT: La loi vise..."
  Output: "LOI 2024-322 avril 2024 copropriétaires obligations"

Requête envoyée à DuckDuckGo: "LOI 2024-322 avril 2024 copropriétaires obligations"
Résultats: Articles sur obligations copropriétaires dans cette loi (pertinents!)
```

---

### Exemple 2 : Correction

**Conversation** :
```
User: "Trouve des plombiers à Paris"
Assistant: [Résultats plombiers Paris]

User: "Non, je veux des plombiers spécialisés en copropriété avec urgence 24/7"
```

**Sans contexte** :
```
Requête: "Non, je veux des plombiers spécialisés en copropriété avec urgence 24/7"
Résultats: Mauvais (phrase négative)
```

**Avec contexte** :
```
Détection: "Non, je veux" → Correction/raffinement
Enrichissement LLM:
  Input: "Non, je veux des plombiers spécialisés en copropriété avec urgence 24/7"
  Context: "USER: plombiers Paris ASSISTANT: [résultats]"
  Output: "plombiers spécialisés copropriété urgence 24/7 Paris"

Requête: "plombiers spécialisés copropriété urgence 24/7 Paris"
Résultats: Plombiers copro avec service urgence (pertinents!)
```

---

### Exemple 3 : Suite Logique

**Conversation** :
```
User: "Informations sur la loi Elan"
Assistant: [Résumé loi Elan]

User: "Les décrets d'application"
```

**Sans contexte** :
```
Requête: "Les décrets d'application"
Résultats: Générique sur décrets (non pertinents)
```

**Avec contexte** :
```
Détection: "Les décrets" → Référence courte
Enrichissement LLM:
  Input: "Les décrets d'application"
  Context: "USER: loi Elan ASSISTANT: [résumé]"
  Output: "décrets application loi Elan logement"

Requête: "décrets application loi Elan logement"
Résultats: Décrets Elan spécifiques (pertinents!)
```

---

## 🎨 CoT Enrichie avec Contexte

### Avant (Sans Contexte)

```
💭 Raisonnement

  🌐 WEB  → Ok, je lance une recherche sur internet...

  🌐 WEB  → Trouvé 5 sources web. Scores : 45%, 42%, 38%.
  ✓        Hmm, scores moyens. Résultats peu pertinents.
```

### Après (Avec Contexte)

```
💭 Raisonnement

  🌐 WEB  → Ok, je lance une recherche sur internet. J'analyse d'abord
            le contexte de la conversation pour mieux comprendre votre demande.

  🔄 CONTEXT → Je détecte une référence au message précédent sur "LOI 2024-322".
            Je reformule votre question : "LOI 2024-322 copropriétaires obligations"

  🌐 WEB  → Trouvé 5 sources web. Scores : 92%, 88%, 85%.
  ✓        Excellent ! Les sources web sont très pertinentes grâce au contexte.
            Sources : legifrance.gouv.fr, service-public.fr...
```

---

## 📁 Modifications Nécessaires

### Fichiers à Modifier

1. **`backend/app/services/agents/websearch_agent.py`**
   - Ajouter paramètre `conversation_history` à `search()`
   - Implémenter `_enrich_query_with_context()`
   - Implémenter `_query_needs_context()`

2. **`backend/app/services/agents/orchestrator_agent.py`**
   - Passer `conversation_history` à `_handle_web_search()`
   - Passer `conversation_history` dans `_execute_hybrid_sources()` → `run_web()`

3. **`backend/app/api/chat.py`**
   - S'assurer que `conversation_history` est bien propagé depuis la requête

4. **Frontend (optionnel - si besoin d'ajustement)**
   - Vérifier que `conversation_history` est bien envoyé dans les requêtes API

---

## 🧪 Tests Recommandés

### Test 1 : Référence Implicite
```python
history = [
    {"role": "user", "content": "Que dit la LOI n° 2024-322 ?"},
    {"role": "assistant", "content": "La loi vise à accélérer la rénovation..."}
]

query = "Et pour les copropriétaires ?"

enriched = await agent._enrich_query_with_context(query, history)
assert "2024-322" in enriched
assert "copropriétaires" in enriched
```

### Test 2 : Requête Autonome
```python
history = [...]
query = "Loi sur la rénovation énergétique 2024"

enriched = await agent._enrich_query_with_context(query, history)
assert enriched == query  # Pas de modification nécessaire
```

### Test 3 : Correction
```python
history = [
    {"role": "user", "content": "Plombiers Paris"},
    {"role": "assistant", "content": "Voici des plombiers..."}
]

query = "Non, je veux spécialisés copropriété"

enriched = await agent._enrich_query_with_context(query, history)
assert "plombiers" in enriched
assert "copropriété" in enriched
assert "Paris" in enriched
```

---

## 🎯 Intégration dans Phase 1

### Option A : Phase 1.5 (Recommandé)

```
Phase 1 : Re-Ranking + Caching (1 jour)
Phase 1.5 : Mémoire Contextuelle (0.5 jour)
  → Total : 1.5 jours
```

**Justification** : La mémoire contextuelle amplifie l'impact du re-ranking en envoyant de meilleures requêtes.

### Option B : Phase 2

```
Phase 1 : Re-Ranking + Caching
Phase 2 : Domain Credibility + Query Expansion + Mémoire Contextuelle
```

---

## 💡 Recommandation Finale

✅ **INCLURE dans Phase 1** car :

1. **Synergie forte** : Mémoire contextuelle → Meilleures requêtes → Re-ranking plus efficace
2. **Impact utilisateur** : Conversations naturelles multi-tours
3. **Complexité acceptable** : +4h développement
4. **Utilise LLM existant** : Mistral déjà disponible

**Temps total Phase 1 révisé** :
- Re-Ranking : 3h
- Caching : 3h
- Mémoire Contextuelle : 4h
- Tests : 2h
**Total : 12h (1.5 jours)**

**Voulez-vous que j'implémente Phase 1 complète avec Mémoire Contextuelle incluse ?** 🚀
