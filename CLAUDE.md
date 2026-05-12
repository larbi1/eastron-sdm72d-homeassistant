# Eastron SDM72D-M — Home Assistant Integration

## Project

Eastron SDM72D-M-2 energy meter connected via Waveshare 8-CH RS485 TO POE ETH (B) gateway to Home Assistant.
GitHub: https://github.com/larbi1/eastron-sdm72d-homeassistant

## Network

| Device | IP | Notes |
|---|---|---|
| Home Assistant | 192.168.0.4:8123 | user: sahel / sahel15 |
| Waveshare RS485-1 (Eastron) | 192.168.0.22:502 | Modbus TCP→RTU, 9600 8N1 |
| This machine | 192.168.0.17 | runs eastron_bridge systemd service |

## Git Workflow

After every change to files in this project, always commit and push to GitHub without being asked. Use a concise commit message. Author: `git -c user.email="testappsandro@gmail.com" -c user.name="larbi1"`.

## Key Files

- `modbus_eastron.yaml` — deployed to HA `/config/`, included via `modbus: !include modbus_eastron.yaml`
- `dashboard.json` — Lovelace dashboard definition (4 views)
- `deploy_dashboard.sh` / `deploy_dashboard.py` — push dashboard to HA via WebSocket
- `eastron_mqtt_bridge.py` — MQTT bridge service running on 192.168.0.17
- `eastron_bridge.service` — systemd user service (`systemctl --user`)

## SSH Access

```bash
ssh hassio@192.168.0.4     # Home Assistant (username: hassio)
ssh akaw@192.168.0.17      # Bridge machine
```
