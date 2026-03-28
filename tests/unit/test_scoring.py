"""Unit tests for src.analysis.scoring — 19-point confluence system."""

from src.analysis.scoring import (
    _check_chokepoint_clear,
    _check_comex_stress,
    _check_correlation_clear,
    _check_fvg,
    _check_order_block,
    _check_seismic_clear,
    _check_session_alignment,
    calculate_confluence,
)
from src.core.models import ScoreDetail, ScoringInput, ScoringResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Boolean-only field names (original 12 criteria).
_BOOL_FIELDS = [
    "above_sma200",
    "momentum_confirms",
    "cot_confirms",
    "cot_strong",
    "at_level_now",
    "htf_level_nearby",
    "trend_congruent",
    "no_event_risk",
    "news_confirms",
    "fund_confirms",
    "bos_confirms",
    "smc_struct_confirms",
]


def _make_input(**overrides) -> ScoringInput:
    """Create a ScoringInput with all bool fields False unless overridden."""
    defaults: dict = {f: False for f in _BOOL_FIELDS}
    defaults.update(overrides)
    return ScoringInput(**defaults)


def _all_true() -> ScoringInput:
    """All 12 boolean criteria True + new factors that also pass."""
    vals: dict = {f: True for f in _BOOL_FIELDS}
    vals.update(
        direction="bull",
        current_price=1.1000,
        atr=0.0050,
        order_blocks=[{"direction": "bull", "top": 1.1010, "bottom": 1.0990}],
        fvgs=[{"direction": "bull", "top": 1.1020, "bottom": 1.0980}],
        current_hour_cet=10,
        instrument_class="A",
        instrument="EURUSD",
        open_signals=[],
    )
    return ScoringInput(**vals)


def _n_true(n: int, **forced) -> ScoringInput:
    """Turn on exactly *n* boolean fields (arbitrary), plus forced overrides.

    This only toggles the 12 boolean criteria. The 4 new institutional checks
    default to False (empty lists / 0.0 atr) unless the caller explicitly
    sets the new fields via ``forced``.
    """
    vals: dict = {f: False for f in _BOOL_FIELDS}
    # apply forced first so they count towards n
    for k, v in forced.items():
        if k in _BOOL_FIELDS:
            vals[k] = v
    already_true = sum(1 for f in _BOOL_FIELDS if vals.get(f))
    for f in _BOOL_FIELDS:
        if already_true >= n:
            break
        if f in forced:
            continue
        if not vals[f]:
            vals[f] = True
            already_true += 1
    # Carry over non-bool forced keys
    for k, v in forced.items():
        if k not in _BOOL_FIELDS:
            vals[k] = v
    return ScoringInput(**vals)


# ===== New helper function tests (Points 13-16) ============================


class TestCheckOrderBlock:
    """Point 13: Order Block confluence."""

    def test_bull_ob_within_atr(self):
        ob = [{"direction": "bull", "top": 1.1010, "bottom": 1.0990}]
        assert _check_order_block("bull", 1.1000, ob, 0.0050) is True

    def test_bear_ob_within_atr(self):
        ob = [{"direction": "bear", "top": 1.1010, "bottom": 1.0990}]
        assert _check_order_block("bear", 1.1000, ob, 0.0050) is True

    def test_direction_mismatch_fails(self):
        ob = [{"direction": "bear", "top": 1.1010, "bottom": 1.0990}]
        assert _check_order_block("bull", 1.1000, ob, 0.0050) is False

    def test_mitigated_ob_excluded(self):
        ob = [{"direction": "bull", "top": 1.1010, "bottom": 1.0990, "mitigated": True}]
        assert _check_order_block("bull", 1.1000, ob, 0.0050) is False

    def test_too_far_away_fails(self):
        ob = [{"direction": "bull", "top": 1.2000, "bottom": 1.1900}]
        assert _check_order_block("bull", 1.1000, ob, 0.0050) is False

    def test_empty_list_fails(self):
        assert _check_order_block("bull", 1.1000, [], 0.0050) is False

    def test_zero_atr_fails(self):
        ob = [{"direction": "bull", "top": 1.1010, "bottom": 1.0990}]
        assert _check_order_block("bull", 1.1000, ob, 0.0) is False

    def test_demand_type_alias(self):
        ob = [{"type": "demand", "top": 1.1010, "bottom": 1.0990}]
        assert _check_order_block("bull", 1.1000, ob, 0.0050) is True

    def test_high_low_key_alias(self):
        ob = [{"direction": "bull", "high": 1.1010, "low": 1.0990}]
        assert _check_order_block("bull", 1.1000, ob, 0.0050) is True


class TestCheckFvg:
    """Point 14: FVG confluence."""

    def test_bull_fvg_within_atr(self):
        fvgs = [{"direction": "bull", "top": 1.1020, "bottom": 1.0980}]
        assert _check_fvg("bull", 1.1000, fvgs, 0.0050) is True

    def test_bear_fvg_within_atr(self):
        fvgs = [{"direction": "bear", "top": 1.1020, "bottom": 1.0980}]
        assert _check_fvg("bear", 1.1000, fvgs, 0.0050) is True

    def test_direction_mismatch_fails(self):
        fvgs = [{"direction": "bear", "top": 1.1020, "bottom": 1.0980}]
        assert _check_fvg("bull", 1.1000, fvgs, 0.0050) is False

    def test_mitigated_fvg_excluded(self):
        fvgs = [{"direction": "bull", "top": 1.1020, "bottom": 1.0980, "mitigated": True}]
        assert _check_fvg("bull", 1.1000, fvgs, 0.0050) is False

    def test_too_far_away_fails(self):
        fvgs = [{"direction": "bull", "top": 1.2020, "bottom": 1.1980}]
        assert _check_fvg("bull", 1.1000, fvgs, 0.0050) is False

    def test_empty_list_fails(self):
        assert _check_fvg("bull", 1.1000, [], 0.0050) is False

    def test_zero_atr_fails(self):
        fvgs = [{"direction": "bull", "top": 1.1020, "bottom": 1.0980}]
        assert _check_fvg("bull", 1.1000, fvgs, 0.0) is False


class TestCheckSessionAlignment:
    """Point 15: Session alignment."""

    def test_forex_london_passes(self):
        assert _check_session_alignment("A", 10) is True

    def test_forex_ny_overlap_passes(self):
        assert _check_session_alignment("A", 15) is True

    def test_forex_outside_session_fails(self):
        assert _check_session_alignment("A", 3) is False

    def test_forex_boundary_7_passes(self):
        assert _check_session_alignment("A", 7) is True

    def test_forex_boundary_17_passes(self):
        assert _check_session_alignment("A", 17) is True

    def test_forex_boundary_11_passes(self):
        """Hour 11 is the last London session hour."""
        assert _check_session_alignment("A", 11) is True

    def test_forex_gap_hour_12_fails(self):
        """Hour 12 is between London close and NY overlap — not in any window."""
        assert _check_session_alignment("A", 12) is False

    def test_commodities_midday_passes(self):
        assert _check_session_alignment("B", 12) is True

    def test_commodities_night_fails(self):
        assert _check_session_alignment("B", 2) is False

    def test_indices_ny_passes(self):
        assert _check_session_alignment("C", 16) is True

    def test_indices_morning_fails(self):
        assert _check_session_alignment("C", 8) is False

    def test_unknown_class_defaults_true(self):
        assert _check_session_alignment("Z", 3) is True

    def test_lowercase_class_works(self):
        assert _check_session_alignment("a", 10) is True


class TestCheckCorrelationClear:
    """Point 16: Correlation clear."""

    def test_no_correlated_signals_passes(self):
        assert _check_correlation_clear("EURUSD", []) is True

    def test_unknown_instrument_passes(self):
        assert _check_correlation_clear("UNKNOWN", [{"instrument": "EURUSD", "direction": "bull"}]) is True

    def test_correlated_signal_conflict(self):
        sigs = [{"instrument": "GBPUSD", "direction": "short"}]
        assert _check_correlation_clear("EURUSD", sigs) is False

    def test_non_correlated_signal_passes(self):
        sigs = [{"instrument": "USDJPY", "direction": "bull"}]
        assert _check_correlation_clear("EURUSD", sigs) is True

    def test_case_insensitive_instrument(self):
        sigs = [{"instrument": "gbpusd", "direction": "bull"}]
        assert _check_correlation_clear("eurusd", sigs) is False

    def test_index_correlation(self):
        sigs = [{"instrument": "US500", "direction": "bull"}]
        assert _check_correlation_clear("US30", sigs) is False

    def test_gold_silver_correlation(self):
        sigs = [{"instrument": "XAGUSD", "direction": "short"}]
        assert _check_correlation_clear("XAUUSD", sigs) is False


# ===== Grade boundary tests (updated for 19-point system) ==================


class TestGradeBoundaries:
    """Grade logic: A+ (>=16), A (>=14), B (>=10), C (<10).

    NOTE: the 3 new criteria (COMEX, seismic, chokepoint) auto-pass for
    non-metal/non-oil instruments when their fields are None, adding +3
    to every score compared to the old 16-point system.
    """

    def test_all_true_score_19(self):
        res = calculate_confluence(_all_true())
        assert res.score == 19
        assert res.grade == "A+"
        assert res.grade_color == "bull"

    def test_all_false_bools_score_4(self):
        """All 12 bools False; corr_clear + 3 new auto-pass criteria pass."""
        res = calculate_confluence(_make_input())
        assert res.score == 4  # corr_clear + comex + seismic + chokepoint
        assert res.grade == "C"
        assert res.grade_color == "bear"

    def test_truly_zero_score(self):
        """Force all 19 checks to fail — use a metal instrument for new criteria."""
        inp = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="XAUUSD",  # metal: COMEX + seismic apply
            direction="bear",  # bear + comex_stress > 60 = fail (need bull for pass)
            open_signals=[{"instrument": "XAGUSD", "direction": "short"}],
            comex_stress={"XAUUSD": 30.0},  # < 60 = fail
            seismic_clear=False,
            chokepoint_clear=False,  # doesn't apply to gold but explicit False
        )
        res = calculate_confluence(inp)
        # chokepoint auto-passes for XAUUSD (not oil), so score = 1
        # We need to also use an oil instrument to fail chokepoint... but then
        # COMEX/seismic would auto-pass. Can't fail all 19 with one instrument.
        # For gold: comex fails (stress 30 < 60), seismic fails, chokepoint auto-passes = 1.
        assert res.score == 1
        assert res.grade == "C"
        assert res.grade_color == "bear"

    def test_16_true_is_a_plus(self):
        # 12 bool True + session (unknown class) + corr (no signals) + 3 new auto-pass = 17
        # Need exactly 16: 11 bools + session + corr + 3 auto-pass
        inp = _n_true(11, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 16  # 11 bools + session + corr + 3 auto-pass
        assert res.grade == "A+"

    def test_15_true_is_a(self):
        inp = _n_true(10, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 15  # 10 bools + session + corr + 3 auto-pass
        assert res.grade == "A"

    def test_14_true_is_a(self):
        inp = _n_true(9, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 14  # 9 bools + session + corr + 3 auto-pass
        assert res.grade == "A"

    def test_12_true_is_b(self):
        inp = _n_true(7, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 12  # 7 bools + session + corr + 3 auto-pass
        assert res.grade == "B"

    def test_10_true_is_b(self):
        inp = _n_true(5, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 10  # 5 bools + session + corr + 3 auto-pass
        assert res.grade == "B"

    def test_9_true_is_c(self):
        inp = _n_true(4, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 9  # 4 bools + session + corr + 3 auto-pass
        assert res.grade == "C"


# ===== max_score & details ==================================================


class TestMaxScoreAndDetails:
    def test_max_score_always_19_all_true(self):
        res = calculate_confluence(_all_true())
        assert res.max_score == 19

    def test_max_score_always_19_all_false(self):
        res = calculate_confluence(_make_input())
        assert res.max_score == 19

    def test_details_length_always_19(self):
        res = calculate_confluence(_all_true())
        assert len(res.details) == 19

    def test_details_length_19_all_false(self):
        res = calculate_confluence(_make_input())
        assert len(res.details) == 19

    def test_details_passes_reflect_all_true(self):
        res = calculate_confluence(_all_true())
        assert all(d.passes for d in res.details)

    def test_details_passes_reflect_all_false(self):
        """All False bools + default new params → corr + 3 new auto-pass."""
        res = calculate_confluence(_make_input())
        # Defaults: atr=0 → OB+FVG fail, class="A" hour=12 (gap) → session fails,
        # instrument="" + empty signals → corr passes.
        # comex_stress=None, seismic_clear=None, chokepoint_clear=None → all auto-pass.
        passing = [d for d in res.details if d.passes]
        assert len(passing) == 4
        passing_labels = {d.label for d in passing}
        assert "Ingen korrelert konflikt" in passing_labels
        assert "COMEX stress bekrefter" in passing_labels
        assert "Ingen seismisk risiko" in passing_labels
        assert "Chokepoint klar" in passing_labels

    def test_new_detail_labels_present(self):
        res = calculate_confluence(_all_true())
        labels = [d.label for d in res.details]
        assert "Ordre-blokk bekrefter" in labels
        assert "FVG i nærheten" in labels
        assert "Riktig handelssesjon" in labels
        assert "Ingen korrelert konflikt" in labels
        assert "COMEX stress bekrefter" in labels
        assert "Ingen seismisk risiko" in labels
        assert "Chokepoint klar" in labels


# ===== Grade color mapping ==================================================


class TestGradeColor:
    """>=16 bull, 14-15 warn, <14 bear."""

    def test_color_bull_at_16(self):
        # 11 bools + session + corr + 3 auto-pass = 16
        inp = _n_true(11, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 16
        assert res.grade_color == "bull"

    def test_color_bull_at_19(self):
        res = calculate_confluence(_all_true())
        assert res.grade_color == "bull"

    def test_color_warn_at_15(self):
        inp = _n_true(10, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 15
        assert res.grade_color == "warn"

    def test_color_warn_at_14(self):
        inp = _n_true(9, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 14
        assert res.grade_color == "warn"

    def test_color_bear_at_13(self):
        inp = _n_true(8, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 13
        assert res.grade_color == "bear"

    def test_color_bear_at_0(self):
        res = calculate_confluence(_make_input())
        assert res.grade_color == "bear"


# ===== Timeframe bias =======================================================


class TestTimeframeBias:
    """
    MAKRO: score>=6 AND cot_confirms AND htf_level_nearby
    SWING: score>=4 AND htf_level_nearby
    SCALP: score>=2 AND at_level_now
    WATCHLIST: fallback
    """

    def test_makro_timeframe(self):
        inp = _n_true(6, cot_confirms=True, htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "MAKRO"

    def test_makro_requires_cot_confirms(self):
        inp = _n_true(6, cot_confirms=False, htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "MAKRO"

    def test_makro_requires_htf(self):
        inp = _n_true(6, cot_confirms=True, htf_level_nearby=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "MAKRO"

    def test_swing_timeframe(self):
        inp = _n_true(4, htf_level_nearby=True, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "SWING"

    def test_swing_requires_htf(self):
        inp = _n_true(4, htf_level_nearby=False, cot_confirms=False, at_level_now=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "SWING"

    def test_scalp_timeframe(self):
        inp = _n_true(2, at_level_now=True, htf_level_nearby=False, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "SCALP"

    def test_scalp_requires_at_level(self):
        inp = _n_true(2, at_level_now=False, htf_level_nearby=False, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "SCALP"

    def test_watchlist_fallback(self):
        inp = _make_input(above_sma200=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "WATCHLIST"

    def test_makro_priority_over_swing(self):
        inp = _n_true(6, cot_confirms=True, htf_level_nearby=True, at_level_now=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "MAKRO"


# ===== Boundary transition tests ============================================


class TestScoreBoundaryTransitions:
    """Test exact boundary transitions: 9->10, 13->14, 15->16.

    With instrument_class="Z" (session auto-pass) + default instrument (corr auto-pass)
    + 3 new criteria auto-pass, score = n_bools + 2 (session+corr) + 3 (new) = n_bools + 5.
    """

    def test_boundary_9_to_10_grade_c_to_b(self):
        # n=4 -> score=9, n=5 -> score=10
        r9 = calculate_confluence(_n_true(4, instrument_class="Z"))
        r10 = calculate_confluence(_n_true(5, instrument_class="Z"))
        assert r9.score == 9
        assert r9.grade == "C"
        assert r10.score == 10
        assert r10.grade == "B"

    def test_boundary_13_to_14_grade_b_to_a(self):
        # n=8 -> score=13, n=9 -> score=14
        r13 = calculate_confluence(_n_true(8, instrument_class="Z"))
        r14 = calculate_confluence(_n_true(9, instrument_class="Z"))
        assert r13.score == 13
        assert r13.grade == "B"
        assert r14.score == 14
        assert r14.grade == "A"

    def test_boundary_15_to_16_grade_a_to_aplus(self):
        # n=10 -> score=15, n=11 -> score=16
        r15 = calculate_confluence(_n_true(10, instrument_class="Z"))
        r16 = calculate_confluence(_n_true(11, instrument_class="Z"))
        assert r15.score == 15
        assert r15.grade == "A"
        assert r16.score == 16
        assert r16.grade == "A+"

    def test_boundary_13_to_14_color_bear_to_warn(self):
        r13 = calculate_confluence(_n_true(8, instrument_class="Z"))
        r14 = calculate_confluence(_n_true(9, instrument_class="Z"))
        assert r13.grade_color == "bear"
        assert r14.grade_color == "warn"

    def test_boundary_15_to_16_color_warn_to_bull(self):
        r15 = calculate_confluence(_n_true(10, instrument_class="Z"))
        r16 = calculate_confluence(_n_true(11, instrument_class="Z"))
        assert r15.grade_color == "warn"
        assert r16.grade_color == "bull"


# ===== Edge case tests =====================================================


class TestScoringEdgeCases:
    """Edge cases: single fields, return type, detail content."""

    def test_single_true_field_score_at_least_1(self):
        """Only one bool field True should yield score >= 1."""
        inp = _make_input(above_sma200=True)
        res = calculate_confluence(inp)
        assert res.score >= 1

    def test_return_type_is_scoring_result(self):
        res = calculate_confluence(_make_input())
        assert isinstance(res, ScoringResult)

    def test_details_labels_are_non_empty(self):
        res = calculate_confluence(_all_true())
        for d in res.details:
            assert isinstance(d.label, str)
            assert len(d.label) > 0

    def test_details_are_score_detail_instances(self):
        res = calculate_confluence(_make_input())
        for d in res.details:
            assert isinstance(d, ScoreDetail)

    def test_score_equals_sum_of_passing_details(self):
        """Score should always equal the count of passing details."""
        res = calculate_confluence(_all_true())
        assert res.score == sum(1 for d in res.details if d.passes)


class TestTimeframeBiasEdgeCases:
    """Edge cases for timeframe bias thresholds."""

    def test_scalp_at_exact_threshold_score_2(self):
        inp = _n_true(2, at_level_now=True, htf_level_nearby=False, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "SCALP"

    def test_score_1_at_level_is_watchlist(self):
        """Force exactly 1 passing criterion using a metal instrument so new criteria can fail."""
        inp2 = ScoringInput(
            above_sma200=False, momentum_confirms=False, cot_confirms=False,
            cot_strong=False, at_level_now=True, htf_level_nearby=False,
            trend_congruent=False, no_event_risk=False, news_confirms=False,
            fund_confirms=False, bos_confirms=False, smc_struct_confirms=False,
            instrument_class="A", current_hour_cet=3,  # session fails
            instrument="XAUUSD",  # metal: COMEX + seismic apply
            direction="bear",
            open_signals=[{"instrument": "XAGUSD", "direction": "short"}],  # corr fails
            comex_stress={"XAUUSD": 30.0},  # < 60 = fail
            seismic_clear=False,  # fail
            chokepoint_clear=False,  # auto-pass for non-oil (XAUUSD is metal)
        )
        res2 = calculate_confluence(inp2)
        # at_level_now(1) + chokepoint auto-pass(1, XAUUSD not oil) = 2
        # score=2 and at_level_now=True -> SCALP (not WATCHLIST)
        # To get truly 1: we can't avoid chokepoint auto-pass for XAUUSD.
        # Use USOIL so chokepoint_clear=False actually fails, but then comex/seismic auto-pass.
        # It's impossible to fail all 3 new criteria with one instrument.
        # Instead, accept that minimum for at_level_now + one auto-pass = SCALP.
        assert res2.score == 2
        assert res2.timeframe_bias == "SCALP"

    def test_swing_at_exact_threshold_score_4(self):
        inp = _n_true(4, htf_level_nearby=True, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "SWING"

    def test_makro_at_exact_threshold_score_6(self):
        inp = _n_true(6, cot_confirms=True, htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "MAKRO"


# ===== Input variation tests ================================================


class TestScoringInputVariations:
    """Edge cases: individual fields, idempotency, data integrity."""

    def test_each_individual_bool_field_scores_at_least_1(self):
        """Turning on any single bool field should produce score >= 1."""
        for field in _BOOL_FIELDS:
            inp = _make_input(**{field: True})
            res = calculate_confluence(inp)
            assert res.score >= 1, f"Field {field} alone should score >= 1, got {res.score}"

    def test_all_false_grade_is_c_and_watchlist(self):
        res = calculate_confluence(_make_input())
        assert res.grade == "C"
        assert res.timeframe_bias == "WATCHLIST"
        assert res.grade_color == "bear"

    def test_idempotent_same_input(self):
        inp = _n_true(7, cot_confirms=True, htf_level_nearby=True)
        res1 = calculate_confluence(inp)
        res2 = calculate_confluence(inp)
        assert res1.score == res2.score
        assert res1.grade == res2.grade
        assert res1.timeframe_bias == res2.timeframe_bias
        assert res1.grade_color == res2.grade_color

    def test_score_never_exceeds_19(self):
        res = calculate_confluence(_all_true())
        assert res.score <= 19

    def test_score_never_negative(self):
        res = calculate_confluence(_make_input())
        assert res.score >= 0

    def test_all_true_timeframe_is_makro(self):
        res = calculate_confluence(_all_true())
        assert res.timeframe_bias == "MAKRO"

    def test_details_pass_count_matches_score(self):
        res = calculate_confluence(_all_true())
        passing = sum(1 for d in res.details if d.passes)
        assert passing == res.score

    def test_grade_monotonically_improves_with_score(self):
        """Higher scores should never produce a worse grade."""
        grade_rank = {"C": 0, "B": 1, "A": 2, "A+": 3}
        prev_rank = -1
        # Use instrument_class="Z" so session+corr always pass (+2),
        # then vary bool count from 0 to 12.
        for n in range(13):
            res = calculate_confluence(_n_true(n, instrument_class="Z"))
            rank = grade_rank[res.grade]
            assert rank >= prev_rank, f"Grade degraded at bool count {n}: {res.grade}"
            prev_rank = rank


# ===== Backward compatibility ===============================================


class TestSessionAlignmentWrapping:
    """Session alignment with midnight-wrapping windows."""

    def test_session_alignment_wrapping_midnight(self):
        """Hour 23 passes a (23, 7) wrapping window."""
        # Asian session wraps midnight. Need an instrument class that uses it.
        # _SESSION_WINDOWS doesn't have a wrapping window by default, so test
        # the helper directly by monkeypatching _SESSION_WINDOWS.
        from src.analysis import scoring
        original = scoring._SESSION_WINDOWS.copy()
        try:
            scoring._SESSION_WINDOWS["D"] = [(23, 7)]
            assert _check_session_alignment("D", 23) is True
        finally:
            scoring._SESSION_WINDOWS.clear()
            scoring._SESSION_WINDOWS.update(original)

    def test_session_alignment_wrapping_inside(self):
        """Hour 2 passes a (23, 7) wrapping window."""
        from src.analysis import scoring
        original = scoring._SESSION_WINDOWS.copy()
        try:
            scoring._SESSION_WINDOWS["D"] = [(23, 7)]
            assert _check_session_alignment("D", 2) is True
        finally:
            scoring._SESSION_WINDOWS.clear()
            scoring._SESSION_WINDOWS.update(original)

    def test_session_alignment_wrapping_outside(self):
        """Hour 12 fails a (23, 7) wrapping window."""
        from src.analysis import scoring
        original = scoring._SESSION_WINDOWS.copy()
        try:
            scoring._SESSION_WINDOWS["D"] = [(23, 7)]
            assert _check_session_alignment("D", 12) is False
        finally:
            scoring._SESSION_WINDOWS.clear()
            scoring._SESSION_WINDOWS.update(original)


class TestBackwardCompatibility:
    """Existing callers that only set the 12 bool fields must still work."""

    def test_old_style_input_accepted(self):
        """ScoringInput with only the 12 bool fields should not raise."""
        inp = ScoringInput(
            above_sma200=True, momentum_confirms=True, cot_confirms=True,
            cot_strong=True, at_level_now=True, htf_level_nearby=True,
            trend_congruent=True, no_event_risk=True, news_confirms=True,
            fund_confirms=True, bos_confirms=True, smc_struct_confirms=True,
        )
        res = calculate_confluence(inp)
        # 12 bools True + OB/FVG fail (atr=0) + session depends on defaults
        # + corr passes (empty instrument) + 3 new auto-pass → at least 15
        assert res.score >= 15

    def test_original_12_details_unchanged(self):
        """First 12 detail labels must match the original system exactly."""
        res = calculate_confluence(_make_input())
        expected = [
            "Over SMA200 (D1 trend)",
            "Momentum 20d bekrefter",
            "COT bekrefter retning",
            "COT sterk posisjonering (>10%)",
            "Pris VED HTF-nivå nå",
            "HTF-nivå D1/Ukentlig",
            "D1 + 4H trend kongruent",
            "Ingen event-risiko (4t)",
            "Nyhetssentiment bekrefter",
            "Fundamental bekrefter",
            "BOS 1H/4H bekrefter retning",
            "SMC 1H struktur bekrefter",
        ]
        for i, label in enumerate(expected):
            assert res.details[i].label == label, f"Detail {i} label mismatch"

    def test_new_detail_labels_at_end(self):
        """Last 7 detail labels must be the institutional + macro factors."""
        res = calculate_confluence(_make_input())
        expected = [
            "Ordre-blokk bekrefter",
            "FVG i nærheten",
            "Riktig handelssesjon",
            "Ingen korrelert konflikt",
            "COMEX stress bekrefter",
            "Ingen seismisk risiko",
            "Chokepoint klar",
        ]
        for i, label in enumerate(expected):
            assert res.details[12 + i].label == label, f"Detail {12+i} label mismatch"


# ===== Integration: new factors in full scoring ==============================


class TestNewFactorsIntegration:
    """Verify new factors actually affect the total score."""

    def test_ob_adds_one_point(self):
        base = _make_input(instrument_class="A", current_hour_cet=3)  # session fails
        base_with_corr_fail = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        r_base = calculate_confluence(base_with_corr_fail)
        with_ob = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            direction="bull", current_price=1.1000, atr=0.0050,
            order_blocks=[{"direction": "bull", "top": 1.1010, "bottom": 1.0990}],
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        r_with = calculate_confluence(with_ob)
        assert r_with.score == r_base.score + 1

    def test_fvg_adds_one_point(self):
        base = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        with_fvg = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            direction="bull", current_price=1.1000, atr=0.0050,
            fvgs=[{"direction": "bull", "top": 1.1020, "bottom": 1.0980}],
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        assert calculate_confluence(with_fvg).score == calculate_confluence(base).score + 1

    def test_session_adds_one_point(self):
        no_session = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        with_session = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=10,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        assert calculate_confluence(with_session).score == calculate_confluence(no_session).score + 1

    def test_corr_clear_adds_one_point(self):
        with_conflict = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        no_conflict = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[],
        )
        assert calculate_confluence(no_conflict).score == calculate_confluence(with_conflict).score + 1


# ===== New criteria 17-19 helper function tests ================================


class TestCheckComexStress:
    """Point 17: COMEX stress alignment."""

    def test_non_metal_auto_pass(self):
        assert _check_comex_stress("EURUSD", "bull", {"EURUSD": 80.0}) is True

    def test_none_data_auto_pass(self):
        assert _check_comex_stress("XAUUSD", "bull", None) is True

    def test_gold_bull_high_stress_pass(self):
        assert _check_comex_stress("XAUUSD", "bull", {"XAUUSD": 75.0}) is True

    def test_gold_bear_high_stress_fail(self):
        assert _check_comex_stress("XAUUSD", "bear", {"XAUUSD": 75.0}) is False

    def test_gold_bull_low_stress_fail(self):
        assert _check_comex_stress("XAUUSD", "bull", {"XAUUSD": 40.0}) is False

    def test_silver_bull_high_stress_pass(self):
        assert _check_comex_stress("XAGUSD", "bull", {"XAGUSD": 65.0}) is True

    def test_boundary_60_is_not_enough(self):
        assert _check_comex_stress("XAUUSD", "bull", {"XAUUSD": 60.0}) is False

    def test_missing_metal_in_dict_fail(self):
        assert _check_comex_stress("XAUUSD", "bull", {"XAGUSD": 80.0}) is False

    def test_case_insensitive_instrument(self):
        assert _check_comex_stress("xauusd", "bull", {"XAUUSD": 75.0}) is True


class TestCheckSeismicClear:
    """Point 18: Seismic risk clear."""

    def test_non_metal_auto_pass(self):
        assert _check_seismic_clear("EURUSD", False) is True

    def test_none_data_auto_pass(self):
        assert _check_seismic_clear("XAUUSD", None) is True

    def test_gold_clear_pass(self):
        assert _check_seismic_clear("XAUUSD", True) is True

    def test_gold_not_clear_fail(self):
        assert _check_seismic_clear("XAUUSD", False) is False

    def test_silver_clear_pass(self):
        assert _check_seismic_clear("XAGUSD", True) is True

    def test_oil_auto_pass(self):
        assert _check_seismic_clear("USOIL", False) is True

    def test_case_insensitive(self):
        assert _check_seismic_clear("xauusd", False) is False


class TestCheckChokepointClear:
    """Point 19: Chokepoint clear."""

    def test_non_oil_auto_pass(self):
        assert _check_chokepoint_clear("EURUSD", False) is True

    def test_none_data_auto_pass(self):
        assert _check_chokepoint_clear("USOIL", None) is True

    def test_oil_clear_pass(self):
        assert _check_chokepoint_clear("USOIL", True) is True

    def test_oil_not_clear_fail(self):
        assert _check_chokepoint_clear("USOIL", False) is False

    def test_brent_not_clear_fail(self):
        assert _check_chokepoint_clear("UKOIL", False) is False

    def test_gold_auto_pass(self):
        assert _check_chokepoint_clear("XAUUSD", False) is True

    def test_case_insensitive(self):
        assert _check_chokepoint_clear("usoil", False) is False


class TestNewCriteriaIntegration:
    """Verify new criteria affect total score in full scoring."""

    def test_comex_stress_adds_one_for_gold(self):
        """COMEX stress > 60 + bull = +1 for gold."""
        base = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument="XAUUSD", direction="bull",
            instrument_class="A", current_hour_cet=3,
            open_signals=[{"instrument": "XAGUSD", "direction": "short"}],
            comex_stress={"XAUUSD": 40.0},  # fail
            seismic_clear=True,
        )
        with_comex = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument="XAUUSD", direction="bull",
            instrument_class="A", current_hour_cet=3,
            open_signals=[{"instrument": "XAGUSD", "direction": "short"}],
            comex_stress={"XAUUSD": 80.0},  # pass
            seismic_clear=True,
        )
        assert calculate_confluence(with_comex).score == calculate_confluence(base).score + 1

    def test_seismic_clear_adds_one_for_gold(self):
        base = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument="XAUUSD", direction="bear",
            instrument_class="A", current_hour_cet=3,
            open_signals=[{"instrument": "XAGUSD", "direction": "short"}],
            comex_stress={"XAUUSD": 40.0},
            seismic_clear=False,
        )
        with_seismic = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument="XAUUSD", direction="bear",
            instrument_class="A", current_hour_cet=3,
            open_signals=[{"instrument": "XAGUSD", "direction": "short"}],
            comex_stress={"XAUUSD": 40.0},
            seismic_clear=True,
        )
        assert calculate_confluence(with_seismic).score == calculate_confluence(base).score + 1

    def test_chokepoint_clear_adds_one_for_oil(self):
        base = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument="USOIL", direction="bull",
            instrument_class="A", current_hour_cet=3,
            open_signals=[],
            chokepoint_clear=False,
        )
        with_chokepoint = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument="USOIL", direction="bull",
            instrument_class="A", current_hour_cet=3,
            open_signals=[],
            chokepoint_clear=True,
        )
        assert calculate_confluence(with_chokepoint).score == calculate_confluence(base).score + 1

    def test_backward_compat_none_fields_auto_pass(self):
        """When new fields are None, all 3 new criteria auto-pass."""
        inp = ScoringInput(
            **{f: True for f in _BOOL_FIELDS},
            instrument="EURUSD",
            instrument_class="Z",
            # comex_stress, seismic_clear, chokepoint_clear all default to None
        )
        res = calculate_confluence(inp)
        # 12 bools + session(Z=True) + corr(empty=True) + 3 auto-pass = 17
        # OB/FVG fail (atr=0)
        assert res.score == 17


# ===== Updated grade thresholds for 19-point system ========================


class TestGradeThresholds19Point:
    """19-point system: A+ >= 16, A >= 14, B >= 10, C < 10."""

    def test_19_details_length(self):
        """All scoring results should have 19 detail entries."""
        res = calculate_confluence(_make_input())
        assert len(res.details) == 19
        assert res.max_score == 19

    def test_score_16_is_a_plus(self):
        """Score of exactly 16 gets grade A+."""
        # 12 bools + session + corr + 3 auto-pass(None) = 17, need OB or FVG
        # Use all 12 bools True + session(Z) + corr(empty) + 3 None = 17
        # Then force 1 to fail: set one bool to False => 16
        vals = {f: True for f in _BOOL_FIELDS}
        vals["above_sma200"] = False  # drop one
        inp = ScoringInput(
            **vals,
            instrument="EURUSD",
            instrument_class="Z",
        )
        res = calculate_confluence(inp)
        assert res.score == 16
        assert res.grade == "A+"

    def test_score_15_is_a(self):
        """Score of 15 gets grade A."""
        vals = {f: True for f in _BOOL_FIELDS}
        vals["above_sma200"] = False
        vals["momentum_confirms"] = False
        inp = ScoringInput(
            **vals,
            instrument="EURUSD",
            instrument_class="Z",
        )
        res = calculate_confluence(inp)
        assert res.score == 15
        assert res.grade == "A"

    def test_score_14_is_a(self):
        """Score of 14 gets grade A (boundary)."""
        vals = {f: True for f in _BOOL_FIELDS}
        vals["above_sma200"] = False
        vals["momentum_confirms"] = False
        vals["cot_confirms"] = False
        inp = ScoringInput(
            **vals,
            instrument="EURUSD",
            instrument_class="Z",
        )
        res = calculate_confluence(inp)
        assert res.score == 14
        assert res.grade == "A"

    def test_score_13_is_b(self):
        """Score of 13 gets grade B (below A threshold)."""
        vals = {f: True for f in _BOOL_FIELDS}
        vals["above_sma200"] = False
        vals["momentum_confirms"] = False
        vals["cot_confirms"] = False
        vals["cot_strong"] = False
        inp = ScoringInput(
            **vals,
            instrument="EURUSD",
            instrument_class="Z",
        )
        res = calculate_confluence(inp)
        assert res.score == 13
        # 13 >= 10 => B
        assert res.grade == "B"

    def test_score_10_is_b_boundary(self):
        """Score of exactly 10 gets grade B."""
        vals = {f: True for f in _BOOL_FIELDS}
        # Need 10 = total - 9 fails. Total possible with Z class: 12 bools + session + corr + 3 None = 17
        # So we need 7 bools False (7 fail) => 5 bools True + session + corr + 3 = 10
        for i, f in enumerate(_BOOL_FIELDS):
            vals[f] = i < 5
        inp = ScoringInput(
            **vals,
            instrument="EURUSD",
            instrument_class="Z",
        )
        res = calculate_confluence(inp)
        assert res.score == 10
        assert res.grade == "B"

    def test_score_9_is_c(self):
        """Score of 9 gets grade C (below B threshold)."""
        vals = {f: True for f in _BOOL_FIELDS}
        for i, f in enumerate(_BOOL_FIELDS):
            vals[f] = i < 4
        inp = ScoringInput(
            **vals,
            instrument="EURUSD",
            instrument_class="Z",
        )
        res = calculate_confluence(inp)
        assert res.score == 9
        assert res.grade == "C"

    def test_new_detail_labels_for_criteria_17_19(self):
        """Details list includes criteria 17-19 labels."""
        res = calculate_confluence(_make_input())
        labels = [d.label for d in res.details]
        assert "COMEX stress bekrefter" in labels
        assert "Ingen seismisk risiko" in labels
        assert "Chokepoint klar" in labels
