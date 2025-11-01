# 🔍 Diagnostic Gmail + Docker - DisruptIQ

**Date**: 1er novembre 2025
**Status**: EN COURS - Solution hybride recommandée

---

## 📊 Résumé du problème

### Symptômes
- ✅ Le script de diagnostic `diagnose_gmail.py` fonctionne **parfaitement** en dehors de Docker (31 emails récupérés)
- ❌ Le backend Docker ne récup ère que **1/17 emails** avec succès
- ❌ 14+ emails timeout avec erreur: `[SSL] record layer failure` ou `The read operation timed out`

### Emails manquants
3 emails importants de `gregori.bonetto@gmail.com` (hier après-midi):
1. "1/3 degat des eaux chez moi" (16:58)
2. "2/3 Gregori bonetto 86 Av Tasigny" (17:00)
3. "3/3 Gregori Bonetto" (17:01)

---

## 🛠️ Solutions testées

### ✅ 1. Augmentation de `max_emails` (RÉUSSI)
**Fichier**: `backend/app/api/endpoints/digest.py`
```python
max_emails: Optional[int] = 100  # Était 10
```
**Résultat**: Permet de récupérer plus d'emails de Gmail API

### ✅ 2. Variables d'environnement Gmail (RÉUSSI)
**Fichier**: `docker-compose.yml`
```yaml
environment:
  GMAIL_CREDENTIALS_PATH: ${GMAIL_CREDENTIALS_PATH}
  GMAIL_TOKEN_PATH: ${GMAIL_TOKEN_PATH}
```
**Résultat**: Backend reconnaît maintenant les credentials

### ✅ 3. Certificats SSL (PARTIELLEMENT)
**Fichier**: `backend/Dockerfile`
```dockerfile
RUN apt-get update && apt-get install -y ca-certificates \
    && update-ca-certificates
```
**Résultat**: Certificats installés mais SSL timeout persiste dans Docker

### ✅ 4. Batching des requêtes (AMÉLIORATION)
**Fichier**: `backend/app/services/email_processor.py`
```python
BATCH_SIZE = 5  # Traiter 5 emails à la fois au lieu de tous en parallèle
await asyncio.sleep(0.5)  # Délai entre batches
```
**Résultat**: Réduit la charge mais ne résout pas les timeout SSL

### ✅ 5. Retries améliorés (AMÉLIORATION)
```python
@retry(
    stop=stop_after_attempt(5),  # Était 3
    wait=wait_exponential(multiplier=2, min=3, max=30),  # Plus long
    retry=retry_if_exception_type((HttpError, TimeoutError, OSError))
)
```
**Résultat**: Plus résilient mais temps de traitement trop long (21 minutes pour 17 emails)

### ✅ 6. Configuration DNS Google (TESTÉ)
**Fichier**: `docker-compose.yml`
```yaml
dns:
  - 8.8.8.8
  - 8.8.4.4
```
**Résultat**: Amélioration mineure, SSL timeout persist

### ❌ 7. Variables SSL explicites (INEFFICACE)
```yaml
REQUESTS_CA_BUNDLE: /etc/ssl/certs/ca-certificates.crt
SSL_CERT_FILE: /etc/ssl/certs/ca-certificates.crt
```
**Résultat**: Aucun changement

---

## 🎯 Analyse de la cause racine

### Problème fondamental
**Gmail API + Python `httplib2` + Docker networking isolé = Incompatibilité SSL**

### Pourquoi ça ne fonctionne pas dans Docker?
1. **Isolation réseau**: Docker créé un réseau virtuel isolé
2. **SSL/TLS handshake**: `httplib2` (utilisé par Google API Client) a des problèmes de compatibilité avec le réseau Docker sur Windows
3. **Timeout cascade**: Avec retries, chaque email qui échoue prend 75 secondes (5 retries × délais exponentiels)

### Pourquoi ça fonctionne en dehors?
- Accès direct au réseau Windows
- Pas d'isolation réseau
- Stack SSL native

---

## 💡 Solutions à long terme

### Option 1: Service Hybride (RECOMMANDÉ ⭐)
**Principe**: Service de digest qui tourne en dehors de Docker, communique avec l'API

**Architecture**:
```
[Gmail API] ←→ [Service Digest externe] ←→ [Backend Docker API]
                  (Python standalone)         (FastAPI)
```

**Avantages**:
- ✅ Accès réseau natif pour Gmail
- ✅ Garde le backend dans Docker
- ✅ Solution stable et scalable
- ✅ Facile à deployer

**Implémentation**:
1. Créer `digest_service.py` standalone
2. Utilise le code Gmail existant
3. Appelle l'API backend pour persister les emails
4. Peut tourner comme service Windows ou cron job

### Option 2: Network Mode Host (LINUX UNIQUEMENT)
**Ne fonctionne PAS sur Windows Docker Desktop**

```yaml
# backend:
#   network_mode: host  # Linux seulement!
```

### Option 3: WSL2 + Docker Linux
**Principe**: Migrer l'environnement Docker vers WSL2

**Avantages**:
- ✅ `network_mode: host` disponible
- ✅ Meilleure compatibilité réseau

**Inconvénients**:
- ❌ Complexe à configurer
- ❌ Nécessite WSL2
- ❌ Peut avoir d'autres problèmes

### Option 4: Remplacer `httplib2` par `requests`
**Principe**: Fork Google API Client pour utiliser `requests` au lieu de `httplib2`

**Avantages**:
- ✅ `requests` plus stable dans Docker

**Inconvénients**:
- ❌ Très complexe
- ❌ Maintenance difficile
- ❌ Pas garanti de fonctionner

---

## 📝 Recommandation finale

### Solution recommandée: **Service Digest Hybride**

1. **Court terme** (aujourd'hui):
   - Utiliser `diagnose_gmail.py` amélioré comme service de digest temporaire
   - Appelle l'API backend pour persister les résultats

2. **Moyen terme** (cette semaine):
   - Créer `digest_service.py` production-ready
   - Déployer comme service Windows ou tâche planifiée
   - Garde toute la logique métier dans le backend Docker

3. **Long terme** (futur):
   - Si migration vers serveur Linux : utiliser `network_mode: host`
   - Si besoin de scalabilité : microservice séparé pour email processing

---

## 📦 Fichiers modifiés

### Configuration
- `backend/app/api/endpoints/digest.py` - max_emails: 100
- `backend/app/services/email_processor.py` - Batching + retries améliorés
- `docker-compose.yml` - Variables env + DNS

### Dockerfile
- `backend/Dockerfile` - Certificats SSL

### Scripts
- `diagnose_gmail.py` - Diagnostic et test
- `test_n8n_integration.py` - Tests N8N

---

## ✅ Ce qui fonctionne

1. ✅ N8N Integration - 100% fonctionnel
2. ✅ Backend API - 100% fonctionnel
3. ✅ Gmail OAuth - 100% fonctionnel (hors Docker)
4. ✅ Classification LLM - 100% fonctionnel
5. ✅ Filtrage promotional - 100% fonctionnel

## ❌ Ce qui ne fonctionne pas

1. ❌ Gmail API dans Docker - Timeout SSL
2. ❌ Digest quotidien automatique - Dépend de Gmail API

---

**Prochaine étape**: Implémenter le service digest hybride pour une solution stable à long terme.
