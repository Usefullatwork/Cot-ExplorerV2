"""Unit tests for src.analysis.scoring.calculate_confluence."""

from src.analysis.scoring import calculate_confluence
from src.core.models import ScoreDetail, ScoringInput, ScoringResult

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_input(**overrides) -> ScoringInput:
    """Create a ScoringInput with all fields False unless overridden."""
    defaults = {f: False for f in ScoringInput.model_fields}
    defaults.update(overrides)
    return ScoringInput(**defaults)


def _all_true() -> ScoringInput:
    return ScoringInput(**{f: True for f in ScoringInput.model_fields})


def _n_true(n: int, **forced) -> ScoringInput:
    """Turn on exactly *n* fields (arbitrary selection), plus any forced overrides.

    Forced fields are pinned and not overwritten by the fill loop.
    """
    fields = list(ScoringInput.model_fields.keys())
    vals = {f: False for f in fields}
    # apply forced first so they count towards n
    for k, v in forced.items():
        vals[k] = v
    already_true = sum(1 for v in vals.values() if v)
    for f in fields:
        if already_true >= n:
            break
        if f in forced:
            continue  # don't overwrite forced values
        if not vals[f]:
            vals[f] = True
            already_true += 1
    return ScoringInput(**vals)


# ===== Score / Grade boundary tests ========================================


class TestGradeBoundaries:
    """Grade logic: A+ (>=11), A (>=9), B (>=6), C (<6)."""

    def test_all_true_score_12(self):
        res = calculate_confluence(_all_true())
        assert res.score == 12
        assert res.grade == "A+"
        assert res.grade_color == "bull"

    def test_all_false_score_0(self):
        res = calculate_confluence(_make_input())
        assert res.score == 0
        assert res.grade == "C"
        assert res.grade_color == "bear"

    def test_11_true_is_a_plus(self):
        inp = _n_true(11)
        res = calculate_confluence(inp)
        assert res.score == 11
        assert res.grade == "A+"

    def test_10_true_is_a(self):
        inp = _n_true(10)
        res = calculate_confluence(inp)
        assert res.score == 10
        assert res.grade == "A"

    def test_9_true_is_a(self):
        inp = _n_true(9)
        res = calculate_confluence(inp)
        assert res.score == 9
        assert res.grade == "A"

    def test_8_true_is_b(self):
        inp = _n_true(8)
        res = calculate_confluence(inp)
        assert res.score == 8
        assert res.grade == "B"

    def test_6_true_is_b(self):
        inp = _n_true(6)
        res = calculate_confluence(inp)
        assert res.score == 6
        assert res.grade == "B"

    def test_5_true_is_c(self):
        inp = _n_true(5)
        res = calculate_confluence(inp)
        assert res.score == 5
        assert res.grade == "C"


# ===== max_score & details ==================================================


class TestMaxScoreAndDetails:
    def test_max_score_always_12_all_true(self):
        res = calculate_confluence(_all_true())
        assert res.max_score == 12

    def test_max_score_always_12_all_false(self):
        res = calculate_confluence(_make_input())
        assert res.max_score == 12

    def test_details_length_always_12(self):
        res = calculate_confluence(_all_true())
        assert len(res.details) == 12

    def test_details_length_12_all_false(self):
        res = calculate_confluence(_make_input())
        assert len(res.details) == 12

    def test_details_passes_reflect_all_true(self):
        res = calculate_confluence(_all_true())
        assert all(d.passes for d in res.details)

    def test_details_passes_reflect_all_false(self):
        res = calculate_confluence(_make_input())
        assert not any(d.passes for d in res.details)


# ===== Grade color mapping ==================================================


class TestGradeColor:
    """>=11 bull, 9-10 warn, <9 bear."""

    def test_color_bull_at_11(self):
        res = calculate_confluence(_n_true(11))
        assert res.grade_color == "bull"

    def test_color_bull_at_12(self):
        res = calculate_confluence(_all_true())
        assert res.grade_color == "bull"

    def test_color_warn_at_10(self):
        res = calculate_confluence(_n_true(10))
        assert res.grade_color == "warn"

    def test_color_warn_at_9(self):
        res = calculate_confluence(_n_true(9))
        assert res.grade_color == "warn"

    def test_color_bear_at_8(self):
        res = calculate_confluence(_n_true(8))
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
        """Without cot_confirms, should NOT be MAKRO even if score>=6 + htf."""
        inp = _n_true(6, cot_confirms=False, htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "MAKRO"

    def test_makro_requires_htf(self):
        """Without htf_level_nearby, should NOT be MAKRO."""
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
        inp = _make_input(above_sma200=True)  # score=1, no qualifiers
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "WATCHLIST"

    def test_makro_priority_over_swing(self):
        """When both MAKRO and SWING qualify, MAKRO wins."""
        inp = _n_true(6, cot_confirms=True, htf_level_nearby=True, at_level_now=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "MAKRO"


# ===== Edge case tests =====================================================


class TestScoreBoundaryTransitions:
    """Test exact boundary transitions: 5->6, 8->9, 10->11."""

    def test_boundary_5_to_6_grade_c_to_b(self):
        """Score 5 = C, score 6 = B — exact boundary."""
        res5 = calculate_confluence(_n_true(5))
        res6 = calculate_confluence(_n_true(6))
        assert res5.grade == "C"
        assert res6.grade == "B"

    def test_boundary_8_to_9_grade_b_to_a(self):
        """Score 8 = B, score 9 = A — exact boundary."""
        res8 = calculate_confluence(_n_true(8))
        res9 = calculate_confluence(_n_true(9))
        assert res8.grade == "B"
        assert res9.grade == "A"

    def test_boundary_10_to_11_grade_a_to_aplus(self):
        """Score 10 = A, score 11 = A+ — exact boundary."""
        res10 = calculate_confluence(_n_true(10))
        res11 = calculate_confluence(_n_true(11))
        assert res10.grade == "A"
        assert res11.grade == "A+"

    def test_boundary_8_to_9_color_bear_to_warn(self):
        """Score 8 = bear, score 9 = warn — color boundary."""
        res8 = calculate_confluence(_n_true(8))
        res9 = calculate_confluence(_n_true(9))
        assert res8.grade_color == "bear"
        assert res9.grade_color == "warn"

    def test_boundary_10_to_11_color_warn_to_bull(self):
        """Score 10 = warn, score 11 = bull — color boundary."""
        res10 = calculate_confluence(_n_true(10))
        res11 = calculate_confluence(_n_true(11))
        assert res10.grade_color == "warn"
        assert res11.grade_color == "bull"


class TestScoringEdgeCases:
    """Edge cases: single fields, return type, detail content."""

    def test_single_true_field_score_1(self):
        """Only one field True should yield score=1."""
        inp = _make_input(above_sma200=True)
        res = calculate_confluence(inp)
        assert res.score == 1

    def test_return_type_is_scoring_result(self):
        """Return type must always be ScoringResult."""
        res = calculate_confluence(_make_input())
        assert isinstance(res, ScoringResult)

    def test_details_labels_are_non_empty(self):
        """Every detail should have a non-empty label."""
        res = calculate_confluence(_all_true())
        for d in res.details:
            assert isinstance(d.label, str)
            assert len(d.label) > 0

    def test_details_are_score_detail_instances(self):
        """Each detail must be a ScoreDetail."""
        res = calculate_confluence(_make_input())
        for d in res.details:
            assert isinstance(d, ScoreDetail)

    def test_score_equals_sum_of_passing_details(self):
        """Score should always equal the count of passing details."""
        for n in range(0, 13):
            inp = _n_true(min(n, 12))
            res = calculate_confluence(inp)
            assert res.score == sum(1 for d in res.details if d.passes)


class TestTimeframeBiasEdgeCases:
    """Edge cases for timeframe bias thresholds."""

    def test_scalp_at_exact_threshold_score_2(self):
        """score=2 + at_level_now -> SCALP (exact minimum)."""
        inp = _n_true(2, at_level_now=True, htf_level_nearby=False, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "SCALP"

    def test_score_1_at_level_is_watchlist(self):
        """score=1 with at_level_now should be WATCHLIST (below SCALP threshold)."""
        inp = _make_input(at_level_now=True)
        res = calculate_confluence(inp)
        assert res.score == 1
        assert res.timeframe_bias == "WATCHLIST"

    def test_swing_at_exact_threshold_score_4(self):
        """score=4 + htf_level_nearby -> SWING (exact minimum)."""
        inp = _n_true(4, htf_level_nearby=True, cot_confirms=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "SWING"

    def test_score_3_htf_nearby_is_not_swing(self):
        """score=3 with htf_level_nearby should NOT be SWING."""
        inp = _n_true(3, htf_level_nearby=True, cot_confirms=False, at_level_now=False)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "SWING"

    def test_makro_at_exact_threshold_score_6(self):
        """score=6 + cot_confirms + htf -> MAKRO (exact minimum)."""
        inp = _n_true(6, cot_confirms=True, htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias == "MAKRO"

    def test_score_5_cot_htf_is_not_makro(self):
        """score=5 with cot+htf should NOT be MAKRO."""
        inp = _n_true(5, cot_confirms=True, htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.timeframe_bias != "MAKRO"


# ===== Edge case tests added by Agent D3 =====================================


class TestScoringInputVariations:
    """Edge cases: individual fields, idempotency, data integrity."""

    def test_each_individual_field_scores_exactly_1(self):
        """Turning on any single field should always produce score=1."""
        for field in ScoringInput.model_fields:
            inp = _make_input(**{field: True})
            res = calculate_confluence(inp)
            assert res.score == 1, f"Field {field} alone should score 1, got {res.score}"

    def test_all_false_grade_is_c_and_watchlist(self):
        """All False => score=0, grade C, WATCHLIST, bear."""
        res = calculate_confluence(_make_input())
        assert res.score == 0
        assert res.grade == "C"
        assert res.timeframe_bias == "WATCHLIST"
        assert res.grade_color == "bear"

    def test_idempotent_same_input(self):
        """Same input called twice should yield identical results."""
        inp = _n_true(7, cot_confirms=True, htf_level_nearby=True)
        res1 = calculate_confluence(inp)
        res2 = calculate_confluence(inp)
        assert res1.score == res2.score
        assert res1.grade == res2.grade
        assert res1.timeframe_bias == res2.timeframe_bias
        assert res1.grade_color == res2.grade_color

    def test_score_never_exceeds_12(self):
        """Even with all True, score cannot exceed 12 (total fields)."""
        res = calculate_confluence(_all_true())
        assert res.score <= 12

    def test_score_never_negative(self):
        """Score should never be negative."""
        res = calculate_confluence(_make_input())
        assert res.score >= 0

    def test_all_true_timeframe_is_makro(self):
        """All True means cot_confirms + htf_level_nearby + score>=6 => MAKRO."""
        res = calculate_confluence(_all_true())
        assert res.timeframe_bias == "MAKRO"

    def test_details_pass_count_matches_score(self):
        """For every possible score, passing detail count must equal score."""
        for n in range(13):
            inp = _n_true(min(n, 12))
            res = calculate_confluence(inp)
            passing = sum(1 for d in res.details if d.passes)
            assert passing == res.score

    def test_grade_monotonically_improves_with_score(self):
        """Higher scores should never produce a worse grade."""
        grade_rank = {"C": 0, "B": 1, "A": 2, "A+": 3}
        prev_rank = -1
        for n in range(13):
            res = calculate_confluence(_n_true(n))
            rank = grade_rank[res.grade]
            assert rank >= prev_rank, f"Grade degraded at score {n}: {res.grade}"
            prev_rank = rank

    def test_only_at_level_now_true_score_1_watchlist(self):
        """at_level_now=True alone => score=1, below SCALP threshold => WATCHLIST."""
        inp = _make_input(at_level_now=True)
        res = calculate_confluence(inp)
        assert res.score == 1
        assert res.timeframe_bias == "WATCHLIST"

    def test_only_htf_level_nearby_true_score_1_watchlist(self):
        """htf_level_nearby=True alone => score=1, below SWING threshold => WATCHLIST."""
        inp = _make_input(htf_level_nearby=True)
        res = calculate_confluence(inp)
        assert res.score == 1
        assert res.timeframe_bias == "WATCHLIST"
