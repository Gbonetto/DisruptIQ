"""
Template Filter - Level 0 Optimization
Bypass classification for common patterns and templates

Philosophy:
- Don't classify what doesn't need classification
- 0ms response for predictable queries
- 40% of queries bypassed

Author: Claude Code - Sprint 1
Date: November 22, 2025
"""

import re
import structlog
from typing import Optional, Dict, Any
from app.models.intent import IntentType, Domain, DataSource, IntentClassification

logger = structlog.get_logger()


class TemplateFilter:
    """
    Level 0: Pre-filter common templates before classification

    Handles:
    1. Greetings & social niceties (canned responses)
    2. Simple help requests (direct to general)
    3. Common patterns (no LLM needed)

    Performance: 0ms, $0
    Coverage: ~10% of queries
    """

    def __init__(self):
        # Canned responses (bypass entire SMA)
        self.CANNED_PATTERNS = {
            # Greetings
            r'^(bonjour|salut|hello|hi|hey|coucou)[\s\!\.\,]*$': {
                'response': 'Bonjour ! 👋 Comment puis-je vous aider avec votre copropriété aujourd\'hui ?',
                'bypass_sma': True,
                'category': 'greeting'
            },
            r'^(bonsoir)[\s\!\.\,]*$': {
                'response': 'Bonsoir ! Comment puis-je vous assister ?',
                'bypass_sma': True,
                'category': 'greeting'
            },

            # Thanks
            r'^(merci|thanks?|thank you)[\s\!\.\,]*$': {
                'response': 'De rien ! 😊 N\'hésitez pas si vous avez d\'autres questions.',
                'bypass_sma': True,
                'category': 'thanks'
            },
            r'^(merci beaucoup|merci bien)[\s\!\.\,]*$': {
                'response': 'Avec plaisir ! Je suis là pour vous aider.',
                'bypass_sma': True,
                'category': 'thanks'
            },

            # Acknowledgments
            r'^(ok|d\'accord|compris|ok merci|très bien)[\s\!\.\,]*$': {
                'response': 'Parfait ! Autre chose que je puisse faire pour vous ?',
                'bypass_sma': True,
                'category': 'acknowledgment'
            },

            # Goodbyes
            r'^(au revoir|bye|goodbye|à bientôt|à plus)[\s\!\.\,]*$': {
                'response': 'Au revoir ! À bientôt pour vos questions de copropriété ! 👋',
                'bypass_sma': True,
                'category': 'goodbye'
            },
        }

        # Intent shortcuts (skip classification but run SMA)
        self.INTENT_SHORTCUTS = {
            # Help requests
            r'^(aide|help|\?|aide[\-\s]moi)[\s\!\.\,]*$': {
                'intent': IntentType.GENERAL_QUESTION,
                'domain': Domain.GENERAL,
                'confidence': 1.0,
                'reasoning': 'Template: help request',
                'bypass_classification': True,
                'category': 'help'
            },

            # Capabilities
            r'^(que peux[\-\s]tu faire|quelles sont tes capacités|comment tu fonctionnes?)[\s\!\.\,]*$': {
                'intent': IntentType.GENERAL_QUESTION,
                'domain': Domain.GENERAL,
                'confidence': 1.0,
                'reasoning': 'Template: capabilities inquiry',
                'bypass_classification': True,
                'category': 'capabilities'
            },
        }

    def check(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Check if query matches a template pattern

        Args:
            user_input: User's raw query

        Returns:
            None: No match, continue to classification
            Dict: Match found with either:
                - 'response': Canned response (bypass entire SMA)
                - 'intent': Direct intent (skip classification only)
        """

        # Normalize input
        query_normalized = user_input.lower().strip()

        # Remove extra whitespace
        query_normalized = re.sub(r'\s+', ' ', query_normalized)

        # Check canned responses first (full bypass)
        for pattern, config in self.CANNED_PATTERNS.items():
            if re.match(pattern, query_normalized, re.IGNORECASE):
                logger.info("template_canned_match",
                           pattern=pattern,
                           category=config.get('category'),
                           bypass_sma=True)

                return {
                    'bypass_sma': True,
                    'response': config['response'],
                    'category': config.get('category'),
                    'level': 0,
                    'method': 'template_canned'
                }

        # Check intent shortcuts (skip classification only)
        for pattern, config in self.INTENT_SHORTCUTS.items():
            if re.match(pattern, query_normalized, re.IGNORECASE):
                logger.info("template_intent_shortcut",
                           pattern=pattern,
                           category=config.get('category'),
                           intent=config['intent'].value,
                           bypass_classification=True)

                return {
                    'bypass_sma': False,
                    'bypass_classification': True,
                    'intent': config['intent'],
                    'domain': config['domain'],
                    'confidence': config['confidence'],
                    'reasoning': config['reasoning'],
                    'category': config.get('category'),
                    'level': 0,
                    'method': 'template_shortcut'
                }

        # No match
        return None

    def get_stats(self) -> Dict[str, int]:
        """Get template counts for monitoring"""
        return {
            'canned_patterns': len(self.CANNED_PATTERNS),
            'intent_shortcuts': len(self.INTENT_SHORTCUTS),
            'total_templates': len(self.CANNED_PATTERNS) + len(self.INTENT_SHORTCUTS)
        }


class UIContextBypass:
    """
    Level 0: Bypass classification when UI context makes intent obvious

    Handles:
    1. UI mode (sql_query_builder, document_viewer, etc.)
    2. Action buttons (generate_email, request_quote, etc.)
    3. Pre-selected context (document_id, user_id, etc.)

    Performance: 0ms, $0
    Coverage: ~30% of queries (when UI provides context)
    """

    def __init__(self):
        # UI Mode → Intent mapping
        self.UI_MODE_INTENT_MAP = {
            'sql_query_builder': IntentType.QUERY_DATA,
            'sql_explorer': IntentType.QUERY_DATA,
            'database_view': IntentType.QUERY_DATA,

            'document_viewer': IntentType.SEARCH_DOCUMENTS,
            'document_search': IntentType.SEARCH_DOCUMENTS,
            'file_explorer': IntentType.SEARCH_DOCUMENTS,

            'email_composer': IntentType.SEND_EMAIL,
            'email_generator': IntentType.SEND_EMAIL,

            'quote_request': IntentType.REQUEST_QUOTES,
            'vendor_finder': IntentType.REQUEST_QUOTES,

            'legal_analyzer': IntentType.LEGAL,
            'contract_review': IntentType.LEGAL,

            'web_search': IntentType.WEB_SEARCH,
            'internet_search': IntentType.WEB_SEARCH,
        }

        # Action Button → Intent mapping
        self.ACTION_BUTTON_INTENT_MAP = {
            'generate_email': IntentType.SEND_EMAIL,
            'compose_email': IntentType.SEND_EMAIL,
            'send_message': IntentType.SEND_EMAIL,

            'request_quote': IntentType.REQUEST_QUOTES,
            'find_vendor': IntentType.REQUEST_QUOTES,
            'get_estimate': IntentType.REQUEST_QUOTES,

            'search_documents': IntentType.SEARCH_DOCUMENTS,
            'find_in_files': IntentType.SEARCH_DOCUMENTS,

            'run_query': IntentType.QUERY_DATA,
            'execute_sql': IntentType.QUERY_DATA,

            'analyze_legal': IntentType.LEGAL,
            'check_compliance': IntentType.LEGAL,

            'search_web': IntentType.WEB_SEARCH,
            'google_it': IntentType.WEB_SEARCH,

            'trigger_workflow': IntentType.TRIGGER_WORKFLOW,
            'run_automation': IntentType.TRIGGER_WORKFLOW,
        }

    # Keywords that should bypass document-based routing to use LLM classifier
    LEGAL_KEYWORDS = [
        "loi", "légal", "légale", "légalement", "juridique",
        "légifrance", "legifrance", "code civil", "article",
        "réglementation", "obligation légale", "obligations légales",
        "conforme", "conformité", "droit", "jurisprudence",
        "loi elan", "loi climat", "décret", "ordonnance"
    ]

    def check(self, context: Dict[str, Any], user_query: str = None) -> Optional[Dict[str, Any]]:
        """
        Check if UI context provides obvious intent

        Args:
            context: Request context from frontend
            user_query: Optional user query for keyword detection

        Returns:
            None: No UI context, continue to classification
            Dict: UI context found, use provided intent
        """

        # Check UI mode
        ui_mode = context.get('ui_mode')
        if ui_mode and ui_mode in self.UI_MODE_INTENT_MAP:
            intent = self.UI_MODE_INTENT_MAP[ui_mode]

            logger.info("ui_context_bypass_mode",
                       ui_mode=ui_mode,
                       intent=intent.value,
                       bypass_classification=True)

            return {
                'bypass_sma': False,
                'bypass_classification': True,
                'intent': intent,
                'domain': self._infer_domain(intent),
                'confidence': 1.0,
                'reasoning': f'UI mode: {ui_mode}',
                'level': 0,
                'method': 'ui_mode'
            }

        # Check action button
        action_button = context.get('action_button')
        if action_button and action_button in self.ACTION_BUTTON_INTENT_MAP:
            intent = self.ACTION_BUTTON_INTENT_MAP[action_button]

            logger.info("ui_context_bypass_button",
                       action_button=action_button,
                       intent=intent.value,
                       bypass_classification=True)

            return {
                'bypass_sma': False,
                'bypass_classification': True,
                'intent': intent,
                'domain': self._infer_domain(intent),
                'confidence': 1.0,
                'reasoning': f'Action button: {action_button}',
                'level': 0,
                'method': 'ui_button'
            }

        # Check pre-selected document (high confidence SEARCH_DOCUMENTS)
        # BUT: if query contains legal keywords, don't bypass - let LLM classifier decide
        if context.get('selected_document_id') or context.get('active_document_id'):
            doc_id = context.get('selected_document_id') or context.get('active_document_id')

            # Check if query contains legal keywords - if so, don't bypass
            if user_query:
                query_lower = user_query.lower()
                has_legal_keywords = any(kw in query_lower for kw in self.LEGAL_KEYWORDS)

                if has_legal_keywords:
                    logger.info("ui_context_bypass_skipped_legal_keywords",
                               document_id=doc_id,
                               query_preview=user_query[:50],
                               reason="Legal keywords detected, using LLM classifier")
                    return None  # Don't bypass, use LLM classifier

            logger.info("ui_context_bypass_document",
                       document_id=doc_id,
                       intent=IntentType.SEARCH_DOCUMENTS.value,
                       bypass_classification=True)

            return {
                'bypass_sma': False,
                'bypass_classification': True,
                'intent': IntentType.SEARCH_DOCUMENTS,
                'domain': Domain.PROPERTY_MGMT,
                'confidence': 0.95,  # Slightly lower (user might want something else)
                'reasoning': f'Document pre-selected: {doc_id}',
                'level': 0,
                'method': 'ui_document'
            }

        # No UI context
        return None

    def _infer_domain(self, intent: IntentType) -> Domain:
        """Infer domain from intent"""
        domain_map = {
            IntentType.QUERY_DATA: Domain.PROPERTY_MGMT,
            IntentType.SEARCH_DOCUMENTS: Domain.PROPERTY_MGMT,
            IntentType.SEND_EMAIL: Domain.PROPERTY_MGMT,
            IntentType.REQUEST_QUOTES: Domain.VENDOR_MGMT,
            IntentType.LEGAL: Domain.LEGAL,
            IntentType.WEB_SEARCH: Domain.GENERAL,
            IntentType.TRIGGER_WORKFLOW: Domain.PROPERTY_MGMT,
            IntentType.GENERAL_QUESTION: Domain.GENERAL,
        }
        return domain_map.get(intent, Domain.GENERAL)


# Singleton instances
template_filter = TemplateFilter()
ui_context_bypass = UIContextBypass()
