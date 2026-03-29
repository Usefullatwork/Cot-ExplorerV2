"""Unit tests for src.trading.scrapers.chokepoints — chokepoint definitions and risk."""

from __future__ import annotations

from src.trading.scrapers.chokepoints import (
    CHOKEPOINTS,
    assess_risk,
    get_chokepoints,
)


# ===== get_chokepoints =====================================================


class TestGetChokepoints:
    """Static chokepoint data retrieval."""

    def test_returns_expected_count(self):
        """Should return all 6 chokepoints."""
        cps = get_chokepoints()
        assert len(cps) == 6

    def test_all_chokepoints_have_required_fields(self):
        """Every chokepoint dict has name, lat, lon, throughput, cargo_types, risk_level."""
        for cp in get_chokepoints():
            assert "name" in cp
            assert "lat" in cp
            assert "lon" in cp
            assert "throughput" in cp
            assert "cargo_types" in cp
            assert "affected_instruments" in cp
            assert "risk_level" in cp

    def test_keywords_excluded_from_public_api(self):
        """Internal 'keywords' field should not appear in get_chokepoints() output."""
        for cp in get_chokepoints():
            assert "keywords" not in cp

    def test_known_chokepoints_present(self):
        """Well-known chokepoints are in the list."""
        names = {cp["name"] for cp in get_chokepoints()}
        assert "Strait of Hormuz" in names
        assert "Suez Canal" in names
        assert "Panama Canal" in names
        assert "Bab el-Mandeb" in names


# ===== assess_risk =========================================================


class TestAssessRisk:
    """Dynamic risk bumping based on news intelligence."""

    def test_matching_article_bumps_risk(self):
        """Article mentioning a chokepoint keyword bumps risk one tier."""
        articles = [{"title": "Houthi attack on Red Sea shipping near Bab el-Mandeb"}]
        results = assess_risk(articles)

        bab = next(r for r in results if r["name"] == "Bab el-Mandeb")
        # Original risk is "high" => stays "high" (already max)
        assert bab["risk_level"] == "high"

        # Test with one that can actually bump
        articles2 = [{"title": "Panama Canal drought causes major delays"}]
        results2 = assess_risk(articles2)
        panama = next(r for r in results2 if r["name"] == "Panama Canal")
        # Original was "low" => bumped to "medium"
        assert panama["risk_level"] == "medium"

    def test_no_matching_articles_keeps_original_risk(self):
        """Articles about unrelated topics don't change risk levels."""
        articles = [{"title": "Bitcoin price surges past $100k"}]
        results = assess_risk(articles)

        for result, original in zip(results, CHOKEPOINTS):
            assert result["risk_level"] == original["risk_level"]

    def test_empty_articles_keeps_original_risk(self):
        """Empty article list returns original risk levels."""
        results = assess_risk([])
        for result, original in zip(results, CHOKEPOINTS):
            assert result["risk_level"] == original["risk_level"]

    def test_suez_canal_bump(self):
        """Article mentioning Suez bumps from medium to high."""
        articles = [{"title": "Suez Canal blocked by container ship again"}]
        results = assess_risk(articles)

        suez = next(r for r in results if r["name"] == "Suez Canal")
        assert suez["risk_level"] == "high"

    def test_high_risk_does_not_go_higher(self):
        """A chokepoint already at 'high' stays at 'high' even with matching news."""
        # Bab el-Mandeb starts at "high"
        articles = [{"title": "New houthi attack in red sea disrupts shipping"}]
        results = assess_risk(articles)

        bab = next(r for r in results if r["name"] == "Bab el-Mandeb")
        assert bab["risk_level"] == "high"

    def test_keywords_not_in_output(self):
        """assess_risk output should not include internal keywords."""
        results = assess_risk([])
        for r in results:
            assert "keywords" not in r
