# F2 Smart Controller MQTT Topics

This document details the MQTT topic structure and payload formats for the F2 Smart Controller devices.

## MQTT Topic Structure

The MQTT broker receives messages with three different topic types:

### Topic Types

1. **Command Topics** (`cmnd`): Used for sending commands to devices
2. **Status Topics** (`stat`): Used for device status updates and sensor readings
3. **Telemetry Topics** (`tele`): Used for telemetry data and diagnostic information

### Topic Structure Pattern

```
<TOPIC_TYPE>/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/<COMPONENT>
```

### Topic Structure Explanation

-   **`<TOPIC_TYPE>`**: The topic type prefix:
    -   `cmnd`: Command topics for device control
    -   `stat`: Status topics for device state and sensor readings
    -   `tele`: Telemetry topics for diagnostic data and events
-   **`f2-<MAC_ADDR>`**: The unique identifier for the F2 Smart Controller, using its MAC address.
-   **`<MODE>`**: The operational mode of the connector. Examples include:
    -   `access-control-mode`
    -   `alarm-mode`
    -   `sensor-mode`
-   **`<CONNECTOR>`**: The physical connector number on the F2 device (e.g., `1`, `2`, `3`, `4`).
-   **`<COMPONENT>`**: The specific component connected to the connector. Examples include:
    -   `strike-<N>`
    -   `door-sensors`
    -   `reader-<N>`
    -   `exit-buttons`
    -   `siren-<N>`
    -   `motion-sensor-<N>`
    -   `sensor-<N>`

## Topics by Device Mode

All payloads are JSON objects with consistent structure containing:
- **`timestamp`**: ISO format timestamp (YYYY-MM-DD HH:MM:SS.ffffff)
- **Data fields**: Component-specific data fields with descriptive names

For RS-485 sensors, the payload contains a hexadecimal string representing raw sensor data that requires decoding based on device parameters.

### Sensor Mode Topics

**RS-485 Sensor Data:**
-   **Topic:** `cmnd/f2-<MAC_ADDR>/sensor-mode/<CONNECTOR>/sensor-<N>`
-   **Payload:** `{"timestamp": "2023-05-25 15:13:10.543400", "data": "<hex value>"}`
-   **Example Hex Value:** `"01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"`

### Access Control Mode Topics

**Electric Strike Status:**
-   **Topic:** `stat/f2-<MAC_ADDR>/access-control-mode/<CONNECTOR>/strike-<N>`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "state": "locked", "voltage": 12.1, "current": 1.5}`

**Door Sensor Status:**
-   **Topic:** `stat/f2-<MAC_ADDR>/access-control-mode/<CONNECTOR>/door-sensors`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "door_1": "open", "door_2": "closed", "tamper": false}`

**QR/NFC Reader Data:**
-   **Topic:** `tele/f2-<MAC_ADDR>/access-control-mode/<CONNECTOR>/reader-<N>`
-   **Payload:** `{"timestamp": "2023-05-26 17:24:28.808888", "card_id": "A1B2C3D4", "read_type": "nfc", "signal_strength": 85}`

**Exit Button Status:**
-   **Topic:** `stat/f2-<MAC_ADDR>/access-control-mode/<CONNECTOR>/exit-buttons`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "button_pressed": true, "button_id": 2}`

### Alarm Mode Topics

**Motion Sensor Status:**
-   **Topic:** `stat/f2-<MAC_ADDR>/alarm-mode/<CONNECTOR>/motion-sensor-<N>`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "motion_detected": true, "sensitivity": 7, "zone": "zone_1"}`

**Siren Status:**
-   **Topic:** `stat/f2-<MAC_ADDR>/alarm-mode/<CONNECTOR>/siren-<N>`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "state": "active", "volume": 95, "pattern": "pulsing"}`

## Data Processing

The raw data from the MQTT messages is processed by the `Data Processor` service. This service uses the information in the topic and the payload, along with device parameters stored in a PostgreSQL database, to decode the data into meaningful measurements.

### Decoding Process

1.  **Data Extraction**: The `Data Processor` uses the `Offset` and `Length` from the `DataPoint` table to extract the relevant hexadecimal data from the payload.
2.  **Data Decoding**: The extracted data is decoded based on the `DataEncoding` (`Int16`, `Uint16`, etc.) specified in the `DataPoint` table.
3.  **Data Storage**: The decoded value is stored in the `iot_measurements` table in TimescaleDB.