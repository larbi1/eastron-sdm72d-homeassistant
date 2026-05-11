#!/usr/bin/env python3
"""
deploy_dashboard.py — Push the Eastron SDM72D-M Lovelace dashboard to Home Assistant.

Requirements: Python 3.6+, no extra packages needed.
Usage:        python3 deploy_dashboard.py

Edit the three configuration variables below, then run the script from any
machine on the same network as Home Assistant.
"""

# ── Configuration — edit these three lines ────────────────────────────────────
HA_HOST = "192.168.0.4"   # Home Assistant IP
HA_USER = "sahel"         # HA username (the one you log into the UI with)
HA_PASS = "sahel15"       # HA password
# ─────────────────────────────────────────────────────────────────────────────

HA_PORT    = 8123
CLIENT_ID  = "http://localhost/"

import socket, json, struct, base64, os, sys, pathlib
import urllib.request, urllib.parse, urllib.error

DASHBOARD_FILE = pathlib.Path(__file__).parent / "dashboard.json"

# ── Auth via HA login flow ────────────────────────────────────────────────────

def get_token():
    def post_json(path, data):
        req = urllib.request.Request(
            f"http://{HA_HOST}:{HA_PORT}{path}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    flow = post_json("/auth/login_flow", {
        "handler": ["homeassistant", None],
        "redirect_uri": CLIENT_ID,
        "client_id": CLIENT_ID,
    })
    result = post_json(f"/auth/login_flow/{flow['flow_id']}", {
        "username": HA_USER,
        "password": HA_PASS,
        "client_id": CLIENT_ID,
    })
    if result.get("type") != "create_entry":
        raise RuntimeError(f"Login failed: {result}")

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": result["result"],
        "client_id": CLIENT_ID,
    }).encode()
    req = urllib.request.Request(
        f"http://{HA_HOST}:{HA_PORT}/auth/token", data=data
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


# ── Raw WebSocket client ──────────────────────────────────────────────────────

def ws_connect():
    s = socket.create_connection((HA_HOST, HA_PORT), timeout=15)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((
        f"GET /api/websocket HTTP/1.1\r\n"
        f"Host: {HA_HOST}:{HA_PORT}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(1024)
    return s


def ws_send(s, msg):
    data = json.dumps(msg).encode()
    n = len(data)
    mask = os.urandom(4)
    masked = bytes(data[i] ^ mask[i % 4] for i in range(n))
    if n < 126:
        s.sendall(bytes([0x81, 0x80 | n]) + mask + masked)
    elif n < 65536:
        s.sendall(bytes([0x81, 0xFE]) + struct.pack("!H", n) + mask + masked)
    else:
        s.sendall(bytes([0x81, 0xFF]) + struct.pack("!Q", n) + mask + masked)


def ws_recv(s):
    def rx(n):
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise EOFError("Connection closed")
            buf += chunk
        return buf

    b0, b1 = rx(2)
    masked = (b1 & 0x80) != 0
    ln = b1 & 0x7F
    if ln == 126:
        ln = struct.unpack("!H", rx(2))[0]
    elif ln == 127:
        ln = struct.unpack("!Q", rx(8))[0]
    mask = rx(4) if masked else b""
    payload = rx(ln)
    if masked:
        payload = bytes(payload[i] ^ mask[i % 4] for i in range(ln))
    return json.loads(payload)


def ws_call(s, msg):
    ws_send(s, msg)
    mid = msg.get("id")
    while True:
        r = ws_recv(s)
        if r.get("id") == mid:
            return r


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not DASHBOARD_FILE.exists():
        print(f"ERROR: dashboard.json not found at {DASHBOARD_FILE}")
        sys.exit(1)

    with open(DASHBOARD_FILE) as f:
        dashboard = json.load(f)

    print(f"Connecting to Home Assistant at {HA_HOST}:{HA_PORT} ...")

    try:
        token = get_token()
    except urllib.error.HTTPError as e:
        print(f"ERROR: Auth failed ({e}). Check HA_HOST, HA_USER, HA_PASS.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot reach Home Assistant: {e}")
        sys.exit(1)

    print("  Authenticated.")

    s = ws_connect()
    msg = ws_recv(s)
    if msg.get("type") != "auth_required":
        print(f"ERROR: Unexpected WebSocket message: {msg}")
        sys.exit(1)

    ws_send(s, {"type": "auth", "access_token": token})
    msg = ws_recv(s)
    if msg.get("type") != "auth_ok":
        print(f"ERROR: WebSocket auth failed: {msg}")
        sys.exit(1)

    print("  WebSocket open.")

    view_count = len(dashboard.get("views", []))
    card_count = sum(len(v.get("cards", [])) for v in dashboard.get("views", []))
    print(f"Deploying dashboard ({view_count} views, {card_count} top-level cards) ...")

    resp = ws_call(s, {"id": 1, "type": "lovelace/config/save", "config": dashboard})
    if not resp.get("success"):
        print(f"ERROR: Save failed: {resp.get('error')}")
        sys.exit(1)

    print("  Saved.")
    print()
    print("Dashboard deployed successfully.")
    print(f"Open: http://{HA_HOST}:{HA_PORT}/lovelace")
    print()
    print("Views:")
    for v in dashboard.get("views", []):
        print(f"  {v['title']:20s}  http://{HA_HOST}:{HA_PORT}/lovelace/{v['path']}")


if __name__ == "__main__":
    main()
