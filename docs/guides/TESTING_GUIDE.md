# 🧪 Guide de Test DisruptIQ

## Bugs Corrigés

1. ✅ **Persistance des emails en base** - Les emails sont maintenant sauvegardés
2. ✅ **Normalisation des réponses digest** - Plus de "Invalid Date"
3. ✅ **Détection automatique du délimiteur CSV** - Support `,` et `;`
4. ✅ **Vérification des doublons vendors** - Skip automatique des doublons
5. ✅ **Contrainte unique sur vendor.email** - Intégrité des données
6. ✅ **Upload et indexation de documents** - RAG fonctionnel avec Qdrant
7. ✅ **Gestion d'erreurs frontend** - Affichage clair des erreurs

---

## 📋 Prérequis

- Docker Desktop en cours d'exécution
- Python 3.11+ installé
- Node.js 18+ installé

---

## 🚀 Étape 1 : Démarrer l'Infrastructure

### Windows (PowerShell/CMD)

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC

# Arrêter et supprimer les anciens conteneurs + volumes
docker-compose down -v

# Démarrer les services
docker-compose up -d postgres redis qdrant

# Vérifier que tout fonctionne
docker-compose ps
```

**Attendre ~10 secondes** que PostgreSQL soit prêt.

---

## 🔧 Étape 2 : Démarrer le Backend

### Terminal 1 - Backend

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC\backend

# Activer l'environnement virtuel (si vous en avez un)
# .venv\Scripts\activate

# Installer les dépendances (si pas déjà fait)
pip install -r requirements.txt

# Démarrer FastAPI
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Vérifier :**
- Les logs doivent afficher : `database_initialized` ✅
- Accéder à : http://localhost:8000/health
- Docs API : http://localhost:8000/api/docs

---

## 🎨 Étape 3 : Démarrer le Frontend

### Terminal 2 - Frontend

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC\frontend

# Installer les dépendances (si pas déjà fait)
npm install

# Démarrer Vite
npm run dev
```

**Vérifier :**
- Accéder à : http://localhost:3000 (ou le port indiqué)

---

## 🧪 Étape 4 : Tests Automatisés

### Terminal 3 - Tests

```bash
cd C:\Users\grego\Desktop\Dossiers\DisruptIQ\DisruptIQ_CC

# Exécuter les tests
python test_api.py
```

**Ce script teste :**
1. ✅ Health check
2. ✅ Stats initiales (0 partout)
3. ✅ Import CSV avec `;` comme délimiteur
4. ✅ Ré-import (détection doublons)
5. ✅ Liste des vendors
6. ✅ Upload document TXT
7. ✅ Liste des documents
8. ✅ Chat RAG avec contexte
9. ✅ Stats finales (mise à jour)

---

## 🖱️ Étape 5 : Tests Manuels Frontend

### Test 1 : Admin Page - Import CSV

1. Aller sur http://localhost:3000/admin
2. Vérifier que les stats affichent **0 partout** au début
3. Cliquer sur **"Importer CSV"**
4. Sélectionner `test_vendors.csv`
5. ✅ **Résultat attendu :**
   - Message : "5 fournisseurs créés"
   - Le tableau affiche 5 fournisseurs
   - Les stats "Fournisseurs" passent à **5**

### Test 2 : Admin Page - Doublons

1. Re-cliquer sur **"Importer CSV"**
2. Re-sélectionner `test_vendors.csv`
3. ✅ **Résultat attendu :**
   - Message : "0 fournisseurs créés, 5 fournisseurs ignorés (déjà existant)"
   - Pas de doublons dans le tableau

### Test 3 : Admin Page - CSV avec virgule

Créer un fichier `test_vendors_comma.csv` avec des **virgules** :

```csv
name,company_name,email,phone,category
Test User,Test Company,test@test.fr,0600000000,Test
```

1. Importer ce fichier
2. ✅ **Résultat attendu :**
   - Import réussi (détection automatique du délimiteur)

### Test 4 : Dashboard - Digest (si Gmail configuré)

⚠️ **Nécessite la configuration Gmail OAuth**

1. Aller sur http://localhost:3000/dashboard
2. Cliquer sur **"Générer le digest"**
3. ✅ **Résultat attendu :**
   - Si pas d'emails : Message "Aucun digest disponible" (structure normalisée)
   - Si emails : Affichage par catégorie (Urgent/Important/Routine)
   - Pas de "Invalid Date"
   - Les stats "Total Emails" dans Admin se mettent à jour

### Test 5 : Chat Page - RAG

1. Aller sur http://localhost:3000/chat
2. Taper : **"Quel est le montant du contrat de maintenance?"**
3. ✅ **Résultat attendu :**
   - Réponse : "850€ HT (1020€ TTC) par mois"
   - L'assistant utilise le contexte du document uploadé
   - Plus de message "Aucun document pertinent trouvé"

---

## 🔍 Vérifications Spécifiques

### Bug 1 : Emails persistés en base

```bash
# Dans psql ou pgAdmin
SELECT COUNT(*) FROM emails;
```

✅ Doit retourner le nombre d'emails traités (>0 après un digest)

### Bug 2 : Délimiteur CSV

- Tester avec `;` ✅
- Tester avec `,` ✅
- Les deux doivent fonctionner

### Bug 3 : Doublons

```bash
# Dans psql
SELECT email, COUNT(*) FROM vendors GROUP BY email HAVING COUNT(*) > 1;
```

✅ Doit retourner **0 ligne** (pas de doublons)

### Bug 4 : Documents indexés

```bash
# Dans psql
SELECT COUNT(*) FROM documents WHERE indexed = true;
```

✅ Doit retourner >0 après upload

### Bug 5 : Qdrant

Accéder à : http://localhost:6333/dashboard

- Collection : `disruptiq_documents`
- Points : Doit afficher les chunks indexés

---

## 📊 Résultats Attendus

Après tous les tests :

| Entité | Nombre Attendu |
|--------|----------------|
| Vendors | 5+ |
| Documents | 1+ |
| Emails | Variable (selon Gmail) |
| Chunks Qdrant | 10+ |

---

## 🐛 Dépannage

### Erreur : "Connection refused" au backend

```bash
# Vérifier que le backend tourne
curl http://localhost:8000/health
```

### Erreur : "Cannot connect to PostgreSQL"

```bash
# Vérifier que PostgreSQL est démarré
docker-compose ps postgres

# Voir les logs
docker-compose logs postgres
```

### Erreur : "Qdrant connection failed"

```bash
# Vérifier Qdrant
docker-compose ps qdrant

# Redémarrer si nécessaire
docker-compose restart qdrant
```

### Erreur : "pypdf not found"

```bash
cd backend
pip install pypdf==4.3.1
```

---

## 📝 Notes

- Le fichier `test_vendors.csv` utilise le **point-virgule** pour tester le bug corrigé
- Le fichier `test_document.txt` contient du texte structuré pour tester le RAG
- Les stats se mettent à jour **immédiatement** après chaque action
- La gestion des erreurs est maintenant **visible** dans l'UI

---

## ✅ Checklist de Validation

- [ ] Backend démarre sans erreur
- [ ] Frontend démarre sans erreur
- [ ] Health check répond 200
- [ ] Import CSV avec `;` fonctionne
- [ ] Doublons sont détectés et ignorés
- [ ] Upload de document fonctionne
- [ ] Document indexé dans Qdrant
- [ ] Chat RAG retourne une réponse pertinente
- [ ] Stats Admin affichent les bons compteurs
- [ ] Dashboard affiche les emails (si Gmail configuré)
- [ ] Pas de "Invalid Date" dans le Dashboard
- [ ] Gestion d'erreurs visible dans l'UI

---

## 🎉 Succès !

Si tous les tests passent, vous avez :
- ✅ Corrigé tous les bugs identifiés
- ✅ Un système RAG fonctionnel
- ✅ Des stats en temps réel
- ✅ Une gestion robuste des doublons
- ✅ Une UX améliorée

**Prochaines étapes :** Continuer le développement avec une base solide ! 🚀
