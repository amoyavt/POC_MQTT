#!/usr/bin/env python3
"""
Stream Processor Service

Processes raw IoT data from Kafka, transforms it by mapping MAC addresses to device IDs
and sensor labels to datapoint IDs, then forwards the optimized data to processed-iot-data topic.
"""

import os
import json
import logging
import signal
import sys
import time
import re
from datetime import datetime
from typing import Dict, Any, Optional

import psycopg2
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

# Import shared models
sys.path.append('/app')
from shared.models import DecodedData, DeviceLookup, DataPointLookup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StreamProcessor:
    """
    Stream processor for IoT data transformation.
    
    Consumes raw IoT data from Kafka, performs MAC→device_id and label→datapoint_id
    mapping using PostgreSQL metadata and Redis caching, then produces optimized
    data to processed-iot-data topic.
    """
    
    def __init__(self):
        # Kafka Configuration
        self.kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.kafka_raw_topic = os.getenv('KAFKA_RAW_TOPIC', 'raw-iot-data')
        self.kafka_processed_topic = os.getenv('KAFKA_PROCESSED_TOPIC', 'processed-iot-data')
        
        # PostgreSQL Configuration
        self.postgres_host = os.getenv('POSTGRES_HOST', 'postgresql')
        self.postgres_user = os.getenv('POSTGRES_USER', 'iot_user')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD', 'iot_password')
        self.postgres_db = os.getenv('POSTGRES_DB', 'iot_metadata')
        
        # Redis Configuration
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        
        # Processing Configuration
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.processing_interval = int(os.getenv('PROCESSING_INTERVAL', '5'))
        
        # Initialize clients
        self.kafka_consumer = None
        self.kafka_producer = None
        self.postgres_conn = None
        self.redis_client = None
        self.running = False
        
        # Cache TTL (1 hour)
        self.cache_ttl = 3600
        
        # Statistics
        self.messages_processed = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.last_stats_time = time.time()
        
    def setup_kafka_consumer(self):
        """Initialize Kafka consumer."""
        try:
            self.kafka_consumer = KafkaConsumer(
                self.kafka_raw_topic,
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                group_id='stream-processor-group',
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                # Performance settings
                fetch_max_wait_ms=500,
                max_poll_records=self.batch_size
            )
            logger.info(f"Kafka consumer connected to {self.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to create Kafka consumer: {e}")
            raise
            
    def setup_kafka_producer(self):
        """Initialize Kafka producer."""
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                # Performance settings
                batch_size=16384,
                linger_ms=10,
                compression_type='gzip',
                # Reliability settings
                acks='all',
                retries=3
            )
            logger.info(f"Kafka producer connected to {self.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to create Kafka producer: {e}")
            raise
            
    def setup_postgres_connection(self):
        """Initialize PostgreSQL connection."""
        try:
            self.postgres_conn = psycopg2.connect(
                host=self.postgres_host,
                user=self.postgres_user,
                password=self.postgres_password,
                database=self.postgres_db,
                port=5432
            )
            logger.info(f"PostgreSQL connected to {self.postgres_host}:{self.postgres_db}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
            
    def setup_redis_client(self):
        """Initialize Redis client."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis connected to {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
            
    def get_device_id_from_mac(self, mac_address: str) -> Optional[int]:
        """
        Get device ID from MAC address using Redis cache and PostgreSQL fallback.
        
        Args:
            mac_address: MAC address (e.g., 'f2-aa:bb:cc:dd:ee:01')
            
        Returns:
            Device ID as integer or None if not found
        """
        # Clean MAC address (remove f2- prefix if present)
        clean_mac = mac_address.replace('f2-', '')
        cache_key = f"device_mac:{clean_mac}"
        
        try:
            # Try Redis cache first
            device_id = self.redis_client.get(cache_key)
            if device_id:
                self.cache_hits += 1
                return int(device_id)
                
            # Cache miss - query PostgreSQL
            self.cache_misses += 1
            with self.postgres_conn.cursor() as cursor:
                cursor.execute(
                    "SELECT \"DeviceId\" FROM \"Device\" WHERE \"MacAddress\" = %s",
                    (clean_mac,)
                )
                result = cursor.fetchone()
                
                if result:
                    device_id = result[0]
                    # Cache the result
                    self.redis_client.setex(cache_key, self.cache_ttl, device_id)
                    return device_id
                    
        except Exception as e:
            logger.error(f"Error getting device ID for MAC {mac_address}: {e}")
            
        return None
        
    def get_connected_sensor_and_datapoint(self, controller_device_id: int, connector: str, component: str) -> Optional[tuple]:
        """
        Get connected sensor device and datapoint ID with metadata using the pin/connector mapping.
        
        This follows the production database architecture:
        1. Find controller's connector (J1->1, J2->2, etc.)
        2. Find connected sensor device via Pin table
        3. Get sensor's device template
        4. Map component (sensor-1) to datapoint based on position
        
        Args:
            controller_device_id: Controller device ID
            connector: Connector identifier (J1, J2, J3, J4)
            component: Component identifier (sensor-1, sensor-2, etc.)
            
        Returns:
            Tuple of (sensor_device_id, datapoint_id, datapoint_metadata) or None if not found
        """
        # Map connector string to number
        connector_mapping = {"J1": 1, "J2": 2, "J3": 3, "J4": 4}
        connector_number = connector_mapping.get(connector)
        if not connector_number:
            logger.warning(f"Invalid connector format: {connector}")
            return None
            
        # Extract sensor number from component (sensor-1 -> 1)
        try:
            sensor_number = int(component.split('-')[1])
        except (IndexError, ValueError):
            logger.warning(f"Invalid component format: {component}")
            return None
            
        cache_key = f"sensor_mapping:{controller_device_id}:{connector_number}:{sensor_number}"
        
        try:
            # Try Redis cache first
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                self.cache_hits += 1
                parts = cached_result.split(':')
                sensor_device_id, datapoint_id = int(parts[0]), int(parts[1])
                # Get datapoint metadata from cache or database
                metadata = self.get_datapoint_metadata(datapoint_id)
                return sensor_device_id, datapoint_id, metadata
                
            # Cache miss - query PostgreSQL
            self.cache_misses += 1
            with self.postgres_conn.cursor() as cursor:
                # Complex query to find connected sensor and its datapoints with metadata
                cursor.execute("""
                    SELECT 
                        pin."DeviceId" as sensor_device_id,
                        dp."DataPointId",
                        dp."Label",
                        dt."Name" as device_template_name,
                        dp."DataEncoding",
                        dp."Offset",
                        dp."Length",
                        dp."Decimals"
                    FROM "Connector" c
                    JOIN "Pin" pin ON c."ConnectorId" = pin."ConnectorId"
                    JOIN "Device" sensor_dev ON pin."DeviceId" = sensor_dev."DeviceId" 
                    JOIN "DeviceTemplate" dt ON sensor_dev."DeviceTemplateId" = dt."DeviceTemplateId"
                    JOIN "DataPoint" dp ON dt."DeviceTemplateId" = dp."DeviceTemplateId"
                    WHERE c."ControllerId" = %s 
                        AND c."ConnectorNumber" = %s
                        AND pin."Position" = %s
                    ORDER BY dp."DataPointId"
                """, (controller_device_id, connector_number, sensor_number))
                
                results = cursor.fetchall()
                
                if results:
                    # Take the first datapoint for this sensor position
                    sensor_device_id, datapoint_id, label, template_name, encoding, offset, length, decimals = results[0]
                    
                    # Create metadata object
                    metadata = {
                        'encoding': encoding,
                        'offset': offset,
                        'length': length,
                        'decimals': decimals,
                        'label': label
                    }
                    
                    # Cache the basic mapping (device_id:datapoint_id)
                    cache_value = f"{sensor_device_id}:{datapoint_id}"
                    self.redis_client.setex(cache_key, self.cache_ttl, cache_value)
                    
                    # Cache the metadata separately
                    metadata_key = f"datapoint_metadata:{datapoint_id}"
                    import json
                    self.redis_client.setex(metadata_key, self.cache_ttl, json.dumps(metadata))
                    
                    logger.debug(f"Found sensor mapping: Controller {controller_device_id} -> {connector} -> Sensor {template_name} -> DataPoint {label}")
                    return sensor_device_id, datapoint_id, metadata
                else:
                    logger.debug(f"No sensor mapping found for Controller {controller_device_id}, Connector {connector_number}, Position {sensor_number}")
                    
        except Exception as e:
            logger.error(f"Error getting sensor mapping: {e}")
            
        return None
        
    def get_datapoint_metadata(self, datapoint_id: int) -> Optional[dict]:
        """Get datapoint metadata for hex decoding."""
        cache_key = f"datapoint_metadata:{datapoint_id}"
        
        try:
            # Try cache first
            cached_metadata = self.redis_client.get(cache_key)
            if cached_metadata:
                import json
                return json.loads(cached_metadata)
                
            # Query database
            with self.postgres_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT "DataEncoding", "Offset", "Length", "Decimals", "Label"
                    FROM "DataPoint" 
                    WHERE "DataPointId" = %s
                """, (datapoint_id,))
                
                result = cursor.fetchone()
                if result:
                    encoding, offset, length, decimals, label = result
                    metadata = {
                        'encoding': encoding,
                        'offset': offset,
                        'length': length,
                        'decimals': decimals,
                        'label': label
                    }
                    
                    # Cache the metadata
                    import json
                    self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(metadata))
                    return metadata
                    
        except Exception as e:
            logger.error(f"Error getting datapoint metadata for {datapoint_id}: {e}")
            
        return None
        
    def parse_sensor_data(self, payload: Dict[str, Any], datapoint_metadata: dict = None) -> Optional[float]:
        """
        Parse sensor data from payload using DataPoint metadata when available.
        
        Args:
            payload: Raw payload from MQTT message
            datapoint_metadata: DataPoint metadata for hex decoding
            
        Returns:
            Parsed numeric value or None
        """
        try:
            # Handle different payload formats
            if isinstance(payload, dict):
                # Check for 'data' field (hex sensor data)
                if 'data' in payload:
                    hex_data = payload['data']
                    if datapoint_metadata:
                        return self.extract_value_from_hex(hex_data, datapoint_metadata)
                    else:
                        # Fallback to simple extraction if no metadata
                        logger.warning("No datapoint metadata available for hex decoding")
                        return None
                    
                # Check for direct numeric fields
                for key in ['value', 'voltage', 'temperature', 'current']:
                    if key in payload:
                        return float(payload[key])
                        
            elif isinstance(payload, (int, float)):
                return float(payload)
                
            elif isinstance(payload, str):
                # Try to extract numeric value from string
                match = re.search(r'(-?\d+\.?\d*)', payload)
                if match:
                    return float(match.group(1))
                    
        except Exception as e:
            logger.warning(f"Error parsing sensor data from payload {payload}: {e}")
            
        return None
        
    def extract_value_from_hex(self, hex_data: str, datapoint_metadata: dict) -> Optional[float]:
        """
        Extract numeric value from hex sensor data using DataPoint metadata.
        
        Uses DataEncoding, Offset, Length, and Decimals from the DataPoint table
        to properly decode different sensor values.
        
        Args:
            hex_data: Hex string data
            datapoint_metadata: Dict containing encoding, offset, length, decimals
            
        Returns:
            Extracted numeric value or None
        """
        try:
            # Remove spaces and convert to bytes
            hex_clean = hex_data.replace(' ', '')
            
            # Get metadata values
            encoding = datapoint_metadata.get('encoding', 'Uint16')
            offset = datapoint_metadata.get('offset', 0)
            length = datapoint_metadata.get('length', 2)
            decimals = datapoint_metadata.get('decimals', 0)
            
            # Calculate start and end positions in hex string (each byte = 2 hex chars)
            start_pos = offset * 2
            end_pos = start_pos + (length * 2)
            
            # Check if we have enough data
            if len(hex_clean) < end_pos:
                logger.warning(f"Hex data too short: need {end_pos} chars, got {len(hex_clean)}")
                return None
                
            # Extract the relevant bytes
            hex_subset = hex_clean[start_pos:end_pos]
            
            # Decode based on encoding type
            if encoding == 'Int16':
                # Signed 16-bit integer
                raw_value = int(hex_subset, 16)
                # Convert to signed if necessary (two's complement)
                if raw_value >= 32768:  # 2^15
                    raw_value = raw_value - 65536  # 2^16
            elif encoding == 'Uint16':
                # Unsigned 16-bit integer
                raw_value = int(hex_subset, 16)
            elif encoding == 'Int8':
                # Signed 8-bit integer
                raw_value = int(hex_subset, 16)
                if raw_value >= 128:  # 2^7
                    raw_value = raw_value - 256  # 2^8
            elif encoding == 'Uint8':
                # Unsigned 8-bit integer
                raw_value = int(hex_subset, 16)
            else:
                # Default to unsigned 16-bit
                logger.warning(f"Unknown encoding {encoding}, defaulting to Uint16")
                raw_value = int(hex_subset, 16)
                
            # Apply decimal scaling
            if decimals > 0:
                scaled_value = raw_value / (10 ** decimals)
            else:
                scaled_value = float(raw_value)
                
            logger.debug(f"Decoded hex {hex_subset} with {encoding}: raw={raw_value}, scaled={scaled_value}")
            return scaled_value
            
        except Exception as e:
            logger.warning(f"Error extracting value from hex {hex_data} with metadata {datapoint_metadata}: {e}")
            
        return None
        
    def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw IoT message following the production database architecture.
        
        This implements the complex controller->connector->pin->sensor->datapoint mapping
        required by the production database schema.
        
        Args:
            message: Raw message from Kafka
            
        Returns:
            Processed message or None if processing failed
        """
        try:
            # Extract controller MAC address
            device_mac = message.get('device_mac', '')
            if not device_mac:
                logger.warning("No device MAC in message")
                return None
                
            # Get controller device ID
            controller_device_id = self.get_device_id_from_mac(device_mac)
            if controller_device_id is None:
                logger.warning(f"Could not find controller device ID for MAC {device_mac}")
                return None
                
            # Extract connector and component info
            connector = message.get('connector', '')  # e.g., "J1"
            component = message.get('component', '')  # e.g., "sensor-1"
            
            if not connector or not component:
                logger.warning(f"Missing connector ({connector}) or component ({component}) in message")
                return None
                
            # Get connected sensor device and datapoint using production architecture
            sensor_mapping = self.get_connected_sensor_and_datapoint(
                controller_device_id, connector, component
            )
            
            if sensor_mapping is None:
                logger.warning(f"Could not find sensor mapping for Controller {controller_device_id}, Connector {connector}, Component {component}")
                return None
                
            sensor_device_id, datapoint_id, datapoint_metadata = sensor_mapping
                
            # Parse sensor value using datapoint metadata
            payload = message.get('payload', {})
            value = self.parse_sensor_data(payload, datapoint_metadata)
            
            # Create optimized data structure using the connected sensor's device ID
            # This follows the production model where data is attributed to the sensor device,
            # not the controller device
            processed_data = {
                'timestamp': message.get('timestamp', datetime.now().isoformat()),
                'device_id': sensor_device_id,  # Use sensor device ID, not controller
                'datapoint_id': datapoint_id,
                'value': value,
                # Add metadata for debugging
                'controller_device_id': controller_device_id,
                'connector': connector,
                'component': component
            }
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None
            
    def print_stats(self):
        """Print processing statistics."""
        current_time = time.time()
        elapsed = current_time - self.last_stats_time
        
        if elapsed >= 60:  # Print stats every minute
            cache_hit_rate = (self.cache_hits / (self.cache_hits + self.cache_misses)) * 100 if (self.cache_hits + self.cache_misses) > 0 else 0
            logger.info(f"Statistics - Processed: {self.messages_processed}, Cache hits: {self.cache_hits}, Cache misses: {self.cache_misses}, Hit rate: {cache_hit_rate:.1f}%")
            self.last_stats_time = current_time
            
    def start(self):
        """Start the stream processor."""
        logger.info("Starting Stream Processor")
        
        try:
            # Setup connections
            self.setup_postgres_connection()
            self.setup_redis_client()
            self.setup_kafka_consumer()
            self.setup_kafka_producer()
            
            self.running = True
            logger.info("Stream Processor started successfully")
            
            # Main processing loop
            while self.running:
                try:
                    # Poll for messages
                    message_batch = self.kafka_consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            try:
                                # Process the message
                                processed_data = self.process_message(message.value)
                                
                                if processed_data:
                                    # Send to processed topic
                                    future = self.kafka_producer.send(
                                        self.kafka_processed_topic,
                                        key=str(processed_data['device_id']),
                                        value=processed_data
                                    )
                                    
                                    self.messages_processed += 1
                                    
                            except Exception as e:
                                logger.error(f"Error processing individual message: {e}")
                                
                    # Print stats periodically
                    self.print_stats()
                    
                except Exception as e:
                    logger.error(f"Error in main processing loop: {e}")
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Stream processor error: {e}")
            raise
        finally:
            self.stop()
            
    def stop(self):
        """Stop the stream processor."""
        logger.info("Stopping Stream Processor")
        self.running = False
        
        if self.kafka_consumer:
            self.kafka_consumer.close()
            
        if self.kafka_producer:
            self.kafka_producer.flush()
            self.kafka_producer.close()
            
        if self.postgres_conn:
            self.postgres_conn.close()
            
        if self.redis_client:
            self.redis_client.close()
            
        logger.info("Stream Processor stopped")
        
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start processor
    processor = StreamProcessor()
    processor.start()