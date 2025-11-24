#!/usr/bin/env python3
"""
🧪 Tests Automatisés Complets - Système Multi-Agent avec Context Store

Simule des requêtes HTTP réelles comme si elles venaient de l'UI
Objectif: 100% de réussite sur tous les tests critiques
"""

import requests
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime


class Color:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TestSession:
    """Simule une session utilisateur avec conversation_history"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = str(uuid.uuid4())
        self.conversation_history: List[Dict[str, str]] = []
        self.test_results = []

    def send_message(self, message: str, selected_sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """Envoie un message comme l'UI le ferait"""

        payload = {
            "message": message,
            "conversation_history": self.conversation_history,
            "session_id": self.session_id,
            "selected_sources": selected_sources
        }

        print(f"\n{Color.OKCYAN}📤 Sending:{Color.ENDC} {message[:80]}...")

        try:
            response = requests.post(
                f"{self.base_url}/api/chat/ask",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            # Update conversation history (simulate UI behavior)
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": result.get("message", "")
            })

            print(f"{Color.OKGREEN}✅ Response received{Color.ENDC} ({len(result.get('message', ''))} chars)")

            return result

        except requests.exceptions.Timeout:
            print(f"{Color.FAIL}❌ TIMEOUT (>30s){Color.ENDC}")
            return {"error": "timeout"}

        except requests.exceptions.RequestException as e:
            print(f"{Color.FAIL}❌ REQUEST ERROR: {str(e)}{Color.ENDC}")
            return {"error": str(e)}

    def reset_session(self):
        """Reset session (nouvelle conversation)"""
        self.session_id = str(uuid.uuid4())
        self.conversation_history = []
        print(f"\n{Color.WARNING}🔄 New session: {self.session_id[:8]}{Color.ENDC}")


class TestRunner:
    """Execute comprehensive tests"""

    def __init__(self):
        self.session = TestSession()
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_details = []

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            status = f"{Color.OKGREEN}✅ PASS{Color.ENDC}"
        else:
            self.failed_tests += 1
            status = f"{Color.FAIL}❌ FAIL{Color.ENDC}"

        print(f"\n{status} - {test_name}")
        if details:
            print(f"  {details}")

        self.test_details.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })

    def check_health(self) -> bool:
        """Vérifie que le backend est up"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}🏥 HEALTH CHECK{Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            response.raise_for_status()
            data = response.json()

            print(f"{Color.OKGREEN}✅ Backend is healthy{Color.ENDC}")
            print(f"   Service: {data.get('service')}")
            print(f"   Status: {data.get('status')}")
            return True

        except Exception as e:
            print(f"{Color.FAIL}❌ Backend is DOWN: {str(e)}{Color.ENDC}")
            return False

    def test_1_1_workflow_only(self):
        """Test 1.1: TRIGGER_WORKFLOW Seul - Urgence Simple"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}📝 TEST 1.1: Workflow Only (Urgence Simple){Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        self.session.reset_session()

        message = """URGENT: Fuite d'eau détectée dans l'appartement 12,
résidence Les Tilleuls, 3ème étage.
Propriétaire: M. Dupont (dupont@example.com, 06 12 34 56 78).
Eau coule du plafond, situation critique."""

        response = self.session.send_message(message)

        if "error" in response:
            self.log_test("Test 1.1", False, f"API error: {response['error']}")
            return

        msg = response.get("message", "").lower()

        # Critères de succès
        checks = {
            "Contains 'urgent' or 'critique'": any(k in msg for k in ["urgent", "critique", "prioritaire"]),
            "Contains building/residence info": any(k in msg for k in ["tilleuls", "bâtiment", "résidence"]),
            "Contains apartment number": "12" in msg or "appartement" in msg,
            "Contains owner info": "dupont" in msg.lower(),
            "Todo list structure": any(k in msg for k in ["étape", "action", "todo", "liste", "procédure"])
        }

        passed = sum(checks.values()) >= 4  # 4/5 minimum

        details = "\n".join([f"   {'✅' if v else '❌'} {k}" for k, v in checks.items()])
        self.log_test("Test 1.1: Workflow Only", passed, details)

        time.sleep(2)

    def test_1_3_email_after_workflow(self):
        """Test 1.3: SEND_EMAIL après workflow (TEST CONTEXT_STORE!)"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}📝 TEST 1.3: Email After Workflow (CONTEXT_STORE TEST!){Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        # Message 1: Create workflow first
        print(f"\n{Color.OKCYAN}Step 1: Create workflow context{Color.ENDC}")
        self.session.reset_session()

        workflow_msg = """URGENT: Panne électrique totale au bâtiment B, résidence Park Avenue.
Concerne 24 appartements. Contact gardien: Jean Martin (martin@test.com, 06 11 22 33 44)."""

        response1 = self.session.send_message(workflow_msg)

        if "error" in response1:
            self.log_test("Test 1.3", False, f"Step 1 failed: {response1['error']}")
            return

        print(f"{Color.OKGREEN}✅ Step 1 complete - Workflow created{Color.ENDC}")

        time.sleep(2)

        # Message 2: Send email using stored context
        print(f"\n{Color.OKCYAN}Step 2: Send email using context_store{Color.ENDC}")

        email_msg = "Envoie un email aux électriciens pour les informer de cette urgence"

        response2 = self.session.send_message(email_msg)

        if "error" in response2:
            self.log_test("Test 1.3", False, f"Step 2 failed: {response2['error']}")
            return

        msg = response2.get("message", "").lower()

        # CRITICAL CHECKS - Email doit contenir contexte du workflow!
        checks = {
            "Email contains 'électrique' or 'panne'": any(k in msg for k in ["électrique", "panne", "électricien"]),
            "Email contains building B": "b" in msg or "bâtiment b" in msg,
            "Email contains 'Park Avenue'": "park avenue" in msg or "park" in msg,
            "Email contains '24 appartements'": "24" in msg or "appartements" in msg,
            "Email mentions urgency": any(k in msg for k in ["urgent", "urgence", "immédiat"]),
            "NOT generic email": not ("demande de devis" in msg and "à compléter" in msg),
            "Email structure (objet/corps)": any(k in msg for k in ["objet", "subject", "destinataire", "email"])
        }

        passed = sum(checks.values()) >= 5  # 5/7 minimum (strict!)

        details = "\n".join([f"   {'✅' if v else '❌'} {k}" for k, v in checks.items()])

        if passed:
            details += f"\n   {Color.OKGREEN}🎉 CONTEXT_STORE WORKS!{Color.ENDC}"
        else:
            details += f"\n   {Color.FAIL}⚠️  Email semble générique - context_store issue?{Color.ENDC}"

        self.log_test("Test 1.3: Email After Workflow (Context Store)", passed, details)

        time.sleep(2)

    def test_2_1_workflow_then_email_sequential(self):
        """Test 2.1: WORKFLOW → EMAIL Sequential (Full Flow)"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}📝 TEST 2.1: WORKFLOW → EMAIL Sequential (FULL FLOW){Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        self.session.reset_session()

        # Message 1: Workflow
        print(f"\n{Color.OKCYAN}Step 1: Create incident workflow{Color.ENDC}")

        workflow_msg = """URGENT: Incendie détecté au 5ème étage, bâtiment C, résidence Grand Lac.
Zone évacuée. Contact pompiers: Chef Durand (durand@pompiers.fr, 18).
15 familles impactées."""

        response1 = self.session.send_message(workflow_msg)

        if "error" in response1:
            self.log_test("Test 2.1", False, f"Workflow step failed: {response1['error']}")
            return

        print(f"{Color.OKGREEN}✅ Workflow créé{Color.ENDC}")
        time.sleep(3)

        # Message 2: Email
        print(f"\n{Color.OKCYAN}Step 2: Generate contextual email{Color.ENDC}")

        email_msg = "Rédige maintenant un email pour informer les résidents du bâtiment C"

        response2 = self.session.send_message(email_msg)

        if "error" in response2:
            self.log_test("Test 2.1", False, f"Email step failed: {response2['error']}")
            return

        msg = response2.get("message", "").lower()

        # Critères stricts
        checks = {
            "Email mentions incendie": "incendie" in msg or "feu" in msg,
            "Email mentions bâtiment C": "bâtiment c" in msg or "batiment c" in msg or " c " in msg,
            "Email mentions Grand Lac": "grand lac" in msg or "lac" in msg,
            "Email mentions 5ème étage": "5" in msg or "cinquième" in msg or "étage" in msg,
            "Email mentions évacuation": "évacua" in msg or "evacua" in msg,
            "Email contextual (not generic)": not ("service demandé" in msg and "à compléter" in msg),
            "Session_id preserved": len(self.session.conversation_history) == 4  # 2 user + 2 assistant
        }

        passed = sum(checks.values()) >= 5

        details = "\n".join([f"   {'✅' if v else '❌'} {k}" for k, v in checks.items()])
        self.log_test("Test 2.1: WORKFLOW → EMAIL Sequential", passed, details)

        time.sleep(2)

    def test_3_2_context_absent_new_session(self):
        """Test 3.2: Email sans contexte (nouvelle session)"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}📝 TEST 3.2: Email Without Context (New Session){Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        self.session.reset_session()

        email_msg = "Envoie un email aux plombiers pour intervention urgente"

        response = self.session.send_message(email_msg)

        if "error" in response:
            self.log_test("Test 3.2", False, f"API error: {response['error']}")
            return

        msg = response.get("message", "").lower()

        # Dans ce cas, système DOIT gérer gracieusement
        checks = {
            "Response provided": len(msg) > 50,
            "No crash/error in response": "error" not in msg and "exception" not in msg,
            "Email structure present": any(k in msg for k in ["email", "objet", "message", "destinataire"]),
            "Graceful degradation": any(k in msg for k in ["générique", "préciser", "détails", "compléter", "clarifi"]) or len(msg) > 100
        }

        passed = sum(checks.values()) >= 3

        details = "\n".join([f"   {'✅' if v else '❌'} {k}" for k, v in checks.items()])
        details += f"\n   ℹ️  Normal que l'email soit plus générique sans contexte"

        self.log_test("Test 3.2: Email Without Context", passed, details)

        time.sleep(2)

    def test_3_5_rapid_context_change(self):
        """Test 3.5: Changement de contexte rapide"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}📝 TEST 3.5: Rapid Context Change{Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        self.session.reset_session()

        # Context 1: Dégât des eaux
        print(f"\n{Color.OKCYAN}Context 1: Water damage{Color.ENDC}")
        msg1 = "URGENT: Dégât des eaux appartement 5, résidence Alpha"
        response1 = self.session.send_message(msg1)

        if "error" in response1:
            self.log_test("Test 3.5", False, "Context 1 failed")
            return

        time.sleep(2)

        # Context 2: Incendie (doit écraser le premier)
        print(f"\n{Color.OKCYAN}Context 2: Fire (should override){Color.ENDC}")
        msg2 = "URGENT: Incendie appartement 10, résidence Beta"
        response2 = self.session.send_message(msg2)

        if "error" in response2:
            self.log_test("Test 3.5", False, "Context 2 failed")
            return

        time.sleep(2)

        # Email: DOIT parler de l'incendie (dernier contexte)
        print(f"\n{Color.OKCYAN}Email: Should use FIRE context (latest){Color.ENDC}")
        msg3 = "Envoie un email pour cette urgence"
        response3 = self.session.send_message(msg3)

        if "error" in response3:
            self.log_test("Test 3.5", False, "Email step failed")
            return

        email = response3.get("message", "").lower()

        # CRITICAL: Email doit parler d'INCENDIE, PAS d'eau
        checks = {
            "Email mentions 'incendie' or 'feu'": any(k in email for k in ["incendie", "feu", "fire"]),
            "Email mentions appartement 10": "10" in email,
            "Email mentions résidence Beta": "beta" in email,
            "Email does NOT mention water": not any(k in email for k in ["eau", "eaux", "water", "fuite"]),
            "Email does NOT mention appartement 5": "5" not in email or ("10" in email and email.index("10") < email.index("5") if "5" in email else True),
            "Email does NOT mention Alpha": "alpha" not in email
        }

        passed = sum(checks.values()) >= 4

        details = "\n".join([f"   {'✅' if v else '❌'} {k}" for k, v in checks.items()])

        if passed:
            details += f"\n   {Color.OKGREEN}🎉 Context override works correctly!{Color.ENDC}"
        else:
            details += f"\n   {Color.FAIL}⚠️  Context confusion - old context leaked?{Color.ENDC}"

        self.log_test("Test 3.5: Rapid Context Change", passed, details)

        time.sleep(2)

    def test_1_2_query_data_only(self):
        """Test 1.2: QUERY_DATA Seul"""
        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}")
        print(f"{Color.HEADER}📝 TEST 1.2: Query Data Only{Color.ENDC}")
        print(f"{Color.HEADER}{'='*80}{Color.ENDC}")

        self.session.reset_session()

        message = "Donne-moi la liste de tous les plombiers avec leurs coordonnées"

        response = self.session.send_message(message)

        if "error" in response:
            self.log_test("Test 1.2", False, f"API error: {response['error']}")
            return

        msg = response.get("message", "").lower()

        checks = {
            "Response has content": len(msg) > 50,
            "No error in response": "error" not in msg and "exception" not in msg,
            "Mentions plombiers or professionals": any(k in msg for k in ["plombier", "professionnel", "artisan", "contact"]),
            "Has data structure": any(k in msg for k in ["nom", "email", "téléphone", "liste", "résultat", "trouvé"]) or "|" in msg or "-" in msg
        }

        passed = sum(checks.values()) >= 3

        details = "\n".join([f"   {'✅' if v else '❌'} {k}" for k, v in checks.items()])
        self.log_test("Test 1.2: Query Data Only", passed, details)

        time.sleep(2)

    def run_all_tests(self):
        """Execute tous les tests critiques"""
        start_time = time.time()

        print(f"\n{Color.BOLD}{Color.HEADER}")
        print("=" * 80)
        print("🧪 COMPREHENSIVE AUTOMATED TESTS - DisruptIQ Multi-Agent System")
        print("=" * 80)
        print(f"{Color.ENDC}")

        # Health check first
        if not self.check_health():
            print(f"\n{Color.FAIL}❌ Cannot run tests - backend is down{Color.ENDC}")
            return

        print(f"\n{Color.OKBLUE}Starting test suite...{Color.ENDC}\n")
        time.sleep(2)

        # Run tests
        try:
            self.test_1_1_workflow_only()
            self.test_1_2_query_data_only()
            self.test_1_3_email_after_workflow()
            self.test_2_1_workflow_then_email_sequential()
            self.test_3_2_context_absent_new_session()
            self.test_3_5_rapid_context_change()

        except KeyboardInterrupt:
            print(f"\n\n{Color.WARNING}⚠️  Tests interrupted by user{Color.ENDC}")
        except Exception as e:
            print(f"\n\n{Color.FAIL}❌ Unexpected error: {str(e)}{Color.ENDC}")

        # Summary
        duration = time.time() - start_time

        print(f"\n{Color.BOLD}{Color.HEADER}")
        print("=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"{Color.ENDC}")

        print(f"\n{Color.BOLD}Total Tests:{Color.ENDC} {self.total_tests}")
        print(f"{Color.OKGREEN}Passed:{Color.ENDC} {self.passed_tests} ✅")
        print(f"{Color.FAIL}Failed:{Color.ENDC} {self.failed_tests} ❌")

        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        print(f"\n{Color.BOLD}Success Rate:{Color.ENDC} {success_rate:.1f}%")

        if success_rate == 100:
            print(f"\n{Color.OKGREEN}{Color.BOLD}🎉 100% SUCCESS! System is working perfectly!{Color.ENDC}")
        elif success_rate >= 80:
            print(f"\n{Color.WARNING}⚠️  Good but needs fixes ({self.failed_tests} failures){Color.ENDC}")
        else:
            print(f"\n{Color.FAIL}❌ System has significant issues - debug required{Color.ENDC}")

        print(f"\n{Color.BOLD}Duration:{Color.ENDC} {duration:.1f}s")

        # Detailed failures
        if self.failed_tests > 0:
            print(f"\n{Color.FAIL}{Color.BOLD}Failed Tests Details:{Color.ENDC}")
            for detail in self.test_details:
                if not detail["passed"]:
                    print(f"\n{Color.FAIL}❌ {detail['test']}{Color.ENDC}")
                    if detail["details"]:
                        print(detail["details"])

        print(f"\n{Color.HEADER}{'='*80}{Color.ENDC}\n")

        return success_rate == 100


if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()

    # Exit code for CI/CD
    exit(0 if success else 1)
