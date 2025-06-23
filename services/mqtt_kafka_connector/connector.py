import json
import logging
import os
import re
import time
from typing import Dict, Any
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from kafka.errors import KafkaError
import signal
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MQTTKafkaConnector:
    def __init__(self):
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'mosquitto:1883')
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.kafka_topic = os.getenv('KAFKA_TOPIC', 'raw_iot_data')
        self.mqtt_topic_pattern = os.getenv('MQTT_TOPIC_PATTERN', 'cmnd/#')
        
        self.mqtt_client = None
        self.kafka_producer = None
        self.running = True
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _extract_device_id(self, topic: str) -> str:
        """Extract device ID from MQTT topic."""
        match = re.search(r'f2-([a-fA-F0-9]+)', topic)
        if match:
            return f"f2-{match.group(1)}"
        return "unknown"

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
            try:
                result, mid = client.subscribe(self.mqtt_topic_pattern)
                if result == 0:
                    logger.info(f"Successfully subscribed to topic pattern: {self.mqtt_topic_pattern}")
                else:
                    logger.error(f"Failed to subscribe to {self.mqtt_topic_pattern}, result code: {result}")
            except Exception as e:
                logger.error(f"Exception during subscription: {e}")
                # Try with a simpler pattern
                result, mid = client.subscribe("cmnd/+/+/+/+")
                logger.info(f"Subscribed to alternative pattern: cmnd/+/+/+/+")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            device_id = self._extract_device_id(topic)
            
            kafka_record = {
                'original_topic': topic,
                'device_id': device_id,
                'payload': json.loads(payload) if self._is_json(payload) else payload,
                'timestamp': time.time()
            }
            
            self._send_to_kafka(device_id, kafka_record)
            
            logger.debug(f"Processed message from {topic} for device {device_id}")
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def _is_json(self, payload: str) -> bool:
        try:
            json.loads(payload)
            return True
        except json.JSONDecodeError:
            return False

    def _send_to_kafka(self, key: str, value: Dict[str, Any]):
        try:
            future = self.kafka_producer.send(
                self.kafka_topic,
                key=key.encode('utf-8'),
                value=json.dumps(value).encode('utf-8')
            )
            
            future.add_callback(self._on_kafka_success)
            future.add_errback(self._on_kafka_error)
            
        except Exception as e:
            logger.error(f"Error sending to Kafka: {e}")

    def _on_kafka_success(self, record_metadata):
        logger.debug(f"Message sent to Kafka topic {record_metadata.topic} partition {record_metadata.partition}")

    def _on_kafka_error(self, excp):
        logger.error(f"Failed to send message to Kafka: {excp}")

    def _setup_mqtt_client(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        broker_parts = self.mqtt_broker.split(':')
        host = broker_parts[0]
        port = int(broker_parts[1]) if len(broker_parts) > 1 else 1883
        
        logger.info(f"Connecting to MQTT broker at {host}:{port}")
        self.mqtt_client.connect(host, port, 60)

    def _setup_kafka_producer(self):
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers.split(','),
            value_serializer=lambda v: v,
            key_serializer=lambda k: k,
            acks='all',
            retries=3,
            max_in_flight_requests_per_connection=1
        )
        logger.info(f"Connected to Kafka at {self.kafka_servers}")

    def run(self):
        logger.info("Starting MQTT-Kafka Connector")
        
        # Wait for services to be ready
        self._wait_for_services()
        
        try:
            self._setup_kafka_producer()
            self._setup_mqtt_client()
            
            self.mqtt_client.loop_start()
            
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self._cleanup()

    def _wait_for_services(self):
        logger.info("Waiting for services to be ready...")
        time.sleep(10)

    def _cleanup(self):
        logger.info("Cleaning up connections...")
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        if self.kafka_producer:
            self.kafka_producer.flush()
            self.kafka_producer.close()

if __name__ == "__main__":
    connector = MQTTKafkaConnector()
    connector.run()