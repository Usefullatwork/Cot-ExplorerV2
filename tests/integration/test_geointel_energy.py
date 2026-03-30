"""Integration tests for energy infrastructure geointel endpoints."""

from __future__ import annotations


async def test_energy_infra_returns_200(app_client):
    """GET /api/v1/geointel/energy-infra returns 200 with expected keys."""
    r = await app_client.get("/api/v1/geointel/energy-infra")
    assert r.status_code == 200
    body = r.json()
    assert "pipelines" in body
    assert "lng_terminals" in body
    assert "shipping_lanes" in body
    assert len(body["pipelines"]) == 8
    assert len(body["lng_terminals"]) == 6
    assert len(body["shipping_lanes"]) == 4
    await app_client.aclose()


async def test_energy_infra_pipeline_shape(app_client):
    """Each pipeline in the response has name, type, color, coords."""
    r = await app_client.get("/api/v1/geointel/energy-infra")
    body = r.json()
    for pipe in body["pipelines"]:
        assert "name" in pipe
        assert "type" in pipe
        assert "color" in pipe
        assert "coords" in pipe
        assert isinstance(pipe["coords"], list)
    await app_client.aclose()


async def test_energy_infra_lng_shape(app_client):
    """Each LNG terminal has name, lat, lon, type, country."""
    r = await app_client.get("/api/v1/geointel/energy-infra")
    body = r.json()
    for term in body["lng_terminals"]:
        assert "name" in term
        assert "lat" in term
        assert "lon" in term
        assert "type" in term
        assert "country" in term
    await app_client.aclose()


async def test_mine_locations_returns_200(app_client):
    """GET /api/v1/geointel/mine-locations returns 200 with 25 mines."""
    r = await app_client.get("/api/v1/geointel/mine-locations")
    assert r.status_code == 200
    body = r.json()
    assert "mines" in body
    assert len(body["mines"]) == 25
    await app_client.aclose()


async def test_mine_locations_entry_shape(app_client):
    """Each mine entry has name, lat, lon, type, commodity, country, production."""
    r = await app_client.get("/api/v1/geointel/mine-locations")
    body = r.json()
    required = {"name", "lat", "lon", "type", "commodity", "country", "production"}
    for mine in body["mines"]:
        missing = required - set(mine.keys())
        assert not missing, f"{mine.get('name', '?')} missing keys: {missing}"
    await app_client.aclose()
