import json
import logging
import os
import re
import time
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from kafka.errors import KafkaError
import signal

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/connector.log', mode='a') if os.path.exists('/app/logs') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set specific log levels for different operations
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('paho').setLevel(logging.WARNING)

class MQTTKafkaConnector:
    def __init__(self):
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'mosquitto:1883')
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.kafka_topic = os.getenv('KAFKA_TOPIC', 'raw_iot_data')
        self.mqtt_topic_pattern = os.getenv('MQTT_TOPIC_PATTERN', 'cmnd/#')
        
        # MQTT authentication
        self.mqtt_username = self._load_secret_from_docker_file(
            os.getenv('MQTT_USERNAME_FILE'), 
            os.getenv('MQTT_USERNAME', 'iot_user'),
            "MQTT username"
        )
        self.mqtt_password = self._load_secret_from_docker_file(
            os.getenv('MQTT_PASSWORD_FILE'),
            os.getenv('MQTT_PASSWORD', 'iot_password'),
            "MQTT password"
        )
        
        # Kafka optimization settings
        self.kafka_batch_size = int(os.getenv('KAFKA_BATCH_SIZE', '16384'))
        self.kafka_linger_ms = int(os.getenv('KAFKA_LINGER_MS', '10'))
        self.kafka_buffer_memory = int(os.getenv('KAFKA_BUFFER_MEMORY', '33554432'))
        self.kafka_compression_type = os.getenv('KAFKA_COMPRESSION_TYPE', 'snappy')
        self.kafka_retries = int(os.getenv('KAFKA_RETRIES', '3'))
        self.kafka_max_in_flight = int(os.getenv('KAFKA_MAX_IN_FLIGHT', '5'))
        
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
                # Subscribe to all F2 device topic types
                client.subscribe("cmnd/+/+/+/+")
                client.subscribe("stat/+/+/+/+") 
                client.subscribe("tele/+/+/+/+")
                logger.info(f"Subscribed to all device topic patterns: cmnd/stat/tele/+/+/+/+")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        """
        Process incoming MQTT message and forward to Kafka.
        
        Args:
            client: MQTT client instance
            userdata: User-defined data
            msg: MQTT message
        """
        try:
            if not msg or not msg.topic:
                logger.warning("Received empty MQTT message")
                return
                
            topic = msg.topic
            
            # Decode payload with error handling
            try:
                payload = msg.payload.decode('utf-8')
            except UnicodeDecodeError as e:
                logger.error(f"Failed to decode MQTT payload for topic {topic}: {e}")
                return
            
            if not payload:
                logger.debug(f"Empty payload for topic {topic}")
                return
            
            device_id = self._extract_device_id(topic)
            if device_id == "unknown":
                logger.warning(f"Could not extract device ID from topic: {topic}")
            
            # Parse JSON payload safely
            parsed_payload = payload
            if self._is_json(payload):
                try:
                    parsed_payload = json.loads(payload)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in payload for topic {topic}: {e}")
                    # Keep as string if JSON parsing fails
            
            kafka_record = {
                'original_topic': topic,
                'device_id': device_id,
                'payload': parsed_payload,
                'timestamp': time.time()
            }
            
            self._send_to_kafka(device_id, kafka_record)
            
            logger.debug(f"Processed message from {topic} for device {device_id} (payload size: {len(payload)} bytes)")
            
        except Exception as e:
            logger.error(f"Unexpected error processing MQTT message from topic {getattr(msg, 'topic', 'unknown')}: {e}", exc_info=True)

    def _is_json(self, payload: str) -> bool:
        try:
            json.loads(payload)
            return True
        except json.JSONDecodeError:
            return False

    def _send_to_kafka(self, key: str, value: Dict[str, Any]):
        """
        Send message to Kafka with enhanced error handling.
        
        Args:
            key: Message key (device ID)
            value: Message value (MQTT data)
        """
        try:
            if not key or not value:
                logger.warning(f"Invalid Kafka message: key='{key}', value={bool(value)}")
                return
                
            # Serialize value to JSON
            try:
                json_value = json.dumps(value, default=str)
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to serialize message to JSON: {e}")
                logger.debug(f"Problematic value: {value}")
                return
            
            future = self.kafka_producer.send(
                self.kafka_topic,
                key=key.encode('utf-8'),
                value=json_value.encode('utf-8')
            )
            
            future.add_callback(lambda metadata: self._on_kafka_success(metadata, key))
            future.add_errback(lambda error: self._on_kafka_error(error, key))
            
        except Exception as e:
            logger.error(f"Unexpected error sending to Kafka for key '{key}': {e}", exc_info=True)

    def _on_kafka_success(self, record_metadata, key=None):
        """Handle successful Kafka message send."""
        logger.debug(
            f"Message sent successfully to Kafka topic {record_metadata.topic} "
            f"partition {record_metadata.partition} offset {record_metadata.offset} "
            f"(key: {key})"
        )

    def _on_kafka_error(self, excp, key=None):
        """Handle failed Kafka message send."""
        logger.error(f"Failed to send message to Kafka for key '{key}': {excp}")
        # Could implement retry logic here if needed

    def _load_secret_from_docker_file(self, secret_file_path: Optional[str], 
                                     fallback_value: str, 
                                     secret_name: str = "credential") -> str:
        """
        Load sensitive data from Docker secrets file or fallback to environment variable.
        
        This method implements the Docker secrets security pattern, where sensitive data
        is mounted as read-only files in containers instead of being exposed through
        environment variables.
        
        Args:
            secret_file_path: Path to Docker secret file (e.g., /run/secrets/mqtt_username)
            fallback_value: Fallback value from environment variable
            secret_name: Name of secret for logging purposes
            
        Returns:
            Secret value from file or fallback
        """
        if secret_file_path and os.path.exists(secret_file_path):
            try:
                with open(secret_file_path, 'r') as f:
                    logger.info(f"Successfully loaded {secret_name} from Docker secret file")
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"Failed to read {secret_name} from {secret_file_path}: {e}")
        
        logger.info(f"Using {secret_name} from environment variable fallback")
        return fallback_value
    
    def _setup_mqtt_client(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        # Set authentication credentials
        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            logger.info(f"MQTT authentication configured for user: {self.mqtt_username}")
        
        broker_parts = self.mqtt_broker.split(':')
        host = broker_parts[0]
        port = int(broker_parts[1]) if len(broker_parts) > 1 else 1883
        
        logger.info(f"Connecting to MQTT broker at {host}:{port} with authentication")
        self.mqtt_client.connect(host, port, 60)

    def _setup_kafka_producer(self):
        """Setup optimized Kafka producer with performance settings."""
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers.split(','),
            value_serializer=lambda v: v,
            key_serializer=lambda k: k,
            # Performance optimizations
            batch_size=self.kafka_batch_size,
            linger_ms=self.kafka_linger_ms,
            buffer_memory=self.kafka_buffer_memory,
            compression_type=self.kafka_compression_type,
            # Reliability settings
            acks=1,  # Balance between performance and durability
            retries=self.kafka_retries,
            max_in_flight_requests_per_connection=self.kafka_max_in_flight,
            # Error handling
            retry_backoff_ms=100,
            request_timeout_ms=30000
        )
        logger.info(f"Connected to Kafka at {self.kafka_servers} with optimized settings")

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