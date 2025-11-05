"""
Evaluator - Vérifie que les résultats respectent les règles de conformité

L'Evaluator applique des règles explicites pour garantir:
- Pas de réponse factuelle sans citation
- Pas d'envoi email sans evidence
- Preview obligatoire pour N8N si danger élevé
- Détection des conflits SQL vs RAG
"""

import structlog
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum
import re

logger = structlog.get_logger()


class RuleSeverity(str, Enum):
    """Sévérité d'une règle"""
    CRITICAL = "critical"  # Échec bloque l'exécution
    WARNING = "warning"    # Échec génère warning mais continue
    INFO = "info"          # Informatif seulement


class RuleResult(BaseModel):
    """Résultat de l'évaluation d'une règle"""
    rule_id: str = Field(..., description="ID de la règle")
    passed: bool = Field(..., description="Règle respectée ou non")
    severity: RuleSeverity = Field(..., description="Sévérité")
    message: str = Field(..., description="Message explicatif")
    evidence: Optional[Dict[str, Any]] = Field(None, description="Evidence de la violation")


class EvaluationResult(BaseModel):
    """Résultat global de l'évaluation"""
    passed: bool = Field(..., description="Toutes les règles critiques passées")
    rules_checked: int = Field(..., description="Nombre de règles vérifiées")
    rules_passed: int = Field(..., description="Nombre de règles OK")
    rules_failed: List[str] = Field(default_factory=list, description="IDs des règles échouées")
    critical_failures: int = Field(0, description="Nombre de règles critiques échouées")
    warnings: int = Field(0, description="Nombre de warnings")
    details: List[RuleResult] = Field(default_factory=list, description="Détails par règle")


class Evaluator:
    """
    Evaluator - Vérifie les règles de conformité

    Règles implémentées:
    1. RAG: Pas de phrase factuelle sans citation
    2. Email: Pas d'envoi sans evidence
    3. N8N: Preview obligatoire si danger élevé
    4. SQL: Résultats non vides et sans erreur
    5. HYBRID: Détection conflits SQL vs RAG
    6. WEB: URLs citées obligatoire
    """

    def __init__(self):
        self.rules_registry: Dict[str, callable] = {
            # RAG rules
            "rag_has_citations": self._check_rag_has_citations,
            "rag_min_sources_2": self._check_rag_min_sources,
            "rag_factual_claims_cited": self._check_rag_factual_claims_cited,

            # SQL rules
            "sql_no_error": self._check_sql_no_error,
            "sql_results_not_empty": self._check_sql_results_not_empty,
            "sql_whitelist_tables": self._check_sql_whitelist_tables,

            # Email rules
            "email_has_evidence": self._check_email_has_evidence,
            "email_preview_shown": self._check_email_preview_shown,
            "email_checklist_validated": self._check_email_checklist_validated,

            # N8N rules
            "n8n_preview_if_danger_high": self._check_n8n_preview_if_danger_high,
            "n8n_correlation_id": self._check_n8n_correlation_id,

            # Hybrid rules
            "hybrid_no_contradiction": self._check_hybrid_no_contradiction,
            "hybrid_sources_attributed": self._check_hybrid_sources_attributed,

            # Web rules
            "web_urls_cited": self._check_web_urls_cited,
        }
        logger.info("evaluator_initialized", rules_count=len(self.rules_registry))

    async def evaluate(
        self,
        rules: List[str],
        context: Dict[str, Any]
    ) -> EvaluationResult:
        """
        Évalue un ensemble de règles.

        Args:
            rules: Liste des IDs de règles à vérifier
            context: Contexte avec les données nécessaires

        Returns:
            EvaluationResult avec détails
        """
        logger.info(
            "evaluator_checking_rules",
            rules=rules,
            context_keys=list(context.keys())
        )

        results: List[RuleResult] = []
        critical_failures = 0
        warnings = 0

        for rule_id in rules:
            if rule_id not in self.rules_registry:
                logger.warning("evaluator_unknown_rule", rule_id=rule_id)
                results.append(
                    RuleResult(
                        rule_id=rule_id,
                        passed=False,
                        severity=RuleSeverity.WARNING,
                        message=f"Règle inconnue: {rule_id}"
                    )
                )
                warnings += 1
                continue

            # Exécuter la règle
            rule_func = self.rules_registry[rule_id]
            try:
                result = rule_func(context)
                results.append(result)

                if not result.passed:
                    if result.severity == RuleSeverity.CRITICAL:
                        critical_failures += 1
                    elif result.severity == RuleSeverity.WARNING:
                        warnings += 1

            except Exception as e:
                logger.error(
                    "evaluator_rule_exception",
                    rule_id=rule_id,
                    error=str(e),
                    exc_info=True
                )
                results.append(
                    RuleResult(
                        rule_id=rule_id,
                        passed=False,
                        severity=RuleSeverity.CRITICAL,
                        message=f"Erreur lors de l'évaluation: {str(e)}"
                    )
                )
                critical_failures += 1

        # Calculer le résultat global
        rules_passed = sum(1 for r in results if r.passed)
        rules_failed = [r.rule_id for r in results if not r.passed]
        overall_passed = critical_failures == 0

        evaluation = EvaluationResult(
            passed=overall_passed,
            rules_checked=len(results),
            rules_passed=rules_passed,
            rules_failed=rules_failed,
            critical_failures=critical_failures,
            warnings=warnings,
            details=results
        )

        logger.info(
            "evaluator_evaluation_complete",
            passed=overall_passed,
            rules_checked=len(results),
            rules_passed=rules_passed,
            critical_failures=critical_failures,
            warnings=warnings
        )

        return evaluation

    # =========================================================================
    # RAG RULES
    # =========================================================================

    def _check_rag_has_citations(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Réponse RAG doit avoir au moins 1 citation"""
        response = context.get("response", "")
        citations = context.get("citations", [])

        # Détecter citations inline [1][2][3]
        citation_pattern = r'\[\d+\]'
        inline_citations = re.findall(citation_pattern, response)

        has_citations = len(inline_citations) > 0 or len(citations) > 0

        return RuleResult(
            rule_id="rag_has_citations",
            passed=has_citations,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Citations présentes" if has_citations
                else "ÉCHEC: Aucune citation trouvée (règle: 0 citation → refus)"
            ),
            evidence={
                "inline_citations_count": len(inline_citations),
                "citations_array_count": len(citations)
            }
        )

    def _check_rag_min_sources(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Minimum 2 sources différentes"""
        citations = context.get("citations", [])

        # Compter les sources uniques
        unique_sources = set()
        for citation in citations:
            if isinstance(citation, dict) and "id" in citation:
                unique_sources.add(citation["id"])

        has_min_sources = len(unique_sources) >= 2

        return RuleResult(
            rule_id="rag_min_sources_2",
            passed=has_min_sources,
            severity=RuleSeverity.WARNING,
            message=(
                f"OK: {len(unique_sources)} sources uniques" if has_min_sources
                else f"WARNING: Seulement {len(unique_sources)} source(s) (recommandé: 2+)"
            ),
            evidence={"unique_sources_count": len(unique_sources)}
        )

    def _check_rag_factual_claims_cited(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Affirmations factuelles doivent être citées"""
        response = context.get("response", "")

        # Heuristique simple: détecter phrases déclaratives sans citation à proximité
        sentences = response.split(". ")
        factual_keywords = ["selon", "d'après", "le document", "indique", "précise", "stipule"]

        uncited_factual = 0
        for sentence in sentences:
            has_factual_keyword = any(kw in sentence.lower() for kw in factual_keywords)
            has_citation = re.search(r'\[\d+\]', sentence)

            if has_factual_keyword and not has_citation:
                uncited_factual += 1

        passed = uncited_factual == 0

        return RuleResult(
            rule_id="rag_factual_claims_cited",
            passed=passed,
            severity=RuleSeverity.WARNING,
            message=(
                "OK: Affirmations factuelles citées" if passed
                else f"WARNING: {uncited_factual} affirmation(s) factuelle(s) potentiellement non citée(s)"
            ),
            evidence={"uncited_factual_count": uncited_factual}
        )

    # =========================================================================
    # SQL RULES
    # =========================================================================

    def _check_sql_no_error(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Requête SQL sans erreur"""
        error = context.get("error")
        sql_result = context.get("results")

        has_error = error is not None

        return RuleResult(
            rule_id="sql_no_error",
            passed=not has_error,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Requête SQL exécutée sans erreur" if not has_error
                else f"ÉCHEC: Erreur SQL: {error}"
            ),
            evidence={"error": error}
        )

    def _check_sql_results_not_empty(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Résultats SQL non vides (optionnel selon query)"""
        results = context.get("results", [])
        query = context.get("query", "")

        is_empty = len(results) == 0

        # Certaines queries légitimes peuvent retourner 0 rows (ex: COUNT = 0)
        # Donc severity = WARNING plutôt que CRITICAL
        return RuleResult(
            rule_id="sql_results_not_empty",
            passed=not is_empty,
            severity=RuleSeverity.WARNING,
            message=(
                f"OK: {len(results)} résultat(s) retourné(s)" if not is_empty
                else "WARNING: Aucun résultat retourné (query valide mais 0 rows)"
            ),
            evidence={"row_count": len(results)}
        )

    def _check_sql_whitelist_tables(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Utilise uniquement views/tables whitelistées"""
        sql = context.get("sql", "")
        whitelist = [
            "vw_professionnels_min",
            "vw_professionnels_full",
            "vw_coproprietaires_contact",
            "vw_emails_urgents",
            "vw_coproprietes_stats",
            "vw_documents_active"
        ]

        # Extraire tables FROM/JOIN (regex simple)
        from_pattern = r'(?:FROM|JOIN)\s+([a-z_]+)'
        tables_used = re.findall(from_pattern, sql.lower())

        unauthorized_tables = [t for t in tables_used if t not in whitelist]
        passed = len(unauthorized_tables) == 0

        return RuleResult(
            rule_id="sql_whitelist_tables",
            passed=passed,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Tables whitelistées uniquement" if passed
                else f"ÉCHEC: Tables non autorisées: {unauthorized_tables}"
            ),
            evidence={
                "tables_used": tables_used,
                "unauthorized_tables": unauthorized_tables
            }
        )

    # =========================================================================
    # EMAIL RULES
    # =========================================================================

    def _check_email_has_evidence(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Email doit avoir des sources/evidence"""
        draft = context.get("draft", {})
        evidence = draft.get("evidence", []) or context.get("evidence", [])

        has_evidence = len(evidence) > 0

        return RuleResult(
            rule_id="email_has_evidence",
            passed=has_evidence,
            severity=RuleSeverity.CRITICAL,
            message=(
                f"OK: {len(evidence)} source(s) d'evidence" if has_evidence
                else "ÉCHEC: Aucune evidence (règle: 0 evidence → preview obligatoire)"
            ),
            evidence={"evidence_count": len(evidence)}
        )

    def _check_email_preview_shown(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Preview email affiché avant envoi"""
        preview_shown = context.get("preview_shown", False)

        return RuleResult(
            rule_id="email_preview_shown",
            passed=preview_shown,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Preview affiché" if preview_shown
                else "ÉCHEC: Preview non affiché (règle: preview obligatoire)"
            ),
            evidence={"preview_shown": preview_shown}
        )

    def _check_email_checklist_validated(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Checklist email validée"""
        checklist = context.get("checklist", {})
        validated = checklist.get("validated", False)

        return RuleResult(
            rule_id="email_checklist_validated",
            passed=validated,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Checklist validée" if validated
                else "ÉCHEC: Checklist non validée (règle: validation obligatoire)"
            ),
            evidence={"checklist": checklist}
        )

    # =========================================================================
    # N8N RULES
    # =========================================================================

    def _check_n8n_preview_if_danger_high(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Preview obligatoire si danger élevé"""
        danger_level = context.get("danger_level", "low")
        preview_shown = context.get("preview_shown", False)

        requires_preview = danger_level in ["high", "critical"]
        passed = not requires_preview or (requires_preview and preview_shown)

        return RuleResult(
            rule_id="n8n_preview_if_danger_high",
            passed=passed,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Preview affiché (danger élevé)" if passed and requires_preview
                else "OK: Pas de preview nécessaire (danger faible)" if passed
                else f"ÉCHEC: Preview obligatoire pour danger={danger_level}"
            ),
            evidence={
                "danger_level": danger_level,
                "preview_shown": preview_shown
            }
        )

    def _check_n8n_correlation_id(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Correlation ID présent pour traçabilité"""
        correlation_id = context.get("correlation_id")

        has_correlation_id = correlation_id is not None and len(str(correlation_id)) > 0

        return RuleResult(
            rule_id="n8n_correlation_id",
            passed=has_correlation_id,
            severity=RuleSeverity.WARNING,
            message=(
                "OK: Correlation ID présent" if has_correlation_id
                else "WARNING: Pas de correlation ID (traçabilité limitée)"
            ),
            evidence={"correlation_id": correlation_id}
        )

    # =========================================================================
    # HYBRID RULES
    # =========================================================================

    def _check_hybrid_no_contradiction(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Pas de contradictions critiques entre SQL et RAG"""
        conflicts = context.get("conflicts", [])

        # Filtrer conflits critiques/high severity
        critical_conflicts = [
            c for c in conflicts
            if isinstance(c, dict) and c.get("severity") in ["critical", "high"]
        ]

        has_critical_conflicts = len(critical_conflicts) > 0

        return RuleResult(
            rule_id="hybrid_no_contradiction",
            passed=not has_critical_conflicts,
            severity=RuleSeverity.CRITICAL,
            message=(
                "OK: Pas de contradictions critiques" if not has_critical_conflicts
                else f"ÉCHEC: {len(critical_conflicts)} contradiction(s) critique(s) détectée(s)"
            ),
            evidence={
                "total_conflicts": len(conflicts),
                "critical_conflicts": len(critical_conflicts),
                "conflicts": critical_conflicts
            }
        )

    def _check_hybrid_sources_attributed(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: Sources SQL et RAG clairement attribuées"""
        merged_response = context.get("merged_response", "")

        # Détecter marqueurs de source (SQL vs RAG)
        has_sql_marker = "sql" in merged_response.lower() or "base de données" in merged_response.lower()
        has_rag_marker = re.search(r'\[\d+\]', merged_response) is not None

        sources_attributed = has_sql_marker or has_rag_marker

        return RuleResult(
            rule_id="hybrid_sources_attributed",
            passed=sources_attributed,
            severity=RuleSeverity.WARNING,
            message=(
                "OK: Sources attribuées" if sources_attributed
                else "WARNING: Attribution sources SQL vs RAG peu claire"
            ),
            evidence={
                "has_sql_marker": has_sql_marker,
                "has_rag_marker": has_rag_marker
            }
        )

    # =========================================================================
    # WEB RULES
    # =========================================================================

    def _check_web_urls_cited(self, context: Dict[str, Any]) -> RuleResult:
        """Règle: URLs web citées obligatoire"""
        response = context.get("response", "")
        citations = context.get("citations", [])

        # Détecter URLs dans citations
        url_pattern = r'https?://[^\s\])]+'
        urls_in_citations = [
            c for c in citations
            if isinstance(c, dict) and re.search(url_pattern, str(c))
        ]

        has_url_citations = len(urls_in_citations) > 0

        return RuleResult(
            rule_id="web_urls_cited",
            passed=has_url_citations,
            severity=RuleSeverity.CRITICAL,
            message=(
                f"OK: {len(urls_in_citations)} URL(s) citée(s)" if has_url_citations
                else "ÉCHEC: Aucune URL citée (règle: citations web obligatoires)"
            ),
            evidence={"urls_cited_count": len(urls_in_citations)}
        )
