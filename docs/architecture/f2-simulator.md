# F2 Device Simulator Service

## Overview

The F2 Device Simulator service emulates multiple F2 Smart Controller IoT devices, generating realistic MQTT messages for testing and development of the IoT data pipeline.

## Service Configuration

### Environment Variables
```bash
MQTT_BROKER=mosquitto:1883        # MQTT broker connection
PUBLISH_INTERVAL=5                # Seconds between message publishes
```

### Docker Configuration
```yaml
f2-simulator:
  build: ./services/f2_simulator
  container_name: f2-simulator
  depends_on: [mosquitto]
  networks: [iot-network]
  restart: unless-stopped
```

## Implementation Details

### Core Functionality

**File**: `services/f2_simulator/simulator.py`

#### Key Classes and Methods

- **`F2DeviceSimulator`**: Main simulator class
- **`_generate_*_data()`**: Data generators for each component type
- **`_get_topics_for_mode()`**: Topic generation based on device mode
- **`_publish_device_data()`**: Publishes data for all simulated devices

#### Simulated Devices
```python
self.devices = [
    {
        'mac': 'e4fd45f654be',
        'modes': ['access-control-mode', 'alarm-mode', 'sensor-mode']
    },
    {
        'mac': 'abc123def456', 
        'modes': ['sensor-mode', 'access-control-mode']
    }
]
```

## Device Modes and Components

### Access Control Mode
**Components**:
- Door Sensors
- Electric Strikes
- Exit Buttons
- QR/NFC Readers

**Topics**:
```
cmnd/f2-{MAC}/access-control-mode/J1/door-sensors
cmnd/f2-{MAC}/access-control-mode/J1/strike-1
cmnd/f2-{MAC}/access-control-mode/J1/exit-buttons
cmnd/f2-{MAC}/access-control-mode/J1/reader-1
```

### Alarm Mode
**Components**:
- Motion Sensors
- Sirens

**Topics**:
```
cmnd/f2-{MAC}/alarm-mode/J1/motion-sensor-1
cmnd/f2-{MAC}/alarm-mode/J1/siren-1
```

### Sensor Mode
**Components**:
- RS-485 Sensors (Temperature, Humidity, Pressure)

**Topics**:
```
cmnd/f2-{MAC}/sensor-mode/J1/sensor-1
cmnd/f2-{MAC}/sensor-mode/J1/sensor-2
cmnd/f2-{MAC}/sensor-mode/J1/sensor-3
```

## Data Generation

### Door Sensors
```python
def _generate_door_sensor_data(self):
    return {
        "timestamp": datetime.now().isoformat(),
        "door-sensor-1": random.choice([True, False]),
        "door-sensor-2": random.choice([True, False])
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-26T18:34:04.928538",
  "door-sensor-1": false,
  "door-sensor-2": true
}
```

### Electric Strike
```python
def _generate_strike_data(self):
    return {
        "timestamp": datetime.now().isoformat(),
        "status": random.choice([True, False])
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-26T18:34:04.928538",
  "status": true
}
```

### Exit Buttons
```python
def _generate_exit_buttons_data(self):
    return {
        "timestamp": datetime.now().isoformat(),
        "exit-button-1": random.choice([True, False]),
        "exit-button-2": random.choice([True, False])
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-26T18:34:04.928538",
  "exit-button-1": false,
  "exit-button-2": true
}
```

### Motion Sensor
```python
def _generate_motion_sensor_data(self):
    return {
        "timestamp": datetime.now().isoformat(),
        "status": random.choice([True, False])
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-26T18:34:04.928538",
  "status": false
}
```

### Siren
```python
def _generate_siren_data(self):
    return {
        "timestamp": datetime.now().isoformat(),
        "status": random.choice([True, False])
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-26T18:34:04.928538",
  "status": true
}
```

### QR/NFC Reader
```python
def _generate_reader_data(self):
    sample_data = [
        "b'\"Hello World\"'",
        "b'\"USER12345\"'",
        "b'\"ACCESS_CARD_789\"'",
        "b'\"QR_CODE_ABC123\"'"
    ]
    return {
        "timestamp": datetime.now().isoformat(),
        "data": random.choice(sample_data)
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-26T17:24:28.808888",
  "data": "b'\"ACCESS_CARD_789\"'"
}
```

### RS-485 Sensors
```python
def _generate_rs485_sensor_data(self):
    if random.choice([True, False]):
        # Temperature sensor (celsius * 10)
        temp_celsius = random.uniform(15.0, 35.0)
        hex_value = hex(int(temp_celsius * 10))
    else:
        # Humidity/pressure sensor
        value = random.uniform(300, 1200)
        hex_value = hex(int(value))
    
    return {
        "timestamp": datetime.now().isoformat(),
        "data": hex_value
    }
```

**Example Output**:
```json
{
  "timestamp": "2023-05-25T15:13:10.543400",
  "data": "0x12a"
}
```

## Publishing Strategy

### Random Selection Logic
```python
def _publish_device_data(self):
    for device in self.devices:
        # Randomly select a mode for this iteration
        mode = random.choice(device['modes'])
        topics = self._get_topics_for_mode(device['mac'], mode)
        
        # Publish to a random subset of topics
        num_topics = random.randint(1, min(3, len(topics)))
        selected_topics = random.sample(topics, num_topics)
        
        for topic in selected_topics:
            # Generate and publish data
```

### Publishing Behavior
- **Interval**: Configurable (default 5 seconds)
- **Topics per Device**: 1-3 random topics per publish cycle
- **Mode Selection**: Random mode selection per device per cycle
- **Component Selection**: Random subset of components for selected mode

## MQTT Integration

### Connection Settings
```python
self.mqtt_client = mqtt.Client()
self.mqtt_client.on_connect = self._on_mqtt_connect

# Connection parameters
broker_parts = self.mqtt_broker.split(':')
host = broker_parts[0]
port = int(broker_parts[1]) if len(broker_parts) > 1 else 1883

self.mqtt_client.connect(host, port, 60)
self.mqtt_client.loop_start()
```

### Message Publishing
```python
# Publish with QoS 0 (fire and forget)
self.mqtt_client.publish(topic, json.dumps(data))
```

## Realistic Data Patterns

### Component Behavior Simulation

1. **Door Sensors**: Simulate door open/close events
2. **Electric Strikes**: Simulate access control activations
3. **Motion Sensors**: Simulate presence detection
4. **Temperature Sensors**: Generate realistic temperature ranges (15-35°C)
5. **Access Readers**: Simulate various card/QR code formats

### Temporal Patterns
- **Variable Intervals**: Random component selection creates realistic usage patterns
- **State Changes**: Boolean components simulate real state transitions
- **Sensor Drift**: Numeric sensors include realistic value variations

## Operational Commands

### Service Management
```bash
# View simulator logs
docker-compose logs -f f2-simulator

# Restart simulator only
docker-compose restart f2-simulator

# Monitor MQTT messages
mosquitto_sub -h localhost -t "cmnd/#" -v
```

### Configuration Adjustments
```bash
# Change publish interval (requires restart)
docker-compose down f2-simulator
# Edit environment variable in docker-compose.yml
# PUBLISH_INTERVAL=10
docker-compose up -d f2-simulator
```

## Dependencies

### Python Libraries
- `paho-mqtt==1.6.1`: MQTT client
- Standard library: `json`, `logging`, `os`, `random`, `time`, `datetime`, `signal`

### Service Dependencies
- **Mosquitto**: MQTT message destination

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY simulator.py .
CMD ["python", "simulator.py"]
```

### Requirements.txt
```
paho-mqtt==1.6.1
```

## Testing and Validation

### Message Validation
```bash
# Monitor generated messages
mosquitto_sub -h localhost -t "cmnd/#" -v

# Check message format
mosquitto_sub -h localhost -t "cmnd/#" -v | head -20
```

### Data Pipeline Testing
```bash
# Check if messages reach Kafka
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_iot_data --from-beginning

# Verify processing
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic decoded_iot_data --from-beginning

# Validate database storage
docker exec -it timescale-db psql -U ts_user -d timeseries
```

## Performance Characteristics

### Message Generation Rate
- **Default**: ~10-20 messages per minute (2 devices, 5s interval)
- **Configurable**: Adjust via `PUBLISH_INTERVAL`
- **Scalable**: Add more devices to `self.devices` array

### Resource Usage
```yaml
resources:
  limits:
    memory: 128Mi
    cpu: 100m
  requests:
    memory: 64Mi
    cpu: 50m
```

## Troubleshooting

### Common Issues

1. **MQTT Connection Failed**
   ```bash
   # Check mosquitto status
   docker-compose ps mosquitto
   
   # Test MQTT connectivity
   docker exec f2-simulator ping mosquitto
   ```

2. **No Messages Generated**
   ```bash
   # Check simulator logs
   docker-compose logs -f f2-simulator
   
   # Verify MQTT broker is receiving messages
   mosquitto_sub -h localhost -t "cmnd/#" -v
   ```

3. **Message Format Issues**
   ```bash
   # Validate JSON format
   mosquitto_sub -h localhost -t "cmnd/#" -v | jq '.'
   ```

## Customization

### Adding New Device Types

1. **Add Device Configuration**:
   ```python
   self.devices.append({
       'mac': 'new-device-mac',
       'modes': ['sensor-mode']
   })
   ```

2. **Create New Component Generator**:
   ```python
   def _generate_new_component_data(self):
       return {
           "timestamp": self._get_current_timestamp(),
           "custom_field": random.uniform(0, 100)
       }
   ```

3. **Register Generator**:
   ```python
   def _get_message_generators(self):
       return {
           # ... existing generators
           'new-component': self._generate_new_component_data
       }
   ```

### Adjusting Data Patterns

1. **Modify Value Ranges**:
   ```python
   # Temperature range
   temp_celsius = random.uniform(10.0, 40.0)  # Wider range
   
   # Boolean probability
   status = random.choices([True, False], weights=[0.8, 0.2])[0]  # 80% True
   ```

2. **Add Time-based Patterns**:
   ```python
   # Business hours simulation
   current_hour = datetime.now().hour
   if 9 <= current_hour <= 17:
       # Higher activity during business hours
       publish_probability = 0.8
   else:
       publish_probability = 0.2
   ```

## Future Enhancements

1. **Configuration File**: External device configuration
2. **Realistic Patterns**: Time-based and usage-pattern simulation
3. **Device Failure Simulation**: Intermittent connectivity issues
4. **Historical Data Replay**: Replay recorded device behavior
5. **Performance Testing**: High-volume message generation
6. **Multiple Device Models**: Support for different F2 variants
7. **Web Interface**: Real-time configuration and monitoring
