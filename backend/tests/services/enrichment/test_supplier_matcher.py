"""
Tests for SupplierMatcher service
"""

import pytest
from decimal import Decimal

from app.services.enrichment.supplier_matcher import (
    SupplierMatcher,
    normalize_text,
    similarity_score,
    normalize_siret,
    levenshtein_distance
)
from app.models.enrichment import SupplierMatchMethod


class TestTextNormalization:
    """Test text normalization functions"""

    def test_normalize_text_lowercase(self):
        """Should convert to lowercase"""
        assert normalize_text("ACME Corp") == "acme corp"

    def test_normalize_text_accents(self):
        """Should remove accents"""
        assert normalize_text("Société Française") == "societe francaise"

    def test_normalize_text_special_chars(self):
        """Should remove special characters"""
        assert normalize_text("Company & Co.") == "company co"

    def test_normalize_text_whitespace(self):
        """Should normalize whitespace"""
        assert normalize_text("  Multiple   Spaces  ") == "multiple spaces"

    def test_normalize_text_empty(self):
        """Should handle empty string"""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestLevenshteinDistance:
    """Test Levenshtein distance calculation"""

    def test_identical_strings(self):
        """Should return 0 for identical strings"""
        assert levenshtein_distance("hello", "hello") == 0

    def test_one_char_difference(self):
        """Should return 1 for one character difference"""
        assert levenshtein_distance("hello", "hallo") == 1

    def test_insertion(self):
        """Should count insertion correctly"""
        assert levenshtein_distance("hello", "helloo") == 1

    def test_deletion(self):
        """Should count deletion correctly"""
        assert levenshtein_distance("hello", "helo") == 1

    def test_empty_strings(self):
        """Should handle empty strings"""
        assert levenshtein_distance("", "hello") == 5
        assert levenshtein_distance("hello", "") == 5


class TestSimilarityScore:
    """Test similarity score calculation"""

    def test_identical_strings(self):
        """Should return 1.0 for identical strings"""
        assert similarity_score("hello", "hello") == 1.0

    def test_similar_strings(self):
        """Should return high score for similar strings"""
        score = similarity_score("Plomberie Dupont", "Plomberie Dupond")
        assert score > 0.9

    def test_different_strings(self):
        """Should return low score for different strings"""
        score = similarity_score("Plomberie", "Électricité")
        assert score < 0.5

    def test_case_insensitive(self):
        """Should be case insensitive"""
        assert similarity_score("HELLO", "hello") == 1.0

    def test_accent_insensitive(self):
        """Should be accent insensitive"""
        score = similarity_score("François", "Francois")
        assert score == 1.0

    def test_empty_strings(self):
        """Should handle empty strings"""
        assert similarity_score("", "") == 0.0
        assert similarity_score("hello", "") == 0.0


class TestNormalizeSiret:
    """Test SIRET normalization"""

    def test_valid_siret(self):
        """Should normalize valid SIRET"""
        assert normalize_siret("12345678901234") == "12345678901234"

    def test_siret_with_spaces(self):
        """Should remove spaces"""
        assert normalize_siret("123 456 789 01234") == "12345678901234"

    def test_siret_with_dashes(self):
        """Should remove dashes"""
        assert normalize_siret("123-456-789-01234") == "12345678901234"

    def test_invalid_length(self):
        """Should return None for invalid length"""
        assert normalize_siret("123") is None
        assert normalize_siret("123456789012345") is None

    def test_contains_letters(self):
        """Should return None for non-numeric"""
        assert normalize_siret("1234567890123A") is None

    def test_empty_string(self):
        """Should return None for empty"""
        assert normalize_siret("") is None
        assert normalize_siret(None) is None


@pytest.mark.asyncio
class TestSupplierMatcher:
    """Test SupplierMatcher service (requires database)"""

    async def test_match_by_siret_exact(self, async_db_session, sample_professionnel):
        """Should match by exact SIRET"""
        matcher = SupplierMatcher(db=async_db_session)

        result = await matcher.match_supplier(
            extracted_siret=sample_professionnel.siret
        )

        assert result.matched is True
        assert result.fournisseur_id == sample_professionnel.id
        assert result.confidence == 1.0
        assert result.method == SupplierMatchMethod.SIRET_EXACT

    async def test_match_by_siret_with_spaces(self, async_db_session, sample_professionnel):
        """Should match by SIRET even with spaces"""
        matcher = SupplierMatcher(db=async_db_session)

        # Add spaces to SIRET
        siret_with_spaces = " ".join([sample_professionnel.siret[i:i+3] for i in range(0, 14, 3)])

        result = await matcher.match_supplier(
            extracted_siret=siret_with_spaces
        )

        assert result.matched is True
        assert result.fournisseur_id == sample_professionnel.id

    async def test_match_by_name_fuzzy(self, async_db_session, sample_professionnel):
        """Should match by fuzzy name"""
        matcher = SupplierMatcher(db=async_db_session, fuzzy_threshold=0.80)

        # Slightly different name
        similar_name = sample_professionnel.name.replace("e", "é")

        result = await matcher.match_supplier(
            extracted_name=similar_name
        )

        assert result.matched is True
        assert result.fournisseur_id == sample_professionnel.id
        assert result.method == SupplierMatchMethod.NAME_FUZZY
        assert result.confidence >= 0.80

    async def test_no_match_below_threshold(self, async_db_session, sample_professionnel):
        """Should not match if below threshold"""
        matcher = SupplierMatcher(db=async_db_session, fuzzy_threshold=0.95)

        result = await matcher.match_supplier(
            extracted_name="Completely Different Company Name"
        )

        assert result.matched is False
        assert result.method == SupplierMatchMethod.NONE
        # But should still return candidates
        assert len(result.candidates) > 0

    async def test_no_match_empty_input(self, async_db_session):
        """Should return no match for empty input"""
        matcher = SupplierMatcher(db=async_db_session)

        result = await matcher.match_supplier(
            extracted_siret=None,
            extracted_name=None
        )

        assert result.matched is False
        assert result.method == SupplierMatchMethod.NONE
        assert len(result.candidates) == 0

    async def test_siret_priority_over_name(self, async_db_session, sample_professionnel):
        """Should prioritize SIRET match over name"""
        matcher = SupplierMatcher(db=async_db_session)

        result = await matcher.match_supplier(
            extracted_siret=sample_professionnel.siret,
            extracted_name="Wrong Name"
        )

        # Should match by SIRET despite wrong name
        assert result.matched is True
        assert result.method == SupplierMatchMethod.SIRET_EXACT
        assert result.fournisseur_id == sample_professionnel.id


# Pytest fixtures for testing

@pytest.fixture
async def sample_professionnel(async_db_session):
    """Create a sample professionnel for testing"""
    from app.models.professionnel import Professionnel

    prof = Professionnel(
        name="Plomberie Dupont",
        company_name="Dupont & Fils SARL",
        email="contact@dupont-plomberie.fr",
        siret="12345678901234",
        category="Plomberie",
        statut="active"
    )

    async_db_session.add(prof)
    await async_db_session.commit()
    await async_db_session.refresh(prof)

    return prof
