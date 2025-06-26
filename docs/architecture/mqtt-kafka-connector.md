# MQTT-Kafka Connector Service

## Overview

The MQTT-Kafka Connector service bridges the MQTT broker and Kafka, transforming MQTT messages into structured Kafka records for downstream processing.

## Service Configuration

### Environment Variables
```bash
MQTT_BROKER=mosquitto:1883          # MQTT broker connection
KAFKA_BOOTSTRAP_SERVERS=kafka:29092 # Kafka cluster connection
KAFKA_TOPIC=raw_iot_data           # Output Kafka topic
MQTT_TOPIC_PATTERN=cmnd/#          # MQTT subscription pattern
```

### Docker Configuration
```yaml
mqtt-kafka-connector:
  build: ./services/mqtt_kafka_connector
  container_name: mqtt-kafka-connector
  depends_on: [mosquitto, kafka]
  networks: [iot-network]
  restart: unless-stopped
```

## Implementation Details

### Core Functionality

**File**: `services/mqtt_kafka_connector/connector.py`

#### Key Classes and Methods

- **`MQTTKafkaConnector`**: Main service class
- **`_extract_device_id()`**: Extracts F2 device MAC address from MQTT topic
- **`_on_mqtt_message()`**: Processes incoming MQTT messages
- **`_send_to_kafka()`**: Publishes transformed data to Kafka

#### Message Transformation

**Input** (MQTT Message):
```
Topic: cmnd/f2-e4fd45f654be/access-control-mode/J1/door-sensors
Payload: {"timestamp": "2023-05-26 18:34:04.928538", "door-sensor-1": false, "door-sensor-2": true}
```

**Output** (Kafka Record):
```json
{
  "original_topic": "cmnd/f2-e4fd45f654be/access-control-mode/J1/door-sensors",
  "device_id": "f2-e4fd45f654be",
  "payload": {
    "timestamp": "2023-05-26 18:34:04.928538",
    "door-sensor-1": false,
    "door-sensor-2": true
  },
  "timestamp": 1684678444.928538
}
```

### MQTT Configuration

#### Subscription Pattern
- **Pattern**: `cmnd/#`
- **Fallback**: `cmnd/+/+/+/+` (if wildcard fails)
- **QoS**: 0 (at most once delivery)

#### Connection Settings
- **Keep Alive**: 60 seconds
- **Auto Reconnect**: Enabled
- **Clean Session**: True

### Kafka Configuration

#### Producer Settings
```python
KafkaProducer(
    bootstrap_servers=servers,
    acks='all',                    # Wait for all replicas
    retries=3,                     # Retry failed sends
    max_in_flight_requests_per_connection=1  # Ensure ordering
)
```

#### Key Strategy
- **Kafka Key**: Device ID (e.g., `f2-e4fd45f654be`)
- **Partitioning**: Messages from same device go to same partition
- **Ordering**: Maintains message order per device

## Error Handling

### MQTT Connection Errors
- Automatic reconnection on connection loss
- Fallback subscription patterns
- Graceful degradation

### Kafka Publishing Errors
- Async callbacks for delivery confirmation
- Error logging with context
- Message loss prevention

### Data Validation
- JSON payload validation
- Topic pattern matching
- Device ID extraction with fallback

## Monitoring and Logging

### Log Levels
- **INFO**: Connection status, successful operations
- **DEBUG**: Message processing details
- **ERROR**: Connection failures, processing errors
- **WARNING**: Fallback operations, recoverable issues

### Key Metrics (Available via Logs)
- Messages processed per second
- MQTT connection status
- Kafka delivery success rate
- Device ID extraction success rate

## Performance Characteristics

### Throughput
- **Expected**: 1000+ messages/second
- **Bottleneck**: Network I/O between MQTT and Kafka
- **Scaling**: Single instance sufficient for POC

### Latency
- **MQTT to Kafka**: < 10ms typical
- **Memory Usage**: < 100MB typical
- **CPU Usage**: < 5% typical

### Resource Requirements
```yaml
resources:
  limits:
    memory: 256Mi
    cpu: 200m
  requests:
    memory: 128Mi
    cpu: 100m
```

## Operational Commands

### Service Management
```bash
# View connector logs
docker-compose logs -f mqtt-kafka-connector

# Restart connector only  
docker-compose restart mqtt-kafka-connector

# Debug MQTT messages
mosquitto_sub -h localhost -t "cmnd/#" -v
```

### Troubleshooting

#### Common Issues

1. **MQTT Connection Failed**
   ```bash
   # Check mosquitto status
   docker-compose ps mosquitto
   # Check network connectivity
   docker exec mqtt-kafka-connector ping mosquitto
   ```

2. **Kafka Connection Failed**
   ```bash
   # Check Kafka status
   docker-compose ps kafka
   # Verify topic exists
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
   ```

3. **No Messages Processing**
   ```bash
   # Check MQTT subscription
   mosquitto_sub -h localhost -t "cmnd/#" -v
   # Check Kafka production
   docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_iot_data --from-beginning
   ```

## Dependencies

### Python Libraries
- `paho-mqtt==1.6.1`: MQTT client
- `kafka-python==2.0.2`: Kafka producer
- Standard library: `json`, `logging`, `os`, `re`, `time`, `signal`

### Service Dependencies
- **Mosquitto**: MQTT message source
- **Kafka**: Message destination
- **Zookeeper**: Kafka coordination (indirect)

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY connector.py .
CMD ["python", "connector.py"]
```

### Requirements.txt
```
paho-mqtt==1.6.1
kafka-python==2.0.2
```

## Future Enhancements

1. **Health Checks**: HTTP endpoint for service status
2. **Metrics Export**: Prometheus metrics integration
3. **Schema Registry**: Avro schema validation
4. **Dead Letter Queue**: Failed message handling
5. **Rate Limiting**: Configurable throughput controls
