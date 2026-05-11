#!/usr/bin/env bash
# deploy_dashboard.sh — Push the Eastron SDM72D-M Lovelace dashboard to Home Assistant
#
# Requirements: bash, curl, python3 (standard on any Linux)
# Usage:        bash deploy_dashboard.sh
#
# Edit the three lines below, then run the script.

# ── Configure these three lines ───────────────────────────────────────────────
HA_HOST="192.168.0.4"
HA_USER="sahel"
HA_PASS="sahel15"
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

HA_PORT=8123
CLIENT_ID="http://localhost/"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DASHBOARD_FILE="$SCRIPT_DIR/dashboard.json"

# ── Check dependencies ────────────────────────────────────────────────────────
for cmd in curl python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' is required but not installed."
        exit 1
    fi
done

if [[ ! -f "$DASHBOARD_FILE" ]]; then
    echo "ERROR: dashboard.json not found at $DASHBOARD_FILE"
    exit 1
fi

# ── Step 1: Start login flow ──────────────────────────────────────────────────
echo "Connecting to Home Assistant at $HA_HOST:$HA_PORT ..."

FLOW_RESP=$(curl -sf -X POST "http://$HA_HOST:$HA_PORT/auth/login_flow" \
    -H "Content-Type: application/json" \
    -d "{\"handler\":[\"homeassistant\",null],\"redirect_uri\":\"$CLIENT_ID\",\"client_id\":\"$CLIENT_ID\"}")

FLOW_ID=$(echo "$FLOW_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['flow_id'])")

# ── Step 2: Submit credentials ────────────────────────────────────────────────
LOGIN_RESP=$(curl -sf -X POST "http://$HA_HOST:$HA_PORT/auth/login_flow/$FLOW_ID" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$HA_USER\",\"password\":\"$HA_PASS\",\"client_id\":\"$CLIENT_ID\"}")

LOGIN_TYPE=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('type',''))")
if [[ "$LOGIN_TYPE" != "create_entry" ]]; then
    echo "ERROR: Login failed. Check HA_USER and HA_PASS."
    echo "       Response: $LOGIN_RESP"
    exit 1
fi

AUTH_CODE=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")

# ── Step 3: Exchange code for access token ────────────────────────────────────
TOKEN_RESP=$(curl -sf -X POST "http://$HA_HOST:$HA_PORT/auth/token" \
    --data-urlencode "grant_type=authorization_code" \
    --data-urlencode "code=$AUTH_CODE" \
    --data-urlencode "client_id=$CLIENT_ID")

TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  Authenticated."

# ── Step 4: Deploy dashboard via WebSocket ────────────────────────────────────
# HA only exposes the Lovelace save API over WebSocket (not REST).
# python3 is used here purely as a WebSocket transport — the dashboard config
# lives in dashboard.json and the connection parameters come from this script.

DASHBOARD=$(cat "$DASHBOARD_FILE")
VIEW_COUNT=$(echo "$DASHBOARD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('views',[])))")
CARD_COUNT=$(echo "$DASHBOARD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(len(v.get('cards',[])) for v in d.get('views',[])))")

echo "Deploying dashboard ($VIEW_COUNT views, $CARD_COUNT top-level cards) ..."

python3 - "$HA_HOST" "$HA_PORT" "$TOKEN" "$DASHBOARD_FILE" << 'PYEOF'
import sys, socket, json, struct, base64, os

host, port, token, dashboard_file = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]

with open(dashboard_file) as f:
    dashboard = json.load(f)

def ws_connect(host, port):
    s = socket.create_connection((host, port), timeout=15)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((
        f"GET /api/websocket HTTP/1.1\r\nHost: {host}:{port}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
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
    if n < 126:       s.sendall(bytes([0x81, 0x80 | n]) + mask + masked)
    elif n < 65536:   s.sendall(bytes([0x81, 0xFE]) + struct.pack("!H", n) + mask + masked)
    else:             s.sendall(bytes([0x81, 0xFF]) + struct.pack("!Q", n) + mask + masked)

def ws_recv(s):
    def rx(n):
        buf = b""
        while len(buf) < n:
            c = s.recv(n - len(buf))
            if not c: raise EOFError
            buf += c
        return buf
    b0, b1 = rx(2)
    masked = (b1 & 0x80) != 0
    ln = b1 & 0x7F
    if ln == 126: ln = struct.unpack("!H", rx(2))[0]
    elif ln == 127: ln = struct.unpack("!Q", rx(8))[0]
    mask = rx(4) if masked else b""
    payload = rx(ln)
    if masked: payload = bytes(payload[i] ^ mask[i % 4] for i in range(ln))
    return json.loads(payload)

s = ws_connect(host, port)
assert ws_recv(s)["type"] == "auth_required"
ws_send(s, {"type": "auth", "access_token": token})
assert ws_recv(s)["type"] == "auth_ok"

ws_send(s, {"id": 1, "type": "lovelace/config/save", "config": dashboard})
while True:
    r = ws_recv(s)
    if r.get("id") == 1: break

if not r.get("success"):
    print(f"ERROR: Save failed: {r.get('error')}", file=sys.stderr)
    sys.exit(1)
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo "  Saved."
echo ""
echo "Dashboard deployed successfully."
echo "Open: http://$HA_HOST:$HA_PORT/lovelace"
echo ""
echo "Views:"
echo "  Overview        http://$HA_HOST:$HA_PORT/lovelace/eastron-overview"
echo "  Per Phase       http://$HA_HOST:$HA_PORT/lovelace/eastron-phases"
echo "  Energy History  http://$HA_HOST:$HA_PORT/lovelace/eastron-energy"
echo "  Statistics      http://$HA_HOST:$HA_PORT/lovelace/statistics"
