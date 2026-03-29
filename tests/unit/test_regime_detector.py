"""Unit tests for src.analysis.regime_detector — regime detection, adjustments, score application."""

from __future__ import annotations

from src.analysis.regime_detector import (
    ENERGY_INSTRUMENTS,
    RISK_ASSETS,
    SAFE_HAVENS,
    MarketRegime,
    apply_regime_to_score,
    detect_regime,
    get_regime_adjustments,
)


# ===== Regime detection =====================================================


class TestDetectRegime:
    """detect_regime threshold and priority tests."""

    def test_normal_regime(self):
        """Low VIX, no events -> NORMAL."""
        regime = detect_regime(15.0, 1.0, 2.0, [], 0.5)
        assert regime == MarketRegime.NORMAL

    def test_risk_off_vix_above_25(self):
        """VIX > 25 but <= 35 with no events -> RISK_OFF."""
        regime = detect_regime(28.0, 5.0, 3.0, [], 1.0)
        assert regime == MarketRegime.RISK_OFF

    def test_risk_off_at_boundary(self):
        """VIX exactly 25 is not > 25, so -> NORMAL."""
        regime = detect_regime(25.0, 0.0, 0.0, [], 0.0)
        assert regime == MarketRegime.NORMAL

    def test_risk_off_just_above_boundary(self):
        """VIX = 25.01 -> RISK_OFF."""
        regime = detect_regime(25.01, 0.0, 0.0, [], 0.0)
        assert regime == MarketRegime.RISK_OFF

    def test_crisis_vix_above_35(self):
        """VIX > 35 with no conflict events -> CRISIS."""
        regime = detect_regime(40.0, 10.0, 5.0, [], 2.0)
        assert regime == MarketRegime.CRISIS

    def test_crisis_at_boundary(self):
        """VIX exactly 35 is not > 35, so -> RISK_OFF."""
        regime = detect_regime(35.0, 0.0, 0.0, [], 0.0)
        assert regime == MarketRegime.RISK_OFF

    def test_war_footing_vix_plus_armed_conflict(self):
        """VIX > 35 + armed_conflict -> WAR_FOOTING (highest priority)."""
        regime = detect_regime(40.0, 15.0, 10.0, ["armed_conflict"], 3.0)
        assert regime == MarketRegime.WAR_FOOTING

    def test_war_footing_vix_plus_political_crisis(self):
        """VIX > 35 + political_crisis -> WAR_FOOTING."""
        regime = detect_regime(42.0, 12.0, 5.0, ["political_crisis"], 2.0)
        assert regime == MarketRegime.WAR_FOOTING

    def test_war_footing_takes_priority_over_crisis(self):
        """WAR_FOOTING is checked before CRISIS for VIX > 35."""
        regime = detect_regime(50.0, 20.0, 30.0, ["armed_conflict", "energy_crisis"], 5.0)
        assert regime == MarketRegime.WAR_FOOTING

    def test_energy_shock(self):
        """Oil > 20% change + energy event -> ENERGY_SHOCK."""
        regime = detect_regime(20.0, 3.0, 25.0, ["energy_crisis"], 1.0)
        assert regime == MarketRegime.ENERGY_SHOCK

    def test_energy_shock_negative_oil_move(self):
        """Oil -25% change + supply_disruption -> ENERGY_SHOCK (abs value)."""
        regime = detect_regime(20.0, 3.0, -25.0, ["supply_disruption"], 1.0)
        assert regime == MarketRegime.ENERGY_SHOCK

    def test_energy_shock_needs_event(self):
        """Oil > 20% but no energy event -> not ENERGY_SHOCK."""
        regime = detect_regime(20.0, 3.0, 25.0, [], 1.0)
        assert regime == MarketRegime.NORMAL

    def test_energy_shock_at_boundary(self):
        """Oil exactly 20% is not > 20%, so no ENERGY_SHOCK."""
        regime = detect_regime(20.0, 0.0, 20.0, ["energy_crisis"], 0.0)
        assert regime == MarketRegime.NORMAL

    def test_sanctions_regime(self):
        """Active sanctions event -> SANCTIONS."""
        regime = detect_regime(18.0, 2.0, 5.0, ["sanctions"], 0.5)
        assert regime == MarketRegime.SANCTIONS

    def test_sanctions_with_low_vix(self):
        """Sanctions detected even with calm VIX."""
        regime = detect_regime(12.0, -1.0, 2.0, ["sanctions"], -0.3)
        assert regime == MarketRegime.SANCTIONS

    def test_priority_war_over_energy(self):
        """VIX > 35 + conflict + energy events -> WAR_FOOTING (VIX priority)."""
        regime = detect_regime(
            40.0, 15.0, 30.0,
            ["armed_conflict", "energy_crisis"],
            3.0,
        )
        assert regime == MarketRegime.WAR_FOOTING

    def test_priority_energy_over_sanctions(self):
        """Energy shock checked before sanctions."""
        regime = detect_regime(
            20.0, 3.0, 25.0,
            ["energy_crisis", "sanctions"],
            1.0,
        )
        assert regime == MarketRegime.ENERGY_SHOCK

    def test_multiple_events_no_conflict(self):
        """Multiple non-conflict events with VIX > 35 -> CRISIS (not WAR)."""
        regime = detect_regime(40.0, 10.0, 5.0, ["sanctions", "energy_crisis"], 2.0)
        assert regime == MarketRegime.CRISIS


# ===== Regime adjustments ===================================================


class TestGetRegimeAdjustments:
    """get_regime_adjustments returns correct override dicts."""

    def test_normal_returns_empty(self):
        """NORMAL regime has no parameter overrides."""
        adj = get_regime_adjustments(MarketRegime.NORMAL)
        assert adj == {}

    def test_risk_off_adjustments(self):
        """RISK_OFF returns min_score=12, risk_pct=0.5, boosts."""
        adj = get_regime_adjustments(MarketRegime.RISK_OFF)
        assert adj["min_score"] == 12
        assert adj["risk_pct"] == 0.5
        assert adj["safe_haven_boost"] == 2
        assert adj["risk_asset_penalty"] == -2

    def test_crisis_adjustments(self):
        """CRISIS returns safe_haven_only=True, tight risk."""
        adj = get_regime_adjustments(MarketRegime.CRISIS)
        assert adj["min_score"] == 14
        assert adj["risk_pct"] == 0.25
        assert adj["max_positions"] == 3
        assert adj["safe_haven_only"] is True

    def test_war_footing_adjustments(self):
        """WAR_FOOTING: tightest risk, safe_haven_only, energy_boost."""
        adj = get_regime_adjustments(MarketRegime.WAR_FOOTING)
        assert adj["min_score"] == 16
        assert adj["risk_pct"] == 0.1
        assert adj["max_positions"] == 2
        assert adj["safe_haven_only"] is True
        assert adj["energy_boost"] == 3

    def test_energy_shock_adjustments(self):
        """ENERGY_SHOCK: energy_boost, max_positions=4."""
        adj = get_regime_adjustments(MarketRegime.ENERGY_SHOCK)
        assert adj["min_score"] == 12
        assert adj["energy_boost"] == 3
        assert adj["max_positions"] == 4

    def test_sanctions_adjustments(self):
        """SANCTIONS: affected_commodity_boost."""
        adj = get_regime_adjustments(MarketRegime.SANCTIONS)
        assert adj["min_score"] == 12
        assert adj["affected_commodity_boost"] == 3

    def test_adjustments_returns_copy(self):
        """Returned dict is a copy, not the internal reference."""
        adj1 = get_regime_adjustments(MarketRegime.RISK_OFF)
        adj1["min_score"] = 999
        adj2 = get_regime_adjustments(MarketRegime.RISK_OFF)
        assert adj2["min_score"] == 12


# ===== Score application ====================================================


class TestApplyRegimeToScore:
    """apply_regime_to_score boost/penalty and clamping tests."""

    def test_safe_haven_boost(self):
        """Gold gets safe_haven_boost in RISK_OFF."""
        adj = get_regime_adjustments(MarketRegime.RISK_OFF)
        score = apply_regime_to_score("XAUUSD", 10, MarketRegime.RISK_OFF, adj)
        assert score == 12  # 10 + 2

    def test_risk_asset_penalty(self):
        """SPX gets risk_asset_penalty in RISK_OFF."""
        adj = get_regime_adjustments(MarketRegime.RISK_OFF)
        score = apply_regime_to_score("SPX", 10, MarketRegime.RISK_OFF, adj)
        assert score == 8  # 10 - 2

    def test_energy_boost(self):
        """Brent gets energy_boost in WAR_FOOTING."""
        adj = get_regime_adjustments(MarketRegime.WAR_FOOTING)
        score = apply_regime_to_score("Brent", 10, MarketRegime.WAR_FOOTING, adj)
        assert score == 13  # 10 + 3

    def test_no_boost_for_unclassified(self):
        """EURUSD (not in any category) gets no boost or penalty."""
        adj = get_regime_adjustments(MarketRegime.RISK_OFF)
        score = apply_regime_to_score("EURUSD", 10, MarketRegime.RISK_OFF, adj)
        assert score == 10

    def test_clamp_upper_bound(self):
        """Score clamped to max 19."""
        adj = get_regime_adjustments(MarketRegime.WAR_FOOTING)
        score = apply_regime_to_score("XAUUSD", 19, MarketRegime.WAR_FOOTING, adj)
        assert score == 19

    def test_clamp_lower_bound(self):
        """Score clamped to min 0."""
        adj = get_regime_adjustments(MarketRegime.RISK_OFF)
        score = apply_regime_to_score("SPX", 1, MarketRegime.RISK_OFF, adj)
        assert score == 0  # 1 + (-2) = -1 -> clamped to 0

    def test_normal_regime_no_change(self):
        """NORMAL regime applies no adjustments to score."""
        adj = get_regime_adjustments(MarketRegime.NORMAL)
        score = apply_regime_to_score("XAUUSD", 10, MarketRegime.NORMAL, adj)
        assert score == 10

    def test_energy_shock_natgas_boost(self):
        """NATGAS gets energy_boost in ENERGY_SHOCK."""
        adj = get_regime_adjustments(MarketRegime.ENERGY_SHOCK)
        score = apply_regime_to_score("NATGAS", 8, MarketRegime.ENERGY_SHOCK, adj)
        assert score == 11  # 8 + 3


# ===== Regime transitions ===================================================


class TestRegimeTransitions:
    """Test that regime transitions follow expected patterns."""

    def test_normal_to_risk_off(self):
        """VIX crossing 25 triggers transition from NORMAL to RISK_OFF."""
        assert detect_regime(24.0, 0.0, 0.0, [], 0.0) == MarketRegime.NORMAL
        assert detect_regime(26.0, 0.0, 0.0, [], 0.0) == MarketRegime.RISK_OFF

    def test_risk_off_to_crisis(self):
        """VIX crossing 35 escalates RISK_OFF to CRISIS."""
        assert detect_regime(30.0, 0.0, 0.0, [], 0.0) == MarketRegime.RISK_OFF
        assert detect_regime(36.0, 0.0, 0.0, [], 0.0) == MarketRegime.CRISIS

    def test_crisis_to_war_footing(self):
        """Adding armed_conflict at VIX > 35 escalates to WAR_FOOTING."""
        assert detect_regime(40.0, 0.0, 0.0, [], 0.0) == MarketRegime.CRISIS
        assert detect_regime(40.0, 0.0, 0.0, ["armed_conflict"], 0.0) == MarketRegime.WAR_FOOTING

    def test_war_footing_deescalation(self):
        """Removing conflict events de-escalates WAR_FOOTING to CRISIS."""
        assert detect_regime(40.0, 0.0, 0.0, ["armed_conflict"], 0.0) == MarketRegime.WAR_FOOTING
        assert detect_regime(40.0, 0.0, 0.0, [], 0.0) == MarketRegime.CRISIS


# ===== Asset classification =================================================


class TestAssetClassification:
    """Verify asset sets contain expected instruments."""

    def test_safe_havens_contain_gold(self):
        assert "XAUUSD" in SAFE_HAVENS
        assert "Gold" in SAFE_HAVENS

    def test_safe_havens_contain_chf(self):
        assert "USDCHF" in SAFE_HAVENS

    def test_risk_assets_contain_indices(self):
        assert "SPX" in RISK_ASSETS
        assert "NAS100" in RISK_ASSETS

    def test_energy_instruments(self):
        assert "Brent" in ENERGY_INSTRUMENTS
        assert "WTI" in ENERGY_INSTRUMENTS
        assert "NATGAS" in ENERGY_INSTRUMENTS
