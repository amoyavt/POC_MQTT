# Kafka Log Compaction Test

This .NET console application tests Kafka log compaction on the `processed-iot-data` topic to verify that only the most recent value for each unique key is retained.

## Purpose

Validates that Kafka log compaction correctly maintains the "last known state" of each sensor data point using composite keys in the format `{device_id}:{datapoint_id}`.

## Prerequisites

1. Docker services running: `docker-compose up -d`
2. Kafka accessible at `localhost:9092`
3. .NET 8.0 or later installed

## Usage

```bash
# Navigate to test directory
cd tests/KafkaLogCompactionTest

# Restore dependencies
dotnet restore

# Run the application
dotnet run
```

## What It Does

- Connects to Kafka at `localhost:9092`
- Subscribes to the `processed-iot-data` topic
- Displays each message with:
  - Timestamp
  - Key (device_id:datapoint_id format)
  - Value (JSON sensor data)
  - Partition and offset information
- Runs continuously until Ctrl+C

## Expected Behavior

With log compaction enabled, you should observe:
- Only the latest message per key is retained long-term
- Older messages with the same key are eventually compacted away
- Each unique sensor data point maintains its current state

## Configuration

The application uses these Kafka settings:
- **Bootstrap Servers**: localhost:9092
- **Consumer Group**: log-compaction-test
- **Auto Offset Reset**: Earliest
- **Topic**: processed-iot-data

## Troubleshooting

If connection fails:
1. Verify Kafka is running: `docker-compose ps kafka`
2. Check Kafka logs: `docker-compose logs kafka`
3. Ensure port 9092 is accessible from host