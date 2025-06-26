# MQTT Architecture POC - System Overview

## System Architecture

This document provides a comprehensive overview of the MQTT Architecture Proof of Concept (POC) system, designed for ingesting, processing, and storing IoT data from F2 Smart Controller devices.

## High-Level Architecture Diagram

```mermaid
graph TD
    subgraph "**IoT Devices**"
        A["**F2 Smart Controllers**"] -->|MQTT| B("**MQTT Broker**")
    end

    subgraph "**Data Pipeline**"
        B --> C{"**MQTT-Kafka Connector**"}
        C -->|raw_iot_data| D("**Kafka**")
        D --> E{"**Data Processor**"}
        E -->|decoded_iot_data| D
        D --> F{"**Kafka-TimescaleDB Sink**"}
    end

    subgraph "**Data Stores**"
        E --> G["**PostgreSQL**"]
        F --> H("**TimescaleDB**")
    end

    subgraph "**Monitoring**"
        M("**Prometheus**") --> N{"**Grafana**"}
        B -->|Metrics| M
        C -->|Metrics| M
        D -->|Metrics| M
        E -->|Metrics| M
        F -->|Metrics| M
        G -->|Metrics| M
        H -->|Metrics| M
    end

    style A fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style B fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style C fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style D fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style E fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style F fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style G fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style H fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style M fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
    style N fill:#fff,stroke:#333,stroke-width:2px,font-weight:bold
```

## Core Components

### 1. **F2 Smart Controllers** (Simulated)
- **Purpose**: IoT devices that generate sensor data
- **Output**: MQTT messages with various sensor readings
- **Topics**: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/<COMPONENT>-<ID>`

### 2. **MQTT Broker (Mosquitto)**
- **Purpose**: Central message hub for all F2 device communications
- **Port**: 1883 (MQTT), 9001 (WebSocket)
- **Configuration**: `/mosquitto/mosquitto.conf`

### 3. **MQTT-Kafka Connector**
- **Purpose**: Bridges MQTT messages to Kafka topics
- **Input**: MQTT messages from `cmnd/#` pattern
- **Output**: Kafka topic `raw_iot_data`
- **Language**: Python with `paho-mqtt` and `kafka-python`

### 4. **Apache Kafka**
- **Purpose**: Message streaming platform and buffer
- **Topics**: 
  - `raw_iot_data` - Raw MQTT messages
  - `decoded_iot_data` - Processed IoT data
- **Port**: 9092

### 5. **PostgreSQL (Device Parameters)**
- **Purpose**: Stores device metadata and processing parameters
- **Database**: `device_params`
- **Port**: 5432
- **Key Table**: `device_parameters`

### 6. **Data Processor**
- **Purpose**: Transforms raw IoT data into meaningful measurements
- **Input**: Kafka topic `raw_iot_data`
- **Output**: Kafka topic `decoded_iot_data`
- **Language**: Python with database lookups

### 7. **TimescaleDB**
- **Purpose**: Time-series data storage for analytics
- **Database**: `timeseries`
- **Port**: 5433
- **Key Table**: `iot_measurements` (hypertable)

### 8. **Kafka-TimescaleDB Sink**
- **Purpose**: Writes processed data to TimescaleDB
- **Input**: Kafka topic `decoded_iot_data`
- **Output**: TimescaleDB `iot_measurements` table
- **Features**: Batch processing, error handling

## Data Flow

1.  **F2 Simulators** publish MQTT messages to topics like `cmnd/f2-{MAC}/{MODE}/{CONNECTOR}/{COMPONENT}`
2.  **MQTT-Kafka Connector** subscribes to `cmnd/#` and forwards to Kafka topic `raw_iot_data`
3.  **Data Processor** consumes `raw_iot_data`, looks up device parameters in PostgreSQL, and publishes enriched data to `decoded_iot_data`
4.  **Kafka-TimescaleDB Sink** consumes `decoded_iot_data` and batch-inserts into TimescaleDB `iot_measurements` hypertable

## Database Schema

```mermaid
erDiagram
    "DeviceType" {
        INT DeviceTypeId PK
        VARCHAR Name
    }
    "DeviceTemplate" {
        INT DeviceTemplateId PK
        VARCHAR Name
        VARCHAR Model
        TEXT Description
        BYTEA Image
        INT DeviceTypeId FK
    }
    "Device" {
        INT DeviceId PK
        VARCHAR DeviceName
        INT DeviceTemplateId FK
        VARCHAR ClaimingCode
        VARCHAR SerialNumber
        VARCHAR Uuid
        VARCHAR MacAddress
        VARCHAR IpAddress
        VARCHAR PcbVersion
    }
    "Connector" {
        INT ConnectorId PK
        INT ControllerId FK
        INT ConnectorNumber
        INT ConnectorTypeId
    }
    "Pin" {
        INT PinId PK
        INT ConnectorId FK
        INT Position
        INT DeviceId FK
    }
    "DataPointIcon" {
        INT DataPointIconId PK
        VARCHAR IconName
    }
    "DataPoint" {
        INT DataPointId PK
        INT DeviceTemplateId FK
        VARCHAR Label
        INT DataPointIconId FK
        VARCHAR DataFormat
        VARCHAR DataEncoding
        INT Offset
        INT Length
        VARCHAR Prepend
        VARCHAR Append
        INT WholeNumber
        INT Decimals
        VARCHAR RealTimeChart
        VARCHAR HistoricalChart
    }
    "iot_measurements" {
        TIMESTAMPTZ timestamp PK
        VARCHAR device_id PK
        VARCHAR connector_mode PK
        VARCHAR component_type PK
        VARCHAR pin_position PK
        DOUBLE_PRECISION value
        VARCHAR unit
        VARCHAR topic
    }

    "DeviceType" ||--o{ "DeviceTemplate" : "has"
    "DeviceTemplate" ||--o{ "Device" : "has"
    "DeviceTemplate" ||--o{ "DataPoint" : "has"
    "Device" ||--o{ "Connector" : "has"
    "Connector" ||--o{ "Pin" : "has"
    "Device" ||--|{ "Pin" : "is"
    "DataPointIcon" ||--o{ "DataPoint" : "has"
    "Device" ||--o{ "iot_measurements" : "generates"

```

## Network Configuration

All components run in the `iot-network` Docker network bridge, enabling inter-service communication using service names as hostnames.

## Scalability Design

- **Horizontal Scaling**: Each Python service can be scaled independently
- **Kafka Partitioning**: Topics can be partitioned for parallel processing
- **Database Optimization**: TimescaleDB provides automatic partitioning and compression
- **Batch Processing**: Sink service uses configurable batch sizes for optimal throughput

## Security Considerations

- **Network Isolation**: All services run in isolated Docker network
- **Database Access**: Separate databases with distinct credentials
- **No External Exposure**: Only necessary ports exposed to host system
- **Logging**: Comprehensive logging without sensitive data exposure