# FACES2 Controller Services (Jetson Side)

This document outlines the services running on the FACES2 Controller (Jetson device), focusing on the **Physical Interaction Python Code** and MQTT topic structure.

---

## 🧩 Services Overview

The controller runs a set of modular services to handle:

- Device control via GPIO/NFC/QR/Sensors
- MQTT message handling
- Authorization decisions
- Schedule enforcement
- Cloud data syncing
- Local and remote telemetry processing

---

## 1. 🔌 MQTT Client Bridge Service (Physical Interaction Python Code)

**Responsibility**: Interfaces with physical hardware and communicates via MQTT.

### ✅ Features:
- Subscribes to `cmnd/` topics to receive commands.
- Publishes to:
  - `stat/` for status (e.g., door sensors, strikes)
  - `tele/` for QR/NFC reads and sensor telemetry
- Converts MQTT messages to hardware I/O and vice versa.

### 🧱 Modules:
- `mqtt_listener.py` – handles MQTT subscriptions
- `gpio_control.py` – toggles GPIO for strikes, sirens, lights
- `reader_listener.py` – handles QR/NFC inputs
- `sensor_monitor.py` – monitors door/motion sensors, buttons

---

## 2. 🔐 Authorization Service

**Responsibility**: Decides if access should be granted based on local data.

- Inputs: QR/NFC event, timestamp, device info
- Checks local CouchDB (`users`, `policies`, `schedules`)
- If valid:
  - Publishes MQTT command: `cmnd/.../strike-1`
  - Publishes reader light feedback: `cmnd/.../reader-1/success`

---

## 3. ⏰ Schedule Service

**Responsibility**: Time-based access control validation.

- Reads schedule data from CouchDB
- Used by Authorization Service for temporal rules

---

## 4. 📩 Tablet Service

**Responsibility**: Communicates with the tablet (if present).

- REST or WebSocket interface
- Sends feedback to UI
- May receive face scan results

---

## 5. 🔄 Sync DB Service

**Responsibility**: Pulls data from the cloud and updates CouchDB.

- Triggered on boot and periodically
- Authenticates via MAC or token
- Uses `_bulk_docs` to push schedules, policies, users

---

## 6. 🧪 Raw Data Processor

**Responsibility**: Normalizes MQTT telemetry into meaningful data.

- Parses messages like `tele/.../sensor-3`
- Maps to device configuration from CouchDB
- Publishes internal events to Kafka or Timeseries

---

## 7. 🗃 Processed Data Sink

**Responsibility**: Stores parsed data locally and forwards to cloud.

- Local options: SQLite, InfluxDB, Timescale
- Cloud forwarding via Kafka, HTTP, or MQTT

---

## 8. 📈 Monitoring Service

**Responsibility**: Reports device health and diagnostics.

- Publishes to `metrics/device/<mac>`
- Tracks:
  - Uptime
  - MQTT connectivity
  - Sync failures
  - GPIO issues

---

## 🔐 MQTT Topic Flow Summary

| Event                    | Topic Pattern                                        | Handled By           |
|--------------------------|------------------------------------------------------|-----------------------|
| Open Strike              | `cmnd/.../strike-1`                                  | `gpio_control.py`     |
| Strike Status            | `stat/.../strike-1`                                  | `gpio_control.py`     |
| QR/NFC Read              | `tele/.../reader-1`                                  | `reader_listener.py`  |
| Reader Feedback Light    | `cmnd/.../reader-1/success`                          | `gpio_control.py`     |
| Door Sensor              | `stat/.../door-sensors`                              | `sensor_monitor.py`   |
| Exit Buttons             | `stat/.../exit-buttons`                              | `sensor_monitor.py`   |
| Siren Activation         | `cmnd/.../siren-1`                                   | `gpio_control.py`     |
| Motion Detection         | `stat/.../motion-sensor-1`                           | `sensor_monitor.py`   |
| RS-485 Sensor Data       | `tele/.../sensor-3`                                  | `sensor_monitor.py`   |

---

## 💡 Suggested Container Layout

| Service                  | Container Name             | Language      |
|--------------------------|----------------------------|---------------|
| Physical Interaction     | `faces2-phy-interaction`   | Python        |
| Authorization            | `faces2-auth-service`      | Python/.NET   |
| Schedule Validation      | `faces2-schedule-service`  | Python        |
| Sync Service             | `faces2-sync-service`      | Python/Node   |
| Raw Processor            | `faces2-raw-parser`        | Python        |
| Data Sink                | `faces2-sink`              | Python        |
| CouchDB Local Store      | `couchdb:3`                | —             |
| Monitoring               | `faces2-monitor`           | Python        |

---

## ✅ Summary

This modular architecture enables:

- Offline-capable, secure access control
- Local enforcement of policies
- MQTT-based hardware interaction
- Periodic sync of device-specific data
- Seamless telemetry integration with Timescale or Kafka

---

