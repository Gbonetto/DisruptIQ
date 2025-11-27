# DIAGNOSTIC BUGS CRITIQUES - DisruptIQ SMA RAG
## Analyse des Problèmes Identifiés
### 27 Novembre 2025

---

## PROBLEMES IDENTIFIES

### BUG 1: "Quel est le montant de la facture de plomberie?" → SQL au lieu de RAG

**Symptôme:** Le système retourne "1 résultat SQL" au lieu de chercher dans les documents uploadés.

**Cause Racine:**
- L'intent classifier V5 ne contient pas "facture", "montant", "devis" comme mots-clés RAG
- Les mots SQL (`combien`, `liste`, etc.) sont prioritaires
- Le mot "facture" devrait déclencher RAG car les factures sont des DOCUMENTS, pas des données SQL

**Solution:**
```python
# Dans intent_classifier_v5.py - Ajouter section RAG keywords AVANT SQL
rag_document_keywords = {
    "facture": 0.90,       # Les factures sont des documents
    "montant": 0.85,       # Souvent dans docs (sauf contexte SQL clair)
    "devis": 0.90,
    "contrat": 0.90,
    "pv": 0.85,            # PV d'AG
    "procès-verbal": 0.90,
    "dans les documents": 0.95,
    "dans le document": 0.95,
    "dans le fichier": 0.95,
}
```

---

### BUG 2: "Combien de lots a-t-elle?" → Perd le contexte (Arc-en-Ciel)

**Symptôme:** Après avoir parlé de la résidence Arc-en-Ciel, la question suivante ne maintient pas le contexte.

**Cause Racine:**
- Le `conversation_history` n'est pas correctement passé à `classify_intention()`
- Ou le `context_store` ne persiste pas l'entité "copropriété" mentionnée
- Ou l'enrichisseur de requêtes ne résout pas le pronom "elle"

**Solution:**
1. Dans `orchestrator_agent.process()`: S'assurer que `conversation_history` est bien passé
2. Dans `query_enrichment.py`: Ajouter résolution de pronoms ("elle" → dernière copropriété mentionnée)
3. Dans `context_store`: Persister les entités importantes

---

### BUG 3: Email avec "[À compléter]" partout + tous les destinataires

**Symptôme:**
- Email généré avec "[À compléter]" dans sujet et corps
- 21 destinataires au lieu des copropriétaires CONCERNES par les travaux

**Cause Racine:**
- `email_agent.py` ne récupère pas le contexte de la conversation (facture plomberie)
- Pas de filtrage des destinataires basé sur le contexte (copropriété concernée, étage, etc.)
- Le LLM ne reçoit pas assez de contexte pour générer un contenu pertinent

**Solution:**
1. Passer `conversation_history` à `email_agent.generate_email()`
2. Extraire le contexte (montant facture, prestataire, copropriété) de la conversation
3. Filtrer les destinataires: seulement les copropriétaires de la copropriété concernée
4. Forcer le LLM à utiliser le contexte pour remplir sujet et corps

---

### BUG 4: "Quel prestataire a fait les travaux?" → Plan bureaucratique

**Symptôme:** Au lieu de chercher dans la facture uploadée (qui contient le nom du prestataire!), le système génère un plan d'action en 5 étapes pour "contacter le syndic, vérifier les archives, etc."

**Cause Racine:**
- L'intent classifier route vers `TRIGGER_WORKFLOW` ou `GENERAL_QUESTION` au lieu de `SEARCH_DOCUMENTS`
- Le système ne sait pas que la réponse est DANS les documents uploadés
- Le RAG n'est pas consulté en priorité quand on parle de "travaux" et qu'il y a des documents

**Solution:**
1. Ajouter "prestataire" + "travaux" comme déclencheur RAG
2. Vérifier si des documents sont uploadés AVANT de classifier
3. Si documents existent ET question concerne leur contenu → forcer RAG

---

### BUG 5: "Ce prestataire est-il dans notre base?" → Aucun résultat

**Symptôme:** Après avoir demandé le prestataire (qui n'a pas fonctionné), la question suivante ne comprend pas "ce prestataire" = référence au contexte.

**Cause Racine:**
- Même problème que BUG 2 - pas de résolution de références
- "ce prestataire" devrait être résolu vers le nom extrait précédemment
- Si pas de nom extrait → demander clarification au lieu de dire "aucun résultat"

---

### BUG 6: "Génère un email pour lui demander une facture" → Envoie aux copropriétaires

**Symptôme:** L'email est adressé à 14 copropriétaires au lieu du PRESTATAIRE mentionné.

**Cause Racine:**
- "lui" n'est pas résolu (devrait être le prestataire)
- L'email_agent utilise les destinataires par défaut (copropriétaires) au lieu du contexte
- Pas de logique pour distinguer "email AU prestataire" vs "email AUX copropriétaires"

**Solution:**
1. Résoudre "lui" → dernier prestataire/professionnel mentionné
2. Détecter "demander [quelque chose] AU prestataire" comme email professionnel
3. Chercher l'email du prestataire dans la facture ou la base

---

## PLAN D'ACTION PRIORISÉ

### PRIORITÉ 1: Intent Classifier - RAG vs SQL (BUG 1 & 4)

```python
# Fichier: intent_classifier_v5.py
# Ajouter AVANT les SQL keywords:

async def _quick_rules_classification(...):
    # ================================================================
    # 0.5 RAG DOCUMENT KEYWORDS - NOUVEAU (AVANT SQL!)
    # ================================================================
    rag_doc_keywords = {
        "facture": 0.90,
        "montant": 0.85,
        "devis": 0.90,
        "contrat": 0.90,
        "pv ag": 0.90,
        "procès-verbal": 0.90,
        "prestataire.*travaux": 0.85,  # regex
        "qui a fait les travaux": 0.90,
        "dans les documents": 0.95,
        "dans le document": 0.95,
    }

    for keyword, confidence in rag_doc_keywords.items():
        if keyword in query_lower:
            # MAIS: vérifier si contexte SQL explicite
            sql_context = ["combien de factures", "nombre de devis", "liste des contrats"]
            if not any(sc in query_lower for sc in sql_context):
                return IntentClassification(
                    intent=IntentType.SEARCH_DOCUMENTS,
                    ...
                )
```

### PRIORITÉ 2: Résolution de Références (BUG 2, 5, 6)

```python
# Fichier: query_enrichment.py (ou nouveau fichier)

class ReferenceResolver:
    """Résout les pronoms et références contextuelles"""

    PRONOUN_MAP = {
        "elle": ["copropriete", "residence"],
        "il": ["coproprietaire", "prestataire", "professionnel"],
        "lui": ["coproprietaire", "prestataire", "professionnel"],
        "ce prestataire": ["professionnel"],
        "cette copropriété": ["copropriete"],
        "ces travaux": ["document", "facture"],
    }

    async def resolve(self, query: str, context_store: ContextStore, session_id: str):
        """Remplace les références par les entités réelles"""
        for pronoun, entity_types in self.PRONOUN_MAP.items():
            if pronoun in query.lower():
                # Chercher dernière entité du type correspondant
                entity = context_store.get_last_entity(session_id, entity_types)
                if entity:
                    query = query.replace(pronoun, entity.name)
        return query
```

### PRIORITÉ 3: Email Agent - Contexte et Destinataires (BUG 3 & 6)

```python
# Fichier: email_agent.py

async def generate_email(self, user_request, db, conversation_history=None, ...):
    # 1. Extraire le contexte de la conversation
    context = self._extract_email_context(conversation_history)
    # context = {
    #   "copropriete": "Arc-en-Ciel",
    #   "montant": "587.40€",
    #   "prestataire": "Plomberie Express",
    #   "sujet_travaux": "plomberie"
    # }

    # 2. Déterminer le type de destinataires
    recipient_type = self._determine_recipient_type(user_request)
    # "prestataire" | "coproprietaires" | "specific_names"

    # 3. Filtrer les destinataires
    if recipient_type == "prestataire":
        recipients = await self._get_prestataire_email(context["prestataire"], db)
    elif recipient_type == "coproprietaires":
        # Filtrer par copropriété concernée
        recipients = await self._get_coproprietaires_filtered(
            copropriete=context.get("copropriete"),
            db=db
        )

    # 4. Générer avec contexte enrichi
    email = await self._generate_with_context(
        user_request=user_request,
        context=context,
        recipients=recipients
    )
```

---

## ORDRE D'IMPLEMENTATION

1. **JOUR 1 - Matin**: Fix Intent Classifier (RAG keywords) - BUG 1 & 4
2. **JOUR 1 - Après-midi**: Fix Reference Resolver - BUG 2 & 5
3. **JOUR 2 - Matin**: Fix Email Agent - BUG 3 & 6
4. **JOUR 2 - Après-midi**: Tests E2E avec assertions strictes
5. **JOUR 3**: Validation manuelle complète + Rapport final

---

## CRITÈRES DE SUCCÈS

Après les fixes, ces tests DOIVENT passer:

| Test | Requête | Réponse Attendue |
|------|---------|------------------|
| T1 | "Quel est le montant de la facture de plomberie?" | "587,40€" (extrait du PDF) |
| T2 | "Parle-moi de Arc-en-Ciel" puis "Combien de lots?" | "48 lots" ou "24 lots" |
| T3 | "Quel prestataire a fait les travaux?" | "Plomberie Express SARL" |
| T4 | "Génère un email pour informer les copropriétaires" | Contenu rempli + filtrés par copro |
| T5 | "Ce prestataire est-il dans notre base?" | Recherche SQL avec nom résolu |
| T6 | "Génère un email pour lui demander une facture" | Email au prestataire (pas copros) |

---

*Diagnostic réalisé par Claude Code*
*27 Novembre 2025*
