# 🚀 RAG v2.0 - Quick Start Guide

**Date**: 4 Novembre 2025
**Phase 1** : Citations Inline - IMPLÉMENTÉ ✅

---

## ⚡ EN 3 MINUTES

### Ce qui a été fait
✅ Nouveau **Synthesis Agent** avec citations inline `[1]`, `[2]`, `[3]`
✅ Chaque affirmation est maintenant **sourcée et traçable**
✅ Détection automatique des **contradictions** entre documents
✅ **Confidence scoring** par phrase et global
✅ Tests unitaires complets (20+ tests)

---

## 🧪 TESTER MAINTENANT (5 min)

### Étape 1 : Restart Backend
```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC
docker-compose restart backend
```

### Étape 2 : Vérifier Logs
```bash
docker-compose logs backend | grep "synthesis_agent"
```
**Attendu** : `synthesis_agent_initialized`

### Étape 3 : Test Interface Web
1. Ouvrir http://localhost:3000
2. Question : **"de quoi parle ce document ?"**
3. Vérifier dans la réponse :
   - ✅ Citations `[1]`, `[2]` dans le texte
   - ✅ Footer "📚 **Sources** :"
   - ✅ Sources avec titre + score %

### Résultat Attendu
```markdown
Le document contient une charte que les futurs époux doivent respecter[1].
Les futurs époux peuvent autoriser la publication dans la presse locale[1].
Des sanctions peuvent être appliquées en cas de manquement[1].

---
📚 **Sources** :
[1] **Charte_mariage_Cannes** - 87%
```

---

## 📊 AVANT vs APRÈS

| Aspect | v1.0 (Avant) | v2.0 (Maintenant) |
|--------|--------------|-------------------|
| Citations inline | ❌ Non | ✅ Oui `[1]`, `[2]` |
| Traçabilité | Globale | Par phrase |
| Contradictions | Non détectées | ✅ Signalées |
| Confidence | Non | ✅ Score 0-100% |
| Metadata | Minimale | ✅ Enrichie |

---

## 📁 FICHIERS IMPORTANTS

| Fichier | Description |
|---------|-------------|
| `RAG_v2.0_SPECIFICATION.md` | Spec complète 7 phases (29h dev) |
| `synthesis_agent.py` | Agent citations (437 lignes) |
| `test_synthesis_agent.py` | Tests unitaires (20+ tests) |
| `TEST_RAG_V2_CITATIONS.md` | Plan de test détaillé |
| `RAG_V2_IMPLEMENTATION_SUMMARY.md` | Résumé complet |

---

## 🎯 PROCHAINES ÉTAPES

### Phase 1 ✅ DONE
- Citations inline implémentées
- Tests créés
- **→ TESTING requis (toi, 1h)**

### Phase 2 🔜 NEXT (6h)
- Retrieval multi-strategy (dense + sparse + hybrid)
- Amélioration précision +20%

### Phase 3 🔜 AFTER (4h)
- Reranker avec cross-encoder
- Amélioration précision +15%

---

## 🐛 TROUBLESHOOTING

### Problème : Pas de citations `[1]`, `[2]`
**Solution** :
```bash
# Vérifier que synthesis_agent.py existe
ls backend/app/services/agents/synthesis_agent.py

# Restart backend
docker-compose restart backend

# Check logs pour erreurs
docker-compose logs backend --tail 100
```

### Problème : ImportError
**Vérifier** :
```python
# Dans orchestrator_agent.py ligne 458
from .synthesis_agent import SynthesisAgent
```

---

## ✅ CHECKLIST RAPIDE

- [ ] Backend restart sans erreurs
- [ ] Log "synthesis_agent_initialized" ✓
- [ ] Query retourne `[1]`, `[2]` ✓
- [ ] Footer "📚 **Sources** :" ✓
- [ ] Scores affichés (ex: 87%) ✓

**Si tous ✓** → Phase 1 RÉUSSIE 🎉

---

## 🆘 BESOIN D'AIDE ?

1. **Consulter** : `TEST_RAG_V2_CITATIONS.md` (troubleshooting détaillé)
2. **Logs** : `docker-compose logs backend --tail 200`
3. **Tests** : `pytest backend/tests/agents/test_synthesis_agent.py -v`

---

**🚀 Let's make DisruptIQ the best RAG on the market!**
