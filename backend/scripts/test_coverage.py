"""
Test Coverage Report Generator

Generates comprehensive coverage reports for DisruptIQ backend tests.

Usage:
    python scripts/test_coverage.py [options]

Options:
    --unit          Run only unit tests
    --integration   Run only integration tests
    --all           Run all tests (default)
    --html          Generate HTML report
    --badge         Generate coverage badge
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime


def run_command(cmd, description):
    """Run a shell command and return success status"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=False,
            text=True
        )
        print(f"✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e}")
        return False


def generate_coverage_summary():
    """Generate coverage summary from JSON report"""
    coverage_json_path = Path("coverage.json")

    if not coverage_json_path.exists():
        print("⚠️  No coverage.json found. Run tests first.")
        return

    with open(coverage_json_path, "r") as f:
        coverage_data = json.load(f)

    total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)

    print("\n" + "="*60)
    print("📊 COVERAGE SUMMARY")
    print("="*60)
    print(f"Total Coverage: {total_coverage:.2f}%")

    # Get file-level coverage
    files = coverage_data.get("files", {})

    # Critical services to highlight
    critical_services = [
        "app/services/agents/intent_classifier_v4.py",
        "app/services/hybrid_search_service.py",
        "app/services/agents/conversation_state.py",
        "app/api/endpoints/chat.py",
        "app/api/endpoints/documents.py",
        "app/api/endpoints/emails.py",
        "app/api/endpoints/health.py"
    ]

    print("\n🎯 CRITICAL SERVICES COVERAGE:")
    print("-" * 60)

    for service in critical_services:
        if service in files:
            file_coverage = files[service]["summary"]["percent_covered"]
            status = "✅" if file_coverage >= 75 else "⚠️" if file_coverage >= 50 else "❌"
            print(f"{status} {service.split('/')[-1]:40s} {file_coverage:6.2f}%")

    # Top 10 best covered files
    print("\n🏆 TOP 10 BEST COVERED FILES:")
    print("-" * 60)

    sorted_files = sorted(
        files.items(),
        key=lambda x: x[1]["summary"]["percent_covered"],
        reverse=True
    )[:10]

    for filepath, data in sorted_files:
        coverage = data["summary"]["percent_covered"]
        filename = filepath.split("/")[-1]
        print(f"✅ {filename:40s} {coverage:6.2f}%")

    # Bottom 10 least covered files (excluding 0%)
    print("\n⚠️  TOP 10 FILES NEEDING COVERAGE:")
    print("-" * 60)

    files_needing_coverage = [
        (filepath, data)
        for filepath, data in files.items()
        if 0 < data["summary"]["percent_covered"] < 50
    ]

    sorted_low_coverage = sorted(
        files_needing_coverage,
        key=lambda x: x[1]["summary"]["percent_covered"]
    )[:10]

    for filepath, data in sorted_low_coverage:
        coverage = data["summary"]["percent_covered"]
        filename = filepath.split("/")[-1]
        print(f"❌ {filename:40s} {coverage:6.2f}%")

    print("\n" + "="*60)


def generate_badge(coverage):
    """Generate a coverage badge (simple text for now)"""
    badge_text = f"Coverage: {coverage:.1f}%"

    if coverage >= 80:
        color = "brightgreen"
        emoji = "✅"
    elif coverage >= 60:
        color = "yellow"
        emoji = "⚠️"
    else:
        color = "red"
        emoji = "❌"

    print(f"\n{emoji} {badge_text} ({color})")

    # Save badge info
    badge_data = {
        "coverage": coverage,
        "color": color,
        "emoji": emoji,
        "timestamp": datetime.now().isoformat()
    }

    with open("coverage_badge.json", "w") as f:
        json.dump(badge_data, f, indent=2)


def main():
    """Main entry point"""
    args = sys.argv[1:]

    print("\n" + "="*60)
    print("🧪 DisruptIQ Backend - Test Coverage Report")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Determine which tests to run
    if "--unit" in args:
        test_path = "tests/unit"
        test_type = "Unit Tests"
    elif "--integration" in args:
        test_path = "tests/integration"
        test_type = "Integration Tests"
    else:
        test_path = "tests/unit"  # Default to unit tests for now
        test_type = "Unit Tests"

    print(f"Test Type: {test_type}")
    print(f"Test Path: {test_path}")

    # Run tests with coverage
    cmd = f"python -m pytest {test_path} --cov=app --cov-report=html --cov-report=json --cov-report=term-missing -v"

    success = run_command(cmd, f"Running {test_type}")

    if not success:
        print("\n⚠️  Tests failed, but coverage report may still be available")

    # Generate coverage summary
    generate_coverage_summary()

    # Generate badge if requested
    if "--badge" in args:
        try:
            with open("coverage.json", "r") as f:
                coverage_data = json.load(f)
                total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
                generate_badge(total_coverage)
        except Exception as e:
            print(f"⚠️  Could not generate badge: {e}")

    # Open HTML report if requested
    if "--html" in args:
        import webbrowser
        html_path = Path("htmlcov/index.html").absolute()
        if html_path.exists():
            print(f"\n🌐 Opening coverage report: {html_path}")
            webbrowser.open(f"file://{html_path}")
        else:
            print("\n⚠️  HTML coverage report not found")

    print("\n" + "="*60)
    print("✅ Coverage Report Generation Complete")
    print("="*60)
    print("\nGenerated Files:")
    print("  - htmlcov/index.html    (HTML report)")
    print("  - coverage.json         (JSON data)")
    print("  - coverage.xml          (XML for CI/CD)")

    if "--badge" in args:
        print("  - coverage_badge.json   (Badge data)")

    print("\n💡 Tips:")
    print("  - View HTML report: open htmlcov/index.html")
    print("  - Run with --html flag to auto-open in browser")
    print("  - Run with --badge to generate coverage badge")
    print("  - Target: Increase coverage to 75%+ for critical services")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
