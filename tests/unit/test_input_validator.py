"""Unit tests for src.security.input_validator — sanitize & validate functions."""

import pytest

from src.security.input_validator import (
    sanitize_string,
    validate_symbol,
    validate_instrument_key,
)


# ---------------------------------------------------------------------------
# sanitize_string
# ---------------------------------------------------------------------------

class TestSanitizeString:
    """Tests for sanitize_string()."""

    def test_passthrough_clean_string(self):
        assert sanitize_string("hello world") == "hello world"

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_truncates_to_max_length(self):
        long = "a" * 2000
        result = sanitize_string(long, max_length=100)
        assert len(result) == 100

    def test_default_max_length_is_1000(self):
        long = "x" * 1500
        assert len(sanitize_string(long)) == 1000

    def test_sql_injection_semicolon_removed(self):
        assert ";" not in sanitize_string("DROP TABLE; --")

    def test_sql_injection_single_quote_removed(self):
        assert "'" not in sanitize_string("' OR 1=1 --")

    def test_sql_injection_double_quote_removed(self):
        assert '"' not in sanitize_string('" OR ""="')

    def test_sql_injection_backslash_removed(self):
        assert "\\" not in sanitize_string("path\\to\\file")

    def test_xss_script_tag_removed(self):
        result = sanitize_string("<script>alert('xss')</script>")
        assert "<script" not in result.lower()

    def test_xss_mixed_case_script_removed(self):
        result = sanitize_string("<ScRiPt>alert(1)</ScRiPt>")
        assert "<script" not in result.lower()

    def test_path_traversal_removed(self):
        result = sanitize_string("../../etc/passwd")
        assert "../" not in result

    def test_empty_string(self):
        assert sanitize_string("") == ""

    def test_unicode_preserved(self):
        """Non-dangerous unicode chars should survive sanitization."""
        assert sanitize_string("café résumé") == "café résumé"


# ---------------------------------------------------------------------------
# validate_symbol
# ---------------------------------------------------------------------------

class TestValidateSymbol:
    """Tests for validate_symbol()."""

    def test_valid_forex_pair(self):
        assert validate_symbol("EURUSD") == "EURUSD"

    def test_valid_commodity(self):
        assert validate_symbol("XAUUSD") == "XAUUSD"

    def test_lowercased_input_uppercased(self):
        assert validate_symbol("eurusd") == "EURUSD"

    def test_symbol_with_slash(self):
        assert validate_symbol("EUR/USD") == "EUR/USD"

    def test_symbol_with_dot(self):
        assert validate_symbol("ES.F") == "ES.F"

    def test_symbol_with_underscore(self):
        assert validate_symbol("BTC_USD") == "BTC_USD"

    def test_symbol_with_digits(self):
        assert validate_symbol("NQ2025") == "NQ2025"

    def test_strips_whitespace(self):
        assert validate_symbol("  EURUSD  ") == "EURUSD"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid symbol"):
            validate_symbol("")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="Invalid symbol"):
            validate_symbol("A" * 21)

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="Invalid symbol"):
            validate_symbol("EUR;USD")

    def test_rejects_spaces_in_middle(self):
        with pytest.raises(ValueError, match="Invalid symbol"):
            validate_symbol("EUR USD")

    def test_rejects_sql_injection(self):
        with pytest.raises(ValueError, match="Invalid symbol"):
            validate_symbol("'; DROP TABLE--")


# ---------------------------------------------------------------------------
# validate_instrument_key
# ---------------------------------------------------------------------------

class TestValidateInstrumentKey:
    """Tests for validate_instrument_key()."""

    def test_valid_simple_key(self):
        assert validate_instrument_key("eurusd") == "eurusd"

    def test_valid_key_with_hyphens(self):
        assert validate_instrument_key("eur-usd") == "eur-usd"

    def test_valid_key_with_underscores(self):
        assert validate_instrument_key("eur_usd") == "eur_usd"

    def test_uppercased_input_lowered(self):
        assert validate_instrument_key("EURUSD") == "eurusd"

    def test_strips_whitespace(self):
        assert validate_instrument_key("  eurusd  ") == "eurusd"

    def test_key_with_digits(self):
        assert validate_instrument_key("nq2025") == "nq2025"

    def test_max_length_50_accepted(self):
        key = "a" * 50
        assert validate_instrument_key(key) == key

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid instrument key"):
            validate_instrument_key("")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="Invalid instrument key"):
            validate_instrument_key("a" * 51)

    def test_rejects_dot(self):
        with pytest.raises(ValueError, match="Invalid instrument key"):
            validate_instrument_key("eur.usd")

    def test_rejects_slash(self):
        with pytest.raises(ValueError, match="Invalid instrument key"):
            validate_instrument_key("eur/usd")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid instrument key"):
            validate_instrument_key("../../etc")
