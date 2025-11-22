# Tests Interface Utilisateur - Legal Agent & Orchestrator
**Guide de Test Complet avec Edge Cases**

---

## 📋 Préparation des Tests

### Prérequis
1. ✅ Backend actif: `http://localhost:8000`
2. ✅ Frontend actif: `http://localhost:3000`
3. ✅ Docker services running (Redis, Postgres, Qdrant)
4. ✅ Documents uploadés dans la base (optionnel pour certains tests)

### Données de Test à Préparer

**Documents à uploader (format PDF ou TXT):**

1. **contrat_syndic_standard.txt**
```
CONTRAT DE SYNDIC DE COPROPRIÉTÉ

Entre les soussignés:
- La copropriété située au 123 Avenue de la République, 75011 Paris
Représentée par son syndic en exercice

Et:
- Cabinet IMMO GESTION, SARL au capital de 50,000€
Siège social: 45 Rue du Commerce, 75015 Paris

IL A ÉTÉ CONVENU CE QUI SUIT:

Article 1 - Durée du mandat
Le présent contrat est conclu pour une durée de 3 ans à compter du 1er janvier 2024.

Article 2 - Honoraires
Les honoraires du syndic sont fixés à 25,000€ par an, payables trimestriellement.
Ces honoraires seront révisés annuellement selon l'indice INSEE de référence, dans la limite de 3% par an.

Article 3 - Travaux d'urgence
Le syndic est autorisé à engager des travaux urgents dans la limite de 3,000€ sans autorisation préalable de l'assemblée générale.

Article 4 - Résiliation
Le contrat peut être résilié par l'une ou l'autre des parties moyennant un préavis de 3 mois notifié par lettre recommandée.

Article 5 - Compétence juridique
En cas de litige, les parties conviennent de la compétence du tribunal de commerce de Paris.

Fait à Paris, le 15 novembre 2023
En deux exemplaires originaux
```

2. **contrat_syndic_abusif.txt**
```
CONTRAT DE SYNDIC DE COPROPRIÉTÉ

Entre les soussignés:
- La copropriété "Les Jardins du Soleil"

Et:
- SyndiPro Services SARL

CLAUSES CONTRACTUELLES:

Article 1 - Durée
Le présent contrat est conclu pour une durée de 5 ans avec reconduction tacite automatique pour des périodes successives de 5 ans.

Article 2 - Honoraires
Honoraires annuels: 45,000€
Le syndic se réserve le droit de modifier ses honoraires à tout moment, sans préavis ni justification.
Indexation automatique de 8% par an sans plafond.

Article 3 - Travaux
Le syndic peut engager des travaux jusqu'à 50,000€ sans consultation de l'assemblée générale.

Article 4 - Résiliation
En cas de résiliation anticipée, le copropriétaire devra verser une indemnité égale à 18 mois d'honoraires.
Préavis de résiliation: 12 mois minimum.

Article 5 - Pénalités
Tout retard de paiement entraînera des pénalités de 15% par mois.
Clause pénale: en cas de non-respect du contrat par le copropriétaire, celui-ci devra verser 100,000€.

Article 6 - Juridiction
Tout litige relève de la juridiction exclusive du tribunal de commerce de Bordeaux, quel que soit le lieu de situation de l'immeuble.

Article 7 - Responsabilité
Le syndic exclut toute responsabilité pour les dommages de quelque nature que ce soit.
```

3. **bail_commercial.txt**
```
BAIL COMMERCIAL

Entre:
- Monsieur Jean DUPONT, propriétaire
- SAS TECH INNOVATION, locataire

Durée: 9 ans à compter du 1er mars 2024
Loyer: 3,500€ HT/mois
Charges: 800€/mois
Dépôt de garantie: 10,500€

Clause spéciale: Interdiction de sous-location
Révision triennale selon indice ILC
```

---

## 🎯 TESTS PAR CATÉGORIE

---

## NIVEAU 1: Tests Basiques (Warming Up)

### Test 1.1: Upload + Analyse Simple
**Objectif:** Tester l'upload et l'analyse de base

**Actions:**
1. Uploader `contrat_syndic_standard.txt`
2. Poser la question: **"Résume-moi ce document en 3 points clés"**

**Résultat Attendu:**
- ✅ Agent détecté: Legal Agent (action: analyze)
- ✅ Résumé structuré avec 3 points
- ✅ Mention: durée 3 ans, honoraires 25K€, résiliation 3 mois

**Modules testés:** Upload → Legal Agent (analyze)

---

### Test 1.2: Recherche Jurisprudence Pure
**Objectif:** Tester Légifrance API

**Actions:**
1. Poser la question: **"Quelle est la jurisprudence sur les assemblées générales de copropriété?"**

**Résultat Attendu:**
- ✅ Agent détecté: Legal Agent (action: jurisprudence)
- ✅ Au moins 3-5 décisions de justice
- ✅ Titres de décisions + dates + juridictions
- ✅ Sommaire de chaque décision

**Modules testés:** Legal Agent (jurisprudence) → Légifrance API

---

### Test 1.3: Extraction Entités Simple
**Objectif:** Tester le NER juridique

**Actions:**
1. Avec `contrat_syndic_standard.txt` uploadé
2. Poser: **"Quels sont les montants et durées mentionnés dans ce contrat?"**

**Résultat Attendu:**
- ✅ Montants: 25,000€, 3,000€
- ✅ Durées: 3 ans, 3 mois (préavis)
- ✅ Parties: copropriété, Cabinet IMMO GESTION

**Modules testés:** Legal Agent (analyze) → NER extraction

---

## NIVEAU 2: Tests Intermédiaires (Edge Cases Simples)

### Test 2.1: Détection Clauses Abusives
**Objectif:** Tester les 13 patterns de clauses

**Actions:**
1. Uploader `contrat_syndic_abusif.txt`
2. Poser: **"Y a-t-il des clauses abusives dans ce contrat?"**

**Résultat Attendu:**
- ✅ Agent: Legal Agent (analyze)
- ✅ Au moins 5-7 clauses détectées:
  - Reconduction tacite excessive (5 ans)
  - Modification unilatérale honoraires
  - Plafond travaux excessif (50K€)
  - Indemnité résiliation disproportionnée (18 mois)
  - Pénalités retard excessives (15%/mois)
  - Clause pénale disproportionnée (100K€)
  - Juridiction exclusive abusive
  - Exclusion responsabilité illégale
- ✅ Chaque clause avec:
  - Nom + Sévérité (critical/high/medium)
  - Base légale
  - Recommandation

**Modules testés:** Legal Agent (analyze) → Détection patterns regex → LLM analysis

---

### Test 2.2: Comparaison Multi-Documents
**Objectif:** Tester la comparaison de 2-3 contrats

**Actions:**
1. Uploader `contrat_syndic_standard.txt`
2. Uploader `contrat_syndic_abusif.txt`
3. Poser: **"Compare ces deux contrats de syndic et dis-moi lequel est le plus avantageux"**

**Résultat Attendu:**
- ✅ Agent: Legal Agent (action: compare)
- ✅ Tableau comparatif avec critères:
  - Durée
  - Honoraires
  - Conditions résiliation
  - Clauses abusives
- ✅ Recommandation claire: "Contrat Standard" avec score
- ✅ Liste des raisons (3-5 points)

**Modules testés:** Legal Agent (compare) → Multi-doc LLM analysis → JSON parsing

---

### Test 2.3: Question Hybride (Document + Jurisprudence)
**Objectif:** Combiner analyse doc + recherche jurisprudence

**Actions:**
1. Avec `contrat_syndic_abusif.txt` uploadé
2. Poser: **"Ce contrat contient-il des clauses abusives? Donne-moi des exemples de jurisprudence sur ce sujet"**

**Résultat Attendu:**
- ✅ Agent: Legal Agent (analyse PUIS jurisprudence)
- ✅ Partie 1: Liste clauses abusives du document
- ✅ Partie 2: Jurisprudence pertinente (3-5 décisions)
- ✅ Synthèse: Application de la jurisprudence au cas

**Modules testés:** Legal Agent (multi-action) → Document analysis → Légifrance → Synthesis

---

## NIVEAU 3: Tests Avancés (Multi-Agents)

### Test 3.1: Legal + PlombAgent (Contexte Mixte)
**Objectif:** Tester le routage intelligent multi-domaines

**Actions:**
1. Uploader un document juridique
2. Poser: **"J'ai un problème de fuite d'eau dans ma copropriété et le syndic refuse d'intervenir. Quels sont mes recours juridiques?"**

**Résultat Attendu:**
- ✅ Orchestrator détecte: contexte mixte (plomberie + juridique)
- ✅ Agent primaire: Legal Agent
- ✅ Contexte incident enrichi avec type: "water"
- ✅ Réponse juridique:
  - Obligations du syndic
  - Article 18 Loi 1965 (travaux urgence)
  - Jurisprudence pertinente
  - Procédure à suivre

**Modules testés:** Orchestrator → Legal Agent → Context enrichment

---

### Test 3.2: Recherche Multi-Sources (RAG + Légifrance + Web)
**Objectif:** Tester le fallback cascade des sources

**Actions:**
1. Avec documents uploadés dans RAG
2. Poser: **"Quelle est la jurisprudence récente sur les clauses de résiliation abusive dans les contrats de syndic?"**

**Résultat Attendu:**
- ✅ Agent: Legal Agent (jurisprudence)
- ✅ Sources utilisées (dans l'ordre):
  1. Légifrance API (prioritaire)
  2. RAG local (si documents pertinents)
  3. DuckDuckGo web search (fallback)
- ✅ Résultats mixtes avec indication de source
- ✅ Synthèse cohérente

**Modules testés:** Legal Agent → Légifrance → RAG → WebSearch → Synthesis

---

### Test 3.3: Query Complexe avec Calculs
**Objectif:** Tester extraction + calculs

**Actions:**
1. Avec `contrat_syndic_abusif.txt` uploadé
2. Poser: **"Si je résilie ce contrat après 2 ans, combien vais-je payer avec l'indemnité et les pénalités?"**

**Résultat Attendu:**
- ✅ Agent: Legal Agent (analyze)
- ✅ Extraction:
  - Honoraires: 45,000€/an
  - Indexation: 8%/an
  - Indemnité: 18 mois
- ✅ Calcul:
  - Année 1: 45,000€
  - Année 2: 45,000€ × 1.08 = 48,600€
  - Année 3: 48,600€ × 1.08 = 52,488€
  - Indemnité: (52,488€ / 12) × 18 = 78,732€
- ✅ Total avec justification

**Modules testés:** Legal Agent → NER → LLM calculations → Structured output

---

## NIVEAU 4: Tests Expert (Edge Cases Extrêmes)

### Test 4.1: Query Ambiguë (Teste Classification)
**Objectif:** Tester la robustesse de la classification

**Actions:**
1. Poser: **"Contrat"**

**Résultat Attendu:**
- ✅ Orchestrator gère l'ambiguïté
- ✅ Demande de clarification OU
- ✅ Suggestion: "Voulez-vous analyser un contrat, comparer des contrats, ou chercher de la jurisprudence?"

**Modules testés:** Orchestrator → Classification → User feedback

---

### Test 4.2: Query Hors Contexte (Teste Boundaries)
**Objectif:** Tester les limites du système

**Actions:**
1. Poser: **"Quelle est la recette du cassoulet?"**

**Résultat Attendu:**
- ✅ Orchestrator détecte: hors scope
- ✅ Agent: General/Advice (fallback)
- ✅ Réponse polie: "Je suis spécialisé en assistance juridique et technique pour la copropriété. Je ne peux pas vous aider avec des recettes de cuisine."

**Modules testés:** Orchestrator → Out-of-scope detection → Graceful response

---

### Test 4.3: Upload Multi-Format
**Objectif:** Tester la robustesse du parsing

**Actions:**
1. Uploader des documents variés:
   - PDF scanné (image)
   - TXT avec encodage UTF-8 spécial (accents)
   - DOCX (si supporté)
2. Analyser chacun

**Résultat Attendu:**
- ✅ TXT: Parsing parfait
- ✅ PDF texte: Extraction réussie
- ✅ PDF image: OCR ou message "nécessite OCR"
- ✅ DOCX: Parsing ou message "format non supporté"

**Modules testés:** Upload service → Document parsing → Error handling

---

### Test 4.4: Query Super Longue (Teste Truncation)
**Objectif:** Tester les limites de tokens

**Actions:**
1. Poser une question de 500+ mots avec contexte massif
2. Exemple: **"J'ai une copropriété de 150 lots construite en 1975, rénovée en 2010, avec [... 400 mots de détails ...]. Le syndic refuse de [détails]. Que puis-je faire selon la jurisprudence récente?"**

**Résultat Attendu:**
- ✅ Query acceptée (ou message taille max)
- ✅ Réponse pertinente même avec truncation
- ✅ Pas de crash

**Modules testés:** Input validation → Token management → LLM processing

---

### Test 4.5: Requêtes Simultanées (Teste Concurrence)
**Objectif:** Tester la gestion multi-utilisateurs

**Actions:**
1. Ouvrir 3 onglets du frontend
2. Poser 3 questions différentes en même temps:
   - Onglet 1: "Analyse ce contrat"
   - Onglet 2: "Jurisprudence assemblée générale"
   - Onglet 3: "Compare ces documents"

**Résultat Attendu:**
- ✅ Les 3 requêtes traitées sans interférence
- ✅ Réponses correctes dans chaque onglet
- ✅ Pas de mélange de contexte
- ✅ Session IDs différents

**Modules testés:** Session management → Async handling → Database isolation

---

## NIVEAU 5: Tests de Performance & Stress

### Test 5.1: Document Très Long (Teste Chunking)
**Objectif:** Tester le traitement de gros documents

**Actions:**
1. Uploader un contrat de 50+ pages (ou créer un TXT de 20,000+ mots)
2. Poser: **"Résume ce document et identifie toutes les clauses abusives"**

**Résultat Attendu:**
- ✅ Upload réussi (ou message taille max)
- ✅ Chunking automatique si nécessaire
- ✅ Analyse complète (peut prendre 60-90s)
- ✅ Résumé + clauses trouvées

**Modules testés:** Upload → Chunking → Large doc processing → Aggregation

---

### Test 5.2: Comparaison 5 Documents Max
**Objectif:** Tester la limite haute de comparaison

**Actions:**
1. Uploader 5 contrats différents
2. Poser: **"Compare ces 5 contrats et recommande le meilleur"**

**Résultat Attendu:**
- ✅ Comparaison réussie (limite max = 5)
- ✅ Tableau avec 5 colonnes
- ✅ Recommandation claire
- ✅ Temps de réponse < 30s

**Modules testés:** Multi-doc comparison → LLM scaling → JSON parsing

---

### Test 5.3: Cache Redis Performance
**Objectif:** Vérifier l'impact du cache

**Actions:**
1. Poser: **"Jurisprudence assemblée générale copropriété"**
2. Noter le temps de réponse (T1)
3. Poser EXACTEMENT la même question
4. Noter le temps de réponse (T2)

**Résultat Attendu:**
- ✅ T1: ~6-8 secondes (requête Légifrance)
- ✅ T2: ~2-3 secondes (cache Redis)
- ✅ Gain: ~50-60% plus rapide

**Modules testés:** Cache service → Redis → Performance optimization

---

## NIVEAU 6: Tests d'Intégration Complète

### Test 6.1: Scénario Réel Complet (User Journey)
**Objectif:** Simuler un cas d'usage réel de A à Z

**Scénario:**
Un copropriétaire reçoit un nouveau contrat de syndic et veut vérifier s'il est correct.

**Actions séquentielles:**
1. Upload du contrat reçu
2. **"Résume-moi ce contrat"**
3. **"Y a-t-il des clauses abusives?"**
4. **"Quelle est la jurisprudence sur les indemnités de résiliation excessives?"**
5. Upload de l'ancien contrat
6. **"Compare mon ancien contrat avec le nouveau"**
7. **"Que recommandes-tu? Dois-je signer?"**

**Résultat Attendu:**
- ✅ 7 réponses cohérentes qui se suivent
- ✅ Contexte conservé entre questions
- ✅ Analyse complète et recommandation finale
- ✅ Temps total < 5 minutes

**Modules testés:** TOUT LE SYSTÈME end-to-end

---

### Test 6.2: Incident + Legal (Multi-Agents)
**Objectif:** Tester la collaboration PlombAgent + Legal Agent

**Scénario:**
Incident de plomberie avec implications juridiques

**Actions:**
1. **"Il y a une fuite d'eau importante depuis 3 jours dans l'appartement du dessus. Le syndic ne répond pas. J'ai déjà dépensé 2,000€ en plombier d'urgence. Puis-je me faire rembourser?"**

**Résultat Attendu:**
- ✅ Orchestrator détecte: incident plomberie + question juridique
- ✅ Réponse multi-agents:
  - **PlombAgent:** Diagnostic de la fuite, actions d'urgence
  - **Legal Agent:**
    - Obligations du syndic (Article 18 Loi 1965)
    - Procédure de remboursement
    - Jurisprudence sur travaux d'urgence
    - Modèle de lettre de mise en demeure
- ✅ Synthèse cohérente des deux aspects

**Modules testés:** Orchestrator → Multi-agent coordination → Context sharing

---

### Test 6.3: RAG + Légifrance + Calculs
**Objectif:** Tester l'intégration maximale

**Préparation:**
1. Uploader dans RAG: plusieurs contrats + documents copropriété
2. Avoir des questions juridiques précédentes dans l'historique

**Actions:**
1. **"D'après mes documents, quel est le montant moyen des honoraires de syndic? Compare-le avec la jurisprudence récente et dis-moi si mes contrats sont dans la norme."**

**Résultat Attendu:**
- ✅ RAG: Extraction honoraires de tous les docs uploadés
- ✅ Calcul: Moyenne des montants
- ✅ Légifrance: Recherche jurisprudence honoraires
- ✅ Web search (fallback): Données marché si dispo
- ✅ Synthèse: Comparaison + recommandation

**Modules testés:** RAG → NER → Calculations → Légifrance → WebSearch → Synthesis

---

## 🎨 Tests d'Interface (UI/UX)

### Test UI.1: Streaming Responses
**Objectif:** Vérifier le streaming SSE

**Actions:**
1. Poser une question longue nécessitant analyse
2. Observer l'affichage progressif

**Résultat Attendu:**
- ✅ Indicateur "Thinking..." visible
- ✅ Réponse s'affiche progressivement (streaming)
- ✅ Chain of thought visible (si activé)
- ✅ Pas de blocage UI

**Modules testés:** SSE → ThoughtStream → UI rendering

---

### Test UI.2: Gestion Erreurs
**Objectif:** Tester les messages d'erreur

**Actions:**
1. Couper le backend
2. Poser une question
3. Redémarrer le backend
4. Poser une question

**Résultat Attendu:**
- ✅ Backend down: Message clair "Service temporairement indisponible"
- ✅ Retry automatique ou bouton "Réessayer"
- ✅ Backend up: Retour à la normale
- ✅ Pas de crash frontend

**Modules testés:** Error handling → User feedback → Resilience

---

### Test UI.3: Upload Progress
**Objectif:** Tester le feedback upload

**Actions:**
1. Uploader un fichier de 5MB+
2. Observer la progression

**Résultat Attendu:**
- ✅ Barre de progression visible
- ✅ Pourcentage d'upload
- ✅ Message de confirmation "Document uploadé"
- ✅ Document visible dans la liste

**Modules testés:** Upload UI → Progress tracking → Feedback

---

## 📊 Checklist de Validation

### Tests Obligatoires (Minimum Viable)
- [ ] Test 1.1: Upload + Analyse simple
- [ ] Test 1.2: Recherche jurisprudence
- [ ] Test 2.1: Détection clauses abusives
- [ ] Test 2.2: Comparaison multi-documents
- [ ] Test 3.2: Recherche multi-sources
- [ ] Test 6.1: Scénario réel complet

### Tests Recommandés (Production Ready)
- [ ] Test 2.3: Question hybride
- [ ] Test 3.1: Multi-agents (Legal + Plomb)
- [ ] Test 4.2: Query hors contexte
- [ ] Test 5.3: Cache performance
- [ ] Test UI.1: Streaming responses
- [ ] Test UI.2: Gestion erreurs

### Tests Avancés (Nice to Have)
- [ ] Test 3.3: Query avec calculs
- [ ] Test 4.3: Upload multi-format
- [ ] Test 4.5: Requêtes simultanées
- [ ] Test 5.1: Document très long
- [ ] Test 6.2: Incident + Legal
- [ ] Test 6.3: RAG + Légifrance + Calculs

---

## 📝 Template de Rapport de Test

Pour chaque test, note:

```markdown
### Test X.X: [Nom du test]

**Date:** [Date]
**Durée:** [Temps de réponse]

**Query:**
[Ta question exacte]

**Agent Détecté:**
[Legal/Plomb/General/Multi]

**Résultat:**
- [ ] ✅ Réussi / ❌ Échoué
- [ ] Temps de réponse: [X secondes]
- [ ] Qualité de la réponse: [1-5 étoiles]

**Observations:**
[Notes, bugs, améliorations]

**Capture d'écran:**
[Optionnel: screenshot de la réponse]
```

---

## 🐛 Bugs à Signaler

Si tu trouves des bugs, note:
1. **Query exacte** qui a causé le bug
2. **Comportement attendu** vs **comportement observé**
3. **Logs d'erreur** (console navigateur / backend logs)
4. **Reproductibilité** (à chaque fois / aléatoire)

---

## 🎯 KPIs à Mesurer

| Métrique | Objectif | Mesure |
|----------|----------|--------|
| Temps réponse analyse | < 30s | [___s] |
| Temps réponse jurisprudence | < 8s | [___s] |
| Précision détection clauses | 100% (3/3) | [_/3] |
| Taux réussite upload | 100% | [___%] |
| Streaming fonctionnel | Oui | [Oui/Non] |
| Cache accélération | > 40% | [___%] |

---

**Bon courage pour les tests! 🚀**

N'hésite pas à me partager tes résultats et on pourra corriger les bugs ou améliorer les fonctionnalités ensemble!
