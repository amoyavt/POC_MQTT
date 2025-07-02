# MQTT Architecture - System Overview

This document provides a comprehensive overview of the MQTT Architecture Proof of Concept (POC) system, designed for ingesting, processing, and storing IoT data from F2 Smart Controller devices.

## Core Components

### 1. **F2 Smart Controllers** (Simulated)
- **Purpose**: IoT devices that generate sensor data
- **Output**: MQTT messages with various sensor readings
- **Topics**: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/<COMPONENT>-<ID>`
- **Security**: mTLS authentication with device-specific certificates
- **Connection**: Secure port 8883 with client certificate validation

### 2. **MQTT Broker (Mosquitto)**
- **Purpose**: Central message hub for all F2 device communications
- **Ports**: 
  - **1883**: Insecure port for internal services (username/password auth)
  - **8883**: Secure mTLS port for F2 controllers (certificate auth)
  - **9001**: WebSocket port
- **Configuration**: `mqtt-security/mosquitto/mosquitto.conf`
- **Security**: Dual-mode authentication with MAC-based ACL authorization
- **Certificates**: CA-signed certificates for device authentication

### 3. **MQTT-Kafka Connector**
- **Purpose**: Bridges MQTT messages to Kafka topics
- **Input**: MQTT messages from `cmnd/#` pattern (port 1883)
- **Output**: Kafka topic `raw_iot_data`
- **Language**: Python with `paho-mqtt` and `kafka-python`
- **Security**: Username/password authentication on internal port

### 4. **Zookeeper**
- **Purpose**: Coordination service for Kafka cluster management
- **Port**: 2181
- **Function**: Manages Kafka metadata, leader election, and cluster coordination

### 5. **Apache Kafka**
- **Purpose**: Message streaming platform and buffer
- **Topics**: 
  - `raw_iot_data` - Raw MQTT messages
  - `decoded_iot_data` - Processed IoT data
- **Port**: 9092

### 6. **PostgreSQL (Device Management)**
- **Purpose**: Stores complete device schema including templates, connectors, pins, and data points
- **Database**: `VT_DeviceManagement` (configurable via `POSTGRES_DB` env var)
- **Port**: 5432
- **User**: `postgres` (configurable via `POSTGRES_USER` env var)
- **Key Tables**: 
  - `Device` - Device instances with MAC addresses and metadata
  - `DeviceTemplate` - Device type definitions and configurations
  - `DataPoint` - Data decoding parameters for each device template
  - `Connector` - Controller connector definitions
  - `Pin` - Pin-to-device mappings for controllers
  - `device_parameters` - Legacy parameter lookup table (used by data processor)

### 7. **Data Processor**
- **Purpose**: Transforms raw IoT data into meaningful measurements
- **Input**: Kafka topic `raw_iot_data`
- **Output**: Kafka topic `decoded_iot_data`
- **Language**: Python with database lookups

### 8. **TimescaleDB**
- **Purpose**: Time-series data storage for analytics
- **Database**: `timeseries`
- **Port**: 5433
- **Key Table**: `iot_measurements` (hypertable)

### 9. **Kafka-TimescaleDB Sink**
- **Purpose**: Writes processed data to TimescaleDB
- **Input**: Kafka topic `decoded_iot_data`
- **Output**: TimescaleDB `iot_measurements` table
- **Features**: Batch processing, error handling

## Data Flow

1.  **F2 Simulators** authenticate using mTLS certificates and publish MQTT messages to topics like `cmnd/f2-{MAC}/{MODE}/{CONNECTOR}/{COMPONENT}` on secure port 8883
2.  **MQTT-Kafka Connector** subscribes to `cmnd/#` on insecure port 1883 and forwards to Kafka topic `raw_iot_data`
3.  **Data Processor** consumes `raw_iot_data`, looks up device parameters in PostgreSQL, and publishes enriched data to `decoded_iot_data`
4.  **Kafka-TimescaleDB Sink** consumes `decoded_iot_data` and batch-inserts into TimescaleDB `iot_measurements` hypertable

## Network Configuration

All components run in the `iot-network` Docker network bridge, enabling inter-service communication using service names as hostnames.

## Scalability Design

- **Horizontal Scaling**: Each Python service can be scaled independently
- **Kafka Partitioning**: Topics can be partitioned for parallel processing
- **Database Optimization**: TimescaleDB provides automatic partitioning and compression
- **Batch Processing**: Sink service uses configurable batch sizes for optimal throughput

## Security Considerations

### **mTLS Implementation**
- **F2 Device Authentication**: Client certificates signed by internal CA
- **MAC-based Authorization**: Device-specific topic permissions via ACL
- **Certificate Management**: Automated device registration and certificate provisioning
- **Dual-Port Security**: Secure (8883) and internal (1883) MQTT listeners

### **Infrastructure Security**
- **Network Isolation**: All services run in isolated Docker network
- **Database Access**: Separate databases with distinct credentials
- **Secrets Management**: Docker secrets for production deployments
- **No External Exposure**: Only necessary ports exposed to host system
- **Logging**: Comprehensive logging without sensitive data exposure

### **Device Registration**
- **Certificate Provisioning**: `register_f2_controller.py` script for device onboarding
- **Device Registry**: JSON-based device tracking with certificate expiration
- **ACL Generation**: Automatic topic permission generation based on device capabilities
