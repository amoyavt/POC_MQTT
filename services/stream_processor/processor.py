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
from shared.models import IotMeasurement, DecodedData, DeviceLookup, DataPointLookup

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
                compression_type='snappy',
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
        
    def get_datapoint_id_from_label(self, label: str, device_template_id: int = None) -> Optional[int]:
        """
        Get datapoint ID from label using Redis cache and PostgreSQL fallback.
        
        Args:
            label: Datapoint label (e.g., 'sensor-1', 'Temperature')
            device_template_id: Optional device template ID for more specific lookup
            
        Returns:
            Datapoint ID as integer or None if not found
        """
        cache_key = f"datapoint_label:{label}"
        if device_template_id:
            cache_key += f":{device_template_id}"
            
        try:
            # Try Redis cache first
            datapoint_id = self.redis_client.get(cache_key)
            if datapoint_id:
                self.cache_hits += 1
                return int(datapoint_id)
                
            # Cache miss - query PostgreSQL
            self.cache_misses += 1
            with self.postgres_conn.cursor() as cursor:
                if device_template_id:
                    cursor.execute(
                        'SELECT "DataPointId" FROM "DataPoint" WHERE "Label" = %s AND "DeviceTemplateId" = %s',
                        (label, device_template_id)
                    )
                else:
                    cursor.execute(
                        'SELECT "DataPointId" FROM "DataPoint" WHERE "Label" = %s LIMIT 1',
                        (label,)
                    )
                    
                result = cursor.fetchone()
                
                if result:
                    datapoint_id = result[0]
                    # Cache the result
                    self.redis_client.setex(cache_key, self.cache_ttl, datapoint_id)
                    return datapoint_id
                    
        except Exception as e:
            logger.error(f"Error getting datapoint ID for label {label}: {e}")
            
        return None
        
    def parse_sensor_data(self, payload: Dict[str, Any]) -> Optional[float]:
        """
        Parse sensor data from payload.
        
        Args:
            payload: Raw payload from MQTT message
            
        Returns:
            Parsed numeric value or None
        """
        try:
            # Handle different payload formats
            if isinstance(payload, dict):
                # Check for 'data' field (hex sensor data)
                if 'data' in payload:
                    hex_data = payload['data']
                    # For now, just try to extract numeric values from hex
                    # In a real implementation, this would use DataPoint metadata
                    # to properly decode based on offset, length, and encoding
                    return self.extract_value_from_hex(hex_data)
                    
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
        
    def extract_value_from_hex(self, hex_data: str) -> Optional[float]:
        """
        Extract numeric value from hex sensor data.
        
        This is a simplified implementation. In production, this would use
        DataPoint metadata (offset, length, encoding) to properly decode.
        
        Args:
            hex_data: Hex string data
            
        Returns:
            Extracted numeric value or None
        """
        try:
            # Remove spaces and convert to bytes
            hex_clean = hex_data.replace(' ', '')
            if len(hex_clean) >= 4:
                # Simple extraction - take first 2 bytes as uint16
                value = int(hex_clean[:4], 16)
                return float(value / 100.0)  # Scale down for sensor values
        except Exception as e:
            logger.warning(f"Error extracting value from hex {hex_data}: {e}")
            
        return None
        
    def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single raw IoT message.
        
        Args:
            message: Raw message from Kafka
            
        Returns:
            Processed message or None if processing failed
        """
        try:
            # Extract device MAC address
            device_mac = message.get('device_mac', '')
            if not device_mac:
                logger.warning("No device MAC in message")
                return None
                
            # Get device ID
            device_id = self.get_device_id_from_mac(device_mac)
            if device_id is None:
                logger.warning(f"Could not find device ID for MAC {device_mac}")
                return None
                
            # Extract component/sensor info
            component = message.get('component', '')
            if not component:
                logger.warning("No component in message")
                return None
                
            # Get datapoint ID
            datapoint_id = self.get_datapoint_id_from_label(component)
            if datapoint_id is None:
                logger.warning(f"Could not find datapoint ID for component {component}")
                return None
                
            # Parse sensor value
            payload = message.get('payload', {})
            value = self.parse_sensor_data(payload)
            
            # Create optimized data structure
            processed_data = {
                'timestamp': message.get('timestamp', datetime.now().isoformat()),
                'device_id': device_id,
                'datapoint_id': datapoint_id,
                'value': value
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