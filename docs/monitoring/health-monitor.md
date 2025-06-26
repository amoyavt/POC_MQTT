# Health Monitor Service

## Overview

The Health Monitor service provides comprehensive health checking and status monitoring for all components in the IoT architecture, offering REST API endpoints for system health validation and metrics export.

## Service Configuration

### Environment Variables
```bash
DOCKER_API_VERSION=1.41              # Docker API version
DOCKER_HOST=unix:///var/run/docker.sock  # Docker socket connection
```

### Docker Configuration
```yaml
health-monitor:
  build: ./health_monitor
  container_name: health-monitor
  ports:
    - "8000:8000"
  environment:
    - DOCKER_API_VERSION=1.41
    - DOCKER_HOST=unix:///var/run/docker.sock
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  networks:
    - iot-network
  depends_on:
    - prometheus
  user: root
```

## Implementation Details

### Core Functionality

**File**: `monitoring/health_monitor/health_monitor.py`

#### Framework and Dependencies
- **FastAPI**: REST API framework
- **Docker SDK**: Container management and monitoring
- **Prometheus Client**: Metrics export
- **Uvicorn**: ASGI server

#### Key Components
- **Health Check Engine**: Container status validation
- **Metrics Collector**: Prometheus metrics generation
- **REST API**: HTTP endpoints for health queries
- **Service Discovery**: Automatic service detection

## API Endpoints

### System Health Endpoints

#### Overall System Health
```bash
GET /health
```

**Response Example**:
```json
{
  "status": "healthy",
  "timestamp": "2023-05-26T18:34:04.928538Z",
  "services": {
    "mosquitto": "healthy",
    "kafka": "healthy",
    "postgres": "healthy",
    "timescaledb": "healthy",
    "zookeeper": "healthy"
  },
  "total_services": 5,
  "healthy_services": 5,
  "unhealthy_services": 0
}
```

#### Individual Service Health
```bash
GET /health/{service_name}
```

**Supported Services**:
- `mosquitto` - MQTT Broker
- `kafka` - Message Streaming
- `postgres` - Device Parameters DB
- `timescaledb` - Time-series DB
- `zookeeper` - Kafka Coordination
- `mqtt-kafka-connector` - MQTT Bridge
- `data-processor` - Data Processing
- `kafka-timescale-sink` - Data Persistence
- `f2-simulator` - Device Simulation

**Response Example**:
```json
{
  "service": "mosquitto",
  "status": "healthy",
  "container_id": "a1b2c3d4e5f6",
  "container_status": "running",
  "started_at": "2023-05-26T12:00:00.000Z",
  "uptime_seconds": 23044,
  "health_check": {
    "last_check": "2023-05-26T18:34:04.928538Z",
    "check_duration_ms": 15,
    "details": "Container running and responsive"
  }
}
```

### Container Management Endpoints

#### All Containers Status
```bash
GET /containers
```

**Response Example**:
```json
{
  "total_containers": 12,
  "running_containers": 11,
  "stopped_containers": 1,
  "containers": [
    {
      "name": "mosquitto",
      "id": "a1b2c3d4e5f6",
      "status": "running",
      "image": "eclipse-mosquitto:2.0",
      "created": "2023-05-26T12:00:00.000Z",
      "started_at": "2023-05-26T12:00:00.000Z",
      "ports": ["1883/tcp", "9001/tcp"],
      "networks": ["iot-network"]
    }
  ]
}
```

#### Container Details
```bash
GET /containers/{container_name}
```

**Response Example**:
```json
{
  "name": "kafka",
  "id": "b2c3d4e5f6a1",
  "status": "running",
  "health": "healthy",
  "image": "confluentinc/cp-kafka:7.4.0",
  "command": "/etc/confluent/docker/run",
  "created": "2023-05-26T12:01:00.000Z",
  "started_at": "2023-05-26T12:01:15.000Z",
  "finished_at": null,
  "exit_code": null,
  "ports": {
    "9092/tcp": [{"HostIp": "0.0.0.0", "HostPort": "9092"}]
  },
  "mounts": [],
  "networks": {
    "iot-network": {
      "IPAddress": "172.18.0.3",
      "Gateway": "172.18.0.1"
    }
  },
  "environment": [
    "KAFKA_BROKER_ID=1",
    "KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181"
  ],
  "resource_usage": {
    "cpu_percent": 5.2,
    "memory_usage_mb": 512,
    "memory_limit_mb": 2048,
    "memory_percent": 25.0
  }
}
```

### Metrics Endpoints

#### Prometheus Metrics Export
```bash
GET /metrics
```

**Metrics Exported**:
```prometheus
# Container status metrics
container_health_status{container="mosquitto",status="running"} 1
container_health_status{container="kafka",status="running"} 1

# Service health metrics
service_health_status{service="mosquitto"} 1
service_health_status{service="kafka"} 1

# System overview metrics
system_total_containers 12
system_running_containers 11
system_healthy_services 5

# Container resource metrics
container_cpu_usage_percent{container="mosquitto"} 2.1
container_memory_usage_mb{container="mosquitto"} 45
container_memory_percent{container="mosquitto"} 4.4

# Health check performance metrics
health_check_duration_seconds{service="mosquitto"} 0.015
health_check_success_total{service="mosquitto"} 1440
health_check_failure_total{service="mosquitto"} 0
```

## Health Check Logic

### Service Health Determination

#### Container Status Checks
```python
def check_container_health(container_name: str) -> dict:
    try:
        container = docker_client.containers.get(container_name)
        
        # Basic status check
        if container.status != 'running':
            return {"status": "unhealthy", "reason": f"Container status: {container.status}"}
        
        # Service-specific health checks
        if container_name == "mosquitto":
            return check_mqtt_broker_health(container)
        elif container_name == "kafka":
            return check_kafka_health(container)
        elif container_name in ["postgres", "timescaledb"]:
            return check_database_health(container)
        else:
            return {"status": "healthy", "reason": "Container running"}
            
    except Exception as e:
        return {"status": "error", "reason": str(e)}
```

#### Service-Specific Health Checks

##### MQTT Broker Health Check
```python
def check_mqtt_broker_health(container) -> dict:
    try:
        # Check if MQTT port is accepting connections
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('mosquitto', 1883))
        sock.close()
        
        if result == 0:
            return {"status": "healthy", "reason": "MQTT port responsive"}
        else:
            return {"status": "unhealthy", "reason": "MQTT port not responding"}
    except Exception as e:
        return {"status": "error", "reason": f"Health check failed: {e}"}
```

##### Kafka Health Check
```python
def check_kafka_health(container) -> dict:
    try:
        # Check Kafka bootstrap server
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=['kafka:29092'],
            request_timeout_ms=5000,
            api_version=(2, 0, 2)
        )
        producer.close()
        return {"status": "healthy", "reason": "Kafka bootstrap server responsive"}
    except Exception as e:
        return {"status": "unhealthy", "reason": f"Kafka connection failed: {e}"}
```

##### Database Health Check
```python
def check_database_health(container) -> dict:
    try:
        # Check PostgreSQL connection
        import psycopg2
        conn = psycopg2.connect(
            host=container.name,
            port=5432,
            database='postgres',
            user='postgres',
            password='password',
            connect_timeout=5
        )
        conn.close()
        return {"status": "healthy", "reason": "Database connection successful"}
    except Exception as e:
        return {"status": "unhealthy", "reason": f"Database connection failed: {e}"}
```

## Resource Monitoring

### Container Resource Collection
```python
def get_container_resources(container) -> dict:
    try:
        stats = container.stats(stream=False)
        
        # Calculate CPU percentage
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                   stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                      stats['precpu_stats']['system_cpu_usage']
        cpu_percent = (cpu_delta / system_delta) * 100.0
        
        # Calculate memory usage
        memory_usage = stats['memory_stats']['usage']
        memory_limit = stats['memory_stats']['limit']
        memory_percent = (memory_usage / memory_limit) * 100.0
        
        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_usage_mb": round(memory_usage / 1024 / 1024, 2),
            "memory_limit_mb": round(memory_limit / 1024 / 1024, 2),
            "memory_percent": round(memory_percent, 2)
        }
    except Exception:
        return {}
```

## Prometheus Integration

### Metrics Configuration
```python
from prometheus_client import Counter, Gauge, Histogram, generate_latest

# Health check metrics
health_check_success = Counter('health_check_success_total', 'Successful health checks', ['service'])
health_check_failure = Counter('health_check_failure_total', 'Failed health checks', ['service'])
health_check_duration = Histogram('health_check_duration_seconds', 'Health check duration', ['service'])

# Service status metrics
service_health = Gauge('service_health_status', 'Service health status', ['service'])
container_health = Gauge('container_health_status', 'Container health status', ['container', 'status'])

# Resource metrics
container_cpu = Gauge('container_cpu_usage_percent', 'Container CPU usage', ['container'])
container_memory = Gauge('container_memory_usage_mb', 'Container memory usage', ['container'])
```

### Metrics Collection Process
```python
def update_prometheus_metrics():
    # Update service health metrics
    for service in MONITORED_SERVICES:
        health_status = check_service_health(service)
        service_health.labels(service=service).set(1 if health_status['status'] == 'healthy' else 0)
    
    # Update container metrics
    for container in docker_client.containers.list():
        resources = get_container_resources(container)
        if resources:
            container_cpu.labels(container=container.name).set(resources['cpu_percent'])
            container_memory.labels(container=container.name).set(resources['memory_usage_mb'])
```

## Error Handling and Resilience

### Connection Error Handling
```python
def safe_docker_operation(operation):
    try:
        return operation()
    except docker.errors.ConnectionError:
        logger.error("Docker connection failed")
        return {"status": "error", "reason": "Docker daemon unavailable"}
    except docker.errors.NotFound:
        logger.warning("Container not found")
        return {"status": "not_found", "reason": "Container does not exist"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"status": "error", "reason": str(e)}
```

### Service Availability
- **Graceful Degradation**: Continue monitoring available services if some fail
- **Retry Logic**: Automatic retry for transient failures
- **Circuit Breaker**: Prevent cascade failures from unresponsive services

## Configuration Files

### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY health_monitor.py .

EXPOSE 8000

CMD ["uvicorn", "health_monitor:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Requirements.txt
```
fastapi==0.68.0
uvicorn[standard]==0.15.0
docker==5.0.3
prometheus-client==0.11.0
psycopg2-binary==2.9.1
kafka-python==2.0.2
```

## Operational Commands

### Service Management
```bash
# Start health monitor
docker-compose -f monitoring/docker-compose.monitoring.yml up -d health-monitor

# View health monitor logs
docker-compose logs health-monitor

# Test health endpoints
curl http://localhost:8000/health
```

### Health Check Commands
```bash
# Check all services
curl http://localhost:8000/health | jq '.'

# Check specific service
curl http://localhost:8000/health/kafka | jq '.'

# Get container status
curl http://localhost:8000/containers | jq '.'

# Export metrics
curl http://localhost:8000/metrics
```

### Debugging Commands
```bash
# Check Docker connection
docker exec health-monitor docker ps

# Verify socket permissions
docker exec health-monitor ls -la /var/run/docker.sock

# Test service connectivity
docker exec health-monitor curl http://mosquitto:1883
```

## Monitoring Dashboard Integration

### Grafana Queries for Health Monitor
```promql
# Service availability
service_health_status

# Container health status
container_health_status

# Health check success rate
rate(health_check_success_total[5m]) / (rate(health_check_success_total[5m]) + rate(health_check_failure_total[5m]))

# Health check duration
health_check_duration_seconds
```

### Alert Rules
```yaml
- alert: ServiceDown
  expr: service_health_status == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Service {{ $labels.service }} is unhealthy"

- alert: HealthCheckFailure
  expr: rate(health_check_failure_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High health check failure rate for {{ $labels.service }}"
```

## Security Considerations

### Docker Socket Access
- **Read-only Mount**: Socket mounted as read-only to prevent container manipulation
- **User Permissions**: Runs as root to access Docker socket
- **Network Isolation**: Runs in isolated Docker network

### API Security
```python
# Future: API key authentication
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != VALID_API_KEY:
        return JSONResponse(status_code=401, content={"error": "Invalid API key"})
    return await call_next(request)
```

## Performance Characteristics

### Resource Usage
- **CPU**: <5% typical
- **Memory**: <100MB typical
- **Disk I/O**: Minimal (logging only)
- **Network**: <1MB/s typical

### Response Times
- **Health Checks**: <100ms typical
- **Container Listing**: <500ms typical
- **Metrics Export**: <200ms typical

## Troubleshooting

### Common Issues

1. **Docker Connection Failed**
   ```bash
   # Check Docker daemon
   docker version
   
   # Verify socket permissions
   ls -la /var/run/docker.sock
   ```

2. **Service Health Check Timeouts**
   ```bash
   # Check network connectivity
   docker exec health-monitor ping mosquitto
   
   # Verify service ports
   docker exec health-monitor netstat -tlpn
   ```

3. **Missing Metrics**
   ```bash
   # Check Prometheus configuration
   curl http://localhost:9090/api/v1/targets
   
   # Verify metrics endpoint
   curl http://localhost:8000/metrics
   ```

## Future Enhancements

1. **Advanced Health Checks**: Application-level health validation
2. **Custom Alerts**: Configurable alerting rules
3. **Historical Data**: Health check history storage
4. **Dependency Mapping**: Service dependency visualization
5. **Auto-healing**: Automatic container restart on failure
6. **Load Testing**: Synthetic transaction monitoring
7. **Integration APIs**: Webhook notifications for status changes