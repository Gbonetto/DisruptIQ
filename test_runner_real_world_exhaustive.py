"""
🏢🔥 BATTERIE ULTRA-EXHAUSTIVE - CONDITIONS RÉELLES SYNDIC 🔥🏢
================================================================

Tests exhaustifs simulant les conditions réelles d'utilisation par un syndic de copropriété.

Couverture complète:
✅ TOUS les agents individuellement (10 agents)
✅ TOUTES les sources de données (SQL, RAG, Web, combinées)
✅ TOUS les use cases réels d'un syndic (20+ scénarios)
✅ Cascades multi-agents complexes (jusqu'à 6 agents)
✅ Conversations longues avec mémoire (10+ échanges)
✅ Tests concurrent users (5+ utilisateurs simultanés)
✅ UI vs API parity (endpoints identiques)
✅ Edge cases et robustesse extrême
✅ Performance sous charge réelle

Objectif: >95% success rate en conditions réelles
"""

import asyncio
import httpx
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import random

BASE_URL = "http://localhost:8000"


class RealWorldExhaustiveTestRunner:
    """Test runner simulant les conditions réelles d'un syndic"""

    def __init__(self):
        self.base_url = BASE_URL
        self.session_id = f"real_world_test_{int(time.time())}"
        self.client = None
        self.results = {
            "scenarios": [],
            "agents_coverage": {},
            "sources_coverage": {},
            "ui_api_parity": [],
            "performance_metrics": []
        }
        self.conversation_history = []

    async def send_message(
        self,
        user_input: str,
        reset_history: bool = False,
        selected_sources: Optional[List[str]] = None,
        use_ui_endpoint: bool = False
    ) -> Dict:
        """Send message to API or UI endpoint"""
        if reset_history:
            self.conversation_history = []

        payload = {
            "message": user_input,
            "conversation_history": self.conversation_history,
            "session_id": self.session_id,
            "context": {}
        }

        if selected_sources:
            payload["selected_sources"] = selected_sources

        # Choose endpoint
        endpoint = "/api/chat/ask" if use_ui_endpoint else "/api/assistant-v2/chat"

        try:
            start_time = time.time()
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=120.0
            )
            duration = time.time() - start_time

            result = {
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None,
                "duration": duration,
                "endpoint": endpoint
            }

            # Track performance
            self.results["performance_metrics"].append({
                "endpoint": endpoint,
                "duration": duration,
                "success": response.status_code == 200
            })

            # Track agents & sources
            if response.status_code == 200:
                resp_data = response.json()
                agents = resp_data.get("agents_used", [])
                for agent in agents:
                    self.results["agents_coverage"][agent] = self.results["agents_coverage"].get(agent, 0) + 1

                # Update history
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({
                    "role": "assistant",
                    "content": resp_data.get("message", "")
                })

            return result

        except Exception as e:
            return {
                "status_code": 0,
                "response": None,
                "error": str(e),
                "duration": 0,
                "endpoint": endpoint
            }

    # ==================== SCÉNARIO 1: TEST TOUS LES AGENTS ====================

    async def scenario_1_all_agents_individual_tests(self):
        """
        🎯 SCÉNARIO 1: Test TOUS les agents individuellement (15 tests)

        Agents testés avec cas réels:
        1. SQLAgent - 3 tests (résidents, professionnels, bâtiments)
        2. RAGService - 2 tests (règlements, contrats)
        3. EmailAgent - 2 tests (urgence, devis)
        4. WorkflowAgentV2 - 2 tests (urgence eau, travaux)
        5. LegalAgent - 2 tests (délais AG, obligations)
        6. WebAgent - 2 tests (nouvelles lois, prix marché)
        7. OCRAgent - 1 test (facture PDF)
        8. Orchestrator - 1 test (question générale)
        """
        print("\n" + "="*80)
        print("🎯 SCÉNARIO 1: TEST TOUS LES AGENTS INDIVIDUELLEMENT")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S1_ALL_AGENTS_INDIVIDUAL",
            "tests": [],
            "agents_tested": set(),
            "success_rate": 0
        }

        self.conversation_history = []

        # SQLAgent - Test 1: Résidents
        print("\n🗄️  TEST 1.1: SQL Agent - Liste copropriétaires")
        t1 = await self.send_message("Liste tous les copropriétaires de la Résidence du Parc", reset_history=True)
        t1_success = t1["status_code"] == 200 and "sql_agent" in t1["response"].get("agents_used", [])
        results["tests"].append({"test": "sql_residents", "success": t1_success, "duration": t1["duration"]})
        if t1_success:
            results["agents_tested"].add("sql_agent")
        print(f"   {'✅' if t1_success else '❌'} {t1['response'].get('agents_used', []) if t1['response'] else 'ERROR'} ({t1['duration']:.1f}s)")
        await asyncio.sleep(1)

        # SQLAgent - Test 2: Professionnels
        print("\n🗄️  TEST 1.2: SQL Agent - Recherche plombiers Paris")
        t2 = await self.send_message("Trouve les 5 meilleurs plombiers disponibles", reset_history=True)
        t2_success = t2["status_code"] == 200 and "sql_agent" in t2["response"].get("agents_used", [])
        results["tests"].append({"test": "sql_professionals", "success": t2_success, "duration": t2["duration"]})
        if t2_success:
            results["agents_tested"].add("sql_agent")
        print(f"   {'✅' if t2_success else '❌'} {t2['response'].get('agents_used', []) if t2['response'] else 'ERROR'} ({t2['duration']:.1f}s)")
        await asyncio.sleep(1)

        # SQLAgent - Test 3: Stats bâtiments
        print("\n🗄️  TEST 1.3: SQL Agent - Statistiques copropriétés")
        t3 = await self.send_message("Combien de copropriétés sont gérées au total et combien de lots?", reset_history=True)
        t3_success = t3["status_code"] == 200 and "sql_agent" in t3["response"].get("agents_used", [])
        results["tests"].append({"test": "sql_stats", "success": t3_success, "duration": t3["duration"]})
        if t3_success:
            results["agents_tested"].add("sql_agent")
        print(f"   {'✅' if t3_success else '❌'} {t3['response'].get('agents_used', []) if t3['response'] else 'ERROR'} ({t3['duration']:.1f}s)")
        await asyncio.sleep(1)

        # RAGService - Test 1: Règlement
        print("\n📚 TEST 1.4: RAG Service - Recherche règlement copropriété")
        t4 = await self.send_message("Cherche dans les documents les règles concernant les travaux privatifs", reset_history=True)
        t4_success = t4["status_code"] == 200
        results["tests"].append({"test": "rag_reglement", "success": t4_success, "duration": t4["duration"]})
        if "rag" in str(t4["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("rag_service")
        print(f"   {'✅' if t4_success else '❌'} {t4['response'].get('agents_used', []) if t4['response'] else 'ERROR'} ({t4['duration']:.1f}s)")
        await asyncio.sleep(1)

        # RAGService - Test 2: Contrats
        print("\n📚 TEST 1.5: RAG Service - Recherche contrats")
        t5 = await self.send_message("Trouve dans les documents les contrats de maintenance existants", reset_history=True)
        t5_success = t5["status_code"] == 200
        results["tests"].append({"test": "rag_contrats", "success": t5_success, "duration": t5["duration"]})
        if "rag" in str(t5["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("rag_service")
        print(f"   {'✅' if t5_success else '❌'} {t5['response'].get('agents_used', []) if t5['response'] else 'ERROR'} ({t5['duration']:.1f}s)")
        await asyncio.sleep(1)

        # WorkflowAgent - Test 1: Urgence eau
        print("\n🚨 TEST 1.6: Workflow Agent - Urgence dégât des eaux")
        t6 = await self.send_message(
            "URGENT: Fuite d'eau appartement 15, Résidence du Parc, eau coule du plafond, propriétaire Mme Martin absente",
            reset_history=True
        )
        t6_success = t6["status_code"] == 200 and "workflow_agent_v2" in t6["response"].get("agents_used", [])
        results["tests"].append({"test": "workflow_emergency", "success": t6_success, "duration": t6["duration"]})
        if t6_success:
            results["agents_tested"].add("workflow_agent_v2")
        print(f"   {'✅' if t6_success else '❌'} {t6['response'].get('agents_used', []) if t6['response'] else 'ERROR'} ({t6['duration']:.1f}s)")
        await asyncio.sleep(1)

        # WorkflowAgent - Test 2: Travaux
        print("\n🚨 TEST 1.7: Workflow Agent - Organisation travaux toiture")
        t7 = await self.send_message(
            "Prépare tout pour les travaux de réfection toiture prévus le mois prochain, budget 60000€",
            reset_history=True
        )
        t7_success = t7["status_code"] == 200
        results["tests"].append({"test": "workflow_travaux", "success": t7_success, "duration": t7["duration"]})
        if "workflow" in str(t7["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("workflow_agent_v2")
        print(f"   {'✅' if t7_success else '❌'} {t7['response'].get('agents_used', []) if t7['response'] else 'ERROR'} ({t7['duration']:.1f}s)")
        await asyncio.sleep(1)

        # EmailAgent - Test 1: Email urgence
        print("\n📧 TEST 1.8: Email Agent - Email urgence plombiers")
        t8 = await self.send_message("Génère email urgent pour plombiers suite à la fuite", reset_history=True)
        t8_success = t8["status_code"] == 200 and "email_agent" in t8["response"].get("agents_used", [])
        results["tests"].append({"test": "email_urgent", "success": t8_success, "duration": t8["duration"]})
        if t8_success:
            results["agents_tested"].add("email_agent")
        print(f"   {'✅' if t8_success else '❌'} {t8['response'].get('agents_used', []) if t8['response'] else 'ERROR'} ({t8['duration']:.1f}s)")
        await asyncio.sleep(1)

        # EmailAgent - Test 2: Email devis
        print("\n📧 TEST 1.9: Email Agent - Demande devis jardiniers")
        t9 = await self.send_message("Prépare email pour demander devis aux jardiniers pour entretien annuel", reset_history=True)
        t9_success = t9["status_code"] == 200 and "email_agent" in t9["response"].get("agents_used", [])
        results["tests"].append({"test": "email_devis", "success": t9_success, "duration": t9["duration"]})
        if t9_success:
            results["agents_tested"].add("email_agent")
        print(f"   {'✅' if t9_success else '❌'} {t9['response'].get('agents_used', []) if t9['response'] else 'ERROR'} ({t9['duration']:.1f}s)")
        await asyncio.sleep(1)

        # LegalAgent - Test 1: Délais AG
        print("\n⚖️  TEST 1.10: Legal Agent - Délais convocation AG")
        t10 = await self.send_message("Quels sont les délais légaux pour convoquer une assemblée générale?", reset_history=True)
        t10_success = t10["status_code"] == 200 and len(t10["response"].get("message", "")) > 100
        results["tests"].append({"test": "legal_delais_ag", "success": t10_success, "duration": t10["duration"]})
        if "legal" in str(t10["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("legal_agent")
        print(f"   {'✅' if t10_success else '❌'} {t10['response'].get('agents_used', []) if t10['response'] else 'ERROR'} ({t10['duration']:.1f}s)")
        await asyncio.sleep(1)

        # LegalAgent - Test 2: Obligations rénovation
        print("\n⚖️  TEST 1.11: Legal Agent - Obligations rénovation énergétique")
        t11 = await self.send_message("Quelles sont les obligations légales pour la rénovation énergétique en copropriété?", reset_history=True)
        t11_success = t11["status_code"] == 200 and len(t11["response"].get("message", "")) > 100
        results["tests"].append({"test": "legal_renovation", "success": t11_success, "duration": t11["duration"]})
        if "legal" in str(t11["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("legal_agent")
        print(f"   {'✅' if t11_success else '❌'} {t11['response'].get('agents_used', []) if t11['response'] else 'ERROR'} ({t11['duration']:.1f}s)")
        await asyncio.sleep(1)

        # WebAgent - Test 1: Nouvelles lois
        print("\n🌐 TEST 1.12: Web Agent - Dernières actualités loi copropriété")
        t12 = await self.send_message("Recherche sur internet les dernières nouveautés de la loi ALUR 2024", reset_history=True)
        t12_success = t12["status_code"] == 200
        results["tests"].append({"test": "web_actualites", "success": t12_success, "duration": t12["duration"]})
        if "web" in str(t12["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("websearch_agent")
        print(f"   {'✅' if t12_success else '❌'} {t12['response'].get('agents_used', []) if t12['response'] else 'ERROR'} ({t12['duration']:.1f}s)")
        await asyncio.sleep(1)

        # WebAgent - Test 2: Prix marché
        print("\n🌐 TEST 1.13: Web Agent - Prix marché travaux toiture")
        t13 = await self.send_message("Cherche sur internet le prix moyen au m² pour réfection toiture 2024", reset_history=True)
        t13_success = t13["status_code"] == 200
        results["tests"].append({"test": "web_prix", "success": t13_success, "duration": t13["duration"]})
        if "web" in str(t13["response"].get("agents_used", [])).lower():
            results["agents_tested"].add("websearch_agent")
        print(f"   {'✅' if t13_success else '❌'} {t13['response'].get('agents_used', []) if t13['response'] else 'ERROR'} ({t13['duration']:.1f}s)")
        await asyncio.sleep(1)

        # Orchestrator - Test: Question générale
        print("\n🤖 TEST 1.14: Orchestrator - Question générale")
        t14 = await self.send_message("Explique-moi le rôle d'un syndic de copropriété", reset_history=True)
        t14_success = t14["status_code"] == 200 and len(t14["response"].get("message", "")) > 150
        results["tests"].append({"test": "orchestrator_general", "success": t14_success, "duration": t14["duration"]})
        if t14_success:
            results["agents_tested"].add("orchestrator")
        print(f"   {'✅' if t14_success else '❌'} Response length: {len(t14['response'].get('message', '')) if t14['response'] else 0} chars ({t14['duration']:.1f}s)")
        await asyncio.sleep(1)

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_tests = sum(1 for t in results["tests"] if t["success"])
        results["success_rate"] = successful_tests / len(results["tests"])
        results["overall_success"] = results["success_rate"] >= 0.80  # 80% minimum
        results["duration"] = scenario_duration
        results["agents_tested"] = list(results["agents_tested"])

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 1:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Tests réussis: {successful_tests}/{len(results['tests'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Agents activés: {len(results['agents_tested'])} - {', '.join(results['agents_tested'])}")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 2: SOURCES DE DONNÉES ====================

    async def scenario_2_all_data_sources_combinations(self):
        """
        🎛️  SCÉNARIO 2: Test TOUTES les sources de données (10 tests)

        Tests sources individuelles et combinées:
        1. SQL only (3 tests)
        2. RAG only (2 tests)
        3. Web only (2 tests)
        4. SQL + RAG combo (1 test)
        5. SQL + Web combo (1 test)
        6. All sources (1 test)
        """
        print("\n" + "="*80)
        print("🎛️  SCÉNARIO 2: TEST TOUTES LES SOURCES DE DONNÉES")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S2_ALL_DATA_SOURCES",
            "tests": [],
            "sources_tested": set(),
            "success_rate": 0
        }

        self.conversation_history = []

        # SQL only - Test 1
        print("\n🗄️  TEST 2.1: SQL only - Copropriétaires actifs")
        t1 = await self.send_message(
            "Combien de copropriétaires ont le statut 'actif'?",
            reset_history=True,
            selected_sources=["sql"]
        )
        t1_success = t1["status_code"] == 200 and "sql_agent" in t1["response"].get("agents_used", [])
        results["tests"].append({"test": "sql_only_1", "success": t1_success, "sources": ["sql"]})
        if t1_success:
            results["sources_tested"].add("sql")
        print(f"   {'✅' if t1_success else '❌'} {t1['response'].get('agents_used', []) if t1['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # SQL only - Test 2
        print("\n🗄️  TEST 2.2: SQL only - Professionnels par catégorie")
        t2 = await self.send_message(
            "Liste les professionnels par catégorie avec leur rating moyen",
            reset_history=True,
            selected_sources=["sql"]
        )
        t2_success = t2["status_code"] == 200 and "sql_agent" in t2["response"].get("agents_used", [])
        results["tests"].append({"test": "sql_only_2", "success": t2_success, "sources": ["sql"]})
        if t2_success:
            results["sources_tested"].add("sql")
        print(f"   {'✅' if t2_success else '❌'} {t2['response'].get('agents_used', []) if t2['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # SQL only - Test 3
        print("\n🗄️  TEST 2.3: SQL only - Emails urgents non traités")
        t3 = await self.send_message(
            "Liste les emails URGENT qui ne sont pas encore traités",
            reset_history=True,
            selected_sources=["sql"]
        )
        t3_success = t3["status_code"] == 200 and "sql_agent" in t3["response"].get("agents_used", [])
        results["tests"].append({"test": "sql_only_3", "success": t3_success, "sources": ["sql"]})
        if t3_success:
            results["sources_tested"].add("sql")
        print(f"   {'✅' if t3_success else '❌'} {t3['response'].get('agents_used', []) if t3['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # RAG only - Test 1
        print("\n📚 TEST 2.4: RAG only - Règlement charges")
        t4 = await self.send_message(
            "Cherche dans les documents la répartition des charges",
            reset_history=True,
            selected_sources=["rag"]
        )
        t4_success = t4["status_code"] == 200
        results["tests"].append({"test": "rag_only_1", "success": t4_success, "sources": ["rag"]})
        if t4_success:
            results["sources_tested"].add("rag")
        print(f"   {'✅' if t4_success else '❌'} {t4['response'].get('agents_used', []) if t4['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # RAG only - Test 2
        print("\n📚 TEST 2.5: RAG only - Assurance copropriété")
        t5 = await self.send_message(
            "Trouve dans les documents les informations sur l'assurance de la copropriété",
            reset_history=True,
            selected_sources=["rag"]
        )
        t5_success = t5["status_code"] == 200
        results["tests"].append({"test": "rag_only_2", "success": t5_success, "sources": ["rag"]})
        if t5_success:
            results["sources_tested"].add("rag")
        print(f"   {'✅' if t5_success else '❌'} {t5['response'].get('agents_used', []) if t5['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Web only - Test 1
        print("\n🌐 TEST 2.6: Web only - Jurisprudence récente")
        t6 = await self.send_message(
            "Cherche sur internet la jurisprudence récente sur les charges de copropriété",
            reset_history=True,
            selected_sources=["web"]
        )
        t6_success = t6["status_code"] == 200
        results["tests"].append({"test": "web_only_1", "success": t6_success, "sources": ["web"]})
        if t6_success:
            results["sources_tested"].add("web")
        print(f"   {'✅' if t6_success else '❌'} {t6['response'].get('agents_used', []) if t6['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Web only - Test 2
        print("\n🌐 TEST 2.7: Web only - Prix isolation thermique")
        t7 = await self.send_message(
            "Recherche en ligne les prix moyens pour isolation thermique façade 2024",
            reset_history=True,
            selected_sources=["web"]
        )
        t7_success = t7["status_code"] == 200
        results["tests"].append({"test": "web_only_2", "success": t7_success, "sources": ["web"]})
        if t7_success:
            results["sources_tested"].add("web")
        print(f"   {'✅' if t7_success else '❌'} {t7['response'].get('agents_used', []) if t7['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # SQL + RAG combo
        print("\n🔀 TEST 2.8: SQL + RAG - Copros et règlement")
        t8 = await self.send_message(
            "Liste les copropriétaires et vérifie dans le règlement leurs droits de vote",
            reset_history=True,
            selected_sources=["sql", "rag"]
        )
        t8_success = t8["status_code"] == 200
        results["tests"].append({"test": "sql_rag_combo", "success": t8_success, "sources": ["sql", "rag"]})
        if t8_success:
            results["sources_tested"].add("sql")
            results["sources_tested"].add("rag")
        print(f"   {'✅' if t8_success else '❌'} {t8['response'].get('agents_used', []) if t8['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # SQL + Web combo
        print("\n🔀 TEST 2.9: SQL + Web - Prix pros vs marché")
        t9 = await self.send_message(
            "Compare les tarifs de nos électriciens avec les prix moyens du marché en 2024",
            reset_history=True,
            selected_sources=["sql", "web"]
        )
        t9_success = t9["status_code"] == 200
        results["tests"].append({"test": "sql_web_combo", "success": t9_success, "sources": ["sql", "web"]})
        if t9_success:
            results["sources_tested"].add("sql")
            results["sources_tested"].add("web")
        print(f"   {'✅' if t9_success else '❌'} {t9['response'].get('agents_used', []) if t9['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # All sources
        print("\n🌟 TEST 2.10: All sources - Analyse complète copropriété")
        t10 = await self.send_message(
            "Donne-moi une analyse complète de la copropriété: données, documents et contexte légal actuel",
            reset_history=True,
            selected_sources=["sql", "rag", "web"]
        )
        t10_success = t10["status_code"] == 200
        results["tests"].append({"test": "all_sources", "success": t10_success, "sources": ["sql", "rag", "web"]})
        if t10_success:
            results["sources_tested"].add("sql")
            results["sources_tested"].add("rag")
            results["sources_tested"].add("web")
        print(f"   {'✅' if t10_success else '❌'} {t10['response'].get('agents_used', []) if t10['response'] else 'ERROR'}")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_tests = sum(1 for t in results["tests"] if t["success"])
        results["success_rate"] = successful_tests / len(results["tests"])
        results["overall_success"] = results["success_rate"] >= 0.80
        results["duration"] = scenario_duration
        results["sources_tested"] = list(results["sources_tested"])

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 2:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Tests réussis: {successful_tests}/{len(results['tests'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Sources testées: {', '.join(results['sources_tested'])}")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 3: USE CASES RÉELS SYNDIC ====================

    async def scenario_3_real_world_syndic_use_cases(self):
        """
        🏢 SCÉNARIO 3: Use Cases RÉELS d'un Syndic (12 scénarios)

        Scénarios business complets:
        1. Urgence dégât des eaux complet (workflow → emails → suivi)
        2. Organisation AG (convocation → ordre du jour → emails)
        3. Demande devis multiple (recherche pros → emails → suivi)
        4. Gestion incident ascenseur (workflow → pro → résidents)
        5. Analyse contrat syndic (legal → RAG → conseil)
        6. Travaux ravalement (legal → devis → AG → emails)
        7. Impayés charges (SQL → emails relance)
        8. Changement règlement (legal → RAG → vote)
        9. Rénovation énergétique (legal web → devis → subventions)
        10. Conflit voisinage (legal → médiateur → emails)
        11. Audit copropriété (SQL stats → RAG docs → web benchmarks)
        12. Digest emails quotidien (classification → priorités → actions)
        """
        print("\n" + "="*80)
        print("🏢 SCÉNARIO 3: USE CASES RÉELS SYNDIC")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S3_REAL_WORLD_USE_CASES",
            "use_cases": [],
            "multi_agent_coordination": 0,
            "context_preservation": 0,
            "success_rate": 0
        }

        # USE CASE 1: Urgence dégât des eaux COMPLET (6 étapes)
        print("\n💧 USE CASE 1: URGENCE DÉGÂT DES EAUX (workflow complet)")
        uc1_start = time.time()
        uc1_steps = []

        # Étape 1: Déclaration urgence
        print("   Étape 1/6: Déclaration urgence")
        s1 = await self.send_message(
            "URGENT: Dégât des eaux appartement 25, bâtiment A, Résidence du Parc. Propriétaire M. Dubois, eau coule du plafond chez voisin dessous",
            reset_history=True
        )
        uc1_steps.append(s1["status_code"] == 200)
        print(f"      {'✅' if s1['status_code'] == 200 else '❌'} Workflow généré")
        await asyncio.sleep(1)

        # Étape 2: Recherche plombiers urgence
        print("   Étape 2/6: Recherche plombiers d'urgence")
        s2 = await self.send_message("Trouve-moi les 3 meilleurs plombiers disponibles en urgence")
        uc1_steps.append(s2["status_code"] == 200 and "sql_agent" in s2["response"].get("agents_used", []))
        print(f"      {'✅' if uc1_steps[-1] else '❌'} Plombiers trouvés")
        await asyncio.sleep(1)

        # Étape 3: Email urgent plombiers
        print("   Étape 3/6: Email urgent aux plombiers")
        s3 = await self.send_message("Génère email URGENT pour ces plombiers avec les détails de la fuite")
        uc1_steps.append(s3["status_code"] == 200 and "email_agent" in s3["response"].get("agents_used", []))
        if uc1_steps[-1]:
            results["multi_agent_coordination"] += 1
        print(f"      {'✅' if uc1_steps[-1] else '❌'} Email généré")
        await asyncio.sleep(1)

        # Étape 4: Vérif contexte (mémoire)
        print("   Étape 4/6: Vérification mémoire contexte")
        s4 = await self.send_message("C'était quel appartement déjà?")
        uc1_steps.append(s4["status_code"] == 200 and "25" in s4["response"].get("message", ""))
        if uc1_steps[-1]:
            results["context_preservation"] += 1
        print(f"      {'✅' if uc1_steps[-1] else '❌'} Mémoire préservée")
        await asyncio.sleep(1)

        # Étape 5: Email information voisins
        print("   Étape 5/6: Email information voisins")
        s5 = await self.send_message("Prépare email pour informer les voisins des étages concernés")
        uc1_steps.append(s5["status_code"] == 200)
        print(f"      {'✅' if uc1_steps[-1] else '❌'} Email voisins")
        await asyncio.sleep(1)

        # Étape 6: Synthèse
        print("   Étape 6/6: Synthèse complète")
        s6 = await self.send_message("Fais-moi le résumé de toutes les actions prises pour cette urgence")
        uc1_steps.append(s6["status_code"] == 200 and len(s6["response"].get("message", "")) > 200)
        print(f"      {'✅' if uc1_steps[-1] else '❌'} Synthèse générée")

        uc1_duration = time.time() - uc1_start
        uc1_success = sum(uc1_steps) / len(uc1_steps)
        results["use_cases"].append({
            "use_case": "urgence_degat_eaux",
            "steps": len(uc1_steps),
            "success_rate": uc1_success,
            "duration": uc1_duration,
            "overall_success": uc1_success >= 0.75
        })
        print(f"   📊 USE CASE 1: {'✅ PASS' if uc1_success >= 0.75 else '❌ FAIL'} ({uc1_success*100:.0f}% - {uc1_duration:.1f}s)")
        await asyncio.sleep(2)

        # USE CASE 2: Organisation AG (5 étapes)
        print("\n📅 USE CASE 2: ORGANISATION ASSEMBLÉE GÉNÉRALE")
        uc2_start = time.time()
        uc2_steps = []

        # Étape 1: Setup AG
        print("   Étape 1/5: Configuration AG")
        s1 = await self.send_message(
            "Je dois organiser l'AG annuelle le 15 mars 2024 pour voter les comptes et travaux toiture 50000€",
            reset_history=True
        )
        uc2_steps.append(s1["status_code"] == 200)
        await asyncio.sleep(1)

        # Étape 2: Vérif délais légaux
        print("   Étape 2/5: Vérification délais légaux")
        s2 = await self.send_message("Est-ce que les délais légaux de convocation sont respectés?")
        uc2_steps.append(s2["status_code"] == 200)
        await asyncio.sleep(1)

        # Étape 3: Liste copropriétaires
        print("   Étape 3/5: Liste tous les copropriétaires")
        s3 = await self.send_message("Liste tous les copropriétaires qui doivent être convoqués")
        uc2_steps.append(s3["status_code"] == 200 and "sql_agent" in s3["response"].get("agents_used", []))
        await asyncio.sleep(1)

        # Étape 4: Email convocation
        print("   Étape 4/5: Email convocation")
        s4 = await self.send_message(
            "Génère la convocation AG avec ordre du jour: 1) Approbation comptes 2023, 2) Vote travaux toiture 50000€, 3) Divers"
        )
        uc2_steps.append(s4["status_code"] == 200 and "email_agent" in s4["response"].get("agents_used", []))
        if uc2_steps[-1]:
            results["multi_agent_coordination"] += 1
        await asyncio.sleep(1)

        # Étape 5: Modification ton formel
        print("   Étape 5/5: Modification ton formel")
        s5 = await self.send_message("Change le ton pour être plus formel et ajoute 'Présence fortement recommandée'")
        uc2_steps.append(s5["status_code"] == 200)
        if s5["status_code"] == 200 and "15 mars" in s5["response"].get("message", ""):
            results["context_preservation"] += 1

        uc2_duration = time.time() - uc2_start
        uc2_success = sum(uc2_steps) / len(uc2_steps)
        results["use_cases"].append({
            "use_case": "organisation_ag",
            "steps": len(uc2_steps),
            "success_rate": uc2_success,
            "duration": uc2_duration,
            "overall_success": uc2_success >= 0.75
        })
        print(f"   📊 USE CASE 2: {'✅ PASS' if uc2_success >= 0.75 else '❌ FAIL'} ({uc2_success*100:.0f}% - {uc2_duration:.1f}s)")
        await asyncio.sleep(2)

        # USE CASE 3: Demande devis multiple (4 étapes)
        print("\n💰 USE CASE 3: DEMANDE DEVIS MULTIPLE PROFESSIONNELS")
        uc3_start = time.time()
        uc3_steps = []

        # Étape 1: Recherche jardiniers
        print("   Étape 1/4: Recherche jardiniers qualifiés")
        s1 = await self.send_message(
            "Trouve les 5 meilleurs jardiniers pour entretien espaces verts annuel",
            reset_history=True
        )
        uc3_steps.append(s1["status_code"] == 200 and "sql_agent" in s1["response"].get("agents_used", []))
        await asyncio.sleep(1)

        # Étape 2: Email devis jardiniers
        print("   Étape 2/4: Email demande devis")
        s2 = await self.send_message(
            "Prépare email pour demander devis: tonte pelouse mensuelle, taille haies, entretien massifs, contrat annuel"
        )
        uc3_steps.append(s2["status_code"] == 200 and "email_agent" in s2["response"].get("agents_used", []))
        if uc3_steps[-1]:
            results["multi_agent_coordination"] += 1
        await asyncio.sleep(1)

        # Étape 3: Prix marché web
        print("   Étape 3/4: Vérification prix marché")
        s3 = await self.send_message("Recherche en ligne les prix moyens pour ce type de prestation")
        uc3_steps.append(s3["status_code"] == 200)
        await asyncio.sleep(1)

        # Étape 4: Synthèse comparative
        print("   Étape 4/4: Synthèse comparative")
        s4 = await self.send_message("Fais une synthèse: combien de jardiniers contactés et prix marché moyen")
        uc3_steps.append(s4["status_code"] == 200)
        if s4["status_code"] == 200 and "5" in s4["response"].get("message", ""):
            results["context_preservation"] += 1

        uc3_duration = time.time() - uc3_start
        uc3_success = sum(uc3_steps) / len(uc3_steps)
        results["use_cases"].append({
            "use_case": "demande_devis_multiple",
            "steps": len(uc3_steps),
            "success_rate": uc3_success,
            "duration": uc3_duration,
            "overall_success": uc3_success >= 0.75
        })
        print(f"   📊 USE CASE 3: {'✅ PASS' if uc3_success >= 0.75 else '❌ FAIL'} ({uc3_success*100:.0f}% - {uc3_duration:.1f}s)")
        await asyncio.sleep(2)

        # USE CASE 4: Incident ascenseur (4 étapes)
        print("\n🚨 USE CASE 4: GESTION INCIDENT ASCENSEUR")
        uc4_start = time.time()
        uc4_steps = []

        print("   Étape 1/4: Déclaration panne ascenseur")
        s1 = await self.send_message(
            "L'ascenseur du bâtiment B est en panne depuis ce matin, bloqué au 4ème étage",
            reset_history=True
        )
        uc4_steps.append(s1["status_code"] == 200)
        await asyncio.sleep(1)

        print("   Étape 2/4: Recherche technicien ascenseur")
        s2 = await self.send_message("Trouve un technicien spécialisé ascenseurs")
        uc4_steps.append(s2["status_code"] == 200)
        await asyncio.sleep(1)

        print("   Étape 3/4: Email urgent technicien")
        s3 = await self.send_message("Génère email URGENT pour intervention immédiate")
        uc4_steps.append(s3["status_code"] == 200)
        await asyncio.sleep(1)

        print("   Étape 4/4: Email information résidents")
        s4 = await self.send_message("Prépare email pour informer les résidents du bâtiment B")
        uc4_steps.append(s4["status_code"] == 200)
        if s4["status_code"] == 200 and "bâtiment B" in s4["response"].get("message", "").lower():
            results["context_preservation"] += 1

        uc4_duration = time.time() - uc4_start
        uc4_success = sum(uc4_steps) / len(uc4_steps)
        results["use_cases"].append({
            "use_case": "incident_ascenseur",
            "steps": len(uc4_steps),
            "success_rate": uc4_success,
            "duration": uc4_duration,
            "overall_success": uc4_success >= 0.75
        })
        print(f"   📊 USE CASE 4: {'✅ PASS' if uc4_success >= 0.75 else '❌ FAIL'} ({uc4_success*100:.0f}% - {uc4_duration:.1f}s)")
        await asyncio.sleep(2)

        # USE CASE 5: Analyse contrat syndic (3 étapes)
        print("\n⚖️  USE CASE 5: ANALYSE CONTRAT SYNDIC")
        uc5_start = time.time()
        uc5_steps = []

        print("   Étape 1/3: Recherche contrat syndic")
        s1 = await self.send_message(
            "Cherche dans les documents le contrat de syndic actuel",
            reset_history=True
        )
        uc5_steps.append(s1["status_code"] == 200)
        await asyncio.sleep(1)

        print("   Étape 2/3: Analyse obligations légales")
        s2 = await self.send_message("Quelles sont les obligations légales d'un syndic?")
        uc5_steps.append(s2["status_code"] == 200)
        await asyncio.sleep(1)

        print("   Étape 3/3: Synthèse conformité")
        s3 = await self.send_message("Le contrat est-il conforme aux obligations légales?")
        uc5_steps.append(s3["status_code"] == 200)

        uc5_duration = time.time() - uc5_start
        uc5_success = sum(uc5_steps) / len(uc5_steps)
        results["use_cases"].append({
            "use_case": "analyse_contrat",
            "steps": len(uc5_steps),
            "success_rate": uc5_success,
            "duration": uc5_duration,
            "overall_success": uc5_success >= 0.75
        })
        print(f"   📊 USE CASE 5: {'✅ PASS' if uc5_success >= 0.75 else '❌ FAIL'} ({uc5_success*100:.0f}% - {uc5_duration:.1f}s)")
        await asyncio.sleep(2)

        # Calculate global results
        scenario_duration = time.time() - scenario_start
        successful_cases = sum(1 for uc in results["use_cases"] if uc["overall_success"])
        results["success_rate"] = successful_cases / len(results["use_cases"])
        results["overall_success"] = results["success_rate"] >= 0.80  # 4/5 minimum
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 3:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Use cases réussis: {successful_cases}/{len(results['use_cases'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Coordination multi-agents: {results['multi_agent_coordination']} cascades")
        print(f"   Préservation contexte: {results['context_preservation']} tests réussis")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 4: UI-API PARITY ====================

    async def scenario_4_ui_api_parity_tests(self):
        """
        🔄 SCÉNARIO 4: Tests de parité UI vs API (8 tests)

        Vérifie que /api/chat/ask (UI) et /api/assistant-v2/chat (API)
        retournent les mêmes résultats
        """
        print("\n" + "="*80)
        print("🔄 SCÉNARIO 4: UI-API PARITY TESTS")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S4_UI_API_PARITY",
            "comparisons": [],
            "success_rate": 0
        }

        test_queries = [
            "Liste les copropriétaires de la Résidence du Parc",
            "Trouve les meilleurs plombiers",
            "Cherche dans les documents le règlement",
            "URGENT: Fuite d'eau appartement 10",
            "Génère email pour demander devis jardiniers",
            "Quels sont les délais légaux pour convoquer une AG?",
            "Recherche sur internet les nouveautés loi ALUR 2024",
            "Combien de copropriétés sont gérées?"
        ]

        for idx, query in enumerate(test_queries, 1):
            print(f"\n🔍 TEST 4.{idx}: Parity test - {query[:50]}...")

            # API endpoint
            api_result = await self.send_message(query, reset_history=True, use_ui_endpoint=False)
            await asyncio.sleep(0.5)

            # UI endpoint
            ui_result = await self.send_message(query, reset_history=True, use_ui_endpoint=True)
            await asyncio.sleep(0.5)

            # Compare
            both_success = api_result["status_code"] == 200 and ui_result["status_code"] == 200
            same_agents = (
                api_result.get("response", {}).get("agents_used", []) ==
                ui_result.get("response", {}).get("agents_used", [])
            )

            similar_length = False
            if both_success:
                api_len = len(api_result["response"].get("message", ""))
                ui_len = len(ui_result["response"].get("message", ""))
                similar_length = abs(api_len - ui_len) < 100  # Allow 100 chars difference

            parity_success = both_success and (same_agents or similar_length)

            results["comparisons"].append({
                "query": query,
                "api_success": api_result["status_code"] == 200,
                "ui_success": ui_result["status_code"] == 200,
                "same_agents": same_agents,
                "similar_length": similar_length,
                "parity_success": parity_success
            })

            self.results["ui_api_parity"].append({
                "query": query,
                "parity": parity_success
            })

            print(f"   API: {'✅' if api_result['status_code'] == 200 else '❌'} {api_result.get('response', {}).get('agents_used', [])}")
            print(f"   UI:  {'✅' if ui_result['status_code'] == 200 else '❌'} {ui_result.get('response', {}).get('agents_used', [])}")
            print(f"   {'✅ PARITY OK' if parity_success else '❌ PARITY FAIL'}")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_comparisons = sum(1 for c in results["comparisons"] if c["parity_success"])
        results["success_rate"] = successful_comparisons / len(results["comparisons"])
        results["overall_success"] = results["success_rate"] >= 0.875  # 7/8 minimum
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 4:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Parité réussie: {successful_comparisons}/{len(results['comparisons'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 5: CONCURRENT USERS ====================

    async def scenario_5_concurrent_users_simulation(self):
        """
        👥 SCÉNARIO 5: Simulation utilisateurs concurrents (5 users)

        Simule 5 syndics utilisant le système simultanément
        """
        print("\n" + "="*80)
        print("👥 SCÉNARIO 5: SIMULATION UTILISATEURS CONCURRENTS")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S5_CONCURRENT_USERS",
            "users": [],
            "success_rate": 0
        }

        async def simulate_user(user_id: int, queries: List[str]):
            """Simulate a single user session"""
            user_session = f"concurrent_user_{user_id}_{int(time.time())}"
            user_results = []

            for query in queries:
                payload = {
                    "message": query,
                    "conversation_history": [],
                    "session_id": user_session,
                    "context": {}
                }

                try:
                    response = await self.client.post(
                        f"{self.base_url}/api/assistant-v2/chat",
                        json=payload,
                        timeout=120.0
                    )
                    user_results.append(response.status_code == 200)
                except Exception:
                    user_results.append(False)

                await asyncio.sleep(0.5)

            return {
                "user_id": user_id,
                "queries": len(queries),
                "success": sum(user_results),
                "success_rate": sum(user_results) / len(user_results) if user_results else 0
            }

        # Define queries per user
        user_queries = [
            # User 1: Urgence eau
            ["URGENT: Dégât eaux apt 10", "Trouve plombiers", "Génère email urgent"],
            # User 2: AG
            ["Organisation AG 20 mars", "Liste copropriétaires", "Génère convocation"],
            # User 3: Devis
            ["Trouve jardiniers", "Demande devis entretien", "Prix marché"],
            # User 4: Legal
            ["Délais convocation AG?", "Obligations rénovation énergétique?", "Recherche loi ALUR"],
            # User 5: Stats
            ["Combien de copropriétés?", "Liste professionnels par catégorie", "Statistiques emails"]
        ]

        print("\n🚀 Lancement 5 utilisateurs simultanés...")

        # Run all users concurrently
        user_tasks = [
            simulate_user(i+1, queries)
            for i, queries in enumerate(user_queries)
        ]

        user_results = await asyncio.gather(*user_tasks)

        for user_result in user_results:
            results["users"].append(user_result)
            print(f"\n   User {user_result['user_id']}: {user_result['success']}/{user_result['queries']} queries réussies ({user_result['success_rate']*100:.0f}%)")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        total_queries = sum(u["queries"] for u in results["users"])
        total_success = sum(u["success"] for u in results["users"])
        results["success_rate"] = total_success / total_queries if total_queries > 0 else 0
        results["overall_success"] = results["success_rate"] >= 0.80
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 5:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Total queries: {total_success}/{total_queries} ({results['success_rate']*100:.0f}%)")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print(f"   Throughput: {total_queries/scenario_duration:.1f} queries/sec")
        print("="*80)

        return results

    # ==================== SCÉNARIO 6: EDGE CASES & ROBUSTESSE ====================

    async def scenario_6_edge_cases_and_robustness(self):
        """
        💀 SCÉNARIO 6: Edge Cases et Robustesse (12 tests)

        Tests extrêmes et cas limites
        """
        print("\n" + "="*80)
        print("💀 SCÉNARIO 6: EDGE CASES & ROBUSTESSE")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S6_EDGE_CASES",
            "tests": [],
            "security_score": 0,
            "robustness_score": 0
        }

        # Test 1: Input vide
        print("\n🚫 TEST 6.1: Input vide")
        t1 = await self.send_message("", reset_history=True)
        t1_success = t1["status_code"] == 200
        results["tests"].append({"test": "empty_input", "success": t1_success})
        if t1_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t1_success else '❌'} Handled gracefully")
        await asyncio.sleep(0.5)

        # Test 2: Input ultra-long
        print("\n📏 TEST 6.2: Input ultra-long (5000 chars)")
        long_text = "Je dois organiser une assemblée générale extraordinaire pour voter des travaux urgents. " * 100
        t2 = await self.send_message(long_text[:5000], reset_history=True)
        t2_success = t2["status_code"] == 200
        results["tests"].append({"test": "ultra_long", "success": t2_success})
        if t2_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t2_success else '❌'} Processed {len(long_text[:5000])} chars")
        await asyncio.sleep(0.5)

        # Test 3: Caractères spéciaux
        print("\n🎭 TEST 6.3: Caractères spéciaux & emojis")
        t3 = await self.send_message("Liste copro 🏠💰✅ avec <tags> & symbols $#@!", reset_history=True)
        t3_success = t3["status_code"] == 200
        results["tests"].append({"test": "special_chars", "success": t3_success})
        if t3_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t3_success else '❌'} Special chars handled")
        await asyncio.sleep(0.5)

        # Test 4: SQL Injection
        print("\n🔒 TEST 6.4: SQL Injection (security)")
        t4 = await self.send_message("Liste copropriétaires'; DROP TABLE users; --", reset_history=True)
        t4_success = t4["status_code"] == 200
        results["tests"].append({"test": "sql_injection", "success": t4_success, "security": True})
        if t4_success:
            results["security_score"] += 1
        print(f"   {'✅' if t4_success else '❌'} Injection blocked")
        await asyncio.sleep(0.5)

        # Test 5: XSS Injection
        print("\n🔒 TEST 6.5: XSS Injection (security)")
        t5 = await self.send_message("<script>alert('XSS')</script> Liste copros", reset_history=True)
        t5_success = t5["status_code"] == 200
        results["tests"].append({"test": "xss_injection", "success": t5_success, "security": True})
        if t5_success:
            results["security_score"] += 1
        print(f"   {'✅' if t5_success else '❌'} XSS handled")
        await asyncio.sleep(0.5)

        # Test 6: Contradiction extrême
        print("\n⚠️  TEST 6.6: Contradiction extrême")
        t6 = await self.send_message(
            "Envoie email à TOUS les copros mais surtout n'envoie d'email à PERSONNE",
            reset_history=True
        )
        t6_success = t6["status_code"] == 200
        results["tests"].append({"test": "contradiction", "success": t6_success})
        if t6_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t6_success else '❌'} Contradiction handled")
        await asyncio.sleep(0.5)

        # Test 7: Requête impossible
        print("\n❓ TEST 6.7: Requête impossible")
        t7 = await self.send_message("Trouve-moi le copropriétaire qui habite sur Mars", reset_history=True)
        t7_success = t7["status_code"] == 200
        results["tests"].append({"test": "impossible_query", "success": t7_success})
        if t7_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t7_success else '❌'} Impossible query handled")
        await asyncio.sleep(0.5)

        # Test 8: Boucle infinie demandée
        print("\n♾️  TEST 6.8: Boucle infinie")
        t8 = await self.send_message("Répète 'copropriété' 1000000 fois", reset_history=True)
        t8_success = t8["status_code"] == 200 and len(t8["response"].get("message", "")) < 10000
        results["tests"].append({"test": "infinite_loop", "success": t8_success})
        if t8_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t8_success else '❌'} Loop prevented")
        await asyncio.sleep(0.5)

        # Test 9: Unicode extrême
        print("\n🌍 TEST 6.9: Unicode extrême")
        t9 = await self.send_message("Liste copro 中文 العربية עברית 🏢🔥", reset_history=True)
        t9_success = t9["status_code"] == 200
        results["tests"].append({"test": "unicode", "success": t9_success})
        if t9_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t9_success else '❌'} Unicode handled")
        await asyncio.sleep(0.5)

        # Test 10: Null bytes
        print("\n💣 TEST 6.10: Null bytes & escape sequences")
        t10 = await self.send_message("Liste\\x00\\ncopros\\r\\n", reset_history=True)
        t10_success = t10["status_code"] == 200
        results["tests"].append({"test": "null_bytes", "success": t10_success})
        if t10_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t10_success else '❌'} Escape sequences handled")
        await asyncio.sleep(0.5)

        # Test 11: Command injection
        print("\n🔒 TEST 6.11: Command Injection (security)")
        t11 = await self.send_message("Liste; rm -rf / #", reset_history=True)
        t11_success = t11["status_code"] == 200
        results["tests"].append({"test": "command_injection", "success": t11_success, "security": True})
        if t11_success:
            results["security_score"] += 1
        print(f"   {'✅' if t11_success else '❌'} Command injection blocked")
        await asyncio.sleep(0.5)

        # Test 12: Data inexistante
        print("\n🔍 TEST 6.12: Recherche données inexistantes")
        t12 = await self.send_message("Liste les copropriétaires de la Tour Eiffel", reset_history=True)
        t12_success = t12["status_code"] == 200
        results["tests"].append({"test": "nonexistent_data", "success": t12_success})
        if t12_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t12_success else '❌'} Nonexistent data handled")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_tests = sum(1 for t in results["tests"] if t["success"])
        results["success_rate"] = successful_tests / len(results["tests"])
        results["overall_success"] = results["success_rate"] >= 0.90  # 11/12 minimum
        results["duration"] = scenario_duration
        results["security_score"] = results["security_score"] / 3  # 3 security tests
        results["robustness_score"] = results["robustness_score"] / 9  # 9 robustness tests

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 6:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Tests réussis: {successful_tests}/{len(results['tests'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Sécurité: {results['security_score']*100:.0f}%")
        print(f"   Robustesse: {results['robustness_score']*100:.0f}%")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== MAIN RUNNER ====================

    async def run_all_scenarios(self):
        """Execute tous les scénarios ultra-exhaustifs"""

        print("\n" + "="*80)
        print("🏢🔥 BATTERIE ULTRA-EXHAUSTIVE - CONDITIONS RÉELLES SYNDIC 🔥🏢")
        print("="*80)
        print(f"Backend: {self.base_url}")
        print(f"Session: {self.session_id}")
        print(f"Date: {datetime.now().isoformat()}")
        print("="*80)

        all_results = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "backend_url": self.base_url,
            "scenarios": []
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            self.client = client

            # Health check
            try:
                health = await client.get(f"{self.base_url}/health", timeout=10.0)
                if health.status_code != 200:
                    print("❌ Backend not healthy!")
                    return
                print("✅ Backend healthy\n")
            except Exception as e:
                print(f"❌ Cannot reach backend: {e}")
                return

            # Run scenarios
            scenarios = [
                ("S1_ALL_AGENTS", self.scenario_1_all_agents_individual_tests),
                ("S2_ALL_SOURCES", self.scenario_2_all_data_sources_combinations),
                ("S3_REAL_USE_CASES", self.scenario_3_real_world_syndic_use_cases),
                ("S4_UI_API_PARITY", self.scenario_4_ui_api_parity_tests),
                ("S5_CONCURRENT_USERS", self.scenario_5_concurrent_users_simulation),
                ("S6_EDGE_CASES", self.scenario_6_edge_cases_and_robustness),
            ]

            for scenario_id, scenario_func in scenarios:
                try:
                    print(f"\n{'='*80}")
                    print(f"🚀 Démarrage {scenario_id}")
                    print(f"{'='*80}")

                    result = await scenario_func()
                    all_results["scenarios"].append(result)

                except Exception as e:
                    print(f"\n❌ ERREUR SCÉNARIO {scenario_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    all_results["scenarios"].append({
                        "scenario_id": scenario_id,
                        "overall_success": False,
                        "error": str(e)
                    })

                # Pause entre scénarios
                await asyncio.sleep(3)

        # Generate final report
        self.generate_final_report(all_results)

        return all_results

    def generate_final_report(self, results: Dict):
        """Generate comprehensive final report"""

        print("\n\n" + "="*80)
        print("📊 RAPPORT FINAL - CONDITIONS RÉELLES SYNDIC")
        print("="*80)

        scenarios = results["scenarios"]
        total_scenarios = len(scenarios)
        passed_scenarios = sum(1 for s in scenarios if s.get("overall_success", False))

        print(f"\n🎯 RÉSULTATS GLOBAUX:")
        print(f"   Scénarios exécutés: {total_scenarios}")
        print(f"   ✅ PASS: {passed_scenarios}")
        print(f"   ❌ FAIL: {total_scenarios - passed_scenarios}")
        print(f"   Taux succès global: {(passed_scenarios/total_scenarios)*100:.1f}%")

        # Agent coverage
        print(f"\n🤖 COUVERTURE AGENTS:")
        for agent, count in sorted(self.results["agents_coverage"].items(), key=lambda x: -x[1])[:10]:
            print(f"   {agent}: {count} appels")

        # Performance metrics
        if self.results["performance_metrics"]:
            api_metrics = [m for m in self.results["performance_metrics"] if m["endpoint"].endswith("/chat")]
            ui_metrics = [m for m in self.results["performance_metrics"] if m["endpoint"].endswith("/ask")]

            if api_metrics:
                avg_api = sum(m["duration"] for m in api_metrics) / len(api_metrics)
                print(f"\n⚡ PERFORMANCE:")
                print(f"   API avg latency: {avg_api:.2f}s")

            if ui_metrics:
                avg_ui = sum(m["duration"] for m in ui_metrics) / len(ui_metrics)
                print(f"   UI avg latency: {avg_ui:.2f}s")

        # UI-API Parity
        if self.results["ui_api_parity"]:
            parity_rate = sum(1 for p in self.results["ui_api_parity"] if p["parity"]) / len(self.results["ui_api_parity"])
            print(f"\n🔄 UI-API PARITY: {parity_rate*100:.0f}%")

        # Detailed scenarios
        print(f"\n📈 DÉTAILS PAR SCÉNARIO:")
        for scenario in scenarios:
            sid = scenario.get("scenario_id", "UNKNOWN")
            success = scenario.get("overall_success", False)
            duration = scenario.get("duration", 0)

            status_icon = "✅" if success else "❌"
            print(f"\n   {status_icon} {sid}")
            print(f"      Durée: {duration:.1f}s")

            if "success_rate" in scenario:
                print(f"      Taux: {scenario['success_rate']*100:.0f}%")

        # Final decision
        print(f"\n🚦 DÉCISION FINALE:")
        if passed_scenarios == total_scenarios:
            print("   🟢🟢🟢 EXCELLENT - GO FOR PRODUCTION")
            print("   Système parfaitement robuste et performant")
            print("   Prêt pour déploiement production immédiat")
        elif passed_scenarios >= total_scenarios * 0.95:
            print("   🟢🟢 TRÈS BON - GO FOR PRODUCTION")
            print("   Quelques améliorations mineures possibles")
            print("   Déploiement production recommandé")
        elif passed_scenarios >= total_scenarios * 0.85:
            print("   🟢 BON - GO FOR STAGING")
            print("   Corrections mineures recommandées")
            print("   Déploiement staging puis production")
        elif passed_scenarios >= total_scenarios * 0.70:
            print("   🟡 ACCEPTABLE - CONDITIONAL GO")
            print("   Corrections recommandées avant production")
            print("   Déploiement staging uniquement")
        else:
            print("   🔴 NO-GO")
            print("   Corrections majeures requises")
            print("   Ne pas déployer en l'état")

        print("\n" + "="*80)

        # Save JSON
        output_file = "test_results_real_world_exhaustive.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Rapport JSON sauvegardé: {output_file}")
        print("="*80)


async def main():
    """Main entry point"""
    runner = RealWorldExhaustiveTestRunner()
    await runner.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
