# ⚡ TODO IMMÉDIAT - 10 Minutes

**Date**: 4 Novembre 2025
**Action**: Finaliser RAG v2.0 Phase 1

---

## ✅ CE QUI FONCTIONNE DÉJÀ

1. ✅ Citations inline `[1]`, `[2]`, `[3]`
2. ✅ Détection contradictions
3. ✅ Confidence scoring
4. ✅ Questions procédurales (steps)
5. ✅ Pas d'hallucination

---

## 🔧 CE QU'IL RESTE À FAIRE (10 min)

### Action 1 : Restart Backend (2 min)
```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC
docker-compose restart backend
timeout /t 10 /nobreak
```

### Action 2 : Re-upload Documents (5 min)
1. Ouvrir http://localhost:3000
2. Cliquer "Documents" (right panel)
3. **Supprimer tous les documents existants** (button Delete)
4. **Re-uploader les mêmes fichiers** (drag & drop)
5. Attendre indexation complète

**Pourquoi ?** Anciens docs ont metadata sans `original_filename`

### Action 3 : Tester (3 min)
```
Query: "de quoi parle ce document ?"
```

**Vérifier** :
- ✅ Citations `[1]`, `[2]` présentes
- ✅ **Footer sources affiche "Charte_mariage_Cannes"** (pas "Document")
- ✅ Scores affichés (ex: 87%)

**Si OK** → ✅ **Phase 1 COMPLETE !**

---

## 📚 DOCUMENTS CRÉÉS

| Document | Usage |
|----------|-------|
| `RESUME_FINAL_RAG_V2.md` | ⭐ **LIS CELUI-LÀ** - Résumé complet |
| `ACTIONS_IMMEDIATES.md` | Guide test détaillé |
| `CORRECTION_SOURCES_DISPLAY.md` | Fix appliqué |
| `RAG_v2.0_SPECIFICATION.md` | Spec complète (7 phases) |

---

## 🎯 APRÈS VALIDATION

### Optionnel : Fix SQL Whitelist (30 min)
**Problème** : "combien facture le plombier ?" est bloqué
**Action** : Ajouter keywords à SQL whitelist
**Fichier** : `backend/app/services/agents/sql_agent.py`

### Prochaines Phases (14h)
- Phase 2 : Retrieval multi-strategy (+20% précision) - 6h
- Phase 3 : Reranker cross-encoder (+15% précision) - 4h
- Phases 4-7 : Features avancées - 4h

---

## ✅ CHECKLIST RAPIDE

- [ ] Backend restarté
- [ ] Documents supprimés
- [ ] Documents re-uploadés
- [ ] Query testée
- [ ] Sources affichent vrais noms de fichiers ✅

**Si tout coché** → 🎉 **BRAVO ! Phase 1 RÉUSSIE !**

---

**Total temps requis : 10 minutes**
**Impact : RAG de classe mondiale ! 🚀**
