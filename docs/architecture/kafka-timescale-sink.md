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

## TimescaleDB Guide

### What is TimescaleDB?

**TimescaleDB** is a time-series database built on PostgreSQL that provides:
- **Automatic partitioning** by time intervals (hypertables)
- **Compression** for older data to save storage
- **Continuous aggregates** for real-time analytics
- **Retention policies** for automated data cleanup
- **All PostgreSQL features** (SQL, indexes, transactions)

**📖 Official Documentation**: https://docs.timescale.com/

### Why We Use TimescaleDB

| Feature | Benefit for IoT Data |
|---------|---------------------|
| **Hypertables** | Automatic partitioning handles millions of IoT measurements |
| **Compression** | Reduces storage costs by 90%+ for older data |
| **Time-based queries** | Optimized for "last 24 hours" type queries |
| **PostgreSQL compatibility** | Use existing SQL knowledge and tools |
| **Horizontal scaling** | Can scale across multiple nodes |

### Hypertables (Automatic Partitioning)

TimescaleDB automatically partitions data by time:

```sql
-- View chunk information
SELECT * FROM timescaledb_information.chunks 
WHERE hypertable_name = 'iot_measurements';

-- Typical chunk size: 7 days
-- Automatic creation as data arrives
```

### Compression Features

Our setup includes compression for older data:

```sql
-- Enable compression (already configured)
ALTER TABLE iot_measurements SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Automatic compression after 1 day
SELECT add_compression_policy('iot_measurements', INTERVAL '1 day');
```

**Compression Benefits**:
- **90%+ storage reduction** for older data
- **Faster queries** for compressed data
- **Automatic background process**

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
-- Automatically delete data older than 30 days
SELECT add_retention_policy('iot_measurements', INTERVAL '30 days');

-- Or for longer retention:
SELECT add_retention_policy('iot_measurements', INTERVAL '90 days');
```

## Database Operations & Monitoring

### Database Connection

```bash
# Connect to TimescaleDB
make db-timescale

# Or manually:
docker exec -it timescale-db psql -U ts_user -d timeseries
```

### System Health Checks

```sql
-- Check hypertable status
SELECT * FROM timescaledb_information.hypertables;

-- Check chunk information
SELECT 
    chunk_schema,
    chunk_name,
    range_start,
    range_end,
    compressed_chunk_id IS NOT NULL AS is_compressed
FROM timescaledb_information.chunks 
WHERE hypertable_name = 'iot_measurements'
ORDER BY range_start DESC
LIMIT 10;

-- Check compression status
SELECT 
    pg_size_pretty(before_compression_bytes) AS before,
    pg_size_pretty(after_compression_bytes) AS after,
    round(after_compression_bytes::NUMERIC/before_compression_bytes::NUMERIC*100, 2) AS ratio
FROM timescaledb_information.compression_settings
WHERE hypertable_name = 'iot_measurements';
```

### Data Ingestion Monitoring

```sql
-- Recent data ingestion rate
SELECT 
    date_trunc('minute', timestamp) AS minute,
    COUNT(*) AS records_per_minute
FROM iot_measurements 
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC
LIMIT 10;

-- Data distribution by device
SELECT 
    device_id,
    COUNT(*) AS total_records,
    MIN(timestamp) AS first_record,
    MAX(timestamp) AS latest_record
FROM iot_measurements
GROUP BY device_id
ORDER BY total_records DESC;
```

### Common Query Examples

```sql
-- Get latest readings for a device
SELECT * FROM iot_measurements 
WHERE device_id = 'f2-e4fd45f654be'
ORDER BY timestamp DESC
LIMIT 10;

-- Average temperature over last hour
SELECT 
    date_trunc('minute', timestamp) AS minute,
    AVG(value) AS avg_temp
FROM iot_measurements 
WHERE component_type = 'Temperature'
  AND timestamp > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute;

-- Device activity summary
SELECT 
    device_id,
    component_type,
    COUNT(*) AS readings,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value
FROM iot_measurements
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY device_id, component_type
ORDER BY device_id, component_type;
```

### Maintenance Operations

```sql
-- Manual compression of older chunks
SELECT compress_chunk(i) FROM show_chunks('iot_measurements', older_than => INTERVAL '1 day') i;

-- View database size
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'timeseries';
```

## Troubleshooting

### Common Issues

#### 1. Connection Problems

**Symptom**: Sink service can't connect to TimescaleDB
```
Error: FATAL: database "timeseries" does not exist
```

**Solution**:
```bash
# Check if TimescaleDB container is running
docker-compose ps timescaledb

# Check initialization logs
docker-compose logs timescaledb

# Verify database exists
docker exec timescale-db psql -U ts_user -l
```

#### 2. Batch Insert Failures

**Symptom**: Sink logs show validation errors
```
Data validation failed: [ValidationError] - for message: {...}
```

**Solution**:
```bash
# Check message format in Kafka
make kafka-decoded

# Verify shared model validation
docker-compose logs kafka-timescale-sink | grep -A5 -B5 "validation failed"
```

**Database Constraint Issues**:
```sql
-- Check for constraint violations
SELECT * FROM pg_stat_activity WHERE state = 'active';

-- Verify table structure
\d iot_measurements
```

#### 3. Consumer Lag
```bash
# Check consumer group status
docker exec kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group timescale_sink_group
```

#### 4. TimescaleDB Connection Issues
```bash
# Test database connection
docker exec kafka-timescale-sink pg_isready -h timescaledb

# Check TimescaleDB logs
docker-compose logs timescaledb
```

#### 5. Performance Issues

**Symptom**: Slow queries or high CPU usage

**Diagnosis**:
```sql
-- Check slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables 
WHERE schemaname = 'public';
```

**Solutions**:
1. **Enable compression** for older data
2. **Add indexes** for common query patterns
3. **Increase batch size** in sink configuration
4. **Check retention policies** to prevent unlimited growth

#### 6. Data Quality Issues

**Symptom**: Missing or incorrect data

**Diagnosis**:
```sql
-- Check for data gaps
SELECT 
    device_id,
    component_type,
    timestamp,
    LAG(timestamp) OVER (PARTITION BY device_id, component_type ORDER BY timestamp) AS prev_timestamp,
    timestamp - LAG(timestamp) OVER (PARTITION BY device_id, component_type ORDER BY timestamp) AS gap
FROM iot_measurements
WHERE timestamp > NOW() - INTERVAL '1 hour'
ORDER BY device_id, component_type, timestamp;

-- Check for invalid values
SELECT 
    device_id,
    component_type,
    COUNT(*) AS total,
    COUNT(value) AS valid_values,
    COUNT(*) - COUNT(value) AS null_values
FROM iot_measurements
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY device_id, component_type;
```

## Performance Optimization

### Batch Configuration

**File**: `services/kafka_timescale_sink/sink.py`

```python
# Optimize batch settings
self.batch_size = int(os.getenv('BATCH_SIZE', '1000'))  # Increase from 100
self.batch_timeout = int(os.getenv('BATCH_TIMEOUT', '10'))  # Less frequent
```

### Connection Pooling

```python
# Add connection pooling (recommended)
from psycopg2.pool import ThreadedConnectionPool

self.db_pool = ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=self.ts_host,
    port=self.ts_port,
    database=self.ts_db,
    user=self.ts_user,
    password=self.ts_password
)
```

### Bulk Insert Optimization

```python
# Use COPY instead of INSERT for better performance
import io
import csv

def bulk_insert_with_copy(self, records):
    csv_data = io.StringIO()
    csv_writer = csv.writer(csv_data)
    
    for record in records:
        csv_writer.writerow(record)
    
    csv_data.seek(0)
    
    with self.db_connection.cursor() as cursor:
        cursor.copy_from(
            csv_data,
            'iot_measurements',
            columns=('timestamp', 'device_id', 'connector_mode', 'component_type', 'pin_position', 'value', 'unit', 'topic'),
            sep=','
        )
```

### Monitoring Views

```sql
-- Create monitoring views
CREATE VIEW recent_activity AS
SELECT 
    date_trunc('minute', timestamp) AS minute,
    device_id,
    COUNT(*) AS records
FROM iot_measurements
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY minute, device_id
ORDER BY minute DESC;

-- Performance metrics
CREATE VIEW compression_stats AS
SELECT 
    chunk_name,
    pg_size_pretty(before_compression_bytes) AS before,
    pg_size_pretty(after_compression_bytes) AS after,
    round(after_compression_bytes::NUMERIC/before_compression_bytes::NUMERIC*100, 2) AS compression_ratio
FROM timescaledb_information.compression_settings
WHERE hypertable_name = 'iot_measurements';
```

## Future Enhancements

1. **Advanced Compression**: Multi-level compression strategies
2. **Continuous Aggregates**: Pre-computed rollups for analytics
3. **Advanced Retention**: Tiered storage policies
4. **Upsert Logic**: Handle duplicate data gracefully
5. **Schema Evolution**: Support for schema changes
6. **Metrics Export**: Prometheus metrics integration
7. **Dead Letter Queue**: Failed message handling
8. **Multi-Node Scaling**: Distributed TimescaleDB setup

## 📚 External Resources

- **[TimescaleDB Documentation](https://docs.timescale.com/)**
- **[TimescaleDB Best Practices](https://docs.timescale.com/timescaledb/latest/best-practices/)**
- **[PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)**
- **[Time-Series Data Modeling](https://docs.timescale.com/timescaledb/latest/how-to-guides/data-modeling/)**
