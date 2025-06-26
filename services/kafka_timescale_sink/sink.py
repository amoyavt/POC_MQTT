import json
import logging
import os
import time
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_batch
from kafka import KafkaConsumer
import signal
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KafkaTimescaleSink:
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'decoded_iot_data')
        
        # TimescaleDB connection parameters
        self.ts_host = os.getenv('TIMESCALE_HOST', 'timescaledb')
        self.ts_db = os.getenv('TIMESCALE_DB', 'timeseries')
        self.ts_user = os.getenv('TIMESCALE_USER', 'ts_user')
        self.ts_password = os.getenv('TIMESCALE_PASSWORD', 'ts_password')
        self.ts_port = os.getenv('TIMESCALE_PORT', '5432')
        
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.batch_timeout = int(os.getenv('BATCH_TIMEOUT', '5'))
        
        self.consumer = None
        self.db_connection = None
        self.running = True
        self.message_batch = []
        self.last_batch_time = time.time()
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _setup_database_connection(self):
        try:
            self.db_connection = psycopg2.connect(
                host=self.ts_host,
                port=self.ts_port,
                database=self.ts_db,
                user=self.ts_user,
                password=self.ts_password
            )
            self.db_connection.autocommit = True
            logger.info("Connected to TimescaleDB")
        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            raise

    def _setup_kafka_consumer(self):
        self.consumer = KafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.kafka_servers.split(','),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='timescale_sink_group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=1000  # Timeout to allow batch processing
        )
        logger.info("Kafka consumer initialized")

    def _convert_timestamp(self, timestamp: Any) -> datetime:
        """Convert various timestamp formats to datetime."""
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            try:
                # Try ISO format
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                try:
                    # Try parsing as float string
                    return datetime.fromtimestamp(float(timestamp))
                except:
                    # Default to current time
                    return datetime.now()
        else:
            return datetime.now()

    def _extract_numeric_value(self, value: Any) -> Optional[float]:
        """Extract a numeric value from various data types."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return float(value)
        elif isinstance(value, dict):
            # For complex values like door sensors, try to extract a summary
            if all(isinstance(v, bool) for v in value.values()):
                # Count of True values for boolean maps
                return float(sum(value.values()))
            # Try to find first numeric value
            for v in value.values():
                if isinstance(v, (int, float)):
                    return float(v)
        elif isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        return None

    def _prepare_record(self, message: Dict[str, Any]) -> Optional[tuple]:
        """Prepare a record for insertion into TimescaleDB."""
        try:
            timestamp = self._convert_timestamp(message.get('timestamp', time.time()))
            device_id = message.get('mac_address', 'unknown')
            connector_mode = message.get('mode', 'unknown')
            component_type = message.get('data_point_label', 'unknown')
            component_id = str(message.get('pin', -1)) # Use pin as component_id, default to -1
            unit = message.get('unit', '')
            raw_data = message.get('original_topic', {})
            
            # Extract numeric value
            value = self._extract_numeric_value(message.get('value'))
            
            # Store raw data as JSONB
            raw_data_json = json.dumps(raw_data) if raw_data else None
            
            return (
                timestamp,
                device_id,
                connector_mode,
                component_type,
                component_id,
                value,
                unit,
                raw_data_json
            )
            
        except Exception as e:
            logger.error(f"Error preparing record: {e}")
            return None

    def _insert_batch(self):
        """Insert a batch of records into TimescaleDB."""
        if not self.message_batch:
            return
            
        try:
            records = []
            for message in self.message_batch:
                record = self._prepare_record(message)
                if record:
                    records.append(record)
            
            if records:
                with self.db_connection.cursor() as cursor:
                    execute_batch(
                        cursor,
                        """
                        INSERT INTO iot_measurements 
                        (timestamp, device_id, connector_mode, component_type, component_id, value, unit, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        records,
                        page_size=self.batch_size
                    )
                    
                logger.info(f"Inserted batch of {len(records)} records into TimescaleDB")
            
            self.message_batch.clear()
            self.last_batch_time = time.time()
            
        except Exception as e:
            logger.error(f"Error inserting batch: {e}")
            # Clear batch to avoid infinite retry
            self.message_batch.clear()

    def _should_flush_batch(self) -> bool:
        """Check if batch should be flushed."""
        return (
            len(self.message_batch) >= self.batch_size or
            (time.time() - self.last_batch_time) >= self.batch_timeout
        )

    def _process_message(self, message):
        """Process a single message from Kafka."""
        try:
            data = message.value
            self.message_batch.append(data)
            
            if self._should_flush_batch():
                self._insert_batch()
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        logger.info("Starting Kafka-TimescaleDB Sink")
        
        # Wait for services to be ready
        time.sleep(20)
        
        try:
            self._setup_database_connection()
            self._setup_kafka_consumer()
            
            logger.info("Sink started, waiting for messages...")
            
            while self.running:
                try:
                    # Poll for messages with timeout
                    message_batch = self.consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            self._process_message(message)
                    
                    # Check if we should flush due to timeout
                    if self._should_flush_batch():
                        self._insert_batch()
                        
                except Exception as e:
                    logger.error(f"Error in message processing loop: {e}")
                    time.sleep(1)
            
            # Flush any remaining messages
            if self.message_batch:
                self._insert_batch()
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        logger.info("Cleaning up connections...")
        if self.consumer:
            self.consumer.close()
        if self.db_connection:
            self.db_connection.close()

if __name__ == "__main__":
    sink = KafkaTimescaleSink()
    sink.run()