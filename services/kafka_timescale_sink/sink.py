import json
import logging
import os
import sys
import time
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import execute_batch
from psycopg2.pool import ThreadedConnectionPool
from kafka import KafkaConsumer
import signal
from pydantic import ValidationError

# Add the parent directory to Python path to import shared modules
sys.path.append('/app/shared')
from models import IotMeasurement

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/sink.log', mode='a') if os.path.exists('/app/logs') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Set specific log levels for different operations
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('psycopg2').setLevel(logging.WARNING)
        
class KafkaTimescaleSink:
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'decoded_iot_data')
        
        self.ts_host = os.getenv('TIMESCALE_HOST', 'timescaledb')
        self.ts_db = os.getenv('TIMESCALE_DB', 'timeseries')
        self.ts_user = os.getenv('TIMESCALE_USER', 'ts_user')
        self.ts_password = self._get_password_from_file(
            os.getenv('TIMESCALE_PASSWORD_FILE'),
            os.getenv('TIMESCALE_PASSWORD', 'ts_password')
        )
        self.ts_port = os.getenv('TIMESCALE_PORT', '5432')
        
        # Optimized batch processing
        self.batch_size = int(os.getenv('BATCH_SIZE', '1000'))  # Increased from 100
        self.batch_timeout = int(os.getenv('BATCH_TIMEOUT', '10'))  # Increased from 5
        
        # Connection pooling
        self.db_pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
        self.db_pool_min = int(os.getenv('DB_POOL_MIN', '2'))
        
        self.consumer = None
        self.db_pool = None
        self.running = True
        self.message_batch = []
        self.last_batch_time = time.time()
        
        self._insert_statement = self._build_insert_statement()
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _get_password_from_file(self, password_file: Optional[str], default_password: str) -> str:
        """Securely load password from file or environment variable."""
        if password_file and os.path.exists(password_file):
            try:
                with open(password_file, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"Failed to read password file {password_file}: {e}")
        return default_password
    
    def _setup_database_pool(self):
        """Setup connection pooling for better performance."""
        try:
            self.db_pool = ThreadedConnectionPool(
                minconn=self.db_pool_min,
                maxconn=self.db_pool_size,
                host=self.ts_host,
                port=self.ts_port,
                database=self.ts_db,
                user=self.ts_user,
                password=self.ts_password
            )
            logger.info(f"Connected to TimescaleDB with connection pool (min: {self.db_pool_min}, max: {self.db_pool_size})")
        except Exception as e:
            logger.error(f"Failed to create TimescaleDB connection pool: {e}")
            raise

    def _setup_kafka_consumer(self):
        self.consumer = KafkaConsumer(
            self.input_topic,
            bootstrap_servers=self.kafka_servers.split(','),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='timescale_sink_group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=1000
        )
        logger.info("Kafka consumer initialized")

    def _build_insert_statement(self) -> str:
        """Build the INSERT statement with correct column names."""
        # Use the actual database column names in the correct order
        columns = "timestamp, device_id, connector_mode, datapoint_label, pin_position, value, unit, topic"
        placeholders = ', '.join(['%s'] * 8)
        return f"INSERT INTO iot_measurements ({columns}) VALUES ({placeholders})"

    def _prepare_record(self, message: Dict[str, Any]) -> Optional[tuple]:
        """Validate and prepare a record using the Pydantic model."""
        try:
            # Add missing fields with default values before validation
            message.setdefault('timestamp', time.time())
            
            record = IotMeasurement.model_validate(message)
            
            # Return values in the exact order matching the INSERT statement
            return (
                record.timestamp,
                record.device_id,
                record.connector_mode,
                record.datapoint_label,
                record.pin_position,
                record.value,
                record.unit,
                record.topic
            )
            
        except ValidationError as e:
            logger.error(f"Data validation failed: {e} - for message: {message}")
            return None
        except Exception as e:
            logger.error(f"Error preparing record: {e}")
            return None

    def _insert_batch(self):
        """Insert a batch of records into TimescaleDB with enhanced error handling."""
        if not self.message_batch:
            logger.debug("No messages in batch to insert")
            return
            
        batch_start_time = time.time()
        batch_size = len(self.message_batch)
        
        try:
            records = []
            failed_records = 0
            
            for message in self.message_batch:
                record = self._prepare_record(message)
                if record:
                    records.append(record)
                else:
                    failed_records += 1
            
            if records:
                conn = self.db_pool.getconn()
                conn.autocommit = True
                
                with conn.cursor() as cursor:
                    execute_batch(
                        cursor,
                        self._insert_statement,
                        records,
                        page_size=min(self.batch_size * 2, 2000)  # Larger page size for better performance
                    )
                
                self.db_pool.putconn(conn)
                
                processing_time = time.time() - batch_start_time
                logger.info(
                    f"Successfully inserted {len(records)} records into TimescaleDB "
                    f"(failed: {failed_records}, batch_size: {batch_size}, time: {processing_time:.3f}s)"
                )
                
                if failed_records > 0:
                    logger.warning(f"Failed to prepare {failed_records} records out of {batch_size}")
            else:
                logger.warning(f"No valid records in batch of {batch_size} messages")
            
            self.message_batch.clear()
            self.last_batch_time = time.time()
            
        except psycopg2.OperationalError as e:
            logger.error(f"Database connection error during batch insert: {e}")
            # Connection pooling will handle reconnection automatically
            self.message_batch.clear()
            
        except psycopg2.Error as e:
            logger.error(f"Database error during batch insert: {e}")
            logger.debug(f"Failed batch size: {len(records)} records")
            self.message_batch.clear()
            
        except Exception as e:
            logger.error(f"Unexpected error inserting batch: {e}", exc_info=True)
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
        logger.info("Starting Kafka-TimescaleDB Sink with optimized batch processing")
        time.sleep(20)
        
        try:
            self._setup_database_pool()
            self._setup_kafka_consumer()
            logger.info("Sink started, waiting for messages...")
            
            while self.running:
                try:
                    message_batch = self.consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            self._process_message(message)
                    
                    if self._should_flush_batch():
                        self._insert_batch()
                        
                except Exception as e:
                    logger.error(f"Error in message processing loop: {e}")
                    time.sleep(1)
            
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
        if self.db_pool:
            self.db_pool.closeall()

if __name__ == "__main__":
    sink = KafkaTimescaleSink()
    sink.run()