"""The /map passthrough to BlueMap, against a stand-in BlueMap on a local port."""

import gzip
import http.server
import importlib
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

TILE = gzip.compress(b"tile bytes")


class FakeBlueMap(http.server.BaseHTTPRequestHandler):
    seen: list[tuple[str, str]] = []

    def do_GET(self):  # noqa: N802
        self.seen.append((self.path, self.headers.get("If-None-Match", "")))
        if self.path == "/":
            self._send(200, b"<html>map</html>", "text/html")
        elif self.path == "/maps/world/tiles/0/x1/z2.prbm":
            if self.headers.get("If-None-Match") == '"v1"':
                self.send_response(304)
                self.end_headers()
                return
            self._send(200, TILE, "application/octet-stream", {"Content-Encoding": "gzip", "ETag": '"v1"'})
        elif self.path.startswith("/maps/world/live/players.json"):
            self._send(200, b'{"players":[]}', "application/json")
        else:
            self._send(404, b"no", "text/plain")

    do_HEAD = do_GET  # noqa: N815

    def _send(self, code, body, kind, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command == "GET":
            self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def client():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeBlueMap)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["MAP_URL"] = f"http://127.0.0.1:{server.server_port}"
    import app as site

    importlib.reload(site)
    yield site.app.test_client()
    server.shutdown()


def test_bare_map_redirects_to_trailing_slash(client):
    r = client.get("/map")
    assert r.status_code == 301
    assert r.headers["Location"].endswith("/map/")


def test_index_is_passed_through_with_the_map_policy(client):
    r = client.get("/map/")
    assert r.status_code == 200
    assert r.data == b"<html>map</html>"
    assert "worker-src 'self' blob:" in r.headers["Content-Security-Policy"]


def test_compressed_tiles_pass_through_untouched(client):
    r = client.get("/map/maps/world/tiles/0/x1/z2.prbm")
    assert r.status_code == 200
    assert r.headers["Content-Encoding"] == "gzip"
    assert r.data == TILE  # still compressed: the browser unpacks it, not us
    assert r.headers["ETag"] == '"v1"'


def test_revalidation_returns_not_modified(client):
    r = client.get("/map/maps/world/tiles/0/x1/z2.prbm", headers={"If-None-Match": '"v1"'})
    assert r.status_code == 304


def test_query_strings_reach_bluemap(client):
    FakeBlueMap.seen.clear()
    r = client.get("/map/maps/world/live/players.json?1700000000")
    assert r.status_code == 200
    assert FakeBlueMap.seen[-1][0] == "/maps/world/live/players.json?1700000000"


def test_unknown_paths_keep_their_status(client):
    assert client.get("/map/nope").status_code == 404


def test_only_reads_are_allowed(client):
    assert client.post("/map/").status_code == 405


def test_bluemap_down_is_a_502(client, monkeypatch):
    import app as site

    monkeypatch.setattr(site, "MAP_URL", "http://127.0.0.1:9")
    assert client.get("/map/").status_code == 502


def test_rest_of_site_keeps_its_strict_policy(client):
    r = client.get("/map")  # a route outside the passthrough
    assert "worker-src" not in r.headers["Content-Security-Policy"]
