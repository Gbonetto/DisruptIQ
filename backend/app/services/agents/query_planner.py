"""
Query Planner - Generate intelligent multi-step execution plans

Takes extracted entities + context and creates actionable plans
with human-in-the-loop validation
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from enum import Enum
import structlog

from .entity_extractor import ExtractedEntities, PersonEntity, GroupEntity

logger = structlog.get_logger()


class StepType(str, Enum):
    """Types of execution steps"""
    SQL_QUERY = "sql_query"
    EMAIL_DRAFT = "email_draft"
    WORKFLOW_TRIGGER = "workflow_trigger"
    CONFIRMATION = "confirmation"


class ExecutionStep(BaseModel):
    """Single step in execution plan"""
    step_type: StepType
    description: str  # Human-readable description
    query: Optional[str] = None  # SQL query or search query
    requires_confirmation: bool = False
    depends_on: Optional[int] = None  # Index of step this depends on
    estimated_results: Optional[str] = None  # What we expect to find


class ExecutionPlan(BaseModel):
    """Complete execution plan for user request"""
    user_intent: str  # What user wants to do
    steps: List[ExecutionStep]
    total_steps: int
    requires_human_validation: bool = True
    confidence: float  # 0.0 to 1.0


class QueryPlanner:
    """
    Intelligent query planning with multi-step execution

    Creates plans like:
    1. SQL: Find emails for "nathalie girard" and "olivier bonnet"
    2. CONFIRM: Show found recipients (2 people found)
    3. EMAIL_DRAFT: Generate email with topic "problème chauffage"
    4. CONFIRM: Show draft, wait for user approval
    5. WORKFLOW: Send email (only if user confirms)
    """

    def __init__(self):
        logger.info("query_planner_initialized")

    def create_plan(
        self,
        entities: ExtractedEntities,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> ExecutionPlan:
        """
        Create intelligent execution plan from entities

        Args:
            entities: Extracted entities from user input
            user_input: Original user input
            context: Current conversation context

        Returns:
            ExecutionPlan with all steps needed
        """
        logger.info("creating_execution_plan",
                   persons=len(entities.persons),
                   groups=len(entities.groups),
                   actions=len(entities.actions))

        steps = []
        user_intent = self._determine_intent(entities, user_input)

        # Determine if we need recipient lookup
        needs_recipient_lookup = self._needs_recipient_lookup(entities, context)

        if needs_recipient_lookup:
            # Step 1: Lookup recipients
            sql_step = self._create_recipient_lookup_step(entities, context)
            steps.append(sql_step)

        # Check if email action
        if any(action.action_type == "send_email" for action in entities.actions):
            # Step 2: Generate email draft
            email_step = self._create_email_draft_step(entities, user_input, context)
            if needs_recipient_lookup:
                email_step.depends_on = 0  # Depends on SQL query
            steps.append(email_step)

            # Step 3: Human confirmation
            confirm_step = ExecutionStep(
                step_type=StepType.CONFIRMATION,
                description="Attente de votre confirmation pour envoyer l'email",
                requires_confirmation=True,
                depends_on=len(steps) - 1
            )
            steps.append(confirm_step)

        # Check if quote request
        elif any(action.action_type == "request_quote" for action in entities.actions):
            # Quote request workflow
            if needs_recipient_lookup:
                # Lookup professionals first
                pass

            quote_step = self._create_quote_request_step(entities, user_input, context)
            if needs_recipient_lookup:
                quote_step.depends_on = 0
            steps.append(quote_step)

            confirm_step = ExecutionStep(
                step_type=StepType.CONFIRMATION,
                description="Attente de votre confirmation pour envoyer les demandes de devis",
                requires_confirmation=True,
                depends_on=len(steps) - 1
            )
            steps.append(confirm_step)

        # Calculate confidence
        confidence = self._calculate_confidence(entities, steps)

        plan = ExecutionPlan(
            user_intent=user_intent,
            steps=steps,
            total_steps=len(steps),
            requires_human_validation=True,
            confidence=confidence
        )

        logger.info("execution_plan_created",
                   intent=user_intent,
                   steps=len(steps),
                   confidence=confidence)

        return plan

    def _determine_intent(self, entities: ExtractedEntities, user_input: str) -> str:
        """Determine main user intent from entities"""
        if entities.actions:
            action = entities.actions[0]
            if action.action_type == "send_email":
                subject = action.subject or "information"
                if entities.persons:
                    return f"Envoyer un email à {len(entities.persons)} personne(s) concernant {subject}"
                elif entities.groups:
                    group = entities.groups[0]
                    return f"Envoyer un email aux {group.type}s concernant {subject}"
                else:
                    return f"Envoyer un email concernant {subject}"
            elif action.action_type == "request_quote":
                return "Demander des devis aux professionnels"

        return "Traiter la demande"

    def _needs_recipient_lookup(self, entities: ExtractedEntities, context: Dict[str, Any] = None) -> bool:
        """Check if we need to query database for recipients"""
        # If specific persons mentioned, need lookup
        if entities.persons:
            return True

        # If groups mentioned, need lookup
        if entities.groups:
            return True

        # If context already has recipients, maybe not needed
        if context and context.get("emails_available"):
            # But if new entities mentioned, need fresh lookup
            return len(entities.persons) > 0 or len(entities.groups) > 0

        return False

    def _create_recipient_lookup_step(
        self,
        entities: ExtractedEntities,
        context: Dict[str, Any] = None
    ) -> ExecutionStep:
        """
        Create SQL query step to lookup recipients

        Generates intelligent SQL based on entities
        """
        query_parts = []
        description_parts = []

        # Handle persons
        if entities.persons:
            person_conditions = []
            for person in entities.persons:
                if person.prenom and person.nom:
                    person_conditions.append(
                        f"(LOWER(prenom) LIKE '%{person.prenom.lower()}%' AND LOWER(nom) LIKE '%{person.nom.lower()}%')"
                    )
            if person_conditions:
                query_parts.append(" OR ".join(person_conditions))
                description_parts.append(f"{len(entities.persons)} personne(s) spécifique(s)")

        # Handle groups
        if entities.groups:
            for group in entities.groups:
                if group.type == "copropriétaire":
                    if group.location:
                        # Specific copropriété
                        query_parts.append(
                            f"copropriete_id IN (SELECT id FROM coproprietes WHERE LOWER(nom) LIKE '%{group.location.lower()}%')"
                        )
                        description_parts.append(f"copropriétaires de {group.location}")
                    elif group.modifier == "tous":
                        # All copropriétaires
                        description_parts.append("tous les copropriétaires")
                    else:
                        description_parts.append("copropriétaires")
                elif group.type in ["chauffagiste", "plombier", "électricien", "menuisier"]:
                    # Professional lookup
                    query_parts.append(f"category = '{group.type}'")
                    description_parts.append(f"{group.type}s")

        # Build SQL query
        if entities.groups and entities.groups[0].type in ["chauffagiste", "plombier", "électricien", "menuisier", "peintre"]:
            # Query professionnels table
            table = "professionnels"
            select_fields = "name, company_name, email, phone, category"
        else:
            # Query coproprietaires table
            table = "coproprietaires"
            select_fields = "nom, prenom, email, telephone, numero_lot"

        where_clause = " AND ".join(query_parts) if query_parts else "1=1"
        sql_query = f"SELECT DISTINCT {select_fields} FROM {table} WHERE {where_clause}"

        description = "Recherche des destinataires: " + ", ".join(description_parts) if description_parts else "Recherche des destinataires"

        return ExecutionStep(
            step_type=StepType.SQL_QUERY,
            description=description,
            query=sql_query,
            requires_confirmation=False,
            estimated_results=f"{len(entities.persons) + len(entities.groups)} groupe(s) ou personne(s)"
        )

    def _create_email_draft_step(
        self,
        entities: ExtractedEntities,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> ExecutionStep:
        """Create email draft generation step"""
        # Extract email subject from action or context
        subject = "Information"
        for action in entities.actions:
            if action.subject:
                subject = action.subject
                break

        # Check context for topic
        if context and context.get("topic"):
            subject = context["topic"]

        description = f"Génération du brouillon d'email concernant '{subject}'"

        return ExecutionStep(
            step_type=StepType.EMAIL_DRAFT,
            description=description,
            requires_confirmation=True,
            estimated_results="Brouillon avec destinataires, objet et corps du message"
        )

    def _create_quote_request_step(
        self,
        entities: ExtractedEntities,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> ExecutionStep:
        """Create quote request step"""
        professions = [group.type for group in entities.groups if group.type != "copropriétaire"]
        description = f"Génération de demandes de devis pour: {', '.join(professions)}"

        return ExecutionStep(
            step_type=StepType.EMAIL_DRAFT,
            description=description,
            requires_confirmation=True,
            estimated_results="Brouillons de demandes de devis"
        )

    def _calculate_confidence(self, entities: ExtractedEntities, steps: List[ExecutionStep]) -> float:
        """Calculate confidence score for the plan"""
        confidence = 0.5  # Base confidence

        # More entities = higher confidence
        if entities.persons:
            confidence += 0.15 * min(len(entities.persons), 3)
        if entities.groups:
            confidence += 0.15
        if entities.actions:
            confidence += 0.2

        # Having a complete plan increases confidence
        if len(steps) >= 2:
            confidence += 0.1

        return min(confidence, 1.0)

    def format_plan_for_user(self, plan: ExecutionPlan) -> str:
        """
        Format execution plan as human-readable text for user confirmation

        Returns markdown-formatted plan
        """
        lines = [
            f"## 📋 Plan d'action proposé",
            f"\n**Objectif:** {plan.user_intent}",
            f"\n**Nombre d'étapes:** {plan.total_steps}",
            f"\n**Confiance:** {int(plan.confidence * 100)}%",
            "\n### Étapes:",
        ]

        for i, step in enumerate(plan.steps, 1):
            emoji = {
                StepType.SQL_QUERY: "🔍",
                StepType.EMAIL_DRAFT: "📧",
                StepType.WORKFLOW_TRIGGER: "⚡",
                StepType.CONFIRMATION: "✅"
            }.get(step.step_type, "•")

            lines.append(f"\n{i}. {emoji} **{step.description}**")

            if step.estimated_results:
                lines.append(f"   - Résultat attendu: {step.estimated_results}")

            if step.requires_confirmation:
                lines.append("   - ⚠️ Nécessite votre confirmation")

        lines.append("\n---")
        lines.append("\n**Valider ce plan?**")
        lines.append("\n- ✅ Oui, exécuter ce plan")
        lines.append("\n- ❌ Non, annuler")
        lines.append("\n- ✏️ Modifier le plan")

        return "\n".join(lines)
