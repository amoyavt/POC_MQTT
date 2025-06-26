# Grafana Configuration and Setup

## Overview

Grafana provides the visualization layer for the monitoring stack, offering real-time dashboards for system health, performance metrics, and IoT data analytics.

## Service Configuration

### Docker Configuration
```yaml
grafana:
  image: grafana/grafana:latest
  container_name: grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana_data:/var/lib/grafana
    - ./grafana/provisioning:/etc/grafana/provisioning
    - ./grafana/dashboards:/var/lib/grafana/dashboards
  networks:
    - iot-network
```

### Access Information
- **URL**: http://localhost:3000
- **Default Credentials**: admin/admin
- **Network**: iot-network (internal Docker network)

## Directory Structure

```
monitoring/grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml      # Prometheus data source config
│   └── dashboards/
│       └── dashboards.yml      # Dashboard provisioning config
└── dashboards/
    └── iot-architecture-dashboard.json  # Main IoT dashboard
```

## Data Source Configuration

### Prometheus Data Source
**File**: `monitoring/grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    basicAuth: false
    editable: true
```

### Connection Details
- **Name**: Prometheus
- **Type**: Prometheus
- **URL**: http://prometheus:9090 (internal Docker network)
- **Access**: Server (proxy) mode
- **Default**: Yes

## Dashboard Provisioning

### Dashboard Configuration
**File**: `monitoring/grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: 'IoT Architecture'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### Provisioning Features
- **Auto-discovery**: Automatically loads dashboard JSON files
- **Live Reload**: Updates dashboards when files change
- **UI Updates**: Allows editing through Grafana interface
- **Version Control**: Dashboard configurations stored in Git

## Main IoT Architecture Dashboard

### Dashboard Overview
**File**: `monitoring/grafana/dashboards/iot-architecture-dashboard.json`

**Dashboard Features**:
- **System Health Overview**: Service status indicators
- **Resource Monitoring**: CPU, memory, disk usage
- **Container Metrics**: Per-service resource consumption
- **Network Monitoring**: Traffic and connectivity metrics
- **Custom Variables**: Time range, service filtering

### Panel Configuration

#### 1. System Status Panel
```json
{
  "title": "Service Health Status",
  "type": "stat",
  "targets": [
    {
      "expr": "up{job=\"health-monitor\"}",
      "legendFormat": "{{instance}}"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "color": {
        "mode": "thresholds"
      },
      "thresholds": {
        "steps": [
          {"color": "red", "value": 0},
          {"color": "green", "value": 1}
        ]
      }
    }
  }
}
```

#### 2. CPU Usage Panel
```json
{
  "title": "CPU Usage by Container",
  "type": "timeseries",
  "targets": [
    {
      "expr": "rate(container_cpu_usage_seconds_total{name!=\"\"}[5m]) * 100",
      "legendFormat": "{{name}}"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "max": 100
    }
  }
}
```

#### 3. Memory Usage Panel
```json
{
  "title": "Memory Usage by Container",
  "type": "timeseries",
  "targets": [
    {
      "expr": "container_memory_usage_bytes{name!=\"\"} / 1024 / 1024",
      "legendFormat": "{{name}}"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "MB"
    }
  }
}
```

#### 4. Network Traffic Panel
```json
{
  "title": "Network Traffic",
  "type": "timeseries",
  "targets": [
    {
      "expr": "rate(container_network_receive_bytes_total[5m])",
      "legendFormat": "{{name}} - RX"
    },
    {
      "expr": "rate(container_network_transmit_bytes_total[5m])",
      "legendFormat": "{{name}} - TX"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "Bps"
    }
  }
}
```

## Dashboard Variables

### Time Range Variable
```json
{
  "name": "timeRange",
  "type": "interval",
  "query": "1m,5m,10m,30m,1h,6h,12h,1d,7d,14d,30d",
  "current": {
    "text": "5m",
    "value": "5m"
  }
}
```

### Service Filter Variable
```json
{
  "name": "service",
  "type": "query",
  "query": "label_values(up, job)",
  "refresh": 1,
  "includeAll": true,
  "multi": true
}
```

## Custom Dashboards

### Creating New Dashboards

1. **Access Grafana UI**: Navigate to http://localhost:3000
2. **Login**: Use admin/admin credentials
3. **Create Dashboard**: Click "+" → "Dashboard"
4. **Add Panel**: Configure visualization and queries
5. **Save Dashboard**: Save with descriptive name

### Dashboard Best Practices

1. **Consistent Time Ranges**: Use dashboard-wide time controls
2. **Meaningful Names**: Clear panel titles and legend formats
3. **Appropriate Units**: Configure units for metrics (MB, %, seconds)
4. **Color Coding**: Use consistent colors for similar metrics
5. **Alerting**: Set thresholds for critical metrics

## Common Queries

### System Health Queries
```promql
# Service availability
up{job="health-monitor"}

# Container status
container_last_seen{name!=""}

# System uptime
time() - node_boot_time_seconds
```

### Resource Usage Queries
```promql
# CPU usage by container
rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100

# Memory usage by container
container_memory_usage_bytes{name!=""} / container_spec_memory_limit_bytes{name!=""} * 100

# Disk usage
(node_filesystem_size_bytes{fstype!="tmpfs"} - node_filesystem_free_bytes{fstype!="tmpfs"}) / node_filesystem_size_bytes{fstype!="tmpfs"} * 100
```

### Network Performance Queries
```promql
# Network receive rate
rate(container_network_receive_bytes_total[5m])

# Network transmit rate
rate(container_network_transmit_bytes_total[5m])

# Network errors
rate(container_network_receive_errors_total[5m])
```

## Alerting Configuration

### Alert Rules Setup
```json
{
  "alert": {
    "name": "High CPU Usage",
    "message": "CPU usage is above 80%",
    "frequency": "10s",
    "conditions": [
      {
        "query": {
          "queryType": "",
          "refId": "A",
          "model": {
            "expr": "rate(container_cpu_usage_seconds_total[5m]) * 100 > 80",
            "intervalMs": 1000,
            "maxDataPoints": 43200
          }
        },
        "reducer": {
          "type": "last",
          "params": []
        },
        "evaluator": {
          "params": [80],
          "type": "gt"
        }
      }
    ]
  }
}
```

### Notification Channels
```json
{
  "name": "Slack Alerts",
  "type": "slack",
  "settings": {
    "url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    "channel": "#alerts",
    "username": "Grafana"
  }
}
```

## Performance Optimization

### Dashboard Performance Tips

1. **Limit Time Ranges**: Use appropriate time windows for queries
2. **Reduce Query Frequency**: Set reasonable refresh intervals
3. **Optimize Queries**: Use efficient PromQL expressions
4. **Limit Data Points**: Configure max data points per panel

### Query Optimization Examples
```promql
# Instead of high-cardinality queries
sum(rate(container_cpu_usage_seconds_total[5m])) by (name)

# Use lower cardinality groupings
sum(rate(container_cpu_usage_seconds_total[5m])) by (job)
```

## Backup and Restore

### Dashboard Export
1. **Dashboard Settings**: Click gear icon → "JSON Model"
2. **Copy JSON**: Copy the complete dashboard JSON
3. **Save to File**: Store in version control

### Dashboard Import
1. **Import Dashboard**: Click "+" → "Import"
2. **Paste JSON**: Paste dashboard JSON or upload file
3. **Configure**: Set data source and variables

### Automated Backup
```bash
# Export dashboard via API
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:3000/api/dashboards/uid/DASHBOARD_UID \
     > dashboard-backup.json
```

## Troubleshooting

### Common Issues

1. **Data Source Connection Error**
   ```bash
   # Check Prometheus connectivity
   docker exec grafana curl http://prometheus:9090/api/v1/label/__name__/values
   ```

2. **Dashboard Not Loading**
   ```bash
   # Check Grafana logs
   docker-compose logs grafana
   
   # Verify provisioning files
   docker exec grafana ls -la /etc/grafana/provisioning/
   ```

3. **No Data in Panels**
   ```bash
   # Test Prometheus queries
   curl 'http://localhost:9090/api/v1/query?query=up'
   
   # Check metric availability
   curl http://localhost:9090/api/v1/label/__name__/values
   ```

### Performance Issues
```bash
# Check Grafana resource usage
docker stats grafana

# Review query performance
# Use Grafana Query Inspector in UI
```

## Security Configuration

### Authentication
```env
# Environment variables for authentication
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=secure_password
GF_SECURITY_SECRET_KEY=your_secret_key
```

### Authorization
```ini
# grafana.ini configuration
[auth.anonymous]
enabled = false

[users]
allow_sign_up = false
allow_org_create = false
```

## Integration with External Systems

### Prometheus Integration
- **Service Discovery**: Automatic target discovery
- **Alertmanager**: Integration for alert routing
- **Recording Rules**: Pre-computed metrics

### Future Integrations
- **Elasticsearch**: Log aggregation dashboards
- **InfluxDB**: Additional time-series data
- **External APIs**: Custom data source plugins

## Operational Commands

### Service Management
```bash
# Start Grafana
docker-compose -f monitoring/docker-compose.monitoring.yml up -d grafana

# View Grafana logs
docker-compose logs grafana

# Restart Grafana
docker-compose restart grafana
```

### Configuration Updates
```bash
# Reload provisioning
docker exec grafana kill -HUP 1

# Check configuration
docker exec grafana grafana-cli admin --help
```

### Dashboard Management
```bash
# List dashboards via API
curl -H "Authorization: Bearer API_KEY" \
     http://localhost:3000/api/search

# Create dashboard folder
curl -X POST -H "Content-Type: application/json" \
     -H "Authorization: Bearer API_KEY" \
     -d '{"title":"IoT Monitoring"}' \
     http://localhost:3000/api/folders
```

## Future Enhancements

1. **Custom Plugins**: Develop IoT-specific visualization plugins
2. **Advanced Alerting**: Multi-condition alerts with dependencies
3. **User Management**: Role-based access control
4. **Custom Themes**: Branded dashboard themes
5. **Mobile Optimization**: Responsive dashboard design
6. **Data Export**: Automated report generation
7. **Integration Testing**: Dashboard validation automation