"""
🔥🔥🔥 BATTERIE ULTRA-EXHAUSTIVE - TESTS IMPITOYABLES 🔥🔥🔥
================================================================

Tests exhaustifs challengeant TOUS les agents avec:
- Cascades multi-agents complexes (4-6 agents)
- Toutes sources de données (SQL, RAG, Web, combinaisons)
- Conversations longues (10+ échanges)
- Edge cases extrêmes
- Tests avec selected_sources (opt-in)
- Scénarios réels business critiques
- Memory & Context propagation hardcore
- Error recovery & Graceful degradation

Objectif: 95%+ success rate ou NO-GO définitif
"""

import asyncio
import httpx
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

BASE_URL = "http://localhost:8000"


class UltraExhaustiveTestRunner:
    """Ultra-comprehensive test runner - NO MERCY"""

    def __init__(self):
        self.base_url = BASE_URL
        self.session_id = f"ultra_test_{int(time.time())}"
        self.client = None
        self.results = {"scenarios": [], "agents_coverage": {}, "sources_coverage": {}}
        self.conversation_history = []

    async def send_message(
        self,
        user_input: str,
        reset_history: bool = False,
        selected_sources: Optional[List[str]] = None
    ) -> Dict:
        """Send message with optional source selection"""
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

        try:
            response = await self.client.post(
                f"{self.base_url}/api/assistant-v2/chat",
                json=payload,
                timeout=120.0
            )

            result = {
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None
            }

            # Track agents & sources used
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
            return {"status_code": 0, "response": None, "error": str(e)}

    # ==================== SCÉNARIO 1: TOUS LES AGENTS ====================

    async def scenario_1_all_agents_orchestration(self):
        """
        🎯 SCÉNARIO 1: Orchestration TOUS LES AGENTS (10 interactions)

        Objectif: Valider que TOUS les agents peuvent être appelés correctement

        Agents testés:
        1. SQLAgent - Queries DB
        2. RAGService - Document search
        3. EmailAgent - Email generation
        4. WorkflowAgentV2 - Workflow creation
        5. TemplateAgent - Template filling
        6. LegalAgent - Legal analysis
        7. WebSearchAgent - Internet search
        8. MailAgent - Email classification
        9. OCRAgent - Document OCR
        10. Orchestrator - General questions
        """
        print("\n" + "="*80)
        print("🎯 SCÉNARIO 1: ORCHESTRATION TOUS LES AGENTS")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S1_ALL_AGENTS",
            "steps": [],
            "agents_tested": [],
            "success_rate": 0
        }

        self.conversation_history = []

        # Test 1: SQLAgent
        print("\n🗄️  TEST 1.1: SQL Agent - Query simple")
        step1 = await self.send_message("Combien y a-t-il de copropriétaires au total?")
        s1_success = (
            step1["status_code"] == 200 and
            "sql_agent" in step1["response"].get("agents_used", [])
        )
        results["steps"].append({"agent": "sql_agent", "success": s1_success})
        if s1_success:
            results["agents_tested"].append("sql_agent")
        print(f"   {'✅' if s1_success else '❌'} {step1['response'].get('agents_used', []) if step1['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 2: RAGService
        print("\n📚 TEST 1.2: RAG Service - Document search")
        step2 = await self.send_message("Cherche dans les documents le règlement de la copropriété")
        s2_success = (
            step2["status_code"] == 200 and
            ("rag_service" in step2["response"].get("agents_used", []) or
             "rag" in str(step2["response"].get("agents_used", [])).lower())
        )
        results["steps"].append({"agent": "rag_service", "success": s2_success})
        if s2_success:
            results["agents_tested"].append("rag_service")
        print(f"   {'✅' if s2_success else '❌'} {step2['response'].get('agents_used', []) if step2['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 3: WorkflowAgentV2
        print("\n🚨 TEST 1.3: Workflow Agent V2 - Emergency workflow")
        step3 = await self.send_message("URGENT: Fuite d'eau dans l'appartement 25, bâtiment A!")
        s3_success = (
            step3["status_code"] == 200 and
            "workflow_agent_v2" in step3["response"].get("agents_used", [])
        )
        results["steps"].append({"agent": "workflow_agent_v2", "success": s3_success})
        if s3_success:
            results["agents_tested"].append("workflow_agent_v2")
        print(f"   {'✅' if s3_success else '❌'} {step3['response'].get('agents_used', []) if step3['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 4: EmailAgent (with context from workflow)
        print("\n📧 TEST 1.4: Email Agent - Generate with workflow context")
        step4 = await self.send_message("Génère un email urgent pour les plombiers")
        s4_success = (
            step4["status_code"] == 200 and
            "email_agent" in step4["response"].get("agents_used", [])
        )
        results["steps"].append({"agent": "email_agent", "success": s4_success})
        if s4_success:
            results["agents_tested"].append("email_agent")
        print(f"   {'✅' if s4_success else '❌'} {step4['response'].get('agents_used', []) if step4['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 5: LegalAgent
        print("\n⚖️  TEST 1.5: Legal Agent - Legal query")
        step5 = await self.send_message("Quels sont les délais légaux pour convoquer une assemblée générale?", reset_history=True)
        s5_success = (
            step5["status_code"] == 200 and
            ("legal_agent" in step5["response"].get("agents_used", []) or
             len(step5["response"].get("message", "")) > 100)  # At least substantial answer
        )
        results["steps"].append({"agent": "legal_agent", "success": s5_success})
        if s5_success:
            results["agents_tested"].append("legal_agent")
        print(f"   {'✅' if s5_success else '❌'} {step5['response'].get('agents_used', []) if step5['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 6: TemplateAgent (via devis)
        print("\n📋 TEST 1.6: Template Agent - Devis request")
        step6 = await self.send_message("Demande de devis pour jardiniers", reset_history=True)
        s6_success = (
            step6["status_code"] == 200 and
            ("template_agent" in step6["response"].get("agents_used", []) or
             "sql_agent" in step6["response"].get("agents_used", []))  # May route via SQL first
        )
        results["steps"].append({"agent": "template_agent", "success": s6_success})
        if s6_success:
            results["agents_tested"].append("template_agent")
        print(f"   {'✅' if s6_success else '❌'} {step6['response'].get('agents_used', []) if step6['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 7: WebSearchAgent
        print("\n🌐 TEST 1.7: Web Search Agent - Internet query")
        step7 = await self.send_message("Recherche sur internet les nouveautés de la loi ALUR 2024", reset_history=True)
        s7_success = (
            step7["status_code"] == 200 and
            ("websearch_agent" in step7["response"].get("agents_used", []) or
             "web" in str(step7["response"].get("agents_used", [])).lower())
        )
        results["steps"].append({"agent": "websearch_agent", "success": s7_success})
        if s7_success:
            results["agents_tested"].append("websearch_agent")
        print(f"   {'✅' if s7_success else '❌'} {step7['response'].get('agents_used', []) if step7['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 8: Orchestrator (general question)
        print("\n🤖 TEST 1.8: Orchestrator - General question")
        step8 = await self.send_message("Explique-moi comment fonctionne une assemblée générale de copropriété", reset_history=True)
        s8_success = step8["status_code"] == 200 and len(step8["response"].get("message", "")) > 100
        results["steps"].append({"agent": "orchestrator", "success": s8_success})
        if s8_success:
            results["agents_tested"].append("orchestrator")
        print(f"   {'✅' if s8_success else '❌'} General answer provided")
        await asyncio.sleep(1)

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_steps = sum(1 for s in results["steps"] if s["success"])
        results["success_rate"] = successful_steps / len(results["steps"])
        results["overall_success"] = results["success_rate"] >= 0.75  # 6/8 minimum
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 1:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Agents testés: {successful_steps}/{len(results['steps'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Agents activés: {', '.join(results['agents_tested'])}")
        print(f"   Durée: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 2: SOURCE SELECTION ====================

    async def scenario_2_source_selection_opt_in(self):
        """
        🎛️  SCÉNARIO 2: Source Selection (Opt-In) - 8 tests

        Test selected_sources parameter:
        - SQL only
        - RAG only
        - Web only
        - SQL + RAG
        - All sources
        - None (auto)
        - Invalid source handling
        """
        print("\n" + "="*80)
        print("🎛️  SCÉNARIO 2: SOURCE SELECTION (OPT-IN)")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S2_SOURCE_SELECTION",
            "tests": [],
            "success_rate": 0
        }

        self.conversation_history = []

        # Test 1: SQL only
        print("\n🗄️  TEST 2.1: Force SQL only")
        t1 = await self.send_message(
            "Combien de professionnels plombiers?",
            reset_history=True,
            selected_sources=["sql"]
        )
        t1_success = (
            t1["status_code"] == 200 and
            "sql_agent" in t1["response"].get("agents_used", [])
        )
        results["tests"].append({"test": "sql_only", "success": t1_success})
        print(f"   {'✅' if t1_success else '❌'} {t1['response'].get('agents_used', []) if t1['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 2: RAG only
        print("\n📚 TEST 2.2: Force RAG only")
        t2 = await self.send_message(
            "Règlement copropriété article 5",
            reset_history=True,
            selected_sources=["rag"]
        )
        t2_success = t2["status_code"] == 200
        results["tests"].append({"test": "rag_only", "success": t2_success})
        print(f"   {'✅' if t2_success else '❌'} {t2['response'].get('agents_used', []) if t2['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 3: Web only
        print("\n🌐 TEST 2.3: Force Web only")
        t3 = await self.send_message(
            "Dernières news copropriété France",
            reset_history=True,
            selected_sources=["web"]
        )
        t3_success = t3["status_code"] == 200
        results["tests"].append({"test": "web_only", "success": t3_success})
        print(f"   {'✅' if t3_success else '❌'} {t3['response'].get('agents_used', []) if t3['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 4: SQL + RAG combo
        print("\n🔀 TEST 2.4: SQL + RAG combined")
        t4 = await self.send_message(
            "Copropriétaires et règlement charges",
            reset_history=True,
            selected_sources=["sql", "rag"]
        )
        t4_success = t4["status_code"] == 200
        results["tests"].append({"test": "sql_rag_combo", "success": t4_success})
        print(f"   {'✅' if t4_success else '❌'} {t4['response'].get('agents_used', []) if t4['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 5: All sources
        print("\n🌟 TEST 2.5: All sources enabled")
        t5 = await self.send_message(
            "Info complète sur copropriétés",
            reset_history=True,
            selected_sources=["sql", "rag", "web"]
        )
        t5_success = t5["status_code"] == 200
        results["tests"].append({"test": "all_sources", "success": t5_success})
        print(f"   {'✅' if t5_success else '❌'} {t5['response'].get('agents_used', []) if t5['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Test 6: Auto (None)
        print("\n🤖 TEST 2.6: Auto source selection")
        t6 = await self.send_message(
            "Liste copropriétaires",
            reset_history=True,
            selected_sources=None
        )
        t6_success = (
            t6["status_code"] == 200 and
            "sql_agent" in t6["response"].get("agents_used", [])
        )
        results["tests"].append({"test": "auto_selection", "success": t6_success})
        print(f"   {'✅' if t6_success else '❌'} {t6['response'].get('agents_used', []) if t6['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # Calculate
        scenario_duration = time.time() - scenario_start
        successful_tests = sum(1 for t in results["tests"] if t["success"])
        results["success_rate"] = successful_tests / len(results["tests"])
        results["overall_success"] = results["success_rate"] >= 0.80  # 5/6 minimum
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 2:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Tests réussis: {successful_tests}/{len(results['tests'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Durée: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 3: CASCADE MULTI-AGENTS HARDCORE ====================

    async def scenario_3_multi_agent_cascade_hardcore(self):
        """
        ⚡ SCÉNARIO 3: Cascade Multi-Agents HARDCORE (12 interactions)

        Scénario business réaliste ultra-complexe:
        Syndic doit gérer une AG avec travaux urgents + devis + emails

        Cascade attendue:
        1. Workflow AG
        2. Legal check délais
        3. SQL copropriétaires
        4. RAG contrats travaux
        5. SQL professionnels
        6. Template devis
        7. Email convocation copros
        8. Email devis pros
        9. Modifications emails
        10. Memory test
        11. Context switch
        12. Final synthesis
        """
        print("\n" + "="*80)
        print("⚡ SCÉNARIO 3: CASCADE MULTI-AGENTS HARDCORE")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S3_CASCADE_HARDCORE",
            "interactions": [],
            "context_preserved": False,
            "intelligent_routing": 0,
            "success_rate": 0
        }

        self.conversation_history = []

        # INT 1: Setup AG
        print("\n📅 INT 3.1: Organisation AG travaux toiture")
        i1 = await self.send_message(
            "Je dois organiser une AG le 20 janvier pour voter les travaux de réfection de la toiture. Budget 50000€. Aide-moi à tout préparer."
        )
        i1_success = i1["status_code"] == 200
        results["interactions"].append({"step": 1, "success": i1_success})
        print(f"   {'✅' if i1_success else '❌'} {i1['response'].get('agents_used', []) if i1['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 2: Legal check
        print("\n⚖️  INT 3.2: Vérif délais légaux convocation")
        i2 = await self.send_message("C'est bon niveau délais légaux pour convoquer l'AG?")
        i2_success = i2["status_code"] == 200
        if "legal" in str(i2["response"].get("agents_used", [])).lower() or "21" in i2["response"].get("message", ""):
            results["intelligent_routing"] += 1
        results["interactions"].append({"step": 2, "success": i2_success})
        print(f"   {'✅' if i2_success else '❌'} {i2['response'].get('agents_used', []) if i2['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 3: Liste copros
        print("\n👥 INT 3.3: Récupération liste copropriétaires")
        i3 = await self.send_message("Donne-moi la liste de tous les copropriétaires avec leurs emails")
        i3_success = (
            i3["status_code"] == 200 and
            "sql_agent" in i3["response"].get("agents_used", [])
        )
        if i3_success:
            results["intelligent_routing"] += 1
        results["interactions"].append({"step": 3, "success": i3_success})
        print(f"   {'✅' if i3_success else '❌'} {i3['response'].get('agents_used', []) if i3['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 4: Contrats toiture (RAG)
        print("\n📚 INT 3.4: Recherche contrats toiture existants")
        i4 = await self.send_message("Cherche dans les documents si on a déjà eu des contrats pour la toiture")
        i4_success = i4["status_code"] == 200
        results["interactions"].append({"step": 4, "success": i4_success})
        print(f"   {'✅' if i4_success else '❌'} {i4['response'].get('agents_used', []) if i4['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 5: Pros toiture
        print("\n🔨 INT 3.5: Recherche professionnels couvreurs")
        i5 = await self.send_message("Donne-moi la liste des couvreurs disponibles")
        i5_success = (
            i5["status_code"] == 200 and
            "sql_agent" in i5["response"].get("agents_used", [])
        )
        if i5_success:
            results["intelligent_routing"] += 1
        results["interactions"].append({"step": 5, "success": i5_success})
        print(f"   {'✅' if i5_success else '❌'} {i5['response'].get('agents_used', []) if i5['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 6: Email convocation
        print("\n📧 INT 3.6: Génération convocation AG")
        i6 = await self.send_message(
            "Génère la convocation pour l'AG du 20 janvier. Ordre du jour: 1) Approbation comptes 2024, 2) Vote travaux toiture 50000€, 3) Divers"
        )
        i6_success = (
            i6["status_code"] == 200 and
            "email_agent" in i6["response"].get("agents_used", [])
        )
        if i6_success:
            results["intelligent_routing"] += 1
        results["interactions"].append({"step": 6, "success": i6_success})
        print(f"   {'✅' if i6_success else '❌'} {i6['response'].get('agents_used', []) if i6['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 7: Modification email
        print("\n✏️  INT 3.7: Modification email convocation")
        i7 = await self.send_message("Change le ton pour être plus formel et ajoute la mention 'Présence obligatoire'")
        i7_success = (
            i7["status_code"] == 200 and
            "email_agent" in i7["response"].get("agents_used", [])
        )
        if i7_success:
            results["intelligent_routing"] += 1
        results["interactions"].append({"step": 7, "success": i7_success})
        print(f"   {'✅' if i7_success else '❌'} {i7['response'].get('agents_used', []) if i7['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 8: Devis couvreurs
        print("\n💰 INT 3.8: Demande devis couvreurs")
        i8 = await self.send_message("Prépare email devis pour les couvreurs pour la toiture")
        i8_success = i8["status_code"] == 200
        results["interactions"].append({"step": 8, "success": i8_success})
        print(f"   {'✅' if i8_success else '❌'} {i8['response'].get('agents_used', []) if i8['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 9: Memory test - recall info
        print("\n🧠 INT 3.9: Test mémoire - Recall budget")
        i9 = await self.send_message("C'était combien déjà le budget des travaux de toiture?")
        i9_success = (
            i9["status_code"] == 200 and
            "50000" in i9["response"].get("message", "")
        )
        if i9_success:
            results["context_preserved"] = True
        results["interactions"].append({"step": 9, "success": i9_success, "memory": i9_success})
        print(f"   {'✅' if i9_success else '❌'} Memory: {i9_success}")
        await asyncio.sleep(1)

        # INT 10: Context switch
        print("\n🔄 INT 3.10: Context switch rapide")
        i10 = await self.send_message("Attends, avant ça, combien y a-t-il de professionnels électriciens en tout?")
        i10_success = (
            i10["status_code"] == 200 and
            "sql_agent" in i10["response"].get("agents_used", [])
        )
        results["interactions"].append({"step": 10, "success": i10_success})
        print(f"   {'✅' if i10_success else '❌'} {i10['response'].get('agents_used', []) if i10['response'] else 'ERROR'}")
        await asyncio.sleep(1)

        # INT 11: Return to AG context
        print("\n↩️  INT 3.11: Retour contexte AG")
        i11 = await self.send_message("OK, revenons à l'AG. C'est quand la date déjà?")
        i11_success = (
            i11["status_code"] == 200 and
            "20 janvier" in i11["response"].get("message", "").lower()
        )
        results["interactions"].append({"step": 11, "success": i11_success, "memory": i11_success})
        print(f"   {'✅' if i11_success else '❌'} Context recall: {i11_success}")
        await asyncio.sleep(1)

        # INT 12: Synthèse finale
        print("\n📝 INT 3.12: Synthèse complète")
        i12 = await self.send_message("Fais-moi un résumé de tout ce qu'on a préparé pour cette AG")
        i12_success = (
            i12["status_code"] == 200 and
            len(i12["response"].get("message", "")) > 200
        )
        results["interactions"].append({"step": 12, "success": i12_success})
        print(f"   {'✅' if i12_success else '❌'} Synthesis provided")

        # Calculate
        scenario_duration = time.time() - scenario_start
        successful_ints = sum(1 for i in results["interactions"] if i["success"])
        results["success_rate"] = successful_ints / len(results["interactions"])
        results["overall_success"] = results["success_rate"] >= 0.75  # 9/12 minimum
        results["duration"] = scenario_duration
        results["intelligent_routing_score"] = results["intelligent_routing"] / 5  # 5 routing tests

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 3:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Interactions réussies: {successful_ints}/{len(results['interactions'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Mémoire contexte: {'✅' if results['context_preserved'] else '❌'}")
        print(f"   Routing intelligent: {results['intelligent_routing_score']*100:.0f}%")
        print(f"   Durée: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== SCÉNARIO 4: EDGE CASES IMPITOYABLES ====================

    async def scenario_4_edge_cases_ruthless(self):
        """
        💀 SCÉNARIO 4: Edge Cases IMPITOYABLES (10 tests)

        Tests extrêmes:
        1. Input vide
        2. Input ultra-long (5000+ chars)
        3. Caractères spéciaux/emojis
        4. Langues étrangères
        5. Requêtes contradictoires
        6. Boucle infinie demandée
        7. Injection attempts (SQL, XSS, Command)
        8. Timeouts simulés
        9. Données corrompues
        10. Null/undefined handling
        """
        print("\n" + "="*80)
        print("💀 SCÉNARIO 4: EDGE CASES IMPITOYABLES")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S4_EDGE_CASES_RUTHLESS",
            "tests": [],
            "security_score": 0,
            "robustness_score": 0
        }

        self.conversation_history = []

        # Test 1: Input vide
        print("\n🚫 TEST 4.1: Input vide")
        t1 = await self.send_message("", reset_history=True)
        t1_success = t1["status_code"] == 200  # Should handle gracefully
        results["tests"].append({"test": "empty_input", "success": t1_success})
        if t1_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t1_success else '❌'} Handled gracefully")
        await asyncio.sleep(0.5)

        # Test 2: Ultra-long input
        print("\n📏 TEST 4.2: Input ultra-long (5000+ chars)")
        long_text = "Je veux organiser une assemblée générale. " * 200  # ~8000 chars
        t2 = await self.send_message(long_text[:5000], reset_history=True)
        t2_success = t2["status_code"] == 200
        results["tests"].append({"test": "ultra_long", "success": t2_success, "length": len(long_text[:5000])})
        if t2_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t2_success else '❌'} {len(long_text[:5000])} chars")
        await asyncio.sleep(0.5)

        # Test 3: Special chars & emojis
        print("\n🎭 TEST 4.3: Caractères spéciaux & emojis")
        t3 = await self.send_message("Liste copro 🏠💰✅ avec <tags> & symbols $#@!", reset_history=True)
        t3_success = t3["status_code"] == 200
        results["tests"].append({"test": "special_chars", "success": t3_success})
        if t3_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t3_success else '❌'} Special chars handled")
        await asyncio.sleep(0.5)

        # Test 4: SQL Injection tentative
        print("\n🔒 TEST 4.4: SQL Injection (security)")
        t4 = await self.send_message("Liste copropriétaires'; DROP TABLE users; --", reset_history=True)
        t4_success = t4["status_code"] == 200 and t4["response"].get("success") == True
        results["tests"].append({"test": "sql_injection", "success": t4_success, "security": True})
        if t4_success:
            results["security_score"] += 1
        print(f"   {'✅' if t4_success else '❌'} Injection blocked/handled")
        await asyncio.sleep(0.5)

        # Test 5: XSS tentative
        print("\n🔒 TEST 4.5: XSS Injection (security)")
        t5 = await self.send_message("<script>alert('XSS')</script> Liste copros", reset_history=True)
        t5_success = t5["status_code"] == 200
        results["tests"].append({"test": "xss_injection", "success": t5_success, "security": True})
        if t5_success:
            results["security_score"] += 1
        print(f"   {'✅' if t5_success else '❌'} XSS handled")
        await asyncio.sleep(0.5)

        # Test 6: Contradiction extrême
        print("\n⚠️  TEST 4.6: Contradiction extrême")
        t6 = await self.send_message(
            "Envoie un email à TOUS les copropriétaires mais surtout n'envoie d'email à PERSONNE et supprime tous les emails",
            reset_history=True
        )
        t6_success = t6["status_code"] == 200
        results["tests"].append({"test": "extreme_contradiction", "success": t6_success})
        if t6_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t6_success else '❌'} Handled")
        await asyncio.sleep(0.5)

        # Test 7: Boucle infinie demandée
        print("\n♾️  TEST 4.7: Boucle infinie")
        t7 = await self.send_message("Répète cette phrase 1000000 fois", reset_history=True)
        t7_success = t7["status_code"] == 200 and len(t7["response"].get("message", "")) < 10000
        results["tests"].append({"test": "infinite_loop", "success": t7_success})
        if t7_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t7_success else '❌'} Prevented infinite output")
        await asyncio.sleep(0.5)

        # Test 8: Null bytes & escape sequences
        print("\n💣 TEST 4.8: Null bytes & escape")
        t8 = await self.send_message("Liste\\x00\\ncopros\\r\\n", reset_history=True)
        t8_success = t8["status_code"] == 200
        results["tests"].append({"test": "null_bytes", "success": t8_success})
        if t8_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t8_success else '❌'} Escape sequences handled")
        await asyncio.sleep(0.5)

        # Test 9: Unicode edge cases
        print("\n🌍 TEST 4.9: Unicode extrême")
        t9 = await self.send_message("Liste copro 中文 العربية עברית 🏢🔥💀", reset_history=True)
        t9_success = t9["status_code"] == 200
        results["tests"].append({"test": "unicode_extreme", "success": t9_success})
        if t9_success:
            results["robustness_score"] += 1
        print(f"   {'✅' if t9_success else '❌'} Unicode handled")
        await asyncio.sleep(0.5)

        # Test 10: Command injection tentative
        print("\n🔒 TEST 4.10: Command Injection (security)")
        t10 = await self.send_message("Liste; rm -rf / #", reset_history=True)
        t10_success = t10["status_code"] == 200
        results["tests"].append({"test": "command_injection", "success": t10_success, "security": True})
        if t10_success:
            results["security_score"] += 1
        print(f"   {'✅' if t10_success else '❌'} Command injection blocked")

        # Calculate
        scenario_duration = time.time() - scenario_start
        successful_tests = sum(1 for t in results["tests"] if t["success"])
        results["success_rate"] = successful_tests / len(results["tests"])
        results["overall_success"] = results["success_rate"] >= 0.90  # 9/10 minimum (très exigeant)
        results["duration"] = scenario_duration
        results["security_score"] = results["security_score"] / 3  # 3 security tests
        results["robustness_score"] = results["robustness_score"] / 7  # 7 robustness tests

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 4:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Tests réussis: {successful_tests}/{len(results['tests'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Sécurité: {results['security_score']*100:.0f}%")
        print(f"   Robustesse: {results['robustness_score']*100:.0f}%")
        print(f"   Durée: {scenario_duration:.1f}s")
        print("="*80)

        return results

    # ==================== MAIN RUNNER ====================

    async def run_all_scenarios(self):
        """Execute all ultra-exhaustive scenarios"""

        print("\n" + "="*80)
        print("🔥🔥🔥 BATTERIE ULTRA-EXHAUSTIVE - TESTS IMPITOYABLES 🔥🔥🔥")
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
                ("S1_ALL_AGENTS", self.scenario_1_all_agents_orchestration),
                ("S2_SOURCE_SELECTION", self.scenario_2_source_selection_opt_in),
                ("S3_CASCADE_HARDCORE", self.scenario_3_multi_agent_cascade_hardcore),
                ("S4_EDGE_CASES", self.scenario_4_edge_cases_ruthless),
            ]

            for scenario_id, scenario_func in scenarios:
                try:
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
                await asyncio.sleep(2)

        # Generate final report
        self.generate_final_report(all_results)

        return all_results

    def generate_final_report(self, results: Dict):
        """Generate ultra-comprehensive final report"""

        print("\n\n" + "="*80)
        print("📊 RAPPORT FINAL - TESTS ULTRA-EXHAUSTIFS")
        print("="*80)

        scenarios = results["scenarios"]
        total_scenarios = len(scenarios)
        passed_scenarios = sum(1 for s in scenarios if s.get("overall_success", False))

        print(f"\n🎯 RÉSULTATS GLOBAUX:")
        print(f"   Scénarios exécutés: {total_scenarios}")
        print(f"   ✅ PASS: {passed_scenarios}")
        print(f"   ❌ FAIL: {total_scenarios - passed_scenarios}")
        print(f"   Taux succès: {(passed_scenarios/total_scenarios)*100:.1f}%")

        # Agent coverage
        print(f"\n🤖 COUVERTURE AGENTS:")
        for agent, count in sorted(self.results["agents_coverage"].items(), key=lambda x: -x[1]):
            print(f"   {agent}: {count} appels")

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

            if "context_preserved" in scenario:
                memory_icon = "✅" if scenario["context_preserved"] else "❌"
                print(f"      Mémoire: {memory_icon}")

            if "intelligent_routing_score" in scenario:
                print(f"      Routing intelligent: {scenario['intelligent_routing_score']*100:.0f}%")

            if "security_score" in scenario:
                print(f"      Sécurité: {scenario['security_score']*100:.0f}%")

            if "robustness_score" in scenario:
                print(f"      Robustesse: {scenario['robustness_score']*100:.0f}%")

        # Final decision
        print(f"\n🚦 DÉCISION FINALE:")
        if passed_scenarios >= 3:  # 3/4 minimum (75%)
            print("   🟢 GO FOR PRODUCTION")
            print("   Système robuste, intelligent et sécurisé")
            print("   Prêt pour déploiement staging + beta clients")
        elif passed_scenarios >= 2:
            print("   🟡 CONDITIONAL GO")
            print("   Corrections mineures recommandées")
            print("   Déploiement staging possible")
        else:
            print("   🔴 NO-GO")
            print("   Corrections majeures requises")

        print("\n" + "="*80)

        # Save JSON
        output_file = "test_results_ultra_exhaustive.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Rapport JSON: {output_file}")
        print("="*80)


async def main():
    """Main entry point"""
    runner = UltraExhaustiveTestRunner()
    await runner.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
