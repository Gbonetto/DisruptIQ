"""
Unified Digest Agent
Phase 3.4 - World-Class SMA Architecture

Consolidated agent for all digest/summary operations:
- Daily digest (emails, interventions, échéances)
- Weekly report (activités, KPIs)
- Monthly summary (financier, AG)
- Custom period digest

Replaces fragmented digest functionality across:
- agent_resumeur_digest.py
- workflow_agent.py (digest triggers)

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

import structlog
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from app.services.agents.base_agent import (
    BaseAgent,
    AgentInput,
    AgentOutput,
    AgentCapability
)
from app.services.llm_service import LLMService

logger = structlog.get_logger()


class DigestPeriod(str, Enum):
    """Digest time periods"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class DigestSection(str, Enum):
    """Sections included in digest"""
    EMAILS = "emails"
    URGENCIES = "urgencies"
    INTERVENTIONS = "interventions"
    DOCUMENTS = "documents"
    DEADLINES = "deadlines"
    FINANCIALS = "financials"
    KPI = "kpi"
    ANOMALIES = "anomalies"


@dataclass
class DigestConfig:
    """Configuration for digest generation"""
    period: DigestPeriod = DigestPeriod.DAILY
    sections: List[DigestSection] = field(default_factory=lambda: [
        DigestSection.EMAILS,
        DigestSection.URGENCIES,
        DigestSection.INTERVENTIONS,
        DigestSection.DEADLINES
    ])
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    copropriete_ids: Optional[List[int]] = None  # Filter by buildings
    max_items_per_section: int = 10
    include_summary: bool = True
    language: str = "fr"


@dataclass
class DigestItem:
    """Single item in digest"""
    title: str
    description: str
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DigestOutput:
    """Complete digest output"""
    period: DigestPeriod
    start_date: datetime
    end_date: datetime
    summary: str
    sections: Dict[str, List[DigestItem]]
    total_items: int
    critical_items: int
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "summary": self.summary,
            "sections": {
                section: [
                    {
                        "title": item.title,
                        "description": item.description,
                        "priority": item.priority,
                        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                        "metadata": item.metadata
                    }
                    for item in items
                ]
                for section, items in self.sections.items()
            },
            "total_items": self.total_items,
            "critical_items": self.critical_items,
            "generated_at": self.generated_at.isoformat()
        }

    def to_markdown(self) -> str:
        """Convert digest to markdown format"""
        lines = []

        # Header
        period_names = {
            DigestPeriod.DAILY: "Quotidien",
            DigestPeriod.WEEKLY: "Hebdomadaire",
            DigestPeriod.MONTHLY: "Mensuel",
            DigestPeriod.CUSTOM: "Personnalisé"
        }
        lines.append(f"# Digest {period_names[self.period]}")
        lines.append(f"**Période:** {self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')}")
        lines.append(f"**Généré le:** {self.generated_at.strftime('%d/%m/%Y %H:%M')}")
        lines.append("")

        # Summary
        if self.summary:
            lines.append("## Résumé")
            lines.append(self.summary)
            lines.append("")

        # Stats
        lines.append(f"**Total:** {self.total_items} éléments")
        if self.critical_items > 0:
            lines.append(f"**Critiques:** {self.critical_items} éléments")
        lines.append("")

        # Sections
        section_names = {
            DigestSection.EMAILS.value: "Emails",
            DigestSection.URGENCIES.value: "Urgences",
            DigestSection.INTERVENTIONS.value: "Interventions",
            DigestSection.DOCUMENTS.value: "Documents",
            DigestSection.DEADLINES.value: "Échéances",
            DigestSection.FINANCIALS.value: "Finances",
            DigestSection.KPI.value: "Indicateurs",
            DigestSection.ANOMALIES.value: "Anomalies"
        }

        for section_key, items in self.sections.items():
            if items:
                section_name = section_names.get(section_key, section_key)
                lines.append(f"## {section_name}")

                for item in items:
                    priority_emoji = {
                        "low": "",
                        "medium": "",
                        "high": "⚠️",
                        "critical": "🚨"
                    }.get(item.priority, "")

                    lines.append(f"- {priority_emoji} **{item.title}**")
                    if item.description:
                        lines.append(f"  {item.description}")

                lines.append("")

        return "\n".join(lines)


class DigestAgent(BaseAgent):
    """
    Unified Digest Agent

    Generates comprehensive digests for syndic operations:
    - Daily: Emails reçus, urgences, interventions du jour
    - Weekly: Activités de la semaine, KPIs
    - Monthly: Bilan financier, préparation AG

    Usage:
        agent = DigestAgent()
        input = AgentInput(query="Génère le digest quotidien")
        output = await agent.process(input)
    """

    def __init__(self):
        super().__init__()
        self.llm_service = LLMService()

    @property
    def name(self) -> str:
        return "digest_agent"

    @property
    def description(self) -> str:
        return "Génère des digests et résumés périodiques (quotidien, hebdomadaire, mensuel)"

    @property
    def capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability.TEXT_GENERATION,
            AgentCapability.SYNTHESIS
        ]

    async def can_handle(self, query: str, context: Dict[str, Any]) -> float:
        """Determine if query is digest-related"""
        query_lower = query.lower()

        # High confidence keywords
        high_keywords = [
            "digest", "résumé quotidien", "résumé hebdomadaire",
            "résumé mensuel", "bilan", "rapport périodique",
            "récapitulatif", "synthèse de la journée",
            "synthèse de la semaine"
        ]

        for keyword in high_keywords:
            if keyword in query_lower:
                return 0.95

        # Medium confidence keywords
        medium_keywords = [
            "résumé", "synthèse", "bilan", "rapport",
            "qu'est-ce qui s'est passé", "quoi de neuf"
        ]

        for keyword in medium_keywords:
            if keyword in query_lower:
                return 0.70

        return 0.0

    async def process(self, input: AgentInput) -> AgentOutput:
        """Process digest request"""
        try:
            # Parse request to determine digest type
            config = await self._parse_request(input.query, input.context)

            # Calculate date range
            start_date, end_date = self._calculate_date_range(config)
            config.start_date = start_date
            config.end_date = end_date

            # Generate digest
            digest = await self._generate_digest(config, input)

            # Format output
            return AgentOutput(
                success=True,
                response=digest.to_markdown(),
                data=digest.to_dict(),
                confidence=0.9,
                metadata={
                    "period": config.period.value,
                    "sections": [s.value for s in config.sections],
                    "total_items": digest.total_items
                }
            )

        except Exception as e:
            logger.error("digest_generation_failed", error=str(e), exc_info=True)
            return AgentOutput(
                success=False,
                response=f"Erreur lors de la génération du digest: {str(e)}",
                confidence=0.0,
                warnings=[str(e)]
            )

    async def _parse_request(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> DigestConfig:
        """Parse query to determine digest configuration"""
        query_lower = query.lower()
        config = DigestConfig()

        # Determine period
        if any(w in query_lower for w in ["quotidien", "aujourd'hui", "journée", "daily"]):
            config.period = DigestPeriod.DAILY
            config.sections = [
                DigestSection.EMAILS,
                DigestSection.URGENCIES,
                DigestSection.INTERVENTIONS,
                DigestSection.DEADLINES
            ]
        elif any(w in query_lower for w in ["hebdomadaire", "semaine", "weekly"]):
            config.period = DigestPeriod.WEEKLY
            config.sections = [
                DigestSection.EMAILS,
                DigestSection.URGENCIES,
                DigestSection.INTERVENTIONS,
                DigestSection.DOCUMENTS,
                DigestSection.DEADLINES,
                DigestSection.KPI
            ]
        elif any(w in query_lower for w in ["mensuel", "mois", "monthly"]):
            config.period = DigestPeriod.MONTHLY
            config.sections = [
                DigestSection.EMAILS,
                DigestSection.INTERVENTIONS,
                DigestSection.DOCUMENTS,
                DigestSection.FINANCIALS,
                DigestSection.KPI,
                DigestSection.ANOMALIES
            ]

        # Check for specific sections in query
        if "email" in query_lower:
            if DigestSection.EMAILS not in config.sections:
                config.sections.append(DigestSection.EMAILS)
        if "urgence" in query_lower:
            if DigestSection.URGENCIES not in config.sections:
                config.sections.append(DigestSection.URGENCIES)
        if "financ" in query_lower or "budget" in query_lower:
            if DigestSection.FINANCIALS not in config.sections:
                config.sections.append(DigestSection.FINANCIALS)

        # Extract copropriete filter from context
        if context and "copropriete_id" in context:
            config.copropriete_ids = [context["copropriete_id"]]

        return config

    def _calculate_date_range(
        self,
        config: DigestConfig
    ) -> tuple[datetime, datetime]:
        """Calculate start and end dates for digest period"""
        now = datetime.now()
        end_date = now

        if config.period == DigestPeriod.DAILY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif config.period == DigestPeriod.WEEKLY:
            # Start of week (Monday)
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif config.period == DigestPeriod.MONTHLY:
            # Start of month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Custom - use provided dates or default to last 7 days
            start_date = config.start_date or (now - timedelta(days=7))

        return start_date, end_date

    async def _generate_digest(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> DigestOutput:
        """Generate the full digest"""
        sections: Dict[str, List[DigestItem]] = {}
        total_items = 0
        critical_items = 0

        # Fetch data for each section
        for section in config.sections:
            items = await self._fetch_section_data(section, config, input)
            sections[section.value] = items
            total_items += len(items)
            critical_items += sum(1 for item in items if item.priority == "critical")

        # Generate summary using LLM
        summary = await self._generate_summary(sections, config)

        return DigestOutput(
            period=config.period,
            start_date=config.start_date,
            end_date=config.end_date,
            summary=summary,
            sections=sections,
            total_items=total_items,
            critical_items=critical_items
        )

    async def _fetch_section_data(
        self,
        section: DigestSection,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch data for a specific digest section"""
        items = []

        try:
            if section == DigestSection.EMAILS:
                items = await self._fetch_emails(config, input)
            elif section == DigestSection.URGENCIES:
                items = await self._fetch_urgencies(config, input)
            elif section == DigestSection.INTERVENTIONS:
                items = await self._fetch_interventions(config, input)
            elif section == DigestSection.DOCUMENTS:
                items = await self._fetch_documents(config, input)
            elif section == DigestSection.DEADLINES:
                items = await self._fetch_deadlines(config, input)
            elif section == DigestSection.FINANCIALS:
                items = await self._fetch_financials(config, input)
            elif section == DigestSection.KPI:
                items = await self._fetch_kpis(config, input)
            elif section == DigestSection.ANOMALIES:
                items = await self._fetch_anomalies(config, input)

        except Exception as e:
            logger.warning(
                "digest_section_fetch_failed",
                section=section.value,
                error=str(e)
            )

        # Limit items
        return items[:config.max_items_per_section]

    async def _fetch_emails(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch email digest items"""
        items = []

        if input.db_session:
            try:
                from sqlalchemy import select, func
                from app.models.email import Email

                # Query emails in date range
                query = select(Email).where(
                    Email.received_at >= config.start_date,
                    Email.received_at <= config.end_date
                ).order_by(Email.received_at.desc()).limit(config.max_items_per_section)

                result = await input.db_session.execute(query)
                emails = result.scalars().all()

                for email in emails:
                    priority = "high" if email.urgency == "urgent" else "medium"
                    items.append(DigestItem(
                        title=email.subject or "Sans objet",
                        description=f"De: {email.sender}",
                        priority=priority,
                        timestamp=email.received_at,
                        metadata={"email_id": email.id}
                    ))

            except Exception as e:
                logger.warning("email_fetch_failed", error=str(e))

        return items

    async def _fetch_urgencies(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch urgency items (high priority emails, incidents)"""
        items = []

        if input.db_session:
            try:
                from sqlalchemy import select
                from app.models.email import Email

                # Query urgent emails
                query = select(Email).where(
                    Email.received_at >= config.start_date,
                    Email.received_at <= config.end_date,
                    Email.urgency == "urgent"
                ).order_by(Email.received_at.desc())

                result = await input.db_session.execute(query)
                emails = result.scalars().all()

                for email in emails:
                    items.append(DigestItem(
                        title=f"🚨 {email.subject or 'Urgence'}",
                        description=f"De: {email.sender}",
                        priority="critical",
                        timestamp=email.received_at,
                        metadata={"email_id": email.id, "type": "urgent_email"}
                    ))

            except Exception as e:
                logger.warning("urgency_fetch_failed", error=str(e))

        return items

    async def _fetch_interventions(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch intervention items"""
        # Placeholder - would query interventions table
        return []

    async def _fetch_documents(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch recently uploaded documents"""
        items = []

        if input.db_session:
            try:
                from sqlalchemy import select
                from app.models.document import Document

                query = select(Document).where(
                    Document.created_at >= config.start_date,
                    Document.created_at <= config.end_date
                ).order_by(Document.created_at.desc()).limit(config.max_items_per_section)

                result = await input.db_session.execute(query)
                docs = result.scalars().all()

                for doc in docs:
                    items.append(DigestItem(
                        title=doc.filename,
                        description=f"Type: {doc.doc_type or 'Non classé'}",
                        priority="low",
                        timestamp=doc.created_at,
                        metadata={"document_id": doc.id}
                    ))

            except Exception as e:
                logger.warning("document_fetch_failed", error=str(e))

        return items

    async def _fetch_deadlines(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch upcoming deadlines"""
        # Placeholder - would query calendar/tasks
        return []

    async def _fetch_financials(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch financial summary items"""
        # Placeholder - would query financial data
        return []

    async def _fetch_kpis(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch KPI summary"""
        # Placeholder - would calculate KPIs
        return []

    async def _fetch_anomalies(
        self,
        config: DigestConfig,
        input: AgentInput
    ) -> List[DigestItem]:
        """Fetch detected anomalies"""
        # Placeholder - would query anomaly detection
        return []

    async def _generate_summary(
        self,
        sections: Dict[str, List[DigestItem]],
        config: DigestConfig
    ) -> str:
        """Generate executive summary using LLM"""
        if not config.include_summary:
            return ""

        # Build context for LLM
        total_items = sum(len(items) for items in sections.values())
        critical_items = sum(
            1 for items in sections.values()
            for item in items
            if item.priority == "critical"
        )

        section_counts = {
            section: len(items)
            for section, items in sections.items()
            if items
        }

        period_name = {
            DigestPeriod.DAILY: "aujourd'hui",
            DigestPeriod.WEEKLY: "cette semaine",
            DigestPeriod.MONTHLY: "ce mois-ci"
        }.get(config.period, "cette période")

        prompt = f"""Génère un résumé exécutif court (2-3 phrases) pour un digest syndic.

Période: {period_name}
Total éléments: {total_items}
Éléments critiques: {critical_items}
Répartition: {section_counts}

Le résumé doit:
- Être concis et professionnel
- Mentionner les points d'attention si critiques > 0
- Être en français

Résumé:"""

        try:
            summary = await self.llm_service.generate_response(
                prompt,
                max_tokens=150,
                temperature=0.3
            )
            return summary.strip()
        except Exception as e:
            logger.warning("summary_generation_failed", error=str(e))
            return f"Période couverte: {period_name}. {total_items} éléments traités."

    async def generate_daily_digest(
        self,
        db_session,
        copropriete_ids: List[int] = None
    ) -> DigestOutput:
        """Convenience method for daily digest"""
        config = DigestConfig(
            period=DigestPeriod.DAILY,
            copropriete_ids=copropriete_ids
        )
        input = AgentInput(
            query="Génère le digest quotidien",
            db_session=db_session
        )
        output = await self.process(input)
        return DigestOutput(**output.data) if output.success else None

    async def generate_weekly_digest(
        self,
        db_session,
        copropriete_ids: List[int] = None
    ) -> DigestOutput:
        """Convenience method for weekly digest"""
        config = DigestConfig(
            period=DigestPeriod.WEEKLY,
            copropriete_ids=copropriete_ids
        )
        input = AgentInput(
            query="Génère le digest hebdomadaire",
            db_session=db_session
        )
        output = await self.process(input)
        return DigestOutput(**output.data) if output.success else None


# Singleton instance
_digest_agent: Optional[DigestAgent] = None


def get_digest_agent() -> DigestAgent:
    """Get or create singleton digest agent"""
    global _digest_agent
    if _digest_agent is None:
        _digest_agent = DigestAgent()
    return _digest_agent
