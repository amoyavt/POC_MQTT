#!/bin/bash
set -e

# Start Kafka in background
echo "Starting Kafka..."
/etc/confluent/docker/run &
KAFKA_PID=$!

# Wait for Kafka to start and configure topics
(
    echo "Waiting for Kafka to be ready..."
    while ! kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; do
        sleep 5
    done
    
    echo "Kafka is ready. Configuring topics..."
    
    # Configure processed-iot-data topic for log compaction
    kafka-configs --bootstrap-server localhost:9092 --alter --entity-type topics --entity-name processed-iot-data --add-config cleanup.policy=compact || true
    kafka-configs --bootstrap-server localhost:9092 --alter --entity-type topics --entity-name processed-iot-data --add-config min.cleanable.dirty.ratio=0.1 || true
    kafka-configs --bootstrap-server localhost:9092 --alter --entity-type topics --entity-name processed-iot-data --add-config segment.ms=60000 || true
    
    echo "Topic configuration completed!"
    
    # Show configuration
    kafka-configs --bootstrap-server localhost:9092 --describe --entity-type topics --entity-name processed-iot-data || true
    
) &

# Wait for Kafka
wait $KAFKA_PID