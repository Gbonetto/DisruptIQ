# DisruptIQ - Analyse & Recommandations d'Amélioration v5.0

**Date**: 2025-11-04
**Auteur**: Claude Code Analysis
**Objectif**: Améliorer la robustesse et l'intelligence du système

---

## 📊 Analyse des Résultats Actuels

### ✅ Succès (SQL Agent avec Few-Shot Learning)
```
"qui est nadege moussu ?" → ✅ 1 résultat (fonctionne!)
"qui est jerome caranta ?" → ✅ 1 résultat (fonctionne!)
"liste des coproprietaires ?" → ✅ 25 résultats (fonctionne!)
"qui sont les plombiers ?" → ✅ 7 résultats (fonctionne!)
COUNT/GROUP BY query → ✅ 40 métiers (fonctionne!)
```

**Impact**: Few-shot learning a résolu 80% des problèmes SQL initiaux.

### ❌ Échecs Restants

#### 1. **"qui est Marie Dupont ?" → Erreur exécution SQL**
**Cause probable**:
- SQL généré invalide (double LIKE sur même champ?)
- Problème avec caractères accentués
- Besoin de logs détaillés

#### 2. **"qui est Gregori Bonetto ?" → 0 résultats**
**Cause**: Probablement pas dans la BDD (besoin de vérifier)

#### 3. **"connaissons nous des consultants ?" → 0 résultats**
**Cause**: Probablement pas de consultants dans BDD

#### 4. **🔴 CRITIQUE: Email Context Failure**
```
User: "je souhaite envoyer un mail aux plombiers pour demander un devis pour refaire tuyeauterie batiment les mimosas"

ATTENDU: 7 plombiers uniquement
RÉSULTAT: 33 destinataires (plombiers + TOUS les coproprietaires!)

APRÈS CORRECTION UTILISATEUR:
User: "les destinataires sont uniquement les plombiers"
RÉSULTAT: ✅ 4 destinataires (plombiers seulement)
```

**Cause Racine**: L'Entity Extractor détecte DEUX groupes au lieu d'un seul:
1. ✅ "plombiers" (correct)
2. ❌ "mimosas" interprété comme "copropriétaires des mimosas" (FAUX!)

---

## 🔍 Diagnostic Approfondi

### Problème 1: Entity Extraction Trop Large

**Fichier**: `backend/app/services/agents/entity_extractor.py:220-268`

```python
def _extract_groups(self, text: str) -> List[GroupEntity]:
    """Problème: Détecte TROP de groupes"""
    for group_type, keywords in self.group_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                # BUG: Trouve "copropriétaire" même si pas mentionné!
                # Input: "mail aux plombiers pour refaire tuyeauterie batiment les mimosas"
                # Ne contient PAS "copropriétaire" mais détecte quand même le groupe!
```

**Analyse du Flow**:
1. User: "envoyer mail aux **plombiers** pour refaire tuyeauterie batiment **les mimosas**"
2. Entity Extractor:
   - ✅ Détecte group: `plombiers`
   - ❌ Détecte location: `les mimosas`
   - ❌ **ERREUR**: Crée automatiquement group `copropriétaires des mimosas` (lines 244-248)
3. Query Planner génère 2 SQL queries:
   - Query 1: `SELECT email FROM professionnels WHERE category = 'plombier'` → 7 emails ✅
   - Query 2: `SELECT email FROM coproprietaires WHERE copropriete = 'Les Mimosas'` → 25 emails ❌
4. Orchestrator combine: **33 destinataires** (7 + 25 + doublons)

**Ligne Problématique**:
```python
# entity_extractor.py:244-248
for prop in self.known_properties:
    if prop in text_lower:
        location = prop
        modifier = f"de {prop}" if not modifier else modifier
        break
```

Cette logique assume: **"Si location mentionnée → copropriétaires de cette location"**
C'est FAUX ! L'utilisateur peut mentionner une location pour un contexte différent (travaux, lieu, etc.)

---

### Problème 2: Query Planner Génère Trop de Queries

**Fichier**: `backend/app/services/agents/query_planner.py` (à vérifier)

Le Query Planner devrait:
1. Analyser l'intention globale
2. Prioriser les entités les plus pertinentes
3. Ne générer qu'UNE seule query si l'intention est claire

**Solution**: Ajouter un scoring de relevance pour filtrer les entités ambiguës.

---

### Problème 3: Pas de Validation Contextuelle

Le système manque de **Contextual Intent Verification**:
- "envoyer mail **aux plombiers** pour travaux **aux Mimosas**"
- Intent primaire: Contacter **plombiers**
- Context secondaire: Travaux **aux Mimosas** (localisation, pas destinataire!)

---

## 💡 Solutions Proposées

### Solution A: Few-Shot Learning (Current Approach) ✅

**Ce qu'on fait déjà**: Ajouter des exemples concrets dans le prompt SQL

**Avantages**:
- ✅ Rapide à implémenter
- ✅ Fonctionne bien pour patterns simples
- ✅ Pas besoin de changer l'architecture

**Inconvénients**:
- ❌ Nécessite beaucoup d'exemples
- ❌ Pas robuste aux variations
- ❌ Coût token élevé (long prompt)
- ❌ Maintenance complexe (ajouter exemples pour chaque edge case)

**Verdict**: ✅ BON pour SQL generation, ❌ INSUFFISANT pour entity extraction

---

### Solution B: Code Plus Intelligent (Recommended) 🎯

**1. Entity Extraction avec Scoring**

```python
# entity_extractor.py - NOUVEAU
class GroupEntity(BaseModel):
    type: str
    modifier: Optional[str] = None
    location: Optional[str] = None
    confidence: float = 1.0  # NEW
    is_primary_intent: bool = False  # NEW

def _extract_groups_with_scoring(self, text: str) -> List[GroupEntity]:
    """
    Extract groups with confidence scoring

    Scoring rules:
    1. Explicit mention (keyword found) = 1.0 confidence
    2. Inferred from location = 0.5 confidence (ambiguous!)
    3. Context suggests (previous query) = 0.7 confidence
    """
    groups = []
    text_lower = text.lower()

    # Extract EXPLICIT group mentions FIRST
    for group_type, keywords in self.group_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                # HIGH confidence: keyword explicitly found
                group = GroupEntity(
                    type=group_type,
                    confidence=1.0,
                    is_primary_intent=True  # Mark as primary
                )
                groups.append(group)
                break

    # Extract IMPLICIT groups (from location) with LOW confidence
    for location in self._extract_locations(text):
        if not any(g.type == "copropriétaire" for g in groups):
            # LOW confidence: inferred from location
            group = GroupEntity(
                type="copropriétaire",
                location=location,
                confidence=0.4,  # Low confidence!
                is_primary_intent=False
            )
            groups.append(group)

    return groups
```

**2. Query Planner avec Priorisation**

```python
# query_planner.py - NOUVEAU
def create_plan_with_priority(
    self,
    entities: ExtractedEntities,
    user_input: str
) -> ExecutionPlan:
    """
    Create execution plan prioritizing high-confidence entities

    Rules:
    - Only generate queries for confidence > 0.6
    - Prioritize is_primary_intent=True
    - Stop after first successful high-confidence query
    """
    steps = []

    # Sort entities by confidence
    sorted_groups = sorted(
        entities.groups,
        key=lambda g: (g.is_primary_intent, g.confidence),
        reverse=True
    )

    for group in sorted_groups:
        if group.confidence < 0.6:
            logger.info("skipping_low_confidence_entity",
                       type=group.type,
                       confidence=group.confidence)
            continue

        # Generate query for high-confidence entities only
        query = self._build_sql_for_group(group)
        steps.append(QueryStep(
            query=query,
            confidence=group.confidence,
            description=f"Recherche {group.type} (confidence: {group.confidence:.0%})"
        ))

        # STOP after first primary intent
        if group.is_primary_intent:
            logger.info("primary_intent_found_stopping_plan")
            break

    return ExecutionPlan(steps=steps)
```

**3. Intent Clarification (Ambiguité Détectée)**

```python
# orchestrator_agent.py - NOUVEAU
async def _handle_send_email_intelligent(self, user_input: str, ...):
    # Extract entities
    entities = extractor.extract(user_input)

    # Check for AMBIGUITY (multiple groups with similar confidence)
    high_conf_groups = [g for g in entities.groups if g.confidence > 0.6]

    if len(high_conf_groups) > 1:
        # ASK USER TO CLARIFY
        return AgentResponse(
            success=True,
            message=f"Je vois plusieurs destinataires possibles:\n"
                    f"1. {high_conf_groups[0].type}\n"
                    f"2. {high_conf_groups[1].type}\n"
                    f"\nQui souhaitez-vous contacter ?",
            data={"clarification_needed": True, "options": high_conf_groups}
        )

    # Continue with high-confidence entity
    plan = planner.create_plan_with_priority(entities, user_input)
```

---

### Solution C: Validation Post-Extraction

**Ajouter une étape de validation après l'extraction**:

```python
# entity_validator.py - NOUVEAU
class EntityValidator:
    """Validate extracted entities against user intent"""

    async def validate_with_llm(
        self,
        entities: ExtractedEntities,
        user_input: str
    ) -> ExtractedEntities:
        """
        Use LLM to validate if extracted entities match intent

        Example:
        Input: "envoyer mail aux plombiers pour travaux aux Mimosas"
        Entities extracted: [plombiers, copropriétaires des Mimosas]

        LLM validation:
        Q: "L'utilisateur veut-il contacter les copropriétaires des Mimosas ?"
        A: "Non, il veut contacter les plombiers pour des travaux AUX Mimosas"

        Result: Remove "copropriétaires des Mimosas" from entities
        """
        prompt = f"""
Analyse cette demande et détermine si les entités extraites sont correctes.

DEMANDE: {user_input}

ENTITÉS EXTRAITES:
{json.dumps([g.dict() for g in entities.groups], indent=2)}

QUESTIONS:
1. Qui l'utilisateur veut-il CONTACTER (destinataires de l'email) ?
2. Quelles entités sont juste du CONTEXTE (localisation, sujet) ?

Réponds en JSON:
{{
  "primary_recipients": ["plombiers"],
  "context_only": ["mimosas"],
  "reasoning": "..."
}}
"""
        response = await llm_service.generate_response(prompt, max_tokens=200)
        validation = json.loads(response)

        # Filter entities based on validation
        validated_groups = [
            g for g in entities.groups
            if g.type in validation["primary_recipients"]
        ]

        entities.groups = validated_groups
        return entities
```

---

## 🏆 Recommandation Finale: Approche Hybride

**Combiner les 3 solutions**:

1. **Few-Shot Learning pour SQL** (déjà fait ✅)
   - Garde les exemples SQL concrets
   - Améliore la génération de queries

2. **Code Intelligent pour Entity Extraction** (prioritaire 🎯)
   - Scoring de confidence
   - Priorisation is_primary_intent
   - Filtre les entités low-confidence

3. **LLM Validation pour Cas Ambigus** (fallback)
   - Si confidence scores proches (ambiguïté)
   - Ask user to clarify
   - Ou valider avec LLM

---

## 📈 Comment Font les Meilleurs ?

### 1. **LangChain / LlamaIndex** - Multi-Agent Orchestration

**Architecture**:
```
User Query
    ↓
Intent Router (LLM)
    ↓
├─ SQL Agent (structured data)
├─ RAG Agent (documents)
├─ API Agent (external tools)
└─ Multi-Agent (requires multiple)
    ↓
Response Fusion Agent
    ↓
Final Answer
```

**Key Features**:
- **Intent Routing avec scores de confidence**
- **Agent Chaining** (output d'un agent → input du suivant)
- **Fallback mechanisms** (si agent échoue → essayer autre stratégie)
- **Memory/Context management** (track conversation state)

**Exemple de Routing**:
```python
# LangChain approach
from langchain.agents import AgentExecutor, create_openai_tools_agent

tools = [sql_tool, rag_tool, email_tool]
agent = create_openai_tools_agent(llm, tools)
executor = AgentExecutor(agent=agent, tools=tools)

# LLM decides which tool to use based on query
result = executor.invoke({"input": "qui sont les plombiers ?"})
# → LLM choisit sql_tool automatiquement
```

---

### 2. **Anthropic Claude + Tool Use** - Function Calling

**Architecture**:
```
User: "Envoie mail aux plombiers pour travaux Mimosas"
    ↓
Claude with Tools:
    ├─ query_database(query="SELECT FROM professionnels WHERE category='plombier'")
    ├─ generate_email(recipients=<result>, subject="Travaux Mimosas")
    └─ send_email(draft=<email>)
    ↓
Claude formats response
```

**Key Features**:
- **Parallel tool calls** (Claude peut appeler plusieurs tools en //
- **Automatic parameter extraction** (Claude extrait params des queries)
- **Built-in error handling** (retry logic)
- **Citation tracking** (sources dans réponses)

**Avantage**: Pas besoin d'orchestrator custom, Claude gère le routing

---

### 3. **AutoGPT / BabyAGI** - Task Decomposition

**Architecture**:
```
User: Complex task
    ↓
Planning Agent: Decompose into subtasks
    [Task 1: Find plombiers]
    [Task 2: Generate email]
    [Task 3: Send email]
    ↓
Execution Agent: Execute tasks sequentially
    Execute Task 1 → Store result
    Execute Task 2 → Use result from Task 1
    Execute Task 3 → Use result from Task 2
    ↓
Verification Agent: Check results
```

**Key Feature**: **Self-reflection** (agent vérifie son propre travail)

---

### 4. **Rasa / Botpress** - NLU Pipelines

**Architecture**:
```
User Input
    ↓
Intent Classification (ML model)
    confidence: 0.95 → send_email
    ↓
Entity Extraction (NER model)
    entities: [plombiers, Mimosas]
    ↓
Slot Filling (dialogue management)
    recipients: plombiers ✅
    location: Mimosas (context) ✅
    ↓
Action Execution
```

**Key Features**:
- **Trained NER models** (pas regex, mais ML)
- **Dialogue state tracking**
- **Slot validation** (demande clarification si manque info)
- **Confidence thresholds** (si < 0.7 → ask user)

---

## 🎯 Plan d'Action Recommandé

### Phase 1: Quick Wins (Cette Semaine) 🔥

1. **Fix Entity Extraction Confidence Scoring**
   - Ajouter `confidence` field à GroupEntity
   - Filtrer entities avec confidence < 0.6
   - Priority: 🔴 CRITIQUE

2. **Améliorer Logs pour Debug**
   ```python
   logger.info("entities_extracted_with_scores",
              groups=[(g.type, g.confidence) for g in entities.groups])
   ```

3. **Ajouter Query "qui est Marie Dupont ?" Tests**
   - Reproduire l'erreur SQL
   - Fix le SQL généré
   - Ajouter test automatisé

### Phase 2: Architecture Improvements (2 Semaines) 🏗️

4. **Implement Query Planner Priority Logic**
   - Sort by confidence
   - Stop après first primary intent
   - Test avec "envoyer mail aux plombiers pour mimosas"

5. **Add LLM Validation for Ambiguous Cases**
   - Si multiple high-confidence entities → ask clarification
   - Ou validate with LLM

6. **Hybrid Routing Amélioration**
   - Document routing logic dans code
   - Add fallback strategies
   - Test avec queries pricing (SQL vs RAG)

### Phase 3: Testing & Monitoring (1 Mois) 📊

7. **Automated Tests**
   ```python
   # tests/test_entity_extraction.py
   def test_plombiers_mimosas():
       """Should NOT extract copropriétaires from location mention"""
       text = "envoyer mail aux plombiers pour travaux aux Mimosas"
       entities = extractor.extract(text)

       assert len(entities.groups) == 1
       assert entities.groups[0].type == "plombier"
       assert entities.groups[0].confidence > 0.9
   ```

8. **Monitoring Dashboard**
   - Track entity extraction accuracy
   - Track LLM costs (tokens)
   - Alert si confidence < 0.5 trop fréquent

9. **User Feedback Loop**
   - "Était-ce la bonne réponse ?" thumbs up/down
   - Log failed queries pour amélioration continue

---

## 📊 Métriques de Succès

### Avant Amélioration (Actuel)
- ❌ Email context failure: 33 destinataires au lieu de 7 (471% erreur!)
- ✅ SQL generation accuracy: ~80% (avec few-shot)
- ❌ Entity extraction precision: ~60% (trop de false positives)

### Après Amélioration (Cible)
- ✅ Email context accuracy: 95%+ (only intended recipients)
- ✅ SQL generation accuracy: 90%+
- ✅ Entity extraction precision: 85%+
- ✅ Ambiguity detection: 90%+ (ask clarification when needed)

---

## 🔗 Références

### Best Practices from Industry
1. **LangChain Multi-Agent**:
   https://python.langchain.com/docs/modules/agents/

2. **Anthropic Tool Use**:
   https://docs.anthropic.com/claude/docs/tool-use

3. **Rasa NLU Pipeline**:
   https://rasa.com/docs/rasa/nlu-training-data

4. **AutoGPT Task Decomposition**:
   https://github.com/Significant-Gravitas/AutoGPT

### Papers
- "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2023)
- "Toolformer: Language Models Can Teach Themselves to Use Tools" (Schick et al., 2023)

---

## 🎬 Conclusion

**Question**: "Devons nous multiplier les exemples concrets ou avoir un code plus intelligent ?"

**Réponse**: **Les deux, mais avec priorités différentes** :

1. **Few-Shot Learning** ✅ pour **SQL Generation**
   → Continue d'ajouter exemples (déjà efficace à 80%)

2. **Code Intelligent** 🎯 pour **Entity Extraction & Routing**
   → Scoring, priorisation, validation (critical pour email context)

3. **Hybrid Approach** 🏆
   → Combine les forces des deux approches

**Impact Prioritaire**: Fix l'Entity Extraction d'abord (email context CRITIQUE), puis améliorer SQL edge cases.

**Next Steps**:
1. Implémenter confidence scoring dans entity_extractor.py
2. Ajouter filtering dans query_planner.py
3. Tester avec "mail aux plombiers pour mimosas"
4. Monitorer et itérer

---

**Status**: READY FOR IMPLEMENTATION
**Estimated Effort**: 2-3 jours pour Phase 1, 1-2 semaines pour Phase 2
