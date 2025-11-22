"""
Test E2E complet du Legal Agent et de l'Orchestrateur
Challenge l'intelligence du système avec des cas réels
"""

import asyncio
import sys
import os
import json
from typing import Dict, Any, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.orchestrator_service import OrchestratorService
from app.services.agents.legal_agent import LegalAgent
from app.services.agents.thought_stream import ThoughtStream, ThoughtType


class LegalAgentTester:
    """Testeur complet du Legal Agent avec scénarios réels"""

    def __init__(self):
        self.orchestrator = OrchestratorService()
        self.legal_agent = LegalAgent()
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

    def log_result(self, test_name: str, success: bool, details: str = "", data: Any = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        self.total_tests += 1
        if success:
            self.passed_tests += 1
            print(f"✅ {test_name}: {details}")
        else:
            self.failed_tests += 1
            print(f"❌ {test_name}: {details}")

    async def test_orchestrator_routing(self):
        """Test 1: Intelligence du routing du Legal Agent (classification interne)"""
        print("\n" + "=" * 80)
        print("TEST 1: INTELLIGENCE DE LA CLASSIFICATION INTERNE")
        print("=" * 80)
        print()

        test_queries = [
            {
                "query": "Analyse ce contrat de syndic et identifie les risques juridiques",
                "expected_action": "analyze",
                "expected_confidence": 0.75
            },
            {
                "query": "Quelle est la jurisprudence sur les assemblées générales de copropriété?",
                "expected_action": "jurisprudence",
                "expected_confidence": 0.85
            },
            {
                "query": "Résume-moi ce contrat en 3 points clés",
                "expected_action": "analyze",  # summary est un mode d'analyze
                "expected_confidence": 0.75
            },
            {
                "query": "Compare ces 3 contrats de syndic et dis-moi lequel est le plus avantageux",
                "expected_action": "compare",
                "expected_confidence": 0.85
            },
            {
                "query": "Y a-t-il des clauses abusives dans ce contrat?",
                "expected_action": "analyze",
                "expected_confidence": 0.75
            }
        ]

        for idx, test in enumerate(test_queries, 1):
            print(f"📋 Query {idx}: '{test['query']}'")

            # Test classification interne
            intent_result = await self.legal_agent._classify_legal_intent(test['query'], {})
            detected_intent = intent_result.get("action", "")  # Changed from "intent" to "action"
            confidence = intent_result.get("confidence", 0)

            print(f"   Intent détecté: {detected_intent} (confidence: {confidence:.2f})")

            if detected_intent == test['expected_action'] and confidence >= test['expected_confidence']:
                self.log_result(
                    f"Classification Query {idx}",
                    True,
                    f"Action: {detected_intent}, Confidence: {confidence:.2f}"
                )
            else:
                self.log_result(
                    f"Classification Query {idx}",
                    False,
                    f"Expected {test['expected_action']} (>={test['expected_confidence']}), got {detected_intent} ({confidence:.2f})"
                )

            print()

    async def test_legal_document_analysis(self):
        """Test 2: Analyse complète de document juridique"""
        print("\n" + "=" * 80)
        print("TEST 2: ANALYSE COMPLÈTE DE DOCUMENT JURIDIQUE")
        print("=" * 80)
        print()

        # Document de test réaliste
        test_document = """
        CONTRAT DE SYNDIC DE COPROPRIÉTÉ

        Entre la Copropriété de l'immeuble situé au 12 rue Victor Hugo, Paris 75016
        Et la Société SYNDIC PRO SARL

        Article 1 - Objet du contrat
        Le syndic s'engage à assurer la gestion de la copropriété conformément à la loi du 10 juillet 1965.

        Article 2 - Durée
        Le présent contrat est conclu pour une durée de 5 ans à compter du 1er janvier 2024.
        Il se renouvelle automatiquement par tacite reconduction pour des périodes successives de 3 ans,
        sauf dénonciation par l'une des parties avec un préavis de 6 mois.

        Article 3 - Honoraires
        Les honoraires du syndic sont fixés à 30 000 € HT par an, payables trimestriellement.
        En cas de retard de paiement, des pénalités de 20% par mois seront appliquées.

        Article 4 - Travaux d'urgence
        Le syndic est autorisé à engager sans autorisation de l'assemblée générale
        tous travaux d'urgence jusqu'à un montant de 25 000 €.

        Article 5 - Résiliation
        En cas de résiliation anticipée du contrat par le syndicat des copropriétaires,
        une indemnité forfaitaire de 10 mois d'honoraires sera due au syndic.

        Article 6 - Juridiction compétente
        Tout litige sera soumis EXCLUSIVEMENT au Tribunal de Commerce de Paris,
        sans possibilité de recours à la médiation ou à l'arbitrage.
        """

        print("📄 Document de test: Contrat de syndic avec clauses potentiellement abusives")
        print()

        # Test analyse complète
        print("🔍 Lancement de l'analyse complète...")
        result = await self.legal_agent.analyze_document(
            document_text=test_document,
            analysis_type="full"
        )

        # Vérifier que l'analyse contient tous les éléments attendus
        expected_fields = [
            "summary", "entities", "key_information", "obligations",
            "abusive_clauses", "risks", "compliance", "recommendations"
        ]

        missing_fields = [field for field in expected_fields if field not in result]

        if not missing_fields:
            self.log_result(
                "Analyse complète - Structure",
                True,
                f"Tous les champs présents: {', '.join(expected_fields)}"
            )
        else:
            self.log_result(
                "Analyse complète - Structure",
                False,
                f"Champs manquants: {', '.join(missing_fields)}"
            )

        # Vérifier détection des clauses abusives
        abusive_count = len(result.get("abusive_clauses", []))
        print(f"\n📊 Clauses abusives détectées: {abusive_count}")

        if abusive_count >= 3:  # On s'attend à au moins 3 clauses abusives
            self.log_result(
                "Détection clauses abusives",
                True,
                f"{abusive_count} clauses détectées (reconduction tacite, pénalités, indemnité résiliation, etc.)"
            )

            for idx, clause in enumerate(result["abusive_clauses"], 1):
                print(f"   {idx}. {clause.get('name', 'N/A')} - Sévérité: {clause.get('severity', 'N/A')}")
        else:
            self.log_result(
                "Détection clauses abusives",
                False,
                f"Seulement {abusive_count} clauses détectées (attendu >= 3)"
            )

        # Vérifier extraction des entités
        entities = result.get("entities", {})
        print(f"\n📊 Entités extraites:")
        print(f"   Montants: {len(entities.get('montants', []))}")
        print(f"   Durées: {len(entities.get('durees', []))}")
        print(f"   Taux: {len(entities.get('taux', []))}")
        print(f"   Parties: {len(entities.get('parties', []))}")

        if len(entities.get('montants', [])) >= 2 and len(entities.get('durees', [])) >= 1:
            self.log_result(
                "Extraction entités NER",
                True,
                f"Montants: {len(entities.get('montants', []))}, Durées: {len(entities.get('durees', []))}"
            )
        else:
            self.log_result(
                "Extraction entités NER",
                False,
                f"Extraction incomplète"
            )

        # Vérifier les recommandations
        recommendations = result.get("recommendations", [])
        if len(recommendations) >= 3:
            self.log_result(
                "Génération recommandations",
                True,
                f"{len(recommendations)} recommandations générées"
            )
        else:
            self.log_result(
                "Génération recommandations",
                False,
                f"Seulement {len(recommendations)} recommandations"
            )

    async def test_jurisprudence_search(self):
        """Test 3: Recherche de jurisprudence avec Légifrance"""
        print("\n" + "=" * 80)
        print("TEST 3: RECHERCHE JURISPRUDENCE LÉGIFRANCE")
        print("=" * 80)
        print()

        test_queries = [
            "assemblée générale copropriété",
            "clause abusive syndic",
            "résiliation contrat copropriété"
        ]

        for query in test_queries:
            print(f"🔍 Recherche: '{query}'")

            result = await self.legal_agent.search_jurisprudence(
                legal_question=query,
                case_type="copropriete"
            )

            if result.get("success") and len(result.get("cases", [])) > 0:
                self.log_result(
                    f"Jurisprudence '{query}'",
                    True,
                    f"{len(result.get('cases', []))} cas trouvés"
                )

                # Afficher les résultats
                for idx, case in enumerate(result.get("cases", [])[:2], 1):
                    print(f"   {idx}. {case.get('title', 'N/A')[:80]}")
            else:
                self.log_result(
                    f"Jurisprudence '{query}'",
                    False,
                    f"Aucun résultat: {result.get('summary', 'N/A')}"
                )

            print()

    async def test_multi_document_comparison(self):
        """Test 4: Comparaison de multiples documents"""
        print("\n" + "=" * 80)
        print("TEST 4: COMPARAISON MULTI-DOCUMENTS")
        print("=" * 80)
        print()

        # 3 contrats avec différences notables
        doc1 = """
        Contrat Syndic A
        Durée: 3 ans
        Honoraires: 25,000€/an
        Travaux urgence: 5,000€
        Résiliation: 3 mois de préavis
        """

        doc2 = """
        Contrat Syndic B
        Durée: 1 an renouvelable
        Honoraires: 30,000€/an
        Travaux urgence: 10,000€
        Résiliation: 6 mois de préavis + indemnité 5 mois
        """

        doc3 = """
        Contrat Syndic C
        Durée: 5 ans avec reconduction tacite
        Honoraires: 28,000€/an
        Travaux urgence: 15,000€
        Résiliation: 1 an de préavis + indemnité 8 mois
        """

        print("📄 Comparaison de 3 contrats de syndic...")

        result = await self.legal_agent.compare_multiple_legal_documents(
            documents=[doc1, doc2, doc3],
            doc_names=["Contrat A", "Contrat B", "Contrat C"]
        )

        # Vérifier la structure de la réponse
        if "comparison_table" in result and "best_document" in result:
            self.log_result(
                "Comparaison structure",
                True,
                f"Tableau de comparaison et recommandation présents"
            )

            # Afficher la recommandation
            best = result.get("best_document")
            if best and isinstance(best, dict):
                print(f"\n🏆 Meilleur contrat: {best.get('name', 'N/A')}")
                print(f"   Score: {best.get('score', 0)}/10")
                print(f"   Raisons: {', '.join(best.get('reasons', [])[:3])}")
            else:
                print(f"\n⚠️  Recommandation non disponible (parsing JSON échoué)")
        else:
            self.log_result(
                "Comparaison structure",
                False,
                "Structure de réponse incomplète"
            )

    async def test_streaming_sse(self):
        """Test 5: Streaming SSE et Chain of Thought"""
        print("\n" + "=" * 80)
        print("TEST 5: STREAMING SSE ET CHAIN OF THOUGHT")
        print("=" * 80)
        print()

        thought_stream = ThoughtStream()
        thoughts_received = []

        # Callback pour capturer les thoughts
        def capture_thought(thought):
            thoughts_received.append(thought)
            print(f"💭 [{thought.get('progress', 0):.0%}] {thought.get('title', 'N/A')}")

        # Mock du callback
        original_send = thought_stream.send_thought

        async def mock_send(thought):
            capture_thought(thought)
            # Don't actually send over SSE in tests

        thought_stream.send_thought = mock_send

        # Document simple pour test
        test_doc = """
        Contrat de syndic
        Durée: 3 ans
        Honoraires: 20,000€
        """

        print("🔍 Analyse avec streaming SSE...")
        result = await self.legal_agent.analyze_document(
            document_text=test_doc,
            analysis_type="full",
            thought_stream=thought_stream
        )

        # Vérifier qu'on a reçu des thoughts
        if len(thoughts_received) >= 10:  # On s'attend à ~14 événements
            self.log_result(
                "SSE Streaming",
                True,
                f"{len(thoughts_received)} événements SSE reçus"
            )
        else:
            self.log_result(
                "SSE Streaming",
                False,
                f"Seulement {len(thoughts_received)} événements (attendu >= 10)"
            )

    async def test_classification_accuracy(self):
        """Test 6: Précision de la classification d'intent"""
        print("\n" + "=" * 80)
        print("TEST 6: PRÉCISION CLASSIFICATION D'INTENT")
        print("=" * 80)
        print()

        test_cases = [
            {
                "query": "Résume ce contrat en 3 points",
                "expected_mode": "summary",
                "expected_confidence": 0.85
            },
            {
                "query": "Quels sont les risques juridiques de ce contrat?",
                "expected_mode": "risk",
                "expected_confidence": 0.90
            },
            {
                "query": "Ce contrat est-il conforme à la loi ALUR?",
                "expected_mode": "compliance",
                "expected_confidence": 0.85
            },
            {
                "query": "Analyse complète de ce document juridique",
                "expected_mode": "full",
                "expected_confidence": 0.90
            },
            {
                "query": "Compare ces deux contrats",
                "expected_mode": "compare",
                "expected_confidence": 0.95
            }
        ]

        for idx, test in enumerate(test_cases, 1):
            print(f"📋 Test {idx}: '{test['query']}'")

            # Classification interne
            intent_result = await self.legal_agent._classify_legal_intent(test['query'], {})

            mode = intent_result.get("action", "")  # Changed from "intent" to "action"
            confidence = intent_result.get("confidence", 0)

            print(f"   Mode détecté: {mode} (confidence: {confidence:.2f})")

            if mode == test['expected_mode'] and confidence >= test['expected_confidence']:
                self.log_result(
                    f"Classification {idx}",
                    True,
                    f"Mode: {mode}, Confidence: {confidence:.2f}"
                )
            else:
                self.log_result(
                    f"Classification {idx}",
                    False,
                    f"Expected {test['expected_mode']}, got {mode} (confidence: {confidence:.2f})"
                )

            print()

    async def test_error_handling(self):
        """Test 7: Gestion d'erreurs et cas limites"""
        print("\n" + "=" * 80)
        print("TEST 7: GESTION D'ERREURS ET CAS LIMITES")
        print("=" * 80)
        print()

        # Test document vide
        print("📋 Test 1: Document vide")
        result = await self.legal_agent.analyze_document(
            document_text="",
            document_name="Empty Doc",
            analysis_type="full"
        )

        if "error" in result or not result.get("summary"):
            self.log_result(
                "Gestion document vide",
                True,
                "Erreur ou réponse vide gérée correctement"
            )
        else:
            self.log_result(
                "Gestion document vide",
                False,
                "Devrait gérer le document vide"
            )

        # Test query vide pour jurisprudence
        print("\n📋 Test 2: Query vide pour jurisprudence")
        result = await self.legal_agent.search_jurisprudence(legal_question="", case_type="copropriete")

        if not result.get("success") or result.get("total", 0) == 0:
            self.log_result(
                "Gestion query vide",
                True,
                "Query vide gérée correctement"
            )
        else:
            self.log_result(
                "Gestion query vide",
                False,
                "Devrait gérer la query vide"
            )

    def print_summary(self):
        """Afficher le résumé des tests"""
        print("\n" + "=" * 80)
        print("RÉSUMÉ DES TESTS E2E - LEGAL AGENT & ORCHESTRATOR")
        print("=" * 80)
        print()

        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0

        print(f"📊 Tests exécutés:  {self.total_tests}")
        print(f"✅ Tests réussis:   {self.passed_tests} ({success_rate:.1f}%)")
        print(f"❌ Tests échoués:   {self.failed_tests}")
        print()

        # Catégories de tests
        print("📋 Par catégorie:")
        categories = {}
        for result in self.results:
            category = result["test"].split(" ")[0]
            if category not in categories:
                categories[category] = {"passed": 0, "failed": 0}
            if result["success"]:
                categories[category]["passed"] += 1
            else:
                categories[category]["failed"] += 1

        for category, stats in categories.items():
            total = stats["passed"] + stats["failed"]
            rate = (stats["passed"] / total * 100) if total > 0 else 0
            print(f"   {category}: {stats['passed']}/{total} ({rate:.0f}%)")

        print()
        print("=" * 80)

        if success_rate >= 80:
            print("✅ SYSTÈME OPÉRATIONNEL - Taux de réussite excellent!")
        elif success_rate >= 60:
            print("⚠️  SYSTÈME FONCTIONNEL - Améliorations possibles")
        else:
            print("❌ SYSTÈME NÉCESSITE DES CORRECTIONS")

        print("=" * 80)
        print()

        # Sauvegarder les résultats
        with open("test_legal_agent_e2e_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": self.total_tests,
                    "passed": self.passed_tests,
                    "failed": self.failed_tests,
                    "success_rate": success_rate
                },
                "results": self.results
            }, f, indent=2, ensure_ascii=False)

        print("💾 Résultats sauvegardés dans: test_legal_agent_e2e_results.json")
        print()


async def main():
    """Execute all tests"""
    print("\n" + "=" * 80)
    print("🧪 TEST E2E COMPLET - LEGAL AGENT & ORCHESTRATEUR")
    print("Challenge de l'intelligence et fiabilité du système")
    print("=" * 80)
    print()

    tester = LegalAgentTester()

    try:
        # Test 1: Routing
        await tester.test_orchestrator_routing()

        # Test 2: Analyse de document
        await tester.test_legal_document_analysis()

        # Test 3: Jurisprudence
        await tester.test_jurisprudence_search()

        # Test 4: Comparaison multi-docs
        await tester.test_multi_document_comparison()

        # Test 5: SSE Streaming
        await tester.test_streaming_sse()

        # Test 6: Classification
        await tester.test_classification_accuracy()

        # Test 7: Gestion d'erreurs
        await tester.test_error_handling()

    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Toujours afficher le résumé
        tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
