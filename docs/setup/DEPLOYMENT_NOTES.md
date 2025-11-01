# 📝 Notes de Déploiement - DisruptIQ

## ⚠️ Actions Critiques Avant Déploiement VPS

### 1. Gmail OAuth - Credentials Type

**État actuel (Développement local)** :
- Le projet utilise des credentials OAuth de type **"web"**
- Le script `gmail_auth.py` a été adapté pour convertir automatiquement les credentials "web" en format "installed" pour fonctionner en local
- Fichier : `backend/credentials/credentials.json` (type "web")

**Action requise pour Production VPS** :

#### Option A (Recommandée) : Utiliser des credentials "Application de bureau"
1. Créer un nouveau client OAuth de type **"Application de bureau"** dans Google Cloud Console
2. Télécharger le nouveau `credentials.json`
3. Remplacer le fichier dans le VPS
4. Le script `gmail_auth.py` fonctionnera nativement sans adaptation

#### Option B : Garder les credentials "web" (nécessite configuration serveur)
1. Configurer un vrai serveur web avec domaine (ex: `auth.disruptiq.com`)
2. Ajouter l'URI de callback dans Google Cloud Console : `https://auth.disruptiq.com/oauth/callback`
3. Modifier le script pour utiliser un flow web complet avec callback
4. Plus complexe, mais permet d'authentifier via une page web publique

**Recommandation** : Utiliser **Option A** pour simplifier le déploiement.

---

### 2. Variables d'Environnement à Configurer sur VPS

```bash
# Backend .env
GMAIL_TOKEN_PATH=/app/credentials/token.json
GMAIL_CREDENTIALS_PATH=/app/credentials/credentials.json

# Assurer que les chemins sont absolus et accessibles dans le container Docker
```

---

### 3. Authentification Gmail sur VPS

**Problème** : Le script `gmail_auth.py` nécessite un navigateur pour l'authentification initiale.

**Solutions** :

#### Option 1 : Authentifier en local, puis copier le token
1. Exécuter `python scripts/gmail_auth.py` sur votre machine locale
2. Récupérer le fichier `backend/credentials/token.json` généré
3. Le copier sur le VPS via SCP :
   ```bash
   scp backend/credentials/token.json user@vps:/path/to/DisruptIQ/backend/credentials/
   ```
4. Le backend utilisera ce token et le rafraîchira automatiquement

#### Option 2 : SSH avec port forwarding
1. Se connecter au VPS avec port forwarding :
   ```bash
   ssh -L 8080:localhost:8080 user@vps
   ```
2. Exécuter le script sur le VPS : `python scripts/gmail_auth.py`
3. Le navigateur local s'ouvrira et redirigera vers `localhost:8080`
4. L'authentification fonctionnera via le tunnel SSH

**Recommandation** : Utiliser **Option 1** (plus simple et rapide).

---

### 4. Sécurité - Fichiers Sensibles

**À NE JAMAIS committer dans Git** :
- `backend/credentials/credentials.json` ✅ Déjà dans `.gitignore`
- `backend/credentials/token.json` ✅ Déjà dans `.gitignore`
- `backend/.env` ✅ Déjà dans `.gitignore`

**Sur le VPS** :
- Permissions strictes sur les credentials :
  ```bash
  chmod 600 backend/credentials/credentials.json
  chmod 600 backend/credentials/token.json
  chmod 600 backend/.env
  ```

---

### 5. Backup et Rotation des Tokens

Le `token.json` Gmail OAuth expire et se rafraîchit automatiquement. En cas de problème :

```bash
# Supprimer le token et ré-authentifier
rm backend/credentials/token.json
python backend/scripts/gmail_auth.py
```

**Recommandation** : Mettre en place un backup automatique du `token.json` :
```bash
# Cron job sur le VPS (tous les jours à 3h du matin)
0 3 * * * cp /path/to/credentials/token.json /path/to/backups/token_$(date +\%Y\%m\%d).json
```

---

## 📦 Checklist Complète de Déploiement

### Avant le déploiement
- [ ] Créer des credentials OAuth "Application de bureau" (si Option A)
- [ ] Générer le `token.json` en local
- [ ] Configurer toutes les variables d'environnement
- [ ] Tester le backend en local avec les vrais credentials

### Pendant le déploiement
- [ ] Copier `credentials.json` sur le VPS (hors Git)
- [ ] Copier `token.json` sur le VPS (hors Git)
- [ ] Configurer `.env` sur le VPS
- [ ] Vérifier les permissions (chmod 600)
- [ ] Tester l'accès Gmail : `curl http://vps:8000/api/digest/generate`

### Après le déploiement
- [ ] Vérifier les logs : `docker-compose logs backend`
- [ ] Tester la génération du digest via l'interface
- [ ] Configurer les backups du `token.json`
- [ ] Documenter le process de ré-authentification

---

## 🔧 Commandes Utiles sur VPS

```bash
# Vérifier si le token est valide
python -c "from google.oauth2.credentials import Credentials; print(Credentials.from_authorized_user_file('credentials/token.json'))"

# Logs backend en temps réel
docker-compose logs -f backend

# Redémarrer uniquement le backend
docker-compose restart backend

# Tester l'API Gmail
docker-compose exec backend python -c "from app.services.email_processor import EmailProcessor; ep = EmailProcessor(); print('Gmail OK' if ep.gmail_service else 'Gmail KO')"
```

---

## 📚 Références

- [Gmail API Python Quickstart](https://developers.google.com/gmail/api/quickstart/python)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Gmail API Auth Guide](https://developers.google.com/gmail/api/auth/about-auth)

---

**Dernière mise à jour** : 31 octobre 2025
**Auteur** : DisruptIQ Team
**Version** : 1.0
