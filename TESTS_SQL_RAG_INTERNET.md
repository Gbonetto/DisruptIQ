# Tests SQL, RAG et Internet - Scénarios Avancés
**Guide pour Tester l'Intégration de Toutes les Sources de Données**

---

## 📊 Vue d'Ensemble des Sources

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   SQL DB    │      │  RAG/Qdrant  │      │  Internet   │
│  Postgres   │      │   Vectors    │      │  APIs/Web   │
└──────┬──────┘      └──────┬───────┘      └──────┬──────┘
       │                    │                     │
       └────────────┬───────┴─────────────────────┘
                    │
              ┌─────▼──────┐
              │Orchestrator│
              └─────┬──────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
 ┌─────────┐  ┌─────────┐  ┌─────────┐
 │  Legal  │  │  Plomb  │  │ General │
 │  Agent  │  │  Agent  │  │  Agent  │
 └─────────┘  └─────────┘  └─────────┘
```

---

## 🗄️ PARTIE 1: Tests SQL (Base de Données Postgres)

### Préparation: Vérifier les Tables

**Ouvrir psql ou PgAdmin:**
```sql
-- Connexion
psql -h localhost -U disruptiq -d disruptiq

-- Lister les tables
\dt

-- Voir la structure
\d users
\d documents
\d conversations
\d messages
```

### Test SQL.1: Récupération Historique Utilisateur

**Scénario:** Tester si l'agent accède à l'historique des conversations

**Préparation SQL:**
```sql
-- Créer un utilisateur de test
INSERT INTO users (email, hashed_password, full_name)
VALUES ('test@disruptiq.com', 'hashed_pwd', 'Utilisateur Test')
ON CONFLICT (email) DO NOTHING;

-- Créer une conversation passée
INSERT INTO conversations (user_id, title, created_at)
VALUES (
  (SELECT id FROM users WHERE email = 'test@disruptiq.com'),
  'Problème fuite appartement 5B',
  NOW() - INTERVAL '2 days'
);

-- Ajouter des messages
INSERT INTO messages (conversation_id, role, content, created_at)
VALUES (
  (SELECT id FROM conversations WHERE title = 'Problème fuite appartement 5B'),
  'user',
  'J''ai une fuite d''eau dans l''appartement 5B',
  NOW() - INTERVAL '2 days'
);
```

**Actions Interface:**
1. Se connecter avec `test@disruptiq.com`
2. Poser: **"Rappelle-moi le problème que j'avais il y a 2 jours"**

**Résultat Attendu:**
- ✅ Agent récupère l'historique de la BDD
- ✅ Réponse: "Vous aviez mentionné une fuite d'eau dans l'appartement 5B"
- ✅ Contexte conversationnel préservé

**Requête SQL Interne Attendue:**
```sql
SELECT m.content, m.role, m.created_at
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
WHERE c.user_id = ? AND c.created_at > NOW() - INTERVAL '7 days'
ORDER BY m.created_at DESC
LIMIT 50;
```

---

### Test SQL.2: Recherche Documents Uploadés

**Scénario:** Retrouver des documents uploadés précédemment

**Préparation SQL:**
```sql
-- Insérer des documents de test
INSERT INTO documents (user_id, filename, file_type, file_size, upload_date, content)
VALUES
  ((SELECT id FROM users WHERE email = 'test@disruptiq.com'),
   'contrat_syndic_2024.pdf', 'pdf', 245000, NOW() - INTERVAL '5 days',
   'Contrat de syndic avec honoraires 28000€ par an...'),
  ((SELECT id FROM users WHERE email = 'test@disruptiq.com'),
   'bail_commercial_paris.pdf', 'pdf', 180000, NOW() - INTERVAL '10 days',
   'Bail commercial local Paris loyer 3500€...');
```

**Actions Interface:**
1. Poser: **"Quels documents j'ai uploadé récemment?"**

**Résultat Attendu:**
- ✅ Liste des 2 documents avec dates
- ✅ Tri par date (plus récent en premier)

**Requête SQL Interne:**
```sql
SELECT filename, file_type, upload_date, file_size
FROM documents
WHERE user_id = ?
ORDER BY upload_date DESC
LIMIT 10;
```

---

### Test SQL.3: Agrégation de Données

**Scénario:** Statistiques sur les documents

**Actions Interface:**
1. Poser: **"Combien de documents juridiques j'ai dans ma base?"**

**Requête SQL Attendue:**
```sql
SELECT COUNT(*) as total_docs,
       COUNT(CASE WHEN file_type = 'pdf' THEN 1 END) as pdf_count,
       SUM(file_size) as total_size
FROM documents
WHERE user_id = ?;
```

**Résultat Attendu:**
- ✅ Nombre total de documents
- ✅ Répartition par type
- ✅ Taille totale

---

### Test SQL.4: Filtrage par Métadonnées

**Scénario:** Recherche avancée avec filtres

**Préparation SQL:**
```sql
-- Ajouter des métadonnées aux documents
UPDATE documents
SET metadata = jsonb_build_object(
  'type', 'contrat_syndic',
  'annee', 2024,
  'copropriete', 'Les Jardins'
)
WHERE filename = 'contrat_syndic_2024.pdf';
```

**Actions Interface:**
1. Poser: **"Montre-moi tous mes contrats de syndic de 2024"**

**Requête SQL Attendue:**
```sql
SELECT filename, upload_date, metadata
FROM documents
WHERE user_id = ?
  AND metadata->>'type' = 'contrat_syndic'
  AND (metadata->>'annee')::int = 2024
ORDER BY upload_date DESC;
```

**Résultat Attendu:**
- ✅ Filtrage correct par métadonnées JSON
- ✅ Résultats pertinents uniquement

---

## 🧠 PARTIE 2: Tests RAG (Qdrant Vector Database)

### Préparation: Peupler Qdrant

**Script Python pour uploader des documents:**
```python
# À exécuter dans backend/
import asyncio
from app.services.rag_service import RAGService
from app.services.document_processor import DocumentProcessor

async def populate_qdrant():
    rag = RAGService()

    documents = [
        {
            "content": """
            Loi du 10 juillet 1965 fixant le statut de la copropriété
            Article 18: Le syndic ne peut procéder à des travaux sans autorisation
            de l'assemblée générale, sauf en cas d'urgence caractérisée.
            Limite: 5000€ pour travaux urgents.
            """,
            "metadata": {
                "type": "loi",
                "source": "Loi 1965",
                "article": "18"
            }
        },
        {
            "content": """
            Jurisprudence Cass. Civ. 3e, 12 mai 2022:
            Les clauses d'indemnité de résiliation supérieures à 6 mois
            d'honoraires sont considérées comme abusives.
            """,
            "metadata": {
                "type": "jurisprudence",
                "juridiction": "Cass. Civ. 3",
                "date": "2022-05-12"
            }
        },
        {
            "content": """
            Guide pratique copropriété:
            En cas de fuite d'eau, le syndic doit intervenir dans les 24h
            si dégât des eaux. Responsabilité: article 1382 Code civil.
            """,
            "metadata": {
                "type": "guide",
                "sujet": "fuite_eau"
            }
        }
    ]

    for doc in documents:
        await rag.add_document(
            content=doc["content"],
            metadata=doc["metadata"]
        )

    print("✅ Qdrant populated with test documents")

if __name__ == "__main__":
    asyncio.run(populate_qdrant())
```

**Exécuter:**
```bash
cd backend
python -c "import asyncio; from populate_test import populate_qdrant; asyncio.run(populate_qdrant())"
```

---

### Test RAG.1: Recherche Sémantique Simple

**Scénario:** Recherche par similarité vectorielle

**Actions Interface:**
1. Poser: **"Quelles sont les obligations du syndic en cas d'urgence?"**

**Processus Interne Attendu:**
```
1. Query → Embedding (Mistral)
2. Qdrant search (top 3 chunks)
3. Retrieved:
   - Loi 1965 Article 18 (score: 0.89)
   - Guide fuite eau (score: 0.75)
4. LLM synthesis avec context
```

**Résultat Attendu:**
- ✅ Réponse basée sur Loi 1965 Article 18
- ✅ Mention limite 5000€
- ✅ Référence au guide pratique si pertinent
- ✅ Citation de la source

**Vérifier dans les logs:**
```log
[info] rag_search_started query='obligations syndic urgence'
[info] qdrant_search_completed chunks_found=3 top_score=0.89
[info] context_enriched sources=['Loi 1965', 'Guide pratique']
```

---

### Test RAG.2: Filtrage par Métadonnées

**Scénario:** Recherche avec filtres spécifiques

**Actions Interface:**
1. Poser: **"Quelle jurisprudence de 2022 parle des clauses abusives?"**

**Processus Interne:**
```python
# Qdrant filter
filter = {
    "must": [
        {"key": "type", "match": {"value": "jurisprudence"}},
        {"key": "date", "range": {
            "gte": "2022-01-01",
            "lte": "2022-12-31"
        }}
    ]
}
```

**Résultat Attendu:**
- ✅ Retour uniquement jurisprudence 2022
- ✅ Citation: "Cass. Civ. 3e, 12 mai 2022"
- ✅ Pas de documents autres types

---

### Test RAG.3: Hybrid Search (Keyword + Semantic)

**Scénario:** Combiner recherche exacte et sémantique

**Actions Interface:**
1. Poser: **"Article 18 de la Loi de 1965"**

**Processus Attendu:**
```
1. Keyword search: "Article 18" + "Loi 1965"
2. Semantic search: embeddings
3. Merge results (RRF - Reciprocal Rank Fusion)
4. Top 3 chunks retournés
```

**Résultat Attendu:**
- ✅ Match exact en premier (score parfait)
- ✅ Texte complet de l'Article 18
- ✅ Contexte additionnel si disponible

---

### Test RAG.4: Multi-Chunk Aggregation

**Scénario:** Réponse nécessitant plusieurs chunks

**Préparation:** Uploader un long document découpé en chunks

**Actions Interface:**
1. Poser: **"Résume toute la Loi de 1965"**

**Processus Attendu:**
```
1. Retrieve top 10 chunks (Loi 1965)
2. LLM summarize each chunk
3. Aggregate summaries
4. Final synthesis
```

**Résultat Attendu:**
- ✅ Résumé cohérent de plusieurs parties
- ✅ Pas de répétitions
- ✅ Structure logique

---

### Test RAG.5: Cross-Reference avec SQL

**Scénario:** Combiner RAG + SQL

**Actions Interface:**
1. Uploader un document "contrat_syndic.pdf"
2. Poser: **"Compare mon contrat avec les obligations légales du syndic"**

**Processus Attendu:**
```
1. SQL: Récupérer le contrat uploadé
2. RAG: Chercher "obligations légales syndic" → Loi 1965
3. Legal Agent: Comparer les deux
4. Synthesis
```

**Résultat Attendu:**
- ✅ Extraction du contrat depuis SQL
- ✅ Obligations depuis RAG
- ✅ Comparaison point par point
- ✅ Non-conformités identifiées

---

## 🌐 PARTIE 3: Tests Internet (APIs + Web Search)

### Test Internet.1: Légifrance API

**Scénario:** Recherche jurisprudence officielle

**Actions Interface:**
1. Poser: **"Dernières décisions de justice sur les assemblées générales de copropriété"**

**API Call Attendue:**
```http
POST https://api.piste.gouv.fr/dila/legifrance/lf-engine-app/search/juri
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "assemblée générale copropriété",
  "filters": {
    "nature": ["ARRET", "JUGEMENT"],
    "jurisdiction": ["CASS", "CA"]
  },
  "sort": "date DESC",
  "size": 5
}
```

**Résultat Attendu:**
- ✅ 5 décisions officielles récentes
- ✅ Chaque décision avec:
  - ID (JURITEXT...)
  - Titre
  - Juridiction
  - Date
  - Résumé
  - URL legifrance.gouv.fr
- ✅ Synthèse LLM des points clés

**Vérifier Cache:**
```bash
docker exec disruptiq_redis redis-cli
> KEYS legifrance:*
> GET "legifrance:search:assemblée générale copropriété"
```

---

### Test Internet.2: Web Search Fallback (DuckDuckGo)

**Scénario:** Recherche web quand Légifrance insuffisant

**Actions Interface:**
1. Poser: **"Quel est le prix moyen d'un syndic de copropriété en 2024?"**

**Cascade Attendue:**
```
1. Légifrance: Pas de résultat (pas de jurisprudence sur prix)
2. RAG: Aucun document pertinent
3. DuckDuckGo Web Search:
   - Query: "prix moyen syndic copropriété 2024 France"
   - Region: fr-fr
   - Top 5 results
```

**Résultat Attendu:**
- ✅ Sources web récentes (2024)
- ✅ Citation des sites (ex: SeLoger, PAP, etc.)
- ✅ Synthèse des prix trouvés
- ✅ Indication "Source: Recherche Web"

**Logs:**
```log
[info] legifrance_no_results query='prix moyen syndic'
[info] websearch_started provider=duckduckgo query='prix moyen syndic 2024'
[info] websearch_completed results=5 sources=['seloger.com', 'pap.fr']
```

---

### Test Internet.3: Multi-Source Aggregation

**Scénario:** Combiner toutes les sources

**Actions Interface:**
1. Poser: **"Donne-moi une analyse complète sur les clauses de résiliation abusive: jurisprudence officielle, mes documents, et informations récentes du web"**

**Cascade Attendue:**
```
┌─ SQL ───────────┐
│ Mes documents:  │ → contrat_syndic.pdf (clause résiliation 12 mois)
└─────────────────┘

┌─ RAG ───────────┐
│ Loi 1965        │ → Préavis raisonnable requis
│ Guide pratique  │ → Recommandations 3-6 mois
└─────────────────┘

┌─ Légifrance ────┐
│ Jurisprudence   │ → 5 arrêts sur clauses résiliation
└─────────────────┘

┌─ Web Search ────┐
│ Articles 2024   │ → Tendances récentes, nouveaux cas
└─────────────────┘

        ↓
┌─────────────────┐
│ LLM Synthesis   │ → Réponse complète multi-sources
└─────────────────┘
```

**Résultat Attendu:**
- ✅ Section 1: "Dans vos documents"
  - Analyse contrat uploadé
- ✅ Section 2: "Cadre légal"
  - Loi 1965 + guides
- ✅ Section 3: "Jurisprudence officielle"
  - 5 décisions Légifrance
- ✅ Section 4: "Tendances récentes"
  - Articles web 2024
- ✅ Section 5: "Recommandation"
  - Synthèse personnalisée

---

### Test Internet.4: API Rate Limiting

**Scénario:** Tester les limites Légifrance

**Actions:**
1. Poser 10 questions de jurisprudence rapidement (< 1 minute)

**Comportement Attendu:**
- ✅ Questions 1-3: Requêtes API normales
- ✅ Questions 4-10: Cache Redis utilisé
- ✅ Pas d'erreur 429 (Too Many Requests)
- ✅ Graceful degradation si rate limit

**Vérifier Logs:**
```log
[info] legifrance_cache_hit query='...' (questions 4-10)
[info] legifrance_token_reused expires_in=3450
```

---

### Test Internet.5: Network Failure Handling

**Scénario:** Tester résilience réseau

**Préparation:**
```bash
# Simuler coupure Légifrance (bloquer l'IP)
# OU déconnecter temporairement internet
```

**Actions:**
1. Poser: **"Jurisprudence sur copropriété"**

**Comportement Attendu:**
- ✅ Tentative Légifrance: timeout/error
- ✅ Fallback automatique:
  1. RAG local (si docs pertinents)
  2. Web search (si internet OK)
  3. Knowledge base LLM
- ✅ Message: "Légifrance temporairement indisponible, voici ce que je peux vous dire..."
- ✅ Pas de crash

**Logs:**
```log
[warning] legifrance_api_timeout query='copropriété' timeout=30s
[info] falling_back_to_rag
[info] rag_search_completed chunks=3
```

---

## 🧪 PARTIE 4: Tests de Performance Multi-Sources

### Test Perf.1: Query Complexe Multi-Sources

**Scénario:** Tester temps de réponse avec toutes sources

**Query:**
**"Analyse mon contrat de syndic (uploadé), compare-le avec la Loi de 1965, donne-moi la jurisprudence récente sur ce type de contrat, et dis-moi si les honoraires sont dans la moyenne du marché 2024"**

**Sources Utilisées:**
- ✅ SQL: Récupérer contrat uploadé
- ✅ RAG: Loi 1965 Article 18
- ✅ Légifrance: Jurisprudence contrats syndic
- ✅ Web Search: Prix marché 2024

**KPIs:**
- Temps total: < 45 secondes
- Appels parallèles quand possible
- Cache hits: > 30%

---

### Test Perf.2: Cache Effectiveness

**Scénario:** Mesurer l'impact du cache

**Actions:**
1. Vider le cache Redis:
   ```bash
   docker exec disruptiq_redis redis-cli FLUSHDB
   ```

2. Poser 5x la même question: **"Jurisprudence assemblée générale"**

**Mesures:**
| Essai | Source | Temps | Cache |
|-------|--------|-------|-------|
| 1 | Légifrance API | 6.5s | MISS |
| 2 | Redis cache | 1.2s | HIT |
| 3 | Redis cache | 1.1s | HIT |
| 4 | Redis cache | 1.0s | HIT |
| 5 | Redis cache | 1.1s | HIT |

**Gain:** ~82% plus rapide avec cache

---

### Test Perf.3: Parallel Query Execution

**Scénario:** Tester parallélisation

**Query:**
**"Donne-moi simultanément: jurisprudence AG + mes contrats uploadés + prix marché syndic"**

**Exécution Attendue (parallèle):**
```python
async def handle_query():
    # Lancement parallèle
    results = await asyncio.gather(
        legifrance_search("assemblée générale"),
        sql_get_documents(user_id),
        web_search("prix syndic 2024")
    )

    # Synthesis
    return llm_synthesize(results)
```

**KPIs:**
- Séquentiel: ~20s (6s + 2s + 12s)
- Parallèle: ~12s (max des 3)
- Gain: ~40% plus rapide

---

## 📝 PARTIE 5: Tests de Cohérence Cross-Source

### Test Cohérence.1: Contradiction Detection

**Scénario:** Gérer informations contradictoires

**Préparation:**
- SQL: Document uploadé dit "préavis 6 mois"
- RAG: Loi dit "préavis raisonnable 3 mois"
- Web: Article dit "standard 3 mois"

**Query:**
**"Mon contrat dit préavis 6 mois, est-ce légal?"**

**Résultat Attendu:**
- ✅ Détection contradiction
- ✅ Explication:
  - "Votre contrat: 6 mois"
  - "Loi recommande: 3 mois"
  - "Jurisprudence considère > 6 mois excessif"
- ✅ Recommandation: "Clause potentiellement abusive"

---

### Test Cohérence.2: Source Priority

**Scénario:** Prioriser sources officielles

**Query:**
**"Quelle est la durée légale d'un contrat de syndic?"**

**Sources Available:**
- RAG: Loi 1965 (source officielle)
- Web: Article blog (source non officielle)

**Résultat Attendu:**
- ✅ Priorité à la Loi 1965
- ✅ Mention blog comme info complémentaire
- ✅ Citation: "Selon la Loi du 10 juillet 1965..."

---

### Test Cohérence.3: Temporal Consistency

**Scénario:** Gérer évolutions temporelles

**Préparation:**
- RAG: Loi 1965 (ancienne)
- Légifrance: Jurisprudence 2024 (récente)
- Web: Article 2024 (actuel)

**Query:**
**"Quelle est la réglementation actuelle sur les assemblées générales?"**

**Résultat Attendu:**
- ✅ Base: Loi 1965 (fondement)
- ✅ Évolutions: Jurisprudence 2024
- ✅ Pratique actuelle: Articles web
- ✅ Indication temporalité: "La loi de 1965, modifiée par..."

---

## 🎯 Checklist de Validation Multi-Sources

### SQL (Postgres)
- [ ] Récupération historique conversations
- [ ] Recherche documents uploadés
- [ ] Agrégation statistiques
- [ ] Filtrage métadonnées JSON
- [ ] Cross-reference avec RAG

### RAG (Qdrant)
- [ ] Recherche sémantique simple
- [ ] Filtrage par métadonnées
- [ ] Hybrid search (keyword + semantic)
- [ ] Multi-chunk aggregation
- [ ] Source citation

### Internet
- [ ] Légifrance API opérationnelle
- [ ] Web search fallback (DuckDuckGo)
- [ ] Multi-source aggregation
- [ ] Rate limiting géré
- [ ] Network failure resilience

### Performance
- [ ] Query complexe < 45s
- [ ] Cache effectiveness > 80%
- [ ] Parallel execution fonctionnelle
- [ ] Memory usage raisonnable

### Cohérence
- [ ] Détection contradictions
- [ ] Priorisation sources officielles
- [ ] Consistency temporelle
- [ ] Citation sources claire

---

## 📊 Template de Rapport

```markdown
## Test [Nom]

**Date:** [Date]
**Source(s):** [SQL/RAG/Légifrance/Web]

**Query:**
[Question posée]

**Résultats:**
- Sources consultées: [Liste]
- Temps total: [Xs]
- Cache hits: [X/Y]
- Qualité: [1-5 ⭐]

**Observations:**
[Notes]

**Logs Relevants:**
[Extraits]
```

---

**Bon courage pour les tests! 🚀**

Ces tests vont vraiment mettre le système à l'épreuve et identifier les optimisations possibles!
