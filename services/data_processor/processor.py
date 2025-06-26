import json
import logging
import os
import re
import time
from typing import Dict, Any, Optional, Tuple, List
import psycopg2
from psycopg2.extras import DictCursor
from kafka import KafkaConsumer, KafkaProducer
import signal
import sys
import struct

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'raw_iot_data')
        self.output_topic = os.getenv('KAFKA_OUTPUT_TOPIC', 'decoded_iot_data')
        
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

    def _parse_mqtt_topic(self, topic: str) -> Optional[Tuple[str, str, int, int]]:
        """
        Parse MQTT topic to extract components based on the format:
        cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/sensor-<N>
        """
        pattern = r'cmnd/f2-([a-fA-F0-9]+)/([^/]+)/(\d+)/sensor-(\d+)'
        match = re.match(pattern, topic)
        
        if match:
            mac_addr = match.group(1)
            mode = match.group(2)
            connector_number = int(match.group(3))
            pin_position = int(match.group(4))
            return mac_addr, mode, connector_number, pin_position
        
        logger.warning(f"Topic '{topic}' does not match expected format.")
        return None

    def _get_data_points(self, mac_addr: str, connector_number: int, pin_position: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve data points for a device connected to a specific controller pin."""
        query = '''
        SELECT dp.*
        FROM "DataPoint" dp
        JOIN "DeviceTemplate" dt ON dp."DeviceTemplateId" = dt."DeviceTemplateId"
        JOIN "Device" d ON dt."DeviceTemplateId" = d."DeviceTemplateId"
        JOIN "Pin" p ON d."DeviceId" = p."DeviceId"
        JOIN "Connector" c ON p."ConnectorId" = c."ConnectorId"
        JOIN "Device" controller ON c."ControllerId" = controller."DeviceId"
        WHERE controller."MacAddress" ILIKE %s
          AND c."ConnectorNumber" = %s
          AND p."Position" = %s;
        '''
        try:
            with self.db_connection.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, (mac_addr, connector_number, pin_position))
                results = cursor.fetchall()
                
                if results:
                    return [dict(row) for row in results]
                else:
                    logger.warning(f"No data points found for device at MAC/connector/pin: {mac_addr}/{connector_number}/{pin_position}")
                    return None
        except psycopg2.Error as e:
            logger.error(f"Database query error for data points: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during DB query: {e}")
            return None

    def _decode_data(self, hex_data: str, data_point: Dict[str, Any]) -> Optional[Any]:
        """Decodes a segment of hex data based on a data point definition."""
        try:
            offset = data_point['Offset']
            length = data_point['Length']
            data_format = data_point['DataFormat']
            
            hex_data = hex_data.replace(" ", "")
            
            start_index = offset * 2
            end_index = start_index + length * 2
            
            if end_index > len(hex_data):
                logger.warning(f"Data point '{data_point['Label']}' (offset: {offset}, length: {length}) is out of bounds for hex data of length {len(hex_data)/2} bytes.")
                return None
                
            segment = hex_data[start_index:end_index]
            byte_data = bytes.fromhex(segment)

            decoded_value = None
            
            if data_format == 'Int16':
                decoded_value = struct.unpack('>h', byte_data)[0]
            elif data_format == 'Uint16':
                decoded_value = struct.unpack('>H', byte_data)[0]
            else:
                logger.warning(f"Unsupported data format: '{data_format}' for data point '{data_point['Label']}'")
                return None

            if 'Decimals' in data_point and data_point['Decimals'] > 0:
                decoded_value = decoded_value / (10 ** data_point['Decimals'])
            
            prepend = data_point.get('Prepend', '')
            append = data_point.get('Append', '')
            
            if prepend or append:
                return f"{prepend}{decoded_value}{append}"
            else:
                return decoded_value

        except (struct.error, ValueError) as e:
            logger.error(f"Error decoding data for data point '{data_point.get('Label', 'N/A')}': {e}. Segment: {segment}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during data decoding: {e}")
            return None

    def _process_message(self, message):
        """Process a single message from Kafka."""
        try:
            data = message.value
            original_topic = data.get('original_topic', '')
            payload = data.get('payload', {})
            
            if not original_topic or 'data' not in payload:
                logger.debug(f"Skipping message with missing topic or payload data: {data}")
                return

            topic_parts = self._parse_mqtt_topic(original_topic)
            if not topic_parts:
                return

            mac_addr, mode, connector_number, pin_position = topic_parts
            
            data_points = self._get_data_points(mac_addr, connector_number, pin_position)
            if not data_points:
                return

            hex_data = payload['data']
            message_timestamp = payload.get('timestamp', time.time())
            
            for dp in data_points:
                decoded_value = self._decode_data(hex_data, dp)
                
                if decoded_value is not None:
                    enriched_message = {
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
                    
                    key = f"{mac_addr}-{connector_number}-{pin_position}-{dp['Label']}"
                    self.producer.send(self.output_topic, key=key, value=enriched_message)
                    logger.info(f"Processed and sent data for {key} - value: {decoded_value}")

        except json.JSONDecodeError:
            logger.error(f"Failed to decode Kafka message value: {message.value}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in _process_message: {e}", exc_info=True)

    def run(self):
        logger.info("Starting Data Processor")
        
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
