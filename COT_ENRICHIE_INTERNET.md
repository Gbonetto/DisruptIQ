# Chain of Thoughts Enrichie pour Internet - Style RAG

**Date** : 21 novembre 2025
**Objectif** : Enrichir la CoT pour les recherches Internet avec métadonnées détaillées (scores, domaines, évaluation qualité)

---

## 🎯 Problème Identifié

La CoT pour les recherches **Internet** était basique comparée à celle de **RAG** :

### CoT Internet (Avant)
```
1. "Ok, je lance une recherche sur internet..."
2. "Parfait ! J'ai trouvé 5 sources web pertinentes..."
3. "Terminé ! J'ai synthétisé les informations..."
```
❌ **Manque de détails** : Pas de scores, pas de domaines, pas d'évaluation qualité

### CoT RAG (Référence)
```
1. "Ok, je cherche dans 3 document(s) sélectionné(s)..."
2. "Trouvé 15 passages en 1.2s. Meilleurs scores : 92%, 87%, 84%. Excellent ! Les passages semblent très pertinents..."
3. "Parfait ! J'ai une réponse solide avec 95% de confiance. Les 5 sources sont détaillées et cohérentes, j'ai extrait 8 faits."
```
✅ **Riche en métadonnées** : Scores, durée, évaluation qualité, nombre de faits, confiance

---

## ✅ Solution Implémentée

### Étape 1 : Lancement de la recherche (Inchangé)

```python
await thought_stream.add_thought(
    ThoughtType.EXECUTING,
    title="Ok, je lance une recherche sur internet. J'utilise DuckDuckGo pour trouver les informations les plus récentes et pertinentes.",
    content="",
    agent="websearch",
    progress=0.4
)
```

---

### Étape 2 : Résultats trouvés **ENRICHIS**

#### Métadonnées calculées

```python
# Calculate metadata for rich CoT (similar to RAG)
top_scores = [r.relevance_score for r in search_results.results[:3]]
scores_display = [f'{int(s*100)}%' for s in top_scores if s > 0]
avg_score = sum(top_scores) / len(top_scores) if top_scores else 0

# Extract domains for context
domains = []
for r in search_results.results[:3]:
    if r.url:
        try:
            domain = r.url.split("/")[2]
            domains.append(domain)
        except:
            pass
domains_str = ", ".join(set(domains[:3])) if domains else "sources web variées"
```

#### Évaluation qualité (comme RAG)

```python
# Quality assessment based on scores (like RAG)
if avg_score >= 0.8:
    quality_assessment = f"Excellent ! Les sources semblent très fiables ({', '.join(scores_display[:3])}). Sources principales : {domains_str}."
elif avg_score >= 0.6:
    quality_assessment = f"Scores corrects ({', '.join(scores_display[:3])}). Les informations sont utiles. Sources : {domains_str}."
else:
    quality_assessment = f"Scores moyens ({', '.join(scores_display[:3])}). Les sources web ne sont peut-être pas totalement pertinentes. Sources : {domains_str}."
```

#### CoT Thought 2 enrichi

```python
await thought_stream.add_thought(
    ThoughtType.COMPLETED,
    title=f"Trouvé {len(search_results.results)} sources web. Meilleurs scores : {', '.join(scores_display[:3])}. {quality_assessment}",
    content="",
    agent="websearch",
    progress=0.7
)
```

**Exemple de rendu** :
```
Trouvé 5 sources web. Meilleurs scores : 92%, 88%, 85%. Excellent ! Les sources semblent très fiables (92%, 88%, 85%). Sources principales : legifrance.gouv.fr, service-public.fr, vie-publique.fr.
```

---

### Étape 3 : Synthèse complète **ENRICHIE**

#### Confidence et évaluation

```python
# Calculate synthesis confidence (similar to RAG)
synthesis_confidence = int(search_results.confidence * 100) if search_results.confidence else 0
source_count = len(structured_sources)

# Build natural narrative based on confidence
if synthesis_confidence >= 80:
    confidence_narrative = f"Parfait ! J'ai synthétisé {source_count} sources avec {synthesis_confidence}% de confiance. Les informations sont claires et cohérentes."
elif synthesis_confidence >= 60:
    confidence_narrative = f"Synthèse terminée avec {synthesis_confidence}% de confiance sur {source_count} sources. Les informations sont utiles mais parfois incomplètes."
else:
    confidence_narrative = f"Synthèse terminée mais ma confiance est moyenne ({synthesis_confidence}%). Les {source_count} sources ne couvrent peut-être pas complètement le sujet."
```

#### CoT Thought 3 enrichi

```python
await thought_stream.add_thought(
    ThoughtType.COMPLETED,
    title=confidence_narrative,
    content="",
    agent="synthesis",
    progress=1.0
)
```

**Exemple de rendu** :
```
Parfait ! J'ai synthétisé 5 sources avec 85% de confiance. Les informations sont claires et cohérentes.
```

---

## 📊 Comparaison Avant/Après

### Avant (CoT Simple)

| Étape | Contenu | Métadonnées |
|-------|---------|-------------|
| 1 | "Lancement recherche internet..." | ❌ Aucune |
| 2 | "Trouvé 5 sources pertinentes..." | ❌ Aucune |
| 3 | "Synthèse terminée" | ❌ Aucune |

**Total d'informations** : ~50 caractères, 0 métadonnée

---

### Après (CoT Enrichie - Style RAG)

| Étape | Contenu | Métadonnées |
|-------|---------|-------------|
| 1 | "Lancement recherche DuckDuckGo..." | ❌ Provider |
| 2 | "Trouvé 5 sources. Scores : 92%, 88%, 85%. Excellent ! Sources : legifrance.gouv.fr, service-public.fr" | ✅ Scores, évaluation, domaines |
| 3 | "Synthétisé 5 sources avec 85% de confiance. Infos claires" | ✅ Confiance, nombre sources |

**Total d'informations** : ~250 caractères, **6+ métadonnées** (scores × 3, domaines × 3, confiance, évaluation qualité)

---

## 🎨 Style DeepSeek Narratif

### Caractéristiques

1. ✅ **Tout dans le titre** : Pas de `content` séparé
2. ✅ **Narratif naturel** : "Ok, je lance...", "Parfait !", "Hmm..."
3. ✅ **Métadonnées intégrées** : Scores, domaines, confiance dans le texte
4. ✅ **Évaluation qualitative** : "Excellent", "Scores corrects", "Scores moyens"
5. ✅ **Contexte actionnable** : Affichage des domaines principaux

### Exemples Concrets

#### Scénario 1 : Recherche réussie avec excellents scores

```
🌐 WEB  →  Trouvé 5 sources web. Meilleurs scores : 95%, 92%, 88%.
           Excellent ! Les sources semblent très fiables (95%, 92%, 88%).
           Sources principales : legifrance.gouv.fr, service-public.fr, vie-publique.fr.

🔄 SYNTHESIS  →  Parfait ! J'ai synthétisé 5 sources avec 90% de confiance.
                  Les informations sont claires et cohérentes.
```

#### Scénario 2 : Recherche avec scores moyens

```
🌐 WEB  →  Trouvé 4 sources web. Meilleurs scores : 65%, 58%, 52%.
           Scores moyens (65%, 58%, 52%). Les sources web ne sont peut-être
           pas totalement pertinentes. Sources : wikipedia.org, blog-example.com.

🔄 SYNTHESIS  →  Synthèse terminée avec 62% de confiance sur 4 sources.
                  Les informations sont utiles mais parfois incomplètes.
```

#### Scénario 3 : Aucun résultat

```
🌐 WEB  →  Hmm, aucun résultat pertinent trouvé sur le web. Soit l'information
           n'est pas publiquement disponible, soit il faudrait reformuler la
           question différemment.

🔄 SYNTHESIS  →  Synthèse terminée mais aucune source fiable trouvée.
                  La réponse risque d'être limitée.
```

---

## 🔍 Métadonnées Affichées

### Pour chaque recherche Internet

| Métadonnée | Type | Exemple | Source |
|------------|------|---------|--------|
| Nombre de résultats | `int` | `5 sources web` | `len(search_results.results)` |
| Scores de pertinence | `float[]` | `92%, 88%, 85%` | `r.relevance_score` (top 3) |
| Score moyen | `float` | `88.3%` | `avg(top_scores)` |
| Évaluation qualité | `string` | `Excellent !` | Basé sur `avg_score` |
| Domaines sources | `string[]` | `legifrance.gouv.fr` | Extrait de `r.url` |
| Confiance synthèse | `int` | `85%` | `search_results.confidence * 100` |

---

## 🧪 Test Recommandé

### Étape 1 : Recherche avec bons résultats

**Question** :
```
que dit la LOI n° 2024-322 du 9 avril 2024
```

**CoT attendue** :
```
1. 🌐 WEB → Ok, je lance une recherche sur internet. J'utilise DuckDuckGo pour trouver
              les informations les plus récentes et pertinentes.

2. 🌐 WEB → Trouvé 5 sources web. Meilleurs scores : 95%, 90%, 85%.
              Excellent ! Les sources semblent très fiables (95%, 90%, 85%).
              Sources principales : legifrance.gouv.fr, service-public.fr.

3. 🔄 SYNTHESIS → Parfait ! J'ai synthétisé 5 sources avec 92% de confiance.
                   Les informations sont claires et cohérentes.
```

### Étape 2 : Recherche générale

**Question** :
```
intelligence artificielle tendances 2025
```

**CoT attendue** :
```
1. 🌐 WEB → Ok, je lance une recherche sur internet...

2. 🌐 WEB → Trouvé 5 sources web. Meilleurs scores : 70%, 65%, 60%.
              Scores corrects (70%, 65%, 60%). Les informations sont utiles.
              Sources : tech-magazine.com, ai-blog.net, news-site.com.

3. 🔄 SYNTHESIS → Synthèse terminée avec 68% de confiance sur 5 sources.
                   Les informations sont utiles mais parfois incomplètes.
```

---

## 📁 Fichiers Modifiés

1. **Backend** : `backend/app/services/agents/orchestrator_agent.py`
   - Lignes **1535-1576** : Thought 2 enrichi avec scores et domaines
   - Lignes **1616-1645** : Thought 3 enrichi avec confiance et évaluation

---

## 🚀 Bénéfices

### 1. Transparence accrue
L'utilisateur voit maintenant :
- ✅ La qualité des sources (scores)
- ✅ Les domaines principaux (crédibilité)
- ✅ La confiance de la synthèse

### 2. Cohérence avec RAG
- ✅ Même format de CoT entre RAG et Internet
- ✅ Même niveau de détail
- ✅ Même style narratif DeepSeek

### 3. Meilleure UX
- ✅ L'utilisateur peut évaluer la fiabilité avant de lire
- ✅ Identification rapide des sources fiables (legifrance.gouv.fr vs blog.com)
- ✅ Compréhension des limites (scores moyens = info incomplète)

---

## ✨ Résultat Final

**La CoT Internet est maintenant au même niveau que RAG** :
- ✅ Métadonnées riches (scores, domaines, confiance)
- ✅ Évaluation qualitative automatique
- ✅ Style narratif DeepSeek engageant
- ✅ Contexte actionnable pour l'utilisateur

**Uniformité totale** : Toutes les sources (SQL, RAG, Internet) affichent maintenant des CoT enrichies avec métadonnées détaillées ! 🎯
