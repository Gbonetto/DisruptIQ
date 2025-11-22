"""
Sprint 1 - Template Filter & UI Context Bypass Tests
Validates Level 0 optimization (40% bypass target)

Test Coverage:
- Template Filter: Greetings, thanks, acknowledgments
- UI Context Bypass: UI modes, action buttons, selected docs
- Integration: Full SMA bypass vs classification bypass
"""

import asyncio
import pytest
from app.services.template_filter import TemplateFilter, UIContextBypass
from app.models.intent import IntentType, Domain


class TestTemplateFilter:
    """Test Template Filter (10% bypass target)"""

    def setup_method(self):
        """Setup test instance"""
        self.filter = TemplateFilter()

    # ==================== CANNED RESPONSES (Full Bypass) ====================

    def test_greeting_simple(self):
        """Test simple greeting → canned response"""
        result = self.filter.check("Bonjour")

        assert result is not None
        assert result['bypass_sma'] == True
        assert "Bonjour" in result['response']
        assert result['category'] == 'greeting'
        assert result['method'] == 'template_canned'
        print(f"✅ Greeting: {result['response']}")

    def test_greeting_variants(self):
        """Test greeting variants"""
        greetings = ["bonjour", "Salut", "Hello!", "Hi   ", "hey,"]

        for greeting in greetings:
            result = self.filter.check(greeting)
            assert result is not None, f"Failed for: {greeting}"
            assert result['bypass_sma'] == True
            print(f"✅ {greeting} → {result['response'][:30]}...")

    def test_thanks(self):
        """Test thanks → canned response"""
        thanks_list = ["merci", "Merci!", "Thanks", "thank you"]

        for thanks in thanks_list:
            result = self.filter.check(thanks)
            assert result is not None
            assert result['bypass_sma'] == True
            assert result['category'] == 'thanks'
            print(f"✅ {thanks} → {result['response'][:30]}...")

    def test_acknowledgment(self):
        """Test acknowledgments → canned response"""
        acks = ["ok", "d'accord", "compris", "très bien"]

        for ack in acks:
            result = self.filter.check(ack)
            assert result is not None
            assert result['bypass_sma'] == True
            assert result['category'] == 'acknowledgment'
            print(f"✅ {ack} → Bypass")

    def test_goodbye(self):
        """Test goodbyes → canned response"""
        goodbyes = ["au revoir", "bye", "goodbye", "à bientôt"]

        for goodbye in goodbyes:
            result = self.filter.check(goodbye)
            assert result is not None
            assert result['bypass_sma'] == True
            assert result['category'] == 'goodbye'
            print(f"✅ {goodbye} → {result['response'][:30]}...")

    # ==================== INTENT SHORTCUTS (Classification Bypass) ====================

    def test_help_request(self):
        """Test help request → direct intent"""
        help_queries = ["aide", "help", "?", "aide-moi"]

        for query in help_queries:
            result = self.filter.check(query)
            assert result is not None
            assert result['bypass_sma'] == False  # Run SMA
            assert result['bypass_classification'] == True  # Skip classifier
            assert result['intent'] == IntentType.GENERAL_QUESTION
            assert result['confidence'] == 1.0
            print(f"✅ {query} → GENERAL_QUESTION (skip classification)")

    def test_capabilities_inquiry(self):
        """Test capabilities question → direct intent"""
        result = self.filter.check("que peux-tu faire")

        assert result is not None
        assert result['bypass_classification'] == True
        assert result['intent'] == IntentType.GENERAL_QUESTION
        print(f"✅ Capabilities → GENERAL_QUESTION")

    # ==================== NO MATCH ====================

    def test_no_match_regular_query(self):
        """Test regular query → no match (continue to classification)"""
        queries = [
            "Combien de copropriétaires avons-nous?",
            "Liste-moi les professionnels",
            "Analyse ce contrat",
        ]

        for query in queries:
            result = self.filter.check(query)
            assert result is None, f"Should not match: {query}"
            print(f"✅ {query} → No match (continue to classification)")

    # ==================== STATS ====================

    def test_get_stats(self):
        """Test stats reporting"""
        stats = self.filter.get_stats()

        assert 'canned_patterns' in stats
        assert 'intent_shortcuts' in stats
        assert 'total_templates' in stats
        assert stats['total_templates'] > 0

        print(f"📊 Template Filter Stats:")
        print(f"   Canned patterns: {stats['canned_patterns']}")
        print(f"   Intent shortcuts: {stats['intent_shortcuts']}")
        print(f"   Total templates: {stats['total_templates']}")


class TestUIContextBypass:
    """Test UI Context Bypass (30% bypass target)"""

    def setup_method(self):
        """Setup test instance"""
        self.bypass = UIContextBypass()

    # ==================== UI MODE ====================

    def test_ui_mode_sql(self):
        """Test SQL UI mode → QUERY_DATA"""
        context = {'ui_mode': 'sql_query_builder'}
        result = self.bypass.check(context)

        assert result is not None
        assert result['bypass_classification'] == True
        assert result['intent'] == IntentType.QUERY_DATA
        assert result['confidence'] == 1.0
        assert result['method'] == 'ui_mode'
        print(f"✅ UI Mode: sql_query_builder → QUERY_DATA")

    def test_ui_mode_documents(self):
        """Test document UI mode → SEARCH_DOCUMENTS"""
        modes = ['document_viewer', 'document_search', 'file_explorer']

        for mode in modes:
            context = {'ui_mode': mode}
            result = self.bypass.check(context)

            assert result is not None
            assert result['intent'] == IntentType.SEARCH_DOCUMENTS
            print(f"✅ UI Mode: {mode} → SEARCH_DOCUMENTS")

    def test_ui_mode_email(self):
        """Test email UI mode → SEND_EMAIL"""
        context = {'ui_mode': 'email_composer'}
        result = self.bypass.check(context)

        assert result is not None
        assert result['intent'] == IntentType.SEND_EMAIL
        print(f"✅ UI Mode: email_composer → SEND_EMAIL")

    def test_ui_mode_legal(self):
        """Test legal UI mode → LEGAL"""
        context = {'ui_mode': 'legal_analyzer'}
        result = self.bypass.check(context)

        assert result is not None
        assert result['intent'] == IntentType.LEGAL
        print(f"✅ UI Mode: legal_analyzer → LEGAL")

    # ==================== ACTION BUTTON ====================

    def test_action_button_email(self):
        """Test email action button → SEND_EMAIL"""
        buttons = ['generate_email', 'compose_email', 'send_message']

        for button in buttons:
            context = {'action_button': button}
            result = self.bypass.check(context)

            assert result is not None
            assert result['intent'] == IntentType.SEND_EMAIL
            assert result['method'] == 'ui_button'
            print(f"✅ Action Button: {button} → SEND_EMAIL")

    def test_action_button_quote(self):
        """Test quote action button → REQUEST_QUOTES"""
        context = {'action_button': 'request_quote'}
        result = self.bypass.check(context)

        assert result is not None
        assert result['intent'] == IntentType.REQUEST_QUOTES
        print(f"✅ Action Button: request_quote → REQUEST_QUOTES")

    def test_action_button_search(self):
        """Test search action button → SEARCH_DOCUMENTS"""
        context = {'action_button': 'search_documents'}
        result = self.bypass.check(context)

        assert result is not None
        assert result['intent'] == IntentType.SEARCH_DOCUMENTS
        print(f"✅ Action Button: search_documents → SEARCH_DOCUMENTS")

    # ==================== PRE-SELECTED DOCUMENT ====================

    def test_selected_document(self):
        """Test pre-selected document → SEARCH_DOCUMENTS"""
        context = {'selected_document_id': 123}
        result = self.bypass.check(context)

        assert result is not None
        assert result['intent'] == IntentType.SEARCH_DOCUMENTS
        assert result['confidence'] == 0.95  # Slightly lower
        assert result['method'] == 'ui_document'
        print(f"✅ Selected document → SEARCH_DOCUMENTS (0.95 confidence)")

    def test_active_document(self):
        """Test active document → SEARCH_DOCUMENTS"""
        context = {'active_document_id': 456}
        result = self.bypass.check(context)

        assert result is not None
        assert result['intent'] == IntentType.SEARCH_DOCUMENTS
        print(f"✅ Active document → SEARCH_DOCUMENTS")

    # ==================== NO MATCH ====================

    def test_no_ui_context(self):
        """Test empty context → no match"""
        context = {}
        result = self.bypass.check(context)

        assert result is None
        print(f"✅ Empty context → No match")

    def test_unknown_ui_mode(self):
        """Test unknown UI mode → no match"""
        context = {'ui_mode': 'unknown_mode'}
        result = self.bypass.check(context)

        assert result is None
        print(f"✅ Unknown UI mode → No match")


# ==================== INTEGRATION TESTS ====================

def test_combined_bypass_coverage():
    """
    Test combined bypass coverage

    Target: 40% of queries bypassed
    - Template: ~10% (greetings, thanks, etc.)
    - UI Context: ~30% (when UI provides context)
    """

    template_filter = TemplateFilter()
    ui_bypass = UIContextBypass()

    # Simulate 100 queries
    test_queries = [
        # Template matches (10%)
        ("Bonjour", {}, True, "template"),
        ("merci", {}, True, "template"),
        ("ok", {}, True, "template"),
        ("au revoir", {}, True, "template"),
        ("aide", {}, False, "template_shortcut"),  # Classification bypass only
        ("?", {}, False, "template_shortcut"),

        # UI Context matches (30% when provided)
        ("Requête SQL", {'ui_mode': 'sql_query_builder'}, False, "ui_mode"),
        ("Recherche doc", {'ui_mode': 'document_viewer'}, False, "ui_mode"),
        ("Email syndic", {'ui_mode': 'email_composer'}, False, "ui_mode"),
        ("Analyse légale", {'ui_mode': 'legal_analyzer'}, False, "ui_mode"),
        ("", {'action_button': 'generate_email'}, False, "ui_button"),
        ("", {'action_button': 'request_quote'}, False, "ui_button"),
        ("Question sur doc", {'selected_document_id': 123}, False, "ui_document"),

        # No match (60% - continue to classification)
        ("Combien de copropriétaires?", {}, None, None),
        ("Liste des professionnels", {}, None, None),
        ("Quelle est la jurisprudence?", {}, None, None),
    ]

    full_bypass_count = 0
    classification_bypass_count = 0
    no_bypass_count = 0

    for query, context, expected_full_bypass, bypass_type in test_queries:
        # Check template
        template_result = template_filter.check(query) if query else None

        # Check UI context
        ui_result = ui_bypass.check(context) if context else None

        if template_result and template_result.get('bypass_sma'):
            full_bypass_count += 1
            print(f"✅ Full bypass: {query[:30]} ({bypass_type})")

        elif (template_result and template_result.get('bypass_classification')) or \
             (ui_result and ui_result.get('bypass_classification')):
            classification_bypass_count += 1
            print(f"✅ Classification bypass: {query[:30] or 'UI action'} ({bypass_type})")

        else:
            no_bypass_count += 1
            print(f"⏩ No bypass: {query[:30]} (continue to classification)")

    total = len(test_queries)
    total_bypass = full_bypass_count + classification_bypass_count

    print(f"\n📊 Bypass Coverage:")
    print(f"   Full bypass (SMA): {full_bypass_count}/{total} ({full_bypass_count/total*100:.1f}%)")
    print(f"   Classification bypass: {classification_bypass_count}/{total} ({classification_bypass_count/total*100:.1f}%)")
    print(f"   Total bypass: {total_bypass}/{total} ({total_bypass/total*100:.1f}%)")
    print(f"   No bypass: {no_bypass_count}/{total} ({no_bypass_count/total*100:.1f}%)")

    # Validation
    assert total_bypass >= total * 0.30, f"Target: ≥30% bypass, Got: {total_bypass/total*100:.1f}%"
    print(f"\n✅ Sprint 1 Target Met: {total_bypass/total*100:.1f}% bypass (≥30%)")


if __name__ == "__main__":
    print("=" * 70)
    print("  SPRINT 1 - TEMPLATE FILTER & UI CONTEXT BYPASS TESTS")
    print("=" * 70)
    print()

    # Run tests
    pytest.main([__file__, "-v", "-s"])
