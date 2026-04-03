"""Tests for src.data.quality -- pure data validation functions."""

from __future__ import annotations

import pytest

from src.data.quality import (
    QualityIssue,
    QualityReport,
    compute_aggregate_quality,
    validate_cot_data,
    validate_macro_data,
    validate_price_data,
)


# ---------------------------------------------------------------------------
# QualityReport.quality_score
# ---------------------------------------------------------------------------


def test_quality_score_zero_records_returns_zero() -> None:
    report = QualityReport(source="cot", total_records=0)
    assert report.quality_score == 0.0


def test_quality_score_no_issues_returns_one() -> None:
    report = QualityReport(source="cot", total_records=10)
    assert report.quality_score == 1.0


def test_quality_score_errors_deduct_point_one() -> None:
    report = QualityReport(
        source="cot",
        total_records=10,
        issues=[
            QualityIssue(severity="error", field="x", message="bad"),
            QualityIssue(severity="error", field="y", message="bad"),
        ],
    )
    assert report.quality_score == pytest.approx(0.8)


def test_quality_score_warnings_deduct_point_zero_two() -> None:
    report = QualityReport(
        source="cot",
        total_records=10,
        issues=[
            QualityIssue(severity="warning", field="x", message="meh"),
        ],
    )
    assert report.quality_score == pytest.approx(0.98)


def test_quality_score_capped_at_zero() -> None:
    report = QualityReport(
        source="cot",
        total_records=5,
        issues=[
            QualityIssue(severity="error", field="x", message="bad")
            for _ in range(15)
        ],
    )
    assert report.quality_score == 0.0


def test_quality_score_mixed_issues() -> None:
    report = QualityReport(
        source="prices",
        total_records=100,
        issues=[
            QualityIssue(severity="error", field="a", message="e1"),
            QualityIssue(severity="error", field="b", message="e2"),
            QualityIssue(severity="warning", field="c", message="w1"),
            QualityIssue(severity="warning", field="d", message="w2"),
            QualityIssue(severity="info", field="e", message="i1"),
        ],
    )
    # 2 errors * 0.1 + 2 warnings * 0.02 = 0.24 penalty
    assert report.quality_score == pytest.approx(0.76)


# ---------------------------------------------------------------------------
# validate_cot_data
# ---------------------------------------------------------------------------


def _make_cot_record(**overrides: object) -> dict:
    base = {
        "symbol": "GC",
        "date": "2024-03-15",
        "open_interest": 500000,
        "spec_long": 200000,
        "spec_short": 150000,
        "spec_net": 50000,
        "comm_long": 180000,
        "comm_short": 200000,
        "comm_net": -20000,
        "nonrept_long": 120000,
        "nonrept_short": 150000,
        "nonrept_net": -30000,
    }
    base.update(overrides)
    return base


def test_cot_valid_records_no_issues() -> None:
    records = [_make_cot_record()]
    report = validate_cot_data(records)
    assert report.error_count == 0
    assert report.warning_count == 0
    assert report.quality_score == 1.0


def test_cot_empty_records() -> None:
    report = validate_cot_data([])
    assert report.total_records == 0
    assert report.quality_score == 0.0


def test_cot_flags_missing_required_field() -> None:
    rec = _make_cot_record()
    del rec["symbol"]
    report = validate_cot_data([rec])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Missing required field: symbol" in e.message for e in errors)


def test_cot_flags_zero_open_interest() -> None:
    report = validate_cot_data([_make_cot_record(open_interest=0)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Invalid open_interest" in e.message for e in errors)


def test_cot_flags_negative_open_interest() -> None:
    report = validate_cot_data([_make_cot_record(open_interest=-100)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Invalid open_interest" in e.message for e in errors)


def test_cot_flags_negative_spec_long() -> None:
    report = validate_cot_data([_make_cot_record(spec_long=-5000)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Negative position: spec_long" in e.message for e in errors)


def test_cot_flags_negative_spec_short() -> None:
    report = validate_cot_data([_make_cot_record(spec_short=-1)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Negative position: spec_short" in e.message for e in errors)


def test_cot_flags_net_exceeds_oi() -> None:
    report = validate_cot_data([_make_cot_record(
        open_interest=100000,
        spec_net=150000,
    )])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("spec_net" in e.message and "open_interest" in e.message for e in errors)


def test_cot_flags_bad_date_format() -> None:
    report = validate_cot_data([_make_cot_record(date="15-03-2024")])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Bad date format" in e.message for e in errors)


def test_cot_flags_composition_mismatch() -> None:
    # spec_long + comm_long + nonrept_long = 10+10+10 = 30, OI=100 -> 70% deviation
    report = validate_cot_data([_make_cot_record(
        open_interest=100,
        spec_long=10,
        comm_long=10,
        nonrept_long=10,
        spec_net=5,
    )])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("composition" in w.field for w in warnings)


def test_cot_flags_duplicates() -> None:
    rec = _make_cot_record()
    report = validate_cot_data([rec, rec.copy()])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("Duplicate" in w.message for w in warnings)


def test_cot_flags_date_gap() -> None:
    records = [
        _make_cot_record(date="2024-01-05"),
        _make_cot_record(date="2024-01-26"),  # 21 day gap
    ]
    report = validate_cot_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("Date gap" in w.message for w in warnings)


def test_cot_no_gap_within_14_days() -> None:
    records = [
        _make_cot_record(date="2024-01-05"),
        _make_cot_record(date="2024-01-12"),  # 7 day gap (normal weekly)
    ]
    report = validate_cot_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert not any("Date gap" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# validate_price_data
# ---------------------------------------------------------------------------


def _make_price_record(**overrides: object) -> dict:
    base = {
        "instrument": "EURUSD",
        "date": "2024-03-15",
        "open": 1.0850,
        "high": 1.0900,
        "low": 1.0800,
        "close": 1.0870,
        "volume": 50000,
    }
    base.update(overrides)
    return base


def test_prices_valid_records_no_issues() -> None:
    records = [_make_price_record()]
    report = validate_price_data(records)
    assert report.error_count == 0
    assert report.warning_count == 0


def test_prices_empty_records() -> None:
    report = validate_price_data([])
    assert report.total_records == 0
    assert report.quality_score == 0.0


def test_prices_flags_missing_close() -> None:
    rec = _make_price_record()
    del rec["close"]
    report = validate_price_data([rec])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Missing required field: close" in e.message for e in errors)


def test_prices_flags_zero_close() -> None:
    report = validate_price_data([_make_price_record(close=0)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Invalid close price" in e.message for e in errors)


def test_prices_flags_negative_close() -> None:
    report = validate_price_data([_make_price_record(close=-5.0)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Invalid close price" in e.message for e in errors)


def test_prices_flags_high_less_than_low() -> None:
    report = validate_price_data([_make_price_record(high=1.08, low=1.09)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("high" in e.message and "low" in e.message for e in errors)


def test_prices_flags_open_above_high() -> None:
    report = validate_price_data([_make_price_record(open=1.10, high=1.09)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("open" in e.message and "high" in e.message for e in errors)


def test_prices_flags_open_below_low() -> None:
    report = validate_price_data([_make_price_record(open=1.07, low=1.08)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("open" in e.message and "low" in e.message for e in errors)


def test_prices_flags_close_above_high() -> None:
    report = validate_price_data([_make_price_record(close=1.10, high=1.09)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("close" in e.message and "high" in e.message for e in errors)


def test_prices_flags_close_below_low() -> None:
    report = validate_price_data([_make_price_record(close=1.07, low=1.08)])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("close" in e.message and "low" in e.message for e in errors)


def test_prices_flags_duplicates() -> None:
    rec = _make_price_record()
    report = validate_price_data([rec, rec.copy()])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("Duplicate" in w.message for w in warnings)


def test_prices_flags_spike() -> None:
    """A massive jump in close price should trigger a spike warning.

    Use 20 stable data points so the std stays small, then a 3x spike
    clearly exceeds the 3-std threshold (z-score ~4.36).
    """
    records = [
        _make_price_record(
            date=f"2024-{1 + d // 28:02d}-{1 + d % 28:02d}",
            open=100,
            high=101,
            low=99,
            close=100.0 + (d % 2) * 0.1,  # alternates 100.0 / 100.1
        )
        for d in range(20)
    ]
    # Add a 3x spike to clearly exceed 3-std threshold
    records.append(
        _make_price_record(
            date="2024-01-22",
            open=290,
            high=310,
            low=285,
            close=300,
        )
    )
    report = validate_price_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("spike" in w.message.lower() for w in warnings)


def test_prices_ignores_weekend_gaps() -> None:
    """Fri to Mon is 3 calendar days -- should NOT trigger gap warning."""
    records = [
        _make_price_record(date="2024-03-15"),  # Friday
        _make_price_record(date="2024-03-18"),  # Monday (3-day gap)
    ]
    report = validate_price_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert not any("Date gap" in w.message for w in warnings)


def test_prices_flags_large_gap() -> None:
    """A gap of 8 calendar days should trigger a warning."""
    records = [
        _make_price_record(date="2024-03-01"),
        _make_price_record(date="2024-03-10"),  # 9-day gap
    ]
    report = validate_price_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("Date gap" in w.message for w in warnings)


def test_prices_flags_stale_quotes() -> None:
    """Same close for 5+ consecutive days triggers stale warning."""
    records = [
        _make_price_record(
            date=f"2024-03-{d:02d}",
            open=100,
            high=101,
            low=99,
            close=100.0,
        )
        for d in range(1, 8)  # 7 days same close
    ]
    report = validate_price_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("Stale" in w.message or "stale" in w.message for w in warnings)


def test_prices_no_stale_warning_for_varying_close() -> None:
    records = [
        _make_price_record(
            date=f"2024-03-{d:02d}",
            open=100 + d,
            high=102 + d,
            low=99 + d,
            close=100.0 + d,
        )
        for d in range(1, 8)
    ]
    report = validate_price_data(records)
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert not any("Stale" in w.message or "stale" in w.message for w in warnings)


def test_prices_single_record_no_gap_check() -> None:
    """Single record should not trigger any gap or spike warnings."""
    report = validate_price_data([_make_price_record()])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert not any("gap" in w.message.lower() for w in warnings)
    assert not any("spike" in w.message.lower() for w in warnings)


# ---------------------------------------------------------------------------
# validate_macro_data
# ---------------------------------------------------------------------------


def _make_macro_record(**overrides: object) -> dict:
    base = {
        "indicator": "VIX",
        "date": "2024-03-15",
        "value": 18.5,
    }
    base.update(overrides)
    return base


def test_macro_valid_records_no_issues() -> None:
    records = [_make_macro_record(indicator="VIX", value=18.5)]
    report = validate_macro_data(records)
    assert report.error_count == 0
    assert report.warning_count == 0


def test_macro_empty_records() -> None:
    report = validate_macro_data([])
    assert report.total_records == 0
    assert report.quality_score == 0.0


def test_macro_flags_missing_required_field() -> None:
    rec = _make_macro_record()
    del rec["value"]
    report = validate_macro_data([rec])
    errors = [i for i in report.issues if i.severity == "error"]
    assert any("Missing required field: value" in e.message for e in errors)


def test_macro_flags_extreme_vix() -> None:
    report = validate_macro_data([_make_macro_record(indicator="VIX", value=120)])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("VIX" in w.message for w in warnings)


def test_macro_flags_low_vix() -> None:
    report = validate_macro_data([_make_macro_record(indicator="VIX", value=3)])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("VIX" in w.message for w in warnings)


def test_macro_normal_vix_no_warning() -> None:
    report = validate_macro_data([_make_macro_record(indicator="VIX", value=22)])
    assert report.warning_count == 0


def test_macro_flags_extreme_dxy() -> None:
    report = validate_macro_data([_make_macro_record(indicator="DXY", value=140)])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("DXY" in w.message for w in warnings)


def test_macro_flags_low_dxy() -> None:
    report = validate_macro_data([_make_macro_record(indicator="DXY", value=60)])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("DXY" in w.message for w in warnings)


def test_macro_flags_negative_rate() -> None:
    report = validate_macro_data([_make_macro_record(indicator="FED_RATE", value=-1)])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("interest rate" in w.message.lower() for w in warnings)


def test_macro_flags_extreme_rate() -> None:
    report = validate_macro_data([_make_macro_record(indicator="YIELD_10Y", value=35)])
    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("interest rate" in w.message.lower() for w in warnings)


def test_macro_normal_rate_no_warning() -> None:
    report = validate_macro_data([_make_macro_record(indicator="FED_RATE", value=5.25)])
    assert report.warning_count == 0


# ---------------------------------------------------------------------------
# compute_aggregate_quality
# ---------------------------------------------------------------------------


def test_aggregate_all_clean_returns_one() -> None:
    reports = [
        QualityReport(source="cot", total_records=100),
        QualityReport(source="prices", total_records=200),
        QualityReport(source="fundamentals", total_records=50),
    ]
    assert compute_aggregate_quality(reports) == 1.0


def test_aggregate_empty_reports_returns_zero() -> None:
    assert compute_aggregate_quality([]) == 0.0


def test_aggregate_degraded_source_caps_at_point_seven() -> None:
    """If any report has quality_score < 0.5, cap at 0.7."""
    reports = [
        QualityReport(source="cot", total_records=100),  # 1.0
        QualityReport(source="prices", total_records=200),  # 1.0
        QualityReport(
            source="fundamentals",
            total_records=50,
            issues=[
                QualityIssue(severity="error", field="x", message="e")
                for _ in range(10)
            ],
        ),  # quality_score = 0.0 -> degraded
    ]
    result = compute_aggregate_quality(reports)
    assert result <= 0.7


def test_aggregate_weights_cot_and_prices_equally() -> None:
    """COT and prices both get 0.4 weight, fundamentals 0.2."""
    reports = [
        QualityReport(
            source="cot",
            total_records=10,
            issues=[QualityIssue(severity="error", field="x", message="e")],
        ),  # 0.9
        QualityReport(source="prices", total_records=10),  # 1.0
        QualityReport(source="fundamentals", total_records=10),  # 1.0
    ]
    # weighted: 0.4*0.9 + 0.4*1.0 + 0.2*1.0 = 0.36 + 0.40 + 0.20 = 0.96
    result = compute_aggregate_quality(reports)
    assert result == pytest.approx(0.96)


def test_aggregate_unknown_source_gets_small_weight() -> None:
    reports = [
        QualityReport(source="unknown", total_records=10),
    ]
    result = compute_aggregate_quality(reports)
    assert result == 1.0  # clean, just with weight 0.1
