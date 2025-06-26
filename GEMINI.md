# MQTT Architecture POC - Gemini Context

## Project Overview

This is an MQTT Architecture Proof of Concept (POC) that demonstrates a complete IoT data pipeline for F2 Smart Controller devices. The system ingests raw MQTT messages, processes them through Kafka, enriches the data using device parameters, and stores the results in TimescaleDB for analytics.

## Architecture Components

The system consists of the following main components:

1. **F2 Device Simulator** - Simulates IoT devices publishing MQTT messages
2. **MQTT Broker (Mosquitto)** - Central message hub for device communications
3. **MQTT-Kafka Connector** - Bridges MQTT messages to Kafka topics
4. **Apache Kafka** - Message streaming platform with raw and processed data topics
5. **PostgreSQL** - Stores device parameters and metadata
6. **Data Processor** - Transforms raw data into meaningful measurements
7. **TimescaleDB** - Time-series database for analytics and storage
8. **Kafka-TimescaleDB Sink** - Persists processed data to TimescaleDB

## Monitoring Stack

The system includes comprehensive monitoring with:

- **Prometheus** - Metrics collection and storage
- **Grafana** - Visualization dashboards (http://localhost:3000, admin/admin)
- **cAdvisor** - Container resource monitoring
- **Node Exporter** - Host system metrics
- **Health Monitor** - Custom health check API (http://localhost:8000)

## Quick Start Commands

```bash
# Complete setup with monitoring
docker-compose up -d && docker-compose -f monitoring/docker-compose.monitoring.yml up -d

# Check system status
docker-compose ps && docker-compose -f monitoring/docker-compose.monitoring.yml ps

# Monitor health
curl http://localhost:8000/health

# View logs
docker-compose logs -f

# Stop everything cleanly
docker-compose down && docker-compose -f monitoring/docker-compose.monitoring.yml down
```

## Service Ports

- **Grafana**: 3000 (admin/admin)
- **Prometheus**: 9090
- **Health Monitor**: 8000
- **cAdvisor**: 8080
- **Node Exporter**: 9100
- **MQTT Broker**: 1883, 9001
- **Kafka**: 9092
- **PostgreSQL**: 5432
- **TimescaleDB**: 5433

## Database Access

```bash
# PostgreSQL (device parameters)
docker exec -it device-params-db psql -U iot_user -d device_params

# TimescaleDB (time-series data)
docker exec -it timescale-db psql -U ts_user -d timeseries
```

## Kafka Monitoring

```bash
# List Kafka topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# View raw IoT data
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_iot_data --from-beginning

# View processed data
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic decoded_iot_data --from-beginning
```

## Log Monitoring

```bash
# All service logs
docker-compose logs -f

# Individual service logs
docker-compose logs -f mqtt-kafka-connector
docker-compose logs -f data-processor
docker-compose logs -f kafka-timescale-sink
docker-compose logs -f f2-simulator
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

### Architecture Documentation (`docs/architecture/`)

- **[overview.md](docs/architecture/overview.md)** - Complete system architecture overview
- **[mqtt-kafka-connector.md](docs/architecture/mqtt-kafka-connector.md)** - MQTT-Kafka bridge service
- **[data-processor.md](docs/architecture/data-processor.md)** - Data transformation service
- **[kafka-timescale-sink.md](docs/architecture/kafka-timescale-sink.md)** - Data persistence service
- **[f2-simulator.md](docs/architecture/f2-simulator.md)** - IoT device simulator

### Monitoring Documentation (`docs/monitoring/`)

- **[overview.md](docs/monitoring/overview.md)** - Complete monitoring stack overview
- **[grafana-setup.md](docs/monitoring/grafana-setup.md)** - Grafana configuration and dashboards
- **[health-monitor.md](docs/monitoring/health-monitor.md)** - Health monitoring service API

## Data Flow

1. **F2 Simulators** publish MQTT messages to topics like `cmnd/f2-{MAC}/{MODE}/{CONNECTOR}/{COMPONENT}`
2. **MQTT-Kafka Connector** subscribes to `cmnd/#` and forwards to Kafka topic `raw_iot_data`
3. **Data Processor** consumes `raw_iot_data`, looks up device parameters in PostgreSQL, and publishes enriched data to `decoded_iot_data`
4. **Kafka-TimescaleDB Sink** consumes `decoded_iot_data` and batch-inserts into TimescaleDB `iot_measurements` hypertable

## Example Device Parameters

The system supports multiple encoding types for device data:

```sql
INSERT INTO device_parameters VALUES 
('f2-e4fd45f654be', 'access-control-mode', 'door-sensors', NULL, 'boolean_map', 'state', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'strike', '1', 'boolean', 'state', 1.0),
('f2-e4fd45f654be', 'sensor-mode', 'sensor', '3', 'hex_to_float', 'celsius', 0.1),
('f2-e4fd45f654be', 'alarm-mode', 'motion-sensor', '1', 'boolean', 'presence', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'reader', '1', 'raw_string', 'text', 1.0);
```

## Troubleshooting

Common troubleshooting commands:

```bash
# Check Docker container status
docker-compose ps

# Check individual service health
curl http://localhost:8000/health/{service_name}

# Monitor MQTT messages
mosquitto_sub -h localhost -t "cmnd/#" -v

# Check Kafka consumer lag
docker exec kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
```

## Development Notes

- All services are containerized and run in the `iot-network` Docker network
- Python microservices handle the data pipeline with proper error handling
- TimescaleDB provides automatic time-series partitioning and compression
- Monitoring stack provides full observability with metrics, logs, and health checks
- The system is designed for horizontal scaling and production deployment

## Service Dependencies

- **MQTT-Kafka Connector**: Requires Mosquitto and Kafka
- **Data Processor**: Requires Kafka and PostgreSQL
- **Kafka-TimescaleDB Sink**: Requires Kafka and TimescaleDB
- **F2 Simulator**: Requires Mosquitto
- **Health Monitor**: Requires Docker socket access
- **Grafana**: Requires Prometheus

## Testing Commands

```bash
# Run lint/typecheck (when available)
# Note: Add specific commands if project has linting setup

# Test data pipeline end-to-end
docker-compose up -d && sleep 30 && curl http://localhost:8000/health
```

## Common Tasks

When working with this codebase:

1. **Adding new device parameters**: Update PostgreSQL `device_parameters` table
2. **Modifying data processing**: Edit `services/data_processor/processor.py`
3. **Adding monitoring panels**: Update Grafana dashboards in `monitoring/grafana/dashboards/`
4. **Scaling services**: Adjust Docker Compose service replicas
5. **Performance tuning**: Monitor Grafana dashboards and adjust batch sizes

The system provides a complete, production-ready IoT data pipeline with full monitoring and observability.
