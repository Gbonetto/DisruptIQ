# Foundation Architecture Integration Guide

## Vue d'ensemble

Ce document explique comment intégrer les nouveaux composants fondation dans l'orchestrateur existant:

1. **Views SQL canoniques** - Accès sécurisé read-only pour SQL agent
2. **Tables observabilité** - Traçabilité complète (agent_runs, agent_steps)
3. **Planner DAG** - Plans d'exécution structurés
4. **Evaluator** - Règles de conformité explicites

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OrchestratorAgent                         │
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐ │
│  │   Intent     │────▶│   Planner    │────▶│  Executors  │ │
│  │ Classifier   │     │     DAG      │     │   (Skills)  │ │
│  └──────────────┘     └──────────────┘     └─────────────┘ │
│                              │                      │        │
│                              ▼                      ▼        │
│                       ┌─────────────┐       ┌──────────────┐│
│                       │  AgentRun   │◀──────│  AgentStep   ││
│                       │  (tracking) │       │  (tracking)  ││
│                       └─────────────┘       └──────────────┘│
│                              │                               │
│                              ▼                               │
│                       ┌─────────────┐                        │
│                       │  Evaluator  │                        │
│                       │   (rules)   │                        │
│                       └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prérequis

### 1. Exécuter la migration SQL

```bash
cd backend/migrations
./run_migration.sh foundation_views_and_observability.sql
```

Cela crée:
- 6 views SQL canoniques (vw_professionnels_min, etc.)
- 2 tables observabilité (agent_runs, agent_steps)
- Index pour performances

### 2. Vérifier les views créées

```bash
psql -h localhost -U disruptiq -d disruptiq -c "\dv"
```

Vous devriez voir:
- `vw_professionnels_min`
- `vw_professionnels_full`
- `vw_coproprietaires_contact`
- `vw_emails_urgents`
- `vw_coproprietes_stats`
- `vw_documents_active`

### 3. Vérifier les tables observabilité

```bash
psql -h localhost -U disruptiq -d disruptiq -c "\d agent_runs"
psql -h localhost -U disruptiq -d disruptiq -c "\d agent_steps"
```

## 🔌 Intégration dans l'orchestrateur

### Étape 1: Importer les nouveaux composants

```python
# backend/app/services/agents/orchestrator_agent.py

from app.services.agents.planner_dag import PlannerDAG, ExecutionPlan
from app.services.agents.evaluator import Evaluator, EvaluationResult
from app.models import AgentRun, AgentStep, AgentRunStatus, AgentStepStatus
from app.core.database import AsyncSession
from sqlalchemy.sql import func
import hashlib
import json
from datetime import datetime
```

### Étape 2: Initialiser dans le constructeur

```python
class OrchestratorAgent:
    def __init__(self):
        # ... existing code ...

        # Nouveaux composants
        self.planner = PlannerDAG()
        self.evaluator = Evaluator()

        logger.info("orchestrator_initialized_with_foundation", version="v2.1")
```

### Étape 3: Créer une nouvelle méthode `execute_with_plan`

```python
async def execute_with_plan(
    self,
    user_input: str,
    conversation_id: str,
    user_id: Optional[int] = None,
    db: Optional[AsyncSession] = None,
    context: Optional[Dict[str, Any]] = None
) -> AgentResponse:
    """
    Exécute une query avec plan DAG et observabilité complète.

    Flow:
    1. Classifier intent
    2. Générer plan DAG
    3. Créer AgentRun (tracking)
    4. Exécuter chaque step
    5. Évaluer résultats
    6. Finaliser AgentRun
    """

    # 1. Intent classification
    intent_result = await self.intent_classifier_v2.classify(user_input, context)
    intent = intent_result["intent"]  # SQL_ONLY, RAG_ONLY, HYBRID, etc.
    confidence = intent_result.get("confidence", 0.0)

    logger.info(
        "orchestrator_intent_classified",
        intent=intent,
        confidence=confidence,
        conversation_id=conversation_id
    )

    # 2. Générer plan DAG
    plan = await self.planner.generate_plan(
        intent=intent,
        query=user_input,
        context=context,
        entities=intent_result.get("entities")
    )

    logger.info(
        "orchestrator_plan_generated",
        steps_count=len(plan.steps),
        estimated_tokens=plan.estimated_tokens
    )

    # Visualiser le plan (pour debug)
    plan_visualization = self.planner.visualize_plan(plan)
    logger.debug("orchestrator_plan_visualization", plan=plan_visualization)

    # 3. Créer AgentRun (tracking)
    agent_run = AgentRun(
        conversation_id=conversation_id,
        user_id=user_id,
        intent=intent,
        source=intent,  # Sera mis à jour après exécution
        confidence=confidence,
        plan_json=plan.dict(),
        status=AgentRunStatus.RUNNING.value,
        started_at=func.now()
    )

    if db:
        db.add(agent_run)
        await db.commit()
        await db.refresh(agent_run)

    run_id = agent_run.id

    logger.info(
        "orchestrator_run_started",
        run_id=run_id,
        conversation_id=conversation_id
    )

    # 4. Exécuter chaque step
    total_tokens = 0
    all_steps_success = True
    output_data = {}

    try:
        for step in plan.steps:
            step_result = await self._execute_step(
                step=step,
                run_id=run_id,
                output_data=output_data,
                db=db
            )

            if not step_result["success"]:
                all_steps_success = False
                if step_result.get("severity") == "critical":
                    break  # Arrêt si erreur critique

            total_tokens += step_result.get("tokens_used", 0)
            output_data[f"step{step.step_number}"] = step_result.get("output")

        # 5. Évaluer résultats
        evaluation = await self._evaluate_results(
            plan=plan,
            output_data=output_data,
            db=db
        )

        # 6. Finaliser AgentRun
        agent_run.status = (
            AgentRunStatus.SUCCESS.value if all_steps_success and evaluation.passed
            else AgentRunStatus.FAILED.value
        )
        agent_run.ended_at = func.now()
        agent_run.cost_tokens = total_tokens
        agent_run.cost_usd = total_tokens * 0.00001  # Estimation
        agent_run.evaluator_passed = evaluation.passed
        agent_run.evaluator_rules_failed = evaluation.rules_failed

        if db:
            await db.commit()

        logger.info(
            "orchestrator_run_completed",
            run_id=run_id,
            status=agent_run.status,
            tokens=total_tokens,
            evaluation_passed=evaluation.passed
        )

        # Préparer réponse
        return AgentResponse(
            success=all_steps_success and evaluation.passed,
            message=self._generate_response_message(output_data, plan),
            data={
                "run_id": run_id,
                "plan": plan.dict(),
                "evaluation": evaluation.dict(),
                "output": output_data
            },
            agents_used=[step.tool for step in plan.steps],
            confidence=confidence
        )

    except Exception as e:
        logger.error(
            "orchestrator_run_failed",
            run_id=run_id,
            error=str(e),
            exc_info=True
        )

        agent_run.status = AgentRunStatus.FAILED.value
        agent_run.error_message = str(e)
        agent_run.ended_at = func.now()

        if db:
            await db.commit()

        return AgentResponse(
            success=False,
            message=f"Erreur lors de l'exécution: {str(e)}",
            data={"run_id": run_id, "error": str(e)}
        )
```

### Étape 4: Implémenter `_execute_step`

```python
async def _execute_step(
    self,
    step: PlanStep,
    run_id: int,
    output_data: Dict[str, Any],
    db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Exécute une étape du plan et crée un AgentStep.
    """

    # Résoudre les variables {{stepX.field}} dans l'input
    resolved_input = self._resolve_step_variables(step.input, output_data)

    # Calculer hash de l'input (pour cache/dedup)
    input_str = json.dumps(resolved_input, sort_keys=True)
    input_hash = hashlib.sha256(input_str.encode()).hexdigest()

    # Créer AgentStep
    agent_step = AgentStep(
        run_id=run_id,
        step_number=step.step_number,
        tool=step.tool,
        input_json=resolved_input,
        input_hash=input_hash,
        status=AgentStepStatus.RUNNING.value,
        started_at=func.now()
    )

    if db:
        db.add(agent_step)
        await db.commit()
        await db.refresh(agent_step)

    logger.info(
        "orchestrator_step_started",
        run_id=run_id,
        step_number=step.step_number,
        tool=step.tool
    )

    # Exécuter le tool
    try:
        result = await self._dispatch_tool(step.tool, resolved_input)

        agent_step.status = AgentStepStatus.SUCCESS.value
        agent_step.output_json = result
        agent_step.ended_at = func.now()
        agent_step.tokens_used = result.get("tokens_used", 0)
        agent_step.evidence_count = result.get("evidence_count", 0)

        if db:
            await db.commit()

        return {
            "success": True,
            "output": result,
            "tokens_used": result.get("tokens_used", 0)
        }

    except Exception as e:
        logger.error(
            "orchestrator_step_failed",
            run_id=run_id,
            step_number=step.step_number,
            tool=step.tool,
            error=str(e),
            exc_info=True
        )

        agent_step.status = AgentStepStatus.FAILED.value
        agent_step.error_message = str(e)
        agent_step.ended_at = func.now()

        if db:
            await db.commit()

        return {
            "success": False,
            "error": str(e),
            "severity": "critical"
        }
```

### Étape 5: Implémenter `_dispatch_tool`

```python
async def _dispatch_tool(
    self,
    tool: str,
    input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Dispatche vers le tool/skill approprié.
    """

    if tool == "sql.plan":
        # Utiliser sql_agent_service existant
        from app.services.sql_agent_service import SQLAgentService
        sql_service = SQLAgentService()
        sql = await sql_service.generate_sql(input_data["query"])
        return {"sql": sql, "tokens_used": 200}

    elif tool == "sql.execute":
        from app.services.sql_agent_service import SQLAgentService
        sql_service = SQLAgentService()
        result = await sql_service.execute_sql(input_data["sql"])
        return {"rows": result, "row_count": len(result), "tokens_used": 0}

    elif tool == "rag.search":
        # Utiliser rag_service existant
        result = await self.rag_service.search(
            query=input_data["query"],
            top_k=input_data.get("top_k", 5)
        )
        return {"chunks": result, "evidence_count": len(result), "tokens_used": 100}

    elif tool == "rag.summarize":
        # Utiliser synthesis_agent existant
        from app.services.agents.synthesis_agent import SynthesisAgent
        synthesis = SynthesisAgent()
        result = await synthesis.synthesize_with_citations(
            query=input_data["query"],
            chunks=input_data["chunks"]
        )
        return {
            "response": result["response"],
            "citations": result["citations"],
            "tokens_used": result.get("tokens_used", 500)
        }

    elif tool == "fusion.merge":
        # Utiliser fusion_agent existant
        result = await self.fusion_agent.merge_sql_rag(
            sql_results=input_data["sql_results"],
            rag_response=input_data["rag_response"],
            rag_citations=input_data["rag_citations"]
        )
        return result

    elif tool == "evaluator.check":
        # Utiliser evaluator
        evaluation = await self.evaluator.evaluate(
            rules=input_data["rules"],
            context=input_data
        )
        return {"evaluation": evaluation.dict(), "tokens_used": 0}

    # ... autres tools ...

    else:
        raise ValueError(f"Tool inconnu: {tool}")
```

### Étape 6: Implémenter `_evaluate_results`

```python
async def _evaluate_results(
    self,
    plan: ExecutionPlan,
    output_data: Dict[str, Any],
    db: Optional[AsyncSession] = None
) -> EvaluationResult:
    """
    Évalue les résultats globaux selon l'intent.
    """

    # Déterminer règles à vérifier selon l'intent
    rules = []

    if plan.intent == "SQL_ONLY":
        rules = ["sql_no_error", "sql_results_not_empty"]

    elif plan.intent == "RAG_ONLY":
        rules = ["rag_has_citations", "rag_min_sources_2"]

    elif plan.intent == "HYBRID":
        rules = ["hybrid_no_contradiction", "hybrid_sources_attributed"]

    elif plan.intent == "EMAIL":
        rules = ["email_has_evidence", "email_preview_shown"]

    elif plan.intent == "N8N":
        rules = ["n8n_preview_if_danger_high", "n8n_correlation_id"]

    # Construire contexte pour l'évaluateur
    context = {
        "plan": plan.dict(),
        "output_data": output_data,
        **output_data  # Flatten pour accès facile
    }

    # Évaluer
    evaluation = await self.evaluator.evaluate(rules=rules, context=context)

    logger.info(
        "orchestrator_evaluation_complete",
        passed=evaluation.passed,
        rules_checked=evaluation.rules_checked,
        rules_failed=evaluation.rules_failed
    )

    return evaluation
```

## 🧪 Tests

### Test unitaire Planner

```python
# backend/tests/agents/test_planner_dag.py

import pytest
from app.services.agents.planner_dag import PlannerDAG

@pytest.mark.asyncio
async def test_planner_sql_only():
    planner = PlannerDAG()

    plan = await planner.generate_plan(
        intent="SQL_ONLY",
        query="Combien de copropriétaires actifs?"
    )

    assert plan.intent == "SQL_ONLY"
    assert len(plan.steps) >= 2  # plan + execute au minimum
    assert plan.steps[0].tool == "sql.plan"
    assert plan.steps[1].tool == "sql.execute"
    assert plan.estimated_tokens > 0
```

### Test unitaire Evaluator

```python
# backend/tests/agents/test_evaluator.py

import pytest
from app.services.agents.evaluator import Evaluator

@pytest.mark.asyncio
async def test_evaluator_rag_has_citations():
    evaluator = Evaluator()

    # Cas succès: citations présentes
    result = await evaluator.evaluate(
        rules=["rag_has_citations"],
        context={
            "response": "Selon le document [1], la procédure est...",
            "citations": [{"id": "doc_1", "content": "..."}]
        }
    )

    assert result.passed is True
    assert result.rules_passed == 1

    # Cas échec: aucune citation
    result_fail = await evaluator.evaluate(
        rules=["rag_has_citations"],
        context={
            "response": "La procédure est...",
            "citations": []
        }
    )

    assert result_fail.passed is False
    assert len(result_fail.rules_failed) == 1
```

## 📊 Queries d'observabilité

### Top 10 queries par coût

```sql
SELECT
    intent,
    AVG(cost_tokens) as avg_tokens,
    AVG(latency_ms) as avg_latency_ms,
    COUNT(*) as executions
FROM agent_runs
WHERE status = 'success'
GROUP BY intent
ORDER BY avg_tokens DESC
LIMIT 10;
```

### Taux de conflits SQL vs RAG

```sql
SELECT
    COUNT(*) FILTER (WHERE has_conflicts) * 100.0 / NULLIF(COUNT(*), 0) as conflict_rate_pct,
    COUNT(*) FILTER (WHERE has_conflicts) as conflicts_count,
    COUNT(*) as total_hybrid_runs
FROM agent_runs
WHERE intent = 'HYBRID';
```

### Latence moyenne par tool

```sql
SELECT
    tool,
    AVG(latency_ms) as avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms,
    COUNT(*) as executions
FROM agent_steps
WHERE status = 'success'
GROUP BY tool
ORDER BY avg_latency_ms DESC;
```

### Règles Evaluator échouées (top 5)

```sql
SELECT
    jsonb_array_elements_text(evaluator_rules_failed) as rule_id,
    COUNT(*) as failures_count
FROM agent_runs
WHERE evaluator_passed = FALSE
GROUP BY rule_id
ORDER BY failures_count DESC
LIMIT 5;
```

## 🚀 Déploiement

### 1. Exécuter migration

```bash
cd backend/migrations
./run_migration.sh foundation_views_and_observability.sql
```

### 2. Redémarrer backend

```bash
docker compose restart backend
```

### 3. Vérifier logs

```bash
docker compose logs -f backend | grep -E "planner|evaluator|agent_run"
```

### 4. Tester endpoint

```bash
curl -X POST http://localhost:8000/api/assistant-v2/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Combien de copropriétaires actifs?",
    "conversation_id": "test-123"
  }'
```

## 📝 Checklist post-intégration

- [ ] Migration SQL exécutée
- [ ] Views accessibles (`\dv`)
- [ ] Tables agent_runs/agent_steps créées
- [ ] Modèles SQLAlchemy importés sans erreur
- [ ] PlannerDAG instancié dans orchestrator
- [ ] Evaluator instancié dans orchestrator
- [ ] `execute_with_plan()` implémenté
- [ ] Tests unitaires passent
- [ ] Queries d'observabilité fonctionnent
- [ ] Logs structurés visibles
- [ ] Première exécution enregistrée dans agent_runs

## 🔍 Troubleshooting

### Erreur: "relation agent_runs does not exist"

→ Migration non exécutée. Relancer `run_migration.sh`

### Erreur: "views not accessible to SQL agent"

→ Grants manquants. Exécuter:
```sql
GRANT SELECT ON ALL TABLES IN SCHEMA public TO disruptiq;
```

### Performance dégradée

→ Vérifier index créés:
```sql
SELECT indexname, tablename FROM pg_indexes WHERE tablename IN ('agent_runs', 'agent_steps');
```

## 📚 Références

- [RAG v2.0 Specification](./RAG_v2.0_SPECIFICATION.md)
- [Right Panel Complete](./RIGHT_PANEL_COMPLETE_v2.0.md)
- [SQL Agent Service](./app/services/sql_agent_service.py)
- [Orchestrator Agent](./app/services/agents/orchestrator_agent.py)

## ✅ Prochaines étapes

1. **Phase 2 - Email safe-send**: Implémenter preview + checklist
2. **Phase 3 - N8N workflows.yaml**: Manifest déclaratif + preview
3. **Phase 4 - OCR factures**: Pipeline complet + tables factures_*
4. **Phase 5 - Web Search**: Agent web.search + cache TTL
5. **Phase 6 - Dashboard observabilité**: Grafana + métriques métier
