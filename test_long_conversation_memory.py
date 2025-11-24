"""
🧠 TESTS MÉMOIRE & CONVERSATIONS LONGUES
=========================================

Tests exhaustifs de la mémoire contextuelle et des conversations multi-tours.

Objectifs:
- Tester la mémoire sur 10+ échanges
- Vérifier la propagation du contexte entre agents
- Tester les rappels d'informations distantes
- Valider le context store (Redis) avec TTL
- Tester les basculements de contexte
"""

import asyncio
import httpx
import time
import json
from typing import List, Dict, Any
from datetime import datetime

BASE_URL = "http://localhost:8000"


class LongConversationMemoryTester:
    """Test runner pour conversations longues et mémoire"""

    def __init__(self):
        self.base_url = BASE_URL
        self.session_id = f"memory_test_{int(time.time())}"
        self.client = None
        self.conversation_history = []
        self.results = {"scenarios": []}

    async def send_message(self, user_input: str, reset_history: bool = False) -> Dict:
        """Send message and track history"""
        if reset_history:
            self.conversation_history = []

        payload = {
            "message": user_input,
            "conversation_history": self.conversation_history,
            "session_id": self.session_id,
            "context": {}
        }

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

            # Update history
            if response.status_code == 200:
                resp_data = response.json()
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({
                    "role": "assistant",
                    "content": resp_data.get("message", "")
                })

            return result

        except Exception as e:
            return {"status_code": 0, "response": None, "error": str(e)}

    async def scenario_1_long_conversation_15_turns(self):
        """
        🧠 SCÉNARIO 1: Conversation longue 15 tours avec rappels mémoire

        Test une conversation réaliste de syndic avec:
        - Informations dispersées sur 15 messages
        - Rappels d'informations distantes (message 3 rappelé au message 12)
        - Basculements de contexte
        - Synthèse finale complète
        """
        print("\n" + "="*80)
        print("🧠 SCÉNARIO 1: CONVERSATION LONGUE 15 TOURS")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S1_LONG_CONVERSATION_15_TURNS",
            "turns": [],
            "memory_recalls": [],
            "success_rate": 0
        }

        self.conversation_history = []

        # Tour 1: Déclaration projet AG travaux
        print("\n📝 Tour 1/15: Déclaration projet")
        t1 = await self.send_message(
            "Je prépare l'AG du 25 février 2024 pour voter travaux toiture 75000€ et ravalement façade 120000€"
        )
        t1_success = t1["status_code"] == 200
        results["turns"].append({"turn": 1, "success": t1_success, "type": "declaration"})
        print(f"   {'✅' if t1_success else '❌'} Déclaration enregistrée")
        await asyncio.sleep(1)

        # Tour 2: Délais légaux
        print("\n⚖️  Tour 2/15: Question délais légaux")
        t2 = await self.send_message("Les délais légaux sont respectés pour cette date?")
        t2_success = t2["status_code"] == 200
        results["turns"].append({"turn": 2, "success": t2_success, "type": "legal"})
        print(f"   {'✅' if t2_success else '❌'} Réponse légale")
        await asyncio.sleep(1)

        # Tour 3: Liste copropriétaires
        print("\n👥 Tour 3/15: Récupération copropriétaires")
        t3 = await self.send_message("Liste tous les copropriétaires avec leurs emails")
        t3_success = t3["status_code"] == 200 and "sql_agent" in t3["response"].get("agents_used", [])
        results["turns"].append({"turn": 3, "success": t3_success, "type": "sql_query"})
        print(f"   {'✅' if t3_success else '❌'} Copropriétaires récupérés")
        await asyncio.sleep(1)

        # Tour 4: Recherche couvreurs
        print("\n🔨 Tour 4/15: Recherche couvreurs toiture")
        t4 = await self.send_message("Trouve les meilleurs couvreurs disponibles")
        t4_success = t4["status_code"] == 200
        results["turns"].append({"turn": 4, "success": t4_success, "type": "search_pros"})
        print(f"   {'✅' if t4_success else '❌'} Couvreurs trouvés")
        await asyncio.sleep(1)

        # Tour 5: Email devis couvreurs
        print("\n📧 Tour 5/15: Email devis couvreurs")
        t5 = await self.send_message("Génère email pour demander devis aux couvreurs pour la toiture")
        t5_success = t5["status_code"] == 200 and "email_agent" in t5["response"].get("agents_used", [])
        results["turns"].append({"turn": 5, "success": t5_success, "type": "email_gen"})
        print(f"   {'✅' if t5_success else '❌'} Email généré")
        await asyncio.sleep(1)

        # Tour 6: Rappel mémoire - budget toiture (info du tour 1)
        print("\n🧠 Tour 6/15: RAPPEL MÉMOIRE - Budget toiture")
        t6 = await self.send_message("C'était combien le budget pour les travaux de toiture déjà?")
        t6_success = t6["status_code"] == 200 and "75000" in t6["response"].get("message", "")
        results["turns"].append({"turn": 6, "success": t6_success, "type": "memory_recall"})
        results["memory_recalls"].append({
            "turn": 6,
            "recalls_from_turn": 1,
            "info": "budget toiture 75000€",
            "success": t6_success
        })
        print(f"   {'✅ MÉMOIRE OK' if t6_success else '❌ MÉMOIRE FAIL'} - Rappel budget 75000€")
        await asyncio.sleep(1)

        # Tour 7: Recherche peintres façade
        print("\n🎨 Tour 7/15: Recherche peintres ravalement")
        t7 = await self.send_message("Trouve maintenant des peintres pour le ravalement de façade")
        t7_success = t7["status_code"] == 200
        results["turns"].append({"turn": 7, "success": t7_success, "type": "search_pros"})
        print(f"   {'✅' if t7_success else '❌'} Peintres trouvés")
        await asyncio.sleep(1)

        # Tour 8: Email devis peintres
        print("\n📧 Tour 8/15: Email devis peintres")
        t8 = await self.send_message("Génère email devis pour les peintres")
        t8_success = t8["status_code"] == 200 and "email_agent" in t8["response"].get("agents_used", [])
        results["turns"].append({"turn": 8, "success": t8_success, "type": "email_gen"})
        print(f"   {'✅' if t8_success else '❌'} Email généré")
        await asyncio.sleep(1)

        # Tour 9: Basculement contexte - Question règlement
        print("\n🔄 Tour 9/15: BASCULEMENT - Règlement copropriété")
        t9 = await self.send_message("Au fait, que dit le règlement sur les travaux de façade?")
        t9_success = t9["status_code"] == 200
        results["turns"].append({"turn": 9, "success": t9_success, "type": "context_switch"})
        print(f"   {'✅' if t9_success else '❌'} Basculement contexte OK")
        await asyncio.sleep(1)

        # Tour 10: Retour contexte AG
        print("\n↩️  Tour 10/15: RETOUR contexte AG")
        t10 = await self.send_message("OK, revenons à l'AG. On a envoyé combien d'emails devis au total?")
        t10_success = t10["status_code"] == 200 and ("2" in t10["response"].get("message", "") or "deux" in t10["response"].get("message", "").lower())
        results["turns"].append({"turn": 10, "success": t10_success, "type": "memory_recall"})
        results["memory_recalls"].append({
            "turn": 10,
            "recalls_from_turn": "5 et 8",
            "info": "2 emails devis (couvreurs + peintres)",
            "success": t10_success
        })
        print(f"   {'✅ MÉMOIRE OK' if t10_success else '❌ MÉMOIRE FAIL'} - Rappel 2 emails")
        await asyncio.sleep(1)

        # Tour 11: Convocation AG
        print("\n📧 Tour 11/15: Génération convocation AG")
        t11 = await self.send_message(
            "Génère maintenant la convocation pour l'AG avec ordre du jour complet"
        )
        t11_success = t11["status_code"] == 200 and "email_agent" in t11["response"].get("agents_used", [])
        results["turns"].append({"turn": 11, "success": t11_success, "type": "email_gen"})
        print(f"   {'✅' if t11_success else '❌'} Convocation générée")
        await asyncio.sleep(1)

        # Tour 12: Rappel mémoire distant - Date AG (info du tour 1)
        print("\n🧠 Tour 12/15: RAPPEL MÉMOIRE DISTANT - Date AG")
        t12 = await self.send_message("Rappelle-moi la date de l'AG?")
        t12_success = t12["status_code"] == 200 and ("25 février" in t12["response"].get("message", "") or "25/02" in t12["response"].get("message", ""))
        results["turns"].append({"turn": 12, "success": t12_success, "type": "memory_recall"})
        results["memory_recalls"].append({
            "turn": 12,
            "recalls_from_turn": 1,
            "info": "date AG 25 février 2024",
            "success": t12_success
        })
        print(f"   {'✅ MÉMOIRE OK' if t12_success else '❌ MÉMOIRE FAIL'} - Rappel date 25 février")
        await asyncio.sleep(1)

        # Tour 13: Prix marché web
        print("\n🌐 Tour 13/15: Vérification prix marché")
        t13 = await self.send_message("Cherche sur internet les prix moyens pour ravalement façade 2024")
        t13_success = t13["status_code"] == 200
        results["turns"].append({"turn": 13, "success": t13_success, "type": "web_search"})
        print(f"   {'✅' if t13_success else '❌'} Prix marché trouvés")
        await asyncio.sleep(1)

        # Tour 14: Rappel budget ravalement (info du tour 1)
        print("\n🧠 Tour 14/15: RAPPEL - Budget ravalement")
        t14 = await self.send_message("Le budget prévu pour le ravalement c'était combien?")
        t14_success = t14["status_code"] == 200 and "120000" in t14["response"].get("message", "")
        results["turns"].append({"turn": 14, "success": t14_success, "type": "memory_recall"})
        results["memory_recalls"].append({
            "turn": 14,
            "recalls_from_turn": 1,
            "info": "budget ravalement 120000€",
            "success": t14_success
        })
        print(f"   {'✅ MÉMOIRE OK' if t14_success else '❌ MÉMOIRE FAIL'} - Rappel budget 120000€")
        await asyncio.sleep(1)

        # Tour 15: Synthèse COMPLÈTE
        print("\n📝 Tour 15/15: SYNTHÈSE COMPLÈTE")
        t15 = await self.send_message(
            "Fais-moi une synthèse complète de tout ce qu'on a préparé pour cette AG: dates, budgets, pros contactés, emails envoyés"
        )
        t15_success = (
            t15["status_code"] == 200 and
            len(t15["response"].get("message", "")) > 400 and
            ("25" in t15["response"].get("message", "") or "février" in t15["response"].get("message", "").lower())
        )
        results["turns"].append({"turn": 15, "success": t15_success, "type": "synthesis"})
        print(f"   {'✅ SYNTHÈSE OK' if t15_success else '❌ SYNTHÈSE FAIL'} - Longueur: {len(t15['response'].get('message', '')) if t15['response'] else 0} chars")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_turns = sum(1 for t in results["turns"] if t["success"])
        successful_recalls = sum(1 for r in results["memory_recalls"] if r["success"])

        results["success_rate"] = successful_turns / len(results["turns"])
        results["memory_recall_rate"] = successful_recalls / len(results["memory_recalls"]) if results["memory_recalls"] else 0
        results["overall_success"] = results["success_rate"] >= 0.80 and results["memory_recall_rate"] >= 0.75
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 1:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Tours réussis: {successful_turns}/{len(results['turns'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Rappels mémoire: {successful_recalls}/{len(results['memory_recalls'])} ({results['memory_recall_rate']*100:.0f}%)")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    async def scenario_2_context_store_ttl_test(self):
        """
        ⏱️  SCÉNARIO 2: Test Context Store avec TTL (3 phases)

        Teste le comportement du context store Redis avec TTL 30min:
        - Phase 1: Stockage contexte
        - Phase 2: Rappel immédiat (< 1min)
        - Phase 3: Simulation attente (check si contexte toujours là)
        """
        print("\n" + "="*80)
        print("⏱️  SCÉNARIO 2: CONTEXT STORE TTL TEST")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S2_CONTEXT_STORE_TTL",
            "phases": [],
            "success_rate": 0
        }

        self.conversation_history = []

        # Phase 1: Stockage contexte workflow
        print("\n💾 Phase 1/3: Stockage contexte workflow")
        p1 = await self.send_message(
            "URGENT: Panne électrique générale dans les Mimosas, tous étages touchés, contacte électriciens immédiatement",
            reset_history=True
        )
        p1_success = p1["status_code"] == 200
        results["phases"].append({"phase": 1, "success": p1_success, "type": "storage"})
        print(f"   {'✅' if p1_success else '❌'} Contexte workflow stocké")
        await asyncio.sleep(2)

        # Phase 2: Rappel immédiat (< 1min)
        print("\n🔄 Phase 2/3: Rappel immédiat contexte")
        p2 = await self.send_message("Génère email URGENT pour les électriciens avec tous les détails")
        p2_success = (
            p2["status_code"] == 200 and
            "email_agent" in p2["response"].get("agents_used", []) and
            "mimosas" in p2["response"].get("message", "").lower()
        )
        results["phases"].append({"phase": 2, "success": p2_success, "type": "immediate_recall"})
        print(f"   {'✅ CONTEXTE OK' if p2_success else '❌ CONTEXTE PERDU'} - Email utilise contexte workflow")
        await asyncio.sleep(2)

        # Phase 3: Rappel après 10s (toujours < TTL)
        print("\n⏱️  Phase 3/3: Rappel après délai (toujours < TTL)")
        await asyncio.sleep(8)  # Total 10s depuis phase 1
        p3 = await self.send_message("C'était quelle copropriété l'urgence électrique?")
        p3_success = (
            p3["status_code"] == 200 and
            "mimosas" in p3["response"].get("message", "").lower()
        )
        results["phases"].append({"phase": 3, "success": p3_success, "type": "delayed_recall"})
        print(f"   {'✅ MÉMOIRE OK' if p3_success else '❌ MÉMOIRE FAIL'} - Rappel 'Les Mimosas'")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_phases = sum(1 for p in results["phases"] if p["success"])
        results["success_rate"] = successful_phases / len(results["phases"])
        results["overall_success"] = results["success_rate"] == 1.0  # 100% requis
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 2:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Phases réussies: {successful_phases}/{len(results['phases'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    async def scenario_3_multi_context_isolation(self):
        """
        🔒 SCÉNARIO 3: Isolation contextes multiples (3 sessions)

        Teste que les contextes de différents utilisateurs restent isolés
        """
        print("\n" + "="*80)
        print("🔒 SCÉNARIO 3: ISOLATION CONTEXTES MULTIPLES")
        print("="*80)

        scenario_start = time.time()
        results = {
            "scenario_id": "S3_MULTI_CONTEXT_ISOLATION",
            "sessions": [],
            "success_rate": 0
        }

        # Session 1: Syndic A - Urgence eau
        print("\n👤 Session 1: Syndic A - Urgence eau")
        session1_id = f"syndic_a_{int(time.time())}"
        s1_payload = {
            "message": "URGENT: Fuite eau appartement 5, Résidence du Parc",
            "conversation_history": [],
            "session_id": session1_id,
            "context": {}
        }
        s1 = await self.client.post(f"{self.base_url}/api/assistant-v2/chat", json=s1_payload, timeout=120.0)
        s1_success = s1.status_code == 200
        results["sessions"].append({"session": "A", "success": s1_success})
        print(f"   {'✅' if s1_success else '❌'} Session A: Urgence eau enregistrée")
        await asyncio.sleep(1)

        # Session 2: Syndic B - Organisation AG
        print("\n👤 Session 2: Syndic B - Organisation AG")
        session2_id = f"syndic_b_{int(time.time())}"
        s2_payload = {
            "message": "Je prépare AG du 10 avril pour voter travaux ascenseur",
            "conversation_history": [],
            "session_id": session2_id,
            "context": {}
        }
        s2 = await self.client.post(f"{self.base_url}/api/assistant-v2/chat", json=s2_payload, timeout=120.0)
        s2_success = s2.status_code == 200
        results["sessions"].append({"session": "B", "success": s2_success})
        print(f"   {'✅' if s2_success else '❌'} Session B: AG enregistrée")
        await asyncio.sleep(1)

        # Session 3: Syndic C - Recherche pros
        print("\n👤 Session 3: Syndic C - Recherche pros")
        session3_id = f"syndic_c_{int(time.time())}"
        s3_payload = {
            "message": "Trouve jardiniers rating supérieur à 4",
            "conversation_history": [],
            "session_id": session3_id,
            "context": {}
        }
        s3 = await self.client.post(f"{self.base_url}/api/assistant-v2/chat", json=s3_payload, timeout=120.0)
        s3_success = s3.status_code == 200 and "sql_agent" in s3.json().get("agents_used", [])
        results["sessions"].append({"session": "C", "success": s3_success})
        print(f"   {'✅' if s3_success else '❌'} Session C: Recherche jardiniers")
        await asyncio.sleep(1)

        # Test isolation: Session A rappelle son contexte
        print("\n🔐 Test isolation: Session A rappelle son contexte")
        s1_recall_payload = {
            "message": "C'était quel appartement la fuite?",
            "conversation_history": s1.json().get("conversation_history", []),
            "session_id": session1_id,
            "context": {}
        }
        s1_recall = await self.client.post(f"{self.base_url}/api/assistant-v2/chat", json=s1_recall_payload, timeout=120.0)
        s1_recall_success = (
            s1_recall.status_code == 200 and
            "5" in s1_recall.json().get("message", "") and
            "ag" not in s1_recall.json().get("message", "").lower() and  # Ne doit PAS rappeler session B
            "jardinier" not in s1_recall.json().get("message", "").lower()  # Ne doit PAS rappeler session C
        )
        results["sessions"].append({"session": "A_recall", "success": s1_recall_success, "isolation_test": True})
        print(f"   {'✅ ISOLATION OK' if s1_recall_success else '❌ ISOLATION FAIL'} - Session A isolée")

        # Calculate results
        scenario_duration = time.time() - scenario_start
        successful_sessions = sum(1 for s in results["sessions"] if s["success"])
        results["success_rate"] = successful_sessions / len(results["sessions"])
        results["overall_success"] = results["success_rate"] == 1.0  # 100% requis
        results["duration"] = scenario_duration

        print("\n" + "="*80)
        print(f"📊 RÉSULTAT SCÉNARIO 3:")
        print(f"   Status: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
        print(f"   Sessions réussies: {successful_sessions}/{len(results['sessions'])} ({results['success_rate']*100:.0f}%)")
        print(f"   Isolation contexte: {'✅ VALIDATED' if s1_recall_success else '❌ COMPROMISED'}")
        print(f"   Durée totale: {scenario_duration:.1f}s")
        print("="*80)

        return results

    async def run_all_scenarios(self):
        """Execute all memory test scenarios"""

        print("\n" + "="*80)
        print("🧠 TESTS MÉMOIRE & CONVERSATIONS LONGUES")
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
                ("S1_LONG_CONVERSATION", self.scenario_1_long_conversation_15_turns),
                ("S2_CONTEXT_STORE_TTL", self.scenario_2_context_store_ttl_test),
                ("S3_MULTI_CONTEXT_ISOLATION", self.scenario_3_multi_context_isolation),
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

                await asyncio.sleep(2)

        # Generate final report
        self.generate_final_report(all_results)

        return all_results

    def generate_final_report(self, results: Dict):
        """Generate comprehensive final report"""

        print("\n\n" + "="*80)
        print("📊 RAPPORT FINAL - TESTS MÉMOIRE")
        print("="*80)

        scenarios = results["scenarios"]
        total_scenarios = len(scenarios)
        passed_scenarios = sum(1 for s in scenarios if s.get("overall_success", False))

        print(f"\n🎯 RÉSULTATS GLOBAUX:")
        print(f"   Scénarios exécutés: {total_scenarios}")
        print(f"   ✅ PASS: {passed_scenarios}")
        print(f"   ❌ FAIL: {total_scenarios - passed_scenarios}")
        print(f"   Taux succès: {(passed_scenarios/total_scenarios)*100:.1f}%")

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

            if "memory_recall_rate" in scenario:
                print(f"      Rappels mémoire: {scenario['memory_recall_rate']*100:.0f}%")

        # Final decision
        print(f"\n🚦 DÉCISION FINALE:")
        if passed_scenarios == total_scenarios:
            print("   🟢 EXCELLENT - Mémoire parfaite")
            print("   Système conserve parfaitement le contexte")
            print("   Context store fonctionne impeccablement")
        elif passed_scenarios >= total_scenarios * 0.90:
            print("   🟢 TRÈS BON - Mémoire fiable")
            print("   Quelques améliorations mineures possibles")
        elif passed_scenarios >= total_scenarios * 0.70:
            print("   🟡 ACCEPTABLE - Mémoire OK")
            print("   Corrections recommandées")
        else:
            print("   🔴 PROBLÉMATIQUE - Mémoire défaillante")
            print("   Corrections majeures requises")

        print("\n" + "="*80)

        # Save JSON
        output_file = "test_results_long_conversation_memory.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Rapport JSON: {output_file}")
        print("="*80)


async def main():
    """Main entry point"""
    tester = LongConversationMemoryTester()
    await tester.run_all_scenarios()


if __name__ == "__main__":
    asyncio.run(main())
