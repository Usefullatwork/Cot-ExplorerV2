"""Integration tests for /api/v1/cot endpoints."""

from __future__ import annotations

import json

from src.db import repository as repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_LATEST = [
    {
        "date": "2026-03-17",
        "symbol": "GOLD",
        "market": "Gold Futures",
        "navn_no": "Gull",
        "report": "tff",
        "report_type": "tff",
        "change_spec_net": 5000,
        "spekulanter": {"long": 200000, "short": 100000},
    },
    {
        "date": "2026-03-17",
        "symbol": "EUROFX",
        "market": "Euro FX",
        "navn_no": "Euro",
        "report": "tff",
        "report_type": "tff",
        "change_spec_net": -3000,
        "spekulanter": {"long": 50000, "short": 150000},
    },
]


# ---------------------------------------------------------------------------
# /cot — reads from combined/latest.json
# ---------------------------------------------------------------------------


async def test_cot_latest_no_file(app_client, tmp_path, monkeypatch):
    """GET /api/v1/cot returns [] when combined file does not exist."""
    from src.api.routes import cot as cot_mod

    monkeypatch.setattr(cot_mod, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(cot_mod, "_ts_cache", None)
    r = await app_client.get("/api/v1/cot")
    assert r.status_code == 200
    assert r.json() == []
    await app_client.aclose()


async def test_cot_latest_with_file(app_client, tmp_path, monkeypatch):
    """GET /api/v1/cot returns data from combined/latest.json."""
    from src.api.routes import cot as cot_mod

    combined_dir = tmp_path / "combined"
    combined_dir.mkdir()
    (combined_dir / "latest.json").write_text(json.dumps(_SAMPLE_LATEST))
    monkeypatch.setattr(cot_mod, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(cot_mod, "_ts_cache", None)

    r = await app_client.get("/api/v1/cot")
    data = r.json()
    assert len(data) == 2
    assert data[0]["symbol"] == "GOLD"
    await app_client.aclose()


async def test_cot_latest_with_sparklines(app_client, tmp_path, monkeypatch):
    """GET /api/v1/cot injects cot_history from timeseries data."""
    from src.api.routes import cot as cot_mod

    # Set up combined/latest.json
    combined_dir = tmp_path / "combined"
    combined_dir.mkdir()
    (combined_dir / "latest.json").write_text(json.dumps(_SAMPLE_LATEST))

    # Set up timeseries file for GOLD
    ts_dir = tmp_path / "timeseries"
    ts_dir.mkdir()
    ts_data = {
        "symbol": "GOLD",
        "report": "tff",
        "data": [{"spec_net": i * 1000} for i in range(25)],
    }
    (ts_dir / "gold_tff.json").write_text(json.dumps(ts_data))

    monkeypatch.setattr(cot_mod, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(cot_mod, "_ts_cache", None)

    r = await app_client.get("/api/v1/cot")
    data = r.json()

    # GOLD should have cot_history (last 20 values)
    gold = next(d for d in data if d["symbol"] == "GOLD")
    assert "cot_history" in gold
    assert len(gold["cot_history"]) == 20
    assert gold["cot_history"][-1] == 24000

    # EUROFX has no timeseries → no cot_history key
    euro = next(d for d in data if d["symbol"] == "EUROFX")
    assert "cot_history" not in euro
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /cot/{symbol}/history — reads from DB
# ---------------------------------------------------------------------------


async def test_cot_history_not_found(app_client):
    """GET /api/v1/cot/NOPE/history returns 404 when no data."""
    r = await app_client.get("/api/v1/cot/NOPE/history")
    assert r.status_code == 404
    await app_client.aclose()


async def test_cot_history_with_data(app_client, db_session):
    """GET /api/v1/cot/{symbol}/history returns rows from DB."""
    repo.save_cot_position(
        {
            "symbol": "GOLD",
            "market": "Gold Futures",
            "report_type": "tff",
            "date": "2026-03-20",
            "open_interest": 500000,
            "change_oi": 1000,
            "spec_long": 200000,
            "spec_short": 100000,
            "spec_net": 100000,
            "comm_long": 150000,
            "comm_short": 200000,
            "comm_net": -50000,
            "nonrept_long": 50000,
            "nonrept_short": 50000,
            "nonrept_net": 0,
            "change_spec_net": 5000,
            "category": "metals",
        },
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/api/v1/cot/GOLD/history")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "GOLD"
    assert data[0]["spec_net"] == 100000
    assert data[0]["date"] == "2026-03-20"
    await app_client.aclose()


async def test_cot_history_filter_report_type(app_client, db_session):
    """Filter cot history by report_type."""
    for rt in ("tff", "legacy"):
        repo.save_cot_position(
            {
                "symbol": "GOLD",
                "market": "Gold Futures",
                "report_type": rt,
                "date": "2026-03-20",
                "open_interest": 500000,
                "change_oi": 0,
                "spec_long": 0,
                "spec_short": 0,
                "spec_net": 0,
                "comm_long": 0,
                "comm_short": 0,
                "comm_net": 0,
                "nonrept_long": 0,
                "nonrept_short": 0,
                "nonrept_net": 0,
                "change_spec_net": 0,
            },
            db=db_session,
        )
    db_session.commit()

    r = await app_client.get("/api/v1/cot/GOLD/history", params={"report_type": "tff"})
    data = r.json()
    assert len(data) == 1
    assert data[0]["report_type"] == "tff"
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /cot/summary — reads from combined/latest.json
# ---------------------------------------------------------------------------


async def test_cot_summary_no_file(app_client, tmp_path, monkeypatch):
    """GET /api/v1/cot/summary returns empty movers/extremes when no file."""
    from src.api.routes import cot as cot_mod

    monkeypatch.setattr(cot_mod, "_DATA_DIR", tmp_path)
    r = await app_client.get("/api/v1/cot/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["top_movers"] == []
    assert body["extremes"] == []
    await app_client.aclose()


async def test_cot_summary_with_file(app_client, tmp_path, monkeypatch):
    """GET /api/v1/cot/summary computes movers and extremes from file."""
    from src.api.routes import cot as cot_mod

    combined_dir = tmp_path / "combined"
    combined_dir.mkdir()
    (combined_dir / "latest.json").write_text(json.dumps(_SAMPLE_LATEST))
    monkeypatch.setattr(cot_mod, "_DATA_DIR", tmp_path)

    r = await app_client.get("/api/v1/cot/summary")
    body = r.json()
    assert len(body["top_movers"]) == 2
    assert len(body["extremes"]) == 2
    # GOLD has larger |change_spec_net| so should be first mover
    assert body["top_movers"][0]["symbol"] == "GOLD"
    await app_client.aclose()


async def test_cot_history_response_shape(app_client, db_session):
    """Verify all expected keys in cot history row."""
    repo.save_cot_position(
        {
            "symbol": "EUROFX",
            "market": "Euro FX",
            "report_type": "tff",
            "date": "2026-03-20",
            "open_interest": 100,
            "change_oi": 10,
            "spec_long": 50,
            "spec_short": 30,
            "spec_net": 20,
            "comm_long": 40,
            "comm_short": 60,
            "comm_net": -20,
            "nonrept_long": 10,
            "nonrept_short": 10,
            "nonrept_net": 0,
            "change_spec_net": 5,
            "category": "forex",
        },
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/api/v1/cot/EUROFX/history")
    row = r.json()[0]
    expected_keys = {
        "date",
        "symbol",
        "market",
        "report_type",
        "open_interest",
        "change_oi",
        "spec_long",
        "spec_short",
        "spec_net",
        "comm_long",
        "comm_short",
        "comm_net",
        "nonrept_long",
        "nonrept_short",
        "nonrept_net",
        "change_spec_net",
        "category",
    }
    assert expected_keys == set(row.keys())
    await app_client.aclose()
