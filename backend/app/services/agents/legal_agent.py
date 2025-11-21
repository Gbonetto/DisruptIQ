"""
Legal Agent - Legal Document Analysis and Compliance

Specialized agent for analyzing legal documents, contracts, regulations, and
providing legal compliance guidance for property management.

Capabilities:
- Contract analysis (terms, obligations, risks)
- Regulation compliance checking (Loi ELAN, Loi Climat, etc.)
- Legal document classification
- Risk assessment and red flags detection
- Citation of relevant laws and articles

Use Cases:
- "Analyser ce contrat de syndic et identifier les risques"
- "Vérifier la conformité de ce règlement de copropriété avec la loi ELAN"
- "Quelles sont les obligations légales pour les travaux de rénovation énergétique ?"
- "Résumer les clauses importantes de ce bail commercial"

Legal Knowledge Bases:
- French property law (Loi 65-557, Loi ELAN 2018, Loi Climat 2021)
- Copropriété regulations
- Energy performance regulations
- Construction and safety codes

DISCLAIMER:
This agent provides informational guidance only. It does NOT replace professional
legal advice. Users should consult qualified legal professionals for specific cases.
"""

import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService

logger = structlog.get_logger()


class LegalAgent:
    """
    Legal Analysis Agent for property management

    Architecture:
    1. Document classification (contract, regulation, court decision, etc.)
    2. Key information extraction (parties, dates, amounts, obligations)
    3. Risk and red flag detection
    4. Compliance verification against known regulations
    5. Structured legal analysis report
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()

        # Legal document types
        self.document_types = {
            "contrat_syndic": "Contrat de syndic de copropriété",
            "contrat_travaux": "Contrat de travaux",
            "bail": "Bail d'habitation ou commercial",
            "reglement_copropriete": "Règlement de copropriété",
            "pv_ag": "Procès-verbal d'assemblée générale",
            "mise_en_demeure": "Mise en demeure",
            "decision_justice": "Décision de justice",
            "loi": "Loi ou décret",
            "autre": "Autre document juridique"
        }

        # Known French property laws and regulations
        self.legal_references = {
            "loi_1965": {
                "name": "Loi n° 65-557 du 10 juillet 1965",
                "description": "Loi fixant le statut de la copropriété des immeubles bâtis",
                "topics": ["copropriété", "assemblée générale", "syndic", "charges"]
            },
            "loi_elan_2018": {
                "name": "Loi ELAN 2018",
                "description": "Loi portant évolution du logement, de l'aménagement et du numérique",
                "topics": ["numérique", "modernisation", "compteurs individuels"]
            },
            "loi_climat_2021": {
                "name": "Loi Climat et Résilience 2021",
                "description": "Loi portant lutte contre le dérèglement climatique",
                "topics": ["rénovation énergétique", "DPE", "passoires thermiques"]
            },
            "decret_2020": {
                "name": "Décret n° 2020-834 du 2 juillet 2020",
                "description": "Décret relatif à l'individualisation des frais de chauffage",
                "topics": ["chauffage", "répartition charges", "compteurs"]
            }
        }

        logger.info("legal_agent_initialized", document_types=len(self.document_types))

    async def process_request(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        db = None
    ) -> Dict[str, Any]:
        """
        Central entry point for all legal requests.

        The LegalAgent analyzes the user's request and decides which specific
        action to perform (analyze, compare, advise, search jurisprudence).

        Architecture principle:
        - Orchestrator routes to LegalAgent (WHAT agent)
        - LegalAgent decides the action (HOW to process)

        Args:
            user_input: Raw user query
            context: Optional context (uploaded documents, etc.)
            db: Database session if needed

        Returns:
            Dict with:
                - action: Action performed ("analyze", "compare", "advice", "jurisprudence")
                - result: Result from the specific action
                - success: Boolean success status
                - message: Human-readable message
        """
        try:
            logger.info("legal_request_received", query=user_input[:100])

            # Step 1: Classify the legal intent internally
            legal_intent = await self._classify_legal_intent(user_input, context)

            logger.info("legal_intent_classified",
                       intent=legal_intent["action"],
                       confidence=legal_intent["confidence"])

            # Step 2: Route to appropriate action based on internal classification
            if legal_intent["action"] == "analyze":
                # Document analysis (full, risk, summary, compliance)
                document_text = self._extract_document_from_context(context)
                if not document_text:
                    return {
                        "action": "analyze",
                        "success": False,
                        "message": "❌ Aucun document à analyser. Veuillez uploader un document d'abord.",
                        "result": {}
                    }

                analysis_mode = legal_intent.get("mode", "full")
                result = await self.analyze_document(
                    document_text=document_text,
                    analysis_type=analysis_mode
                )

                return {
                    "action": "analyze",
                    "mode": analysis_mode,
                    "success": "error" not in result,
                    "message": self._format_analysis_result(result),
                    "result": result
                }

            elif legal_intent["action"] == "compare":
                # Document comparison
                doc1, doc2 = self._extract_two_documents_from_context(context)
                if not doc1 or not doc2:
                    return {
                        "action": "compare",
                        "success": False,
                        "message": "❌ Deux documents sont nécessaires pour la comparaison.",
                        "result": {}
                    }

                result = await self.compare_legal_documents(doc1=doc1, doc2=doc2)

                return {
                    "action": "compare",
                    "success": result.get("success", False),
                    "message": result.get("comparison", ""),
                    "result": result
                }

            elif legal_intent["action"] == "advice":
                # Legal advice/counsel
                result = await self.provide_legal_advice(
                    situation=user_input,
                    context=context or {}
                )

                return {
                    "action": "advice",
                    "success": result.get("success", False),
                    "message": result.get("advice", ""),
                    "result": result
                }

            elif legal_intent["action"] == "jurisprudence":
                # Jurisprudence search
                result = await self.search_jurisprudence(
                    legal_question=user_input,
                    case_type="copropriete"
                )

                return {
                    "action": "jurisprudence",
                    "success": result.get("success", False),
                    "message": result.get("summary", ""),
                    "result": result
                }

            else:
                # Fallback: general legal question
                return {
                    "action": "unknown",
                    "success": False,
                    "message": "❌ Je n'ai pas pu déterminer le type de demande juridique.",
                    "result": {"intent": legal_intent}
                }

        except Exception as e:
            logger.error("legal_request_processing_failed", error=str(e), exc_info=True)
            return {
                "action": "error",
                "success": False,
                "message": f"Erreur lors du traitement de la demande juridique : {str(e)}",
                "result": {}
            }

    async def _classify_legal_intent(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Internal classification of legal intent.

        Determines:
        - analyze (+ mode: full, risk, summary, compliance)
        - compare
        - advice
        - jurisprudence
        """
        user_lower = user_input.lower()

        # Quick rules for legal intent classification

        # 1. Document analysis
        if any(keyword in user_lower for keyword in [
            "analyser", "analyse", "analyser ce", "analyser le",
            "identifier les risques", "vérifier", "contrôler",
            "conformité", "obligations", "clauses"
        ]):
            # Determine analysis mode
            mode = "full"  # Default
            if "risque" in user_lower or "dangereux" in user_lower:
                mode = "risk"
            elif "résumé" in user_lower or "résume" in user_lower:
                mode = "summary"
            elif "conformité" in user_lower or "conforme" in user_lower:
                mode = "compliance"

            return {"action": "analyze", "mode": mode, "confidence": 0.9}

        # 2. Document comparison
        if any(keyword in user_lower for keyword in [
            "comparer", "comparaison", "différence", "écart",
            "versus", "vs", "par rapport"
        ]):
            return {"action": "compare", "confidence": 0.85}

        # 3. Jurisprudence search
        if any(keyword in user_lower for keyword in [
            "jurisprudence", "décision de justice", "jugement",
            "arrêt", "tribunal", "cour"
        ]):
            return {"action": "jurisprudence", "confidence": 0.9}

        # 4. Legal advice (default for legal questions)
        # If it's a legal question without specific action
        return {"action": "advice", "confidence": 0.75}

    def _extract_document_from_context(self, context: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract document text from context"""
        if not context:
            return None
        return context.get("document_text", None)

    def _extract_two_documents_from_context(self, context: Optional[Dict[str, Any]]) -> tuple:
        """Extract two documents from context for comparison"""
        if not context:
            return (None, None)
        doc1 = context.get("document1", None)
        doc2 = context.get("document2", None)
        return (doc1, doc2)

    def _format_analysis_result(self, result: Dict[str, Any]) -> str:
        """Format analysis result for human-readable message"""
        if "error" in result:
            return result["error"]

        # Build formatted message
        formatted = f"## Analyse juridique\n\n"
        formatted += f"**Type de document:** {self.document_types.get(result.get('document_type', 'autre'), 'Document juridique')}\n\n"

        if result.get("summary"):
            formatted += f"### Résumé\n{result['summary']}\n\n"

        if result.get("risks"):
            formatted += f"### Risques identifiés ({len(result['risks'])})\n"
            for risk in result["risks"][:5]:  # Top 5
                severity_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(risk.get("severity", "medium"), "⚪")
                formatted += f"{severity_emoji} **{risk.get('category', 'Risque')}**: {risk.get('description', '')}\n"
            formatted += "\n"

        if result.get("obligations"):
            formatted += f"### Obligations principales ({len(result['obligations'])})\n"
            for obligation in result["obligations"][:5]:
                formatted += f"- **{obligation.get('partie', '')}**: {obligation.get('description', '')}\n"
            formatted += "\n"

        if result.get("recommendations"):
            formatted += f"### Recommandations\n"
            for idx, rec in enumerate(result["recommendations"], 1):
                formatted += f"{idx}. {rec}\n"

        return formatted

    async def analyze_document(
        self,
        document_text: str,
        analysis_type: str = "full",
        specific_questions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a legal document

        Args:
            document_text: Full text of the legal document
            analysis_type: Type of analysis ("full", "summary", "risk", "compliance")
            specific_questions: Optional list of specific questions to answer

        Returns:
            Dict with:
                - document_type: Classified document type
                - summary: Executive summary
                - key_information: Extracted key info (parties, dates, amounts, etc.)
                - obligations: List of legal obligations
                - risks: Identified risks and red flags
                - compliance: Compliance check results
                - recommendations: Legal recommendations
                - citations: Relevant law citations
                - qa: Answers to specific questions (if provided)

        Example:
            >>> analysis = await legal_agent.analyze_document(
            ...     document_text=contract_text,
            ...     analysis_type="full"
            ... )
            >>> print(analysis["summary"])
            "Ce contrat de syndic engage la copropriété pour 3 ans..."
            >>> print(analysis["risks"])
            [
                {
                    "severity": "high",
                    "description": "Clause de reconduction tacite sans période de préavis"
                }
            ]
        """
        try:
            logger.info("legal_analysis_started", text_length=len(document_text), analysis_type=analysis_type)

            # Initialize result structure
            result = {
                "document_type": None,
                "summary": None,
                "key_information": {},
                "obligations": [],
                "risks": [],
                "compliance": {},
                "recommendations": [],
                "citations": [],
                "qa": [],
                "metadata": {
                    "analyzed_at": datetime.now().isoformat(),
                    "analysis_type": analysis_type,
                    "text_length": len(document_text)
                }
            }

            # Step 1: Classify document type
            result["document_type"] = await self._classify_legal_document(document_text)

            # Step 2: Extract key information
            result["key_information"] = await self._extract_key_information(document_text, result["document_type"])

            # Step 3: Generate summary
            if analysis_type in ["full", "summary"]:
                result["summary"] = await self._generate_summary(document_text, result["document_type"])

            # Step 4: Identify obligations
            if analysis_type in ["full", "risk"]:
                result["obligations"] = await self._extract_obligations(document_text)

            # Step 5: Risk analysis
            if analysis_type in ["full", "risk"]:
                result["risks"] = await self._analyze_risks(document_text, result["document_type"])

            # Step 6: Compliance check
            if analysis_type in ["full", "compliance"]:
                result["compliance"] = await self._check_compliance(document_text, result["document_type"])

            # Step 7: Generate recommendations
            if analysis_type == "full":
                result["recommendations"] = await self._generate_recommendations(
                    document_text,
                    result["document_type"],
                    result["risks"],
                    result["compliance"]
                )

            # Step 8: Identify relevant law citations
            result["citations"] = await self._identify_citations(document_text)

            # Step 9: Answer specific questions if provided
            if specific_questions:
                result["qa"] = await self._answer_questions(document_text, specific_questions)

            logger.info(
                "legal_analysis_completed",
                document_type=result["document_type"],
                risks_count=len(result["risks"]),
                obligations_count=len(result["obligations"])
            )

            return result

        except Exception as e:
            logger.error("legal_analysis_failed", error=str(e), exc_info=True)
            return {
                "error": f"Erreur lors de l'analyse juridique : {str(e)}",
                "metadata": {
                    "analyzed_at": datetime.now().isoformat(),
                    "analysis_type": analysis_type
                }
            }

    async def _classify_legal_document(self, text: str) -> str:
        """Classify the type of legal document"""
        try:
            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Analyse ce document et détermine son type parmi ces catégories :
{', '.join([f"{k}: {v}" for k, v in self.document_types.items()])}

DOCUMENT :
{text[:3000]}

Réponds UNIQUEMENT avec le code du type (par exemple: "contrat_syndic"). Si aucune catégorie ne correspond, réponds "autre".
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=50
            )

            doc_type = response.strip().lower()

            # Validate response
            if doc_type in self.document_types:
                return doc_type
            else:
                logger.warning("unknown_document_type", response=doc_type)
                return "autre"

        except Exception as e:
            logger.error("document_classification_failed", error=str(e))
            return "autre"

    async def _extract_key_information(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract key information from legal document"""
        try:
            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Ce document est de type : {self.document_types.get(doc_type, "document juridique")}

Extrait les informations clés suivantes au format JSON :
- parties : liste des parties au contrat/document
- dates : dates importantes (signature, début, fin, échéances)
- montants : montants et prix mentionnés
- duree : durée du contrat (si applicable)
- objet : objet principal du document
- conditions_particulieres : conditions particulières importantes

DOCUMENT :
{text[:4000]}

Réponds UNIQUEMENT avec un objet JSON valide.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=600
            )

            # Parse JSON
            import json
            try:
                info = json.loads(response)
                return info
            except json.JSONDecodeError:
                # Try to extract JSON from markdown
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    info = json.loads(match.group())
                    return info
                else:
                    logger.warning("key_info_extraction_failed_invalid_json")
                    return {}

        except Exception as e:
            logger.error("key_info_extraction_failed", error=str(e))
            return {}

    async def _generate_summary(self, text: str, doc_type: str) -> str:
        """Generate executive summary of legal document"""
        try:
            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Ce document est de type : {self.document_types.get(doc_type, "document juridique")}

Génère un résumé exécutif en 3-5 phrases qui capture :
- L'objet principal du document
- Les parties impliquées
- Les éléments essentiels (durée, montant, obligations principales)
- Les points particulièrement importants

DOCUMENT :
{text[:5000]}

Réponds avec un paragraphe clair et professionnel.
"""

            summary = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=400
            )

            return summary.strip()

        except Exception as e:
            logger.error("summary_generation_failed", error=str(e))
            return "Résumé non disponible."

    async def _extract_obligations(self, text: str) -> List[Dict[str, Any]]:
        """Extract legal obligations from document"""
        try:
            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Identifie les obligations légales et contractuelles principales dans ce document.

Pour chaque obligation, précise :
- partie : qui est concerné
- description : description de l'obligation
- echeance : échéance si mentionnée
- sanction : sanction en cas de non-respect si mentionnée

DOCUMENT :
{text[:5000]}

Réponds avec une liste JSON d'objets. Exemple :
[
  {{
    "partie": "Le syndic",
    "description": "Convoquer l'assemblée générale annuelle",
    "echeance": "Dans les 6 mois suivant la clôture des comptes",
    "sanction": "Révocation possible"
  }}
]
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=800
            )

            # Parse JSON
            import json
            try:
                obligations = json.loads(response)
                return obligations if isinstance(obligations, list) else []
            except json.JSONDecodeError:
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    obligations = json.loads(match.group())
                    return obligations if isinstance(obligations, list) else []
                else:
                    return []

        except Exception as e:
            logger.error("obligations_extraction_failed", error=str(e))
            return []

    async def _analyze_risks(self, text: str, doc_type: str) -> List[Dict[str, Any]]:
        """Analyze legal risks and red flags"""
        try:
            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Ce document est de type : {self.document_types.get(doc_type, "document juridique")}

Identifie les risques juridiques et clauses potentiellement problématiques.

Pour chaque risque :
- severity : "low", "medium", "high", "critical"
- category : catégorie du risque (financier, temporel, responsabilité, etc.)
- description : description claire du risque
- recommendation : recommandation pour atténuer le risque

DOCUMENT :
{text[:5000]}

Réponds avec une liste JSON d'objets.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1000
            )

            # Parse JSON
            import json
            try:
                risks = json.loads(response)
                return risks if isinstance(risks, list) else []
            except json.JSONDecodeError:
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    risks = json.loads(match.group())
                    return risks if isinstance(risks, list) else []
                else:
                    return []

        except Exception as e:
            logger.error("risk_analysis_failed", error=str(e))
            return []

    async def _check_compliance(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Check compliance with known regulations"""
        try:
            # Get relevant legal references for this document type
            relevant_laws = self._get_relevant_laws(doc_type)

            if not relevant_laws:
                return {
                    "status": "unknown",
                    "message": "Aucune référence légale spécifique pour ce type de document"
                }

            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Ce document est de type : {self.document_types.get(doc_type, "document juridique")}

Vérifie la conformité avec les réglementations suivantes :
{chr(10).join([f"- {law['name']}: {law['description']}" for law in relevant_laws])}

Pour chaque réglementation :
- conforme : true/false/unknown
- observations : observations sur la conformité
- articles_concernes : articles de loi concernés si identifiés

DOCUMENT :
{text[:5000]}

Réponds avec un objet JSON.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.0,
                max_tokens=800
            )

            # Parse JSON
            import json
            try:
                compliance = json.loads(response)
                return compliance
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    compliance = json.loads(match.group())
                    return compliance
                else:
                    return {"status": "error", "message": "Échec de l'analyse de conformité"}

        except Exception as e:
            logger.error("compliance_check_failed", error=str(e))
            return {"status": "error", "message": str(e)}

    def _get_relevant_laws(self, doc_type: str) -> List[Dict[str, Any]]:
        """Get relevant laws for document type"""
        # Map document types to relevant laws
        relevance_map = {
            "contrat_syndic": ["loi_1965", "loi_elan_2018"],
            "reglement_copropriete": ["loi_1965"],
            "contrat_travaux": ["loi_climat_2021"],
            "pv_ag": ["loi_1965", "loi_elan_2018"]
        }

        law_codes = relevance_map.get(doc_type, [])
        return [self.legal_references[code] for code in law_codes if code in self.legal_references]

    async def _generate_recommendations(
        self,
        text: str,
        doc_type: str,
        risks: List[Dict[str, Any]],
        compliance: Dict[str, Any]
    ) -> List[str]:
        """Generate legal recommendations based on analysis"""
        try:
            risks_summary = "\n".join([
                f"- [{risk.get('severity', 'unknown')}] {risk.get('description', '')}"
                for risk in risks[:5]  # Limit to top 5 risks
            ])

            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Basé sur l'analyse de ce document ({self.document_types.get(doc_type, 'document juridique')}), génère 3-5 recommandations juridiques concrètes et actionnables.

RISQUES IDENTIFIÉS :
{risks_summary if risks_summary else "Aucun risque majeur identifié"}

CONFORMITÉ :
{compliance.get('message', 'Non évalué')}

Génère une liste numérotée de recommandations claires et professionnelles.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=600
            )

            # Parse numbered list
            recommendations = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    clean_line = line.lstrip('0123456789.-) ').strip()
                    if clean_line:
                        recommendations.append(clean_line)

            return recommendations

        except Exception as e:
            logger.error("recommendations_generation_failed", error=str(e))
            return []

    async def _identify_citations(self, text: str) -> List[Dict[str, str]]:
        """Identify legal citations in document"""
        # Regex patterns for French law citations
        patterns = {
            "loi": r"[Ll]oi n?°?\s*(\d{2,4}[-−]\d{1,4})(?: du (\d{1,2} [a-zéû]+ \d{4}))?",
            "decret": r"[Dd]écret n?°?\s*(\d{2,4}[-−]\d{1,4})(?: du (\d{1,2} [a-zéû]+ \d{4}))?",
            "article": r"[Aa]rticle\s+([A-Z]?\d+(?:[-−][A-Z]?\d+)?)",
            "code": r"[Cc]ode (?:civil|de la construction|de l'urbanisme|de la propriété)"
        }

        citations = []
        for citation_type, pattern in patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                citations.append({
                    "type": citation_type,
                    "reference": match.group(0),
                    "context": text[max(0, match.start() - 100):min(len(text), match.end() + 100)]
                })

        # Deduplicate
        unique_citations = []
        seen = set()
        for citation in citations:
            key = f"{citation['type']}:{citation['reference']}"
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)

        return unique_citations[:10]  # Limit to 10 citations

    async def _answer_questions(
        self,
        text: str,
        questions: List[str]
    ) -> List[Dict[str, str]]:
        """Answer specific questions about the document"""
        qa_results = []

        for question in questions:
            try:
                prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Réponds à cette question en te basant UNIQUEMENT sur le document fourni.

QUESTION :
{question}

DOCUMENT :
{text[:6000]}

Réponds de manière claire, précise et professionnelle. Si l'information n'est pas dans le document, dis-le explicitement.
"""

                answer = await self.llm_service.generate_response(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=500
                )

                qa_results.append({
                    "question": question,
                    "answer": answer.strip()
                })

            except Exception as e:
                logger.error("question_answering_failed", question=question[:50], error=str(e))
                qa_results.append({
                    "question": question,
                    "answer": f"Erreur : {str(e)}"
                })

        return qa_results

    async def compare_legal_documents(
        self,
        doc1: str,
        doc2: str,
        comparison_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Compare two legal documents

        Args:
            doc1: First document text
            doc2: Second document text
            comparison_type: Type of comparison ("general", "clauses", "risks")

        Returns:
            Dict with:
                - success: Boolean
                - comparison: Formatted comparison result
                - differences: List of key differences
                - similarities: List of similarities
                - confidence: Confidence score
        """
        try:
            logger.info("legal_comparison_started", doc1_length=len(doc1), doc2_length=len(doc2))

            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Compare ces deux documents juridiques et identifie :
1. Les différences principales (clauses, conditions, montants, durées)
2. Les similitudes
3. Les points d'attention

DOCUMENT 1 :
{doc1[:4000]}

DOCUMENT 2 :
{doc2[:4000]}

Réponds en format JSON:
{{
  "differences": [
    {{"aspect": "Durée", "doc1": "3 ans", "doc2": "1 an", "importance": "high"}},
    ...
  ],
  "similarities": [
    {{"aspect": "Type de contrat", "description": "Contrat de syndic standard"}}
  ],
  "summary": "Résumé de la comparaison en 2-3 phrases"
}}
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1000
            )

            # Parse JSON
            import json
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                else:
                    result = {"differences": [], "similarities": [], "summary": response}

            # Format comparison message
            comparison_message = "## Comparaison de documents juridiques\n\n"

            if result.get("summary"):
                comparison_message += f"{result['summary']}\n\n"

            if result.get("differences"):
                comparison_message += f"### Différences principales ({len(result['differences'])})\n"
                for diff in result["differences"][:10]:
                    importance_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(diff.get("importance", "medium"), "⚪")
                    comparison_message += f"{importance_emoji} **{diff.get('aspect', '')}**\n"
                    comparison_message += f"  - Document 1: {diff.get('doc1', '')}\n"
                    comparison_message += f"  - Document 2: {diff.get('doc2', '')}\n\n"

            if result.get("similarities"):
                comparison_message += f"### Points communs ({len(result['similarities'])})\n"
                for sim in result["similarities"][:5]:
                    comparison_message += f"- **{sim.get('aspect', '')}**: {sim.get('description', '')}\n"

            logger.info("legal_comparison_completed",
                       differences_count=len(result.get("differences", [])),
                       similarities_count=len(result.get("similarities", [])))

            return {
                "success": True,
                "comparison": comparison_message,
                "differences": result.get("differences", []),
                "similarities": result.get("similarities", []),
                "confidence": 0.85
            }

        except Exception as e:
            logger.error("legal_comparison_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "comparison": f"Erreur lors de la comparaison : {str(e)}",
                "differences": [],
                "similarities": [],
                "confidence": 0.0
            }

    async def provide_legal_advice(
        self,
        situation: str,
        context: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """
        Provide legal advice based on a situation

        Args:
            situation: Description of the legal situation/question
            context: Additional context

        Returns:
            Dict with:
                - success: Boolean
                - advice: Legal advice text
                - relevant_laws: List of relevant laws
                - recommendations: List of recommendations
                - sources: List of sources (RAG + Web if needed)
                - confidence: Confidence score
        """
        try:
            logger.info("legal_advice_started", situation=situation[:100])

            # First, try to find relevant documents in RAG
            rag_sources = []
            try:
                rag_results = await self.rag_service.search_similar_chunks(
                    query=situation,
                    top_k=3
                )
                rag_sources = [
                    {
                        "type": "rag",
                        "title": chunk.get("filename", "Document"),
                        "content": chunk.get("content", "")[:300],
                        "score": chunk.get("score", 0.0)
                    }
                    for chunk in rag_results
                ]
            except Exception as e:
                logger.warning("rag_search_failed_for_legal_advice", error=str(e))

            # Build context for LLM
            context_str = ""
            if rag_sources:
                context_str = "\n\nDOCUMENTS PERTINENTS :\n"
                for idx, src in enumerate(rag_sources, 1):
                    context_str += f"{idx}. {src['title']}: {src['content']}\n"

            # Identify relevant laws
            relevant_laws = []
            situation_lower = situation.lower()
            for law_key, law_info in self.legal_references.items():
                if any(topic in situation_lower for topic in law_info["topics"]):
                    relevant_laws.append(law_info)

            laws_str = ""
            if relevant_laws:
                laws_str = "\n\nLOIS PERTINENTES :\n"
                for law in relevant_laws:
                    laws_str += f"- {law['name']}: {law['description']}\n"

            # Generate advice
            prompt = f"""Tu es un expert juridique spécialisé en droit immobilier français.

Fournis un conseil juridique professionnel et détaillé pour cette situation :

SITUATION :
{situation}
{context_str}
{laws_str}

Réponds en format JSON :
{{
  "advice": "Conseil juridique détaillé (3-5 paragraphes)",
  "key_points": [
    "Point juridique important 1",
    "Point juridique important 2"
  ],
  "recommendations": [
    "Recommandation 1",
    "Recommandation 2"
  ],
  "warnings": [
    "Mise en garde si nécessaire"
  ]
}}

IMPORTANT : Indique toujours que ce conseil est informatif et ne remplace pas l'avis d'un avocat.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1200
            )

            # Parse JSON
            import json
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                else:
                    result = {"advice": response, "key_points": [], "recommendations": [], "warnings": []}

            # Format advice message
            advice_message = "## Conseil Juridique\n\n"
            advice_message += f"{result.get('advice', '')}\n\n"

            if result.get("key_points"):
                advice_message += "### Points juridiques importants\n"
                for point in result["key_points"]:
                    advice_message += f"- {point}\n"
                advice_message += "\n"

            if result.get("recommendations"):
                advice_message += "### Recommandations\n"
                for idx, rec in enumerate(result["recommendations"], 1):
                    advice_message += f"{idx}. {rec}\n"
                advice_message += "\n"

            if result.get("warnings"):
                advice_message += "### ⚠️ Mises en garde\n"
                for warning in result["warnings"]:
                    advice_message += f"- {warning}\n"
                advice_message += "\n"

            # Add disclaimer
            advice_message += "\n---\n\n"
            advice_message += "**Disclaimer** : Ce conseil est fourni à titre informatif uniquement et ne constitue pas un avis juridique. "
            advice_message += "Pour des situations spécifiques, consultez un avocat qualifié.\n"

            logger.info("legal_advice_completed", rag_sources_count=len(rag_sources))

            return {
                "success": True,
                "advice": advice_message,
                "relevant_laws": [law["name"] for law in relevant_laws],
                "recommendations": result.get("recommendations", []),
                "sources": {
                    "rag": rag_sources,
                    "laws": relevant_laws
                },
                "confidence": 0.80
            }

        except Exception as e:
            logger.error("legal_advice_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "advice": f"Erreur lors de la génération du conseil juridique : {str(e)}",
                "relevant_laws": [],
                "recommendations": [],
                "sources": {},
                "confidence": 0.0
            }

    async def search_jurisprudence(
        self,
        legal_question: str,
        case_type: str = "copropriete"
    ) -> Dict[str, Any]:
        """
        Search for relevant jurisprudence (case law)

        Args:
            legal_question: Legal question or topic
            case_type: Type of case ("copropriete", "travaux", "general")

        Returns:
            Dict with:
                - success: Boolean
                - summary: Summary of findings
                - cases: List of relevant cases
                - confidence: Confidence score
        """
        try:
            logger.info("jurisprudence_search_started", question=legal_question[:100])

            # Note: In production, this would connect to a real jurisprudence database
            # (e.g., Légifrance API, Doctrine.fr API, or internal RAG with jurisprudence)
            # For now, we'll use a combination of RAG + Web search

            # Try RAG first (if jurisprudence documents are indexed)
            rag_cases = []
            try:
                rag_results = await self.rag_service.search_similar_chunks(
                    query=f"jurisprudence {legal_question}",
                    top_k=5
                )
                rag_cases = [
                    {
                        "source": "RAG",
                        "title": chunk.get("filename", "Document"),
                        "excerpt": chunk.get("content", "")[:400],
                        "relevance": chunk.get("score", 0.0)
                    }
                    for chunk in rag_results
                    if chunk.get("score", 0) > 0.7
                ]
            except Exception as e:
                logger.warning("rag_search_failed_for_jurisprudence", error=str(e))

            # Use Web Search as fallback/complement (if WebSearchAgent available)
            web_cases = []
            try:
                from .websearch_agent import WebSearchAgent
                web_agent = WebSearchAgent()
                web_results = await web_agent.search(
                    query=f"jurisprudence copropriété {legal_question}",
                    num_results=5,
                    region="fr-fr"
                )

                web_cases = [
                    {
                        "source": "Web",
                        "title": result.title,
                        "url": result.url,
                        "excerpt": result.snippet[:300],
                        "relevance": result.relevance_score
                    }
                    for result in web_results.results[:3]
                ]
            except Exception as e:
                logger.warning("web_search_failed_for_jurisprudence", error=str(e))

            # Combine and format results
            all_cases = rag_cases + web_cases

            if not all_cases:
                return {
                    "success": False,
                    "summary": f"Aucune jurisprudence trouvée pour : {legal_question}",
                    "cases": [],
                    "confidence": 0.0
                }

            # Generate summary
            summary_message = f"## Jurisprudence : {legal_question}\n\n"
            summary_message += f"Trouvé {len(all_cases)} cas pertinents :\n\n"

            for idx, case in enumerate(all_cases, 1):
                summary_message += f"### {idx}. {case['title']}\n"
                summary_message += f"**Source** : {case['source']}\n"
                if case.get("url"):
                    summary_message += f"**Lien** : [{case['url']}]({case['url']})\n"
                summary_message += f"**Pertinence** : {int(case['relevance']*100)}%\n"
                summary_message += f"\n{case['excerpt']}\n\n"

            logger.info("jurisprudence_search_completed", cases_found=len(all_cases))

            return {
                "success": True,
                "summary": summary_message,
                "cases": all_cases,
                "confidence": 0.75
            }

        except Exception as e:
            logger.error("jurisprudence_search_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "summary": f"Erreur lors de la recherche de jurisprudence : {str(e)}",
                "cases": [],
                "confidence": 0.0
            }

    def get_capabilities(self) -> Dict[str, Any]:
        """Get legal agent capabilities"""
        return {
            "name": "Legal Agent",
            "description": "Analyse de documents juridiques et conformité réglementaire",
            "document_types": list(self.document_types.values()),
            "legal_references": list(self.legal_references.keys()),
            "analysis_types": ["full", "summary", "risk", "compliance"],
            "capabilities": [
                "Classification de documents juridiques",
                "Extraction d'informations clés",
                "Analyse de risques juridiques",
                "Vérification de conformité réglementaire",
                "Identification d'obligations légales",
                "Citations de lois pertinentes",
                "Recommandations juridiques"
            ],
            "disclaimer": "Cet outil fournit une assistance informative uniquement. Il ne remplace pas les conseils d'un avocat qualifié."
        }
