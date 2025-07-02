import json
import logging
import os
import re
import sys
import time
from typing import Dict, Any, Optional, Tuple, List
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import ThreadedConnectionPool
from kafka import KafkaConsumer, KafkaProducer
import signal
import struct
from pydantic import ValidationError
from functools import lru_cache
import redis
from datetime import datetime, timedelta

# Add the parent directory to Python path to import shared modules
sys.path.append('/app/shared')
from models import IotMeasurement

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/processor.log', mode='a') if os.path.exists('/app/logs') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set specific log levels for different operations
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('psycopg2').setLevel(logging.WARNING)

class DataProcessor:
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'raw_iot_data')
        self.output_topic = os.getenv('KAFKA_OUTPUT_TOPIC', 'decoded_iot_data')
        
        self.pg_host = os.getenv('POSTGRES_HOST', 'postgres')
        self.pg_db = os.getenv('POSTGRES_DB', 'device_params')
        self.pg_user = os.getenv('POSTGRES_USER', 'iot_user')
        self.pg_password = self._load_secret_from_docker_file(
            os.getenv('POSTGRES_PASSWORD_FILE'), 
            os.getenv('POSTGRES_PASSWORD', 'iot_password'),
            "PostgreSQL password"
        )
        self.pg_port = os.getenv('POSTGRES_PORT', '5432')
        
        # Redis caching configuration
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.cache_ttl = int(os.getenv('CACHE_TTL', '600'))  # 10 minutes
        
        self.consumer = None
        self.producer = None
        self.db_pool = None
        self.redis_client = None
        self.running = True
        
        # Compiled regex for better performance and security
        self.topic_pattern = re.compile(r'^cmnd/f2-([a-fA-F0-9]{12})/([^/]+)/(\d+)/sensor-(\d+)$')
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _load_secret_from_docker_file(self, secret_file_path: Optional[str], 
                                     fallback_value: str, 
                                     secret_name: str = "credential") -> str:
        """
        Load sensitive data from Docker secrets file or fallback to environment variable.
        
        This method implements the Docker secrets security pattern, where sensitive data
        is mounted as read-only files in containers instead of being exposed through
        environment variables.
        
        Args:
            secret_file_path: Path to Docker secret file (e.g., /run/secrets/db_password)
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
    
    def _setup_database_pool(self):
        """Setup connection pooling for better performance and security."""
        try:
            self.db_pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=self.pg_host,
                port=self.pg_port,
                database=self.pg_db,
                user=self.pg_user,
                password=self.pg_password
            )
            logger.info("Connected to PostgreSQL database with connection pooling")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    def _setup_redis_connection(self):
        """Setup Redis connection for caching."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Caching disabled.")
            self.redis_client = None

    def _setup_kafka_connections(self):
        self.consumer = KafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.kafka_servers.split(','),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='data_processor_group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_servers.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8'),
            acks='all'
        )
        
        logger.info("Kafka consumer and producer initialized")

    def _validate_mac_address(self, mac_addr: str) -> bool:
        """Validate MAC address format for security."""
        if not mac_addr or len(mac_addr) != 12:
            return False
        return all(c in '0123456789abcdefABCDEF' for c in mac_addr)
    
    def _validate_input_parameters(self, mac_addr: str, connector_number: int, pin_position: int) -> bool:
        """Validate all input parameters to prevent SQL injection."""
        # Validate MAC address format
        if not self._validate_mac_address(mac_addr):
            logger.error(f"Invalid MAC address format: {mac_addr}")
            return False
        
        # Validate numeric parameters
        if connector_number < 0 or connector_number > 99:
            logger.error(f"Invalid connector number: {connector_number}")
            return False
        
        if pin_position < 0 or pin_position > 99:
            logger.error(f"Invalid pin position: {pin_position}")
            return False
        
        return True
    
    @lru_cache(maxsize=1000)
    def _parse_mqtt_topic(self, topic: str) -> Optional[Tuple[str, str, int, int]]:
        """
        Securely parse MQTT topic with strict validation.
        
        Args:
            topic: MQTT topic string
            
        Returns:
            Tuple of (mac_addr, mode, connector_number, pin_position) or None
        """
        if not topic or not isinstance(topic, str) or len(topic) > 200:
            logger.error(f"Invalid topic format or length: {topic}")
            return None
        
        match = self.topic_pattern.match(topic)
        
        if match:
            try:
                mac_addr = match.group(1).lower()  # Normalize to lowercase
                mode = match.group(2)
                connector_number = int(match.group(3))
                pin_position = int(match.group(4))
                
                # Additional validation
                if not self._validate_input_parameters(mac_addr, connector_number, pin_position):
                    return None
                
                # Validate mode parameter (whitelist approach)
                allowed_modes = {'sensor-mode', 'access-control-mode', 'alarm-mode'}
                if mode not in allowed_modes:
                    logger.warning(f"Unknown mode '{mode}' in topic: {topic}")
                
                logger.debug(f"Parsed topic '{topic}' -> {mac_addr}, {mode}, {connector_number}, {pin_position}")
                return mac_addr, mode, connector_number, pin_position
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing topic components from '{topic}': {e}")
                return None
        
        logger.warning(f"Topic '{topic}' does not match expected format")
        return None

    def _get_cache_key(self, mac_addr: str, connector_number: int, pin_position: int) -> str:
        """Generate cache key for data points."""
        return f"dp:{mac_addr}:{connector_number}:{pin_position}"
    
    def _get_data_points_from_cache(self, mac_addr: str, connector_number: int, pin_position: int) -> Optional[List[Dict[str, Any]]]:
        """Get data points from Redis cache."""
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._get_cache_key(mac_addr, connector_number, pin_position)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                logger.debug(f"Cache HIT for {cache_key}")
                return json.loads(cached_data)
            else:
                logger.debug(f"Cache MISS for {cache_key}")
                return None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def _set_data_points_cache(self, mac_addr: str, connector_number: int, pin_position: int, data: List[Dict[str, Any]]):
        """Store data points in Redis cache."""
        if not self.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(mac_addr, connector_number, pin_position)
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data, default=str)
            )
            logger.debug(f"Cached data for {cache_key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def _get_data_points(self, mac_addr: str, connector_number: int, pin_position: int) -> Optional[List[Dict[str, Any]]]:
        """
        Securely retrieve data points with caching and validation.
        
        Args:
            mac_addr: Device MAC address (validated)
            connector_number: Connector number (validated)
            pin_position: Pin position (validated)
            
        Returns:
            List of data point dictionaries or None if not found
        """
        # Input validation already done in _validate_input_parameters
        if not self._validate_input_parameters(mac_addr, connector_number, pin_position):
            return None
        
        # Try cache first
        cached_result = self._get_data_points_from_cache(mac_addr, connector_number, pin_position)
        if cached_result is not None:
            return cached_result
        
        # Secure parameterized query with exact match (no ILIKE)
        query = '''
        SELECT dp."DataPointId", dp."Label", dp."Offset", dp."Length", 
               dp."DataEncoding", dp."Decimals", dp."Append"
        FROM "DataPoint" dp
        JOIN "DeviceTemplate" dt ON dp."DeviceTemplateId" = dt."DeviceTemplateId"
        JOIN "Device" d ON dt."DeviceTemplateId" = d."DeviceTemplateId"
        JOIN "Pin" p ON d."DeviceId" = p."DeviceId"
        JOIN "Connector" c ON p."ConnectorId" = c."ConnectorId"
        JOIN "Device" controller ON c."ControllerId" = controller."DeviceId"
        WHERE LOWER(controller."MacAddress") = LOWER(%s)
          AND c."ConnectorNumber" = %s
          AND p."Position" = %s;
        '''
        
        try:
            conn = self.db_pool.getconn() if self.db_pool else None
            if not conn:
                logger.error("No database connection available")
                return None
            
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                logger.debug(f"Querying data points for {mac_addr}/{connector_number}/{pin_position}")
                
                # Use exact parameterized values - no string formatting
                cursor.execute(query, (mac_addr, connector_number, pin_position))
                results = cursor.fetchall()
                
                if results:
                    data_points = [dict(row) for row in results]
                    logger.debug(f"Found {len(data_points)} data points for {mac_addr}/{connector_number}/{pin_position}")
                    
                    # Cache the results
                    self._set_data_points_cache(mac_addr, connector_number, pin_position, data_points)
                    
                    return data_points
                else:
                    logger.info(f"No data points found for device at MAC/connector/pin: {mac_addr}/{connector_number}/{pin_position}")
                    return None
                    
        except psycopg2.Error as e:
            logger.error(f"Database query error for data points: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during DB query: {e}", exc_info=True)
            return None
        finally:
            if conn and self.db_pool:
                self.db_pool.putconn(conn)

    def _decode_data(self, hex_data: str, data_point: Dict[str, Any]) -> Optional[Any]:
        """Decodes a segment of hex data based on a data point definition."""
        try:
            offset = data_point['Offset']
            length = data_point['Length']
            data_encoding = data_point['DataEncoding']
            
            hex_data = hex_data.replace(" ", "")
            
            start_index = offset * 2
            end_index = start_index + length * 2
            
            if end_index > len(hex_data):
                logger.warning(f"Data point '{data_point['Label']}' (offset: {offset}, length: {length}) is out of bounds for hex data of length {len(hex_data)/2} bytes.")
                return None
                
            segment = hex_data[start_index:end_index]
            byte_data = bytes.fromhex(segment)

            decoded_value = None
            
            if data_encoding == 'Int16':
                decoded_value = struct.unpack('>h', byte_data)[0]
            elif data_encoding == 'Uint16':
                decoded_value = struct.unpack('>H', byte_data)[0]
            else:
                logger.warning(f"Unsupported data encoding: '{data_encoding}' for data point '{data_point['Label']}'")
                return None

            if 'Decimals' in data_point and data_point['Decimals'] > 0:
                decoded_value = decoded_value / (10 ** data_point['Decimals'])
            
            return decoded_value

        except (struct.error, ValueError) as e:
            logger.error(f"Error decoding data for data point '{data_point.get('Label', 'N/A')}': {e}. Segment: {segment}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during data decoding: {e}")
            return None

    def _process_message(self, message):
        """
        Process a single message from Kafka.
        
        Args:
            message: Kafka message containing IoT data
        """
        start_time = time.time()
        
        try:
            # Validate message structure
            if not hasattr(message, 'value') or message.value is None:
                logger.warning("Received message with no value")
                return
                
            data = message.value
            original_topic = data.get('original_topic', '')
            payload = data.get('payload', {})
            
            if not original_topic:
                logger.debug("Skipping message with missing original_topic")
                return
                
            if not isinstance(payload, dict) or 'data' not in payload:
                logger.debug(f"Skipping message with invalid payload structure: {type(payload)}")
                return

            # Parse MQTT topic
            topic_parts = self._parse_mqtt_topic(original_topic)
            if not topic_parts:
                logger.debug(f"Could not parse topic: {original_topic}")
                return

            mac_addr, mode, connector_number, pin_position = topic_parts
            
            # Get device configuration
            data_points = self._get_data_points(mac_addr, connector_number, pin_position)
            if not data_points:
                logger.debug(f"No data points configured for {mac_addr}/{connector_number}/{pin_position}")
                return

            hex_data = payload.get('data', '')
            if not hex_data:
                logger.warning(f"Empty hex data in payload for topic {original_topic}")
                return
                
            message_timestamp = payload.get('timestamp', time.time())
            processed_count = 0
            
            # Process each data point
            for dp in data_points:
                try:
                    decoded_value = self._decode_data(hex_data, dp)
                    
                    if decoded_value is not None:
                        # Create message data in the format expected by IotMeasurement
                        message_data = {
                            'timestamp': message_timestamp,
                            'mac_address': mac_addr,
                            'connector': connector_number,
                            'pin': pin_position,
                            'mode': mode,
                            'data_point_label': dp['Label'],
                            'value': decoded_value,
                            'unit': dp.get('Append', '').strip(),
                            'original_topic': original_topic,
                        }
                        
                        # Validate the message using the shared model
                        try:
                            validated_message = IotMeasurement.model_validate(message_data)
                            enriched_message = validated_message.dict_for_kafka()
                            
                            key = f"{mac_addr}-{connector_number}-{pin_position}-{dp['Label']}"
                            self.producer.send(self.output_topic, key=key, value=enriched_message)
                            
                            logger.debug(f"Processed data point {dp['Label']} for {mac_addr} - value: {decoded_value}")
                            processed_count += 1
                            
                        except ValidationError as e:
                            logger.error(f"Data validation failed for {dp['Label']}: {e}")
                            logger.debug(f"Failed message data: {message_data}")
                            # Skip this data point rather than sending invalid data
                            continue
                            
                    else:
                        logger.debug(f"Could not decode data for {dp['Label']} from hex: {hex_data}")
                        
                except Exception as dp_error:
                    logger.error(f"Error processing data point {dp.get('Label', 'unknown')}: {dp_error}")
                    continue
            
            processing_time = time.time() - start_time
            if processed_count > 0:
                logger.info(f"Successfully processed {processed_count} data points from {original_topic} in {processing_time:.3f}s")
            else:
                logger.warning(f"No data points successfully processed from {original_topic}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Kafka message JSON: {e}")
            logger.debug(f"Invalid message value: {message.value}")
        except Exception as e:
            logger.error(f"Unexpected error in _process_message: {e}", exc_info=True)
            logger.debug(f"Message that caused error: {getattr(message, 'value', 'Unknown')}")

    def run(self):
        logger.info("Starting Data Processor with enhanced security and performance")
        
        time.sleep(15)
        
        try:
            self._setup_database_pool()
            self._setup_redis_connection()
            self._setup_kafka_connections()
            
            logger.info("Data processor started, waiting for messages...")
            
            for message in self.consumer:
                if not self.running:
                    break
                self._process_message(message)
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        logger.info("Cleaning up connections...")
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.flush()
            self.producer.close()
        if self.db_pool:
            self.db_pool.closeall()
        if self.redis_client:
            self.redis_client.close()

if __name__ == "__main__":
    processor = DataProcessor()
    processor.run()
