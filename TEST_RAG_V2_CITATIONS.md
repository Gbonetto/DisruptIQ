# 🧪 Test Plan: RAG v2.0 - Citations Inline

**Date**: 4 Novembre 2025
**Feature**: Synthesis Agent with inline citations [N]
**Status**: Phase 1 Implementation Complete - Ready for Testing

---

## ✅ CHANGEMENTS IMPLÉMENTÉS

### 1. **Nouveau fichier : `synthesis_agent.py`**
- Classe `SynthesisAgent` avec méthode `synthesize_with_citations()`
- Citations inline automatiques `[1]`, `[2]`, `[3]`
- Détection de contradictions entre sources
- Scoring de confiance par phrase
- Formatage markdown avec footer sources

### 2. **Modification : `orchestrator_agent.py`**
- Fonction `_handle_search_documents()` mise à jour (ligne 444-530)
- Utilise maintenant `SynthesisAgent` au lieu de `_format_as_informational()`
- Augmentation du limit de 3 à 5 chunks pour meilleure synthèse
- Retourne metadata enrichie (contradictions, warnings, confidence)

---

## 🎯 OBJECTIFS DE TEST

### Test 1 : Citations Inline Basiques
**Objectif** : Vérifier que chaque affirmation factuelle est citée

**Query** : `"Que contient le document de mariage Cannes ?"`

**Résultat Attendu v1.0 (AVANT)** :
```markdown
Ce document traite des procédures et des règles à suivre pour l'organisation
d'une cérémonie de mariage à Cannes...

---
📄 Sources : Charte_mariage_Cannes.pdf (85%)
```
❌ **Problème** : Impossible de savoir quelle phrase vient de quelle partie du document

**Résultat Attendu v2.0 (APRÈS)** :
```markdown
Le document contient une charte que les futurs époux doivent respecter pour
assurer le bon déroulement de leur cérémonie[1]. Les futurs époux peuvent
également autoriser la publication des informations sur l'événement dans la
presse locale[1]. Des sanctions peuvent être appliquées en cas de manquement
à la charte[1].

---
📚 **Sources** :
[1] **Charte_mariage_Cannes** - 85%
```
✅ **Amélioration** : Chaque affirmation est tracée avec [1]

---

### Test 2 : Sources Multiples
**Objectif** : Vérifier citations avec plusieurs sources

**Query** : `"Quels sont les délais et tarifs du plombier ?"`

**Résultat Attendu** :
```markdown
Le délai d'intervention du plombier est de **24 heures maximum pour les
urgences**[1] et de **48-72 heures pour les interventions non urgentes**[2].
Le tarif horaire est fixé à **80€/h en semaine**[3] et **120€/h les week-ends
et jours fériés**[3].

---
📚 **Sources** :
[1] **Règlement_copropriété** (page 12) - 95%
[2] **Contrat_plombier_2025** (page 1) - 98%
[3] **Tarifs_professionels_2025** (page 5) - 92%
```

**Vérifications** :
- ✅ `[1]` cite source pour délai urgences
- ✅ `[2]` cite source pour délai non-urgences
- ✅ `[3]` cite source pour tarifs (deux fois car deux infos du même doc)
- ✅ Footer liste les 3 sources avec scores

---

### Test 3 : Détection de Contradictions
**Objectif** : Vérifier que l'agent signale les contradictions entre sources

**Setup** : Uploader 2 documents avec infos contradictoires
- `tarifs_2023.pdf` : "Le plombier facture 75€/h"
- `tarifs_2025.pdf` : "Le plombier facture 80€/h"

**Query** : `"Quel est le tarif du plombier ?"`

**Résultat Attendu** :
```markdown
Le tarif actuel du plombier est de **80€/h**[2].

⚠️ **Note** : Le document [1] mentionne un tarif de 75€/h, mais cette
information date de 2023 et a été mise à jour par le contrat actuel[2].

---
📚 **Sources** :
[1] **tarifs_2023** - 65%
[2] **tarifs_2025** - 98%
```

**Vérifications** :
- ✅ Agent détecte la contradiction
- ✅ Agent privilégie la source la plus fiable (score 98% vs 65%)
- ✅ Agent signale explicitement la différence avec ⚠️

---

### Test 4 : Questions Procédurales (Steps)
**Objectif** : Vérifier le formatage en étapes avec citations

**Query** : `"Comment procéder en cas de dégât des eaux ?"`

**Résultat Attendu** :
```markdown
## 📋 Actions à suivre

1. **Couper l'arrivée d'eau immédiatement**[1]
   - Localiser la vanne principale
   - Fermer complètement la vanne

2. **Contacter le syndic dans les 24 heures**[1]
   - Téléphone : 04 XX XX XX XX
   - Email : syndic@example.com

3. **Prévenir votre assurance sous 5 jours**[2]
   - Préparer photos des dégâts
   - Conserver factures de réparation d'urgence

**Note** : En cas d'urgence, vous pouvez contacter le plombier référent
directement[3].

---
📚 **Sources** :
[1] **Procédure_dégâts_eaux** (page 1) - 97%
[2] **Guide_assurances** (page 8) - 88%
[3] **Contacts_urgence** - 92%
```

**Vérifications** :
- ✅ Format en étapes numérotées
- ✅ Chaque étape citée
- ✅ Sous-actions avec tirets
- ✅ Note finale citée

---

### Test 5 : Information Manquante
**Objectif** : Vérifier que l'agent ne fabrique pas d'informations

**Query** : `"Quel est l'email du plombier ?"`

**Si info absente**, **Résultat Attendu** :
```markdown
Je n'ai pas trouvé d'adresse email pour le plombier dans les documents disponibles[1].
Le document mentionne uniquement un numéro de téléphone : 06 XX XX XX XX[1].

---
📚 **Sources** :
[1] **Contrat_plombier_2025** (page 3) - 89%
```

**Vérifications** :
- ✅ Agent dit explicitement "Je n'ai pas trouvé"
- ✅ Agent propose info alternative (téléphone) si disponible
- ✅ Pas d'hallucination d'email inventé

---

### Test 6 : Confidence Scoring
**Objectif** : Vérifier les scores de confiance dans les métadonnées

**Query** : `"Quels sont les horaires d'ouverture ?"`

**Response Data Attendu** :
```json
{
  "success": true,
  "message": "Les horaires d'ouverture sont...",
  "data": {
    "sources": [
      {"id": 1, "title": "Règlement", "score": 0.95}
    ],
    "is_procedural": false,
    "has_contradictions": false,
    "sentences": [
      {
        "text": "Les horaires d'ouverture sont de 9h à 18h",
        "source_ids": [1],
        "has_citation": true,
        "is_factual": true
      }
    ],
    "warnings": []
  },
  "agents_used": ["rag_agent", "synthesis_agent"],
  "confidence": 0.92
}
```

**Vérifications** :
- ✅ `confidence` global entre 0-1
- ✅ `sentences` liste toutes les phrases avec métadonnées
- ✅ `has_citation` = true pour phrases factuelles
- ✅ `sources` contient score par source

---

## 🚀 PROCÉDURE DE TEST

### Étape 1 : Restart Backend
```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC
docker-compose restart backend

# Vérifier logs
docker-compose logs backend --tail=50 | grep "synthesis_agent"
```

**Attendu** :
```
synthesis_agent_initialized
```

---

### Étape 2 : Upload Document de Test
**Document recommandé** : Celui sur le mariage à Cannes (déjà uploadé)

Vérifier dans UI :
1. Ouvrir http://localhost:3000
2. Cliquer "Documents" (right panel)
3. Vérifier que le document est listé et coché ✅

---

### Étape 3 : Test Query via Interface
**Query** : `"de quoi parle ce document ?"`

**Observer** :
1. **Response format** : Doit contenir `[1]`, `[2]` dans le texte
2. **Footer** : Section "📚 **Sources** :" en bas
3. **Sources list** : Titre + score pour chaque source

**Screenshot attendu** :
```
Assistant: Ce document contient une charte que les futurs époux doivent
respecter[1]. Il inclut également un formulaire pour autoriser la publication
des informations dans la presse locale[1]. Des sanctions peuvent être
appliquées en cas de non-respect[1].

---
📚 **Sources** :
[1] **Charte_mariage_Cannes** - 87%
```

---

### Étape 4 : Test Query via API (cURL)
```bash
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "de quoi parle ce document ?"
  }' | jq '.response'
```

**Vérifier JSON response** :
- `response` contient citations `[N]`
- `data.sources` est un array avec `id`, `title`, `score`
- `data.sentences` contient métadonnées par phrase
- `data.confidence` est un float entre 0-1

---

### Étape 5 : Test Contradictions (Optionnel)
**Setup** :
1. Upload `document_A.txt` avec : "Le tarif est 75€"
2. Upload `document_B.txt` avec : "Le tarif est 80€"

**Query** : `"Quel est le tarif ?"`

**Observer** :
- Response doit mentionner les deux sources avec `[1]` et `[2]`
- Section ⚠️ doit signaler la contradiction
- `data.has_contradictions` = `true`
- `data.contradiction_note` contient l'explication

---

## 📊 MÉTRIQUES DE SUCCÈS

| Critère | v1.0 (Avant) | v2.0 (Cible) | Statut |
|---------|--------------|--------------|--------|
| **Citations inline** | ❌ 0% | ✅ 100% | 🟡 À vérifier |
| **Sources footer** | ✅ Oui (mais vague) | ✅ Numérotées + score | 🟡 À vérifier |
| **Traçabilité** | ❌ Impossible | ✅ Chaque fait tracé | 🟡 À vérifier |
| **Contradictions** | ❌ Non détectées | ✅ Signalées | 🟡 À vérifier |
| **Confidence score** | ❌ Non | ✅ Par phrase + global | 🟡 À vérifier |

---

## 🐛 TROUBLESHOOTING

### Problème 1 : ImportError synthesis_agent
**Symptôme** :
```
ImportError: cannot import name 'SynthesisAgent' from 'app.services.agents.synthesis_agent'
```

**Solution** :
```bash
# Vérifier fichier existe
ls backend/app/services/agents/synthesis_agent.py

# Si absent, recréer le fichier
# (code fourni précédemment)

# Restart backend
docker-compose restart backend
```

---

### Problème 2 : Pas de citations [N] dans la réponse
**Symptôme** : Response normale sans `[1]`, `[2]`

**Causes possibles** :
1. LLM n'a pas suivi les instructions de citation
2. Parsing des citations a échoué

**Debug** :
```bash
# Check logs backend
docker-compose logs backend | grep "synthesis"

# Chercher :
# - "generating_synthesis" → Prompt envoyé au LLM
# - "synthesis_completed" → Response générée
# - Erreurs ?
```

**Solution** :
- Vérifier temperature = 0.2 (bas pour respect des instructions)
- Vérifier prompt contient "RÈGLES IMPÉRATIVES" de citation
- Augmenter max_tokens si response tronquée

---

### Problème 3 : Citations incorrectes ([99] au lieu de [1])
**Symptôme** : Citations avec numéros qui n'existent pas

**Cause** : LLM hallucine les numéros de sources

**Solution** :
- Ajouter validation post-génération
- Remplacer citations invalides par [?]
- Logger warning

**Code à ajouter dans synthesis_agent.py** :
```python
def _validate_citations(self, text: str, max_source_id: int) -> str:
    """Replace invalid citations with [?]"""
    def replace_invalid(match):
        ids = [int(x) for x in match.group(1).split(',')]
        valid_ids = [id for id in ids if 1 <= id <= max_source_id]
        if not valid_ids:
            return "[?]"
        return f"[{','.join(map(str, valid_ids))}]"

    return re.sub(r'\[(\d+(?:,\d+)*)\]', replace_invalid, text)
```

---

## ✅ CHECKLIST DE VALIDATION

Avant de considérer Phase 1 comme complète :

- [ ] Backend démarre sans erreurs
- [ ] Logs montrent "synthesis_agent_initialized"
- [ ] Query simple retourne response avec `[1]`
- [ ] Footer "📚 **Sources** :" est présent
- [ ] Sources listées avec titre + score %
- [ ] JSON response contient `data.sentences` avec métadonnées
- [ ] `data.confidence` est entre 0-1
- [ ] Pas d'hallucinations (citations valides uniquement)
- [ ] Questions procédurales retournent format en étapes
- [ ] Si info manquante, agent dit "Je n'ai pas trouvé"

**Si tous les checks passent** → Phase 1 ✅ COMPLÈTE

**Puis** → Passer à Phase 2 : Retrieval Multi-Strategy

---

## 🎯 RÉSUMÉ PHASE 1

**Durée estimée** : 4h
**Durée réelle** : _À compléter après implémentation_

**Fichiers modifiés** :
- ✅ `backend/app/services/agents/synthesis_agent.py` (CRÉÉ)
- ✅ `backend/app/services/agents/orchestrator_agent.py` (MODIFIÉ ligne 444-530)

**Impact utilisateur** :
- ✅ Traçabilité complète : chaque affirmation est sourcée
- ✅ Confiance accrue : scores de pertinence affichés
- ✅ Détection contradictions : signalées automatiquement
- ✅ Qualité pro : format markdown clair et structuré

**Prochaine étape** :
- Phase 2 : Retrieval Agent multi-strategy (dense + sparse + hybrid)
- Phase 3 : Reranker Agent avec cross-encoder

---

**Date de test** : _____________________
**Testeur** : _____________________
**Résultat** : ✅ PASS / ❌ FAIL / 🟡 PARTIAL

**Notes** :
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
