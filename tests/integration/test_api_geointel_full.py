"""Integration tests for geointel endpoints: seismic, comex, intel, chokepoints, regime."""

from __future__ import annotations


async def test_seismic_returns_200(app_client):
    """GET /api/v1/geointel/seismic returns 200 with a list."""
    r = await app_client.get("/api/v1/geointel/seismic")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    await app_client.aclose()


async def test_seismic_empty_db(app_client):
    """Seismic returns empty list when DB has no events (no live fetch)."""
    r = await app_client.get("/api/v1/geointel/seismic")
    body = r.json()
    assert body == []
    await app_client.aclose()


async def test_comex_returns_200(app_client):
    """GET /api/v1/geointel/comex returns 200 with expected keys."""
    r = await app_client.get("/api/v1/geointel/comex")
    assert r.status_code == 200
    body = r.json()
    assert "gold" in body
    assert "silver" in body
    assert "copper" in body
    assert "stress_index" in body
    await app_client.aclose()


async def test_comex_empty_db_defaults(app_client):
    """COMEX returns null metals and zero stress when DB is empty."""
    r = await app_client.get("/api/v1/geointel/comex")
    body = r.json()
    assert body["gold"] is None
    assert body["silver"] is None
    assert body["copper"] is None
    assert body["stress_index"] == 0.0
    await app_client.aclose()


async def test_intel_returns_200(app_client):
    """GET /api/v1/geointel/intel returns 200 with a list."""
    r = await app_client.get("/api/v1/geointel/intel")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    await app_client.aclose()


async def test_intel_empty_db(app_client):
    """Intel returns empty list when DB has no articles."""
    r = await app_client.get("/api/v1/geointel/intel")
    body = r.json()
    assert body == []
    await app_client.aclose()


async def test_intel_category_filter(app_client):
    """Intel category filter returns list (empty when no matching articles)."""
    r = await app_client.get("/api/v1/geointel/intel?category=gold")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    await app_client.aclose()


async def test_chokepoints_returns_200(app_client):
    """GET /api/v1/geointel/chokepoints returns 200 with list of chokepoints."""
    r = await app_client.get("/api/v1/geointel/chokepoints")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 6
    await app_client.aclose()


async def test_chokepoints_shape(app_client):
    """Each chokepoint has name, lat, lon, throughput, cargo_types, affected_instruments, risk_level."""
    r = await app_client.get("/api/v1/geointel/chokepoints")
    body = r.json()
    required = {"name", "lat", "lon", "throughput", "cargo_types", "affected_instruments", "risk_level"}
    for cp in body:
        missing = required - set(cp.keys())
        assert not missing, f"{cp.get('name', '?')} missing keys: {missing}"
    await app_client.aclose()


async def test_chokepoints_no_keywords_exposed(app_client):
    """Chokepoints should not expose the internal keywords field."""
    r = await app_client.get("/api/v1/geointel/chokepoints")
    body = r.json()
    for cp in body:
        assert "keywords" not in cp, f"{cp['name']} should not expose keywords"
    await app_client.aclose()


async def test_regime_returns_200(app_client):
    """GET /api/v1/geointel/regime returns 200 with regime data."""
    r = await app_client.get("/api/v1/geointel/regime")
    assert r.status_code == 200
    body = r.json()
    assert "regime" in body
    assert "adjustments" in body
    assert "safe_havens" in body
    assert "risk_assets" in body
    assert "energy_instruments" in body
    assert "safe_haven_only" in body
    await app_client.aclose()


async def test_regime_default_is_normal(app_client):
    """Default regime with no params should be NORMAL."""
    r = await app_client.get("/api/v1/geointel/regime")
    body = r.json()
    assert body["regime"] == "normal"
    assert body["safe_haven_only"] is False
    await app_client.aclose()


async def test_regime_with_high_vix(app_client):
    """High VIX should shift regime away from NORMAL."""
    r = await app_client.get("/api/v1/geointel/regime?vix_price=45&vix_5d_change=50")
    assert r.status_code == 200
    body = r.json()
    assert body["regime"] != "NORMAL"
    await app_client.aclose()


async def test_regime_lists_are_sorted(app_client):
    """safe_havens, risk_assets, energy_instruments should be sorted."""
    r = await app_client.get("/api/v1/geointel/regime")
    body = r.json()
    assert body["safe_havens"] == sorted(body["safe_havens"])
    assert body["risk_assets"] == sorted(body["risk_assets"])
    assert body["energy_instruments"] == sorted(body["energy_instruments"])
    await app_client.aclose()
