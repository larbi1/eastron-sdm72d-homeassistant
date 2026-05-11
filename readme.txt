================================================================================
  EASTRON SDM72D-M → HOME ASSISTANT — COMPLETE SETUP GUIDE
================================================================================

HARDWARE REQUIRED
-----------------
  Eastron SDM72D-M-2        3-phase energy meter (direct connection, up to 100A)
  Waveshare 8-CH RS485      RS485-to-Ethernet gateway
    TO POE ETH (B)

WHAT YOU NEED
-------------
  - Home Assistant instance (2023.x or newer) on your network
  - A Linux/Mac machine with bash, curl, and python3 on the same network as HA
    (python3 is used only as a WebSocket transport — all logic is in bash)
  - SSH client

FILES IN THIS REPOSITORY
-------------------------
  deploy_dashboard.sh         Run this to push the Lovelace dashboard to HA
  dashboard.json              Dashboard definition (4 views, all cards)
  modbus_eastron.yaml         Modbus sensor config — copy this to HA /config/
  eastron_mqtt_bridge.py      Optional MQTT bridge (secondary data path)
  eastron_bridge.service      Systemd service for the MQTT bridge
  lovelace_eastron.yaml       Dashboard reference YAML (informational only)
  configuration_addition.yaml Shows what line to add to configuration.yaml
  eastron_sdm72dmv2.pdf       Eastron SDM72D-M-2 user manual
  readme.txt                  This file


================================================================================
  STEP 1 — CONFIGURE THE WAVESHARE RS485-TO-ETH GATEWAY
================================================================================

The Waveshare 8-CH RS485 TO POE ETH (B) has 8 independent RS485 channels.
Connect your Eastron meter to channel 1 (or any channel — just note which one).

  1a. Find the gateway IP
      Look in your router's DHCP client list, or scan your subnet:
        nmap -sn 192.168.1.0/24   (replace with your subnet)
      The gateway shows up with vendor "Waveshare" or similar.

  1b. Open the web interface
      Navigate to http://<gateway-ip> in a browser.
      Default: no username/password required.

  1c. Configure the channel connected to the Eastron meter
      Find the channel settings for the port you wired to (e.g. "UART1"):
        Work Mode:    Modbus TCP to RTU
        Local Port:   502
        Baud Rate:    9600
        Data Bits:    8
        Stop Bits:    1
        Parity:       None
      Save and reboot the gateway if prompted.

  1d. Verify the port is open
        telnet <gateway-ip> 502
      If it connects (blank screen), press Ctrl+] then type quit.
      If it says "Connection refused", recheck the Work Mode setting.


================================================================================
  STEP 2 — WIRE THE EASTRON METER
================================================================================

  RS485 communication (to Waveshare):
    Eastron terminal A+  →  Waveshare channel terminal A
    Eastron terminal B-  →  Waveshare channel terminal B

  Power and measurement (1-phase 2-wire — page 11 of Eastron manual):
    Mains phase (L)   →  Eastron terminal 1  (top-left)
    Mains neutral (N) →  Eastron terminal 4  (top-right)
    Load phase out    →  Eastron terminal 5  (bottom-left)
    Load neutral out  →  Eastron terminal 8  (bottom-right)

  How it works:
    Terminals 1+4 power the meter and measure voltage.
    Current is measured by current flowing THROUGH the meter: in at 1+4, out at 5+8.
    Wire your load between terminals 5+8 and the rest of your circuit.
    If nothing is connected to terminals 5+8, current and power will read 0. Normal.

  After powering on, the Eastron screen should show "00000.00" (energy counter).
  If the screen is blank, check that mains is connected and screws are tight.


================================================================================
  STEP 3 — INSTALL MOSQUITTO MQTT BROKER IN HOME ASSISTANT
================================================================================

  The primary data path (Modbus YAML, Step 5) does NOT need MQTT.
  Only do this step if you also want the MQTT bridge (Step 7) running.

  3a. In HA: Settings → Add-ons → Add-on Store
      Search "Mosquitto broker" → Install

  3b. Start and enable
      Click Start → toggle "Start on boot" and "Watchdog" on → Start

  3c. Create an MQTT user
      HA's Mosquitto uses HA user accounts.
      Settings → People → Users → Add User
      Example: username "mqtt", password "yourpassword"
      Note these — you will need them in Step 7.

  3d. Add the MQTT integration (if HA does not auto-detect it)
      Settings → Devices & Services → Add Integration → MQTT
      Host: localhost  Port: 1883  Username/Password: as created above


================================================================================
  STEP 4 — SET UP SSH ACCESS TO HOME ASSISTANT
================================================================================

  You need SSH to copy modbus_eastron.yaml onto the HA filesystem and to
  edit configuration.yaml. This step only needs to be done once.

  4a. Install the SSH addon
      Settings → Add-ons → Add-on Store
      Search "Advanced SSH & Web Terminal" → Install

  4b. Configure key-based authentication (recommended)
      On your machine, generate a key if you don't have one:
        ssh-keygen -t ed25519
      Copy your public key:
        cat ~/.ssh/id_ed25519.pub
      In HA: Settings → Add-ons → Advanced SSH → Configuration tab
      Add your key:
        authorized_keys:
          - "ssh-ed25519 AAAA... you@yourmachine"
      Click Save.

      Alternatively, set a password in the same Configuration tab:
        password: "yourpassword"

  4c. Start and enable the addon
      Click Start → enable "Start on boot" and "Watchdog"

  4d. Connect
        ssh hassio@<HA_IP>
      Username is always "hassio" — not your HA login name, not "root".
      Port is 22 (default, no need to specify).

  NOTE: If you have an existing SSH key at ~/.ssh/id_ed25519, it will be
  used automatically. If you generated it just now, you may need to run:
    ssh-add ~/.ssh/id_ed25519


================================================================================
  STEP 5 — DEPLOY MODBUS SENSOR CONFIG TO HOME ASSISTANT
================================================================================

  This step creates 34 sensor entities in HA that poll the Eastron meter
  every 30 seconds (60 seconds for energy counters).

  5a. Edit modbus_eastron.yaml
      Open the file and change the host IP on line 4 to your Waveshare
      channel's IP address:
        host: 192.168.0.22    ← replace with your gateway IP

      If you used a channel other than channel 1, or changed the Modbus
      slave address on the meter, also update:
        slave: 1              ← must match the meter's Modbus address (default: 1)

  5b. Copy the file to Home Assistant
      From your machine:
        scp modbus_eastron.yaml hassio@<HA_IP>:/config/modbus_eastron.yaml

  5c. Add the include line to configuration.yaml
        ssh hassio@<HA_IP>
        nano /config/configuration.yaml

      Add this line (anywhere at the root level):
        modbus: !include modbus_eastron.yaml

      Save (Ctrl+O, Enter) and exit (Ctrl+X).

      IMPORTANT: The modbus_eastron.yaml file must NOT start with "modbus:".
      It must start with: - name: "eastron_sdm72dm"
      (The modbus: key comes from configuration.yaml via !include.)

  5d. Restart Home Assistant
        ha core restart

      Or via the HA UI: Settings → System → Restart → Restart Home Assistant
      HA will be unavailable for about 30–60 seconds during restart.

  5e. Verify sensors are live
      Settings → Devices & Services → Entities → search "sdm72d"
      You should see 34 entities. Within 30 seconds they will all show values.
      Expected: L1 voltage ~230V, frequency ~50Hz, L2/L3 voltage = 0V (if 1-phase).


================================================================================
  STEP 6 — DEPLOY THE LOVELACE DASHBOARD
================================================================================

  Run deploy_dashboard.sh from any machine on the same network as HA.
  Requirements: bash, curl, python3 (standard on any Linux/Mac).

  6a. Edit deploy_dashboard.sh
      Open the file and set the three variables at the top:
        HA_HOST="192.168.0.4"    ← your HA IP address
        HA_USER="admin"          ← your HA username (for the UI login)
        HA_PASS="yourpassword"   ← your HA password

  6b. Run the script
        bash deploy_dashboard.sh

      Successful output ends with:
        Dashboard deployed successfully.
        Open: http://<HA_IP>:8123/lovelace

  NOTE: dashboard.json must be in the same directory as deploy_dashboard.sh.
  To change the dashboard layout, edit dashboard.json directly.

  6c. Open the dashboard
        http://<HA_IP>:8123/lovelace

      You will see 4 tabs:
        Overview       Gauge dials (voltage, frequency, power, current, PF)
                       + system totals list + averages
        Per Phase      Per-phase gauge dials (voltage, current) + glance cards
                       for L-L voltages, power, reactive power, power factor
        Energy History Import/export statistics + 24h voltage and current graphs
        Statistics     Daily/monthly bar charts for energy and power


================================================================================
  STEP 7 — INSTALL THE MQTT BRIDGE SERVICE (OPTIONAL)
================================================================================

  The MQTT bridge is a secondary/backup data path. The Modbus sensors from
  Step 5 are the primary method. Only set this up if you want redundancy or
  cannot use the Modbus YAML approach.

  The bridge script runs on any Linux machine and polls the meter via Modbus
  TCP, then publishes values to Mosquitto on HA. HA creates MQTT sensors
  automatically via MQTT auto-discovery.

  7a. Edit eastron_mqtt_bridge.py
      Set these variables at the top of the file:
        MODBUS_HOST = "192.168.0.22"   ← your Waveshare channel IP
        MQTT_HOST   = "192.168.0.4"    ← your HA IP
        MQTT_USER   = "mqtt"           ← MQTT username (from Step 3)
        MQTT_PASS   = "yourpassword"   ← MQTT password

  7b. Edit eastron_bridge.service
      Change the ExecStart path to where you put the script:
        ExecStart=/usr/bin/python3 /path/to/eastron_mqtt_bridge.py

  7c. Copy both files to the machine that will run the bridge
      (e.g. your Debian VM, Raspberry Pi, or any always-on Linux machine)

  7d. Install the systemd user service
        mkdir -p ~/.config/systemd/user/
        cp eastron_bridge.service ~/.config/systemd/user/
        systemctl --user daemon-reload
        systemctl --user enable eastron_bridge
        systemctl --user start eastron_bridge

  7e. Enable auto-start on boot (without needing to log in first)
        sudo loginctl enable-linger $USER

  7f. Check it is running
        systemctl --user status eastron_bridge
        journalctl --user -u eastron_bridge -f   (live log, Ctrl+C to exit)

  MQTT sensor entity IDs are different from the Modbus ones:
    sensor.eastron_sdm72d_m_sdm72d_l1_voltage  (MQTT)
    sensor.sdm72d_l1_voltage                   (Modbus — primary, used by dashboard)


================================================================================
  SENSOR REFERENCE — ALL 34 ENTITIES
================================================================================

  After setup, these entity IDs are available in Home Assistant:

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


================================================================================
  EXPECTED VALUES — 1-PHASE CONNECTION ON L1
================================================================================

  L1 voltage:         ~230–240 V
  L2, L3 voltage:     0 V   (not connected — normal for single-phase use)
  Frequency:          ~50 Hz
  Avg L-N voltage:    ~79 V  (= L1/3, because L2+L3 are 0 — expected)
  Avg L-L voltage:    ~159 V (same reason — expected)
  Current/Power:      0 if no load is wired through terminals 5+8


================================================================================
  GAUGE CARD COLOUR ZONES
================================================================================

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


================================================================================
  STATISTICS-GRAPH CARDS
================================================================================

  HA automatically stores hourly statistics for every sensor with a state_class.
  No extra addon is needed. Data accumulates from the moment sensors are created.

  The Statistics view has 5 cards. Each card has a period selector (top-right
  corner) to switch between: hour / day / week / month / year.

  Card                        Default period  stat_types       Sensors
  ─────────────────────────── ─────────────── ──────────────── ─────────────────
  Energy Import / Export      month           sum              import, export
  Total Active Energy         month           sum              total_active_energy
  Total Active Power          day             mean, max        total_active_power
  Per-Phase Active Power      day             mean             l1/l2/l3_active_power
  Per-Phase Voltage           day             mean, min, max   l1/l2/l3_voltage

  NOTE: HA does not backfill statistics. There is no data before the sensors
        were first created. Energy counters accumulate from day one.


================================================================================
  ADDING MORE EASTRON METERS
================================================================================

  SCENARIO A — Multiple meters on the SAME RS485 bus / Waveshare channel
  -----------------------------------------------------------------------
  Each meter must have a unique Modbus slave address.
  The factory default for all Eastron meters is slave address 1.
  Change each additional meter's address via its front panel buttons before
  wiring them together on the same A/B bus.

  In modbus_eastron.yaml, add a second hub block with slave: 2:

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

  Entity IDs: sensor.m2_l1_voltage, sensor.m2_l2_voltage, etc.


  SCENARIO B — Multiple meters on DIFFERENT Waveshare channels
  ------------------------------------------------------------
  Each meter connects to its own Waveshare channel (its own IP).
  All meters can keep slave address 1.

  In modbus_eastron.yaml, add a hub block for each new channel IP:

  - name: "eastron_ch2"
    type: tcp
    host: 192.168.0.31        # Waveshare CH2 IP
    port: 502
    sensors:
      - name: "CH2 L1 Voltage"
        unique_id: ch2_sdm72d_l1_voltage
        slave: 1
        address: 0
        input_type: input
        data_type: float32
        unit_of_measurement: "V"
        device_class: voltage
        state_class: measurement
        scan_interval: 30
      # ... all 34 registers

  Entity IDs: sensor.ch2_l1_voltage, sensor.ch2_l2_voltage, etc.

  RULES:
    - unique_id must be globally unique — use a clear prefix per meter
    - After editing the YAML, restart HA to apply the changes


================================================================================
  TROUBLESHOOTING
================================================================================

  Meter screen is blank
    → Mains circuit feeding terminals 1+4 is not live (check breaker)
    → Terminal screws are loose — re-insert wire and tighten firmly

  Sensors show "unavailable" in HA
    → Check Waveshare is reachable:  ping <gateway-ip>
    → Check Modbus port is open:     telnet <gateway-ip> 502
    → SSH into HA and check logs:    grep -i modbus /config/home-assistant.log
    → Verify YAML include is correct: cat /config/configuration.yaml

  Sensors disappeared after HA restart
    → SSH into HA: ssh hassio@<HA_IP>
    → Check: cat /config/configuration.yaml
             (must contain: modbus: !include modbus_eastron.yaml)
    → Check: head -3 /config/modbus_eastron.yaml
             (must start with: - name:   NOT with: modbus:)

  deploy_dashboard.py fails with "Auth failed"
    → Double-check HA_HOST, HA_USER, HA_PASS in the script
    → Make sure HA is reachable: ping <HA_IP>
    → Try opening http://<HA_IP>:8123 in a browser first

  MQTT bridge is not running
    → ssh <bridge-machine>
    → systemctl --user restart eastron_bridge
    → journalctl --user -u eastron_bridge -f

================================================================================
