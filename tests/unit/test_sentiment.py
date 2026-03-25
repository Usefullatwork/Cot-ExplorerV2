"""Unit tests for src.analysis.sentiment.detect_conflict."""

import pytest

from src.analysis.sentiment import detect_conflict


# ---------------------------------------------------------------------------
# Defaults – no conflicts triggered
# ---------------------------------------------------------------------------

_SAFE = dict(vix=18.0, dxy_5d=0.5, fg={"score": 50}, cot_usd=0.0)


# ===== Individual conflict conditions =========================================

class TestSingleConflicts:
    """Each condition triggers exactly one conflict string."""

    def test_vix_dxy_conflict(self):
        """vix>25 and dxy_5d<0 -> 'VIX>25 men DXY faller'."""
        result = detect_conflict(vix=30, dxy_5d=-2, fg={"score": 50}, cot_usd=0)
        assert any("VIX>25 men DXY faller" in c for c in result)

    def test_fear_dxy_conflict(self):
        """fg.score<30 and dxy_5d<0 -> 'Ekstrem frykt men USD svekkes'."""
        result = detect_conflict(vix=18, dxy_5d=-1, fg={"score": 20}, cot_usd=0)
        assert any("Ekstrem frykt men USD svekkes" in c for c in result)

    def test_greed_vix_conflict(self):
        """fg.score>70 and vix>22 -> 'Grådighet men VIX forhøyet'."""
        result = detect_conflict(vix=25, dxy_5d=0.5, fg={"score": 75}, cot_usd=0)
        assert any("Grådighet" in c and "VIX" in c for c in result)

    def test_cot_usd_divergence(self):
        """cot_usd>0 and dxy_5d<-1 -> 'COT long USD men pris faller'."""
        result = detect_conflict(vix=18, dxy_5d=-2, fg={"score": 50}, cot_usd=1.0)
        assert any("COT long USD men pris faller" in c for c in result)

    def test_hy_stress_low_vix(self):
        """hy_stress=True and vix<20 -> 'HY-spreader øker men VIX lav'."""
        result = detect_conflict(
            vix=15, dxy_5d=0.5, fg={"score": 50}, cot_usd=0, hy_stress=True,
        )
        assert any("HY-spreader" in c for c in result)

    def test_yield_curve_inverted(self):
        """yield_curve<-0.3 -> 'Rentekurve invertert'."""
        result = detect_conflict(
            vix=18, dxy_5d=0.5, fg={"score": 50}, cot_usd=0, yield_curve=-0.5,
        )
        assert any("Rentekurve invertert" in c for c in result)

    def test_news_risk_on_vix_high(self):
        """news risk_on and vix>25 -> 'Nyheter risk-on men VIX forhøyet'."""
        result = detect_conflict(
            vix=30, dxy_5d=0.5, fg={"score": 50}, cot_usd=0,
            news_sent={"label": "risk_on"},
        )
        assert any("Nyheter risk-on men VIX" in c for c in result)

    def test_news_risk_off_greed(self):
        """news risk_off and fg.score>60 -> 'Nyheter risk-off men Fear&Greed viser grådighet'."""
        result = detect_conflict(
            vix=18, dxy_5d=0.5, fg={"score": 65}, cot_usd=0,
            news_sent={"label": "risk_off"},
        )
        assert any("Nyheter risk-off" in c and "grådighet" in c.lower() for c in result)


# ===== Clean / composite =====================================================

class TestComposite:
    """No-conflict baseline and multi-trigger scenarios."""

    def test_no_conflicts(self):
        """All values normal -> empty list."""
        result = detect_conflict(**_SAFE)
        assert result == []

    def test_multiple_conflicts(self):
        """Several triggers fire simultaneously."""
        result = detect_conflict(
            vix=30,
            dxy_5d=-2,
            fg={"score": 20},
            cot_usd=1.5,
            hy_stress=True,
            yield_curve=-0.5,
            news_sent={"label": "risk_on"},
        )
        # At minimum we expect: VIX+DXY, fear+DXY, COT divergence, yield curve, news+VIX, news+fear
        assert len(result) >= 4
        # Verify a few specific strings are present
        conflict_text = " | ".join(result)
        assert "VIX" in conflict_text
        assert "Rentekurve" in conflict_text
        assert "COT" in conflict_text
