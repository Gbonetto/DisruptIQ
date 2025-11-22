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
import hashlib
import json

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.core.redis_client import get_redis_client
from app.services.agents.thought_stream import ThoughtStream, ThoughtType
from app.services.legifrance_service import get_legifrance_service

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
        self.redis_client = get_redis_client()

        # Cache configuration
        self.cache_ttl = 3600 * 24 * 7  # 7 days for legal analysis
        self.cache_enabled = True

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

        # Abusive clauses database (based on French jurisprudence)
        self.abusive_clauses_patterns = [
            {
                "name": "Reconduction tacite excessive",
                "pattern": r"reconduction\s+(?:automatique|tacite)(?:.*?pour.*?(\d+)\s+(?:an|année))?",
                "severity": "critical",
                "legal_basis": "Article 1210 Code civil, Loi ALUR 2014",
                "description": "Clause de reconduction tacite sans préavis suffisant ou pour durée excessive",
                "recommendation": "Durée max 3 ans avec résiliation possible moyennant préavis 3-6 mois"
            },
            {
                "name": "Indemnité de résiliation disproportionnée",
                "pattern": r"indemn(?:ité|isation).*?r(?:é|e)siliation.*?(\d+)\s+mois",
                "severity": "high",
                "legal_basis": "Jurisprudence : clause pénale disproportionnée",
                "description": "Indemnité de résiliation excessive (jurisprudence considère > 6 mois comme abusif)",
                "recommendation": "Plafonner à 3 mois d'honoraires maximum ou supprimer"
            },
            {
                "name": "Pénalité de retard excessive",
                "pattern": r"p(?:é|e)nalit(?:é|e).*?retard.*?(\d+)\s*%",
                "severity": "medium",
                "legal_basis": "Décret 2020-1736 (taux légal + 10 points max)",
                "description": "Pénalités de retard supérieures au taux légal + 10 points",
                "recommendation": "Utiliser taux légal (actuellement ~3.4%) + max 10 points"
            },
            {
                "name": "Clause attributive de juridiction abusive",
                "pattern": r"comp(?:é|e)tence\s+exclusive.*?tribunal",
                "severity": "medium",
                "legal_basis": "Article L212-2 Code de l'organisation judiciaire",
                "description": "Clause imposant une juridiction éloignée du domicile du consommateur",
                "recommendation": "Compétence du tribunal du lieu de situation de l'immeuble"
            },
            {
                "name": "Exclusion de responsabilité illégale",
                "pattern": r"(?:exclut|exclusion).*?responsabilit(?:é|e).*?(?:toute|totale)",
                "severity": "critical",
                "legal_basis": "Article 1231-3 Code civil",
                "description": "Clause excluant totalement la responsabilité du professionnel (interdite)",
                "recommendation": "Responsabilité limitée aux fautes prouvées, jamais exclusion totale"
            },
            {
                "name": "Plafond de travaux urgents excessif",
                "pattern": r"travaux.*?urgence.*?(\d+[\s\.]?\d*)\s*(?:€|euros)",
                "severity": "high",
                "legal_basis": "Article 18 Loi 1965",
                "description": "Plafond de travaux d'urgence sans AG trop élevé (>10,000€ suspect)",
                "recommendation": "Plafond raisonnable 2,000-5,000€ selon taille copropriété"
            },
            {
                "name": "Absence de clause de résiliation",
                "pattern": r"(?!.*r(?:é|e)siliation).*dur(?:é|e)e.*?(\d+)\s+an",
                "severity": "high",
                "legal_basis": "Principe de liberté contractuelle",
                "description": "Contrat sans possibilité de résiliation pendant la durée",
                "recommendation": "Ajouter clause de résiliation avec préavis raisonnable"
            },
            {
                "name": "Modification unilatérale du contrat",
                "pattern": r"(?:modifier|modification).*?(?:unilat(?:é|e)ral|de plein droit)",
                "severity": "high",
                "legal_basis": "Article 1103 Code civil (principe consensualisme)",
                "description": "Clause permettant modification unilatérale sans accord",
                "recommendation": "Toute modification doit être acceptée par les deux parties"
            },
            {
                "name": "Tacite reconduction sans information",
                "pattern": r"tacite.*?reconduction(?!.*information|pr(?:é|e)avis)",
                "severity": "critical",
                "legal_basis": "Loi Chatel 2008",
                "description": "Reconduction tacite sans information préalable du cocontractant",
                "recommendation": "Information obligatoire 3 mois avant échéance + possibilité résiliation"
            }
        ]

        logger.info("legal_agent_initialized",
                   document_types=len(self.document_types),
                   abusive_clauses_patterns=len(self.abusive_clauses_patterns))

    async def process_request(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        db = None,
        thought_stream: Optional[ThoughtStream] = None
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
            thought_stream: Optional ThoughtStream for real-time CoT

        Returns:
            Dict with:
                - action: Action performed ("analyze", "compare", "advice", "jurisprudence")
                - result: Result from the specific action
                - success: Boolean success status
                - message: Human-readable message
        """
        try:
            logger.info("legal_request_received", query=user_input[:100])

            # Stream: Starting legal analysis
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.ANALYZING,
                    title="Analyse juridique",
                    content=f"Classification de la demande juridique : {user_input[:100]}...",
                    agent="LegalAgent",
                    progress=0.1
                )

            # Step 1: Classify the legal intent internally
            legal_intent = await self._classify_legal_intent(user_input, context)

            logger.info("legal_intent_classified",
                       intent=legal_intent["action"],
                       confidence=legal_intent["confidence"])

            # Stream: Intent classified
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.CLASSIFYING,
                    title="Intent juridique détecté",
                    content=f"Action : {legal_intent['action']}, Mode : {legal_intent.get('mode', 'N/A')}, Confiance : {legal_intent['confidence']:.0%}",
                    agent="LegalAgent",
                    data={"intent": legal_intent},
                    progress=0.2
                )

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

                # Stream: Analyzing document
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.EXECUTING,
                        title=f"Analyse de document ({analysis_mode})",
                        content=f"Analyse en cours du document ({len(document_text)} caractères)...",
                        agent="LegalAgent",
                        progress=0.3
                    )

                result = await self.analyze_document(
                    document_text=document_text,
                    analysis_type=analysis_mode,
                    thought_stream=thought_stream
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

        Enhanced with:
        - Multiple linguistic variants
        - Question vs command detection
        - Mixed requests handling
        """
        user_lower = user_input.lower()

        # Enhanced keyword sets with linguistic variants

        # Analysis keywords (extended)
        analyze_keywords = [
            # Commands
            "analyser", "analyse", "analyser ce", "analyser le", "analyser la",
            "étudier", "étude", "examiner", "examen",
            "décortiquer", "décortique",
            # Summaries
            "résume", "résumer", "résumé", "fais-moi un résumé", "faire un résumé",
            "synthèse", "synthétise", "synthétiser",
            "en bref", "l'essentiel",
            # Verification
            "identifier les risques", "vérifier", "contrôler", "vérification", "contrôle",
            "conformité", "obligations", "clauses",
            "checker", "check",
            # Extraction
            "extraire", "extraction", "lister", "liste",
            "quelles sont les clauses", "quels sont les risques"
        ]

        # Risk keywords (extended)
        risk_keywords = [
            "risque", "risques", "dangereux", "danger",
            "problème", "problèmes", "problématique",
            "red flag", "alerte", "alertes",
            "vigilance", "attention",
            "point d'attention", "points d'attention",
            "suspicious", "suspect",
            "clause abusive", "clauses abusives"
        ]

        # Summary keywords (extended)
        summary_keywords = [
            "résumé", "résume", "résumer",
            "synthèse", "synthétise", "synthétiser",
            "en bref", "l'essentiel", "principales",
            "points clés", "points importants",
            "grandes lignes", "aperçu général",
            "vue d'ensemble", "overview"
        ]

        # Compliance keywords (extended)
        compliance_keywords = [
            "conformité", "conforme", "conformes",
            "légal", "légale", "légalement",
            "réglementaire", "réglementation",
            "respect de la loi", "respecte la loi",
            "en accord avec", "selon la loi",
            "loi elan", "loi climat", "loi 1965",
            "aux normes", "norme"
        ]

        # Comparison keywords (extended)
        compare_keywords = [
            "comparer", "comparaison", "compare",
            "différence", "différences", "écart", "écarts",
            "versus", "vs", "par rapport à",
            "contraste", "opposer",
            "mettre en parallèle", "parallèle",
            "similitude", "similarités",
            "quel est le meilleur", "lequel choisir"
        ]

        # Jurisprudence keywords (extended)
        jurisprudence_keywords = [
            "jurisprudence", "jurisprudences",
            "décision de justice", "décisions de justice",
            "jugement", "jugements",
            "arrêt", "arrêts",
            "tribunal", "tribunaux",
            "cour", "cours",
            "cas similaire", "cas similaires",
            "précédent", "précédents juridiques",
            "cassation", "appel",
            "contentieux"
        ]

        # 1. Document analysis
        if any(keyword in user_lower for keyword in analyze_keywords):
            # Determine analysis mode
            mode = "full"  # Default

            if any(keyword in user_lower for keyword in risk_keywords):
                mode = "risk"
            elif any(keyword in user_lower for keyword in summary_keywords):
                mode = "summary"
            elif any(keyword in user_lower for keyword in compliance_keywords):
                mode = "compliance"

            return {"action": "analyze", "mode": mode, "confidence": 0.95}

        # 2. Document comparison
        if any(keyword in user_lower for keyword in compare_keywords):
            return {"action": "compare", "confidence": 0.90}

        # 3. Jurisprudence search
        if any(keyword in user_lower for keyword in jurisprudence_keywords):
            return {"action": "jurisprudence", "confidence": 0.95}

        # 4. Legal advice (default for legal questions)
        # Questions typically start with: quoi, comment, pourquoi, quelles, quel, est-ce que
        question_indicators = ["quoi", "comment", "pourquoi", "quelles", "quel",
                               "est-ce que", "puis-je", "peut-on", "dois-je"]

        is_question = any(user_lower.startswith(q) or f" {q} " in user_lower
                          for q in question_indicators)

        confidence = 0.80 if is_question else 0.75
        return {"action": "advice", "confidence": confidence}

    async def _detect_abusive_clauses(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect potentially abusive clauses using pattern matching and jurisprudence.

        Returns list of detected abusive clauses with:
        - name: Clause name
        - severity: critical/high/medium/low
        - legal_basis: Legal reference
        - description: Why it's problematic
        - recommendation: How to fix it
        - context: Where found in document
        """
        try:
            detected_clauses = []
            text_lower = text.lower()

            for clause_pattern in self.abusive_clauses_patterns:
                # Search for pattern
                matches = re.finditer(clause_pattern["pattern"], text_lower, re.IGNORECASE | re.DOTALL)

                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    context = text[start:end]

                    # Additional validation for numeric thresholds
                    is_abusive = True

                    # Validate indemnity amount (> 6 months is abusive)
                    if clause_pattern["name"] == "Indemnité de résiliation disproportionnée":
                        if match.groups():
                            months = int(match.group(1))
                            is_abusive = months > 6

                    # Validate penalty rate (> 13.4% is excessive given current legal rate ~3.4%)
                    elif clause_pattern["name"] == "Pénalité de retard excessive":
                        if match.groups():
                            rate = float(match.group(1))
                            is_abusive = rate > 13.4  # Legal rate + 10 points

                    # Validate urgency works ceiling (> 10,000€ is suspect)
                    elif clause_pattern["name"] == "Plafond de travaux urgents excessif":
                        if match.groups():
                            amount_str = match.group(1).replace(' ', '').replace('.', '')
                            try:
                                amount = float(amount_str)
                                is_abusive = amount > 10000
                            except ValueError:
                                is_abusive = False

                    if is_abusive:
                        detected_clauses.append({
                            "name": clause_pattern["name"],
                            "severity": clause_pattern["severity"],
                            "legal_basis": clause_pattern["legal_basis"],
                            "description": clause_pattern["description"],
                            "recommendation": clause_pattern["recommendation"],
                            "context": context,
                            "matched_text": match.group(0)
                        })

            # Deduplicate by name
            unique_clauses = []
            seen_names = set()
            for clause in detected_clauses:
                if clause["name"] not in seen_names:
                    seen_names.add(clause["name"])
                    unique_clauses.append(clause)

            logger.info("abusive_clauses_detected", count=len(unique_clauses))

            return unique_clauses

        except Exception as e:
            logger.error("abusive_clause_detection_failed", error=str(e))
            return []

    async def _extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract structured entities from legal document using NER.

        Entities extracted:
        - MONTANT: Monetary amounts (€30,000)
        - DUREE: Time periods (5 ans, 3 mois)
        - PARTIE: Parties involved (syndic, copropriétaires)
        - DATE: Dates
        - TAUX: Rates/percentages (15%)
        - CLAUSE: Specific clause types
        """
        try:
            # Regex patterns for entity extraction
            entities = {
                "montants": [],
                "durees": [],
                "parties": [],
                "dates": [],
                "taux": [],
                "clauses": []
            }

            # Extract monetary amounts
            montant_pattern = r'(\d+[\s\.]?\d*)\s*(?:€|euros?|EUR)'
            montants = re.finditer(montant_pattern, text, re.IGNORECASE)
            for match in montants:
                value_str = match.group(1).replace(' ', '').replace('.', '')
                try:
                    value = float(value_str)
                    entities["montants"].append({
                        "value": value,
                        "formatted": f"{value:,.0f} €",
                        "context": text[max(0, match.start()-50):match.end()+50]
                    })
                except ValueError:
                    pass

            # Extract time durations
            duree_pattern = r'(\d+)\s*(an(?:s|née)?|mois|jour(?:s)?|semaine(?:s)?)'
            durees = re.finditer(duree_pattern, text, re.IGNORECASE)
            for match in durees:
                number = int(match.group(1))
                unit = match.group(2).lower()
                entities["durees"].append({
                    "number": number,
                    "unit": unit,
                    "formatted": f"{number} {unit}",
                    "context": text[max(0, match.start()-50):match.end()+50]
                })

            # Extract rates/percentages
            taux_pattern = r'(\d+(?:[,\.]\d+)?)\s*%'
            taux = re.finditer(taux_pattern, text)
            for match in taux:
                rate_str = match.group(1).replace(',', '.')
                try:
                    rate = float(rate_str)
                    entities["taux"].append({
                        "value": rate,
                        "formatted": f"{rate}%",
                        "context": text[max(0, match.start()-50):match.end()+50]
                    })
                except ValueError:
                    pass

            # Extract parties (common legal entities)
            parties_keywords = [
                "syndic", "copropriétaire", "copropriétaires", "bailleur",
                "locataire", "prestataire", "entrepreneur", "architecte",
                "conseil syndical", "assemblée générale", "propriétaire"
            ]
            for keyword in parties_keywords:
                if keyword in text.lower():
                    # Find context around the party mention
                    pattern = re.compile(rf'\b{keyword}\b', re.IGNORECASE)
                    for match in pattern.finditer(text):
                        entities["parties"].append({
                            "name": keyword.title(),
                            "context": text[max(0, match.start()-50):match.end()+50]
                        })

            # Extract dates (basic patterns)
            date_pattern = r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})\b'
            dates = re.finditer(date_pattern, text, re.IGNORECASE)
            for match in dates:
                entities["dates"].append({
                    "day": match.group(1),
                    "month": match.group(2),
                    "year": match.group(3),
                    "formatted": f"{match.group(1)} {match.group(2)} {match.group(3)}",
                    "context": text[max(0, match.start()-30):match.end()+30]
                })

            # Extract specific clauses
            clause_keywords = [
                "reconduction tacite", "résiliation", "préavis",
                "indemnité", "pénalité", "clause pénale", "force majeure",
                "garantie", "assurance", "responsabilité"
            ]
            for keyword in clause_keywords:
                if keyword in text.lower():
                    pattern = re.compile(rf'\b{keyword}\b', re.IGNORECASE)
                    for match in pattern.finditer(text):
                        entities["clauses"].append({
                            "type": keyword.title(),
                            "context": text[max(0, match.start()-80):match.end()+80]
                        })

            # Deduplicate entities
            entities["montants"] = list({m["formatted"]: m for m in entities["montants"]}.values())
            entities["durees"] = list({d["formatted"]: d for d in entities["durees"]}.values())
            entities["parties"] = list({p["name"]: p for p in entities["parties"]}.values())
            entities["dates"] = list({d["formatted"]: d for d in entities["dates"]}.values())
            entities["taux"] = list({t["formatted"]: t for t in entities["taux"]}.values())
            entities["clauses"] = list({c["type"]: c for c in entities["clauses"]}.values())

            logger.info("entities_extracted",
                       montants=len(entities["montants"]),
                       durees=len(entities["durees"]),
                       parties=len(entities["parties"]))

            return entities

        except Exception as e:
            logger.error("entity_extraction_failed", error=str(e))
            return {
                "montants": [],
                "durees": [],
                "parties": [],
                "dates": [],
                "taux": [],
                "clauses": []
            }

    def _generate_cache_key(self, document_text: str, analysis_type: str) -> str:
        """
        Generate cache key from document content and analysis type.
        Uses SHA256 hash of document + analysis type for deterministic caching.
        """
        content = f"{document_text}:{analysis_type}"
        hash_digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return f"legal_analysis:{hash_digest}"

    async def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis result from Redis"""
        if not self.cache_enabled or not self.redis_client:
            return None

        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                logger.info("cache_hit", cache_key=cache_key[:20] + "...")
                return json.loads(cached)
        except Exception as e:
            logger.warning("cache_get_error", error=str(e))

        return None

    async def _set_cached_analysis(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Store analysis result in Redis cache"""
        if not self.cache_enabled or not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(result, ensure_ascii=False)
            )
            logger.info("cache_set", cache_key=cache_key[:20] + "...", ttl=self.cache_ttl)
        except Exception as e:
            logger.warning("cache_set_error", error=str(e))

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
        specific_questions: Optional[List[str]] = None,
        thought_stream: Optional[ThoughtStream] = None
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

            # Check cache first
            cache_key = self._generate_cache_key(document_text, analysis_type)
            cached_result = await self._get_cached_analysis(cache_key)

            if cached_result:
                logger.info("legal_analysis_cache_hit", analysis_type=analysis_type)
                # Add cache metadata
                cached_result["metadata"]["cached"] = True
                cached_result["metadata"]["retrieved_at"] = datetime.now().isoformat()
                return cached_result

            # Initialize result structure
            result = {
                "document_type": None,
                "summary": None,
                "key_information": {},
                "entities": {},  # NER extracted entities
                "abusive_clauses": [],  # Auto-detected abusive clauses
                "obligations": [],
                "risks": [],
                "compliance": {},
                "recommendations": [],
                "citations": [],
                "qa": [],
                "metadata": {
                    "analyzed_at": datetime.now().isoformat(),
                    "analysis_type": analysis_type,
                    "text_length": len(document_text),
                    "cached": False
                }
            }

            # Step 1: Classify document type
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Classification du document",
                    content="Identification du type de document juridique...",
                    agent="LegalAgent",
                    progress=0.4
                )
            result["document_type"] = await self._classify_legal_document(document_text)

            # Step 2: Extract entities (NER)
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Extraction des entités (NER)",
                    content="Extraction des montants, durées, parties, dates, taux...",
                    agent="LegalAgent",
                    progress=0.45
                )
            result["entities"] = await self._extract_entities(document_text)

            # Step 3: Extract key information
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Extraction des informations clés",
                    content=f"Type détecté : {self.document_types.get(result['document_type'], result['document_type'])}",
                    agent="LegalAgent",
                    progress=0.5
                )
            result["key_information"] = await self._extract_key_information(document_text, result["document_type"])

            # Step 3: Generate summary
            if analysis_type in ["full", "summary"]:
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Génération du résumé",
                        content="Synthèse des éléments principaux du document...",
                        agent="LegalAgent",
                        progress=0.6
                    )
                result["summary"] = await self._generate_summary(document_text, result["document_type"])

            # Step 4: Identify obligations
            if analysis_type in ["full", "risk"]:
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Identification des obligations",
                        content="Extraction des obligations contractuelles...",
                        agent="LegalAgent",
                        progress=0.65
                    )
                result["obligations"] = await self._extract_obligations(document_text)

            # Step 5: Detect abusive clauses (pattern-based)
            if analysis_type in ["full", "risk"]:
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Détection de clauses abusives",
                        content="Scan automatique des clauses problématiques (jurisprudence)...",
                        agent="LegalAgent",
                        progress=0.68
                    )
                result["abusive_clauses"] = await self._detect_abusive_clauses(document_text)

            # Step 6: Risk analysis (LLM-based)
            if analysis_type in ["full", "risk"]:
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Analyse des risques juridiques",
                        content="Détection des clauses problématiques et red flags...",
                        agent="LegalAgent",
                        progress=0.75
                    )
                result["risks"] = await self._analyze_risks(document_text, result["document_type"])

            # Step 7: Compliance check
            if analysis_type in ["full", "compliance"]:
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Vérification de conformité",
                        content="Contrôle par rapport aux lois ELAN, Climat, et 1965...",
                        agent="LegalAgent",
                        progress=0.80
                    )
                result["compliance"] = await self._check_compliance(document_text, result["document_type"])

            # Step 7: Generate recommendations
            if analysis_type == "full":
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Génération des recommandations",
                        content=f"{len(result['risks'])} risques identifiés, élaboration des recommandations...",
                        agent="LegalAgent",
                        progress=0.90
                    )
                result["recommendations"] = await self._generate_recommendations(
                    document_text,
                    result["document_type"],
                    result["risks"],
                    result["compliance"]
                )

            # Step 8: Identify relevant law citations
            if thought_stream:
                await thought_stream.add_thought(
                    thought_type=ThoughtType.PROCESSING,
                    title="Identification des références légales",
                    content="Recherche des lois et articles applicables...",
                    agent="LegalAgent",
                    progress=0.95
                )
            result["citations"] = await self._identify_citations(document_text)

            # Step 9: Answer specific questions if provided
            if specific_questions:
                if thought_stream:
                    await thought_stream.add_thought(
                        thought_type=ThoughtType.PROCESSING,
                        title="Réponse aux questions spécifiques",
                        content=f"Traitement de {len(specific_questions)} question(s)...",
                        agent="LegalAgent",
                        progress=0.98
                    )
                result["qa"] = await self._answer_questions(document_text, specific_questions)

            logger.info(
                "legal_analysis_completed",
                document_type=result["document_type"],
                risks_count=len(result["risks"]),
                obligations_count=len(result["obligations"])
            )

            # Stream: Analysis completed
            if thought_stream:
                abusive_count = len(result.get("abusive_clauses", []))
                abusive_msg = f", {abusive_count} clauses abusives" if abusive_count > 0 else ""
                await thought_stream.add_thought(
                    thought_type=ThoughtType.COMPLETED,
                    title="Analyse juridique terminée",
                    content=f"✅ Document analysé : {len(result['risks'])} risques, {len(result['obligations'])} obligations{abusive_msg}",
                    agent="LegalAgent",
                    data={"summary": result.get("summary", "")[:200]},
                    progress=1.0
                )

            # Cache the result
            await self._set_cached_analysis(cache_key, result)

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
        """Analyze legal risks and red flags with enhanced few-shot prompting"""
        try:
            prompt = f"""Tu es un avocat spécialisé en droit de la copropriété et droit immobilier français.

Ce document est de type : {self.document_types.get(doc_type, "document juridique")}

Identifie TOUS les risques juridiques, clauses abusives ou problématiques selon la jurisprudence française.

EXEMPLES DE RISQUES À DÉTECTER :

1. Durée excessive ou reconduction tacite :
   - Contrat > 3 ans sans justification
   - Reconduction automatique sans préavis
   - Absence de clause de résiliation

2. Clauses financières abusives :
   - Indemnités de résiliation disproportionnées (> 6 mois)
   - Pénalités de retard excessives (> taux légal + 10 points)
   - Plafonds de travaux d'urgence trop élevés

3. Déséquilibre contractuel :
   - Clause attributive de compétence abusive
   - Clause pénale disproportionnée
   - Exclusion de responsabilité illégale

4. Non-conformité réglementaire :
   - Absence d'obligations légales (loi ELAN, loi Climat)
   - Clauses contraires à l'ordre public
   - Non-respect des règles de copropriété

DOCUMENT À ANALYSER :
{text[:5000]}

Réponds UNIQUEMENT avec un JSON array strict au format suivant (pas de markdown, pas de texte avant/après) :

[
  {{
    "severity": "critical",
    "category": "temporel",
    "description": "Clause de reconduction tacite de 3 ans sans préavis minimum de 6 mois",
    "legal_reference": "Article 1210 Code civil, Loi ALUR 2014",
    "recommendation": "Exiger une durée initiale de 3 ans maximum avec résiliation à tout moment moyennant préavis de 3 mois"
  }},
  {{
    "severity": "high",
    "category": "financier",
    "description": "Indemnité de résiliation anticipée de 12 mois d'honoraires",
    "legal_reference": "Jurisprudence : clause pénale disproportionnée",
    "recommendation": "Négocier une indemnité plafonnée à 3 mois maximum ou suppression totale"
  }}
]

Severity : "low" | "medium" | "high" | "critical"
Category : "financier" | "temporel" | "responsabilité" | "conformité" | "déséquilibre" | "autre"
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,  # Plus déterministe
                max_tokens=1500  # Plus d'espace pour détails
            )

            # Parse JSON with robust error handling
            import json

            # Clean response (remove markdown code blocks if present)
            cleaned_response = response.strip()
            if cleaned_response.startswith("```"):
                # Remove markdown code fences
                cleaned_response = re.sub(r'^```(?:json)?\s*\n', '', cleaned_response)
                cleaned_response = re.sub(r'\n```\s*$', '', cleaned_response)

            try:
                risks = json.loads(cleaned_response)
                if isinstance(risks, list):
                    # Validate and enrich each risk
                    validated_risks = []
                    for risk in risks:
                        if isinstance(risk, dict) and "severity" in risk and "description" in risk:
                            # Add legal_reference if missing
                            if "legal_reference" not in risk:
                                risk["legal_reference"] = "À vérifier"
                            validated_risks.append(risk)
                    return validated_risks
                return []
            except json.JSONDecodeError:
                # Fallback: try to extract JSON array from response
                match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned_response, re.DOTALL)
                if match:
                    try:
                        risks = json.loads(match.group())
                        return risks if isinstance(risks, list) else []
                    except json.JSONDecodeError:
                        logger.warning("risks_json_parse_failed", response_preview=cleaned_response[:200])
                        return []
                else:
                    logger.warning("risks_no_json_found", response_preview=cleaned_response[:200])
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

    async def compare_multiple_legal_documents(
        self,
        documents: List[str],
        doc_names: Optional[List[str]] = None,
        comparison_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Compare 3-5 legal documents simultaneously.

        Args:
            documents: List of 3-5 document texts
            doc_names: Optional list of document names (e.g., ["Contrat A", "Contrat B", ...])
            comparison_type: Type of comparison ("general", "clauses", "risks", "pricing")

        Returns:
            Dict with:
                - success: Boolean
                - comparison_table: Matrix comparison table
                - best_document: Recommended document with justification
                - differences: List of key differences by category
                - summary: Executive summary
        """
        try:
            num_docs = len(documents)
            if num_docs < 3 or num_docs > 5:
                return {
                    "success": False,
                    "error": f"Nombre de documents invalide : {num_docs} (attendu: 3-5)",
                    "comparison_table": [],
                    "best_document": None,
                    "differences": [],
                    "summary": ""
                }

            # Generate default names if not provided
            if not doc_names:
                doc_names = [f"Document {i+1}" for i in range(num_docs)]

            logger.info("multi_document_comparison_started", count=num_docs)

            # Build comparison prompt
            docs_text = ""
            for idx, (doc, name) in enumerate(zip(documents, doc_names)):
                docs_text += f"\n\n### {name} :\n{doc[:2000]}\n"

            prompt = f"""Tu es un expert juridique spécialisé en comparaison de contrats immobiliers.

Compare ces {num_docs} documents et crée un tableau récapitulatif détaillé.

{docs_text}

Réponds en format JSON strict :
{{
  "comparison_table": [
    {{
      "criteria": "Durée du contrat",
      "{doc_names[0]}": "3 ans",
      "{doc_names[1]}": "1 an",
      {"".join([f'"{doc_names[i]}": "value",' for i in range(2, num_docs)])}
      "importance": "high"
    }}
  ],
  "best_document": {{
    "name": "{doc_names[0]}",
    "score": 8.5,
    "reasons": [
      "Durée raisonnable",
      "Pas de clause abusive",
      "Prix compétitif"
    ]
  }},
  "differences_by_category": {{
    "duree_et_resiliation": ["Différence 1", "Différence 2"],
    "conditions_financieres": ["Différence 1"],
    "obligations_parties": ["Différence 1"],
    "clauses_specifiques": ["Différence 1"]
  }},
  "summary": "Résumé en 3-4 phrases de la comparaison"
}}

IMPORTANT : Compare TOUS les aspects clés (durée, prix, clauses, obligations, résiliation, garanties)."""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000
            )

            # Parse JSON
            cleaned_response = response.strip()
            if cleaned_response.startswith("```"):
                cleaned_response = re.sub(r'^```(?:json)?\s*\n', '', cleaned_response)
                cleaned_response = re.sub(r'\n```\s*$', '', cleaned_response)

            try:
                result = json.loads(cleaned_response)

                logger.info("multi_document_comparison_completed", best_doc=result.get("best_document", {}).get("name"))

                return {
                    "success": True,
                    "comparison_table": result.get("comparison_table", []),
                    "best_document": result.get("best_document", {}),
                    "differences": result.get("differences_by_category", {}),
                    "summary": result.get("summary", ""),
                    "document_count": num_docs
                }

            except json.JSONDecodeError:
                logger.error("multi_comparison_json_parse_failed", response_preview=cleaned_response[:200])
                return {
                    "success": False,
                    "error": "Erreur de parsing JSON",
                    "comparison_table": [],
                    "best_document": None,
                    "differences": {},
                    "summary": cleaned_response[:500]
                }

        except Exception as e:
            logger.error("multi_document_comparison_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "comparison_table": [],
                "best_document": None,
                "differences": {},
                "summary": ""
            }

    async def compare_legal_documents(
        self,
        doc1: str,
        doc2: str,
        comparison_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Compare two legal documents (legacy method - use compare_multiple_legal_documents for 3+).

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

            # Multi-source jurisprudence search:
            # 1. Légifrance API (official French legal database)
            # 2. RAG (if jurisprudence documents are indexed)
            # 3. Web search (fallback/complement)

            # 1. Try Légifrance API first (if configured)
            legifrance_cases = []
            legifrance_service = get_legifrance_service()
            if legifrance_service:
                try:
                    logger.info("querying_legifrance_api")
                    legifrance_result = await legifrance_service.search_jurisprudence(
                        query=legal_question,
                        case_type=case_type,
                        max_results=5
                    )

                    if legifrance_result.get("success") and legifrance_result.get("results"):
                        legifrance_cases = [
                            {
                                "source": "Légifrance (Officiel)",
                                "title": case.get("title", ""),
                                "jurisdiction": case.get("jurisdiction", ""),
                                "date": case.get("date", ""),
                                "numero": case.get("numero", ""),
                                "excerpt": case.get("summary", "")[:400],
                                "url": case.get("url", ""),
                                "relevance": 0.95  # High relevance for official sources
                            }
                            for case in legifrance_result["results"]
                        ]
                        logger.info("legifrance_cases_found", count=len(legifrance_cases))
                except Exception as e:
                    logger.warning("legifrance_search_failed", error=str(e))
            else:
                logger.info("legifrance_not_configured", message="Add LEGIFRANCE_CLIENT_ID and LEGIFRANCE_CLIENT_SECRET to use official API")

            # 2. Try RAG (if jurisprudence documents are indexed)
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

            # Combine and format results (prioritize Légifrance)
            all_cases = legifrance_cases + rag_cases + web_cases

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

                # Additional fields for Légifrance cases
                if case.get("jurisdiction"):
                    summary_message += f"**Juridiction** : {case['jurisdiction']}\n"
                if case.get("date"):
                    summary_message += f"**Date** : {case['date']}\n"
                if case.get("numero"):
                    summary_message += f"**Numéro** : {case['numero']}\n"

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
