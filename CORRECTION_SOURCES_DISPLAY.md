# 🔧 Correction : Affichage des Sources

**Date**: 4 Novembre 2025
**Problème**: Sources affichent "Document - 86%" au lieu du nom de fichier réel
**Status**: ✅ CORRIGÉ

---

## 🐛 PROBLÈME IDENTIFIÉ

### Symptôme
```
📚 Sources :
[1] Document - 86%
[2] Document - 86%
[3] Document - 85%
```
❌ Pas de noms de fichiers, impossible d'identifier les sources

### Cause Racine
**Fichier** : `backend/app/api/endpoints/documents.py` ligne 193-197

**Code problématique** :
```python
metadata={
    "filename": file.filename,  # UUID, pas utile
    "mime_type": file.content_type,
    "uploaded_at": datetime.now().isoformat()
    # ❌ MANQUE: "original_filename" et "title"
}
```

Le `synthesis_agent.py` cherche `metadata.get("original_filename")` (ligne 171) mais ce champ n'était pas rempli lors de l'indexation.

---

## ✅ SOLUTION APPLIQUÉE

### Modification
**Fichier** : `backend/app/api/endpoints/documents.py` ligne 190-200

**Nouveau code** :
```python
metadata={
    "filename": file.filename,
    "original_filename": db_document.original_filename,  # ✅ AJOUTÉ
    "title": db_document.original_filename,              # ✅ AJOUTÉ (fallback)
    "mime_type": file.content_type,
    "uploaded_at": datetime.now().isoformat()
}
```

---

## 🚀 DÉPLOIEMENT

### Étape 1 : Restart Backend
```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC
docker-compose restart backend
```

### Étape 2 : Re-upload Documents
⚠️ **IMPORTANT** : Les documents déjà uploadés ont les anciennes métadonnées dans Qdrant.

**Option A : Supprimer et re-uploader** (RECOMMANDÉ)
1. Ouvrir http://localhost:3000
2. Cliquer "Documents" (right panel)
3. Supprimer tous les documents existants
4. Re-uploader les mêmes fichiers

**Option B : Script de migration** (si beaucoup de docs)
```python
# TODO: Script pour mettre à jour metadata dans Qdrant
# Pas urgent si peu de documents en dev
```

### Étape 3 : Tester
```bash
# Query après re-upload
"de quoi parle ce document ?"
```

**Résultat attendu** :
```
Le document contient une charte...[1]

---
📚 Sources :
[1] **Charte_mariage_Cannes** - 87%  ✅ Nom de fichier visible
```

---

## 🧪 VALIDATION

### Checklist
- [ ] Backend restarté
- [ ] Documents supprimés depuis le panel
- [ ] Documents re-uploadés
- [ ] Query testée : "de quoi parle ce document ?"
- [ ] Sources affichent le bon nom de fichier (ex: "Charte_mariage_Cannes")
- [ ] Pas de "Document - 86%" générique

---

## 📊 IMPACT

| Aspect | Avant | Après |
|--------|-------|-------|
| Sources footer | "Document - 86%" | **"Charte_mariage_Cannes - 87%"** |
| Traçabilité | ❌ Impossible | ✅ Nom de fichier clair |
| User UX | ⚠️ Confus | ✅ Professionnel |

---

## 🔄 AUTRES PROBLÈMES IDENTIFIÉS

### Problème 2 : SQL Whitelist trop restrictive
**Symptôme** :
```
User: "combien facture le plombier ?"
Assistant: "La requête générée n'est pas sûre."
```

**Cause** : Whitelist SQL bloque les queries avec "facture", "prix", "tarif"

**Fichier à vérifier** : `backend/app/services/agents/sql_agent.py` (whitelist)

**Action** : Voir document séparé `CORRECTION_SQL_WHITELIST.md`

---

## ✅ CONCLUSION

**Correction** : ✅ Metadata enrichie avec `original_filename` et `title`

**Next steps** :
1. Restart backend
2. Re-upload documents
3. Tester affichage sources

**Temps estimé** : 5 minutes

---

*Correction appliquée le 4 Novembre 2025*
*Fichier modifié : `backend/app/api/endpoints/documents.py` ligne 195-196*
