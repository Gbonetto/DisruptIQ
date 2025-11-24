"""
🚀 SCRIPT D'EXÉCUTION GLOBAL - TESTS EXHAUSTIFS
================================================

Lance TOUS les tests exhaustifs en séquence avec rapport consolidé final.

Tests inclus:
1. test_runner_real_world_exhaustive.py - Conditions réelles syndic (6 scénarios)
2. test_long_conversation_memory.py - Mémoire et conversations longues (3 scénarios)
3. test_runner_ultra_exhaustive.py - Tests API hardcore (4 scénarios)

Total: 13+ scénarios, 100+ tests individuels
Durée estimée: 15-20 minutes
"""

import subprocess
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Any


class ComprehensiveTestOrchestrator:
    """Orchestrateur pour tous les tests exhaustifs"""

    def __init__(self):
        self.results = {
            "timestamp_start": datetime.now().isoformat(),
            "test_suites": [],
            "overall_stats": {}
        }
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

    def run_test_suite(self, script_name: str, description: str) -> Dict[str, Any]:
        """Execute a test suite and return results"""
        print("\n" + "="*80)
        print(f"🚀 LANCEMENT: {description}")
        print(f"   Script: {script_name}")
        print("="*80)

        script_path = os.path.join(self.base_dir, script_name)

        if not os.path.exists(script_path):
            print(f"❌ ERREUR: Script non trouvé - {script_path}")
            return {
                "suite_name": script_name,
                "description": description,
                "success": False,
                "error": "Script not found"
            }

        start_time = time.time()

        try:
            # Run the test script
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=1200  # 20 minutes max
            )

            duration = time.time() - start_time

            # Parse result JSON if available
            json_filename = script_name.replace(".py", "").replace("test_runner_", "test_results_") + ".json"
            json_path = os.path.join(self.base_dir, json_filename)

            suite_results = None
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    suite_results = json.load(f)

            success = result.returncode == 0

            print(f"\n{'✅ SUCCÈS' if success else '❌ ÉCHEC'}")
            print(f"Durée: {duration:.1f}s")
            print(f"Return code: {result.returncode}")

            if not success and result.stderr:
                print(f"\nErreurs:\n{result.stderr[:500]}")

            return {
                "suite_name": script_name,
                "description": description,
                "success": success,
                "duration": duration,
                "return_code": result.returncode,
                "stdout": result.stdout[-1000:] if result.stdout else "",  # Last 1000 chars
                "stderr": result.stderr[-500:] if result.stderr else "",
                "json_results": suite_results
            }

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"\n❌ TIMEOUT après {duration:.1f}s")
            return {
                "suite_name": script_name,
                "description": description,
                "success": False,
                "duration": duration,
                "error": "Timeout"
            }

        except Exception as e:
            duration = time.time() - start_time
            print(f"\n❌ ERREUR: {e}")
            return {
                "suite_name": script_name,
                "description": description,
                "success": False,
                "duration": duration,
                "error": str(e)
            }

    def run_all_tests(self):
        """Execute all test suites"""

        print("\n" + "="*80)
        print("🔥🔥🔥 BATTERIE COMPLÈTE - TESTS EXHAUSTIFS 🔥🔥🔥")
        print("="*80)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Répertoire: {self.base_dir}")
        print("="*80)

        test_suites = [
            {
                "script": "test_runner_real_world_exhaustive.py",
                "description": "Tests Conditions Réelles Syndic",
                "priority": 1
            },
            {
                "script": "test_long_conversation_memory.py",
                "description": "Tests Mémoire et Conversations Longues",
                "priority": 2
            },
            {
                "script": "test_runner_ultra_exhaustive.py",
                "description": "Tests API Ultra-Exhaustifs",
                "priority": 3
            }
        ]

        overall_start = time.time()

        for suite in test_suites:
            result = self.run_test_suite(suite["script"], suite["description"])
            self.results["test_suites"].append(result)

            # Pause entre suites
            print("\n⏸️  Pause 5 secondes avant suite suivante...\n")
            time.sleep(5)

        overall_duration = time.time() - overall_start
        self.results["timestamp_end"] = datetime.now().isoformat()
        self.results["total_duration"] = overall_duration

        # Generate final report
        self.generate_final_report()

    def generate_final_report(self):
        """Generate consolidated final report"""

        print("\n\n" + "="*80)
        print("📊 RAPPORT FINAL CONSOLIDÉ - TOUS LES TESTS")
        print("="*80)

        total_suites = len(self.results["test_suites"])
        successful_suites = sum(1 for s in self.results["test_suites"] if s.get("success", False))
        total_duration = self.results.get("total_duration", 0)

        print(f"\n🎯 RÉSULTATS GLOBAUX:")
        print(f"   Test suites exécutées: {total_suites}")
        print(f"   ✅ Réussies: {successful_suites}")
        print(f"   ❌ Échouées: {total_suites - successful_suites}")
        print(f"   Taux succès: {(successful_suites/total_suites)*100:.1f}%")
        print(f"   Durée totale: {total_duration/60:.1f} minutes")

        # Detailed results per suite
        print(f"\n📈 DÉTAILS PAR SUITE DE TESTS:")

        for suite in self.results["test_suites"]:
            suite_name = suite.get("suite_name", "Unknown")
            description = suite.get("description", "")
            success = suite.get("success", False)
            duration = suite.get("duration", 0)

            status_icon = "✅" if success else "❌"
            print(f"\n   {status_icon} {description}")
            print(f"      Script: {suite_name}")
            print(f"      Durée: {duration:.1f}s")

            # If JSON results available, show detailed stats
            json_results = suite.get("json_results")
            if json_results and "scenarios" in json_results:
                scenarios = json_results["scenarios"]
                passed_scenarios = sum(1 for s in scenarios if s.get("overall_success", False))
                print(f"      Scénarios: {passed_scenarios}/{len(scenarios)} réussis")

        # Aggregated statistics
        total_scenarios = 0
        passed_scenarios = 0
        total_tests = 0
        passed_tests = 0

        for suite in self.results["test_suites"]:
            json_results = suite.get("json_results")
            if json_results and "scenarios" in json_results:
                scenarios = json_results["scenarios"]
                total_scenarios += len(scenarios)
                passed_scenarios += sum(1 for s in scenarios if s.get("overall_success", False))

                # Count individual tests
                for scenario in scenarios:
                    if "tests" in scenario:
                        tests = scenario["tests"]
                        total_tests += len(tests)
                        passed_tests += sum(1 for t in tests if t.get("success", False))
                    elif "turns" in scenario:
                        turns = scenario["turns"]
                        total_tests += len(turns)
                        passed_tests += sum(1 for t in turns if t.get("success", False))

        print(f"\n📊 STATISTIQUES AGRÉGÉES:")
        print(f"   Total scénarios: {total_scenarios}")
        print(f"   Scénarios réussis: {passed_scenarios}")
        print(f"   Taux succès scénarios: {(passed_scenarios/total_scenarios)*100:.1f}%" if total_scenarios > 0 else "   N/A")
        print(f"   Total tests individuels: {total_tests}")
        print(f"   Tests réussis: {passed_tests}")
        print(f"   Taux succès tests: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "   N/A")

        self.results["overall_stats"] = {
            "total_suites": total_suites,
            "successful_suites": successful_suites,
            "total_scenarios": total_scenarios,
            "passed_scenarios": passed_scenarios,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "scenario_success_rate": passed_scenarios / total_scenarios if total_scenarios > 0 else 0,
            "test_success_rate": passed_tests / total_tests if total_tests > 0 else 0
        }

        # Final verdict
        print(f"\n🚦 VERDICT FINAL:")

        suite_success_rate = successful_suites / total_suites
        scenario_success_rate = passed_scenarios / total_scenarios if total_scenarios > 0 else 0

        if suite_success_rate == 1.0 and scenario_success_rate >= 0.95:
            print("   🟢🟢🟢 EXCELLENCE TOTALE")
            print("   ✅ Toutes les suites PASS")
            print("   ✅ 95%+ scénarios réussis")
            print("   🚀 DÉPLOIEMENT PRODUCTION IMMÉDIAT RECOMMANDÉ")
        elif suite_success_rate >= 0.90 and scenario_success_rate >= 0.90:
            print("   🟢🟢 TRÈS BON NIVEAU")
            print("   ✅ 90%+ suites et scénarios réussis")
            print("   🚀 DÉPLOIEMENT PRODUCTION APRÈS VALIDATION")
        elif suite_success_rate >= 0.75 and scenario_success_rate >= 0.80:
            print("   🟢 BON NIVEAU")
            print("   ✅ 75%+ suites, 80%+ scénarios réussis")
            print("   🎯 DÉPLOIEMENT STAGING RECOMMANDÉ")
        elif suite_success_rate >= 0.60 and scenario_success_rate >= 0.70:
            print("   🟡 NIVEAU ACCEPTABLE")
            print("   ⚠️  Corrections recommandées")
            print("   🔧 CORRECTIONS AVANT STAGING")
        else:
            print("   🔴 NIVEAU INSUFFISANT")
            print("   ❌ Corrections majeures requises")
            print("   🛑 NE PAS DÉPLOYER")

        # Recommendations
        print(f"\n💡 RECOMMANDATIONS:")

        failed_suites = [s for s in self.results["test_suites"] if not s.get("success", False)]
        if failed_suites:
            print(f"\n   Suites à corriger:")
            for suite in failed_suites:
                print(f"   - {suite['description']}")
                if "error" in suite:
                    print(f"     Erreur: {suite['error']}")

        if scenario_success_rate < 0.90:
            print(f"\n   Scénarios à améliorer:")
            for suite in self.results["test_suites"]:
                json_results = suite.get("json_results")
                if json_results and "scenarios" in json_results:
                    failed_scenarios = [s for s in json_results["scenarios"] if not s.get("overall_success", False)]
                    if failed_scenarios:
                        print(f"   - {suite['description']}:")
                        for scenario in failed_scenarios[:3]:  # Show max 3
                            print(f"     • {scenario.get('scenario_id', 'Unknown')}")

        print("\n" + "="*80)

        # Save consolidated JSON
        output_file = "test_results_comprehensive_all.json"
        output_path = os.path.join(self.base_dir, output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Rapport consolidé sauvegardé: {output_file}")
        print("="*80)


def main():
    """Main entry point"""
    orchestrator = ComprehensiveTestOrchestrator()
    orchestrator.run_all_tests()


if __name__ == "__main__":
    main()
