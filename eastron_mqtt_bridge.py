#!/usr/bin/env python3
"""
Eastron SDM72D-M → MQTT bridge
Polls the meter via Modbus TCP and publishes readings to Home Assistant via MQTT.

Requirements: Python 3.6+, no extra packages needed.

Run:  python3 eastron_mqtt_bridge.py
Auto: see README section below for systemd service installation
"""

import socket
import struct
import json
import time
import logging
import sys

# ── Configuration ─────────────────────────────────────────────────────────────
MODBUS_HOST   = "192.168.0.22"
MODBUS_PORT   = 502
MODBUS_SLAVE  = 1
MODBUS_TIMEOUT = 5   # seconds per Modbus TCP response

MQTT_HOST     = "192.168.0.4"
MQTT_PORT     = 1883
MQTT_USER     = "sahel"
MQTT_PASS     = "sahel15"
MQTT_CLIENT   = "eastron_bridge"

BASE_TOPIC    = "eastron/sdm72d"

POLL_FAST     = 30   # seconds — voltage, current, power
POLL_SLOW     = 60   # seconds — energy totals

# ── Register map ──────────────────────────────────────────────────────────────
# (topic_suffix, start_address, fast_poll)  — all float32, function code 04
REGISTERS = [
    ("l1_voltage",           0,    True),
    ("l2_voltage",           2,    True),
    ("l3_voltage",           4,    True),
    ("l1_current",           6,    True),
    ("l2_current",           8,    True),
    ("l3_current",           10,   True),
    ("l1_active_power",      12,   True),
    ("l2_active_power",      14,   True),
    ("l3_active_power",      16,   True),
    ("l1_apparent_power",    18,   True),
    ("l2_apparent_power",    20,   True),
    ("l3_apparent_power",    22,   True),
    ("l1_reactive_power",    24,   True),
    ("l2_reactive_power",    26,   True),
    ("l3_reactive_power",    28,   True),
    ("l1_power_factor",      30,   True),
    ("l2_power_factor",      32,   True),
    ("l3_power_factor",      34,   True),
    ("avg_ln_voltage",       42,   True),
    ("avg_current",          46,   True),
    ("total_active_power",   52,   True),
    ("total_apparent_power", 56,   True),
    ("total_reactive_power", 60,   True),
    ("total_power_factor",   62,   True),
    ("frequency",            70,   True),
    ("import_energy",        72,   False),
    ("export_energy",        74,   False),
    ("avg_ll_voltage",       206,  True),
    ("neutral_current",      224,  True),
    ("l1l2_voltage",         200,  True),
    ("l2l3_voltage",         202,  True),
    ("l3l1_voltage",         204,  True),
    ("total_active_energy",  342,  False),
    ("total_reactive_energy",344,  False),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("eastron")


# ── Minimal raw MQTT client ───────────────────────────────────────────────────

class MQTTClient:
    def __init__(self, host, port, client_id, user, password):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.user = user
        self.password = password
        self.sock = None
        self._pkt_id = 0

    def _encode_string(self, s):
        b = s.encode("utf-8")
        return struct.pack("!H", len(b)) + b

    def _remaining_length(self, n):
        result = b""
        while True:
            byte = n % 128
            n //= 128
            if n > 0:
                byte |= 0x80
            result += bytes([byte])
            if n == 0:
                break
        return result

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        # Build CONNECT packet
        cid = self._encode_string(self.client_id)
        user = self._encode_string(self.user)
        pwd = self._encode_string(self.password)
        # Protocol name + level + connect flags + keepalive
        proto = self._encode_string("MQTT") + bytes([4])  # protocol level 4 = MQTT 3.1.1
        flags = 0xC2  # clean session + username + password
        keepalive = struct.pack("!H", 60)
        var_header = proto + bytes([flags]) + keepalive
        payload = cid + user + pwd
        body = var_header + payload
        packet = bytes([0x10]) + self._remaining_length(len(body)) + body
        self.sock.sendall(packet)
        # Read CONNACK
        resp = self.sock.recv(4)
        if len(resp) >= 4 and resp[0] == 0x20 and resp[3] == 0:
            log.info("MQTT connected to %s:%d", self.host, self.port)
            return True
        raise ConnectionError(f"MQTT CONNACK failed: {resp.hex()}")

    def publish(self, topic, payload, retain=False):
        topic_b = self._encode_string(topic)
        payload_b = payload.encode("utf-8") if isinstance(payload, str) else payload
        flags = 0x30 | (0x01 if retain else 0x00)
        body = topic_b + payload_b
        packet = bytes([flags]) + self._remaining_length(len(body)) + body
        self.sock.sendall(packet)

    def ping(self):
        self.sock.sendall(bytes([0xC0, 0x00]))
        self.sock.settimeout(5)
        try:
            resp = self.sock.recv(2)
        except socket.timeout:
            raise ConnectionError("MQTT PINGRESP timeout")
        finally:
            self.sock.settimeout(None)

    def disconnect(self):
        if self.sock:
            try:
                self.sock.sendall(bytes([0xE0, 0x00]))
                self.sock.close()
            except Exception:
                pass
            self.sock = None


# ── Minimal Modbus TCP client ─────────────────────────────────────────────────

_modbus_tid = 0

def modbus_read_float32(host, port, slave, address, timeout=MODBUS_TIMEOUT):
    global _modbus_tid
    _modbus_tid = (_modbus_tid + 1) & 0xFFFF
    tid = _modbus_tid
    # Request: function 04 (read input registers), 2 registers
    pdu = bytes([slave, 0x04]) + struct.pack("!HH", address, 2)
    mbap = struct.pack("!HHHB", tid, 0, len(pdu), slave) + pdu[1:]
    request = struct.pack("!HHH", tid, 0, len(pdu)) + pdu

    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(request)
        # Read MBAP header (6 bytes) + PDU
        header = b""
        while len(header) < 6:
            chunk = s.recv(6 - len(header))
            if not chunk:
                raise EOFError("Connection closed")
            header += chunk
        r_tid, r_proto, r_len = struct.unpack("!HHH", header)
        body = b""
        while len(body) < r_len:
            chunk = s.recv(r_len - len(body))
            if not chunk:
                raise EOFError("Connection closed")
            body += chunk
        # body: unit_id(1) + func(1) + byte_count(1) + data(4)
        if len(body) < 6 or body[1] != 0x04:
            raise ValueError(f"Unexpected Modbus response: {body.hex()}")
        return struct.unpack("!f", body[3:7])[0]


# ── Main polling loop ─────────────────────────────────────────────────────────

def poll_and_publish(mqtt, fast_only=False):
    ok = 0
    fail = 0
    for suffix, addr, fast in REGISTERS:
        if fast_only and not fast:
            continue
        try:
            value = modbus_read_float32(MODBUS_HOST, MODBUS_PORT, MODBUS_SLAVE, addr)
            rounded = round(value, 3)
            topic = f"{BASE_TOPIC}/{suffix}"
            mqtt.publish(topic, str(rounded))
            ok += 1
            log.debug("  %s = %s", suffix, rounded)
        except Exception as e:
            fail += 1
            log.warning("  Failed %s (addr %d): %s", suffix, addr, e)
    return ok, fail


def main():
    log.info("Eastron SDM72D-M MQTT bridge starting")
    log.info("  Modbus: %s:%d  slave=%d", MODBUS_HOST, MODBUS_PORT, MODBUS_SLAVE)
    log.info("  MQTT:   %s:%d  user=%s", MQTT_HOST, MQTT_PORT, MQTT_USER)

    mqtt = MQTTClient(MQTT_HOST, MQTT_PORT, MQTT_CLIENT, MQTT_USER, MQTT_PASS)
    last_slow = 0
    last_ping = 0
    consecutive_failures = 0

    while True:
        # (Re)connect MQTT if needed
        if mqtt.sock is None:
            try:
                mqtt.connect()
                consecutive_failures = 0
            except Exception as e:
                log.error("MQTT connect failed: %s — retry in 30s", e)
                time.sleep(30)
                continue

        now = time.monotonic()
        do_slow = (now - last_slow) >= POLL_SLOW

        log.info("Polling Eastron (%s poll)...", "full" if do_slow else "fast")
        try:
            ok, fail = poll_and_publish(mqtt, fast_only=not do_slow)
            log.info("  %d OK, %d failed", ok, fail)
            if do_slow:
                last_slow = now
            if fail > 0:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    log.error("5 consecutive poll rounds with failures — check RS485 wiring")
            else:
                consecutive_failures = 0
        except Exception as e:
            log.error("Poll error: %s", e)
            mqtt.disconnect()

        # MQTT keepalive ping every 45s
        if now - last_ping >= 45 and mqtt.sock:
            try:
                mqtt.ping()
                last_ping = now
            except Exception as e:
                log.warning("MQTT ping failed: %s — reconnecting", e)
                mqtt.disconnect()

        time.sleep(POLL_FAST)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped.")
