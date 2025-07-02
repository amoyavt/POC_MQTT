# Data Processor Service

## Overview

The Data Processor service is the intelligence layer of the IoT pipeline, responsible for transforming raw MQTT messages into meaningful, decoded measurements using device-specific parameters.

## Service Configuration

### Environment Variables

**Development Mode**:
```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:29092    # Kafka cluster connection
KAFKA_INPUT_TOPIC=raw_iot_data         # Input topic for raw data
KAFKA_OUTPUT_TOPIC=decoded_iot_data    # Output topic for processed data
POSTGRES_HOST=postgres                 # Device parameters database
POSTGRES_DB=device_params              # Database name
POSTGRES_USER=iot_user                 # Database username
POSTGRES_PASSWORD=iot_password         # Database password (fallback)
POSTGRES_PORT=5432                     # Database port
```

**Production Mode (Docker Secrets)**:
```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:29092    # Kafka cluster connection
KAFKA_INPUT_TOPIC=raw_iot_data         # Input topic for raw data
KAFKA_OUTPUT_TOPIC=decoded_iot_data    # Output topic for processed data
POSTGRES_HOST=postgres                 # Device parameters database
POSTGRES_DB=device_params              # Database name
POSTGRES_USER=iot_user                 # Database username
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password  # Secure password file
POSTGRES_PORT=5432                     # Database port
```

### Docker Configuration
```yaml
data-processor:
  build: ./services/data_processor
  container_name: data-processor
  depends_on: [kafka, postgres]
  networks: [iot-network]
  restart: unless-stopped
```

## Implementation Details

### Core Functionality

**File**: `services/data_processor/processor.py`

#### Key Classes and Methods

- **`DataProcessor`**: Main service class
- **`_load_secret_from_docker_file()`**: Secure credential loading from Docker secrets
- **`_parse_mqtt_topic()`**: Extracts device metadata from MQTT topic structure
- **`_get_device_parameters()`**: Database lookup for device-specific parameters
- **`_decode_value()`**: Transforms raw data based on encoding type
- **`_process_message()`**: Main message processing pipeline

#### Security Implementation

The service implements secure credential management using the Docker secrets pattern:

```python
def _load_secret_from_docker_file(self, secret_file_path: Optional[str], 
                                 fallback_value: str, 
                                 secret_name: str = "credential") -> str:
    """
    Load sensitive data from Docker secrets file or fallback to environment variable.
    
    Used for PostgreSQL password loading:
    - Production: Reads from /run/secrets/postgres_password
    - Development: Falls back to POSTGRES_PASSWORD environment variable
    """
```

#### Topic Parsing Logic

**MQTT Topic Pattern**: `cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/<COMPONENT>-<ID>`

**Examples**:
```
cmnd/f2-e4fd45f654be/access-control-mode/J1/door-sensors
cmnd/f2-e4fd45f654be/sensor-mode/J1/sensor-3
cmnd/f2-e4fd45f654be/alarm-mode/J1/motion-sensor-1
```

**Extracted Components**:
- Device ID: `f2-e4fd45f654be`
- Connector Mode: `access-control-mode`
- Component Type: `door-sensors`
- Component ID: `3` (optional)

## Database Integration

### Device Parameters Schema

**Table**: `device_parameters`

```sql
CREATE TABLE device_parameters (
    device_id VARCHAR(50),
    connector_mode VARCHAR(50),
    component_type VARCHAR(50),
    component_id VARCHAR(10),
    encoding_type VARCHAR(20),
    units VARCHAR(20),
    scaling_factor DECIMAL(10,6),
    PRIMARY KEY (device_id, connector_mode, component_type, component_id)
);
```

### Parameter Lookup Query
```sql
SELECT encoding_type, units, scaling_factor 
FROM device_parameters 
WHERE device_id = %s AND connector_mode = %s 
AND component_type = %s AND (component_id = %s OR component_id IS NULL)
ORDER BY component_id NULLS LAST
LIMIT 1
```

## Data Transformation

### Encoding Types

#### 1. **Boolean Encoding**
```python
# Raw Data
{"timestamp": "2023-05-26 18:34:04", "status": true}

# Decoded Result
True
```

#### 2. **Boolean Map Encoding**
```python
# Raw Data
{"timestamp": "2023-05-26 18:34:04", "door-sensor-1": false, "door-sensor-2": true}

# Decoded Result
{"door-sensor-1": False, "door-sensor-2": True}
```

#### 3. **Hex to Float Encoding**
```python
# Raw Data
{"timestamp": "2023-05-25 15:13:10", "data": "0x12A"}

# Parameters: scaling_factor = 0.1
# Decoded Result
29.8  # (0x12A = 298, 298 * 0.1 = 29.8)
```

#### 4. **Raw String Encoding**
```python
# Raw Data
{"timestamp": "2023-05-26 17:24:28", "data": "b'\"Hello World\"'"}

# Decoded Result
"b'\"Hello World\"'"
```

### Message Transformation Pipeline

**Input** (from `raw_iot_data`):
```json
{
  "original_topic": "cmnd/f2-e4fd45f654be/sensor-mode/J1/sensor-3",
  "device_id": "f2-e4fd45f654be",
  "payload": {
    "timestamp": "2023-05-25 15:13:10.543400",
    "data": "0x12A"
  },
  "timestamp": 1684681990.5434
}
```

**Output** (to `decoded_iot_data`):
```json
{
  "timestamp": 1684681990.5434,
  "device_id": "f2-e4fd45f654be",
  "connector_mode": "sensor-mode",
  "component_type": "sensor",
  "pin_position": "3",
  "value": 29.8,
  "unit": "celsius",
  "topic": "cmnd/f2-e4fd45f654be/sensor-mode/J1/sensor-3",
  "raw_data": {
    "timestamp": "2023-05-25 15:13:10.543400",
    "data": "0x12A"
  }
}
```

## Kafka Integration

### Consumer Configuration
```python
KafkaConsumer(
    'raw_iot_data',
    bootstrap_servers=servers,
    auto_offset_reset='latest',    # Start from newest messages
    enable_auto_commit=True,       # Commit offsets automatically
    group_id='data_processor_group',  # Consumer group
    value_deserializer=json.loads  # JSON deserialization
)
```

### Producer Configuration
```python
KafkaProducer(
    bootstrap_servers=servers,
    value_serializer=json.dumps,   # JSON serialization
    key_serializer=str.encode,     # String key encoding
    acks='all'                     # Wait for all replicas
)
```

## Error Handling

### Database Connection Errors
- Automatic reconnection on connection loss
- Connection pooling for efficiency
- Graceful degradation with logging

### Message Processing Errors
- Skip messages with missing parameters
- Log processing errors with context
- Continue processing other messages

### Data Validation Errors
- Handle malformed JSON payloads
- Validate encoding type compatibility
- Fallback to raw data on decode failure

## Performance Characteristics

### Throughput
- **Expected**: 500+ messages/second
- **Bottleneck**: Database parameter lookups
- **Optimization**: Parameter caching (future enhancement)

### Database Query Performance
- **Lookup Time**: < 5ms typical
- **Index Strategy**: Composite index on (device_id, connector_mode, component_type)
- **Connection Pool**: 5-10 connections

### Resource Requirements
```yaml
resources:
  limits:
    memory: 512Mi
    cpu: 500m
  requests:
    memory: 256Mi
    cpu: 200m
```

## Monitoring and Logging

### Log Levels
- **INFO**: Service startup, processing status
- **DEBUG**: Message processing details
- **ERROR**: Database errors, processing failures
- **WARNING**: Missing parameters, decode failures

### Key Metrics (Available via Logs)
- Messages processed per second
- Database lookup success rate
- Decode success rate by encoding type
- Processing latency distribution

## Operational Commands

### Service Management
```bash
# View processor logs
docker-compose logs -f data-processor

# Restart processor only
docker-compose restart data-processor

# Check processed data
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic decoded_iot_data --from-beginning
```

### Database Operations
```bash
# Access device parameters database
docker exec -it device-params-db psql -U iot_user -d device_params

# Query device parameters
SELECT * FROM device_parameters WHERE device_id = 'f2-e4fd45f654be';
```

### Troubleshooting

#### Common Issues

1. **No Parameters Found**
   ```sql
   -- Check if device exists in parameters table
   SELECT * FROM device_parameters WHERE device_id = 'f2-device-id';
   
   -- Add missing parameters
   INSERT INTO device_parameters VALUES 
   ('f2-device-id', 'sensor-mode', 'sensor', '1', 'hex_to_float', 'celsius', 0.1);
   ```

2. **Database Connection Failed**
   ```bash
   # Check PostgreSQL status
   docker-compose ps postgres
   # Test connection
   docker exec data-processor pg_isready -h postgres
   ```

3. **Kafka Processing Lag**
   ```bash
   # Check consumer lag
   docker exec kafka kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group data_processor_group
   ```

## Dependencies

### Python Libraries
- `kafka-python==2.0.2`: Kafka consumer/producer
- `psycopg2-binary==2.9.5`: PostgreSQL adapter
- Standard library: `json`, `logging`, `os`, `re`, `time`, `signal`

### Service Dependencies
- **Kafka**: Message source and destination
- **PostgreSQL**: Device parameters lookup
- **Zookeeper**: Kafka coordination (indirect)

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY processor.py .
CMD ["python", "processor.py"]
```

### Requirements.txt
```
kafka-python==2.0.2
psycopg2-binary==2.9.5
```

## Sample Device Parameters

```sql
-- Example device parameter entries
INSERT INTO device_parameters VALUES 
('f2-e4fd45f654be', 'access-control-mode', 'door-sensors', NULL, 'boolean_map', 'state', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'strike', '1', 'boolean', 'state', 1.0),
('f2-e4fd45f654be', 'sensor-mode', 'sensor', '3', 'hex_to_float', 'celsius', 0.1),
('f2-e4fd45f654be', 'alarm-mode', 'motion-sensor', '1', 'boolean', 'presence', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'reader', '1', 'raw_string', 'text', 1.0);
```

## Future Enhancements

1. **Parameter Caching**: Redis-based parameter cache
2. **Schema Validation**: JSON schema validation for messages
3. **Batch Processing**: Process multiple messages in batches
4. **Dead Letter Queue**: Handle failed messages
5. **Metrics Export**: Prometheus metrics integration
6. **Configuration Hot-reload**: Update parameters without restart
