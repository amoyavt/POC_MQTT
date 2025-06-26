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

- **`IotMeasurement`**: A Pydantic model that defines the data structure, handles validation, and data conversion.
- **`KafkaTimescaleSink`**: The main service class that orchestrates data consumption and persistence.
- **`_build_insert_statement()`**: Dynamically generates the `INSERT` SQL query from the `IotMeasurement` model.
- **`_prepare_record()`**: Validates incoming messages against the Pydantic model.
- **`_insert_batch()`**: Executes the batch insertion into the database.

#### Message Processing Pipeline

1.  **Consume**: Reads messages from the `decoded_iot_data` Kafka topic.
2.  **Validate & Prepare**: Each message is parsed and validated by the `IotMeasurement` Pydantic model. This step also handles data type conversions (e.g., for timestamps and numeric values).
3.  **Batch**: Valid records are accumulated in a list for efficient batch processing.
4.  **Insert**: The batch is inserted into the TimescaleDB `iot_measurements` hypertable using a dynamically generated `INSERT` statement.

## Database Schema

### TimescaleDB Hypertable

**Table**: `iot_measurements`

The schema is defined in `sql/timescale_init.sql` and is created when the system starts.

```sql
CREATE TABLE IF NOT EXISTS iot_measurements (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    connector_mode VARCHAR(50) NOT NULL,
    component_type VARCHAR(50) NOT NULL,
    pin_position VARCHAR(10),
    value DOUBLE PRECISION,
    unit VARCHAR(20),
    topic VARCHAR(255),
    PRIMARY KEY (timestamp, device_id, connector_mode, component_type, pin_position)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('iot_measurements', 'timestamp', if_not_exists => TRUE);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_iot_device_id ON iot_measurements (device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_iot_component ON iot_measurements (component_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_iot_mode ON iot_measurements (connector_mode, timestamp DESC);
```

## Data Validation with Pydantic

Data integrity is enforced by a `pydantic.BaseModel`, which ensures that every record inserted into the database conforms to the expected schema.

### Pydantic Model Definition

```python
class IotMeasurement(BaseModel):
    """Pydantic model for an IoT measurement record."""
    timestamp: datetime
    device_id: str = Field(..., alias='mac_address')
    connector_mode: str = Field('unknown', alias='mode')
    component_type: str = Field('unknown', alias='data_point_label')
    pin_position: str = Field('-1', alias='pin')
    value: Optional[float] = None
    unit: str = ''
    topic: str = Field('', alias='original_topic')

    @validator('timestamp', pre=True)
    def convert_timestamp(cls, v):
        # ... timestamp conversion logic ...

    @validator('value', pre=True)
    def convert_value_to_float(cls, v):
        # ... value conversion logic ...
```

This model automatically handles:
-   **Validation**: Type checking for all fields.
-   **Alias Mapping**: Maps incoming JSON fields (e.g., `mac_address`) to the model's field names (e.g., `device_id`).
-   **Data Conversion**: Custom validators handle complex conversions for timestamps and numeric values.
-   **Default Values**: Provides default values for optional fields.

## Batch Processing

### Dynamic SQL Generation

The `INSERT` statement is generated dynamically from the `IotMeasurement` model's fields, ensuring it always stays in sync with the data structure.

```python
def _build_insert_statement(self) -> str:
    """Dynamically build the INSERT statement from the Pydantic model."""
    fields = list(IotMeasurement.__fields__.keys())
    columns = ', '.join(fields)
    placeholders = ', '.join(['%s'] * len(fields))
    return f"INSERT INTO iot_measurements ({columns}) VALUES ({placeholders})"
```

### Batch Insertion

The sink uses `psycopg2.extras.execute_batch` for high-performance batch inserts.

```python
# Using psycopg2's execute_batch for efficiency
execute_batch(
    cursor,
    self._insert_statement, # The dynamically generated SQL
    records,
    page_size=self.batch_size
)
```

## Error Handling

-   **Data Validation Errors**: If a message fails Pydantic validation (`ValidationError`), it is logged and skipped, preventing malformed data from entering the database or halting the pipeline.
-   **Database Errors**: Connection errors and batch insertion failures are logged, and the batch is cleared to prevent repeated retries on failing data.

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
docker-compose logs -f kafka-timescale-sink

# Restart sink only
docker-compose restart kafka-timescale-sink

# Check TimescaleDB data
docker exec -it timescale-db psql -U ts_user -d timeseries
```

### Database Operations
```bash
# Access TimescaleDB
docker exec -it timescale-db psql -U ts_user -d timeseries

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
-   `kafka-python==2.0.2`: Kafka consumer client.
-   `psycopg2-binary==2.9.5`: PostgreSQL/TimescaleDB adapter.
-   `pydantic==2.7.1`: For data validation and settings management.

### Service Dependencies
-   **Kafka**: The message source.
-   **TimescaleDB**: The data destination.

## Requirements.txt

```
kafka-python==2.0.2
psycopg2-binary==2.9.5
pydantic==2.7.1
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
