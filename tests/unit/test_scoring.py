"""Unit tests for src.analysis.scoring — 16-point confluence system."""

from src.analysis.scoring import (
    _check_correlation_clear,
    _check_fvg,
    _check_order_block,
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


# ===== Grade boundary tests (updated for 16-point system) ==================


class TestGradeBoundaries:
    """Grade logic: A+ (>=14), A (>=12), B (>=8), C (<8)."""

    def test_all_true_score_16(self):
        res = calculate_confluence(_all_true())
        assert res.score == 16
        assert res.grade == "A+"
        assert res.grade_color == "bull"

    def test_all_false_bools_score_1(self):
        """All 12 bools False; corr_clear passes by default (empty instrument)."""
        res = calculate_confluence(_make_input())
        assert res.score == 1  # only corr_clear passes
        assert res.grade == "C"
        assert res.grade_color == "bear"

    def test_truly_zero_score(self):
        """Force all 16 checks to fail."""
        inp = ScoringInput(
            **{f: False for f in _BOOL_FIELDS},
            instrument_class="A", current_hour_cet=3,
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],
        )
        res = calculate_confluence(inp)
        assert res.score == 0
        assert res.grade == "C"
        assert res.grade_color == "bear"

    def test_14_true_is_a_plus(self):
        # 12 bool True + session (defaults True for unknown class) + corr (defaults True)
        # But we need exactly 14 — set 12 bools + ensure session+corr pass
        inp = _n_true(12, instrument_class="Z")  # unknown class = session True, no signals = corr True
        res = calculate_confluence(inp)
        assert res.score == 14
        assert res.grade == "A+"

    def test_13_true_is_a(self):
        # 12 bools + only 1 new factor (session pass via unknown class, but
        # corr also passes by default). Need 13 exactly: 11 bools + session + corr
        inp = _n_true(11, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 13
        assert res.grade == "A"

    def test_12_true_is_a(self):
        inp = _n_true(10, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 12
        assert res.grade == "A"

    def test_10_true_is_b(self):
        inp = _n_true(8, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 10
        assert res.grade == "B"

    def test_8_true_is_b(self):
        inp = _n_true(6, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 8
        assert res.grade == "B"

    def test_7_true_is_c(self):
        inp = _n_true(5, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 7
        assert res.grade == "C"


# ===== max_score & details ==================================================


class TestMaxScoreAndDetails:
    def test_max_score_always_16_all_true(self):
        res = calculate_confluence(_all_true())
        assert res.max_score == 16

    def test_max_score_always_16_all_false(self):
        res = calculate_confluence(_make_input())
        assert res.max_score == 16

    def test_details_length_always_16(self):
        res = calculate_confluence(_all_true())
        assert len(res.details) == 16

    def test_details_length_16_all_false(self):
        res = calculate_confluence(_make_input())
        assert len(res.details) == 16

    def test_details_passes_reflect_all_true(self):
        res = calculate_confluence(_all_true())
        assert all(d.passes for d in res.details)

    def test_details_passes_reflect_all_false(self):
        """All False bools + default new params → only corr passes (empty instrument)."""
        res = calculate_confluence(_make_input())
        # Defaults: atr=0 → OB+FVG fail, class="A" hour=12 (gap) → session fails,
        # instrument="" + empty signals → corr passes.
        passing = [d for d in res.details if d.passes]
        assert len(passing) == 1
        assert passing[0].label == "Ingen korrelert konflikt"

    def test_new_detail_labels_present(self):
        res = calculate_confluence(_all_true())
        labels = [d.label for d in res.details]
        assert "Ordre-blokk bekrefter" in labels
        assert "FVG i nærheten" in labels
        assert "Riktig handelssesjon" in labels
        assert "Ingen korrelert konflikt" in labels


# ===== Grade color mapping ==================================================


class TestGradeColor:
    """>=14 bull, 12-13 warn, <12 bear."""

    def test_color_bull_at_14(self):
        inp = _n_true(12, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 14
        assert res.grade_color == "bull"

    def test_color_bull_at_16(self):
        res = calculate_confluence(_all_true())
        assert res.grade_color == "bull"

    def test_color_warn_at_13(self):
        inp = _n_true(11, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 13
        assert res.grade_color == "warn"

    def test_color_warn_at_12(self):
        inp = _n_true(10, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 12
        assert res.grade_color == "warn"

    def test_color_bear_at_11(self):
        inp = _n_true(9, instrument_class="Z")
        res = calculate_confluence(inp)
        assert res.score == 11
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
    """Test exact boundary transitions: 7->8, 11->12, 13->14."""

    def test_boundary_7_to_8_grade_c_to_b(self):
        res7 = _n_true(5, instrument_class="Z")
        res8 = _n_true(6, instrument_class="Z")
        r7 = calculate_confluence(res7)
        r8 = calculate_confluence(res8)
        assert r7.grade == "C"
        assert r8.grade == "B"

    def test_boundary_11_to_12_grade_b_to_a(self):
        res11 = _n_true(9, instrument_class="Z")
        res12 = _n_true(10, instrument_class="Z")
        r11 = calculate_confluence(res11)
        r12 = calculate_confluence(res12)
        assert r11.grade == "B"
        assert r12.grade == "A"

    def test_boundary_13_to_14_grade_a_to_aplus(self):
        res13 = _n_true(11, instrument_class="Z")
        res14 = _n_true(12, instrument_class="Z")
        r13 = calculate_confluence(res13)
        r14 = calculate_confluence(res14)
        assert r13.grade == "A"
        assert r14.grade == "A+"

    def test_boundary_11_to_12_color_bear_to_warn(self):
        r11 = calculate_confluence(_n_true(9, instrument_class="Z"))
        r12 = calculate_confluence(_n_true(10, instrument_class="Z"))
        assert r11.grade_color == "bear"
        assert r12.grade_color == "warn"

    def test_boundary_13_to_14_color_warn_to_bull(self):
        r13 = calculate_confluence(_n_true(11, instrument_class="Z"))
        r14 = calculate_confluence(_n_true(12, instrument_class="Z"))
        assert r13.grade_color == "warn"
        assert r14.grade_color == "bull"


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
        inp = _make_input(at_level_now=True)
        res = calculate_confluence(inp)
        # score is 1 (from at_level_now) + potentially corr_clear default
        # at_level_now counts as bool, and corr_clear passes by default (empty instrument)
        # so total is 2. But at_level_now=True + score>=2 = SCALP.
        # We need exactly 1 total. Force session/corr to fail.
        inp2 = ScoringInput(
            above_sma200=False, momentum_confirms=False, cot_confirms=False,
            cot_strong=False, at_level_now=True, htf_level_nearby=False,
            trend_congruent=False, no_event_risk=False, news_confirms=False,
            fund_confirms=False, bos_confirms=False, smc_struct_confirms=False,
            instrument_class="A", current_hour_cet=3,  # session fails
            instrument="EURUSD",
            open_signals=[{"instrument": "GBPUSD", "direction": "short"}],  # corr fails
        )
        res2 = calculate_confluence(inp2)
        assert res2.score == 1
        assert res2.timeframe_bias == "WATCHLIST"

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

    def test_score_never_exceeds_16(self):
        res = calculate_confluence(_all_true())
        assert res.score <= 16

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
        # + corr passes (empty instrument) → at least 12
        assert res.score >= 12

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
        """Last 4 detail labels must be the new institutional factors."""
        res = calculate_confluence(_make_input())
        expected = [
            "Ordre-blokk bekrefter",
            "FVG i nærheten",
            "Riktig handelssesjon",
            "Ingen korrelert konflikt",
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
