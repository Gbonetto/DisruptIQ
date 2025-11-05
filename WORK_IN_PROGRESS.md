# 🚧 Corrections en Cours - Statut

**Date**: 2025-11-05
**Session**: Correction complète des 7 problèmes identifiés
**Branche**: `claude/review-improvements-011CUpYBLnQQ1aDyL444zNjv`

---

## ✅ Problèmes Résolus (2/7)

### 1. ✅ Import SQL - `is_indexed` NULL
**Commit**: `b613cbe`
**Status**: RÉSOLU ET TESTÉ

**Fix appliqué**:
- Ajout de `is_indexed: False` dans `get_default_values()`
- Ajout de `server_default=text('false')` dans les modèles
- Migration Alembic créée

**Pour appliquer**:
```bash
cd backend
alembic upgrade head
```

---

### 2. ✅ Orchestrateur - Messages de Choix Inutiles
**Commit**: `bc8f026`
**Status**: RÉSOLU

**Fix appliqué**:
- Ajout de mots-clés RAG forts (poids 1.0):
  - "document sélectionné", "ce document", "de quoi parle"
  - "dans le document", "ce fichier"

- Logique de décision améliorée (7 niveaux):
  1. Strong SQL dominance (sql > 0.65, rag < 0.5, diff > 0.2)
  2. Strong RAG dominance (rag > 0.65, sql < 0.5, diff > 0.2)
  3. Moderate SQL preference (sql > 0.5, diff > 0.15)
  4. Moderate RAG preference (rag > 0.5, diff > 0.15)
  5. HYBRID (both > 0.4)
  6. AMBIGUOUS (both < 0.35) - **RARE maintenant**
  7. Fallback (choisit le score le plus élevé)

- AMBIGUOUS ne se déclenche que si les DEUX scores < 0.35

**Impact**: L'assistant demandera beaucoup moins souvent de clarification

**Fichier modifié**: `backend/app/services/agents/intent_classifier_v2.py`

---

### 3. ⚠️ RAG Search - Message d'Erreur Amélioré
**Commit**: À commiter
**Status**: AMÉLIORATION PARTIELLE

**Fix appliqué**:
- Message "Aucun résultat" amélioré avec:
  - Suggestions concrètes (vérifier documents uploadés)
  - Options de reformulation
  - Logs de debugging améliorés

**Fichier modifié**: `backend/app/services/agents/orchestrator_agent.py`

**⚠️ Problème racine non résolu**: Le vrai problème (documents pas trouvés même s'ils existent) nécessite un debug plus approfondi:
- Vérifier extraction texte des PDFs
- Vérifier embeddings
- Vérifier filtres Qdrant
- Voir `ISSUES_ANALYSIS_AND_ROADMAP.md` section "Problème 4"

---

## 🔴 Problèmes À Faire (4 critiques)

### 4. ❌ Gestion des Conversations (Sidebar)
**Priorité**: 🔴 HAUTE
**Estimation**: 4-6 heures
**Status**: NON COMMENCÉ

**Ce qui manque**:
1. **Backend**:
   - Endpoints CRUD (`/api/conversations`)
     - `GET /conversations` - Lister
     - `POST /conversations` - Créer
     - `PATCH /conversations/{id}` - Renommer
     - `DELETE /conversations/{id}` - Supprimer

   - Génération automatique de titres:
     - Service `conversation_service.py`
     - Fonction `generate_conversation_title(messages)`
     - Appel après 2ème tour de conversation

2. **Frontend**:
   - Connecter `MainChatPageV2.tsx` aux endpoints
   - Remplacer mock data par vraies conversations
   - Ajouter menu burger (3 points) sur chaque conversation
   - Implémenter renommer/supprimer

**Plan détaillé**: Voir `ISSUES_ANALYSIS_AND_ROADMAP.md` section "Problème 2"

**Fichiers à créer**:
- `backend/app/api/endpoints/conversations.py`
- `backend/app/services/conversation_service.py`

**Fichiers à modifier**:
- `backend/app/main.py` (ajouter router)
- `frontend/src/pages/MainChatPageV2.tsx`
- `frontend/src/components/chat/ConversationSidebar.tsx`

---

### 5. ❌ RAG Search - Documents Pas Trouvés (Problème Racine)
**Priorité**: 🔴 HAUTE
**Estimation**: 5-6 heures
**Status**: DIAGNOSTIC NÉCESSAIRE

**Hypothèses**:
1. **PDFs avec images** → Extraction texte échoue
2. **Documents pas indexés** → `is_indexed=False` dans DB
3. **Embeddings incorrects** → Vecteurs pas créés
4. **Threshold trop strict** → (NON, pas de threshold trouvé)

**Actions à faire**:
1. **Vérifier indexation**:
   ```sql
   SELECT id, original_filename, indexed, processed
   FROM documents
   WHERE indexed = true;
   ```

2. **Vérifier Qdrant**:
   ```bash
   curl http://localhost:6333/collections/documents
   # Vérifier point count
   ```

3. **Ajouter logs détaillés**:
   - Dans `rag_service.search()` : log query + results
   - Dans `document_service.extract_text()` : log extraction
   - Dans `rag_service.index_document_chunks()` : log indexation

4. **Tester extraction**:
   - Upload un PDF simple avec texte
   - Vérifier que texte est extrait
   - Vérifier que chunks sont créés
   - Vérifier que Qdrant reçoit les points

**Fichiers concernés**:
- `backend/app/services/rag_service.py`
- `backend/app/services/document_service.py`
- `backend/app/api/endpoints/documents.py`

---

### 6. ❌ SQL Agent - Intelligence Limitée
**Priorité**: 🟡 MOYENNE
**Estimation**: 6 heures
**Status**: NON COMMENCÉ

**Améliorations nécessaires**:
1. **Prompts optimisés**:
   - Ajouter schéma complet des tables
   - Ajouter exemples de requêtes
   - Règles SQL (ILIKE, LIMIT, etc.)

2. **Schema Context**:
   - Fonction `get_schema_context()`
   - Description colonnes + types
   - Relations entre tables

3. **Gestion d'erreurs**:
   - Validation SQL avant exécution
   - Retry avec correction automatique
   - Messages d'erreur explicites

**Plan détaillé**: Voir `ISSUES_ANALYSIS_AND_ROADMAP.md` section "Problème 5"

---

### 7. ❌ Titres de Conversations Automatiques
**Priorité**: 🟡 MOYENNE
**Estimation**: 2 heures
**Status**: NON COMMENCÉ (lié au #4)

**Implémentation**:
```python
async def generate_conversation_title(messages: List[dict]) -> str:
    """Génère un titre basé sur les 3 premiers échanges"""
    first_messages = messages[:6]  # 3 user + 3 assistant

    prompt = f\"\"\"Génère un titre court (max 50 caractères):

    {format_messages(first_messages)}

    Titre:\"\"\"

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=20,
        temperature=0.3
    )

    return response.choices[0].message.content.strip()
```

**Appel**: Après le 2ème tour de conversation (4 messages)

---

## 🟢 Problèmes Polish (2 à faire)

### 8. ❌ CoT (Chain of Thoughts) Pas Affiché
**Priorité**: 🟡 MOYENNE
**Estimation**: 2-3 heures
**Status**: NON COMMENCÉ

**Diagnostic**:
- Component existe: `ChainOfThoughts.tsx` ✅
- Frontend prêt: `MainChatPageV2.tsx` écoute `event: thought` ✅
- **Problème**: Backend n'envoie pas les events `thought` ❌

**Fix nécessaire**: Dans `assistant_v2_stream.py`, ajouter:
```python
# Avant chaque étape
yield f"event: thought\ndata: {json.dumps({
    'id': str(uuid.uuid4()),
    'type': 'analyzing',  # ou 'classifying', 'executing', etc.
    'timestamp': datetime.now().isoformat(),
    'title': 'Analyse de la question',
    'content': 'Je comprends votre demande...',
    'progress': 0.2
})}\n\n"
```

**Fichier à modifier**: `backend/app/api/endpoints/assistant_v2_stream.py`

---

### 9. ❌ Sources Pas Affichées
**Priorité**: 🟡 MOYENNE
**Estimation**: 2 heures
**Status**: NON COMMENCÉ

**Diagnostic**:
- Component existe: `SourceCitation.tsx` ✅
- Frontend prêt: `ChatMessage.tsx` affiche si `sources` existe ✅
- **Problème**: Backend n'envoie pas `sources` dans la réponse ❌

**Fix nécessaire**: Dans `assistant_v2_stream.py`, dans l'event `response`:
```python
yield f"event: response\ndata: {json.dumps({
    'message': final_answer,
    'sources': [
        {
            'type': 'rag',  # ou 'sql', 'web'
            'title': 'Document XYZ.pdf',
            'metadata': {
                'page': 5,
                'score': 0.87
            }
        }
    ],
    'table_data': table_data if table_data else None
})}\n\n"
```

**Fichier à modifier**: `backend/app/api/endpoints/assistant_v2_stream.py`

---

## 📊 Résumé de Progression

| # | Problème | Priorité | Estimé | Status | Temps Restant |
|---|----------|----------|--------|--------|---------------|
| 1 | ✅ Import SQL | 🔴 | 1h | RÉSOLU | - |
| 2 | ✅ Orchestrateur | 🔴 | 4-5h | RÉSOLU | - |
| 3 | ⚠️ RAG message | 🔴 | 5-6h | PARTIEL | 4-5h |
| 4 | ❌ Conversations | 🔴 | 4-6h | À FAIRE | 4-6h |
| 5 | ❌ RAG root cause | 🔴 | 5-6h | À FAIRE | 5-6h |
| 6 | ❌ SQL Agent | 🟡 | 6h | À FAIRE | 6h |
| 7 | ❌ Titres auto | 🟡 | 2h | À FAIRE | 2h |
| 8 | ❌ CoT | 🟡 | 2-3h | À FAIRE | 2-3h |
| 9 | ❌ Sources | 🟡 | 2h | À FAIRE | 2h |

**Progression**: 2.5/9 problèmes résolus (28%)
**Temps passé**: ~3 heures
**Temps restant estimé**: 21-26 heures

---

## 🎯 Prochaines Étapes Recommandées

### Sprint 1 (Urgent - MAINTENANT)
1. ✅ ~~Orchestrateur~~ (FAIT)
2. ⏳ **RAG root cause debug** (4-5h)
   - Vérifier extraction PDFs
   - Vérifier indexation Qdrant
   - Ajouter logs détaillés

3. ⏳ **Conversations CRUD** (4-6h)
   - Créer endpoints backend
   - Connecter frontend
   - Ajouter menu burger

**Résultat Sprint 1**: Assistant intelligent + Sidebar fonctionnelle

---

### Sprint 2 (Important)
4. SQL Agent amélioration (6h)
5. Titres automatiques (2h)

---

### Sprint 3 (Polish)
6. CoT connexion (2-3h)
7. Sources affichage (2h)

---

## 💻 Commandes Utiles

### Appliquer Migration SQL
```bash
cd backend
alembic upgrade head
```

### Redémarrer Backend
```bash
cd backend
uvicorn app.main:app --reload
```

### Tester Endpoints
```bash
# Health check
curl http://localhost:8000/api/health

# List documents
curl http://localhost:8000/api/documents

# Test RAG search
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "plombier", "limit": 5}'
```

### Vérifier Qdrant
```bash
# Collection info
curl http://localhost:6333/collections/documents

# Point count
curl http://localhost:6333/collections/documents/points/count
```

### Vérifier Base de Données
```bash
psql -h localhost -U disruptiq -d disruptiq

# Vérifier documents
SELECT id, original_filename, indexed, processed
FROM documents
ORDER BY id DESC
LIMIT 10;

# Vérifier is_indexed
SELECT COUNT(*) FROM coproprietaires WHERE is_indexed IS NULL;
```

---

## 📝 Notes de Session

**Commits créés**:
1. `b613cbe` - Fix import SQL is_indexed
2. `bc8f026` - Fix orchestrator intent classification
3. *(à créer)* - Fix RAG error message + WORK_IN_PROGRESS doc

**Fichiers modifiés**:
- ✅ `backend/app/api/endpoints/sql_tables.py`
- ✅ `backend/app/models/coproprietaire.py`
- ✅ `backend/app/models/copropriete.py`
- ✅ `backend/migrations/versions/20251105_add_is_indexed_default.py`
- ✅ `backend/app/services/agents/intent_classifier_v2.py`
- ✅ `backend/app/services/agents/orchestrator_agent.py`

**Prochains fichiers à modifier** (Sprint 1):
- `backend/app/api/endpoints/conversations.py` (créer)
- `backend/app/services/conversation_service.py` (créer)
- `backend/app/main.py` (ajouter router)
- `frontend/src/pages/MainChatPageV2.tsx`
- `frontend/src/components/chat/ConversationSidebar.tsx`

---

**Dernière mise à jour**: 2025-11-05
**Status global**: 🟡 EN COURS (28% complété)
