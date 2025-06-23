import json
import logging
import os
import re
import time
from typing import Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import DictCursor
from kafka import KafkaConsumer, KafkaProducer
import signal
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'raw_iot_data')
        self.output_topic = os.getenv('KAFKA_OUTPUT_TOPIC', 'decoded_iot_data')
        
        # PostgreSQL connection parameters
        self.pg_host = os.getenv('POSTGRES_HOST', 'postgres')
        self.pg_db = os.getenv('POSTGRES_DB', 'device_params')
        self.pg_user = os.getenv('POSTGRES_USER', 'iot_user')
        self.pg_password = os.getenv('POSTGRES_PASSWORD', 'iot_password')
        self.pg_port = os.getenv('POSTGRES_PORT', '5432')
        
        self.consumer = None
        self.producer = None
        self.db_connection = None
        self.running = True
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _setup_database_connection(self):
        try:
            self.db_connection = psycopg2.connect(
                host=self.pg_host,
                port=self.pg_port,
                database=self.pg_db,
                user=self.pg_user,
                password=self.pg_password
            )
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

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

    def _parse_mqtt_topic(self, topic: str) -> Tuple[str, str, str, Optional[str]]:
        """Parse MQTT topic to extract components."""
        # Pattern: cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/<COMPONENT>-<ID>
        pattern = r'cmnd/f2-([a-fA-F0-9]+)/([^/]+)/([^/]+)/([^-]+)(?:-(\d+))?'
        match = re.match(pattern, topic)
        
        if match:
            mac_addr = match.group(1)
            mode = match.group(2)
            connector = match.group(3)
            component_type = match.group(4)
            component_id = match.group(5)
            
            device_id = f"f2-{mac_addr}"
            return device_id, mode, component_type, component_id
        
        # Fallback for simpler patterns
        parts = topic.split('/')
        if len(parts) >= 4:
            device_id = parts[1]
            mode = parts[2] if len(parts) > 2 else 'unknown'
            component_type = parts[-1].split('-')[0]
            component_id = parts[-1].split('-')[1] if '-' in parts[-1] else None
            return device_id, mode, component_type, component_id
        
        return "unknown", "unknown", "unknown", None

    def _get_device_parameters(self, device_id: str, connector_mode: str, 
                             component_type: str, component_id: Optional[str]) -> Optional[Dict]:
        """Retrieve device parameters from PostgreSQL."""
        try:
            with self.db_connection.cursor(cursor_factory=DictCursor) as cursor:
                query = """
                SELECT encoding_type, units, scaling_factor 
                FROM device_parameters 
                WHERE device_id = %s AND connector_mode = %s 
                AND component_type = %s AND (component_id = %s OR component_id IS NULL)
                ORDER BY component_id NULLS LAST
                LIMIT 1
                """
                
                cursor.execute(query, (device_id, connector_mode, component_type, component_id))
                result = cursor.fetchone()
                
                if result:
                    return dict(result)
                else:
                    logger.warning(f"No parameters found for {device_id}/{connector_mode}/{component_type}/{component_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return None

    def _decode_value(self, raw_data: Any, encoding_type: str, scaling_factor: float) -> Any:
        """Decode raw data based on encoding type."""
        try:
            if encoding_type == 'boolean':
                if isinstance(raw_data, dict) and 'status' in raw_data:
                    return bool(raw_data['status'])
                return bool(raw_data)
            
            elif encoding_type == 'boolean_map':
                if isinstance(raw_data, dict):
                    # For door sensors, exit buttons, etc.
                    return {k: bool(v) for k, v in raw_data.items() if k != 'timestamp'}
                return raw_data
            
            elif encoding_type == 'hex_to_float':
                if isinstance(raw_data, dict) and 'data' in raw_data:
                    hex_value = raw_data['data']
                    if isinstance(hex_value, str):
                        # Convert hex string to float
                        try:
                            int_value = int(hex_value, 16)
                            return float(int_value) * scaling_factor
                        except ValueError:
                            logger.warning(f"Could not convert hex value: {hex_value}")
                            return None
                return raw_data
            
            elif encoding_type == 'raw_string':
                if isinstance(raw_data, dict) and 'data' in raw_data:
                    return str(raw_data['data'])
                return str(raw_data)
            
            else:
                logger.warning(f"Unknown encoding type: {encoding_type}")
                return raw_data
                
        except Exception as e:
            logger.error(f"Error decoding value: {e}")
            return raw_data

    def _process_message(self, message):
        """Process a single message from Kafka."""
        try:
            data = message.value
            original_topic = data.get('original_topic', '')
            device_id = data.get('device_id', '')
            payload = data.get('payload', {})
            kafka_timestamp = data.get('timestamp', time.time())
            
            # Parse the MQTT topic
            parsed_device_id, connector_mode, component_type, component_id = self._parse_mqtt_topic(original_topic)
            
            # Use parsed device_id if available
            if parsed_device_id != "unknown":
                device_id = parsed_device_id
            
            # Get device parameters
            params = self._get_device_parameters(device_id, connector_mode, component_type, component_id)
            
            if not params:
                logger.warning(f"Skipping message - no parameters found for {device_id}")
                return
            
            # Extract timestamp from payload if available
            message_timestamp = payload.get('timestamp', kafka_timestamp)
            if isinstance(message_timestamp, str):
                # Try to parse timestamp string
                try:
                    import datetime
                    dt = datetime.datetime.fromisoformat(message_timestamp.replace('Z', '+00:00'))
                    message_timestamp = dt.timestamp()
                except:
                    message_timestamp = kafka_timestamp
            
            # Decode the value
            decoded_value = self._decode_value(
                payload, 
                params['encoding_type'], 
                params['scaling_factor']
            )
            
            # Create enriched message
            enriched_message = {
                'timestamp': message_timestamp,
                'device_id': device_id,
                'connector_mode': connector_mode,
                'component_type': component_type,
                'component_id': component_id,
                'value': decoded_value,
                'unit': params['units'],
                'original_topic': original_topic,
                'raw_data': payload
            }
            
            # Send to output topic
            self.producer.send(
                self.output_topic,
                key=device_id,
                value=enriched_message
            )
            
            logger.debug(f"Processed message for {device_id}/{component_type}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        logger.info("Starting Data Processor")
        
        # Wait for services to be ready
        time.sleep(15)
        
        try:
            self._setup_database_connection()
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
        if self.db_connection:
            self.db_connection.close()

if __name__ == "__main__":
    processor = DataProcessor()
    processor.run()