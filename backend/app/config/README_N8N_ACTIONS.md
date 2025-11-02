# Configuration des Actions N8N

## 📍 Où Renseigner les Actions N8N ?

Le fichier **`n8n_actions.yaml`** dans ce dossier contient toutes les actions que l'orchestrateur peut suggérer et exécuter.

### Structure du Fichier

```yaml
workflows:
  nom_action:
    name: "Nom affiché"
    description: "Description de l'action"
    webhook_id: "id-webhook-n8n"
    required_params: [...]
    optional_params: [...]
    confirmation_required: true/false
    suggested_when: [...]
```

## 🔧 Comment Ajouter une Nouvelle Action N8N ?

### Étape 1 : Créer le Workflow dans N8N

1. Créez votre workflow dans N8N
2. Ajoutez un nœud **Webhook** en début de workflow
3. Configurez le webhook avec un ID unique (ex: `mon-nouveau-workflow`)
4. Notez les paramètres attendus par votre workflow

### Étape 2 : Ajouter l'Action dans n8n_actions.yaml

Ajoutez votre action dans la section appropriée :

```yaml
workflows:
  mon_action:
    name: "Mon Action"
    description: "Description claire de ce que fait l'action"
    webhook_id: "mon-nouveau-workflow"  # ID du webhook N8N
    required_params:
      - param1
      - param2
    optional_params:
      - param3
    confirmation_required: true  # true si action critique
    suggested_when:
      - intent: "mon_intention"
      - keywords: ["mot-clé1", "mot-clé2"]
```

### Étape 3 : Ajouter les Règles de Suggestion (Optionnel)

Si vous voulez que l'IA suggère automatiquement cette action dans certains contextes :

```yaml
suggestion_rules:
  mon_contexte:
    - action: "mon_action"
      label: "Texte du bouton"
      icon: "🔧"
```

## 📋 Exemples Pratiques

### Exemple 1 : Ajouter une Action d'Envoi de Rapport

```yaml
workflows:
  rapport_technique_send:
    name: "Envoi Rapport Technique"
    description: "Envoyer un rapport technique aux copropriétaires"
    webhook_id: "rapport-technique"
    required_params:
      - rapport_type  # maintenance, incident, travaux
      - copropriete_id
      - period  # month/quarter/year
    optional_params:
      - recipients  # Si vide, tous les copropriétaires
      - include_photos
    confirmation_required: false
    suggested_when:
      - intent: "generation_rapport"
      - schedule: "monthly_end"
```

### Exemple 2 : Action de Planification Travaux

```yaml
workflows:
  travaux_planification:
    name: "Planifier Travaux"
    description: "Planifier et notifier travaux importants"
    webhook_id: "travaux-planning"
    required_params:
      - type_travaux
      - date_debut
      - date_fin
      - entreprise_id
      - copropriete_id
    optional_params:
      - impact  # "partiel", "total"
      - zones_concernees
      - consignes_acces
    confirmation_required: true  # Important : demande confirmation
    suggested_when:
      - intent: "planifier_travaux"
      - keywords: ["travaux", "rénovation", "chantier"]
```

## 🎯 Types d'Intentions Reconnues

L'orchestrateur peut détecter ces intentions automatiquement :

- `urgence_detectee` - Urgence identifiée
- `digest_generated` - Digest d'emails généré
- `facture_validee` - Facture validée
- `facture_rejetee` - Facture rejetée
- `demande_devis` - Demande de devis
- `professionnel_trouve` - Professionnel identifié
- `declaration_sinistre` - Déclaration de sinistre
- `preparation_ag` - Préparation assemblée générale

Vous pouvez en ajouter d'autres dans `orchestrator_agent.py`.

## ⚠️ Bonnes Pratiques

### Quand mettre `confirmation_required: true` ?

Mettez `true` pour :
- ✅ Envoi d'emails en masse
- ✅ Notifications SMS
- ✅ Actions financières (paiements, etc.)
- ✅ Modifications de données importantes
- ✅ Déclarations officielles (sinistres, etc.)

Mettez `false` pour :
- ✅ Création de brouillons
- ✅ Export de données
- ✅ Recherches
- ✅ Rapports automatiques

### Nommage des Actions

- Utilisez `snake_case` pour les IDs : `mon_action_cool`
- Utilisez des noms clairs et descriptifs
- Préfixez par catégorie si possible : `email_`, `devis_`, `ag_`, etc.

### Paramètres

**required_params** : Paramètres absolument nécessaires
```yaml
required_params:
  - recipients
  - message
```

**optional_params** : Paramètres optionnels avec valeurs par défaut
```yaml
optional_params:
  - cc
  - urgency_level  # default: "normal"
```

## 🔄 Recharger les Configurations

Après modification de `n8n_actions.yaml`, redémarrez le backend :

```bash
docker-compose restart backend
```

Ou en développement :
```bash
# Le backend recharge automatiquement avec uvicorn --reload
```

## 📚 Structure Complète de Référence

```yaml
workflows:
  action_id:
    # OBLIGATOIRE - Nom affiché dans l'interface
    name: "Nom Action"

    # OBLIGATOIRE - Description pour l'IA et l'utilisateur
    description: "Description détaillée"

    # OBLIGATOIRE - ID du webhook N8N
    webhook_id: "mon-webhook-n8n"

    # OBLIGATOIRE - Liste des paramètres requis
    required_params:
      - param1
      - param2

    # OPTIONNEL - Liste des paramètres optionnels
    optional_params:
      - param3

    # OBLIGATOIRE - Demander confirmation avant exécution ?
    confirmation_required: true

    # OPTIONNEL - Quand suggérer cette action ?
    suggested_when:
      - intent: "mon_intent"
      - keywords: ["mot1", "mot2"]
      - schedule: "daily_8am"
      - urgency_level: "critical"

suggestion_rules:
  context_name:
    - action: "action_id"
      label: "Texte du bouton"
      icon: "🔧"
```

## 🆘 Support

Si vous avez des questions sur la configuration :
1. Consultez les exemples dans `n8n_actions.yaml`
2. Regardez `workflow_agent.py` pour voir comment les actions sont appelées
3. Testez vos workflows dans N8N d'abord avant de les ajouter ici

## 📝 Changelog

Documentez vos modifications ici :

### [Date] - Votre Nom
- Ajout action `nom_action` : description
- Modification `autre_action` : changement params
