"""Tests for agriculture weather scoring pure functions."""

from __future__ import annotations

import pytest

from src.trading.scrapers.agri_weather import (
    combine_agri_outlook,
    compute_season_multiplier,
    score_cot,
    score_weather,
)


# ── score_weather ────────────────────────────────────────────────────────────


def test_drought_extreme():
    ws = score_weather(precip_7d=1.5, temp_max_avg=33.0, temp_min_avg=20.0,
                       crop="corn", lat=41.5, month=7)
    assert ws.raw_score == 3
    assert ws.outlook == "tørke"


def test_drought_moderate():
    ws = score_weather(precip_7d=5.0, temp_max_avg=27.0, temp_min_avg=15.0,
                       crop="wheat", lat=39.0, month=6)
    assert ws.raw_score == 2
    assert ws.outlook == "tørt"


def test_flood_extreme():
    ws = score_weather(precip_7d=150.0, temp_max_avg=25.0, temp_min_avg=18.0,
                       crop="rice", lat=30.7, month=7)
    assert ws.raw_score == 3
    assert ws.outlook == "flom"


def test_normal_weather():
    ws = score_weather(precip_7d=20.0, temp_max_avg=22.0, temp_min_avg=12.0,
                       crop="wheat", lat=51.0, month=8)
    assert ws.raw_score == 0
    assert ws.outlook == "normalt"


def test_frost_risk():
    ws = score_weather(precip_7d=10.0, temp_max_avg=5.0, temp_min_avg=-5.0,
                       crop="wheat", lat=51.0, month=4)
    assert ws.raw_score == 2
    assert ws.outlook == "frost"


def test_frost_ignored_southern():
    ws = score_weather(precip_7d=10.0, temp_max_avg=5.0, temp_min_avg=-5.0,
                       crop="wheat", lat=-33.0, month=4)
    assert ws.outlook == "normalt"


# ── compute_season_multiplier ────────────────────────────────────────────────


def test_critical_month_nh():
    assert compute_season_multiplier("corn", 41.5, 6) == 1.5


def test_non_critical_month_nh():
    assert compute_season_multiplier("corn", 41.5, 12) == 1.0


def test_critical_month_sh():
    # Southern hemisphere shifts months by 6
    assert compute_season_multiplier("corn", -34.5, 12) == 1.5


# ── score_cot ────────────────────────────────────────────────────────────────


def test_cot_strong_long():
    assert score_cot(20.0) == 2


def test_cot_mild_long():
    assert score_cot(8.0) == 1


def test_cot_neutral():
    assert score_cot(0.0) == 0


def test_cot_mild_short():
    assert score_cot(-10.0) == -1


def test_cot_strong_short():
    assert score_cot(-20.0) == -2


# ── combine_agri_outlook ─────────────────────────────────────────────────────


def test_combine_sterkt_bullish():
    signal, color, total = combine_agri_outlook(3, 1)
    assert signal == "STERKT BULLISH"
    assert color == "bull"


def test_combine_bullish():
    signal, color, total = combine_agri_outlook(1, 0)
    assert signal == "BULLISH"
    assert color == "bull"


def test_combine_neutral():
    signal, color, total = combine_agri_outlook(0, 0)
    assert signal == "NØYTRAL"
    assert color == "neutral"


def test_combine_bearish():
    signal, color, total = combine_agri_outlook(-1, 0)
    assert signal == "BEARISH"
    assert color == "bear"


def test_combine_sterkt_bearish():
    signal, color, total = combine_agri_outlook(-2, -2)
    assert signal == "STERKT BEARISH"
    assert color == "bear"
