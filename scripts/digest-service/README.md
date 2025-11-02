# Digest Service - External Gmail Fetcher

## Vue d'ensemble

Les scripts de ce dossier permettent de récupérer les emails Gmail **en dehors du conteneur Docker** et de les envoyer au backend pour traitement. Cette approche "hybride" résout les problèmes de réseau/SSL que Docker peut rencontrer avec l'API Gmail.

## Architecture Hybride

```
┌─────────────────────────────────────────────────────────────┐
│               PRODUCTION DIGEST FLOW                        │
└─────────────────────────────────────────────────────────────┘

User/Cron → digest_service (External - Windows/Mac/Linux)
           ├─ Gmail API OAuth ✓ (Native network access)
           ├─ fetch_unread_emails()
           └─ POST /api/digest/process-emails
                    │
                    ▼
           backend/app/api/endpoints/digest.py
           ├─ EmailProcessor.classify_emails()  [LLM]
           ├─ Database persistence
           └─ Response grouped by urgency (URGENT, IMPORTANT, ROUTINE)
```

## Versions Disponibles

### v1.py (Production - Recommandé)
- ✅ **Version stable** utilisée en production
- Récupération Gmail via OAuth2
- Classification LLM des emails (OpenAI/Anthropic)
- Envoi au backend via `/api/digest/process-emails`
- Gestion d'erreurs basique
- **Performance testée**: 17/17 emails récupérés (100% vs 6% Docker seul)

### v2.py (Enhanced - Beta)
- ✨ **Version améliorée** avec fonctionnalités avancées
- Tout ce que v1 fait, PLUS:
  - Validation Pydantic stricte
  - Retry logic avec tenacity (3-5 tentatives)
  - Health checks intégrés (`--health-check`)
  - Métriques détaillées (execution_id, duration, errors)
  - Signal handlers (graceful shutdown)
  - CLI arguments (`--dry-run`, `--since-hours`, `--max-emails`)

## Installation

### Prérequis

1. **Python 3.11+** installé localement
2. **Gmail API credentials** (`credentials/credentials.json`)
3. **Backend DisruptIQ** en cours d'exécution

### Setup Gmail API

```bash
# 1. Créer le dossier credentials s'il n'existe pas
mkdir -p ../../credentials

# 2. Placer votre credentials.json depuis Google Cloud Console
cp /path/to/credentials.json ../../credentials/

# 3. Authentifier (génère token.json)
python v1.py  # ou v2.py
# → Navigateur s'ouvre pour OAuth consent
# → Accepter les permissions
# → token.json créé automatiquement
```

### Installation des dépendances

```bash
# Installer les dépendances Python
pip install google-auth google-auth-oauthlib google-api-python-client \
            openai anthropic structlog httpx python-dotenv pydantic tenacity

# Ou depuis backend/requirements.txt
cd ../../backend
pip install -r requirements.txt
```

## Utilisation

### v1.py - Usage Simple

```bash
# Exécution simple (dernières 24h, max 50 emails)
python v1.py

# Personnalisation via code
# Éditer les paramètres dans v1.py:
# SINCE_HOURS = 24
# MAX_EMAILS = 50
```

### v2.py - Usage Avancé

```bash
# Exécution standard
python v2.py

# Dernières 48h, max 100 emails
python v2.py --since-hours 48 --max-emails 100

# Dry-run (teste sans envoyer au backend)
python v2.py --dry-run

# Health check (vérifie connexion Gmail + Backend)
python v2.py --health-check

# Toutes les options
python v2.py --help
```

### Options v2.py

| Option | Description | Défaut |
|--------|-------------|--------|
| `--since-hours` | Nombre d'heures à récupérer | 24 |
| `--max-emails` | Nombre max d'emails | 50 |
| `--dry-run` | Test sans envoi backend | False |
| `--health-check` | Vérifie Gmail + Backend | False |
| `--debug` | Mode debug verbose | False |

## Automatisation (Cron/Task Scheduler)

### Linux/Mac (Cron)

```bash
# Éditer crontab
crontab -e

# Exécuter tous les jours à 8h
0 8 * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && python v1.py >> digest.log 2>&1

# Exécuter toutes les 6 heures
0 */6 * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && python v2.py --since-hours 6
```

### Windows (Task Scheduler)

```powershell
# Créer une tâche planifiée
schtasks /create /tn "DisruptIQ Digest" /tr "python C:\path\to\DisruptIQ_CC\scripts\digest-service\v1.py" /sc daily /st 08:00

# Ou via GUI: Task Scheduler → Create Task
```

## Troubleshooting

### Erreur: "Credentials not found"

```bash
# Vérifier que credentials.json existe
ls -la ../../credentials/credentials.json

# Si absent, télécharger depuis Google Cloud Console
# Projet → APIs & Services → Credentials → OAuth 2.0 Client IDs
```

### Erreur: "Token refresh failed"

```bash
# Supprimer le token expiré et réauthentifier
rm ../../credentials/token.json
python v1.py  # Relance OAuth flow
```

### Erreur: "Backend connection failed"

```bash
# Vérifier que le backend est en cours d'exécution
curl http://localhost:8000/health

# Si non, démarrer Docker
cd ../..
docker-compose up -d backend
```

### Aucun email récupéré

```bash
# 1. Vérifier qu'il y a des emails non lus
# 2. Augmenter SINCE_HOURS
python v2.py --since-hours 72

# 3. Vérifier les logs
python v2.py --debug
```

## Comparaison v1 vs v2

| Fonctionnalité | v1 | v2 |
|---------------|----|----|
| Récupération Gmail | ✅ | ✅ |
| Classification LLM | ✅ | ✅ |
| Envoi Backend | ✅ | ✅ |
| Validation Pydantic | ❌ | ✅ |
| Retry Logic | Basic | Tenacity (3-5x) |
| Health Checks | ❌ | ✅ |
| Métriques | ❌ | ✅ (execution_id, duration) |
| CLI Args | ❌ | ✅ (7+ options) |
| Graceful Shutdown | ❌ | ✅ (SIGINT/SIGTERM) |
| Logging | structlog | structlog++ |

## Migration v1 → v2

```bash
# Tester v2 en dry-run
python v2.py --dry-run

# Si OK, remplacer v1 dans cron
# Ancien: python v1.py
# Nouveau: python v2.py --since-hours 24 --max-emails 50
```

## Logs et Monitoring

### Logs v1
```bash
# Logs dans stdout/stderr uniquement
python v1.py 2>&1 | tee digest.log
```

### Logs v2
```bash
# Logs structurés JSON
python v2.py --debug

# Métriques disponibles:
# - execution_id: ID unique de chaque run
# - duration: Durée totale
# - emails_fetched: Nombre d'emails récupérés
# - emails_sent: Nombre envoyés au backend
# - errors: Liste des erreurs
```

## Support

Pour toute question ou problème:
1. Vérifier les logs: `docker-compose logs backend`
2. Vérifier la doc backend: `../../backend/docs/DIGEST_ARCHITECTURE.md`
3. Tester en mode debug: `python v2.py --debug --health-check`

## Liens Utiles

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
- [Backend Digest Architecture](../../backend/docs/DIGEST_ARCHITECTURE.md)
