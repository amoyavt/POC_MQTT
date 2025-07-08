# Services Implementation Management

This document provides a comprehensive analysis of the current services architecture and implementation plan for the complete IoT data pipeline.

## Architecture Analysis

### Current Services (Implemented ✅)

1. **Certificate Generation API** (`services/certgen_api/`) ✅
   - **Status**: Fully implemented and working
   - **Technology**: FastAPI + OpenSSL
   - **Purpose**: Generates X.509 certificates for mTLS authentication
   - **Network**: Internal HTTP API (port 8080)
   - **Security**: No auth required (internal service)

2. **MQTT Broker** (`services/mqtt_broker/`) ✅
   - **Status**: Fully implemented and working
   - **Technology**: Eclipse Mosquitto
   - **Purpose**: Secure MQTT message broker with mTLS
   - **Network**: MQTT port 8883 (mTLS), ACL-based authorization
   - **Security**: mTLS for IoT devices, certificate validation

3. **FACES2 Controllers Simulator** (`services/faces2_controllers/`) ✅
   - **Status**: Fully implemented and working
   - **Technology**: Python + Paho MQTT
   - **Purpose**: Simulates F2 Smart Controller IoT devices
   - **Network**: MQTT client with mTLS authentication
   - **Security**: Device certificates for mTLS authentication
   - **MAC Addresses**: Uses MAC addresses from `sql/init.sql` data (aa:bb:cc:dd:ee:01-04)

4. **Shared Models** (`services/shared/`) ✅
   - **Status**: Fully implemented and working
   - **Technology**: Pydantic models
   - **Purpose**: Data validation and transformation across services
   - **Network**: N/A (library)
   - **Security**: Data validation and sanitization

### Services to Implement (Missing from Current Architecture)

5. **MQTT-Kafka Connector** ❌
   - **Status**: Not implemented
   - **Technology**: Python + Paho MQTT + Kafka Python client
   - **Purpose**: Bridge MQTT messages to Kafka topics
   - **Network**: MQTT subscriber (internal), Kafka producer
   - **Security**: No auth required (internal service)

6. **Apache Kafka** ❌
   - **Status**: Not implemented
   - **Technology**: Apache Kafka + Zookeeper
   - **Purpose**: Stream processing and message queuing
   - **Network**: Internal Kafka protocol (port 9092)
   - **Security**: No auth required (internal service)

7. **Stream Processor** ❌
   - **Status**: Not implemented
   - **Technology**: Python + Kafka Python client
   - **Purpose**: Real-time data transformation and processing
   - **Network**: Kafka consumer/producer
   - **Security**: No auth required (internal service)

8. **PostgreSQL Database** ❌
   - **Status**: Not implemented
   - **Technology**: PostgreSQL
   - **Purpose**: Metadata storage for processor configuration
   - **Network**: PostgreSQL protocol (port 5432)
   - **Security**: No auth required (internal service)
   - **Schema**: Uses `sql/init.sql` with configurable schema name via `SCHEMA_PARAMS`
   - **Authentication**: Environment variables for user/password
   - **Database**: Configurable via `POSTGRES_DB` environment variable
   - **Data**: Includes MAC addresses matching `faces2_controllers` simulator

9. **Redis Cache** ❌
   - **Status**: Not implemented
   - **Technology**: Redis
   - **Purpose**: High-speed caching for processor lookups
   - **Network**: Redis protocol (port 6379)
   - **Security**: No auth required (internal service)

10. **TimescaleDB** ❌
    - **Status**: Not implemented
    - **Technology**: TimescaleDB (PostgreSQL extension)
    - **Purpose**: Time-series data storage and analytics
    - **Network**: PostgreSQL protocol (port 5432)
    - **Security**: No auth required (internal service)
    - **Schema**: Uses `sql/timescale_init.sql` with optimized structure
    - **Database**: Configurable via `TIMESCALE_DB` environment variable
    - **Table**: `decoded_data` (renamed from `iot_measurements`)
    - **Structure**: Minimal columns for space optimization: `device_id`, `datapoint_id`, `value`, `timestamp`

11. **Kafka-TimescaleDB Sink** ❌
    - **Status**: Not implemented
    - **Technology**: Python + Kafka + TimescaleDB
    - **Purpose**: Batch insert processed data into TimescaleDB
    - **Network**: Kafka consumer, TimescaleDB client
    - **Security**: No auth required (internal service)

## Implementation Plan

### Phase 1: Core Infrastructure (Priority: High)

**1. Apache Kafka + Zookeeper Setup**
- **Location**: `services/kafka/`
- **Implementation**: Docker Compose with Kafka + Zookeeper
- **Configuration**: 
  - Kafka broker on port 9092
  - Zookeeper on port 2181
  - Auto-create topics enabled
  - Internal network communication
- **Dependencies**: None

**2. MQTT-Kafka Connector**
- **Location**: `services/mqtt_kafka_connector/`
- **Implementation**: Python service
- **Functionality**:
  - Subscribe to MQTT topics: `stat/+/+/+/+`, `tele/+/+/+/+`
  - Transform MQTT messages to Kafka format
  - Publish to Kafka topic: `raw-iot-data`
  - Use shared models for data validation
- **Dependencies**: mqtt-broker, kafka

### Phase 2: Data Storage (Priority: High)

**3. PostgreSQL Database**
- **Location**: `services/postgresql/`
- **Implementation**: PostgreSQL Docker container
- **Configuration**:
  - Database: Configurable via `POSTGRES_DB` environment variable
  - Port: 5432
  - Schema: Configurable via `SCHEMA_PARAMS` environment variable
  - Authentication: `POSTGRES_USER` and `POSTGRES_PASSWORD` environment variables
  - Initialization: Uses `sql/init.sql` for schema setup
  - Data: Includes MAC addresses for `faces2_controllers` compatibility
  - Volume mount for persistence
- **Dependencies**: None

**4. Redis Cache**
- **Location**: `services/redis/`
- **Implementation**: Redis Docker container
- **Configuration**:
  - Port: 6379
  - Volume mount for persistence
  - Memory optimization settings
- **Dependencies**: None

**5. TimescaleDB**
- **Location**: `services/timescaledb/`
- **Implementation**: TimescaleDB Docker container
- **Configuration**:
  - Database: Configurable via `TIMESCALE_DB` environment variable
  - Port: 5432 (different from PostgreSQL)
  - Schema: Uses `sql/timescale_init.sql`
  - Table: `decoded_data` (space-optimized structure)
  - Columns: `device_id`, `datapoint_id`, `value`, `timestamp` (minimal for big data)
  - Hypertables for time-series optimization
  - Volume mount for persistence
- **Dependencies**: None

### Phase 3: Data Processing (Priority: Medium)

**6. Stream Processor**
- **Location**: `services/stream_processor/`
- **Implementation**: Python service
- **Functionality**:
  - Consume from Kafka topic: `raw-iot-data`
  - Parse hex sensor data using shared models
  - Transform to structured format
  - Map MAC addresses to `device_id` using PostgreSQL metadata
  - Map sensor labels to `datapoint_id` using PostgreSQL metadata
  - Cache lookups via Redis
  - Produce to Kafka topic: `processed-iot-data`
  - Output format: `{device_id, datapoint_id, value, timestamp}`
- **Dependencies**: kafka, postgresql, redis

**7. Kafka-TimescaleDB Sink**
- **Location**: `services/kafka_timescale_sink/` (already exists)
- **Implementation**: Enhance existing service
- **Functionality**:
  - Consume from Kafka topic: `processed-iot-data`
  - Batch processing (configurable batch size)
  - Bulk insert to TimescaleDB `decoded_data` table
  - Optimized for space efficiency and performance
  - Error handling and retry logic
- **Dependencies**: kafka, timescaledb

## Data Model Updates

### TimescaleDB Schema (`sql/timescale_init.sql`)
**Table Rename**: `iot_measurements` → `decoded_data`

**New Structure** (Space-Optimized):
```sql
CREATE TABLE IF NOT EXISTS decoded_data (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id INTEGER NOT NULL,
    datapoint_id INTEGER NOT NULL,
    value DOUBLE PRECISION,
    PRIMARY KEY (timestamp, device_id, datapoint_id)
);
```

### Shared Models (`services/shared/models.py`)
**Model Update**: Update `IotMeasurement` to support new structure
- Map MAC addresses to `device_id` integers
- Map sensor labels to `datapoint_id` integers
- Remove redundant fields for space optimization
- Maintain backward compatibility during transition

### Documentation (`docs/data-models.md`)
**Updates Required**:
- Update ERD to show `decoded_data` table
- Document new optimized structure
- Show relationships between PostgreSQL metadata and TimescaleDB data
- Update field descriptions for space optimization

## Communication Protocols

### Security Model

**mTLS Authentication** (Only for IoT Devices):
- **FACES2 Controllers** → **MQTT Broker**: mTLS with device certificates
- **Reason**: Simulates real-world IoT devices that need secure authentication
- **MAC Addresses**: Must match those in `sql/init.sql` for proper metadata mapping

**Internal Communication** (No Authentication):
- All internal services communicate without authentication
- **Reason**: Services run on same host in trusted environment
- **Network**: Docker bridge network (`iot-network`)

### Data Flow Protocols

1. **MQTT → Kafka**: 
   - Protocol: MQTT (port 8883) → Kafka (port 9092)
   - Format: JSON messages with timestamp and hex data
   - Topics: `stat/f2-*/sensor-mode/*/sensor-*` → `raw-iot-data`

2. **Kafka → Processing**:
   - Protocol: Kafka consumer/producer
   - Format: Structured JSON with parsed sensor values
   - Topics: `raw-iot-data` → `processed-iot-data`
   - Transformation: MAC → device_id, sensor_label → datapoint_id

3. **Processing → Storage**:
   - Protocol: PostgreSQL (metadata), Redis (cache), TimescaleDB (time-series)
   - Format: Optimized structure for space efficiency
   - Target: `decoded_data` table with minimal columns
   - Batching: Configurable batch sizes for optimal performance

## Docker Compose Integration

### New Services to Add

```yaml
services:
  # Infrastructure
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    
  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on: [zookeeper]
    
  postgresql:
    image: postgres:15
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
      - ./data/postgresql:/var/lib/postgresql/data
    
  redis:
    image: redis:7-alpine
    volumes:
      - ./data/redis:/data
    
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      - POSTGRES_DB=${TIMESCALE_DB}
    volumes:
      - ./sql/timescale_init.sql:/docker-entrypoint-initdb.d/init.sql
      - ./data/timescaledb:/var/lib/postgresql/data
    
  # Application Services
  mqtt-kafka-connector:
    build: services/mqtt_kafka_connector/
    depends_on: [mqtt-broker, kafka]
    
  stream-processor:
    build: services/stream_processor/
    depends_on: [kafka, postgresql, redis]
    environment:
      - SCHEMA_PARAMS=${SCHEMA_PARAMS}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    
  kafka-timescale-sink:
    build: services/kafka_timescale_sink/
    depends_on: [kafka, timescaledb]
    environment:
      - TIMESCALE_DB=${TIMESCALE_DB}
```

### Environment Variables

```bash
# Database Configuration
POSTGRES_USER=iot_user
POSTGRES_PASSWORD=iot_password
POSTGRES_DB=iot_metadata
TIMESCALE_DB=iot_timeseries
SCHEMA_PARAMS=iot_schema

# Kafka Configuration
KAFKA_BROKERS=kafka:9092
KAFKA_RAW_TOPIC=raw-iot-data
KAFKA_PROCESSED_TOPIC=processed-iot-data

# Database Connections
POSTGRES_HOST=postgresql
TIMESCALE_HOST=timescaledb

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Processing Configuration
BATCH_SIZE=1000
PROCESSING_INTERVAL=5
```

## Data Consistency Requirements

### MAC Address Mapping
- **Source**: `faces2_controllers` simulator uses MAC addresses: `aa:bb:cc:dd:ee:01-04`
- **Metadata**: `sql/init.sql` must include matching MAC addresses in Device table
- **Processing**: Stream processor maps MAC → device_id using PostgreSQL lookup

### Space Optimization
- **TimescaleDB**: Use integer IDs instead of string labels
- **Compression**: Enable TimescaleDB compression for older data
- **Indexing**: Optimize indexes for `device_id` and `datapoint_id` queries
- **Retention**: Configure data retention policies for space management

## Implementation Priority

### Immediate (Phase 1)
1. Kafka + Zookeeper setup
2. MQTT-Kafka connector implementation
3. Basic data flow testing

### Short-term (Phase 2)
1. PostgreSQL setup with updated `sql/init.sql`
2. TimescaleDB setup with `decoded_data` table
3. Redis setup
4. Update shared models for new structure

### Medium-term (Phase 3)
1. Stream processor with MAC→device_id mapping
2. Kafka-TimescaleDB sink with space optimization
3. Update documentation
4. End-to-end testing

## Testing Strategy

### Unit Testing
- Each service has independent unit tests
- Mock external dependencies
- Test data transformation logic
- Validate MAC address mapping

### Integration Testing
- Test service-to-service communication
- Validate data flow through pipeline
- Test MAC address consistency
- Verify space optimization

### Performance Testing
- Measure throughput and latency
- Test batch processing optimization
- Monitor storage space usage
- Validate TimescaleDB compression

## Monitoring and Observability

### Logging
- Structured logging across all services
- Centralized log aggregation
- Error tracking and alerting
- MAC address mapping validation

### Metrics
- Service health checks
- Data throughput metrics
- Processing latency monitoring
- Storage space utilization
- Cache hit rates

### Health Checks
- HTTP health endpoints for each service
- Dependency health validation
- Database connectivity checks
- Automated service recovery

## Notes

- All services use the same Docker network (`iot-network`)
- No authentication between internal services (trusted environment)
- Only FACES2 controllers require mTLS (simulating real IoT devices)
- MAC addresses must be consistent between simulator and database
- TimescaleDB optimized for space efficiency with minimal columns
- Shared models updated to support new `decoded_data` structure
- Database names configurable via environment variables (`POSTGRES_DB`, `TIMESCALE_DB`)
- PostgreSQL schema configurable via `SCHEMA_PARAMS`
- Database authentication via environment variables
- Configuration via environment variables
- Emphasis on easy deployment and maintenance