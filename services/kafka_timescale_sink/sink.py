import json
import logging
import os
import time
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import execute_batch
from kafka import KafkaConsumer
import signal
import sys
from datetime import datetime
from pydantic import BaseModel, Field, validator, ValidationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IotMeasurement(BaseModel):
    """Pydantic model for an IoT measurement record."""
    timestamp: datetime
    device_id: str = Field(..., alias='mac_address')
    connector_mode: str = Field('unknown', alias='mode')
    component_type: str = Field('unknown', alias='data_point_label')
    pin_position: str = Field('-1', alias='pin')
    value: Optional[float] = None
    unit: str = ''
    topic: str = Field('', alias='original_topic')

    @validator('timestamp', pre=True)
    def convert_timestamp(cls, v):
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return datetime.fromtimestamp(float(v))
                except (ValueError, TypeError):
                    pass
        return datetime.now()

    @validator('value', pre=True)
    def convert_value_to_float(cls, v):
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert value '{v}' to float, setting to None")
            return None
            
    class Config:
        orm_mode = True
        
class KafkaTimescaleSink:
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.input_topic = os.getenv('KAFKA_INPUT_TOPIC', 'decoded_iot_data')
        
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
        
        self._insert_statement = self._build_insert_statement()
        
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
            consumer_timeout_ms=1000
        )
        logger.info("Kafka consumer initialized")

    def _build_insert_statement(self) -> str:
        """Dynamically build the INSERT statement from the Pydantic model."""
        fields = list(IotMeasurement.__fields__.keys())
        columns = ', '.join(fields)
        placeholders = ', '.join(['%s'] * len(fields))
        return f"INSERT INTO iot_measurements ({columns}) VALUES ({placeholders})"

    def _prepare_record(self, message: Dict[str, Any]) -> Optional[tuple]:
        """Validate and prepare a record using the Pydantic model."""
        try:
            # Add missing fields with default values before validation
            message.setdefault('timestamp', time.time())
            
            record = IotMeasurement.parse_obj(message)
            
            # The order of fields is guaranteed by dict in Python 3.7+
            return tuple(record.dict().values())
            
        except ValidationError as e:
            logger.error(f"Data validation failed: {e} - for message: {message}")
            return None
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
                        self._insert_statement,
                        records,
                        page_size=self.batch_size
                    )
                logger.info(f"Inserted batch of {len(records)} records into TimescaleDB")
            
            self.message_batch.clear()
            self.last_batch_time = time.time()
            
        except Exception as e:
            logger.error(f"Error inserting batch: {e}")
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
        time.sleep(20)
        
        try:
            self._setup_database_connection()
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
        if self.db_connection:
            self.db_connection.close()

if __name__ == "__main__":
    sink = KafkaTimescaleSink()
    sink.run()