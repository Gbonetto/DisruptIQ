# 🚀 TODO: Déploiement VPS

## ⚠️ IMPORTANT: Configuration à Faire sur le VPS

### 📧 Automatisation Gmail Sync (OBLIGATOIRE)

**Action requise:** Configurer un cron job pour synchroniser Gmail toutes les 6 heures

```bash
# 1. Se connecter au VPS
ssh user@your-vps-ip

# 2. Éditer le crontab
crontab -e

# 3. Ajouter cette ligne (lance v1.py toutes les 6h: 0h, 6h, 12h, 18h)
0 */6 * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && /usr/bin/python3 v1.py >> /var/log/disruptiq_digest.log 2>&1

# 4. Sauvegarder et quitter (ESC + :wq sous vim)

# 5. Vérifier que le cron est bien créé
crontab -l
```

### 📝 Explication du Cron

```
0 */6 * * *  → Toutes les 6 heures, à l'heure pile (00:00, 06:00, 12:00, 18:00)
cd ...       → Va dans le dossier du script
python3 v1.py → Lance le script de synchronisation Gmail
>> /var/log/disruptiq_digest.log → Sauvegarde les logs
2>&1         → Inclut aussi les erreurs dans le log
```

### 🔍 Autres Options de Fréquence

```bash
# Toutes les 3 heures:
0 */3 * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && python3 v1.py >> /var/log/disruptiq_digest.log 2>&1

# Toutes les heures:
0 * * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && python3 v1.py >> /var/log/disruptiq_digest.log 2>&1

# Deux fois par jour (8h et 20h):
0 8,20 * * * cd /path/to/DisruptIQ_CC/scripts/digest-service && python3 v1.py >> /var/log/disruptiq_digest.log 2>&1
```

### ✅ Vérification Post-Déploiement

```bash
# 1. Vérifier que le cron tourne
crontab -l

# 2. Tester v1.py manuellement
cd /path/to/DisruptIQ_CC/scripts/digest-service
python3 v1.py

# 3. Vérifier les logs
tail -f /var/log/disruptiq_digest.log

# 4. Vérifier que les emails arrivent en base
# Via l'interface: "Genere mon digest"
# Tu devrais voir les emails récents
```

### 🔑 Prérequis VPS

Avant de configurer le cron, assure-toi que:

- [ ] Python 3.11+ installé
- [ ] Dépendances installées: `pip install -r backend/requirements.txt`
- [ ] Credentials Gmail configurés: `credentials/gmail_token.json`
- [ ] Docker et Docker Compose installés
- [ ] Conteneurs Docker lancés: `docker-compose up -d`
- [ ] Backend accessible sur port 8000

### 📊 Monitoring (Optionnel)

```bash
# Créer un script de monitoring
# /home/user/check_digest.sh

#!/bin/bash
LOG_FILE="/var/log/disruptiq_digest.log"
LAST_RUN=$(tail -1 $LOG_FILE | grep -o '[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}')

if [ -z "$LAST_RUN" ]; then
    echo "⚠️ Digest n'a jamais été exécuté"
else
    echo "✅ Dernière exécution: $LAST_RUN"
fi

# Rendre exécutable:
# chmod +x /home/user/check_digest.sh
```

---

## 📌 Rappel: Pourquoi C'est Important?

Sans le cron job:
- ❌ Les emails ne seront JAMAIS synchronisés automatiquement
- ❌ La base de données restera vide
- ❌ Les utilisateurs ne verront aucun email dans leur digest

Avec le cron job:
- ✅ Emails synchronisés toutes les 6h automatiquement
- ✅ Base de données toujours à jour (max 6h de retard)
- ✅ Digest instantané et fonctionnel

---

**Date de création:** 2025-11-03
**Statut:** ⚠️ À FAIRE lors du déploiement VPS
**Priorité:** 🔴 CRITIQUE (sans ça, le digest ne fonctionne pas)
