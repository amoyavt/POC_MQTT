# Shared Models

This directory contains shared Pydantic models used across multiple services in the IoT Architecture PoC.

## IotMeasurement Model

The `IotMeasurement` model provides a standardized schema for IoT sensor data flowing through the Kafka pipeline from the data processor to TimescaleDB.

### Usage

```python
from shared.models import IotMeasurement

# Parse raw message data
data = {
    'timestamp': 1640995200,
    'mac_address': 'f2-e4fd45f654be',
    'mode': 'sensor-mode',
    'data_point_label': 'temperature',
    'pin': 3,
    'value': '27.93 °C',
    'unit': '°C',
    'original_topic': 'data/f2-e4fd45f654be/sensor-mode/1/3'
}

# Validate and convert
measurement = IotMeasurement.parse_obj(data)
print(measurement.value)  # 27.93 (extracted from string)
print(measurement.pin_position)  # "3" (converted to string)
```

### Key Features

1. **Field Mapping**: Uses Pydantic aliases to map incoming JSON fields:
   - `mac_address` → `device_id`
   - `mode` → `connector_mode`
   - `data_point_label` → `datapoint_label`
   - `pin` → `pin_position`
   - `original_topic` → `topic`

2. **Data Validation & Conversion**:
   - **Timestamp**: Converts Unix timestamps and ISO strings to datetime objects
   - **Pin Position**: Ensures pin positions are strings (database requirement)
   - **Numeric Values**: Extracts numbers from strings with units (e.g., "27.93 °C" → 27.93)

3. **Robust Error Handling**: 
   - Provides sensible defaults for missing fields
   - Logs warnings for unparseable values
   - Falls back gracefully on conversion errors

### Services Using This Model

- **Data Processor**: Validates outgoing messages before sending to Kafka
- **Kafka-TimescaleDB Sink**: Validates incoming messages before database insertion

### Schema Compatibility

The model is designed to match the TimescaleDB `iot_measurements` table schema:

```sql
CREATE TABLE iot_measurements (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id TEXT NOT NULL,
    connector_mode TEXT,
    datapoint_label TEXT,
    pin_position TEXT,
    value DOUBLE PRECISION,
    unit TEXT,
    topic TEXT
);
```

### Dependencies

- `pydantic>=1.8.0,<2.0.0`

### Integration with Docker

Services using shared models should include them in their Dockerfile:

```dockerfile
# Copy shared models
COPY ../../shared /app/shared

# Install shared dependencies
RUN pip install --no-cache-dir -r /app/shared/requirements.txt
```

And import them in Python:

```python
import sys
sys.path.append('/app/shared')
from models import IotMeasurement
```
