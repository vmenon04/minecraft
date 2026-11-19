"""The site's pages and status, with the Minecraft pings and machine stats stubbed out."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import app as site  # noqa: E402

ONLINE = {"online": True, "latency_ms": 3, "version": "Paper 26.3", "players": 2,
          "max_players": 20, "motd": "Rocket Lockett"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(site, "ping", lambda host, port, timeout=2.0: ONLINE if port == 25567 else {"online": False})
    monkeypatch.setattr(site, "machine_stats", lambda: {"load": [0.1, 0.2, 0.3]})
    monkeypatch.setitem(site._cache, "data", None)
    return site.app.test_client()


def test_status_lists_every_server(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.get_json()
    by_id = {s["id"]: s for s in body["servers"]}
    assert by_id["rocket_lockett"]["online"] is True
    assert by_id["rocket_lockett"]["players"] == 2
    assert by_id["bsm"]["online"] is False


def test_status_never_publishes_addresses(client):
    for server in client.get("/api/status").get_json()["servers"]:
        assert "host" not in server and "port" not in server


def test_status_is_cached_for_the_stated_time(client):
    r = client.get("/api/status")
    assert r.headers["Cache-Control"] == f"public, max-age={site.CACHE_SECONDS}"


def test_home_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Rocket Lockett" in r.data


def test_pages_carry_the_strict_policy(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert client.get("/").headers["X-Content-Type-Options"] == "nosniff"


def test_map_is_not_served_here(client):
    # homelab's nginx sends /map/ to BlueMap; this site has no route for it.
    assert client.get("/map/").status_code == 404
