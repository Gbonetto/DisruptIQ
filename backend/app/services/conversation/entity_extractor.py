"""
Entity Extractor Service - Extraction d'entités structurées

Extrait les entités clés des messages utilisateur :
- Montants (500€, 1000 euros, cinq cents euros)
- Dates (le mois dernier, 2024-01-15, janvier, hier)
- Fournisseurs (Plomberie Dupont, électricien Martin)
- Numéros de facture (FAC-001, INV-123)
- Statuts (en attente, payée, annulée)
- Catégories (plomberie, électricité, jardinage)
- Ranges (entre 100 et 500€, > 1000€)
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import structlog

logger = structlog.get_logger(__name__)


class EntityExtractor:
    """
    Service d'extraction d'entités avec support multi-format
    """

    # Patterns de montants (simplified to capture any number)
    AMOUNT_PATTERNS = [
        # Format: 500€, 1000.50€, 1,500€, 1234.56€
        r'(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)',
        # Format: € 500
        r'(?:€|euros?|eur)\s*(\d+(?:[.,]\d+)?)',
    ]

    # Patterns de comparaison (handle accents and variations)
    COMPARISON_PATTERNS = [
        (r'(?:sup[eé]rieur(?:e)?s?\s+(?:[aà])|>\s*|plus\s+de)\s*', '>'),
        (r'(?:inf[eé]rieur(?:e)?s?\s+(?:[aà])|<\s*|moins\s+de)\s*', '<'),
        (r'(?:au\s+moins|minimum|mini)\s*', '>='),
        (r'(?:au\s+plus|maximum|maxi)\s*', '<='),
        (r'(?:[eé]gal(?:e)?s?\s+(?:[aà])|=\s*)', '='),
    ]

    # Patterns de ranges (allow more flexible number formats)
    RANGE_PATTERNS = [
        r'entre\s+(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)?\s+et\s+(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)?',
        r'de\s+(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)?\s+(?:[aà])\s+(\d+(?:[.,]\d+)?)\s*(?:€|euros?|eur)?',
    ]

    # Patterns de dates relatives (more flexible, allow d' prefix)
    RELATIVE_DATE_PATTERNS = {
        r"aujourd'?hui": lambda: datetime.now(),
        r"d'?hier\b": lambda: datetime.now() - timedelta(days=1),
        r'avant[- ]hier': lambda: datetime.now() - timedelta(days=2),
        r'demain': lambda: datetime.now() + timedelta(days=1),
        r'apr[eè]s[- ]demain': lambda: datetime.now() + timedelta(days=2),

        # Semaines
        r'cette\s+semaine': lambda: datetime.now(),
        r'(?:de\s+)?la\s+semaine\s+derni[eè]re': lambda: datetime.now() - timedelta(weeks=1),
        r'la\s+semaine\s+prochaine': lambda: datetime.now() + timedelta(weeks=1),

        # Mois
        r'ce\s+mois[-\s]?ci': lambda: datetime.now(),
        r'(?:du?\s+)?(?:le\s+)?mois\s+dernier': lambda: datetime.now() - relativedelta(months=1),
        r'le\s+mois\s+prochain': lambda: datetime.now() + relativedelta(months=1),

        # Années
        r'cette\s+ann[eé]e': lambda: datetime.now(),
        r"l'?ann[eé]e\s+derni[eè]re": lambda: datetime.now() - relativedelta(years=1),
        r"l'?ann[eé]e\s+prochaine": lambda: datetime.now() + relativedelta(years=1),

        # Périodes with numbers
        r'(?:des?\s+)?les?\s+(\d+)\s+derniers?\s+jours?': lambda match: datetime.now() - timedelta(days=int(match.group(1))),
        r'(?:des?\s+)?les?\s+(\d+)\s+derni[eè]res?\s+semaines?': lambda match: datetime.now() - timedelta(weeks=int(match.group(1))),
        r'(?:des?\s+)?les?\s+(\d+)\s+derniers?\s+mois': lambda match: datetime.now() - relativedelta(months=int(match.group(1))),
    }

    # Mois en français
    FRENCH_MONTHS = {
        'janvier': 1, 'janv': 1,
        'février': 2, 'fevrier': 2, 'fév': 2, 'fev': 2,
        'mars': 3,
        'avril': 4, 'avr': 4,
        'mai': 5,
        'juin': 6,
        'juillet': 7, 'juil': 7,
        'août': 8, 'aout': 8,
        'septembre': 9, 'sept': 9, 'sep': 9,
        'octobre': 10, 'oct': 10,
        'novembre': 11, 'nov': 11,
        'décembre': 12, 'decembre': 12, 'déc': 12, 'dec': 12,
    }

    # Patterns de numéros de facture
    INVOICE_PATTERNS = [
        r'\b(FAC[-_]?\d{3,})\b',
        r'\b(INV[-_]?\d{3,})\b',
        r'\b(INVOICE[-_]?\d{3,})\b',
        r'facture\s+(?:n[°o]?\s*)?(\d{3,})',
        r'invoice\s+(?:#\s*)?(\d{3,})',
    ]

    # Statuts possibles
    STATUS_MAPPINGS = {
        'en attente': 'pending',
        'attente': 'pending',
        'pending': 'pending',
        'à traiter': 'pending',
        'non traitée': 'pending',

        'payée': 'paid',
        'payé': 'paid',
        'paid': 'paid',
        'réglée': 'paid',
        'réglé': 'paid',

        'annulée': 'cancelled',
        'annulé': 'cancelled',
        'cancelled': 'cancelled',
        'canceled': 'cancelled',

        'en cours': 'in_progress',
        'en traitement': 'in_progress',
        'processing': 'in_progress',

        'validée': 'validated',
        'validé': 'validated',
        'validated': 'validated',
        'approuvée': 'validated',
    }

    # Catégories de services
    CATEGORY_MAPPINGS = {
        'plomberie': 'plomberie',
        'plombier': 'plomberie',
        'plumbing': 'plomberie',

        'électricité': 'électricité',
        'électrique': 'électricité',
        'électricien': 'électricité',
        'electric': 'électricité',

        'jardinage': 'jardinage',
        'jardinier': 'jardinage',
        'espaces verts': 'jardinage',
        'gardening': 'jardinage',

        'nettoyage': 'nettoyage',
        'ménage': 'nettoyage',
        'cleaning': 'nettoyage',

        'chauffage': 'chauffage',
        'heating': 'chauffage',

        'ascenseur': 'ascenseur',
        'elevator': 'ascenseur',

        'sécurité': 'sécurité',
        'security': 'sécurité',
        'gardien': 'sécurité',
    }

    def __init__(self):
        self.logger = logger.bind(service="entity_extractor")

    def extract_entities(self, message: str) -> Dict[str, Any]:
        """
        Extrait toutes les entités d'un message

        Args:
            message: Message utilisateur

        Returns:
            Dict avec toutes les entités extraites
        """
        message_lower = message.lower()

        entities = {
            'amounts': self.extract_amounts(message_lower),
            'dates': self.extract_dates(message_lower),
            'invoice_numbers': self.extract_invoice_numbers(message),
            'statuses': self.extract_statuses(message_lower),
            'categories': self.extract_categories(message_lower),
            'suppliers': self.extract_suppliers(message),
        }

        # Log extraction results
        self.logger.debug(
            "entities_extracted",
            message_preview=message[:50],
            entity_count=sum(len(v) if isinstance(v, list) else (1 if v else 0) for v in entities.values())
        )

        return entities

    def extract_amounts(self, message: str) -> List[Dict[str, Any]]:
        """
        Extrait les montants avec comparaisons et ranges

        Returns:
            List of dicts with 'value', 'operator', 'range'
        """
        amounts = []

        # Check for ranges first (entre X et Y)
        for pattern in self.RANGE_PATTERNS:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                min_val = self._parse_amount(match.group(1))
                max_val = self._parse_amount(match.group(2))
                if min_val and max_val:
                    amounts.append({
                        'type': 'range',
                        'min': min_val,
                        'max': max_val,
                        'operator': 'between',
                        'text': match.group(0)
                    })

        # Check for comparisons (>, <, >=, <=)
        for comp_pattern, operator in self.COMPARISON_PATTERNS:
            for amount_pattern in self.AMOUNT_PATTERNS:
                full_pattern = comp_pattern + amount_pattern
                matches = re.finditer(full_pattern, message, re.IGNORECASE)
                for match in matches:
                    # Get the amount part (last group)
                    amount_str = match.group(match.lastindex)
                    value = self._parse_amount(amount_str)
                    if value:
                        amounts.append({
                            'type': 'comparison',
                            'value': value,
                            'operator': operator,
                            'text': match.group(0)
                        })

        # Extract standalone amounts (no comparison)
        if not amounts:  # Only if no comparisons found
            for pattern in self.AMOUNT_PATTERNS:
                matches = re.finditer(pattern, message, re.IGNORECASE)
                for match in matches:
                    amount_str = match.group(1)
                    value = self._parse_amount(amount_str)
                    if value:
                        amounts.append({
                            'type': 'exact',
                            'value': value,
                            'operator': '=',
                            'text': match.group(0)
                        })

        return amounts

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse amount string to float"""
        try:
            # Remove spaces and normalize
            amount_str = amount_str.replace(' ', '').replace(',', '.')
            # Handle French format (1.000,50 or 1 000,50)
            if '.' in amount_str and ',' in amount_str:
                amount_str = amount_str.replace('.', '').replace(',', '.')
            return float(amount_str)
        except (ValueError, AttributeError):
            return None

    def extract_dates(self, message: str) -> List[Dict[str, Any]]:
        """
        Extrait les dates (absolues et relatives)

        Returns:
            List of dicts with 'type', 'value', 'text'
        """
        dates = []

        # Check relative dates
        for pattern, date_func in self.RELATIVE_DATE_PATTERNS.items():
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                try:
                    if callable(date_func):
                        # Some patterns capture groups (e.g., "les 30 derniers jours")
                        if match.groups():
                            date_obj = date_func(match)
                        else:
                            date_obj = date_func()

                        dates.append({
                            'type': 'relative',
                            'value': date_obj.isoformat(),
                            'text': match.group(0),
                            'parsed': date_obj
                        })
                except Exception as e:
                    self.logger.warning("date_parse_error", pattern=pattern, error=str(e))

        # Check for month names (e.g., "janvier", "en mars")
        for month_name, month_num in self.FRENCH_MONTHS.items():
            pattern = rf'\b(?:en\s+)?({month_name})\b'
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                # Assume current year if not specified
                date_obj = datetime(datetime.now().year, month_num, 1)
                dates.append({
                    'type': 'month',
                    'value': date_obj.isoformat(),
                    'text': match.group(0),
                    'month': month_num,
                    'parsed': date_obj
                })

        # Check for absolute dates (YYYY-MM-DD, DD/MM/YYYY)
        absolute_patterns = [
            r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
            r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b',
        ]
        for pattern in absolute_patterns:
            matches = re.finditer(pattern, message)
            for match in matches:
                try:
                    date_obj = date_parser.parse(match.group(1), dayfirst=True)
                    dates.append({
                        'type': 'absolute',
                        'value': date_obj.isoformat(),
                        'text': match.group(0),
                        'parsed': date_obj
                    })
                except Exception as e:
                    self.logger.warning("absolute_date_parse_error", date_str=match.group(1), error=str(e))

        return dates

    def extract_invoice_numbers(self, message: str) -> List[str]:
        """
        Extrait les numéros de facture

        Returns:
            List of invoice numbers
        """
        invoice_numbers = []

        for pattern in self.INVOICE_PATTERNS:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                invoice_num = match.group(1).upper()
                if invoice_num not in invoice_numbers:
                    invoice_numbers.append(invoice_num)

        return invoice_numbers

    def extract_statuses(self, message: str) -> List[str]:
        """
        Extrait les statuts de facture

        Returns:
            List of status codes
        """
        statuses = []

        for status_text, status_code in self.STATUS_MAPPINGS.items():
            if status_text in message:
                if status_code not in statuses:
                    statuses.append(status_code)

        return statuses

    def extract_categories(self, message: str) -> List[str]:
        """
        Extrait les catégories de service

        Returns:
            List of category names
        """
        categories = []

        for category_text, category_name in self.CATEGORY_MAPPINGS.items():
            if category_text in message:
                if category_name not in categories:
                    categories.append(category_name)

        return categories

    def extract_suppliers(self, message: str) -> List[str]:
        """
        Extrait les noms de fournisseurs

        Uses patterns like:
        - "Plomberie Dupont"
        - "électricien Martin"
        - "Dupont" (after category mention)

        Returns:
            List of supplier names
        """
        suppliers = []

        # Pattern: [Category] [Capitalized Name]
        # e.g., "Plomberie Dupont", "électricien Martin"
        category_supplier_pattern = r'(?:plomberie|électricien|jardinier|chauffagiste|entreprise)\s+([A-Z][a-zàâäéèêëïîôùûü]+(?:\s+[A-Z][a-zàâäéèêëïîôùûü]+)?)'
        matches = re.finditer(category_supplier_pattern, message, re.IGNORECASE)
        for match in matches:
            supplier_name = match.group(1).strip()
            if supplier_name not in suppliers:
                suppliers.append(supplier_name)

        # Pattern: Capitalized name followed by category
        # e.g., "Dupont le plombier"
        name_category_pattern = r'([A-Z][a-zàâäéèêëïîôùûü]+(?:\s+[A-Z][a-zàâäéèêëïîôùûü]+)?)\s+(?:le|la|l\')(?:plombier|électricien|jardinier)'
        matches = re.finditer(name_category_pattern, message)
        for match in matches:
            supplier_name = match.group(1).strip()
            if supplier_name not in suppliers:
                suppliers.append(supplier_name)

        return suppliers

    def entities_to_filters(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convertit les entités extraites en filtres SQL/query

        Args:
            entities: Dict d'entités extraites

        Returns:
            Dict de filtres applicables
        """
        filters = {}

        # Amount filters
        if entities.get('amounts'):
            amount_entity = entities['amounts'][0]  # Take first amount
            if amount_entity['type'] == 'range':
                filters['amount_min'] = amount_entity['min']
                filters['amount_max'] = amount_entity['max']
            elif amount_entity['type'] == 'comparison':
                op = amount_entity['operator']
                val = amount_entity['value']
                if op == '>':
                    filters['amount_min'] = val
                elif op == '<':
                    filters['amount_max'] = val
                elif op == '>=':
                    filters['amount_min'] = val
                elif op == '<=':
                    filters['amount_max'] = val
                elif op == '=':
                    filters['amount_exact'] = val
            elif amount_entity['type'] == 'exact':
                filters['amount_exact'] = amount_entity['value']

        # Date filters
        if entities.get('dates'):
            date_entity = entities['dates'][0]  # Take first date
            filters['date'] = date_entity['value']
            if date_entity['type'] == 'month':
                filters['date_type'] = 'month'
                filters['month'] = date_entity['month']

        # Status filters
        if entities.get('statuses'):
            filters['status'] = entities['statuses']

        # Category filters
        if entities.get('categories'):
            filters['category'] = entities['categories']

        # Invoice number filters
        if entities.get('invoice_numbers'):
            filters['invoice_numbers'] = entities['invoice_numbers']

        # Supplier filters
        if entities.get('suppliers'):
            filters['suppliers'] = entities['suppliers']

        return filters

    def format_entities_summary(self, entities: Dict[str, Any]) -> str:
        """
        Formate les entités en texte lisible pour debug/logging

        Args:
            entities: Dict d'entités

        Returns:
            String summary
        """
        parts = []

        if entities.get('amounts'):
            for amt in entities['amounts']:
                if amt['type'] == 'range':
                    parts.append(f"Montant: {amt['min']}€ - {amt['max']}€")
                elif amt['type'] == 'comparison':
                    parts.append(f"Montant: {amt['operator']} {amt['value']}€")

        if entities.get('dates'):
            for date in entities['dates']:
                parts.append(f"Date: {date['text']}")

        if entities.get('statuses'):
            parts.append(f"Statuts: {', '.join(entities['statuses'])}")

        if entities.get('categories'):
            parts.append(f"Catégories: {', '.join(entities['categories'])}")

        if entities.get('invoice_numbers'):
            parts.append(f"Factures: {', '.join(entities['invoice_numbers'])}")

        if entities.get('suppliers'):
            parts.append(f"Fournisseurs: {', '.join(entities['suppliers'])}")

        return " | ".join(parts) if parts else "Aucune entité"
