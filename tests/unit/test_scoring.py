"""Unit tests for src.analysis.scoring.calculate_confluence."""

import pytest

from src.analysis.scoring import calculate_confluence
from src.core.models import ScoringInput, ScoringResult, ScoreDetail


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
