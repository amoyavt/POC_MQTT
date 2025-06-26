# Kafka-TimescaleDB Sink Service

## Overview

The Kafka-TimescaleDB Sink service is the final stage of the data pipeline, responsible for persisting processed IoT measurements into TimescaleDB for long-term storage and analytics.

## Service Configuration

### Environment Variables
```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:29092      # Kafka cluster connection
KAFKA_INPUT_TOPIC=decoded_iot_data       # Input topic for processed data
TIMESCALE_HOST=timescaledb               # TimescaleDB connection
TIMESCALE_DB=timeseries                  # Database name
TIMESCALE_USER=ts_user                   # Database username
TIMESCALE_PASSWORD=ts_password           # Database password
TIMESCALE_PORT=5432                      # Database port
BATCH_SIZE=100                           # Batch size for inserts
BATCH_TIMEOUT=5                          # Batch timeout in seconds
```

### Docker Configuration
```yaml
kafka-timescale-sink:
  build: ./services/kafka_timescale_sink
  container_name: kafka-timescale-sink
  depends_on: [kafka, timescaledb]
  networks: [iot-network]
  restart: unless-stopped
```

## Implementation Details

### Core Functionality

**File**: `services/kafka_timescale_sink/sink.py`

#### Key Classes and Methods

- **`KafkaTimescaleSink`**: Main service class
- **`_convert_timestamp()`**: Handles various timestamp formats
- **`_extract_numeric_value()`**: Converts complex values to numeric
- **`_prepare_record()`**: Formats data for database insertion
- **`_insert_batch()`**: Batch insert with error handling

#### Message Processing Pipeline

1. **Consume**: Read processed messages from Kafka
2. **Convert**: Transform timestamps and extract numeric values
3. **Batch**: Accumulate messages for efficient insertion
4. **Insert**: Batch insert into TimescaleDB hypertable
5. **Commit**: Acknowledge successful processing

## Database Schema

### TimescaleDB Hypertable

**Table**: `iot_measurements`

```sql
CREATE TABLE iot_measurements (
    timestamp        TIMESTAMPTZ NOT NULL,
    device_id        VARCHAR(50) NOT NULL,
    connector_mode   VARCHAR(50),
    component_type   VARCHAR(50),
    component_id     VARCHAR(10),
    value           DECIMAL(15,6),
    unit            VARCHAR(20),
    raw_data        JSONB
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('iot_measurements', 'timestamp');

-- Create indexes for efficient queries
CREATE INDEX idx_iot_measurements_device_id ON iot_measurements (device_id, timestamp DESC);
CREATE INDEX idx_iot_measurements_component ON iot_measurements (component_type, timestamp DESC);
CREATE INDEX idx_iot_measurements_device_component ON iot_measurements (device_id, component_type, timestamp DESC);
```

### Data Type Conversion

#### Timestamp Handling
```python
# Input formats supported:
# - Unix timestamp (float): 1684681990.5434
# - ISO string: "2023-05-21T15:13:10.543400"
# - ISO with timezone: "2023-05-21T15:13:10.543400Z"

def _convert_timestamp(self, timestamp):
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp)
    elif isinstance(timestamp, str):
        return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    else:
        return datetime.now()  # Fallback
```

#### Value Extraction
```python
# Numeric value extraction from various data types:
# - Primitive numbers: 29.8 → 29.8
# - Booleans: True → 1.0, False → 0.0
# - Boolean maps: {"door-1": True, "door-2": False} → 1.0 (count of True)
# - Complex objects: Extract first numeric value found
# - Strings: Attempt float conversion

def _extract_numeric_value(self, value):
    if isinstance(value, (int, float)):
        return float(value)
    elif isinstance(value, bool):
        return float(value)
    elif isinstance(value, dict):
        if all(isinstance(v, bool) for v in value.values()):
            return float(sum(value.values()))  # Count True values
    # ... additional conversion logic
```

## Batch Processing

### Batch Configuration
- **Default Batch Size**: 100 records
- **Default Timeout**: 5 seconds
- **Optimization**: Reduces database round trips

### Batch Logic
```python
def _should_flush_batch(self):
    return (
        len(self.message_batch) >= self.batch_size or
        (time.time() - self.last_batch_time) >= self.batch_timeout
    )
```

### Batch Insertion
```python
# Using psycopg2's execute_batch for efficiency
execute_batch(
    cursor,
    """
    INSERT INTO iot_measurements 
    (timestamp, device_id, connector_mode, component_type, component_id, value, unit, raw_data)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """,
    records,
    page_size=self.batch_size
)
```

## Data Transformation Examples

### Example 1: Temperature Sensor Data

**Input** (from `decoded_iot_data`):
```json
{
  "timestamp": 1684681990.5434,
  "device_id": "f2-e4fd45f654be",
  "connector_mode": "sensor-mode",
  "component_type": "sensor",
  "component_id": "3",
  "value": 29.8,
  "unit": "celsius",
  "original_topic": "cmnd/f2-e4fd45f654be/sensor-mode/J1/sensor-3",
  "raw_data": {"timestamp": "2023-05-25 15:13:10.543400", "data": "0x12A"}
}
```

**Output** (TimescaleDB record):
```sql
INSERT INTO iot_measurements VALUES (
    '2023-05-21 15:13:10.543400+00',  -- timestamp
    'f2-e4fd45f654be',                -- device_id
    'sensor-mode',                    -- connector_mode
    'sensor',                         -- component_type
    '3',                              -- component_id
    29.8,                             -- value
    'celsius',                        -- unit
    '{"timestamp": "2023-05-25 15:13:10.543400", "data": "0x12A"}'  -- raw_data
);
```

### Example 2: Door Sensor Data

**Input**:
```json
{
  "timestamp": 1684681990.5434,
  "device_id": "f2-e4fd45f654be",
  "connector_mode": "access-control-mode",
  "component_type": "door-sensors",
  "component_id": null,
  "value": {"door-sensor-1": false, "door-sensor-2": true},
  "unit": "state",
  "raw_data": {"timestamp": "2023-05-26 18:34:04", "door-sensor-1": false, "door-sensor-2": true}
}
```

**Output**:
```sql
INSERT INTO iot_measurements VALUES (
    '2023-05-21 15:13:10.543400+00',
    'f2-e4fd45f654be',
    'access-control-mode',
    'door-sensors',
    NULL,
    1.0,  -- Count of True values (1 door open)
    'state',
    '{"timestamp": "2023-05-26 18:34:04", "door-sensor-1": false, "door-sensor-2": true}'
);
```

## Error Handling

### Database Connection Errors
- Automatic reconnection on connection loss
- Connection validation before operations
- Graceful degradation with logging

### Batch Processing Errors
- Clear failed batches to prevent infinite retry
- Log detailed error information
- Continue processing subsequent batches

### Data Validation Errors
- Handle malformed timestamps
- Skip records with critical missing data
- Log validation failures for debugging

## Performance Characteristics

### Throughput
- **Expected**: 1000+ records/second
- **Batch Optimization**: 10x improvement over single inserts
- **Scaling**: Single instance handles POC requirements

### Database Performance
- **Insert Time**: < 100ms per batch (100 records)
- **Index Strategy**: Optimized for time-series queries
- **Compression**: Automatic TimescaleDB compression for older data

### Resource Requirements
```yaml
resources:
  limits:
    memory: 512Mi
    cpu: 300m
  requests:
    memory: 256Mi
    cpu: 150m
```

## Kafka Integration

### Consumer Configuration
```python
KafkaConsumer(
    'decoded_iot_data',
    bootstrap_servers=servers,
    auto_offset_reset='latest',        # Start from newest messages
    enable_auto_commit=True,           # Commit offsets automatically
    group_id='timescale_sink_group',   # Consumer group
    value_deserializer=json.loads,     # JSON deserialization
    consumer_timeout_ms=1000           # Timeout for batch processing
)
```

### Polling Strategy
```python
# Non-blocking poll with timeout
message_batch = self.consumer.poll(timeout_ms=1000)

# Process all messages in current poll
for topic_partition, messages in message_batch.items():
    for message in messages:
        self._process_message(message)
```

## Monitoring and Logging

### Log Levels
- **INFO**: Batch insertions, service status
- **DEBUG**: Individual message processing
- **ERROR**: Database errors, connection failures
- **WARNING**: Data validation issues

### Key Metrics (Available via Logs)
- Records inserted per second
- Batch size utilization
- Database insertion latency
- Error rate by error type

## Operational Commands

### Service Management
```bash
# View sink logs
make logs-sink

# Restart sink only
docker-compose restart kafka-timescale-sink

# Check TimescaleDB data
make db-timescale
```

### Database Operations
```bash
# Access TimescaleDB
make db-timescale

# Query recent measurements
SELECT * FROM iot_measurements 
WHERE timestamp > NOW() - INTERVAL '1 hour' 
ORDER BY timestamp DESC LIMIT 100;

# Check hypertable stats
SELECT * FROM timescaledb_information.hypertables;
```

### Performance Monitoring
```sql
-- Query performance statistics
SELECT 
    device_id,
    component_type,
    COUNT(*) as measurement_count,
    AVG(value) as avg_value,
    MIN(timestamp) as first_measurement,
    MAX(timestamp) as last_measurement
FROM iot_measurements 
GROUP BY device_id, component_type 
ORDER BY measurement_count DESC;
```

## Dependencies

### Python Libraries
- `kafka-python==2.0.2`: Kafka consumer
- `psycopg2-binary==2.9.5`: PostgreSQL/TimescaleDB adapter
- Standard library: `json`, `logging`, `os`, `time`, `signal`, `datetime`

### Service Dependencies
- **Kafka**: Message source
- **TimescaleDB**: Data destination
- **Zookeeper**: Kafka coordination (indirect)

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY sink.py .
CMD ["python", "sink.py"]
```

### Requirements.txt
```
kafka-python==2.0.2
psycopg2-binary==2.9.5
```

## TimescaleDB Optimization

### Hypertable Configuration
```sql
-- Adjust chunk time interval (default: 7 days)
SELECT set_chunk_time_interval('iot_measurements', INTERVAL '1 day');

-- Enable compression for data older than 1 day
ALTER TABLE iot_measurements SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id,component_type'
);

SELECT add_compression_policy('iot_measurements', INTERVAL '1 day');
```

### Retention Policy
```sql
-- Automatically drop data older than 90 days
SELECT add_retention_policy('iot_measurements', INTERVAL '90 days');
```

## Troubleshooting

### Common Issues

1. **Batch Insertion Failures**
   ```sql
   -- Check for constraint violations
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   
   -- Verify table structure
   \d iot_measurements
   ```

2. **Consumer Lag**
   ```bash
   # Check consumer group status
   docker exec kafka kafka-consumer-groups.sh \
     --bootstrap-server localhost:9092 \
     --describe --group timescale_sink_group
   ```

3. **TimescaleDB Connection Issues**
   ```bash
   # Test database connection
   docker exec kafka-timescale-sink pg_isready -h timescaledb
   
   # Check TimescaleDB logs
   docker-compose logs timescaledb
   ```

## Future Enhancements

1. **Compression**: Enable TimescaleDB native compression
2. **Continuous Aggregates**: Pre-computed rollups for analytics
3. **Retention Policies**: Automatic data cleanup
4. **Upsert Logic**: Handle duplicate data gracefully
5. **Schema Evolution**: Support for schema changes
6. **Metrics Export**: Prometheus metrics integration
7. **Dead Letter Queue**: Failed message handling