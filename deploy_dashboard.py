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

import socket, json, struct, base64, os, sys
import urllib.request, urllib.parse, urllib.error

# ── Dashboard definition ──────────────────────────────────────────────────────
DASHBOARD = {
    "title": "Eastron SDM72D-M",
    "views": [
        {
            "title": "Overview",
            "path": "eastron-overview",
            "icon": "mdi:lightning-bolt",
            "cards": [
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {"type": "gauge", "entity": "sensor.sdm72d_l1_voltage",
                         "name": "L1 Voltage", "min": 195, "max": 265, "needle": True,
                         "severity": {"green": 216, "yellow": 253, "red": 258}},
                        {"type": "gauge", "entity": "sensor.sdm72d_frequency",
                         "name": "Frequency", "min": 49, "max": 51, "needle": True,
                         "severity": {"green": 49.5, "yellow": 50.5, "red": 50.8}},
                        {"type": "gauge", "entity": "sensor.sdm72d_total_active_power",
                         "name": "Active Power", "min": 0, "max": 23000, "needle": True,
                         "severity": {"green": 0, "yellow": 15000, "red": 20000}},
                    ],
                },
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {"type": "gauge", "entity": "sensor.sdm72d_l1_current",
                         "name": "L1 Current", "min": 0, "max": 100, "needle": True,
                         "severity": {"green": 0, "yellow": 63, "red": 85}},
                        {"type": "gauge", "entity": "sensor.sdm72d_total_power_factor",
                         "name": "Power Factor", "min": 0, "max": 1, "needle": True,
                         "severity": {"green": 0.9, "yellow": 0.7, "red": 0}},
                        {"type": "gauge", "entity": "sensor.sdm72d_neutral_current",
                         "name": "Neutral Current", "min": 0, "max": 100, "needle": True,
                         "severity": {"green": 0, "yellow": 10, "red": 30}},
                    ],
                },
                {
                    "type": "entities",
                    "title": "System Totals",
                    "entities": [
                        {"entity": "sensor.sdm72d_total_active_power",   "name": "Active Power",    "icon": "mdi:flash"},
                        {"entity": "sensor.sdm72d_total_apparent_power", "name": "Apparent Power",  "icon": "mdi:flash-outline"},
                        {"entity": "sensor.sdm72d_total_reactive_power", "name": "Reactive Power",  "icon": "mdi:flash-circle"},
                        {"entity": "sensor.sdm72d_total_power_factor",   "name": "Power Factor",    "icon": "mdi:angle-acute"},
                        {"entity": "sensor.sdm72d_frequency",            "name": "Frequency",       "icon": "mdi:sine-wave"},
                        {"type": "divider"},
                        {"entity": "sensor.sdm72d_import_energy",        "name": "Import Energy",   "icon": "mdi:transmission-tower-import"},
                        {"entity": "sensor.sdm72d_export_energy",        "name": "Export Energy",   "icon": "mdi:transmission-tower-export"},
                        {"entity": "sensor.sdm72d_total_active_energy",  "name": "Total Active Energy",   "icon": "mdi:counter"},
                        {"entity": "sensor.sdm72d_total_reactive_energy","name": "Total Reactive Energy", "icon": "mdi:counter"},
                    ],
                },
                {
                    "type": "glance",
                    "title": "Averages",
                    "columns": 3,
                    "entities": [
                        {"entity": "sensor.sdm72d_average_l_n_voltage",  "name": "Avg L-N V"},
                        {"entity": "sensor.sdm72d_average_l_l_voltage",  "name": "Avg L-L V"},
                        {"entity": "sensor.sdm72d_average_line_current", "name": "Avg Current"},
                        {"entity": "sensor.sdm72d_neutral_current",      "name": "Neutral A"},
                        {"entity": "sensor.sdm72d_frequency",            "name": "Frequency"},
                    ],
                },
            ],
        },
        {
            "title": "Per Phase",
            "path": "eastron-phases",
            "icon": "mdi:chart-bar",
            "cards": [
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {"type": "gauge", "entity": "sensor.sdm72d_l1_voltage",
                         "name": "L1 Voltage", "min": 195, "max": 265, "needle": True,
                         "severity": {"green": 216, "yellow": 253, "red": 258}},
                        {"type": "gauge", "entity": "sensor.sdm72d_l2_voltage",
                         "name": "L2 Voltage", "min": 195, "max": 265, "needle": True,
                         "severity": {"green": 216, "yellow": 253, "red": 258}},
                        {"type": "gauge", "entity": "sensor.sdm72d_l3_voltage",
                         "name": "L3 Voltage", "min": 195, "max": 265, "needle": True,
                         "severity": {"green": 216, "yellow": 253, "red": 258}},
                    ],
                },
                {
                    "type": "horizontal-stack",
                    "cards": [
                        {"type": "gauge", "entity": "sensor.sdm72d_l1_current",
                         "name": "L1 Current", "min": 0, "max": 100, "needle": True,
                         "severity": {"green": 0, "yellow": 63, "red": 85}},
                        {"type": "gauge", "entity": "sensor.sdm72d_l2_current",
                         "name": "L2 Current", "min": 0, "max": 100, "needle": True,
                         "severity": {"green": 0, "yellow": 63, "red": 85}},
                        {"type": "gauge", "entity": "sensor.sdm72d_l3_current",
                         "name": "L3 Current", "min": 0, "max": 100, "needle": True,
                         "severity": {"green": 0, "yellow": 63, "red": 85}},
                    ],
                },
                {
                    "type": "glance", "title": "Line-to-Line Voltages", "columns": 3,
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_l2_voltage", "name": "L1-L2"},
                        {"entity": "sensor.sdm72d_l2_l3_voltage", "name": "L2-L3"},
                        {"entity": "sensor.sdm72d_l3_l1_voltage", "name": "L3-L1"},
                    ],
                },
                {
                    "type": "glance", "title": "Active Power (W)", "columns": 3,
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_active_power", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_active_power", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_active_power", "name": "L3"},
                    ],
                },
                {
                    "type": "glance", "title": "Reactive Power (VAr)", "columns": 3,
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_reactive_power", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_reactive_power", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_reactive_power", "name": "L3"},
                    ],
                },
                {
                    "type": "glance", "title": "Apparent Power (VA)", "columns": 3,
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_apparent_power", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_apparent_power", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_apparent_power", "name": "L3"},
                    ],
                },
                {
                    "type": "glance", "title": "Power Factor", "columns": 3,
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_power_factor", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_power_factor", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_power_factor", "name": "L3"},
                    ],
                },
            ],
        },
        {
            "title": "Energy History",
            "path": "eastron-energy",
            "icon": "mdi:chart-line",
            "cards": [
                {"type": "energy-date-selection"},
                {
                    "type": "statistics-graph",
                    "title": "Import vs Export Energy",
                    "entities": [
                        {"entity": "sensor.sdm72d_import_energy", "name": "Import"},
                        {"entity": "sensor.sdm72d_export_energy", "name": "Export"},
                    ],
                    "stat_types": ["sum"],
                    "period": "day",
                },
                {
                    "type": "statistics-graph",
                    "title": "Total Active Power History",
                    "entities": [
                        {"entity": "sensor.sdm72d_total_active_power", "name": "Active Power"},
                    ],
                    "stat_types": ["mean", "max"],
                    "period": "hour",
                },
                {
                    "type": "history-graph",
                    "title": "Phase Voltages (Last 24h)",
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_voltage", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_voltage", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_voltage", "name": "L3"},
                    ],
                    "hours_to_show": 24,
                    "refresh_interval": 60,
                },
                {
                    "type": "history-graph",
                    "title": "Phase Currents (Last 24h)",
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_current", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_current", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_current", "name": "L3"},
                    ],
                    "hours_to_show": 24,
                    "refresh_interval": 60,
                },
            ],
        },
        {
            "title": "Statistics",
            "path": "statistics",
            "icon": "mdi:chart-bar",
            "cards": [
                {
                    "type": "statistics-graph",
                    "title": "Energy Import / Export (Monthly)",
                    "period": "month",
                    "stat_types": ["sum"],
                    "entities": [
                        {"entity": "sensor.sdm72d_import_energy",  "name": "Import"},
                        {"entity": "sensor.sdm72d_export_energy",  "name": "Export"},
                    ],
                },
                {
                    "type": "statistics-graph",
                    "title": "Total Active Energy (Monthly)",
                    "period": "month",
                    "stat_types": ["sum"],
                    "entities": [
                        {"entity": "sensor.sdm72d_total_active_energy", "name": "Total kWh"},
                    ],
                },
                {
                    "type": "statistics-graph",
                    "title": "Total Active Power — Daily Mean / Max",
                    "period": "day",
                    "stat_types": ["mean", "max"],
                    "entities": [
                        {"entity": "sensor.sdm72d_total_active_power", "name": "Total Power"},
                    ],
                },
                {
                    "type": "statistics-graph",
                    "title": "Per-Phase Active Power (Daily Mean)",
                    "period": "day",
                    "stat_types": ["mean"],
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_active_power", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_active_power", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_active_power", "name": "L3"},
                    ],
                },
                {
                    "type": "statistics-graph",
                    "title": "Per-Phase Voltage (Daily Mean / Min / Max)",
                    "period": "day",
                    "stat_types": ["mean", "min", "max"],
                    "entities": [
                        {"entity": "sensor.sdm72d_l1_voltage", "name": "L1"},
                        {"entity": "sensor.sdm72d_l2_voltage", "name": "L2"},
                        {"entity": "sensor.sdm72d_l3_voltage", "name": "L3"},
                    ],
                },
            ],
        },
    ],
}

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
    print("Deploying dashboard (4 views) ...")

    resp = ws_call(s, {"id": 1, "type": "lovelace/config/save", "config": DASHBOARD})
    if not resp.get("success"):
        print(f"ERROR: Save failed: {resp.get('error')}")
        sys.exit(1)

    print(f"  Saved: {len(DASHBOARD['views'])} views, "
          f"{sum(len(v.get('cards',[])) for v in DASHBOARD['views'])} cards total.")
    print()
    print(f"Dashboard deployed successfully.")
    print(f"Open: http://{HA_HOST}:{HA_PORT}/lovelace")
    print()
    print("Views:")
    for v in DASHBOARD["views"]:
        print(f"  {v['title']:20s}  http://{HA_HOST}:{HA_PORT}/lovelace/{v['path']}")


if __name__ == "__main__":
    main()
