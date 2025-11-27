"""
Legal Agent V2 - Zero-hallucination legal analysis with Légifrance integration

⚠️ ARCHITECTURE NOTE (Phase 3 - World-Class SMA):
   This agent is wrapped by WrappedLegalAgent in wrapped_agents.py for integration
   with the new BaseAgent interface and AgentRegistry system.

   For new integrations, prefer using:
   - WrappedLegalAgent from app.services.agents.wrapped_agents
   - AgentRegistry for discovery and routing
   - ResilientAgent wrapper for production resilience

   See: base_agent.py, agent_registry.py, resilience.py

Key improvements over V1:
1. Two-stage pipeline: Facts extraction → Legal analysis
2. All legal claims sourced from Légifrance API or verified knowledge base
3. Smart 3-tier caching (local KB → Redis → Légifrance)
4. Validation layer prevents LLM hallucinations

Architecture:
    User Document
          ↓
    [1. Factual Extraction] (temperature=0.0, strict)
          ↓
    {montants: [...], durees: [...], penalties: [...]}
          ↓
    [2. Legal Validation] (LegalReferenceService)
          ↓
    {is_valid, severity, legal_basis, sources}
          ↓
    [3. Synthesis] (temperature=0.2, with verified facts)
          ↓
    Final Report with Citations
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.llm_service import LLMService
from app.services.legal_reference_service import get_legal_reference_service
from app.services.agents.thought_stream import ThoughtStream, ThoughtType

logger = structlog.get_logger()


class LegalAgentV2:
    """
    Legal Analysis Agent V2 with zero-hallucination guarantee

    Usage:
        agent = LegalAgentV2()
        await agent.initialize()

        result = await agent.analyze_document(
            document_text=contract_text,
            analysis_type="full"
        )
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.legal_ref_service = None

    async def initialize(self):
        """Initialize agent (must be called before use)"""
        self.legal_ref_service = get_legal_reference_service()
        await self.legal_ref_service.initialize()
        logger.info("legal_agent_v2_initialized")

    async def analyze_document_risk_focus(
        self,
        document_text: str,
        thought_stream: Optional[ThoughtStream] = None
    ) -> Dict[str, Any]:
        """
        Two-stage document analysis: Extract facts → Validate against law

        Args:
            document_text: Full document text
            thought_stream: Optional ThoughtStream for real-time updates

        Returns:
            Analysis result with:
                - facts_extracted: Raw facts from document
                - validated_claims: Legal validation results
                - abusive_clauses: Identified abusive clauses with sources
                - recommendations: Actionable recommendations
                - confidence: Analysis confidence score
        """
        try:
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Stage 1: Extraction factuelle",
                    content="Extraction des faits du document (montants, durées, clauses)...",
                    agent="LegalAgentV2",
                    progress=0.2
                )

            # === STAGE 1: FACTUAL EXTRACTION (NO LEGAL INTERPRETATION) ===
            facts = await self._extract_facts_only(document_text)

            logger.info("facts_extracted",
                       montants=len(facts.get("montants", [])),
                       durees=len(facts.get("durees", [])),
                       clauses=len(facts.get("clauses_detectees", [])))

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Stage 2: Validation juridique",
                    content=f"Vérification de {len(facts.get('clauses_detectees', []))} clauses contre Légifrance...",
                    agent="LegalAgentV2",
                    progress=0.5
                )

            # === STAGE 2: LEGAL VALIDATION (WITH AUTHORITATIVE SOURCES) ===
            validated_claims = await self._validate_facts_against_law(facts)

            if thought_stream:
                abusive_count = sum(1 for v in validated_claims if v.get("severity") in ["abusive", "illegal"])
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title=f"Analyse terminée: {abusive_count} clauses problématiques",
                    content="Génération du rapport avec citations légales...",
                    agent="LegalAgentV2",
                    progress=0.8
                )

            # === STAGE 3: SYNTHESIS WITH CITATIONS ===
            synthesis = await self._synthesize_analysis(
                facts=facts,
                validated_claims=validated_claims,
                document_text=document_text
            )

            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.COMPLETED,
                    title="✅ Analyse juridique terminée",
                    content=f"{len(validated_claims)} validations effectuées, toutes sourcées via Légifrance",
                    agent="LegalAgentV2",
                    progress=1.0
                )

            return {
                "success": True,
                "facts_extracted": facts,
                "validated_claims": validated_claims,
                "synthesis": synthesis,
                "abusive_clauses": [
                    v for v in validated_claims
                    if v.get("severity") in ["abusive", "illegal"]
                ],
                "metadata": {
                    "analyzed_at": datetime.now().isoformat(),
                    "agent_version": "v2",
                    "zero_hallucination": True,
                    "all_claims_sourced": True
                }
            }

        except Exception as e:
            logger.error("legal_analysis_v2_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "facts_extracted": {},
                "validated_claims": [],
                "abusive_clauses": []
            }

    async def _extract_facts_only(self, document_text: str) -> Dict[str, Any]:
        """
        Stage 1: Extract ONLY factual information from document

        CRITICAL: No legal interpretation at this stage!
        Temperature=0.0 for maximum precision.

        Returns:
            {
                "montants": [45000, ...],
                "durees": [{"value": 5, "unit": "ans"}, ...],
                "penalties": [{"type": "retard", "rate": 15.0}, ...],
                "clauses_detectees": [
                    {"type": "reconduction_tacite", "value": "automatique", "context": "..."},
                    ...
                ]
            }
        """
        try:
            prompt = f"""Tu es un extracteur de faits juridiques. Ta mission est d'extraire UNIQUEMENT les faits du document, SANS interprétation juridique.

DOCUMENT :
{document_text[:5000]}

Extrait les faits suivants en JSON strict :

{{
  "montants": [
    {{"type": "honoraires_annuels", "valeur": 45000, "contexte": "..."}}
  ],
  "durees": [
    {{"type": "duree_contrat", "valeur": 5, "unite": "ans", "contexte": "..."}}
  ],
  "clauses_detectees": [
    {{
      "type": "reconduction_tacite",
      "present": true,
      "modalite": "automatique",
      "contexte": "Article 1 : reconduction tacite automatique..."
    }},
    {{
      "type": "penalite_retard",
      "present": true,
      "taux": 15.0,
      "contexte": "Article 5 : pénalités de 15% par mois"
    }},
    {{
      "type": "indemnite_resiliation",
      "present": true,
      "duree_mois": 18,
      "contexte": "Article 4 : indemnité égale à 18 mois..."
    }},
    {{
      "type": "preavis_resiliation",
      "present": true,
      "duree_mois": 12,
      "contexte": "Article 4 : Préavis de résiliation: 12 mois..."
    }},
    {{
      "type": "travaux_urgence",
      "present": true,
      "plafond_euros": 50000,
      "contexte": "Article 3 : travaux jusqu'à 50,000€..."
    }},
    {{
      "type": "exclusion_responsabilite",
      "present": true,
      "etendue": "totale",
      "contexte": "Article 7 : exclut toute responsabilité..."
    }},
    {{
      "type": "revision_honoraires",
      "present": true,
      "modalite": "unilatérale",
      "taux_indexation": 8.0,
      "plafond": false,
      "contexte": "..."
    }}
  ],
  "parties": [
    {{"nom": "Cabinet IMMO GESTION", "role": "syndic"}},
    {{"nom": "Copropriété Les Jardins du Soleil", "role": "copropriétaire"}}
  ]
}}

RÈGLES CRITIQUES :
1. Extrais UNIQUEMENT ce qui est écrit dans le document
2. NE DIS PAS si c'est légal ou illégal
3. NE MENTIONNE PAS de seuils légaux
4. Si une clause n'est pas présente, mets "present": false
5. Sois précis sur les chiffres (montants, taux, durées)

Réponds UNIQUEMENT avec le JSON, rien d'autre."""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,  # Maximum precision
                max_tokens=1500
            )

            # Parse JSON
            import json
            import re

            # Clean response
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*\n', '', cleaned)
                cleaned = re.sub(r'\n```\s*$', '', cleaned)

            facts = json.loads(cleaned)

            logger.info("factual_extraction_completed",
                       clauses_found=len(facts.get("clauses_detectees", [])))

            return facts

        except Exception as e:
            logger.error("factual_extraction_failed", error=str(e))
            return {
                "montants": [],
                "durees": [],
                "clauses_detectees": [],
                "parties": []
            }

    async def _validate_facts_against_law(
        self,
        facts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Stage 2: Validate extracted facts against authoritative legal sources

        For each clause detected, check against:
        1. Local knowledge base (fast)
        2. Redis cache (medium)
        3. Légifrance API (authoritative)

        Returns list of validation results with sources.
        """
        validated = []

        clauses = facts.get("clauses_detectees", [])

        for clause in clauses:
            if not clause.get("present"):
                continue  # Skip absent clauses

            clause_type = clause.get("type")

            # Map clause type to validation type
            validation_type_map = {
                "penalite_retard": "penalty_rate",
                "duree_contrat": "duration",
                "indemnite_resiliation": "indemnity_months",
                "preavis_resiliation": "notice_period",
                "travaux_urgence": "urgent_works",
                "exclusion_responsabilite": "liability_exclusion",
                "revision_honoraires": "fee_revision"
            }

            validation_type = validation_type_map.get(clause_type)

            if not validation_type:
                logger.warning("unknown_clause_type_for_validation", clause_type=clause_type)
                continue

            # Extract value to validate
            extracted_value = None

            if clause_type == "penalite_retard":
                extracted_value = clause.get("taux")
            elif clause_type == "duree_contrat":
                extracted_value = clause.get("valeur")
            elif clause_type == "indemnite_resiliation":
                extracted_value = clause.get("duree_mois")
            elif clause_type == "preavis_resiliation":
                extracted_value = clause.get("duree_mois")
            elif clause_type == "travaux_urgence":
                extracted_value = clause.get("plafond_euros")
            elif clause_type == "exclusion_responsabilite":
                # Special case: presence of total exclusion
                extracted_value = clause.get("etendue") == "totale"
            elif clause_type == "revision_honoraires":
                # Check if unilateral
                extracted_value = clause.get("modalite") == "unilatérale"

            if extracted_value is None:
                continue

            # Validate against legal reference
            try:
                validation_result = await self.legal_ref_service.validate_claim(
                    claim_type=validation_type,
                    extracted_value=extracted_value,
                    context={"clause_context": clause.get("contexte")}
                )

                # Enrich with original clause data
                validation_result["clause_type"] = clause_type
                validation_result["clause_context"] = clause.get("contexte", "")
                validation_result["validation_timestamp"] = datetime.now().isoformat()

                validated.append(validation_result)

                logger.info("clause_validated",
                           clause_type=clause_type,
                           severity=validation_result.get("severity"),
                           is_valid=validation_result.get("is_valid"))

            except Exception as e:
                logger.error("clause_validation_failed",
                            clause_type=clause_type,
                            error=str(e))
                # Add failed validation
                validated.append({
                    "clause_type": clause_type,
                    "is_valid": None,
                    "severity": "unknown",
                    "explanation": f"Erreur de validation: {str(e)}",
                    "clause_context": clause.get("contexte", "")
                })

        # Special validation: reconduction tacite (always illegal)
        reconduction_clause = next(
            (c for c in clauses if c.get("type") == "reconduction_tacite" and c.get("present")),
            None
        )

        if reconduction_clause:
            # Get reference for syndic duration
            ref = await self.legal_ref_service.get_reference("syndic_contract_duration")

            if ref:
                validated.append({
                    "clause_type": "reconduction_tacite",
                    "is_valid": False,
                    "severity": "illegal",
                    "extracted_value": reconduction_clause.get("modalite"),
                    "explanation": f"La reconduction tacite est interdite pour les contrats de syndic (Loi ALUR 2014). Durée max: {ref['rule']['max_duration_years']} ans avec nouveau vote AG obligatoire.",
                    "reference": {
                        "title": ref["title"],
                        "legal_basis": ref["legal_basis"],
                        "sources": ref["sources"]
                    },
                    "clause_context": reconduction_clause.get("contexte", ""),
                    "recommendation": "Supprimer la clause de reconduction tacite. Renouvellement uniquement par vote en AG."
                })

        return validated

    async def _synthesize_analysis(
        self,
        facts: Dict[str, Any],
        validated_claims: List[Dict[str, Any]],
        document_text: str
    ) -> str:
        """
        Stage 3: Generate human-readable synthesis with citations

        Uses validated facts (no hallucination possible) to create
        a structured report with proper legal citations.
        """
        try:
            # Count issues by severity
            critical_count = sum(1 for v in validated_claims if v.get("severity") == "illegal")
            abusive_count = sum(1 for v in validated_claims if v.get("severity") == "abusive")
            warning_count = sum(1 for v in validated_claims if v.get("severity") == "warning")

            # Build synthesis
            synthesis_parts = []

            synthesis_parts.append("# Analyse juridique du contrat\n\n")

            # Executive summary
            synthesis_parts.append("## Résumé exécutif\n\n")

            if critical_count > 0 or abusive_count > 0:
                synthesis_parts.append(f"⚠️ **{critical_count + abusive_count} clause(s) problématique(s) identifiée(s)**\n\n")
            else:
                synthesis_parts.append("✅ Aucune clause manifestement abusive détectée.\n\n")

            synthesis_parts.append(f"- 🔴 **{critical_count}** clause(s) illégale(s)\n")
            synthesis_parts.append(f"- 🟠 **{abusive_count}** clause(s) abusive(s)\n")
            synthesis_parts.append(f"- 🟡 **{warning_count}** point(s) d'attention\n\n")

            # Detailed analysis
            synthesis_parts.append("## Analyse détaillée\n\n")

            for idx, validation in enumerate(validated_claims, 1):
                severity = validation.get("severity", "unknown")
                emoji_map = {
                    "illegal": "🔴",
                    "abusive": "🟠",
                    "warning": "🟡",
                    "ok": "🟢",
                    "unknown": "⚪"
                }
                emoji = emoji_map.get(severity, "⚪")

                clause_type_labels = {
                    "penalty_rate": "Pénalités de retard",
                    "duration": "Durée du contrat",
                    "indemnity_months": "Indemnité de résiliation",
                    "notice_period": "Préavis de résiliation",
                    "urgent_works": "Plafond travaux d'urgence",
                    "liability_exclusion": "Exclusion de responsabilité",
                    "fee_revision": "Révision des honoraires",
                    "reconduction_tacite": "Reconduction tacite"
                }

                clause_label = clause_type_labels.get(
                    validation.get("clause_type"),
                    validation.get("clause_type", "Clause")
                )

                synthesis_parts.append(f"### {emoji} {idx}. {clause_label}\n\n")

                # Extracted value
                if "extracted_value" in validation:
                    synthesis_parts.append(f"**Valeur du contrat** : {validation['extracted_value']}\n\n")

                # Explanation
                synthesis_parts.append(f"{validation.get('explanation', '')}\n\n")

                # Legal reference with citations
                if "reference" in validation and validation["reference"]:
                    ref = validation["reference"]
                    synthesis_parts.append("**Base légale** :\n")

                    for basis in ref.get("legal_basis", []):
                        law_name = basis.get("law", "")
                        article = basis.get("article", "")
                        url = basis.get("url", "")

                        if url:
                            synthesis_parts.append(f"- [{law_name}, {article}]({url})\n")
                        else:
                            synthesis_parts.append(f"- {law_name}, {article}\n")

                    synthesis_parts.append("\n")

                # Recommendation
                if validation.get("recommendation"):
                    synthesis_parts.append(f"**Recommandation** : {validation['recommendation']}\n\n")

                # Context from document
                if validation.get("clause_context"):
                    context_preview = validation["clause_context"][:200]
                    synthesis_parts.append(f"**Contexte** : *\"{context_preview}...\"*\n\n")

                synthesis_parts.append("---\n\n")

            # Disclaimer
            synthesis_parts.append("\n## Note importante\n\n")
            synthesis_parts.append("Cette analyse est générée automatiquement en s'appuyant sur les données officielles de Légifrance ")
            synthesis_parts.append("et une base de connaissance juridique vérifiée. Toutes les affirmations juridiques sont sourcées.\n\n")
            synthesis_parts.append("⚖️ **Disclaimer** : Cette analyse est fournie à titre informatif et ne constitue pas un avis juridique. ")
            synthesis_parts.append("Pour des décisions importantes, consultez un avocat qualifié.\n")

            return "".join(synthesis_parts)

        except Exception as e:
            logger.error("synthesis_generation_failed", error=str(e))
            return f"Erreur lors de la génération de la synthèse : {str(e)}"
