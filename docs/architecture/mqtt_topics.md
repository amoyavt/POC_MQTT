# F2 Smart Controller MQTT Topics

This document details the MQTT topic structure and payload formats for the F2 Smart Controller devices.

## MQTT Topic Structure

The MQTT broker receives messages with the following topic structure:

```
cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/<COMPONENT>
```

### Topic Structure Explanation

-   **`cmnd`**: The root of the command topic tree.
-   **`f2-<MAC_ADDR>`**: The unique identifier for the F2 Smart Controller, using its MAC address.
-   **`<MODE>`**: The operational mode of the connector. Examples include:
    -   `access-control-mode`
    -   `alarm-mode`
    -   `sensor-mode`
-   **`<CONNECTOR>`**: The physical connector on the F2 device (e.g., `J1`, `J2`, `J3`, `J4`).
-   **`<COMPONENT>`**: The specific component connected to the connector. Examples include:
    -   `strike-<N>`
    -   `door-sensors`
    -   `reader-<N>`
    -   `exit-buttons`
    -   `siren-<N>`
    -   `motion-sensor-<N>`
    -   `sensor-<N>`

## Payload Formats

The payload format varies depending on the component.

### JSON Payloads

For most components, the payload is a JSON object with a `timestamp` and a data field.

**Electric Strike Status:**

-   **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/strike-<N>`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "status": true/false}`

**Door Sensor Status:**

-   **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/door-sensors`
-   **Payload:** `{"timestamp": "2023-05-26 18:34:04.928538", "door-sensor-1": false, "door-sensor-2": true}`

**QR/NFC Reader Data:**

-   **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/reader-<N>`
-   **Payload:** `{"timestamp": "2023-05-26 17:24:28.808888", "data": "b'\"Hello World\"'"}`

### Hexadecimal Payloads

For RS-485 sensors, the payload is a JSON object containing a hexadecimal string.

**RS-485 Sensor Data:**

-   **Topic:** `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/sensor-<N>`
-   **Payload:** `{"timestamp": "2023-05-25 15:13:10.543400", "data": "<hex value>"}`
-   **Example Hex Value:** `"01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"`

## Data Processing

The raw data from the MQTT messages is processed by the `Data Processor` service. This service uses the information in the topic and the payload, along with device parameters stored in a PostgreSQL database, to decode the data into meaningful measurements.

### Decoding Process

1.  **Data Extraction**: The `Data Processor` uses the `Offset` and `Length` from the `DataPoint` table to extract the relevant hexadecimal data from the payload.
2.  **Data Decoding**: The extracted data is decoded based on the `DataFormat` (`Int16`, `Uint16`, etc.) specified in the `DataPoint` table.
3.  **Data Storage**: The decoded value is stored in the `iot_measurements` table in TimescaleDB.