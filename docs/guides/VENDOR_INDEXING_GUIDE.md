# 🔍 Guide d'Indexation des Fournisseurs

## 📋 Vue d'Ensemble

Le système DisruptIQ indexe maintenant automatiquement les fournisseurs dans **Qdrant** (base de données vectorielle) pour permettre à l'**assistant RAG** de les rechercher et de répondre aux questions.

---

## ✨ Fonctionnalités

### **1. Indexation Automatique à l'Import**

Lorsque vous importez un CSV de fournisseurs :
1. ✅ Les fournisseurs sont créés en base PostgreSQL
2. ✅ **Indexation automatique** dans Qdrant
3. ✅ Disponibles immédiatement pour l'assistant

**Message affiché :**
```
Import réussi!

✅ 45 fournisseur(s) créé(s)
⏭️ 5 fournisseur(s) ignoré(s) (déjà existant)
🔍 45 fournisseur(s) indexé(s) pour l'assistant
```

---

### **2. Réindexation Manuelle**

Si l'assistant ne trouve pas les fournisseurs, vous pouvez les réindexer :

#### **Via API :**
```bash
curl -X POST http://localhost:8000/api/admin/vendors/reindex
```

#### **Via Swagger UI :**
1. Allez sur http://localhost:8000/api/docs
2. Cherchez `/admin/vendors/reindex`
3. Cliquez sur "Try it out" → "Execute"

**Réponse :**
```json
{
  "status": "success",
  "message": "Indexed 49 vendors successfully",
  "total_vendors": 49,
  "indexed": 49,
  "failed": 0,
  "errors": []
}
```

---

### **3. Gestion d'Erreurs Robuste**

Le système gère automatiquement :

✅ **Emails invalides** : Ignorés avec message d'erreur
✅ **Doublons** : Détectés et comptés
✅ **Échecs d'indexation** : N'interrompent pas l'import
✅ **Validation Pydantic** : Emails validés avant insertion

---

## 🤖 Utilisation avec l'Assistant

L'assistant peut maintenant répondre à des questions sur les fournisseurs :

### **Exemples de Questions**

#### **1. Recherche par Catégorie**
```
Question : Qui est le plombier ?
Réponse : Les plombiers mentionnés sont Laurent Mercier, Romain Bruno et Lucas Martin.
```

#### **2. Coordonnées Spécifiques**
```
Question : Donne-moi l'email de Laurent Mercier
Réponse : Laurent Mercier a pour email laurent.mercier@exemple.fr
```

#### **3. Recherche par Ville**
```
Question : Quel électricien à Lyon ?
Réponse : Marie Martin, Électricité Martin, email: marie.martin@elec.fr
```

#### **4. Spécialités**
```
Question : Qui fait du dépannage ?
Réponse : Jean Dupont (Plomberie), spécialités : Dépannage, Rénovation
```

#### **5. Téléphones**
```
Question : Quel est le téléphone du jardinier ?
Réponse : Sophie Bernard, téléphone : 0604050607
```

---

## 🔧 Architecture Technique

### **Flux de Données**

```
CSV Import
    ↓
PostgreSQL (vendors table)
    ↓
VendorIndexService.index_vendor()
    ↓
Conversion en texte structuré
    ↓
RAGService.index_document()
    ↓
Qdrant Vector Database
    ↓
Assistant RAG
```

### **Format d'Indexation**

Chaque vendor est converti en document texte :

```
FOURNISSEUR: Jean Dupont
Type: Plomberie
Entreprise: Plomberie Dupont
Email: jean.dupont@plomberie.fr
Téléphone: 0601020304
Adresse: 12 rue de Paris
Ville: Paris
Code postal: 75001
Spécialités: Dépannage, Rénovation
```

### **Métadonnées Qdrant**

```json
{
  "source": "vendor",
  "vendor_id": 1,
  "vendor_name": "Jean Dupont",
  "vendor_email": "jean.dupont@plomberie.fr",
  "category": "Plomberie",
  "city": "Paris"
}
```

### **ID de Document**

- **Documents réels** : ID positifs (1, 2, 3...)
- **Vendors** : ID négatifs (-1, -2, -3...)
- Évite les conflits entre documents et vendors

---

## 📊 Vérification de l'Indexation

### **1. Via Qdrant Dashboard**

1. Ouvrir http://localhost:6333/dashboard
2. Collection : `disruptiq_documents`
3. **Points** : Nombre total de chunks indexés
   - Documents : IDs positifs
   - Vendors : IDs négatifs

### **2. Via PostgreSQL**

```sql
SELECT COUNT(*) FROM vendors;
```

### **3. Via API**

```bash
curl http://localhost:8000/api/admin/stats
```

Résultat :
```json
{
  "total_vendors": 49
}
```

---

## 🐛 Dépannage

### **Problème : L'assistant ne trouve pas les vendors**

**Solution 1 :** Réindexer manuellement
```bash
curl -X POST http://localhost:8000/api/admin/vendors/reindex
```

**Solution 2 :** Vérifier Qdrant
```bash
curl http://localhost:6333/collections/disruptiq_documents
```

**Solution 3 :** Vérifier les logs
```bash
docker-compose logs backend | grep -i vendor
```

---

### **Problème : Emails invalides lors de l'import**

**Symptôme :**
```json
{
  "error": "Invalid email format: test@exempl"
}
```

**Cause :** Email sans extension valide (`.com`, `.fr`, etc.)

**Solution :** Corriger le CSV avant import :
- ✅ `test@exemple.fr`
- ❌ `test@exempl`

---

### **Problème : Network Error après import**

**Cause :** Un vendor avec email invalide déjà en base

**Solution :**
```sql
-- Supprimer les vendors avec emails invalides
DELETE FROM vendors WHERE email NOT LIKE '%@%.%';
```

Puis réindexer :
```bash
curl -X POST http://localhost:8000/api/admin/vendors/reindex
```

---

## 🚀 Utilisation en Production

### **1. Import Initial**

```bash
# Via frontend
http://localhost:3000/admin → "Importer CSV"

# Ou via API
curl -X POST http://localhost:8000/api/admin/vendors/import-csv \
  -F "file=@vendors.csv"
```

### **2. Vérifier l'Indexation**

```bash
curl -X POST http://localhost:8000/api/admin/vendors/reindex
```

### **3. Tester l'Assistant**

```bash
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Qui est le plombier ?"}'
```

---

## 📈 Performance

### **Temps d'Indexation**

| Nombre de Vendors | Temps Estimé |
|-------------------|--------------|
| 10 vendors | ~2 secondes |
| 50 vendors | ~8 secondes |
| 100 vendors | ~15 secondes |
| 500 vendors | ~1 minute |

### **Optimisations**

- ✅ Indexation en batch (tous les vendors en une fois)
- ✅ Gestion d'erreurs partielle (un échec n'arrête pas tout)
- ✅ Logs structurés pour le monitoring

---

## 🔒 Sécurité

### **Validation des Emails**

```python
# Validation Pydantic stricte
from pydantic import EmailStr

# Rejetés :
- "test@exemple" (pas de TLD)
- "test.exemple.fr" (pas de @)
- "@exemple.fr" (pas de partie locale)

# Acceptés :
- "test@exemple.fr" ✅
- "jean.dupont@plomberie.com" ✅
```

### **Protection contre les Doublons**

```python
# Vérification avant insertion
existing = await db.execute(
    select(Vendor).where(Vendor.email == email)
)
if existing.scalar_one_or_none():
    vendors_skipped += 1
    continue
```

---

## 📝 API Reference

### **POST /api/admin/vendors/import-csv**

Import vendors from CSV file with automatic indexing.

**Request:**
```
Content-Type: multipart/form-data
file: vendors.csv
```

**Response:**
```json
{
  "status": "success",
  "vendors_created": 45,
  "vendors_skipped": 5,
  "vendors_indexed": 45,
  "index_errors": 0,
  "errors": [],
  "error_count": 0
}
```

---

### **POST /api/admin/vendors/reindex**

Reindex all vendors in Qdrant.

**Request:** No body required

**Response:**
```json
{
  "status": "success",
  "message": "Indexed 49 vendors successfully",
  "total_vendors": 49,
  "indexed": 49,
  "failed": 0,
  "errors": []
}
```

---

## ✅ Checklist de Validation

- [ ] Import CSV fonctionne
- [ ] Indexation automatique se lance
- [ ] Doublons détectés
- [ ] Emails invalides rejetés
- [ ] Assistant trouve les vendors
- [ ] Réponses précises avec coordonnées
- [ ] Qdrant contient les vendors (IDs négatifs)
- [ ] Logs sans erreurs

---

## 🎉 Résumé

**Ce qui a été implémenté :**

1. ✅ **Service d'Indexation** (`vendor_index_service.py`)
2. ✅ **Indexation Automatique** à l'import CSV
3. ✅ **Endpoint de Réindexation** manuelle
4. ✅ **Validation Robuste** des emails
5. ✅ **Gestion d'Erreurs** complète
6. ✅ **Intégration Assistant** RAG
7. ✅ **Messages Informatifs** dans le frontend

**Résultat :**

L'assistant peut maintenant répondre à toutes les questions sur vos fournisseurs avec précision et rapidité ! 🚀

---

**📧 Support :** Consultez les logs avec `docker-compose logs backend`
