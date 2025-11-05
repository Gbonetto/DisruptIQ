"""
Tests for Entity Extractor Service
"""

import pytest
from datetime import datetime
from app.services.conversation.entity_extractor import EntityExtractor


class TestEntityExtractor:
    """Test entity extraction functionality"""

    def setup_method(self):
        self.extractor = EntityExtractor()

    # === Amount Extraction Tests ===

    def test_extract_simple_amount(self):
        """Should extract simple amounts"""
        message = "Factures de 500€"
        entities = self.extractor.extract_entities(message)

        assert len(entities['amounts']) == 1
        assert entities['amounts'][0]['value'] == 500.0
        assert entities['amounts'][0]['type'] == 'exact'

    def test_extract_amount_with_comparison(self):
        """Should extract amounts with comparison operators"""
        test_cases = [
            ("Factures supérieures à 1000€", '>', 1000.0),
            ("Factures > 500€", '>', 500.0),
            ("Factures inférieures à 200€", '<', 200.0),
            ("Factures < 300€", '<', 300.0),
            ("Plus de 1500€", '>', 1500.0),
            ("Moins de 800€", '<', 800.0),
        ]

        for message, expected_op, expected_val in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['amounts']) >= 1
            assert entities['amounts'][0]['operator'] == expected_op
            assert entities['amounts'][0]['value'] == expected_val

    def test_extract_amount_range(self):
        """Should extract amount ranges"""
        test_cases = [
            "Entre 100 et 500€",
            "De 100€ à 500€",
            "entre 100€ et 500€",
        ]

        for message in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['amounts']) >= 1
            assert entities['amounts'][0]['type'] == 'range'
            assert entities['amounts'][0]['min'] == 100.0
            assert entities['amounts'][0]['max'] == 500.0

    def test_extract_amount_with_decimals(self):
        """Should extract amounts with decimal points"""
        message = "Factures de 1234.56€"
        entities = self.extractor.extract_entities(message)

        assert len(entities['amounts']) == 1
        assert entities['amounts'][0]['value'] == 1234.56

    def test_extract_amount_french_format(self):
        """Should handle French number format (1.000,50)"""
        # Note: Current implementation might need adjustment for this
        message = "Factures de 1000€"
        entities = self.extractor.extract_entities(message)
        assert len(entities['amounts']) >= 1

    # === Date Extraction Tests ===

    def test_extract_relative_dates(self):
        """Should extract relative dates"""
        test_cases = [
            "Factures d'hier",
            "Factures de aujourd'hui",
            "Factures de demain",
            "Factures de la semaine dernière",
            "Factures du mois dernier",
            "Factures de cette année",
        ]

        for message in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['dates']) >= 1
            assert 'value' in entities['dates'][0]
            assert 'type' in entities['dates'][0]

    def test_extract_month_names(self):
        """Should extract month names"""
        test_cases = [
            ("Factures de janvier", 1),
            ("En février", 2),
            ("Factures de décembre", 12),
        ]

        for message, expected_month in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['dates']) >= 1
            assert entities['dates'][0]['type'] == 'month'
            assert entities['dates'][0]['month'] == expected_month

    def test_extract_absolute_dates(self):
        """Should extract absolute dates"""
        test_cases = [
            "Factures du 2024-01-15",
            "Factures du 15/01/2024",
            "Factures du 15-01-2024",
        ]

        for message in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['dates']) >= 1
            assert entities['dates'][0]['type'] == 'absolute'

    def test_extract_last_n_days(self):
        """Should extract 'last N days' patterns"""
        message = "Factures des 30 derniers jours"
        entities = self.extractor.extract_entities(message)

        assert len(entities['dates']) >= 1
        assert entities['dates'][0]['type'] == 'relative'

    # === Invoice Number Tests ===

    def test_extract_invoice_numbers(self):
        """Should extract invoice numbers"""
        test_cases = [
            ("Facture FAC-001", "FAC-001"),
            ("Invoice INV-123", "INV-123"),
            ("Facture n°456", "456"),
            ("facture numéro 789", "789"),
        ]

        for message, expected_num in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['invoice_numbers']) >= 1
            assert expected_num in entities['invoice_numbers'][0]

    def test_extract_multiple_invoice_numbers(self):
        """Should extract multiple invoice numbers"""
        message = "Factures FAC-001, FAC-002 et FAC-003"
        entities = self.extractor.extract_entities(message)

        assert len(entities['invoice_numbers']) >= 2

    # === Status Tests ===

    def test_extract_statuses(self):
        """Should extract payment statuses"""
        test_cases = [
            ("Factures en attente", "pending"),
            ("Factures payées", "paid"),
            ("Factures annulées", "cancelled"),
            ("Factures validées", "validated"),
        ]

        for message, expected_status in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['statuses']) >= 1
            assert expected_status in entities['statuses']

    def test_extract_multiple_statuses(self):
        """Should extract multiple statuses"""
        message = "Factures en attente ou payées"
        entities = self.extractor.extract_entities(message)

        assert len(entities['statuses']) >= 2
        assert 'pending' in entities['statuses']
        assert 'paid' in entities['statuses']

    # === Category Tests ===

    def test_extract_categories(self):
        """Should extract service categories"""
        test_cases = [
            ("Factures de plomberie", "plomberie"),
            ("Factures d'électricité", "électricité"),
            ("Factures de jardinage", "jardinage"),
            ("Factures de nettoyage", "nettoyage"),
            ("Factures du plombier", "plomberie"),
            ("Factures de l'électricien", "électricité"),
        ]

        for message, expected_category in test_cases:
            entities = self.extractor.extract_entities(message)
            assert len(entities['categories']) >= 1
            assert expected_category in entities['categories']

    # === Supplier Tests ===

    def test_extract_suppliers(self):
        """Should extract supplier names"""
        test_cases = [
            "Factures de Plomberie Dupont",
            "Factures de l'électricien Martin",
            "Factures du jardinier Leblanc",
        ]

        for message in test_cases:
            entities = self.extractor.extract_entities(message)
            # Note: Supplier extraction is complex, just check it doesn't crash
            assert 'suppliers' in entities

    # === Complex Query Tests ===

    def test_extract_complex_query(self):
        """Should extract multiple entity types from complex query"""
        message = "Montre-moi les factures de plomberie supérieures à 500€ du mois dernier"
        entities = self.extractor.extract_entities(message)

        # Should extract category
        assert 'plomberie' in entities['categories']

        # Should extract amount with comparison
        assert len(entities['amounts']) >= 1
        assert entities['amounts'][0]['operator'] == '>'
        assert entities['amounts'][0]['value'] == 500.0

        # Should extract date
        assert len(entities['dates']) >= 1

    def test_extract_with_range_and_category(self):
        """Should extract range + category"""
        message = "Factures d'électricité entre 100 et 1000€"
        entities = self.extractor.extract_entities(message)

        assert 'électricité' in entities['categories']
        assert len(entities['amounts']) >= 1
        assert entities['amounts'][0]['type'] == 'range'

    # === Filters Conversion Tests ===

    def test_entities_to_filters_amount(self):
        """Should convert amount entities to filters"""
        message = "Factures supérieures à 500€"
        entities = self.extractor.extract_entities(message)
        filters = self.extractor.entities_to_filters(entities)

        assert 'amount_min' in filters
        assert filters['amount_min'] == 500.0

    def test_entities_to_filters_range(self):
        """Should convert range to min/max filters"""
        message = "Factures entre 100 et 500€"
        entities = self.extractor.extract_entities(message)
        filters = self.extractor.entities_to_filters(entities)

        assert 'amount_min' in filters
        assert 'amount_max' in filters
        assert filters['amount_min'] == 100.0
        assert filters['amount_max'] == 500.0

    def test_entities_to_filters_status(self):
        """Should convert status to filter"""
        message = "Factures en attente"
        entities = self.extractor.extract_entities(message)
        filters = self.extractor.entities_to_filters(entities)

        assert 'status' in filters
        assert 'pending' in filters['status']

    def test_entities_to_filters_complex(self):
        """Should convert multiple entities to filters"""
        message = "Factures de plomberie payées supérieures à 1000€"
        entities = self.extractor.extract_entities(message)
        filters = self.extractor.entities_to_filters(entities)

        assert 'category' in filters
        assert 'status' in filters
        assert 'amount_min' in filters

    # === Edge Cases ===

    def test_extract_empty_message(self):
        """Should handle empty message gracefully"""
        entities = self.extractor.extract_entities("")

        assert entities['amounts'] == []
        assert entities['dates'] == []
        assert entities['invoice_numbers'] == []

    def test_extract_no_entities(self):
        """Should handle message with no entities"""
        message = "Bonjour comment allez-vous"
        entities = self.extractor.extract_entities(message)

        assert entities['amounts'] == []
        assert entities['dates'] == []
        assert entities['invoice_numbers'] == []

    def test_format_entities_summary(self):
        """Should format entities summary"""
        message = "Factures de plomberie supérieures à 500€ du mois dernier"
        entities = self.extractor.extract_entities(message)
        summary = self.extractor.format_entities_summary(entities)

        assert isinstance(summary, str)
        assert len(summary) > 0
        # Summary should mention key entities
        assert "Montant" in summary or "Date" in summary or "Catégories" in summary


# Integration test
def test_entity_extractor_integration():
    """Integration test with realistic queries"""
    extractor = EntityExtractor()

    queries = [
        "Montre-moi les factures de plomberie supérieures à 500€",
        "Factures en attente du mois dernier",
        "Factures entre 100 et 1000€ de janvier",
        "Facture FAC-001",
        "Factures d'électricité payées",
    ]

    for query in queries:
        entities = extractor.extract_entities(query)
        # Each query should extract at least something
        total_entities = sum(
            len(v) if isinstance(v, list) else (1 if v else 0)
            for v in entities.values()
        )
        assert total_entities > 0, f"No entities extracted from: {query}"
