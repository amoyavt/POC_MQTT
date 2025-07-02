# Debugging & Troubleshooting Guide

> Complete guide for debugging the MQTT Architecture POC system

## 📋 Table of Contents
- [Quick Diagnostics](#quick-diagnostics)
- [Service-Specific Debugging](#service-specific-debugging)
- [Log Analysis](#log-analysis)
- [Common Issues & Solutions](#common-issues--solutions)
- [Health Monitoring](#health-monitoring)
- [Database Debugging](#database-debugging)
- [Performance Troubleshooting](#performance-troubleshooting)
- [Emergency Procedures](#emergency-procedures)

## 🚀 Quick Diagnostics

### System Health Check
```bash
# Overall system status
make status

# Health endpoint check
curl http://localhost:8000/health

# Quick service verification
docker-compose ps
```

### Log Overview
```bash
# View all service logs (last 100 lines)
make logs

# Monitor logs in real-time
docker-compose logs -f --tail=50

# Check for errors across all services
docker-compose logs | grep -i error
```

### Resource Check
```bash
# Container resource usage
docker stats

# System resources
df -h
free -h
```

## 🔍 Service-Specific Debugging

### 1. MQTT-Kafka Connector

**Check if MQTT messages are being received:**
```bash
# View connector logs
make logs-connector

# Monitor MQTT messages directly
docker exec mqtt-broker mosquitto_sub -t "cmnd/#" -v

# Check Kafka topic for raw data
make kafka-raw
```

**Common Issues:**
- **MQTT connection failed**: Check if Mosquitto is running
- **No messages in Kafka**: Verify MQTT topic subscription
- **JSON parsing errors**: Check MQTT payload format

**Debug Steps:**
```bash
# 1. Verify MQTT broker is accessible
docker exec mqtt-kafka-connector nc -zv mosquitto 1883

# 2. Check connector service logs for detailed errors
docker-compose logs mqtt-kafka-connector | grep -E "(ERROR|WARN)"

# 3. Test MQTT publishing manually
docker exec mqtt-broker mosquitto_pub -t "cmnd/f2-test/sensor-mode/1/sensor-1" -m '{"data":"1234", "timestamp":1642678800}'
```

### 2. Data Processor

**Check data processing pipeline:**
```bash
# View processor logs
make logs-processor

# Check input/output Kafka topics
make kafka-raw      # Input: raw_iot_data
make kafka-decoded  # Output: decoded_iot_data
```

**Common Issues:**
- **Database connection failed**: PostgreSQL not accessible
- **No data points found**: Device not configured in database
- **Validation errors**: Data format doesn't match schema

**Debug Steps:**
```bash
# 1. Test database connectivity
make db-params
# In psql: \dt to list tables

# 2. Check device configuration
docker exec device-params-db psql -U iot_user -d device_params -c "
SELECT * FROM \"Device\" 
WHERE \"MacAddress\" ILIKE '%your_device_mac%';"

# 3. Monitor processing metrics
docker-compose logs data-processor | grep "Successfully processed"
```

### 3. Kafka-TimescaleDB Sink

**Check data persistence:**
```bash
# View sink logs
make logs-sink

# Connect to TimescaleDB
make db-timescale

# Check recent data
# In psql: 
SELECT COUNT(*) FROM iot_measurements WHERE timestamp > NOW() - INTERVAL '1 hour';
```

**Common Issues:**
- **TimescaleDB connection failed**: Database not ready
- **Batch insert errors**: Data validation failures
- **Performance issues**: Batch size too small

**Debug Steps:**
```bash
# 1. Verify TimescaleDB is accessible
docker exec kafka-timescale-sink nc -zv timescaledb 5432

# 2. Check data validation errors
docker-compose logs kafka-timescale-sink | grep "validation failed"

# 3. Monitor batch processing
docker-compose logs kafka-timescale-sink | grep "inserted batch"
```

### 4. F2 Simulator

**Check device simulation:**
```bash
# View simulator logs
make logs-simulator

# Monitor generated MQTT messages
docker exec mqtt-broker mosquitto_sub -t "cmnd/f2-+/+/+/+" -v
```

## 📊 Log Analysis

### Enhanced Logging Format

All services now use structured logging with the format:
```
TIMESTAMP - SERVICE_NAME - LEVEL - [FILE:LINE] - MESSAGE
```

### Log Levels

| Level | Usage | Examples |
|-------|-------|----------|
| **DEBUG** | Detailed processing info | Topic parsing, data validation |
| **INFO** | Normal operations | Successful processing, batch inserts |
| **WARNING** | Non-critical issues | Unknown devices, failed validation |
| **ERROR** | Service errors | Database connection, Kafka failures |
| **CRITICAL** | System failures | Service crashes, data corruption |

### Log Filtering

```bash
# Filter by log level
docker-compose logs | grep "ERROR"
docker-compose logs | grep "WARNING"

# Filter by service
docker-compose logs data-processor
docker-compose logs kafka-timescale-sink

# Filter by time (last hour)
docker-compose logs --since="1h"

# Combine filters
docker-compose logs data-processor | grep ERROR | tail -10
```

### Performance Logging

Look for these performance indicators:
```bash
# Processing time metrics
docker-compose logs | grep "time:"

# Batch processing metrics
docker-compose logs | grep "batch_size:"

# Database query performance
docker-compose logs | grep "query time"
```

## 🚨 Common Issues & Solutions

### Issue 1: Services Not Starting

**Symptoms:**
- Container exits immediately
- "Connection refused" errors
- Health checks failing

**Diagnosis:**
```bash
# Check container status
docker-compose ps

# View startup logs
docker-compose logs [service-name]

# Check resource constraints
docker stats
```

**Solutions:**
1. **Wait for dependencies**: Services have startup delays
2. **Check resource limits**: Ensure sufficient RAM/CPU
3. **Verify configuration**: Check environment variables
4. **Restart in order**: Stop all, then start with dependencies first

### Issue 2: No Data Flow

**Symptoms:**
- Empty Kafka topics
- No data in TimescaleDB
- Processing counters at zero

**Diagnosis Flow:**
```bash
# 1. Check MQTT message generation
docker exec mqtt-broker mosquitto_sub -t "cmnd/#" -c 5

# 2. Check Kafka raw topic
make kafka-raw

# 3. Check Kafka processed topic  
make kafka-decoded

# 4. Check TimescaleDB data
make db-timescale
# In psql: SELECT COUNT(*) FROM iot_measurements;
```

**Solutions:**
1. **Start F2 simulator** if no MQTT messages
2. **Check connector service** if MQTT but no Kafka
3. **Check processor service** if raw Kafka but no processed
4. **Check sink service** if processed Kafka but no database

### Issue 3: High Memory Usage

**Symptoms:**
- Container restarts due to OOM
- Slow processing
- System becomes unresponsive

**Diagnosis:**
```bash
# Check memory usage by container
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Check system memory
free -h
```

**Solutions:**
1. **Increase batch timeout** to process data more frequently
2. **Reduce batch size** to use less memory
3. **Add resource limits** to prevent runaway processes
4. **Check for memory leaks** in application logs

### Issue 4: Database Connection Issues

**Symptoms:**
- "Connection refused" to PostgreSQL/TimescaleDB
- Timeouts during queries
- Transaction rollbacks

**Diagnosis:**
```bash
# Test direct database connection
docker exec device-params-db pg_isready -U iot_user
docker exec timescale-db pg_isready -U ts_user

# Check connection limits
docker exec device-params-db psql -U iot_user -d device_params -c "
SELECT count(*) FROM pg_stat_activity;"
```

**Solutions:**
1. **Increase connection limits** in PostgreSQL configuration
2. **Implement connection pooling** in application code
3. **Add retry logic** for transient connection failures
4. **Monitor connection usage** and close idle connections

## 🏥 Health Monitoring

### Health Check Endpoints

```bash
# Overall system health
curl http://localhost:8000/health

# Individual service health
curl http://localhost:8000/health/kafka
curl http://localhost:8000/health/postgres
curl http://localhost:8000/health/timescaledb
```

### Health Check Response Format

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "kafka": {"status": "healthy", "details": "..."},
    "postgres": {"status": "healthy", "details": "..."},
    "timescaledb": {"status": "healthy", "details": "..."}
  },
  "system": {
    "cpu_usage": 45.2,
    "memory_usage": 68.5,
    "disk_usage": 23.1
  }
}
```

### Automated Health Monitoring

Set up monitoring alerts:
```bash
# Create health check script
cat > health_check.sh << 'EOF'
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s "$HEALTH_URL")
STATUS=$(echo "$RESPONSE" | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    echo "ALERT: System status is $STATUS"
    echo "$RESPONSE"
    # Send notification (email, Slack, etc.)
fi
EOF

# Run every 5 minutes
chmod +x health_check.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * /path/to/health_check.sh") | crontab -
```

## 💾 Database Debugging

### PostgreSQL (Device Parameters)

```bash
# Connect to database
make db-params

# Common diagnostic queries
# Check device configuration
SELECT * FROM "Device" LIMIT 5;

# Check data point configuration
SELECT dp.*, dt."DeviceName" 
FROM "DataPoint" dp 
JOIN "DeviceTemplate" dt ON dp."DeviceTemplateId" = dt."DeviceTemplateId"
LIMIT 10;

# Check for missing device configurations
SELECT DISTINCT device_id 
FROM iot_measurements 
WHERE device_id NOT IN (SELECT "MacAddress" FROM "Device");
```

### TimescaleDB (Time-Series Data)

```bash
# Connect to TimescaleDB
make db-timescale

# Check data ingestion rate
SELECT 
    date_trunc('minute', timestamp) as minute,
    COUNT(*) as records
FROM iot_measurements 
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY minute 
ORDER BY minute DESC;

# Check data distribution
SELECT 
    device_id,
    datapoint_label,
    COUNT(*) as records,
    MIN(timestamp) as first_record,
    MAX(timestamp) as latest_record
FROM iot_measurements
GROUP BY device_id, datapoint_label
ORDER BY records DESC;

# Check for data quality issues
SELECT 
    device_id,
    COUNT(*) as total_records,
    COUNT(value) as valid_values,
    COUNT(*) - COUNT(value) as null_values
FROM iot_measurements
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY device_id;
```

## ⚡ Performance Troubleshooting

### Kafka Performance

```bash
# Check consumer lag
docker exec kafka kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --describe --group data_processor_group

# Monitor topic throughput
docker exec kafka kafka-run-class.sh kafka.tools.ConsumerPerformance \
    --topic raw_iot_data \
    --bootstrap-server localhost:9092 \
    --messages 1000
```

### Database Performance

```sql
-- Check slow queries (PostgreSQL)
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes 
ORDER BY idx_tup_read DESC;
```

## 🚨 Emergency Procedures

### Complete System Restart

```bash
# Graceful shutdown
make clean

# Wait for cleanup
sleep 30

# Full restart
make full-setup

# Verify health
make health
```

### Emergency Data Backup

```bash
# Backup TimescaleDB
docker exec timescale-db pg_dump -U ts_user timeseries > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup PostgreSQL
docker exec device-params-db pg_dump -U iot_user device_params > params_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Log Collection for Support

```bash
# Collect all logs
mkdir debug_logs_$(date +%Y%m%d_%H%M%S)
cd debug_logs_$(date +%Y%m%d_%H%M%S)

# Service logs
docker-compose logs --no-color > all_services.log
docker-compose logs mqtt-kafka-connector --no-color > connector.log
docker-compose logs data-processor --no-color > processor.log
docker-compose logs kafka-timescale-sink --no-color > sink.log

# System info
docker-compose ps > services_status.txt
docker stats --no-stream > resource_usage.txt
curl -s http://localhost:8000/health | jq . > health_status.json

# Compress for sharing
cd ..
tar -czf debug_logs_$(date +%Y%m%d_%H%M%S).tar.gz debug_logs_$(date +%Y%m%d_%H%M%S)/
```

## 🔗 Related Documentation

- **[TimescaleDB Guide](TIMESCALE.md)** - Database-specific debugging
- **[Developer Guide](DEVELOPER_GUIDE.md)** - Development debugging
- **[Performance Guide](PERFORMANCE.md)** - Performance optimization
- **[Logging Guide](LOGGING.md)** - Detailed logging information

## 📞 Getting Help

1. **Check this guide** for common issues
2. **Review logs** using the commands above
3. **Check GitHub issues** for known problems
4. **Create detailed bug reports** with logs and steps to reproduce

**Bug Report Template:**
```
## Environment
- Docker version: 
- OS: 
- System specs: 

## Issue Description
Brief description of the problem

## Steps to Reproduce
1. 
2. 
3. 

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Logs
```
[Relevant log snippets]
```

## System Health
```
[Output of `make health`]
```
```