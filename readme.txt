================================================================================
  EASTRON SDM72D-M → HOME ASSISTANT SETUP
  Complete documentation of what was done and how it works
================================================================================

HARDWARE
--------
  Eastron SDM72D-M-2   3-phase energy meter (direct connection, up to 100A)
  Waveshare 8-CH RS485 TO POE ETH (B)   RS485-to-Ethernet gateway

NETWORK
-------
  Home Assistant   192.168.0.4:8123   user: sahel / sahel15
  Waveshare CH1    192.168.0.22:502   (Modbus TCP port)
  This machine     192.168.0.17       (runs the MQTT bridge service)
  Proxmox          192.168.0.15

PHYSICAL WIRING
---------------
  Eastron A+ terminal  →  Waveshare channel 1, terminal A
  Eastron B- terminal  →  Waveshare channel 1, terminal B

  Power/measurement wiring (1 phase 2 wire, per page 11 of SDM72D-M manual):
    Mains phase (L1)  →  Eastron terminal 1  (top-left)
    Mains neutral (N) →  Eastron terminal 4  (top-right)
    Load L1 out       →  Eastron terminal 5  (bottom-left)   [connect load here]
    Load N out        →  Eastron terminal 8  (bottom-right)  [connect load here]

  NOTE: Terminals 1+4 power the meter and measure voltage.
        Current is measured by current flowing THROUGH the meter (1→5 and 4→8).
        With nothing on terminals 5+8, current/power will read 0. That is normal.

HOW THE COMMUNICATION WORKS
----------------------------
  Eastron <--RS485--> Waveshare <--Modbus TCP (port 502)--> Home Assistant

  The Waveshare gateway is pre-configured as:
    - Mode: Modbus TCP to RTU (transparent bridge)
    - Port: 502
    - Baud: 9600, 8N1, no parity
    - No password

  The Eastron is configured at:
    - Modbus slave address: 1
    - Baud: 9600, 8N1
    - All registers use function code 04 (Read Input Registers)
    - Values are 32-bit floats (2 registers each)

HOW HOME ASSISTANT RECEIVES DATA
---------------------------------
  TWO parallel methods are active:

  METHOD 1 — Modbus YAML (primary, recommended)
    File: /config/modbus_eastron.yaml (on HA machine)
    Included via: /config/configuration.yaml → modbus: !include modbus_eastron.yaml
    HA polls Waveshare directly over Modbus TCP every 30s (60s for energy counters)
    Entity IDs: sensor.sdm72d_*  (e.g. sensor.sdm72d_l1_voltage)

  METHOD 2 — MQTT Bridge (secondary, backup)
    Script: /data/claude_share/eastron_home_assistant/eastron_mqtt_bridge.py
    Service: eastron_bridge (systemd user service, running on 192.168.0.17)
    The script polls Modbus TCP → publishes to Mosquitto MQTT on HA → HA creates sensors
    Entity IDs: sensor.eastron_sdm72d_m_sdm72d_*

  The Lovelace dashboard uses METHOD 1 (Modbus) entity IDs.

SENSORS (34 total)
------------------
  Phase voltages (L-N):    sensor.sdm72d_l1_voltage / l2 / l3              [V]
  Line-to-line voltages:   sensor.sdm72d_l1_l2_voltage / l2_l3 / l3_l1    [V]
  Average voltages:        sensor.sdm72d_average_l_n_voltage                [V]
                           sensor.sdm72d_average_l_l_voltage                [V]
  Phase currents:          sensor.sdm72d_l1_current / l2 / l3              [A]
  Average current:         sensor.sdm72d_average_line_current               [A]
  Neutral current:         sensor.sdm72d_neutral_current                    [A]
  Active power:            sensor.sdm72d_l1_active_power / l2 / l3         [W]
  Apparent power:          sensor.sdm72d_l1_apparent_power / l2 / l3       [VA]
  Reactive power:          sensor.sdm72d_l1_reactive_power / l2 / l3       [var]
  Power factor:            sensor.sdm72d_l1_power_factor / l2 / l3
  Totals:                  sensor.sdm72d_total_active_power                 [W]
                           sensor.sdm72d_total_apparent_power               [VA]
                           sensor.sdm72d_total_reactive_power               [var]
                           sensor.sdm72d_total_power_factor
  Frequency:               sensor.sdm72d_frequency                          [Hz]
  Energy:                  sensor.sdm72d_import_energy                      [kWh]
                           sensor.sdm72d_export_energy                      [kWh]
                           sensor.sdm72d_total_active_energy                [kWh]
                           sensor.sdm72d_total_reactive_energy              [kVArh]

LOVELACE DASHBOARD
------------------
  URL: http://192.168.0.4:8123/lovelace/eastron-overview
  3 views:
    Overview     — gauge dials (voltage, frequency, power, current, PF) + totals list
    Per Phase    — gauge dials per phase (voltage, current) + power/PF glance cards
    Energy History — statistics and history graphs

  The dashboard is stored in HA in "storage" mode (not a YAML file).
  It was pushed directly via the HA WebSocket API.

GRAPHICAL GAUGE CARDS
---------------------
  The dashboard uses HA's built-in "gauge" card type (no extra addons needed).
  Each gauge has a needle and colour zones:

  Voltage gauges (195–265 V):
    green  ≥ 216 V   (normal operating range 216–253 V)
    yellow ≥ 253 V   (high voltage warning)
    red    ≥ 258 V   (overvoltage)

  Current gauges (0–100 A):
    green  0–63 A    (normal)
    yellow 63–85 A   (high load)
    red    ≥ 85 A    (near limit)

  Active power gauge (0–23 000 W):
    green  0–15 000 W
    yellow 15 000–20 000 W
    red    ≥ 20 000 W

  Frequency gauge (49–51 Hz):
    green  ≥ 49.5 Hz
    yellow ≥ 50.5 Hz
    red    ≥ 50.8 Hz

  Power factor gauge (0–1):
    green  ≥ 0.9      (good)
    yellow ≥ 0.7      (acceptable)
    red    < 0.7      (poor)

SSH ACCESS TO HOME ASSISTANT
-----------------------------
  The "Advanced SSH & Web Terminal" addon is installed and running.

  From this machine (key auth, already set up):
    ssh hassio@192.168.0.4

  From any other machine (add your public key):
    1. Get your key:  cat ~/.ssh/id_ed25519.pub
    2. In HA UI: Settings → Add-ons → Advanced SSH & Web Terminal → Configuration
    3. Paste key under authorized_keys → Save → Restart addon

  Or set a password in the addon Configuration tab, then:
    ssh hassio@192.168.0.4   (will prompt for password)

  NOTE: username is "hassio", NOT "sahel" or "root". Port is 22.

MQTT BRIDGE SERVICE (on 192.168.0.17)
---------------------------------------
  Manage with:
    systemctl --user status eastron_bridge    # check if running
    systemctl --user restart eastron_bridge   # restart
    systemctl --user stop eastron_bridge      # stop
    journalctl --user -u eastron_bridge -f    # live logs

  To start automatically on boot without login:
    sudo loginctl enable-linger akaw

FILES IN /data/claude_share/eastron_home_assistant/
-----------------------------------------------------
  eastron_mqtt_bridge.py      MQTT bridge script (Python, no extra packages needed)
  eastron_bridge.service      Systemd user service unit file
  modbus_eastron.yaml         Modbus sensor config (deployed to HA /config/)
  lovelace_eastron.yaml       Reference dashboard YAML (deployed via API)
  configuration_addition.yaml Reference for what was added to configuration.yaml
  eastron_sdm72dmv2.pdf       Eastron SDM72D-M-2 user manual
  readme.txt                  This file
  readme.html                 HTML version of this documentation

WHAT HAPPENED DURING SETUP (summary)
--------------------------------------
  1. Scanned network to find the correct IPs (Waveshare channels + HA)
  2. Verified Waveshare CH1 was already configured correctly (no changes needed)
  3. Created modbus_eastron.yaml with all 34 register mappings
  4. Discovered HA had no SSH/file access, so used the REST/WebSocket API instead
  5. Pushed Lovelace dashboard via WebSocket (lovelace/config/save)
  6. Created 34 MQTT sensors via MQTT auto-discovery (mqtt.publish service)
  7. Wrote and deployed the MQTT bridge script as a systemd service
  8. Installed the Advanced SSH & Web Terminal addon via supervisor API
  9. Fixed modbus_eastron.yaml on HA (had duplicate 'modbus:' root key)
  10. Restarted HA core to load Modbus YAML → 34 Modbus sensors came live
  11. Fixed dashboard entity IDs to use Modbus sensors (correct full names)

NORMAL VALUES FOR 1-PHASE CONNECTION ON L1
--------------------------------------------
  L1 voltage:         ~230–240 V
  L2, L3 voltage:     0 V   (not connected — normal)
  Frequency:          ~50 Hz
  Avg L-N voltage:    ~79 V  (= L1/3, because L2+L3 are 0 — expected)
  Avg L-L voltage:    ~159 V (same reason — expected)
  Current/Power:      0 if no load is wired through terminals 5+8

MULTIPLE EASTRON METERS
-----------------------
  You can add as many meters as you like. Two scenarios:

  SCENARIO A — Multiple meters on the SAME RS485 bus / Waveshare channel
  -----------------------------------------------------------------------
  Each meter must have a unique Modbus slave address (set on the meter itself).
  All meters share the same Waveshare channel (same IP and port 502).

  Factory default for all Eastron meters is slave address 1.
  Change address on the meter via its front buttons before wiring the second one.

  Example: meter 1 = address 1, meter 2 = address 2, meter 3 = address 3.

  In /config/modbus_eastron.yaml add a second hub block (or add sensors to
  the same hub with different slave numbers):

  ── modbus_eastron.yaml excerpt for 2 meters on same channel ──
  - name: "eastron_meter1"
    type: tcp
    host: 192.168.0.22        # Waveshare CH1
    port: 502
    sensors:
      - name: "M1 L1 Voltage"
        unique_id: m1_sdm72d_l1_voltage
        slave: 1              # ← meter 1 address
        address: 0
        input_type: input
        data_type: float32
        unit_of_measurement: "V"
        device_class: voltage
        state_class: measurement
        scan_interval: 30
      # ... repeat all 34 registers with slave: 1

  - name: "eastron_meter2"
    type: tcp
    host: 192.168.0.22        # same Waveshare channel
    port: 502
    sensors:
      - name: "M2 L1 Voltage"
        unique_id: m2_sdm72d_l1_voltage
        slave: 2              # ← meter 2 address
        address: 0
        input_type: input
        data_type: float32
        unit_of_measurement: "V"
        device_class: voltage
        state_class: measurement
        scan_interval: 30
      # ... repeat all 34 registers with slave: 2

  Entity IDs produced:
    sensor.m1_l1_voltage   (meter 1)
    sensor.m2_l1_voltage   (meter 2)


  SCENARIO B — Multiple meters on DIFFERENT Waveshare channels
  ------------------------------------------------------------
  Each Waveshare channel is a separate TCP server with its own IP.
  Each meter can keep slave address 1 (factory default).

  Waveshare IPs in this installation:
    CH1: 192.168.0.22    CH2: 192.168.0.31    CH3: 192.168.0.12
    CH4: 192.168.0.39    CH5: 192.168.0.33    CH6: 192.168.0.40
    CH7: 192.168.0.18    CH8: 192.168.0.49

  ── modbus_eastron.yaml excerpt for 2 meters on different channels ──
  - name: "eastron_ch1"
    type: tcp
    host: 192.168.0.22        # Waveshare CH1
    port: 502
    sensors:
      - name: "CH1 L1 Voltage"
        unique_id: ch1_sdm72d_l1_voltage
        slave: 1
        address: 0
        input_type: input
        data_type: float32
        unit_of_measurement: "V"
        device_class: voltage
        state_class: measurement
        scan_interval: 30
      # ... all 34 registers

  - name: "eastron_ch2"
    type: tcp
    host: 192.168.0.31        # Waveshare CH2
    port: 502
    sensors:
      - name: "CH2 L1 Voltage"
        unique_id: ch2_sdm72d_l1_voltage
        slave: 1              # slave 1 again, different IP
        address: 0
        input_type: input
        data_type: float32
        unit_of_measurement: "V"
        device_class: voltage
        state_class: measurement
        scan_interval: 30
      # ... all 34 registers

  Entity IDs produced:
    sensor.ch1_l1_voltage   (CH1 meter)
    sensor.ch2_l1_voltage   (CH2 meter)

  NOTE: unique_id must be globally unique across all sensors.
        Use a clear prefix per meter (m1_, m2_, ch1_, ch2_, kitchen_, garage_, etc.)
        After editing the YAML, SSH into HA and restart:
          ha core restart
        or via HA UI: Settings → System → Restart

TROUBLESHOOTING
---------------
  Meter screen blank:
    → Check mains is live at terminals 1 and 4
    → Check wire is properly clamped in terminal screws

  Sensors show "unavailable" in HA:
    → Check Waveshare is reachable: ping 192.168.0.22
    → Check Modbus: telnet 192.168.0.22 502
    → SSH into HA and check: grep modbus /config/home-assistant.log

  MQTT sensors stale (MQTT bridge stopped):
    → ssh akaw@192.168.0.17
    → systemctl --user restart eastron_bridge

  Modbus sensors disappeared after HA restart:
    → SSH into HA: ssh hassio@192.168.0.4
    → Check: cat /config/configuration.yaml (must contain: modbus: !include modbus_eastron.yaml)
    → Check: head -3 /config/modbus_eastron.yaml (must start with: - name:  NOT with modbus:)

================================================================================
