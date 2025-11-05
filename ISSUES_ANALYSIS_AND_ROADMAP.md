# 🐛 Analyse des Problèmes et Plan d'Action - DisruptIQ

**Date**: 2025-11-05
**Branche**: `claude/review-improvements-011CUpYBLnQQ1aDyL444zNjv`
**Status**: 1/10 problèmes résolus

---

## ✅ Problème 1: Import SQL - is_indexed NULL (RÉSOLU)

### Problème
```
(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError)
null value in column "is_indexed" of relation "coproprietaires"
violates not-null constraint
```

### Solution Implémentée
**Commit**: `b613cbe` - "fix: Add is_indexed default value"

1. ✅ `sql_tables.py`: Ajout de `is_indexed: False` dans `get_default_values()` pour coproprietaires et coproprietes
2. ✅ Modèles: Ajout de `server_default=text('false')` aux colonnes `is_indexed`
3. ✅ Migration Alembic créée: `20251105_add_is_indexed_default.py`

### Application
```bash
cd backend
alembic upgrade head  # Applique la migration
```

---

## ❌ Problème 2: Gestion des Conversations (Sidebar)

### Symptômes
1. **Bouton "Nouvelle conversation"** ne fonctionne pas
2. **Pas de menu pour renommer/supprimer** les conversations
3. **Titres de conversations** ne reflètent pas le contenu (mock data)

### Diagnostic

**Frontend** (`MainChatPageV2.tsx:77-92`):
```typescript
// Conversations mockées actuellement
const [conversations, _setConversations] = useState<Conversation[]>([
  {
    id: '1',
    title: 'Analyse facture plomberie',  // <-- Titre en dur
    preview: 'Vérifier la facture de plomberie...',
    timestamp: new Date(Date.now() - 3600000),
    messageCount: 5
  }
]);
```

**Backend**: Le modèle `ConversationSession` existe (`backend/app/models/conversation.py:18-48`), mais :
- ❌ Pas d'endpoints CRUD pour conversations
- ❌ Pas de génération automatique de titres
- ❌ Pas de liaison avec `assistant_v2_stream.py`

### Plan d'Action

#### 📝 Étape 2.1: Créer les Endpoints Backend

**Fichier à créer**: `backend/app/api/endpoints/conversations.py`

```python
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import ConversationSession, ConversationTurn
from app.core.database import get_db

router = APIRouter()

@router.get("/conversations")
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List user conversations with metadata"""
    # Implémenter: Query DB avec SQLAlchemy
    pass

@router.post("/conversations")
async def create_conversation(db: AsyncSession = Depends(get_db)):
    """Create a new conversation session"""
    # Implémenter: Créer ConversationSession avec titre généré par LLM
    pass

@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    title: str,
    db: AsyncSession = Depends(get_db)
):
    """Rename a conversation"""
    # Implémenter: UPDATE ConversationSession SET title
    pass

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation and all its turns"""
    # Implémenter: DELETE CASCADE ConversationSession
    pass
```

**Ajouter au router principal** (`backend/app/main.py`):
```python
from app.api.endpoints import ..., conversations

app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
```

#### 📝 Étape 2.2: Générer Titres Intelligents

**Fonction utilitaire**: `backend/app/services/conversation_service.py`

```python
import openai
from typing import List

async def generate_conversation_title(messages: List[dict]) -> str:
    """
    Génère un titre intelligent basé sur les 3 premiers messages

    Args:
        messages: Liste des messages [{role, content}, ...]

    Returns:
        Titre court (< 50 caractères)
    """
    # Prendre les 3 premiers échanges
    first_messages = messages[:6]  # 3 user + 3 assistant

    prompt = f"""Génère un titre court (max 50 caractères) pour cette conversation:

{format_messages(first_messages)}

Titre:"""

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=20,
        temperature=0.3
    )

    return response.choices[0].message.content.strip()
```

**Appel automatique**: Après le 2ème tour de conversation, générer le titre et le sauvegarder.

#### 📝 Étape 2.3: Connecter Frontend aux Endpoints

**Modifier** `frontend/src/pages/MainChatPageV2.tsx`:

```typescript
// Remplacer le state mocké
const [conversations, setConversations] = useState<Conversation[]>([]);

// Charger les conversations au montage
useEffect(() => {
  fetchConversations();
}, []);

const fetchConversations = async () => {
  const response = await fetch(`${API_BASE_URL}/api/conversations`);
  const data = await response.json();
  setConversations(data);
};

const handleNewConversation = async () => {
  const response = await fetch(`${API_BASE_URL}/api/conversations`, {
    method: 'POST'
  });
  const newConv = await response.json();
  setConversations(prev => [newConv, ...prev]);
  setActiveConversationId(newConv.id);
  setMessages([]);  // Clear current messages
};

const handleRenameConversation = async (convId: string, newTitle: string) => {
  await fetch(`${API_BASE_URL}/api/conversations/${convId}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title: newTitle})
  });
  fetchConversations();  // Reload
};

const handleDeleteConversation = async (convId: string) => {
  await fetch(`${API_BASE_URL}/api/conversations/${convId}`, {
    method: 'DELETE'
  });
  fetchConversations();  // Reload
};
```

#### 📝 Étape 2.4: Ajouter Menu Burger (3 points)

**Modifier** `frontend/src/components/chat/ConversationSidebar.tsx`:

```typescript
import { MoreVertical, Edit2, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// Dans le component ConversationSidebar
const [openMenuId, setOpenMenuId] = useState<string | null>(null);

// Dans le JSX de chaque conversation
<div className="flex items-center justify-between">
  <button onClick={() => onSelectConversation(conversation.id)}>
    {/* Titre et preview */}
  </button>

  {/* Menu 3 points */}
  <div className="relative">
    <button
      onClick={(e) => {
        e.stopPropagation();
        setOpenMenuId(openMenuId === conversation.id ? null : conversation.id);
      }}
      className="p-1 hover:bg-gray-200 rounded"
    >
      <MoreVertical className="w-4 h-4 text-gray-500" />
    </button>

    {/* Dropdown menu */}
    <AnimatePresence>
      {openMenuId === conversation.id && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="absolute right-0 top-8 bg-white border rounded-lg shadow-lg z-50 w-40"
        >
          <button
            onClick={() => {
              const newTitle = prompt('Nouveau titre:', conversation.title);
              if (newTitle) onRenameConversation(conversation.id, newTitle);
              setOpenMenuId(null);
            }}
            className="flex items-center gap-2 w-full px-3 py-2 hover:bg-gray-50"
          >
            <Edit2 className="w-3.5 h-3.5" />
            Renommer
          </button>
          <button
            onClick={() => {
              if (confirm('Supprimer cette conversation ?')) {
                onDeleteConversation(conversation.id);
              }
              setOpenMenuId(null);
            }}
            className="flex items-center gap-2 w-full px-3 py-2 hover:bg-red-50 text-red-600"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Supprimer
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  </div>
</div>
```

### Estimation
- **Backend**: 2-3 heures
- **Frontend**: 1-2 heures
- **Tests**: 1 heure
- **Total**: 4-6 heures

---

## ❌ Problème 3: Orchestrateur - Messages de Choix Inutiles

### Symptôme
```
U: de quoi parle le document sélectionné dans le RAG ?
AI: Je peux vous aider de plusieurs façons...
    Choisissez une option:
    1. Chercher dans les documents uploadés

    Que souhaitez-vous ?
```

**Problème**: L'assistant demande systématiquement à l'utilisateur de choisir, même quand l'intent est clair.

### Diagnostic

**Fichier**: `backend/app/services/orchestrator_service.py`

Le problème vient probablement d'une logique de classification trop prudente qui:
1. Détecte plusieurs intents possibles
2. Renvoie un message de choix au lieu de prendre une décision

### Plan d'Action

#### 📝 Étape 3.1: Analyser l'Orchestrateur

```bash
# Lire le fichier orchestrator
grep -n "Choisissez une option\|Je peux vous aider" backend/app/services/orchestrator_service.py
```

#### 📝 Étape 3.2: Améliorer la Logique de Décision

**Stratégie**:
- Si confidence > 0.7 pour un seul intent → Exécuter directement
- Si ambiguïté réelle (2 intents > 0.6) → Demander clarification
- Sinon → Choisir l'intent le plus probable

**Pseudo-code**:
```python
async def orchestrate(query: str, context: dict):
    intents = await classify_intent(query)

    # Si un intent clair domine
    if intents[0].confidence > 0.7 and intents[1].confidence < 0.5:
        return await execute_intent(intents[0])

    # Si vraiment ambigu
    elif intents[0].confidence - intents[1].confidence < 0.15:
        return await ask_clarification(intents[:2])

    # Sinon, choisir le meilleur
    else:
        return await execute_intent(intents[0])
```

#### 📝 Étape 3.3: Améliorer la Classification

**Mots-clés forts** pour intent automatique:
```python
RAG_KEYWORDS = [
    'document sélectionné', 'ce document', 'ce pdf',
    'dans le document', 'document uploadé', 'fichier'
]

SQL_KEYWORDS = [
    'base de données', 'combien de', 'liste des',
    'tous les', 'table', 'nombre de'
]

WEB_KEYWORDS = [
    'sur internet', 'sur le web', 'cherche sur',
    'google', 'recherche en ligne'
]
```

### Estimation
- **Analyse**: 1 heure
- **Implémentation**: 2-3 heures
- **Tests**: 1 heure
- **Total**: 4-5 heures

---

## ❌ Problème 4: RAG Search - "Aucun résultat trouvé"

### Symptôme
```
U: combien coûte le plombier ?
AI: (option 2 = documents)
AI: Je n'ai trouvé aucun résultat pour votre question.
```

**Mais**: Il y a 2 PDFs avec des infos sur le plombier dans le RAG !

### Diagnostic Possible

#### Cause 1: Documents pas indexés dans Qdrant
```python
# Vérifier si documents sont indexés
is_indexed = False pour les documents uploadés
```

#### Cause 2: Requête de recherche mal formulée
```python
# La requête envoyée à Qdrant ne match pas le contenu
search_query = "combien coûte le plombier"
# Mais le document contient: "Tarif plomberie: 85€/heure"
```

#### Cause 3: Threshold de similarité trop élevé
```python
# Seuil de score trop strict
score_threshold = 0.8  # Trop élevé
results = [r for r in results if r.score > 0.8]  # <-- Rejette tout
```

### Plan d'Action

#### 📝 Étape 4.1: Vérifier l'Indexation

**Fichier**: `backend/app/services/rag_service.py` ou `document_service.py`

```bash
# Trouver le service RAG
find backend/app/services -name "*rag*" -o -name "*document*"
```

**Vérifications**:
1. Les documents sont-ils indexés automatiquement après upload ?
2. La colonne `is_indexed` est-elle mise à jour ?
3. Le contenu est-il bien extrait (PDF, texte) ?

#### 📝 Étape 4.2: Debug la Recherche

**Ajouter des logs détaillés**:
```python
async def search_documents(query: str, limit: int = 5):
    logger.info("rag_search_start", query=query)

    # Embedding de la requête
    query_embedding = await get_embedding(query)
    logger.info("query_embedded", query=query, embedding_dim=len(query_embedding))

    # Recherche dans Qdrant
    results = await qdrant_client.search(
        collection_name="documents",
        query_vector=query_embedding,
        limit=limit,
        score_threshold=0.3  # <-- BAISSER pour tester
    )

    logger.info("rag_search_results",
                query=query,
                results_count=len(results),
                scores=[r.score for r in results])

    if not results:
        logger.warning("rag_search_no_results", query=query)

    return results
```

#### 📝 Étape 4.3: Améliorer la Recherche

**Stratégies**:

1. **Query Expansion**:
```python
# Ajouter des synonymes
query = "combien coûte le plombier"
expanded = [
    "combien coûte le plombier",
    "tarif plombier",
    "prix plomberie",
    "coût intervention plombier"
]
# Chercher avec toutes les variantes
```

2. **Hybrid Search** (BM25 + Vector):
```python
# Combiner recherche vectorielle + keyword
vector_results = await vector_search(query)
keyword_results = await keyword_search(query)
combined = merge_results(vector_results, keyword_results)
```

3. **Reranking**:
```python
# Après la recherche, reranker avec un modèle plus précis
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([(query, doc.text) for doc in results])
```

### Estimation
- **Debug**: 2 heures
- **Fixes**: 2-3 heures
- **Tests**: 1 heure
- **Total**: 5-6 heures

---

## ❌ Problème 5: SQL Agent - Intelligence Limitée

### Symptôme
L'agent SQL ne comprend pas bien les requêtes complexes ou ne génère pas les bons SQL.

### Diagnostic Nécessaire

**À analyser**:
```bash
# Trouver le service SQL agent
find backend/app/services -name "*sql*"
```

**Questions**:
1. Utilise-t-il des prompts optimisés ?
2. A-t-il accès au schéma complet des tables ?
3. Valide-t-il le SQL avant exécution ?
4. Gère-t-il les erreurs et retry ?

### Plan d'Action

#### 📝 Étape 5.1: Auditer l'Agent SQL

Lire et analyser:
- `backend/app/services/sql_agent_service.py`
- Prompts utilisés
- Gestion des erreurs
- Logs de requêtes échouées

#### 📝 Étape 5.2: Améliorer les Prompts

**Exemple de prompt amélioré**:
```python
SQL_AGENT_PROMPT = """Tu es un expert SQL PostgreSQL.
Génère une requête SQL pour répondre à la question.

SCHÉMA DISPONIBLE:
{schema_info}

EXEMPLES DE REQUÊTES:
- "Combien de professionnels ?" -> SELECT COUNT(*) FROM professionnels;
- "Liste des plombiers" -> SELECT * FROM professionnels WHERE metier ILIKE '%plomb%';

RÈGLES:
1. Utilise ILIKE pour la recherche texte (insensible à la casse)
2. Limite les résultats à 100 par défaut
3. Formate les résultats de manière lisible
4. Vérifie que les colonnes existent avant de les utiliser

QUESTION: {user_question}

SQL:"""
```

#### 📝 Étape 5.3: Ajouter Schema Context

```python
async def get_schema_context() -> str:
    """Génère une description complète du schéma pour l'agent"""
    tables = ['professionnels', 'coproprietaires', 'coproprietes']
    schema_desc = []

    for table in tables:
        columns = await get_table_columns(table)
        schema_desc.append(f"Table {table}:")
        for col in columns:
            schema_desc.append(f"  - {col.name} ({col.type})")

    return "\n".join(schema_desc)
```

### Estimation
- **Audit**: 2 heures
- **Amélioration prompts**: 2 heures
- **Tests**: 2 heures
- **Total**: 6 heures

---

## ❌ Problème 6: CoT (Chain of Thoughts) - Ancien Style

### Symptôme
Le CoT affiché n'est pas le nouveau style dynamique DeepSeek.

### Diagnostic

**Frontend**: Le component `ChainOfThoughts` existe (`frontend/src/components/ChainOfThoughts.tsx`) et est bien stylé.

**Problème**: Le backend n'envoie peut-être pas les thoughts au bon format, ou le frontend ne les affiche pas.

### Vérification

**Dans** `MainChatPageV2.tsx:253-264`:
```typescript
eventSource.addEventListener('thought', (e) => {
  const thought = JSON.parse(e.data);
  setCurrentThoughts(prev => [...prev, thought]);
});
```

**Le backend envoie-t-il** des events `thought` ?

**Vérifier** dans `backend/app/api/endpoints/assistant_v2_stream.py`:
```python
# Doit contenir des lignes comme:
yield f"event: thought\ndata: {json.dumps(thought_data)}\n\n"
```

### Plan d'Action

#### 📝 Étape 6.1: Vérifier Backend Envoie Thoughts

```bash
# Lire le fichier assistant_v2_stream
grep -n "event: thought" backend/app/api/endpoints/assistant_v2_stream.py
```

#### 📝 Étape 6.2: Ajouter Thoughts si Manquant

```python
async def stream_chat_response(query: str):
    # Avant chaque étape, envoyer un thought
    yield f"event: thought\ndata: {json.dumps({
        'id': str(uuid.uuid4()),
        'type': 'analyzing',
        'timestamp': datetime.now().isoformat(),
        'title': 'Analyse de la question',
        'content': 'Je comprends votre demande...',
        'progress': 0.2
    })}\n\n"

    # Classification
    intent = await classify(query)
    yield f"event: thought\ndata: {json.dumps({
        'id': str(uuid.uuid4()),
        'type': 'classifying',
        'timestamp': datetime.now().isoformat(),
        'title': 'Classification de l\'intent',
        'content': f'Intent détecté: {intent}',
        'progress': 0.4
    })}\n\n"

    # Exécution
    yield f"event: thought\ndata: {json.dumps({
        'id': str(uuid.uuid4()),
        'type': 'executing',
        'timestamp': datetime.now().isoformat(),
        'title': 'Exécution de la requête',
        'content': 'Recherche en cours...',
        'progress': 0.7
    })}\n\n"
```

#### 📝 Étape 6.3: Tester l'Affichage

Ouvrir le frontend et vérifier que le CoT s'affiche en temps réel.

### Estimation
- **Vérification**: 30 min
- **Implémentation**: 1-2 heures
- **Tests**: 30 min
- **Total**: 2-3 heures

---

## ❌ Problème 7: Sources - Pas Affichées

### Symptôme
Les sources ne s'affichent pas avec le nouveau style élégant.

### Diagnostic

**Component existe**: `frontend/src/components/chat/SourceCitation.tsx` ✅

**Utilisé dans**: `ChatMessage.tsx:67-68`
```typescript
{sources && <SourceCitation sources={sources} />}
```

**Le backend envoie-t-il** des sources dans la réponse SSE ?

### Plan d'Action

#### 📝 Étape 7.1: Vérifier Backend Envoie Sources

**Dans** `assistant_v2_stream.py`:
```python
# Doit contenir:
yield f"event: response\ndata: {json.dumps({
    'message': answer,
    'sources': [
        {
            'type': 'rag',  # ou 'sql', 'web'
            'title': 'Document XYZ',
            'metadata': {'page': 5}
        }
    ]
})}\n\n"
```

#### 📝 Étape 7.2: Ajouter Sources si Manquant

**Exemple avec RAG**:
```python
# Après recherche RAG
rag_results = await rag_service.search(query)

sources = [
    {
        'type': 'rag',
        'title': result.metadata.get('filename', 'Document'),
        'metadata': {
            'page': result.metadata.get('page'),
            'score': result.score
        }
    }
    for result in rag_results
]

response_data = {
    'message': final_answer,
    'sources': sources,
    'table_data': table_data if table_data else None
}
```

**Exemple avec SQL**:
```python
# Après requête SQL
sources = [{
    'type': 'sql',
    'title': f"Table: {table_name}",
    'metadata': {
        'query': sql_query,
        'rows_returned': len(results)
    }
}]
```

### Estimation
- **Vérification**: 30 min
- **Implémentation**: 1 heure
- **Tests**: 30 min
- **Total**: 2 heures

---

## 📊 Résumé et Priorisation

| # | Problème | Priorité | Estimation | Status |
|---|----------|----------|------------|--------|
| 1 | ✅ Import SQL `is_indexed` | 🔴 Critique | 1h | RÉSOLU |
| 2 | ❌ Gestion conversations (sidebar) | 🔴 Haute | 4-6h | À faire |
| 3 | ❌ Orchestrateur - Choix inutiles | 🔴 Haute | 4-5h | À faire |
| 4 | ❌ RAG - Aucun résultat | 🔴 Haute | 5-6h | À faire |
| 5 | ❌ SQL Agent intelligence | 🟡 Moyenne | 6h | À faire |
| 6 | ❌ CoT pas affiché | 🟡 Moyenne | 2-3h | À faire |
| 7 | ❌ Sources pas affichées | 🟡 Moyenne | 2h | À faire |

**Temps total estimé**: 23-27 heures de développement

---

## 🎯 Plan de Développement Recommandé

### Sprint 1 (Urgent - 1-2 jours)
1. ✅ ~~Import SQL fix~~ (FAIT)
2. Orchestrateur intelligent (4-5h)
3. RAG search fixes (5-6h)

**Livrable**: Import fonctionne + Assistant plus intelligent

---

### Sprint 2 (Important - 2-3 jours)
4. Gestion conversations complète (4-6h)
5. SQL agent amélioration (6h)

**Livrable**: Sidebar fonctionnelle + SQL plus smart

---

### Sprint 3 (Polish - 1 jour)
6. CoT connexion (2-3h)
7. Sources affichage (2h)

**Livrable**: Interface complète avec CoT et Sources

---

## 📝 Instructions d'Application

### Appliquer le Fix Import SQL (MAINTENANT)

```bash
cd backend
alembic upgrade head
```

Puis relancer le backend et tester l'import CSV.

---

### Continuer le Développement

Choisir un problème dans l'ordre de priorité et suivre le plan d'action détaillé pour chaque problème.

Chaque problème a:
- ✅ Diagnostic précis
- ✅ Code d'exemple
- ✅ Estimation temps
- ✅ Fichiers concernés

---

## 🔍 Debugging Tips

### Activer les Logs Détaillés

**Backend** (`backend/app/main.py`):
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Frontend** (Console):
```typescript
console.log('SSE Event received:', event);
console.log('Thoughts:', currentThoughts);
console.log('Messages:', messages);
```

### Tester les Endpoints

```bash
# Test conversation creation
curl -X POST http://localhost:8000/api/conversations

# Test RAG search
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "plombier", "limit": 5}'

# Test SQL agent
curl -X POST http://localhost:8000/api/sql/query \
  -H "Content-Type: application/json" \
  -d '{"query": "combien de professionnels"}'
```

---

## 📚 Documentation Utile

- **Qdrant**: https://qdrant.tech/documentation/
- **SQLAlchemy Async**: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Server-Sent Events**: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- **OpenAI Embeddings**: https://platform.openai.com/docs/guides/embeddings

---

**Next Step**: Choisissez le problème à traiter et suivez le plan d'action détaillé ! 🚀
