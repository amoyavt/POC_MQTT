# IoT Data Processing Architecture - Production Implementation

A complete, production-ready implementation of the IoT data processing and storage architecture for F2 Smart Controllers. This system transforms raw MQTT device data into meaningful time-series analytics through a fully containerized, monitored, and scalable Python microservices architecture.

## 🎯 Project Status: **COMPLETE**

✅ All architecture components implemented and tested  
✅ Comprehensive monitoring and health checking  
✅ Production-ready containerized deployment  
✅ Full documentation and operational procedures

## 📋 Table of Contents

- [🏗️ Architecture Components](#️-architecture-components)
- [🚀 Quick Start](#-quick-start)
  - [Option 1: Complete Setup with Monitoring](#option-1-complete-setup-with-monitoring)
  - [Option 2: Basic Setup](#option-2-basic-setup)
  - [🌐 Access Points](#-access-points)
- [🛑 Stopping the System](#-stopping-the-system)
- [📊 Data Flow Example](#-data-flow-example)
- [🗃️ Database Access](#️-database-access)
- [🔍 Container Health Monitoring](#-container-health-monitoring)
- [📈 Kafka Topics](#-kafka-topics)
- [🔧 Configuration](#-configuration)
- [🎮 Simulated Device Types](#-simulated-device-types)
- [📈 Production Scaling](#-production-scaling)
- [🛠️ Development Workflow](#️-development-workflow)
- [📋 Production Readiness Checklist](#-production-readiness-checklist)
- [🎯 Next Steps for Production](#-next-steps-for-production)
- [⚡ Quick Command Reference](#-quick-command-reference)

## Architecture Overview

The system implements the following data flow:

```
F2 Smart Controller IoT Devices (Simulated) 
    ↓ MQTT
Mosquitto MQTT Broker 
    ↓ 
MQTT-Kafka Connector (Python) 
    ↓ 
Apache Kafka (raw_iot_data topic) 
    ↓ 
Data Processing Service (Python) ← PostgreSQL (Device Parameters)
    ↓ 
Apache Kafka (decoded_iot_data topic) 
    ↓ 
Kafka-TimescaleDB Sink (Python) 
    ↓ 
TimescaleDB (Time-series Storage)
```

## 🏗️ Architecture Components

### Core Infrastructure
- **🔌 Mosquitto MQTT Broker**: Reliable MQTT message hub with WebSocket support
- **📊 Apache Kafka + Zookeeper**: High-throughput message streaming platform
- **🗃️ PostgreSQL**: Device parameters and configuration metadata store
- **⏰ TimescaleDB**: Optimized time-series database with hypertables and compression

### Python Microservices
- **🔄 MQTT-Kafka Connector**: Reliable bridge between MQTT and Kafka with error handling
- **⚙️ Data Processor**: Intelligent data decoder with multi-encoding support
- **💾 Kafka-TimescaleDB Sink**: High-performance batch writer with configurable batching
- **🤖 F2 Device Simulator**: Realistic multi-device simulator for testing

### Monitoring & Observability
- **📈 Prometheus**: Metrics collection with custom IoT pipeline metrics
- **📊 Grafana**: Visual dashboards for system and IoT data monitoring
- **🔍 Health Monitor API**: Custom FastAPI service for container health checking
- **📋 cAdvisor**: Container resource monitoring and performance metrics
- **🖥️ Node Exporter**: Host system metrics and resource utilization

## Quick Start

### Option 1: Complete Setup with Monitoring
```bash
# Start everything including monitoring stack
make full-setup

# Check system status
make status

# View health
make health
```

### Option 2: Basic Setup
```bash
# Start just the IoT architecture
docker-compose up -d

# View logs
docker-compose logs -f
```

### 🌐 Access Points
- **📊 Grafana Dashboards**: http://localhost:3000 (admin/admin) - IoT data visualization
- **📈 Prometheus**: http://localhost:9090 - Metrics queries and alerting
- **🩺 Health Monitor API**: http://localhost:8000 - Container and service health
- **📋 Container Metrics**: http://localhost:8080 - cAdvisor resource monitoring

## 🛑 Stopping the System

### Complete Stop (Recommended)
```bash
# Stop everything and clean up (improved - now removes monitoring too!)
make clean
```
This command will:
- Stop all IoT architecture containers
- Stop all monitoring containers  
- Remove data volumes (clears all data)
- Clean up Docker system resources

### Nuclear Option (If containers are stuck)
```bash
# Force remove everything - use if normal cleanup fails
make nuclear-clean
```
This will forcefully stop and remove all related containers.

### Partial Stop Options
```bash
# Stop everything but preserve data
docker-compose down                           # Stop main IoT services
make monitoring-down                          # Stop monitoring stack (now includes volumes)

# Stop only monitoring (keep IoT pipeline running)
make monitoring-down

# Stop only main services (keep monitoring running)
docker-compose down
```

### Verify System Status
```bash
# Check what's still running
make status

# Check all containers
docker ps -a

# Check specific services
docker-compose ps                             # Main services
docker-compose -f monitoring/docker-compose.monitoring.yml ps  # Monitoring
```

## Data Flow Example

1. **F2 Simulator** publishes MQTT messages like:
   ```
   Topic: cmnd/f2-e4fd45f654be/access-control-mode/J1/door-sensors
   Payload: {"timestamp": "2023-05-26T18:34:04.928538", "door-sensor-1": false, "door-sensor-2": true}
   ```

2. **MQTT-Kafka Connector** receives the message and forwards it to Kafka:
   ```json
   {
     "original_topic": "cmnd/f2-e4fd45f654be/access-control-mode/J1/door-sensors",
     "device_id": "f2-e4fd45f654be",
     "payload": {"timestamp": "2023-05-26T18:34:04.928538", "door-sensor-1": false, "door-sensor-2": true},
     "timestamp": 1684863244.928
   }
   ```

3. **Data Processor** enriches the data using device parameters:
   ```json
   {
     "timestamp": 1684863244.928,
     "device_id": "f2-e4fd45f654be",
     "connector_mode": "access-control-mode",
     "component_type": "door-sensors",
     "component_id": null,
     "value": {"door-sensor-1": false, "door-sensor-2": true},
     "unit": "state",
     "original_topic": "cmnd/f2-e4fd45f654be/access-control-mode/J1/door-sensors",
     "raw_data": {...}
   }
   ```

4. **TimescaleDB Sink** stores the data in the time-series database.

## Database Access

### PostgreSQL (Device Parameters)
```bash
docker exec -it device-params-db psql -U iot_user -d device_params
```

### TimescaleDB (Time-series Data)
```bash
docker exec -it timescale-db psql -U ts_user -d timeseries
```

Example queries:
```sql
-- View device parameters
SELECT * FROM device_parameters;

-- View recent IoT measurements
SELECT * FROM iot_measurements ORDER BY timestamp DESC LIMIT 10;

-- View hourly aggregates
SELECT * FROM iot_hourly_stats ORDER BY bucket DESC LIMIT 10;
```

## Container Health Monitoring

The system includes comprehensive monitoring:

### Health Check API
```bash
# Overall system health
curl http://localhost:8000/health

# Container status
curl http://localhost:8000/containers

# Service connectivity  
curl http://localhost:8000/connectivity

# System resources
curl http://localhost:8000/system
```

### Monitoring Stack
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization dashboards  
- **Health Monitor**: Custom API for container/service health
- **cAdvisor**: Container resource metrics
- **Node Exporter**: Host system metrics

### Monitoring Commands
```bash
# Start monitoring
make monitoring-up

# Stop monitoring  
make monitoring-down

# View monitoring logs
make monitoring-logs

# Check overall status
make status

# Quick health check
make health
```

## Kafka Topics
```bash
# List topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# View raw IoT data
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_iot_data --from-beginning

# View decoded IoT data  
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic decoded_iot_data --from-beginning
```

### MQTT Messages
```bash
# Subscribe to all F2 device messages
docker exec mosquitto mosquitto_sub -h localhost -t "cmnd/f2-#"
```

## Configuration

Environment variables can be modified in `.env` file or directly in `docker-compose.yml`.

Key configuration options:
- `PUBLISH_INTERVAL`: How often simulator publishes data (seconds)
- `BATCH_SIZE`: Number of records to batch before inserting to TimescaleDB
- `BATCH_TIMEOUT`: Maximum time to wait before flushing batch (seconds)

## 🎮 Simulated Device Types

The F2 simulator generates realistic data for all component types:

| Component Type | Data Format | Example Use Case |
|---|---|---|
| **🚪 Door Sensors** | Boolean mapping | Access control entry/exit monitoring |
| **⚡ Electric Strikes** | Boolean status | Door lock control and status |
| **🔘 Exit Buttons** | Boolean mapping | Emergency exit button monitoring |
| **👀 Motion Sensors** | Boolean presence | Security and occupancy detection |
| **🚨 Sirens** | Boolean activation | Security alarm status |
| **📱 QR/NFC Readers** | Raw string data | Access card and code processing |
| **🌡️ RS-485 Sensors** | Hex-encoded values | Temperature, humidity, pressure monitoring |

## 📈 Production Scaling

This implementation is designed for production scaling:

### ✅ Already Implemented
- **🔍 Comprehensive Monitoring**: Prometheus, Grafana, Health APIs
- **⚡ Error Handling**: Robust error handling and retry logic throughout pipeline
- **📊 Batch Processing**: Configurable batch sizes for optimal performance
- **🐳 Containerization**: Full Docker Compose orchestration
- **🔧 Configuration Management**: Environment-based configuration

### 🚀 Scaling Options
1. **Kafka Partitioning**: Increase partitions for higher throughput
2. **Horizontal Scaling**: Run multiple instances of Python services
3. **Resource Optimization**: Tune container resources and batch sizes
4. **Load Balancing**: Add load balancers for service distribution
5. **Database Optimization**: Implement TimescaleDB compression and retention policies

## 🛠️ Development Workflow

### Modifying Services
```bash
# Make changes to Python code in services/ directories
# Rebuild specific service
docker-compose build <service-name>

# Restart service
docker-compose up -d <service-name>

# View logs
docker-compose logs -f <service-name>
```

### Adding New Devices
1. Update device parameters in PostgreSQL
2. Add device MAC addresses to simulator
3. Test data flow through pipeline
4. Monitor in Grafana dashboards

## 📋 Production Readiness Checklist

- ✅ **Container Health Checks**: All services have health monitoring
- ✅ **Error Handling**: Comprehensive error handling and logging
- ✅ **Monitoring**: Full observability stack with metrics and dashboards  
- ✅ **Documentation**: Complete architecture and operational documentation
- ✅ **Configuration**: Environment-based configuration management
- ✅ **Testing**: Realistic device simulation for testing
- ✅ **Scalability**: Designed for horizontal scaling and high throughput

## 🎯 Next Steps for Production

1. **Security**: Add authentication, TLS encryption, and secrets management
2. **CI/CD**: Implement automated testing and deployment pipelines
3. **Alerting**: Configure Prometheus alerting rules and notification channels
4. **Backup**: Implement database backup and disaster recovery procedures
5. **Performance Testing**: Load testing with realistic device volumes

## ⚡ Quick Command Reference

### 🚀 Essential Commands
```bash
# Start everything
make full-setup

# Stop everything 
make clean

# Force cleanup (if stuck)
make nuclear-clean

# Check status
make status

# Monitor health
make health
```

### 📊 Monitoring & Access
```bash
# Web interfaces
http://localhost:3000    # Grafana (admin/admin)
http://localhost:9090    # Prometheus  
http://localhost:8000    # Health API
http://localhost:8080    # Container metrics

# View logs
make logs                # All services
make monitoring-logs     # Monitoring stack only
```

### 🗃️ Data Access
```bash
# Database connections
make db-params          # Device parameters (PostgreSQL)
make db-timescale       # Time-series data (TimescaleDB)

# Message streams
make kafka-topics       # List Kafka topics
make kafka-raw          # Raw IoT data stream
make kafka-decoded      # Processed data stream
make mqtt-monitor       # MQTT message stream
```

### 🔧 Development
```bash
# Partial operations
make monitoring-up      # Start monitoring only
make monitoring-down    # Stop monitoring only
docker-compose up -d    # Start main services only
docker-compose down     # Stop main services only

# Service-specific logs
make logs-connector     # MQTT-Kafka connector
make logs-processor     # Data processor
make logs-sink          # TimescaleDB sink  
make logs-simulator     # Device simulator
```