# FACES2 Controller MQTT Topics

This document details the MQTT topic structure and payload formats for the FACES2 Controller devices based on the official documentation.

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

- **`<TOPIC_TYPE>`**: The topic type prefix:
  - `cmnd`: Command topics for device control
  - `stat`: Status topics for device state and sensor readings
  - `tele`: Telemetry topics for diagnostic data and events
- **`f2-<MAC_ADDR>`**: The unique identifier for the F2 Smart Controller, using its MAC address (lowercase, without ":").
- **`<MODE>`**: The operational mode of the connector. Examples include:
  - `access-control-mode`
  - `alarm-mode`
  - `sensor-mode`
- **`<CONNECTOR>`**: The physical connector on the F2 device (J1, J2, J3, J4).
- **`<COMPONENT>`**: The specific component connected to the connector.

## Access Control Mode

### Electric Strike 1 and Electric Strike 2

**Subscribe (Command)**
- **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/strike-<N>`
- **Description:** Command to control the door access controller
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: access-control-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)
  - `<N>`: The identifier of the electric strike (1 or 2)

**Payload:**
```json
{
  "power-flag": 2,
  "period": 3
}
```

- **power-flag:**
  - 2: Toggle for <period> seconds
  - 1: Powered (12V)
  - 0: No powered (0V)
- **period:** Time in seconds (max value 255, recommended max 120)
- **None:** Without payload returns current status in stat topic

**Example:** `cmnd/f2-e4fd45f654be/access-control-mode/J2/strike-1`

**Publish (Status)**
- **Topic:** `stat/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/strike-<N>`
- **Description:** Return the current status of the electric strike
- **Payload:**
```json
{
  "timestamp": "2023-05-26 18:34:04.928538",
  "status": true
}
```

**Example:** `stat/f2-e4fd45f654be/access-control-mode/J2/strike-1`

### Door Sensors

**Publish (Status)**
- **Topic:** `stat/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/door-sensors`
- **Description:** Publish door sensor's status. Updates every time the status changes.
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: access-control-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)

**Payload:**
```json
{
  "timestamp": "2023-05-26 18:34:04.928538",
  "door-sensor-1": false,
  "door-sensor-2": true
}
```

**Example:** `stat/f2-e4fd45f654be/access-control-mode/J2/door-sensors`

### QR Code and NFC Reader

**Subscribe (Command)**
- **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/reader-<N>/success`
- **Description:** Command to activate the light indicators of the reader (feedback to user)
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: access-control-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)
  - `<N>`: The identifier of the reader (1 or 2)

**Payload:**
- 1: Success
- 2: Fail 1
- 3: Fail 2

**Example:** `cmnd/f2-e4fd45f654be/access-control-mode/J2/reader-1/success`

**Publish (Telemetry)**
- **Topic:** `tele/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/reader-<N>`
- **Description:** Publish the string data of the QR code or NFC token (max 1023 characters)
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: access-control-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)
  - `<N>`: The identifier of the reader (1 or 2)

**Payload (QR/NFC Data):**
```json
{
  "timestamp": "2023-05-26 17:24:28.808888",
  "data": "b'\"Hello World\"'"
}
```

**Payload (Light Indicator Response):**
```json
{
  "timestamp": "2023-05-26 17:20:52.115179",
  "data": "b'\\x02\\x02\\x01\\x00\\x00\\x00\\x03\\x03'"
}
```

**Example:** `tele/f2-e4fd45f654be/access-control-mode/J2/reader-1`

### Exit Buttons

**Publish (Status)**
- **Topic:** `stat/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/exit-buttons`
- **Description:** Publish status of both exit buttons when pressed. Updates every time status changes.
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: access-control-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)

**Payload:**
```json
{
  "timestamp": "2023-05-26 17:17:09.127331",
  "exit-button-1": false,
  "exit-button-2": false
}
```

**Example:** `stat/f2-e4fd45f654be/access-control-mode/J2/exit-buttons`

**Note:** Should be a tele topic but for practical purposes, it's considered a stat topic.

## Alarm Mode

### Sirens

**Subscribe (Command)**
- **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/siren-<N>`
- **Description:** Command to control sirens (turn on/off) or request status if payload is null
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: alarm-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)
  - `<N>`: The identifier of the siren (1 or 2)

**Payload:**
- 1: Powered (12V)
- 0: No powered (0V)
- None: Return current status in published topic

**Example:** `cmnd/f2-e4fd45f654be/alarm-mode/J1/siren-1`

**Publish (Status)**
- **Topic:** `stat/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/siren-<N>`
- **Description:** Return the current status of a siren
- **Payload:**
```json
{
  "timestamp": "2023-05-26 18:34:04.928538",
  "status": false
}
```

**Example:** `stat/f2-e4fd45f654be/alarm-mode/J1/siren-1`

**Note:** Active only per request.

### Motion Sensors

**Publish (Status)**
- **Topic:** `stat/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/motion-sensor-<N>`
- **Description:** Return the status of a motion sensor. Updates every time status changes (person detected).
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: alarm-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)
  - `<N>`: ID of the sensor (1, 2, 3, 4, and 5)

**Payload:**
```json
{
  "timestamp": "2023-05-26 18:34:04.928538",
  "status": true
}
```

**Example:** `stat/f2-e4fd45f654be/alarm-mode/J1/motion-sensor-1`

**Note:** Publish only when status changes.

## Sensor Mode

### RS-485 Sensors

**Publish (Telemetry)**
- **Topic:** `tele/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/sensor-<N>`
- **Description:** Publish raw sensor data (hex) periodically (every 30 seconds, not configurable)
- **Fields:**
  - `<MAC_ADDR>`: MAC address of the F2 device (eth0 interface), in lowercase and without ":"
  - `<MODE>`: sensor-mode
  - `<CONNECTOR>`: The connector on the F2 board (J1, J2, J3 and J4)
  - `<N>`: ID of the RS-485 sensor (1, ..., 6)

**Payload:**
```json
{
  "timestamp": "2023-05-25 15:13:10.543400",
  "data": "01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"
}
```

**Example:** `tele/f2-e4fd45f654be/sensor-mode/J4/sensor-3`

## Data Processing

The raw data from the MQTT messages is processed by the Stream Processor service. This service uses the information in the topic and the payload, along with device parameters stored in a PostgreSQL database, to decode the data into meaningful measurements.

### Decoding Process

1. **Data Extraction**: The Stream Processor uses the `Offset` and `Length` from the `DataPoint` table to extract the relevant hexadecimal data from the payload.
2. **Data Decoding**: The extracted data is decoded based on the `DataEncoding` (`Int16`, `Uint16`, etc.) specified in the `DataPoint` table.
3. **Data Storage**: The decoded value is stored in the `decoded_data` table in TimescaleDB.

### MAC Address Format

- All MAC addresses in topics are lowercase and without colons
- Example: `e4fd45f654be` (instead of `E4:FD:45:F6:54:BE`)

### Topic Subscription Patterns

The MQTT-Kafka connector subscribes to the following patterns:
- `stat/+/+/+/+` (all status topics)
- `tele/+/+/+/+` (all telemetry topics)

Command topics are typically used for device control and are not processed by the data pipeline.
