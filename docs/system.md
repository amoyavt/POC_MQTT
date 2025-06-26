# IoT Data Processing and Storage Architecture for F2 Smart Controllers

This document outlines a robust, scalable, and real-time architecture for ingesting, processing, and storing data from F2 Smart Controller IoT devices. The system is designed to transform raw, device-specific MQTT messages into meaningful, decoded data, optimized for time-series analysis.

## Implementation Status

✅ **COMPLETED** - This architecture has been fully implemented as a containerized proof-of-concept using Python microservices with comprehensive monitoring and health checking capabilities.

### Key Implementation Features
- **Containerized Architecture**: All components run in Docker containers with Docker Compose orchestration
- **Python Microservices**: Custom Python services replace Kafka Connect components for flexibility
- **Comprehensive Monitoring**: Prometheus, Grafana, and custom health monitoring APIs
- **Production-Ready**: Includes error handling, batching, health checks, and observability

## Overall Vision

To ingest raw data from a multitude of F2 Smart Controller IoT devices, process it in real-time by enriching it with device-specific parameters (including connector mode, sensor type, and identifier), and then store the decoded, meaningful data in a time-series optimized database for analysis and querying.

## Detailed Components and Data Flow

### 1. F2 Smart Controller IoT Devices

* **Function:** These are edge devices (F2-212, F2-403, F2-401, F2-214, F2-215, F2-213, F2-301) responsible for collecting various types of raw data, including electric strike status, door sensor status, QR code/NFC reader data, exit button status, siren status, motion sensor status, and RS-485 sensor data. They also receive commands for electric strikes, QR/NFC reader indicators, and sirens.
* **Communication:** They publish this raw, often compact or binary, data as MQTT messages.
* **Topic Convention:** Messages are sent to well-defined MQTT topic structures, which include the MAC address of the F2 device, the connector mode (e.g., `access-control-mode`, `alarm-mode`, `sensor-mode`), the specific connector (J1, J2, J3, J4), and an identifier for the sensor/component.
    * **Examples of Publish Topics:**
        * Electric Strike Status: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/strike-<N>` 
        * Door Sensors Status: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/door-sensors` 
        * QR code and NFC reader data: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/reader-<N>` 
        * Exit Buttons Status: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/exit-buttons` 
        * Sirens Status: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/siren-<N>` 
        * Motion Sensors Status: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/motion-sensor-<N>` 
        * RS-485 sensors raw data: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/sensor-<N>` 
    * **Example Payloads:**
        * Electric Strike Status: `{"timestamp": "2023-05-26 18:34:04.928538", "status": true/false}` 
        * Door Sensor Status: `{"timestamp": "2023-05-26 18:34:04.928538", "door-sensor-1": false, "door-sensor-2": true}` 
        * QR/NFC Reader Data: `{"timestamp": "2023-05-26 17:24:28.808888", "data": "b'\"Hello World\"'"}` 
        * RS-485 Sensor Data: `{"timestamp": "2023-05-25 15:13:10.543400", "data": <hex value>}` 

### 2. MQTT Broker (Mosquitto)

* **Function:** Acts as the central message hub for all incoming F2 Smart Controller data.
* **Role:** Receives all MQTT messages from F2 Smart Controller devices across the `cmnd` topics. It efficiently handles message routing and delivery to authorized subscribers. Mosquitto provides the initial, reliable entry point for your massive influx of F2 device data.

### 3. MQTT-Kafka Connector Service (Python Microservice)

* **Implementation:** Custom Python service using `paho-mqtt` and `kafka-python` libraries
* **Function:** Bridges the gap between Mosquitto MQTT broker and Apache Kafka
* **Configuration:** Connects to Mosquitto broker and subscribes to pattern `cmnd/f2-#` to capture all F2 Smart Controller command messages
* **Data Transformation:** The service performs critical transformations:
    * Extracts the `f2-<MAC_ADDR>` part from MQTT topic and sets it as Kafka record key (serves as unique `deviceid`)
    * Maps raw MQTT payload to Kafka record value
    * Includes the full MQTT topic path in the Kafka record for downstream processing
    * Adds processing timestamp for tracking
* **Reliability:** Implements "at least once" delivery semantics with error handling and logging
* **Containerized:** Runs as Docker container with automatic restart capabilities

### 4. Apache Kafka (Reliable Message Queue)

* **Implementation:** Confluent Kafka with Zookeeper in containerized setup
* **Topic: `raw_iot_data`** - Stores raw MQTT messages from F2 devices
* **Topic: `decoded_iot_data`** - Stores processed and enriched IoT data
* **Function:** Central, high-throughput, and durable stream storage for all F2 Smart Controller messages
* **Role:** Acts as buffer and persistent log with automatic topic creation and configurable retention

### 5. Device Parameters Store (PostgreSQL)

* **Function:** A robust relational database system used to store static or slowly changing metadata critical for decoding raw IoT data.
* **Schema:** It holds a table (e.g., `device_parameters`) with `device_id` (F2 MAC address) as the primary key. It will also require columns to specify the `sensor_type` or `component_identifier` (e.g., `door-sensors`, `strike-1`, `siren-2`, `motion-sensor-1`, `reader-1`, `RS485-sensor-3`), `connector_mode` (e.g., `access-control-mode`, `alarm-mode`, `sensor-mode`), `scaling_factor`, `units`, `encoding_type`, and any other parameters needed for processing a specific device's raw data type.
    * **Example `device_parameters` entries:**
        | device\_id        | connector\_mode     | component\_type | component\_id | encoding\_type | units     | scaling\_factor |
        | :---------------- | :------------------ | :-------------- | :------------ | :------------- | :-------- | :-------------- |
        | f2-e4fd45f654be   | access-control-mode | door-sensors    | N/A           | boolean\_map   | state     | 1.0             |
        | f2-e4fd45f654be   | access-control-mode | strike          | 1             | boolean        | state     | 1.0             |
        | f2-e4fd45f654be   | sensor-mode         | RS485-sensor    | 3             | hex\_to\_float | celsius   | 0.1             |
        | f2-e4fd45f654be   | alarm-mode          | motion-sensor   | 1             | boolean        | presence  | 1.0             |
        | f2-e4fd45f654be   | access-control-mode | qr-nfc-reader   | 1             | raw\_string    | text      | 1.0             |

### 6. Data Processing Service (Python Microservice)

* **Implementation:** Custom Python service using `kafka-python` and `psycopg2` libraries
* **Function:** The brain of the processing pipeline - transforms raw IoT data into meaningful measurements
* **Consumption:** Consumes messages from `raw_iot_data` Kafka topic with configurable consumer groups
* **Processing Pipeline:** For each incoming raw data message:
    * Extracts `deviceid` (F2 MAC address) from Kafka record key
    * Parses MQTT topic structure to identify `connector_mode`, `connector_id`, and `component_type`
    * Performs database lookup against PostgreSQL `device_parameters` table using device metadata
    * **Decoding & Transformation:** Applies device-specific parameters:
        * **Encoding Types Supported:**
            * `boolean` - Simple true/false status values
            * `boolean_map` - Multi-sensor boolean mappings (door sensors, exit buttons)
            * `hex_to_float` - RS-485 sensor hex values converted to floating point with scaling
            * `raw_string` - QR/NFC reader text data processing
        * **Scaling & Units:** Applies scaling factors and unit conversions
        * **Enrichment:** Creates structured messages with timestamp, device info, decoded values, and metadata
    * **Error Handling:** Comprehensive error handling for missing parameters, malformed data, and database connectivity
* **Output:** Publishes enriched data to `decoded_iot_data` Kafka topic
* **Containerized:** Runs with automatic restart and configurable processing parameters

### 7. Kafka-TimescaleDB Sink Service (Python Microservice)

* **Implementation:** Custom Python service using `kafka-python` and `psycopg2` libraries
* **Function:** Consumes processed IoT data and writes to TimescaleDB for time-series storage
* **Consumption:** Reads from `decoded_iot_data` Kafka topic with configurable consumer groups
* **Batch Processing:** Implements efficient batch writing with configurable batch size and timeout
* **Data Mapping:** Transforms Kafka messages into TimescaleDB records with proper time-series structure
* **Performance:** Optimized for high-throughput writes with batch insertions and connection pooling
* **Reliability:** Includes error handling, retry logic, and dead letter queue concepts

### 8. Time-Series Data Storage (TimescaleDB)

* **Implementation:** TimescaleDB as PostgreSQL extension in containerized setup
* **Function:** Final destination for processed F2 Smart Controller IoT data with time-series optimization
* **Schema Features:**
    * **Hypertable:** `iot_measurements` table partitioned by time for optimal performance
    * **Columns:** `timestamp`, `device_id`, `connector_mode`, `component_type`, `pin_position`, `value`, `unit`, `topic`
    * **Indexes:** Optimized indexes on device_id, component_type, and time-based queries
    * **Continuous Aggregates:** Automated hourly statistics for performance
    * **Compression:** Optional data compression for older data
* **Analytics:** Supports complex time-series queries, aggregations, and trend analysis for F2 device metrics

### 9. F2 Device Simulator (Python Microservice)

* **Implementation:** Python simulation service for testing and development
* **Function:** Simulates multiple F2 Smart Controller devices publishing realistic MQTT data
* **Device Types:** Supports all F2 variants (F2-212, F2-403, F2-401, F2-214, F2-215, F2-213, F2-301)
* **Data Generation:** Creates realistic payloads for all component types:
    * Door sensors, electric strikes, exit buttons, motion sensors, sirens
    * QR/NFC readers with sample access card data
    * RS-485 sensors with hex-encoded temperature, humidity, and pressure data
* **Configurable:** Adjustable publishing intervals and device behaviors

### 10. Monitoring and Observability Stack

* **Health Monitor API (FastAPI):** Custom REST API for container and service health monitoring
* **Prometheus:** Metrics collection with custom metrics for IoT pipeline performance
* **Grafana:** Visual dashboards for system monitoring and IoT data analytics
* **cAdvisor:** Container resource monitoring and performance metrics
* **Node Exporter:** Host system metrics and resource utilization

## Implemented Data Flow Path

**F2 Smart Controller Devices** (Simulated) 
↓ *MQTT Messages*
**Mosquitto MQTT Broker** 
↓ *Python MQTT-Kafka Connector*
**Apache Kafka** (`raw_iot_data` topic) 
↓ *Python Data Processor* ← **PostgreSQL** (Device Parameters)
**Apache Kafka** (`decoded_iot_data` topic) 
↓ *Python Kafka-TimescaleDB Sink*
**TimescaleDB** (Time-series Storage)

## Production Deployment Features

* **Containerization:** All services containerized with Docker Compose orchestration
* **Health Monitoring:** Comprehensive health checks and monitoring APIs
* **Error Handling:** Robust error handling and logging throughout the pipeline
* **Scalability:** Services designed for horizontal scaling and high throughput
* **Observability:** Full metrics, logging, and monitoring stack included
* **Configuration:** Environment-based configuration with sensible defaults

This implementation provides a production-ready foundation that leverages the specific topic structures and payload types of the F2 Smart Controller to ensure accurate and meaningful data ingestion, processing, and storage with full operational visibility.

## Operational Commands

### Quick Start
```bash
# Complete setup with monitoring
make full-setup

# Check system status
make status

# Monitor health
make health
```

### System Management
```bash
# Stop everything cleanly
make clean

# Nuclear cleanup (for stuck containers)
make nuclear-clean

# Partial stops
make monitoring-down    # Stop monitoring only
docker-compose down     # Stop main services only
```

### Access Points
- **Grafana Dashboards**: http://localhost:3000 (admin/admin)
- **Prometheus Metrics**: http://localhost:9090
- **Health Monitor API**: http://localhost:8000
- **Container Metrics**: http://localhost:8080

### Development Commands
```bash
# View logs
make logs                    # All services
make logs-connector         # MQTT-Kafka connector
make logs-processor         # Data processor  
make logs-sink              # TimescaleDB sink
make logs-simulator         # Device simulator

# Database access
make db-params              # PostgreSQL device parameters
make db-timescale           # TimescaleDB time-series data

# Kafka monitoring
make kafka-topics           # List topics
make kafka-raw              # View raw IoT data
make kafka-decoded          # View processed data

# MQTT monitoring
make mqtt-monitor           # Subscribe to all F2 messages
```