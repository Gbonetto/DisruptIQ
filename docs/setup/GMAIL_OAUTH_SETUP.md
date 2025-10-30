# 📧 Configuration Gmail OAuth pour DisruptIQ

## 🎯 Objectif

Configurer l'authentification Gmail OAuth 2.0 pour permettre à DisruptIQ de :
- Récupérer automatiquement les emails non lus
- Générer le Digest Quotidien avec de vrais emails
- Classifier les emails par urgence

---

## 📋 Prérequis

- Compte Google (Gmail)
- Accès à Google Cloud Console
- DisruptIQ installé et fonctionnel

---

## 🚀 Étapes de Configuration

### 1. Créer un Projet Google Cloud

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Cliquez sur **"Sélectionner un projet"** → **"Nouveau projet"**
3. Nom du projet : `DisruptIQ-Gmail`
4. Cliquez sur **"Créer"**

---

### 2. Activer Gmail API

1. Dans le menu, allez dans **"APIs et services"** → **"Bibliothèque"**
2. Recherchez **"Gmail API"**
3. Cliquez sur **"Gmail API"**
4. Cliquez sur **"Activer"**

---

### 3. Configurer l'Écran de Consentement OAuth

1. Allez dans **"APIs et services"** → **"Écran de consentement OAuth"**
2. Sélectionnez **"Externe"** (pour tester)
3. Cliquez sur **"Créer"**

**Configuration de l'écran de consentement** :
- **Nom de l'application** : `DisruptIQ`
- **E-mail d'assistance utilisateur** : Votre email
- **Logo de l'application** : (Optionnel)
- **Domaines autorisés** : (Laissez vide pour le développement)
- **E-mail du développeur** : Votre email

4. Cliquez sur **"Enregistrer et continuer"**

**Scopes (Portées)** :
5. Cliquez sur **"Ajouter ou supprimer des scopes"**
6. Ajoutez les scopes suivants :
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`

7. Cliquez sur **"Enregistrer et continuer"**

**Utilisateurs de test** :
8. Ajoutez votre email Gmail comme utilisateur de test
9. Cliquez sur **"Enregistrer et continuer"**
10. Vérifiez le résumé et cliquez sur **"Revenir au tableau de bord"**

---

### 4. Créer les Identifiants OAuth 2.0

1. Allez dans **"APIs et services"** → **"Identifiants"**
2. Cliquez sur **"+ Créer des identifiants"** → **"ID client OAuth"**

**Configuration** :
- **Type d'application** : Application web
- **Nom** : `DisruptIQ Backend`
- **URIs de redirection autorisés** :
  - `http://localhost:8000/api/auth/gmail/callback`
  - `http://localhost:3000/auth/callback` (pour le frontend si nécessaire)

3. Cliquez sur **"Créer"**

4. **IMPORTANT** : Téléchargez le fichier JSON des identifiants
   - Cliquez sur **"Télécharger JSON"**
   - Renommez le fichier en `credentials.json`

---

### 5. Installer les Dépendances Python

Dans le répertoire `backend/` :

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

Ajoutez dans `backend/requirements.txt` :
```txt
google-auth==2.23.4
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.1.1
google-api-python-client==2.108.0
```

---

### 6. Configurer DisruptIQ

#### A. Placer le fichier credentials.json

```bash
# Créez le dossier si nécessaire
mkdir -p backend/credentials

# Copiez le fichier téléchargé
cp ~/Downloads/credentials.json backend/credentials/credentials.json
```

#### B. Mettre à jour .env

Ajoutez dans `backend/.env` :

```env
# Gmail OAuth Configuration
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_CREDENTIALS_PATH=credentials/credentials.json
GOOGLE_TOKEN_PATH=credentials/token.json
GMAIL_USER_EMAIL=your.email@gmail.com
```

**Pour obtenir CLIENT_ID et CLIENT_SECRET** :
- Ouvrez le fichier `credentials.json`
- Copiez les valeurs de `client_id` et `client_secret`

---

### 7. Première Authentification (Autorisation)

Vous devrez autoriser DisruptIQ une seule fois. Deux méthodes :

#### Méthode 1 : Via Script Python (Recommandé)

Créez `backend/scripts/gmail_auth.py` :

```python
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def main():
    creds = None
    token_path = 'credentials/token.json'
    credentials_path = 'credentials/credentials.json'

    # Load existing token if available
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    print("✅ Authentication successful!")
    print(f"Token saved to: {token_path}")

if __name__ == '__main__':
    main()
```

Exécutez :
```bash
cd backend
python scripts/gmail_auth.py
```

Une fenêtre de navigateur s'ouvrira :
1. Connectez-vous avec votre compte Gmail
2. Autorisez DisruptIQ
3. Le token sera sauvegardé dans `credentials/token.json`

#### Méthode 2 : Via Endpoint API (Alternative)

Accédez à :
```
http://localhost:8000/api/auth/gmail/authorize
```

Cela vous redirigera vers Google pour autoriser l'application.

---

### 8. Vérifier la Configuration

#### Test 1 : Récupérer les emails

```bash
curl http://localhost:8000/api/digest/generate
```

Si la configuration est correcte, vous devriez voir les emails classés par urgence.

#### Test 2 : Via l'interface

1. Ouvrez http://localhost:3000
2. Allez sur le Dashboard
3. Le Digest devrait charger automatiquement avec vos vrais emails

---

## 🔒 Sécurité

### Fichiers Sensibles

Ajoutez dans `.gitignore` :
```
# Gmail OAuth
backend/credentials/credentials.json
backend/credentials/token.json
backend/credentials/*.json
```

### Variables d'Environnement

**NE JAMAIS committer** :
- `credentials.json` - Contient client_id et client_secret
- `token.json` - Contient les tokens d'accès

### Permissions

Les scopes utilisés sont :
- `gmail.readonly` - Lire les emails (non destructif)
- `gmail.modify` - Marquer comme lu (nécessaire pour le digest)

---

## 🐛 Dépannage

### Erreur : "Access blocked: DisruptIQ has not completed the Google verification process"

**Solution** : Ajoutez votre email comme utilisateur de test
1. Google Cloud Console → "Écran de consentement OAuth"
2. Section "Utilisateurs de test"
3. Ajoutez votre email

### Erreur : "invalid_grant"

**Solution** : Le token a expiré
```bash
# Supprimez le token et réautorisez
rm backend/credentials/token.json
python backend/scripts/gmail_auth.py
```

### Erreur : "Credentials file not found"

**Solution** : Vérifiez le chemin
```bash
# Le fichier doit être ici :
backend/credentials/credentials.json
```

### Aucun email récupéré

**Causes possibles** :
1. **Boîte de réception vide** : Envoyez-vous un email de test
2. **Filtre trop restrictif** : Vérifiez le paramètre `since_hours` (défaut: 24h)
3. **Permissions insuffisantes** : Vérifiez que les scopes sont corrects

---

## 📊 Configuration Avancée

### Filtrer les Emails

Modifiez `backend/.env` :

```env
# Récupérer seulement les emails non lus
GMAIL_QUERY=is:unread

# Récupérer les emails d'un label spécifique
GMAIL_QUERY=label:important

# Récupérer les emails récents (dernières 24h)
GMAIL_QUERY=is:unread newer_than:1d
```

### Limiter le Nombre d'Emails

```env
# Maximum 50 emails par récupération
GMAIL_MAX_RESULTS=50
```

### Fréquence de Récupération

Pour un digest quotidien automatique, configurez un cron job :

```bash
# Tous les jours à 8h du matin
0 8 * * * curl http://localhost:8000/api/digest/generate
```

---

## 🎯 Checklist de Validation

- [ ] Projet Google Cloud créé
- [ ] Gmail API activée
- [ ] Écran de consentement configuré
- [ ] Identifiants OAuth créés
- [ ] `credentials.json` téléchargé et placé
- [ ] Dépendances Python installées
- [ ] Variables `.env` configurées
- [ ] Première autorisation effectuée
- [ ] `token.json` généré
- [ ] Test de récupération d'emails réussi
- [ ] Dashboard affiche les vrais emails

---

## 🚀 Prochaines Étapes

Une fois Gmail OAuth configuré :

1. **Tester le Digest Quotidien** avec vos vrais emails
2. **Vérifier la classification** par urgence (Urgent/Important/Routine)
3. **Configurer l'envoi automatique** du digest par email
4. **Intégrer avec N8N** pour les workflows automatisés

---

## 📚 Ressources

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 Python Guide](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)

---

**Dernière mise à jour** : 30 octobre 2025
**Statut** : Guide complet pour configuration Gmail OAuth
