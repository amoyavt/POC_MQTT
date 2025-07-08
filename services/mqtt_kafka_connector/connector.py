#!/usr/bin/env python3
"""
MQTT-Kafka Connector Service

Bridges MQTT messages from the broker to Kafka topics for stream processing.
Subscribes to stat and tele topics from F2 Smart Controllers and forwards
the raw IoT data to Kafka for further processing.
"""

import os
import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any

import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MqttKafkaConnector:
    """
    Connects MQTT broker to Kafka for IoT data streaming.
    
    Subscribes to MQTT topics from F2 Smart Controllers and forwards
    messages to Kafka topics for processing by downstream services.
    """
    
    def __init__(self):
        # MQTT Configuration
        self.mqtt_broker_host = os.getenv('MQTT_BROKER_HOST', 'mqtt-broker')
        self.mqtt_broker_port = int(os.getenv('MQTT_BROKER_PORT', '1883'))
        
        # Kafka Configuration
        self.kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.kafka_raw_topic = os.getenv('KAFKA_RAW_TOPIC', 'raw-iot-data')
        
        # MQTT Topics to subscribe to (stat and tele from F2 controllers)
        self.mqtt_topics = [
            'stat/+/+/+/+',  # Status messages
            'tele/+/+/+/+'   # Telemetry messages
        ]
        
        # Initialize clients
        self.mqtt_client = None
        self.kafka_producer = None
        self.running = False
        
        # Message statistics
        self.messages_received = 0
        self.messages_sent = 0
        self.last_stats_time = time.time()
        
    def setup_mqtt_client(self):
        """Initialize and configure MQTT client."""
        self.mqtt_client = mqtt.Client(client_id="mqtt-kafka-connector")
        
        # Set callbacks
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        
        logger.info(f"Connecting to MQTT broker at {self.mqtt_broker_host}:{self.mqtt_broker_port}")
        
    def setup_kafka_producer(self):
        """Initialize Kafka producer with optimized settings."""
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                # Performance settings
                batch_size=16384,
                linger_ms=10,
                compression_type='snappy',
                # Reliability settings
                acks='all',
                retries=3,
                retry_backoff_ms=100
            )
            logger.info(f"Connected to Kafka at {self.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to create Kafka producer: {e}")
            raise
            
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to all relevant topics
            for topic in self.mqtt_topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to MQTT topic: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
            
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection."""
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        
    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages and forward to Kafka."""
        try:
            self.messages_received += 1
            
            # Parse MQTT topic to extract device info
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 5:
                logger.warning(f"Invalid topic format: {msg.topic}")
                return
                
            topic_type = topic_parts[0]  # stat or tele
            device_mac = topic_parts[1]  # f2-MAC_ADDRESS
            mode = topic_parts[2]        # sensor-mode, etc.
            connector_raw = topic_parts[3]   # connector identifier (J1, J2, J3, J4)
            component = topic_parts[4]   # sensor component
            
            # Convert connector from J1/J2/J3/J4 format to numeric (1/2/3/4)
            connector_mapping = {"J1": "1", "J2": "2", "J3": "3", "J4": "4"}
            connector = connector_mapping.get(connector_raw, connector_raw)
            
            # Log connector conversion for debugging
            if connector_raw in connector_mapping:
                logger.debug(f"Converted connector {connector_raw} to {connector} for topic {msg.topic}")
            
            # Decode message payload
            try:
                payload = msg.payload.decode('utf-8')
                # Try to parse as JSON first
                try:
                    payload_data = json.loads(payload)
                except json.JSONDecodeError:
                    # If not JSON, treat as raw string
                    payload_data = payload
            except UnicodeDecodeError:
                logger.warning(f"Could not decode payload for topic {msg.topic}")
                return
                
            # Create Kafka message
            kafka_message = {
                'timestamp': datetime.now().isoformat(),
                'topic': msg.topic,
                'topic_type': topic_type,
                'device_mac': device_mac,
                'mode': mode,
                'connector': connector,  # Numeric format (1, 2, 3, 4)
                'connector_raw': connector_raw,  # Original format (J1, J2, J3, J4)
                'component': component,
                'payload': payload_data,
                'qos': msg.qos,
                'retain': msg.retain
            }
            
            # Send to Kafka using device MAC as key for partitioning
            key = device_mac
            
            future = self.kafka_producer.send(
                self.kafka_raw_topic,
                key=key,
                value=kafka_message
            )
            
            # Add callback for delivery confirmation
            future.add_callback(self.on_kafka_success)
            future.add_errback(self.on_kafka_error)
            
            self.messages_sent += 1
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
            
    def on_kafka_success(self, record_metadata):
        """Callback for successful Kafka message delivery."""
        # Log periodically to avoid spam
        if self.messages_sent % 100 == 0:
            logger.debug(f"Message delivered to {record_metadata.topic} [{record_metadata.partition}] at offset {record_metadata.offset}")
            
    def on_kafka_error(self, excp):
        """Callback for Kafka delivery errors."""
        logger.error(f"Failed to deliver message to Kafka: {excp}")
        
    def print_stats(self):
        """Print connection statistics."""
        current_time = time.time()
        elapsed = current_time - self.last_stats_time
        
        if elapsed >= 60:  # Print stats every minute
            logger.info(f"Statistics - Received: {self.messages_received}, Sent: {self.messages_sent}")
            self.last_stats_time = current_time
            
    def start(self):
        """Start the connector service."""
        logger.info("Starting MQTT-Kafka Connector")
        
        try:
            # Setup clients
            self.setup_kafka_producer()
            self.setup_mqtt_client()
            
            # Connect to MQTT broker
            self.mqtt_client.connect(self.mqtt_broker_host, self.mqtt_broker_port, 60)
            
            # Start MQTT loop
            self.mqtt_client.loop_start()
            self.running = True
            
            logger.info("MQTT-Kafka Connector started successfully")
            
            # Main loop
            while self.running:
                time.sleep(1)
                self.print_stats()
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Connector error: {e}")
            raise
        finally:
            self.stop()
            
    def stop(self):
        """Stop the connector service."""
        logger.info("Stopping MQTT-Kafka Connector")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        if self.kafka_producer:
            self.kafka_producer.flush()
            self.kafka_producer.close()
            
        logger.info("MQTT-Kafka Connector stopped")
        
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start connector
    connector = MqttKafkaConnector()
    connector.start()