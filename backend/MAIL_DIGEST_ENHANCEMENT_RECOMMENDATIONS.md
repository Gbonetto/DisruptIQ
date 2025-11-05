# Recommandations: Amélioration du Mail Digest

## 📋 Contexte

**Question**: "Il y a une fonctionalité restante qui est celle du mail digest, que pouvons nous faire pour améliorer cette fonctionalité ?"

**Status actuel**: Digest fonctionnel mais basique - classification 3 niveaux (urgent/important/routine), HTML simple, pas d'intelligence contextuelle.

---

## 🔍 Analyse de l'Implémentation Actuelle

### **Architecture Existante**

```
Gmail API (external) → Backend Classification (LLM) → Database → Digest Generation → HTML Email
     ↓                       ↓                            ↓              ↓
  v1.py (host)      EmailProcessor           PostgreSQL      Simple HTML
                    (3 urgency levels)       (emails table)   (color-coded)
```

### **Flux Actuel**

1. **Sync Gmail** (`/api/digest/sync-gmail`)
   - Service externe (v1.py) fetch emails depuis Gmail
   - Contourne les problèmes réseau Docker
   - Envoie emails à backend pour classification

2. **Classification** (`EmailProcessor.classify_emails()`)
   - LLM classifie chaque email: URGENT / IMPORTANT / ROUTINE
   - Classification en parallèle (10 concurrent max)
   - Filtrage spam basique (noreply@, newsletter@)
   - Pas de catégorisation avancée

3. **Persistance** (DB PostgreSQL)
   - Table `emails` avec colonnes: urgency, category, llm_analysis
   - `category` et `llm_analysis` **non utilisés actuellement** ❌
   - Relations FK vers professionnels/coproprietes/coproprietaires **non utilisées** ❌

4. **Génération Digest** (`/api/digest/generate`)
   - Récupère emails depuis DB (dernières 24h)
   - Groupe par urgency seulement
   - HTML simple avec 3 sections colorées
   - Pas de résumé, pas d'analytics

5. **Scheduling** (`SchedulerService`)
   - Background job hourly pour sync + classification
   - Daily email à 08:00 (configurable)
   - Pas de personnalisation par utilisateur

---

## ❌ **Limitations Actuelles**

### 1. **Classification Simpliste**

**Problème**: Seulement 3 niveaux d'urgence, pas de catégorisation

```python
# Actuellement
email.urgency = "urgent" | "important" | "routine"

# Manque
email.category = None  # ❌ Colonne existe mais vide
email.llm_analysis = None  # ❌ Colonne existe mais vide
```

**Impact**:
- ❌ Impossible de filtrer par type (client, fournisseur, facturation, travaux, etc.)
- ❌ Pas de regroupement intelligent (tous les emails fournisseur ensemble)
- ❌ Pas de détection d'entités (montants, dates, noms mentionnés)

---

### 2. **Pas d'Intelligence Contextuelle**

**Problème**: Chaque email traité isolément, pas de contexte

```python
# Actuellement
for email in emails:
    urgency = classify_email(email)  # ❌ Email traité seul
```

**Manque**:
- ❌ **Thread intelligence**: Pas de groupage par conversation
- ❌ **Action detection**: Pas de détection "email nécessite réponse"
- ❌ **Deadline detection**: Pas d'extraction de dates limites
- ❌ **Priority scoring**: Pas de score composite (urgency + sender + deadline)

**Exemple concret**:
```
Email 1: "Devis plomberie pour Les Mimosas"
Email 2: "Re: Devis plomberie pour Les Mimosas"
Email 3: "Re: Re: Devis plomberie pour Les Mimosas"

Actuellement → 3 emails séparés ❌
Souhaité → 1 conversation groupée ✅
```

---

### 3. **Pas de Résumé Intelligent**

**Problème**: Liste brute d'emails, pas de synthèse

**Actuellement**:
```html
<div class="section">
    <h2>URGENT (3)</h2>
    <div>Email 1 - Subject - Sender - Snippet...</div>
    <div>Email 2 - Subject - Sender - Snippet...</div>
    <div>Email 3 - Subject - Sender - Snippet...</div>
</div>
```

**Manque**:
- ❌ **Executive summary**: Pas de résumé exécutif du jour
- ❌ **Key insights**: Pas de highlights automatiques
- ❌ **Timeline**: Pas de vue chronologique des événements
- ❌ **Action items**: Pas d'extraction des tâches à faire

**Exemple souhaité**:
```
📊 RÉSUMÉ DU JOUR
Total: 15 emails | 3 nécessitent une réponse urgente | 2 devis reçus

🔥 ACTIONS URGENTES
1. Répondre à M. Dupont (plombier) avant 17h - Devis Les Mimosas
2. Approuver facture Électricien Martin - 1 245€

💼 FAITS MARQUANTS
- 2 nouveaux devis reçus (total: 3 450€)
- Réclamation copropriétaire Apt 302 (fuite)
- Assemblée générale confirmée pour 15/11
```

---

### 4. **Pas de Personnalisation**

**Problème**: Digest identique pour tous les utilisateurs

```python
# Actuellement
digest = generate_digest(since_hours=24)  # ❌ Identique pour tous
```

**Manque**:
- ❌ **Filtrage par rôle**: Admin vs Manager vs Viewer
- ❌ **Préférences**: Verbosité (concis vs détaillé)
- ❌ **Focus areas**: Certains veulent seulement "urgent + travaux"
- ❌ **Langue**: Pas de support multi-langue

**Cas d'usage**:
- **Admin**: Veut TOUT voir (urgent + important + routine)
- **Manager**: Veut seulement urgent + important + facturation
- **Copropriétaire**: Veut seulement emails qui le concernent

---

### 5. **HTML Basique**

**Problème**: Design simple, pas moderne, pas interactif

**Actuellement**:
```html
<!-- Design basique -->
<div style="background: #EF4444;">URGENT</div>
<div style="background: #F59E0B;">IMPORTANT</div>
<div style="background: #10B981;">ROUTINE</div>
```

**Manque**:
- ❌ **Design moderne**: Pas de Tailwind/CSS moderne
- ❌ **Interactivité**: Pas de boutons d'action (Répondre, Archiver, Transférer)
- ❌ **Responsive**: Pas optimisé mobile
- ❌ **Charts**: Pas de visualisations (volume trends, response time)
- ❌ **Badges**: Pas de badges visuels (🔥 HOT, ⏰ DEADLINE, ❓ QUESTION)

---

### 6. **Pas d'Analytics**

**Problème**: Pas de métriques sur l'activité email

**Manque**:
- ❌ **Volume trends**: Pas de graphe "emails par jour"
- ❌ **Response time**: Pas de tracking "temps de réponse moyen"
- ❌ **Sender analytics**: Pas de "top senders cette semaine"
- ❌ **Category breakdown**: Pas de "répartition par catégorie"

**Exemple souhaité**:
```
📊 ANALYTICS (7 derniers jours)
- Volume: 105 emails (+15% vs semaine précédente)
- Taux de réponse: 78%
- Temps de réponse moyen: 4h 23min
- Top senders: M. Dupont (8), ENGIE (5), Copro Les Mimosas (4)
```

---

### 7. **Pas d'Intégration RAG**

**Problème**: Emails isolés, pas de contexte depuis documents

**Manque**:
- ❌ **Link to documents**: Email mentionne "facture 2024-001" → Pas de lien vers doc
- ❌ **Context enrichment**: Email de plombier → Pas d'historique des interventions
- ❌ **Knowledge base**: Email question → Pas de suggestions depuis docs

**Exemple souhaité**:
```
📧 Email: "Devis plomberie Les Mimosas - 1 245€"

🔗 CONTEXTE AUTOMATIQUE
- Document lié: Devis_Plomberie_2024-001.pdf
- Interventions précédentes: 3 (2023-2024)
- Budget restant copropriété: 45 000€
- Dernière facture: 850€ (Juin 2024)
```

---

### 8. **Relations Entités Non Utilisées**

**Problème**: Colonnes FK existent mais vides

```python
# Dans models/email.py
professionnel_id = Column(Integer)  # ❌ Toujours NULL
copropriete_id = Column(Integer)     # ❌ Toujours NULL
coproprietaire_id = Column(Integer)  # ❌ Toujours NULL
```

**Impact**:
- ❌ Impossible de requêter "tous les emails de M. Dupont (plombier)"
- ❌ Impossible de voir "emails liés à Les Mimosas (copropriété)"
- ❌ Impossible de filtrer "emails concernant M. Martin (copropriétaire Apt 302)"

---

## ✨ **Opportunités d'Amélioration**

### **Option A: Enhanced Classification & Categorization** ⭐

**Objectif**: Ajouter classification multi-dimension (urgency + category + entities + sentiment)

#### Implémentation

**1. Étendre le modèle Email**

Utiliser les colonnes existantes mais vides:

```python
# app/models/email.py (déjà existant mais pas utilisé)
category = Column(String)  # Type d'email
llm_analysis = Column(JSON)  # Analyse complète

# Nouvelle structure llm_analysis
{
    "urgency": "urgent",
    "category": "devis_fournisseur",  # ← NOUVEAU
    "subcategory": "plomberie",       # ← NOUVEAU
    "sentiment": "neutral",           # ← NOUVEAU
    "confidence": 0.92,
    "entities": {                     # ← NOUVEAU
        "amounts": [{"value": 1245, "currency": "EUR"}],
        "dates": ["2024-11-15"],
        "persons": ["M. Dupont"],
        "companies": ["Les Mimosas"]
    },
    "action_required": true,          # ← NOUVEAU
    "deadline": "2024-11-15T17:00:00Z",  # ← NOUVEAU
    "priority_score": 85,             # ← NOUVEAU (0-100)
    "thread_summary": "Échange de 3 emails sur devis plomberie",  # ← NOUVEAU
    "suggested_response": "Demander disponibilité pour intervention"  # ← NOUVEAU
}
```

**Catégories proposées**:
```python
class EmailCategory(str, enum.Enum):
    # Fournisseurs / Prestataires
    DEVIS_FOURNISSEUR = "devis_fournisseur"
    FACTURE_FOURNISSEUR = "facture_fournisseur"
    TRAVAUX_PLANIFICATION = "travaux_planification"
    INTERVENTION_URGENTE = "intervention_urgente"

    # Copropriétaires
    RECLAMATION_COPROPRIETAIRE = "reclamation_coproprietaire"
    QUESTION_COPROPRIETAIRE = "question_coproprietaire"
    PAIEMENT_CHARGES = "paiement_charges"

    # Administration
    ASSEMBLEE_GENERALE = "assemblee_generale"
    VOTE_DECISION = "vote_decision"
    DOCUMENT_ADMINISTRATIF = "document_administratif"

    # Finances
    COMPTABILITE = "comptabilite"
    BUDGET = "budget"
    PAIEMENT = "paiement"

    # Autres
    INFORMATION = "information"
    SPAM = "spam"
    AUTRE = "autre"
```

**2. Service de Classification Avancée**

**Nouveau fichier**: `app/services/advanced_email_classifier.py`

```python
"""
Advanced Email Classifier
Classification multi-dimension des emails avec extraction d'entités
"""

from typing import Dict, Any, List, Optional
import structlog
from datetime import datetime

from app.services.llm_service import LLMService
from app.services.conversation.entity_extractor import EntityExtractor
from app.models.email import EmailCategory

logger = structlog.get_logger(__name__)


class AdvancedEmailClassifier:
    """
    Classificateur d'emails avancé

    Capacités:
    - Classification multi-dimension (urgency + category + sentiment)
    - Extraction d'entités (montants, dates, personnes)
    - Détection d'actions requises
    - Score de priorité composite
    - Détection de threads/conversations
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.entity_extractor = EntityExtractor()

    async def classify_advanced(
        self,
        email: Dict[str, Any],
        thread_emails: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Classification avancée d'un email

        Args:
            email: Email à classifier
            thread_emails: Emails du même thread (pour contexte)

        Returns:
            Dict avec classification complète
        """
        # Construction du prompt pour LLM
        prompt = self._build_classification_prompt(email, thread_emails)

        # Appel LLM pour classification
        llm_result = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.1,
            response_format="json"
        )

        # Extraction d'entités depuis subject + body
        text = f"{email['subject']} {email['body']}"
        entities = self.entity_extractor.extract_entities(text)

        # Calcul du score de priorité
        priority_score = self._calculate_priority_score(
            urgency=llm_result.get('urgency'),
            category=llm_result.get('category'),
            has_deadline=llm_result.get('deadline') is not None,
            has_amount=len(entities.get('amounts', [])) > 0,
            sender_importance=self._get_sender_importance(email['sender'])
        )

        return {
            "urgency": llm_result.get('urgency', 'routine'),
            "category": llm_result.get('category', 'autre'),
            "subcategory": llm_result.get('subcategory'),
            "sentiment": llm_result.get('sentiment', 'neutral'),
            "confidence": llm_result.get('confidence', 0.5),
            "entities": entities,
            "action_required": llm_result.get('action_required', False),
            "deadline": llm_result.get('deadline'),
            "priority_score": priority_score,
            "thread_summary": llm_result.get('thread_summary'),
            "suggested_response": llm_result.get('suggested_response'),
            "tags": llm_result.get('tags', []),
        }

    def _build_classification_prompt(
        self,
        email: Dict[str, Any],
        thread_emails: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Construit le prompt pour le LLM"""

        prompt = f"""Analyse cet email et retourne une classification JSON complète.

EMAIL:
Sujet: {email['subject']}
Expéditeur: {email['sender']}
Corps: {email['body'][:500]}

CONTEXTE DU THREAD:
{self._format_thread_context(thread_emails) if thread_emails else "Aucun"}

CATÉGORIES POSSIBLES:
- devis_fournisseur, facture_fournisseur, travaux_planification, intervention_urgente
- reclamation_coproprietaire, question_coproprietaire, paiement_charges
- assemblee_generale, vote_decision, document_administratif
- comptabilite, budget, paiement
- information, spam, autre

RETOURNE UN JSON:
{{
    "urgency": "urgent|important|routine",
    "category": "category_name",
    "subcategory": "specific_type",
    "sentiment": "positive|neutral|negative|angry",
    "confidence": 0.85,
    "action_required": true|false,
    "deadline": "2024-11-15T17:00:00Z" ou null,
    "thread_summary": "Résumé de la conversation en 1 phrase",
    "suggested_response": "Action suggérée pour répondre",
    "tags": ["plomberie", "urgent", "devis"]
}}
"""
        return prompt

    def _calculate_priority_score(
        self,
        urgency: str,
        category: str,
        has_deadline: bool,
        has_amount: bool,
        sender_importance: int
    ) -> int:
        """
        Calcule un score de priorité composite (0-100)

        Pondération:
        - Urgency: 40 points max
        - Category: 20 points max
        - Deadline: 20 points max
        - Amount: 10 points max
        - Sender: 10 points max
        """
        score = 0

        # Urgency (40 points)
        urgency_scores = {
            'urgent': 40,
            'important': 25,
            'routine': 10
        }
        score += urgency_scores.get(urgency, 10)

        # Category (20 points)
        high_priority_categories = [
            'intervention_urgente',
            'reclamation_coproprietaire',
            'vote_decision'
        ]
        if category in high_priority_categories:
            score += 20
        elif category == 'facture_fournisseur':
            score += 15
        else:
            score += 10

        # Deadline (20 points)
        if has_deadline:
            score += 20

        # Amount (10 points)
        if has_amount:
            score += 10

        # Sender importance (10 points)
        score += sender_importance

        return min(score, 100)

    def _get_sender_importance(self, sender: str) -> int:
        """
        Évalue l'importance de l'expéditeur (0-10)

        TODO: Intégrer avec base de données (professionnels, coproprietaires)
        """
        # Logique simple pour MVP
        if 'noreply' in sender.lower():
            return 0
        elif '@gouv.fr' in sender or '@mairie' in sender:
            return 10
        else:
            return 5

    def _format_thread_context(self, thread_emails: List[Dict[str, Any]]) -> str:
        """Formate le contexte du thread pour le prompt"""
        if not thread_emails:
            return "Aucun"

        context = f"{len(thread_emails)} emails dans cette conversation:\n"
        for email in thread_emails[-3:]:  # Derniers 3 emails
            context += f"- {email['subject']} (de {email['sender']})\n"

        return context
```

**Bénéfices**:
- ✅ **Classification riche**: 15+ catégories au lieu de 3
- ✅ **Entités extraites**: Montants, dates, noms automatiquement
- ✅ **Score de priorité**: Ranking intelligent des emails
- ✅ **Actions suggérées**: LLM propose quoi faire
- ✅ **Sentiment**: Détecte emails négatifs/angry → Escalade

---

### **Option B: Thread Intelligence & Grouping** ⭐

**Objectif**: Grouper emails par conversation pour réduire le bruit

#### Implémentation

**Nouveau service**: `app/services/email_thread_analyzer.py`

```python
"""
Email Thread Analyzer
Analyse et groupe les emails par conversation/thread
"""

from typing import Dict, Any, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.email import Email

logger = structlog.get_logger(__name__)


class EmailThreadAnalyzer:
    """
    Analyseur de threads d'emails

    Capacités:
    - Grouper emails par thread_id Gmail
    - Détecter conversations multi-emails
    - Résumer thread en 1-2 phrases
    - Identifier "awaiting response"
    """

    async def group_emails_by_thread(
        self,
        emails: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Groupe emails par thread

        Returns:
            Dict[thread_id, List[emails]]
        """
        threads = {}

        for email in emails:
            thread_id = email.get('thread_id', email['message_id'])
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(email)

        # Trier emails dans chaque thread par date
        for thread_id in threads:
            threads[thread_id].sort(
                key=lambda e: e.get('received_at', ''),
                reverse=False  # Plus ancien en premier
            )

        logger.info(
            "threads_grouped",
            total_emails=len(emails),
            total_threads=len(threads),
            multi_email_threads=sum(1 for t in threads.values() if len(t) > 1)
        )

        return threads

    async def detect_awaiting_response(
        self,
        thread_emails: List[Dict[str, Any]],
        user_email: str
    ) -> bool:
        """
        Détecte si un thread attend une réponse de l'utilisateur

        Args:
            thread_emails: Emails du thread (triés chronologiquement)
            user_email: Email de l'utilisateur (pour détecter si dernier = autre)

        Returns:
            True si attend réponse
        """
        if not thread_emails:
            return False

        # Dernier email du thread
        last_email = thread_emails[-1]

        # Si dernier email n'est pas de l'utilisateur → Attend réponse
        last_sender = last_email.get('sender', '')

        if user_email.lower() not in last_sender.lower():
            # Vérifier si c'est une question
            subject = last_email.get('subject', '').lower()
            body = last_email.get('body', '').lower()

            question_indicators = ['?', 'question', 'demande', 'pouvez-vous', 'pourriez-vous']

            has_question = any(ind in subject or ind in body for ind in question_indicators)

            return has_question

        return False

    def summarize_thread(
        self,
        thread_emails: List[Dict[str, Any]]
    ) -> str:
        """
        Résume un thread en 1-2 phrases

        TODO: Utiliser LLM pour résumé intelligent
        """
        if not thread_emails:
            return ""

        if len(thread_emails) == 1:
            return f"Email de {thread_emails[0]['sender']}"

        first_subject = thread_emails[0]['subject']
        num_emails = len(thread_emails)
        senders = set(e['sender'] for e in thread_emails)

        return f"Conversation de {num_emails} emails: {first_subject} (entre {len(senders)} personnes)"
```

**Bénéfices**:
- ✅ **Réduction bruit**: 20 emails → 5 conversations
- ✅ **Contexte**: Voir toute la conversation d'un coup
- ✅ **Action items**: Détecte "awaiting response"

---

### **Option C: Executive Summary Generation** ⭐⭐⭐

**Objectif**: Générer résumé intelligent du jour avec LLM

#### Implémentation

**Nouveau service**: `app/services/digest_summarizer.py`

```python
"""
Digest Summarizer
Génère résumé exécutif intelligent du digest quotidien
"""

from typing import Dict, Any, List
import structlog

from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class DigestSummarizer:
    """
    Générateur de résumés de digest

    Capacités:
    - Résumé exécutif du jour (3-5 bullet points)
    - Highlights par catégorie
    - Actions urgentes identifiées
    - Métriques clés (volume, response rate, etc.)
    """

    def __init__(self):
        self.llm_service = LLMService()

    async def generate_executive_summary(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]],
        analytics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère résumé exécutif du digest

        Args:
            classified_emails: Emails classifiés par urgence/catégorie
            analytics: Métriques du digest

        Returns:
            Dict avec summary, highlights, actions
        """
        # Préparer contexte pour LLM
        context = self._prepare_context(classified_emails, analytics)

        # Prompt pour résumé
        prompt = f"""Tu es un assistant qui génère des résumés de digest d'emails pour un syndic de copropriété.

CONTEXTE:
{context}

GÉNÈRE UN RÉSUMÉ EXÉCUTIF AVEC:

1. VUE D'ENSEMBLE (2-3 phrases)
   Résumé global de l'activité du jour

2. ACTIONS URGENTES (top 3 max)
   Actions qui nécessitent une réponse/décision immédiate
   Format: "- [ACTION] Description (Deadline si applicable)"

3. FAITS MARQUANTS (3-5 bullet points)
   Événements importants du jour (nouveaux devis, réclamations, décisions)

4. PAR CATÉGORIE
   Résumé par catégorie d'email si pertinent

Retourne au format JSON:
{{
    "overview": "Vue d'ensemble...",
    "urgent_actions": [
        {{"action": "Répondre à M. Dupont", "description": "...", "deadline": "2024-11-15T17:00:00Z"}}
    ],
    "highlights": [
        "2 nouveaux devis reçus (total: 3 450€)",
        "Réclamation copropriétaire Apt 302",
        "..."
    ],
    "by_category": {{
        "devis_fournisseur": "2 devis reçus, total 3 450€",
        "reclamation_coproprietaire": "1 réclamation en attente"
    }}
}}
"""

        result = await self.llm_service.generate_response(
            prompt=prompt,
            temperature=0.3,
            response_format="json"
        )

        return result

    def _prepare_context(
        self,
        classified_emails: Dict[str, List[Dict[str, Any]]],
        analytics: Dict[str, Any]
    ) -> str:
        """Prépare le contexte pour le LLM"""

        urgent = classified_emails.get('urgent', [])
        important = classified_emails.get('important', [])
        routine = classified_emails.get('routine', [])

        context = f"""
MÉTRIQUES:
- Total emails: {analytics.get('total_emails', 0)}
- Urgents: {len(urgent)}
- Importants: {len(important)}
- Routine: {len(routine)}

EMAILS URGENTS:
"""

        for email in urgent[:5]:  # Top 5 urgents
            context += f"- {email.get('subject')} (de {email.get('sender')})\n"
            if email.get('llm_analysis'):
                context += f"  Catégorie: {email['llm_analysis'].get('category')}\n"
                if email['llm_analysis'].get('entities', {}).get('amounts'):
                    amounts = email['llm_analysis']['entities']['amounts']
                    context += f"  Montants: {amounts}\n"

        context += "\nEMAILS IMPORTANTS:\n"

        for email in important[:3]:  # Top 3 importants
            context += f"- {email.get('subject')} (de {email.get('sender')})\n"

        return context
```

**Bénéfices**:
- ✅ **Gain de temps**: Lecture 30s au lieu de 10min
- ✅ **Priorisation**: Actions urgentes en haut
- ✅ **Contexte**: Vue d'ensemble avant détails

---

### **Option D: Rich HTML Digest with Analytics** ⭐

**Objectif**: Design moderne + Charts + Boutons d'action

#### Implémentation

**Améliorations HTML**:

1. **Design Moderne** (Tailwind-style inline CSS)
2. **Charts**: Volume trends, category breakdown
3. **Action Buttons**: Répondre, Archiver, Voir thread
4. **Badges**: 🔥 HOT, ⏰ DEADLINE, ❓ QUESTION
5. **Responsive**: Mobile-friendly

**Exemple de nouveau HTML**:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* Modern Tailwind-inspired CSS */
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #F9FAFB;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .action-btn {
            background: #3B82F6;
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            text-decoration: none;
            display: inline-block;
            margin-right: 8px;
        }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 8px;
        }
        .badge-hot { background: #FEE2E2; color: #DC2626; }
        .badge-deadline { background: #FEF3C7; color: #D97706; }
        .badge-question { background: #DBEAFE; color: #2563EB; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header avec métriques -->
        <div class="header">
            <h1>📧 Digest Quotidien - DisruptIQ</h1>
            <p>Mardi 5 Novembre 2024</p>
            <div style="display: flex; gap: 30px; margin-top: 20px;">
                <div>
                    <div style="font-size: 32px; font-weight: bold;">15</div>
                    <div style="opacity: 0.9;">emails</div>
                </div>
                <div>
                    <div style="font-size: 32px; font-weight: bold;">3</div>
                    <div style="opacity: 0.9;">actions urgentes</div>
                </div>
                <div>
                    <div style="font-size: 32px; font-weight: bold;">2</div>
                    <div style="opacity: 0.9;">devis reçus</div>
                </div>
            </div>
        </div>

        <!-- Executive Summary -->
        <div class="summary-card">
            <h2 style="margin-top: 0;">📊 Résumé Exécutif</h2>
            <p>15 emails reçus aujourd'hui (+3 vs hier). 3 actions nécessitent votre attention urgente.</p>

            <h3>🔥 Actions Urgentes</h3>
            <ul>
                <li>
                    <strong>Répondre à M. Dupont (plombier)</strong> avant 17h - Devis Les Mimosas
                    <span class="badge badge-hot">🔥 HOT</span>
                    <span class="badge badge-deadline">⏰ Aujourd'hui 17h</span>
                    <br><br>
                    <a href="#" class="action-btn">✉️ Répondre</a>
                    <a href="#" class="action-btn">👁️ Voir thread</a>
                </li>
            </ul>

            <h3>💡 Faits Marquants</h3>
            <ul>
                <li>2 nouveaux devis reçus (total: 3 450€)</li>
                <li>Réclamation copropriétaire Apt 302 (fuite salle de bain)</li>
                <li>Assemblée générale confirmée pour 15/11</li>
            </ul>
        </div>

        <!-- Analytics Chart (SVG simple) -->
        <div class="summary-card">
            <h2 style="margin-top: 0;">📈 Analytics (7 derniers jours)</h2>
            <!-- TODO: Ajouter chart SVG ou Chart.js -->
            <p>Volume: 105 emails (+15% vs semaine précédente)</p>
            <p>Taux de réponse: 78%</p>
            <p>Temps de réponse moyen: 4h 23min</p>
        </div>

        <!-- Emails par catégorie -->
        <div class="summary-card">
            <h2 style="margin-top: 0;">🔴 Emails Urgents (3)</h2>

            <!-- Email card -->
            <div style="border-left: 4px solid #DC2626; padding-left: 16px; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <h3 style="margin: 0 0 8px 0;">Devis plomberie Les Mimosas</h3>
                        <p style="color: #6B7280; margin: 0 0 8px 0;">De: M. Dupont (dupont.plomberie@example.com)</p>
                        <p style="margin: 0 0 12px 0;">Bonjour, je vous envoie le devis pour la réparation fuite salle de bain...</p>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge badge-hot">🔥 HOT</span>
                        <span class="badge badge-deadline">⏰ 17h</span>
                    </div>
                </div>

                <div style="display: flex; gap: 12px; margin-top: 12px;">
                    <span style="background: #F3F4F6; padding: 4px 12px; border-radius: 8px; font-size: 12px;">
                        💼 devis_fournisseur
                    </span>
                    <span style="background: #F3F4F6; padding: 4px 12px; border-radius: 8px; font-size: 12px;">
                        💰 1 245€
                    </span>
                    <span style="background: #F3F4F6; padding: 4px 12px; border-radius: 8px; font-size: 12px;">
                        🏠 Les Mimosas
                    </span>
                </div>

                <div style="margin-top: 16px;">
                    <a href="#" class="action-btn">✉️ Répondre</a>
                    <a href="#" class="action-btn">👁️ Voir thread (3 emails)</a>
                    <a href="#" class="action-btn">📁 Archiver</a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
```

**Bénéfices**:
- ✅ **UX Moderne**: Design 2024, pas 2010
- ✅ **Actionnable**: Boutons 1-click
- ✅ **Visuel**: Charts et badges
- ✅ **Mobile**: Responsive design

---

### **Option E: Link to RAG & Database Entities** ⭐⭐

**Objectif**: Enrichir emails avec contexte depuis RAG/SQL

#### Implémentation

**Service de linking**: `app/services/email_entity_linker.py`

```python
"""
Email Entity Linker
Lie emails aux entités (professionnels, copropriétés, documents) via NER + RAG
"""

from typing import Dict, Any, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.professionnel import Professionnel
from app.models.copropriete import Copropriete
from app.models.coproprietaire import Coproprietaire
from app.models.document import Document
from app.services.rag_service import RAGService

logger = structlog.get_logger __name__)


class EmailEntityLinker:
    """
    Lie emails aux entités de la base de données

    Capacités:
    - Détecte mentions de professionnels dans email
    - Détecte mentions de copropriétés
    - Lie documents mentionnés via RAG
    - Enrichit email avec contexte historique
    """

    def __init__(self):
        self.rag_service = RAGService()

    async def link_entities(
        self,
        email: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Lie un email aux entités de la DB

        Returns:
            Dict avec linked_professionnels, linked_coproprietes, linked_documents
        """
        text = f"{email['subject']} {email['body']}"

        # Recherche professionnels mentionnés
        professionnels = await self._find_professionnels(text, db)

        # Recherche copropriétés mentionnées
        coproprietes = await self._find_coproprietes(text, db)

        # Recherche documents liés via RAG
        documents = await self._find_related_documents(text)

        return {
            "linked_professionnels": professionnels,
            "linked_coproprietes": coproprietes,
            "linked_documents": documents,
            "context_enrichment": await self._build_context(
                professionnels, coproprietes, documents, db
            )
        }

    async def _find_professionnels(
        self,
        text: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Trouve professionnels mentionnés dans le texte"""
        text_lower = text.lower()

        # Requête fuzzy match sur noms
        stmt = select(Professionnel).where(
            or_(
                Professionnel.name.ilike(f'%{word}%'),
                Professionnel.company_name.ilike(f'%{word}%')
            )
        ).limit(5)

        # TODO: Améliorer avec NER ou fuzzy matching avancé

        result = await db.execute(stmt)
        professionnels = result.scalars().all()

        return [
            {
                "id": p.id,
                "name": p.name,
                "company_name": p.company_name,
                "category": p.category
            }
            for p in professionnels
        ]

    async def _find_coproprietes(
        self,
        text: str,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Trouve copropriétés mentionnées"""
        # TODO: Implémenter recherche copropriétés
        return []

    async def _find_related_documents(
        self,
        text: str
    ) -> List[Dict[str, Any]]:
        """Trouve documents liés via RAG"""
        results = await self.rag_service.search(
            query=text[:200],  # Premiers 200 chars
            limit=3
        )

        return [
            {
                "document_id": r["document_id"],
                "text_snippet": r["text"][:100],
                "score": r["score"]
            }
            for r in results
        ]

    async def _build_context(
        self,
        professionnels: List[Dict],
        coproprietes: List[Dict],
        documents: List[Dict],
        db: AsyncSession
    ) -> str:
        """Construit contexte enrichi"""
        context_parts = []

        if professionnels:
            context_parts.append(
                f"Professionnel(s) lié(s): {', '.join(p['name'] for p in professionnels)}"
            )

        if coproprietes:
            context_parts.append(
                f"Copropriété(s) liée(s): {', '.join(c['nom'] for c in coproprietes)}"
            )

        if documents:
            context_parts.append(
                f"{len(documents)} document(s) lié(s) trouvé(s)"
            )

        return " | ".join(context_parts) if context_parts else "Aucun contexte lié"
```

**Bénéfices**:
- ✅ **Contexte automatique**: Email + historique en 1 vue
- ✅ **FK populées**: `professionnel_id`, `copropriete_id` remplis
- ✅ **RAG intégré**: Documents liés automatiquement

---

## 📊 **Comparaison des Options**

| Option | Impact | Complexité | Temps | Priorité |
|--------|--------|------------|-------|----------|
| **A: Enhanced Classification** | 🔥🔥🔥 Haut | ⭐⭐ Moyenne | 3 jours | **P0** |
| **B: Thread Intelligence** | 🔥🔥 Moyen | ⭐⭐ Moyenne | 2 jours | **P1** |
| **C: Executive Summary** | 🔥🔥🔥 Haut | ⭐⭐⭐ Élevée | 2 jours | **P0** |
| **D: Rich HTML** | 🔥🔥 Moyen | ⭐⭐ Moyenne | 3 jours | **P1** |
| **E: Entity Linking** | 🔥🔥 Moyen | ⭐⭐⭐ Élevée | 4 jours | **P2** |

---

## 🎯 **Recommandation: Approche Progressive**

### **Phase 1: Quick Wins** (1 semaine - Options A + C)

**Objectif**: Maximum d'impact avec effort raisonnable

1. ✅ **Enhanced Classification** (Option A)
   - Utiliser colonnes existantes (`category`, `llm_analysis`)
   - Classification multi-dimension avec LLM
   - Extraction d'entités
   - Priority scoring

2. ✅ **Executive Summary** (Option C)
   - Résumé LLM du digest
   - Actions urgentes identifiées
   - Highlights automatiques

**Bénéfices Phase 1**:
- ⏱️ **Lecture 5x plus rapide** (résumé exécutif)
- 🎯 **Priorisation automatique** (score de priorité)
- 📊 **Catégorisation riche** (15+ catégories)

---

### **Phase 2: UX & Intelligence** (2 semaines - Options B + D)

3. ✅ **Thread Intelligence** (Option B)
   - Groupage par conversation
   - Détection "awaiting response"

4. ✅ **Rich HTML Digest** (Option D)
   - Design moderne Tailwind-style
   - Action buttons (Répondre, Archiver)
   - Charts et analytics

**Bénéfices Phase 2**:
- 📉 **Réduction bruit**: 20 emails → 5 conversations
- 💅 **UX Moderne**: Design 2024
- 📊 **Visualisations**: Charts et métriques

---

### **Phase 3: Advanced Features** (3-4 semaines - Option E + extras)

5. ✅ **Entity Linking** (Option E)
   - Liaison emails ↔ professionnels/copropriétés
   - RAG integration pour documents
   - Contexte enrichi automatique

6. 🔮 **Bonus Features**:
   - Multi-user personnalisation (filtres par rôle)
   - Analytics dashboard (trends, response time)
   - Smart routing (qui doit répondre?)
   - Auto-response templates

---

## 📝 **Plan d'Implémentation Détaillé - Phase 1**

### **Semaine 1: Enhanced Classification (Option A)**

**Jour 1-2**: Service de classification avancée
- [ ] Créer `AdvancedEmailClassifier`
- [ ] Intégrer `EntityExtractor` (déjà existant!)
- [ ] Implémenter calcul priority score
- [ ] Tests unitaires (15+ tests)

**Jour 3**: Modification EmailProcessor
- [ ] Remplacer classification simple par avancée
- [ ] Peupler `category` et `llm_analysis`
- [ ] Tests d'intégration

**Jour 4-5**: Executive Summary (Option C)
- [ ] Créer `DigestSummarizer`
- [ ] Génération résumé LLM
- [ ] Intégration dans `/api/digest/generate`
- [ ] Tests E2E

---

## 🚀 **Bénéfices Attendus**

### **Avant (État Actuel)**
- ⏱️ **Temps de lecture**: 10-15 minutes
- 📧 **Organisation**: 3 niveaux (urgent/important/routine)
- 🤷 **Contexte**: Aucun
- 🎨 **Design**: Basique
- 📊 **Analytics**: Aucun

### **Après Phase 1**
- ⏱️ **Temps de lecture**: 2-3 minutes (résumé exécutif)
- 📧 **Organisation**: 15+ catégories + priority score
- 💡 **Contexte**: Entités extraites + actions suggérées
- 🎨 **Design**: Amélioré (résumé structuré)
- 📊 **Analytics**: Métriques basiques

### **Après Phase 2**
- ⏱️ **Temps de lecture**: 1-2 minutes
- 📧 **Organisation**: Conversations groupées
- 💡 **Contexte**: Thread intelligence + "awaiting response"
- 🎨 **Design**: Moderne + action buttons
- 📊 **Analytics**: Charts et visualisations

### **Après Phase 3**
- ⏱️ **Temps de lecture**: <1 minute
- 📧 **Organisation**: Personnalisée par utilisateur
- 💡 **Contexte**: RAG enrichi + historique complet
- 🎨 **Design**: Production-ready
- 📊 **Analytics**: Dashboard complet

---

## ✅ **Résumé Exécutif**

**Problème**: Digest fonctionnel mais basique - classification 3 niveaux, pas de contexte, HTML simple

**Solution Recommandée**: Approche progressive en 3 phases

**Phase 1** (1 semaine - **RECOMMANDÉ MAINTENANT**):
1. **Enhanced Classification** → 15+ catégories + priority score + extraction entités
2. **Executive Summary** → Résumé LLM intelligent avec actions urgentes

**Impact Phase 1**:
- ⏱️ **5x plus rapide** à lire (résumé exécutif)
- 🎯 **Priorisation automatique** (score 0-100)
- 📊 **Catégorisation riche** (devis, factures, réclamations, etc.)
- 💡 **Actions suggérées** par LLM

**Effort**: ~5 jours de développement

**ROI**: Positif dès le 1er mois (gain 8-10 min/jour × 20 jours = 160-200 min/mois économisées)

**Prochaine étape**: Valider Phase 1 et démarrer implémentation ✅
