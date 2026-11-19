"""mc.vasumenon.com: about flatboy + live Minecraft server status."""
import json
import os
import socket
import struct
import threading
import time
import urllib.error
import urllib.request

from urllib.parse import quote

from flask import Flask, Response, jsonify, redirect, render_template, request

app = Flask(__name__)

JOIN_ADDRESS = "mc.vasumenon.com"
# Where the servers listen: flatboy itself, which a container reaches through MC_HOST.
MC_HOST = os.environ.get("MC_HOST", "127.0.0.1")
SERVERS = [
    {"id": "rocket_lockett", "name": "Rocket Lockett", "host": MC_HOST, "port": 25567,
     "machine": "flatboy", "join": JOIN_ADDRESS},
    {"id": "bsm", "name": "BSM", "host": MC_HOST, "port": 25566,
     "machine": "flatboy", "join": None},
]
CACHE_SECONDS = 30
_cache = {"at": 0.0, "data": None}
_lock = threading.Lock()


# --- Minecraft Server List Ping (https://minecraft.wiki/w/Java_Edition_protocol/Server_List_Ping)

def _varint(n):
    out = b""
    n &= 0xFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _read_varint(sock):
    n = shift = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise ConnectionError("closed")
        n |= (b[0] & 0x7F) << shift
        if not b[0] & 0x80:
            return n
        shift += 7
        if shift > 35:
            raise ValueError("varint too long")


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def _flatten(desc):
    """MOTD can be a string or a chat component; return plain text without § codes."""
    if isinstance(desc, dict):
        text = desc.get("text", "") + "".join(_flatten(e) for e in desc.get("extra", []))
    elif isinstance(desc, list):
        text = "".join(_flatten(e) for e in desc)
    else:
        text = str(desc or "")
    out, skip = [], False
    for ch in text:
        if skip:
            skip = False
        elif ch == "§":
            skip = True
        else:
            out.append(ch)
    return "".join(out).strip()


def ping(host, port, timeout=2.0):
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            hb = host.encode()
            handshake = b"\x00" + _varint(-1) + _varint(len(hb)) + hb + struct.pack(">H", port) + _varint(1)
            s.sendall(_varint(len(handshake)) + handshake + b"\x01\x00")
            _read_varint(s)                      # packet length
            if _read_varint(s) != 0:             # packet id
                raise ValueError("unexpected packet")
            payload = json.loads(_recv_exact(s, _read_varint(s)))
        players = payload.get("players", {})
        return {
            "online": True,
            "latency_ms": round((time.monotonic() - start) * 1000),
            "version": payload.get("version", {}).get("name"),
            "players": players.get("online", 0),
            "max_players": players.get("max", 0),
            "motd": _flatten(payload.get("description")),
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {"online": False}


def bot_health(url, timeout=3.0):
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "mc_site-status"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read())
    except (OSError, ValueError):            # URLError/HTTPError (503 = bot disconnected) are OSErrors
        return {"online": False}
    if not payload.get("connected"):
        return {"online": False}
    return {
        "online": True,
        "latency_ms": round((time.monotonic() - start) * 1000),
        "version": payload.get("version"),
        "players": payload.get("players", 0),
        "max_players": "?",
        "motd": None,
    }


# --- flatboy itself

def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def machine_stats():
    mem = {}
    for line in (_read("/proc/meminfo", "") or "").splitlines():
        k, v = line.split(":", 1)
        mem[k] = int(v.split()[0]) * 1024
    temp = None
    for i in range(16):
        if _read(f"/sys/class/thermal/thermal_zone{i}/type") == "x86_pkg_temp":
            t = _read(f"/sys/class/thermal/thermal_zone{i}/temp")
            temp = round(int(t) / 1000) if t else None
            break
    batteries = [int(c) for c in (_read(f"/sys/class/power_supply/BAT{i}/capacity") for i in range(2)) if c]
    return {
        "uptime_s": int(float((_read("/proc/uptime", "0") or "0").split()[0])),
        "load": [float(x) for x in (_read("/proc/loadavg", "0 0 0") or "0 0 0").split()[:3]],
        "mem_used": mem.get("MemTotal", 0) - mem.get("MemAvailable", 0),
        "mem_total": mem.get("MemTotal", 0),
        "cpu_temp_c": temp,
        "battery_pct": round(sum(batteries) / len(batteries)) if batteries else None,
        "on_ac": _read("/sys/class/power_supply/AC/online") == "1",
    }


def status():
    with _lock:
        if _cache["data"] and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]
        servers = []
        for srv in SERVERS:
            public = {k: v for k, v in srv.items() if k not in ("host", "port", "health_url")}
            result = bot_health(srv["health_url"]) if "health_url" in srv else ping(srv["host"], srv["port"])
            servers.append({**public, **result})
        _cache["data"] = {"checked_at": int(time.time()), "servers": servers, "machine": machine_stats()}
        _cache["at"] = time.time()
        return _cache["data"]


@app.route("/")
def index():
    return render_template("index.html", s=status(), join=JOIN_ADDRESS)


@app.route("/api/status")
def api_status():
    resp = jsonify(status())
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return resp


# --- /map: BlueMap's web map, which the Rocket Lockett server serves on MAP_URL. The tunnel
# can route a path but not strip it, and BlueMap expects to be at the root, so it's passed
# through here with /map removed. Only GET and HEAD; nothing is cached or changed on the way.

MAP_URL = os.environ.get("MAP_URL", "http://127.0.0.1:8100").rstrip("/")
# Request headers BlueMap uses (compressed tiles, revalidation); everything else stays here.
_MAP_REQUEST_HEADERS = ("Accept", "Accept-Encoding", "If-Modified-Since", "If-None-Match")
_MAP_RESPONSE_HEADERS = ("Content-Type", "Content-Encoding", "Cache-Control", "ETag",
                         "Last-Modified", "Expires")
# BlueMap's web app renders with WebGL and decodes tiles in workers made from blobs.
MAP_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
           "worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
           "img-src 'self' data: blob:; connect-src 'self'; font-src 'self' data:; "
           "frame-ancestors 'none'; base-uri 'self'; form-action 'none'")


@app.route("/map")
def map_root():
    # The web app loads its files relative to the page, so it must be /map/, not /map.
    return redirect("/map/", code=301)


@app.route("/map/", defaults={"path": ""}, methods=["GET", "HEAD"])
@app.route("/map/<path:path>", methods=["GET", "HEAD"])
def map_passthrough(path):
    target = f"{MAP_URL}/{quote(path)}"
    if request.query_string:
        target += "?" + request.query_string.decode("latin-1")
    headers = {h: request.headers[h] for h in _MAP_REQUEST_HEADERS if h in request.headers}
    upstream = urllib.request.Request(target, headers=headers, method=request.method)
    try:
        r = urllib.request.urlopen(upstream, timeout=15)
    except urllib.error.HTTPError as e:  # 304 Not Modified and 404s land here too
        r = e
    except OSError:
        return Response("The map is not available right now.", status=502,
                        mimetype="text/plain", headers={"Content-Security-Policy": MAP_CSP})
    body = r.read() if request.method == "GET" else b""
    resp = Response(body, status=r.status)
    for h in _MAP_RESPONSE_HEADERS:
        if r.headers.get(h):
            resp.headers[h] = r.headers[h]
    resp.headers["Content-Security-Policy"] = MAP_CSP
    # Werkzeug would otherwise fill in its own Content-Length for HEAD; keep BlueMap's.
    if request.method == "HEAD" and r.headers.get("Content-Length"):
        resp.headers["Content-Length"] = r.headers["Content-Length"]
    return resp


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Content-Security-Policy",
                            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
    return resp
