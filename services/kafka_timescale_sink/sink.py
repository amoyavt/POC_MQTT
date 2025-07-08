#!/usr/bin/env python3
"""
Kafka-TimescaleDB Sink Service

Consumes processed IoT data from Kafka and performs optimized batch inserts
into TimescaleDB for high-performance time-series storage.
"""

import os
import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# Import shared models
sys.path.append('/app')
from shared.models import DecodedData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KafkaTimescaleSink:
    """
    High-performance Kafka to TimescaleDB sink.
    
    Consumes processed IoT data from Kafka and performs optimized batch inserts
    into TimescaleDB using efficient bulk operations and connection pooling.
    """
    
    def __init__(self):
        # Kafka Configuration
        self.kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.kafka_processed_topic = os.getenv('KAFKA_PROCESSED_TOPIC', 'processed-iot-data')
        
        # TimescaleDB Configuration
        self.timescale_host = os.getenv('TIMESCALE_HOST', 'timescaledb')
        self.timescale_user = os.getenv('TIMESCALE_USER', 'iot_user')
        self.timescale_password = os.getenv('TIMESCALE_PASSWORD', 'iot_password')
        self.timescale_db = os.getenv('TIMESCALE_DB', 'iot_timeseries')
        self.timescale_port = int(os.getenv('TIMESCALE_PORT', '5432'))
        
        # Processing Configuration
        self.batch_size = int(os.getenv('BATCH_SIZE', '1000'))
        self.flush_interval = int(os.getenv('FLUSH_INTERVAL', '10'))  # seconds
        
        # Initialize clients
        self.kafka_consumer = None
        self.timescale_conn = None
        self.running = False
        
        # Batch processing
        self.batch_buffer = []
        self.last_flush_time = time.time()
        
        # Statistics
        self.messages_consumed = 0
        self.messages_inserted = 0
        self.batch_count = 0
        self.failed_inserts = 0
        self.last_stats_time = time.time()
        
    def setup_kafka_consumer(self):
        """Initialize Kafka consumer with optimized settings."""
        try:
            self.kafka_consumer = KafkaConsumer(
                self.kafka_processed_topic,
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                group_id='timescale-sink-group',
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                # Optimized for batch processing
                fetch_max_wait_ms=1000,
                max_poll_records=self.batch_size * 2,  # Allow larger polls
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            logger.info(f"Kafka consumer connected to {self.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to create Kafka consumer: {e}")
            raise
            
    def setup_timescale_connection(self):
        """Initialize TimescaleDB connection with optimized settings."""
        try:
            self.timescale_conn = psycopg2.connect(
                host=self.timescale_host,
                user=self.timescale_user,
                password=self.timescale_password,
                database=self.timescale_db,
                port=self.timescale_port,
                # Connection optimizations
                connect_timeout=10,
                # Disable autocommit for batch operations
                autocommit=False
            )
            
            # Set optimized connection parameters
            with self.timescale_conn.cursor() as cursor:
                # Optimize for batch inserts
                cursor.execute("SET synchronous_commit = OFF")
                cursor.execute("SET wal_buffers = '16MB'")
                cursor.execute("SET checkpoint_completion_target = 0.9")
                
            self.timescale_conn.commit()
            logger.info(f"TimescaleDB connected to {self.timescale_host}:{self.timescale_db}")
            
        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            raise
            
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor with error handling."""
        cursor = None
        try:
            cursor = self.timescale_conn.cursor()
            yield cursor
        except Exception as e:
            if self.timescale_conn:
                self.timescale_conn.rollback()
            raise e
        finally:
            if cursor:
                cursor.close()
                
    def validate_and_transform_data(self, data: Dict[str, Any]) -> Optional[DecodedData]:
        """
        Validate and transform incoming data.
        
        Args:
            data: Raw data from Kafka
            
        Returns:
            Validated DecodedData instance or None if invalid
        """
        try:
            # Create DecodedData instance for validation
            decoded_data = DecodedData(**data)
            return decoded_data
        except Exception as e:
            logger.warning(f"Invalid data format: {data}, error: {e}")
            return None
            
    def batch_insert_data(self, batch_data: List[DecodedData]) -> int:
        """
        Perform optimized batch insert into TimescaleDB.
        
        Args:
            batch_data: List of validated DecodedData instances
            
        Returns:
            Number of successfully inserted records
        """
        if not batch_data:
            return 0
            
        try:
            with self.get_cursor() as cursor:
                # Prepare data for batch insert
                insert_data = []
                for data in batch_data:
                    insert_data.append((
                        data.timestamp,
                        data.device_id,
                        data.datapoint_id,
                        data.value
                    ))
                
                # Use execute_values for high-performance batch insert
                psycopg2.extras.execute_values(
                    cursor,
                    """
                    INSERT INTO decoded_data (timestamp, device_id, datapoint_id, value)
                    VALUES %s
                    ON CONFLICT (timestamp, device_id, datapoint_id) 
                    DO UPDATE SET value = EXCLUDED.value
                    """,
                    insert_data,
                    template=None,
                    page_size=1000  # Optimize page size for bulk inserts
                )
                
                # Commit the batch
                self.timescale_conn.commit()
                
                inserted_count = len(insert_data)
                self.messages_inserted += inserted_count
                self.batch_count += 1
                
                logger.debug(f"Batch inserted {inserted_count} records")
                return inserted_count
                
        except Exception as e:
            logger.error(f"Error during batch insert: {e}")
            self.failed_inserts += len(batch_data)
            if self.timescale_conn:
                self.timescale_conn.rollback()
            return 0
            
    def should_flush_batch(self) -> bool:
        """Check if batch should be flushed based on size or time."""
        current_time = time.time()
        
        # Flush if batch size reached or time interval exceeded
        return (len(self.batch_buffer) >= self.batch_size or 
                (current_time - self.last_flush_time) >= self.flush_interval)
                
    def flush_batch(self):
        """Flush current batch to TimescaleDB."""
        if not self.batch_buffer:
            return
            
        try:
            # Validate all data in batch
            validated_data = []
            for data in self.batch_buffer:
                validated = self.validate_and_transform_data(data)
                if validated:
                    validated_data.append(validated)
                    
            # Perform batch insert
            if validated_data:
                self.batch_insert_data(validated_data)
                
            # Clear batch buffer
            self.batch_buffer.clear()
            self.last_flush_time = time.time()
            
        except Exception as e:
            logger.error(f"Error flushing batch: {e}")
            self.batch_buffer.clear()  # Clear to prevent infinite retry
            
    def print_stats(self):
        """Print processing statistics."""
        current_time = time.time()
        elapsed = current_time - self.last_stats_time
        
        if elapsed >= 60:  # Print stats every minute
            rate = self.messages_consumed / elapsed if elapsed > 0 else 0
            insert_rate = self.messages_inserted / elapsed if elapsed > 0 else 0
            
            logger.info(f"Statistics - Consumed: {self.messages_consumed} ({rate:.1f}/sec), "
                       f"Inserted: {self.messages_inserted} ({insert_rate:.1f}/sec), "
                       f"Batches: {self.batch_count}, Failed: {self.failed_inserts}")
            
            # Reset counters
            self.messages_consumed = 0
            self.messages_inserted = 0
            self.batch_count = 0
            self.failed_inserts = 0
            self.last_stats_time = current_time
            
    def start(self):
        """Start the sink service."""
        logger.info("Starting Kafka-TimescaleDB Sink")
        
        try:
            # Setup connections
            self.setup_timescale_connection()
            self.setup_kafka_consumer()
            
            self.running = True
            logger.info("Kafka-TimescaleDB Sink started successfully")
            
            # Main processing loop
            while self.running:
                try:
                    # Poll for messages
                    message_batch = self.kafka_consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            try:
                                # Add to batch buffer
                                self.batch_buffer.append(message.value)
                                self.messages_consumed += 1
                                
                                # Check if batch should be flushed
                                if self.should_flush_batch():
                                    self.flush_batch()
                                    
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                                
                    # Flush batch if time interval exceeded
                    if self.should_flush_batch():
                        self.flush_batch()
                        
                    # Print stats periodically
                    self.print_stats()
                    
                except Exception as e:
                    logger.error(f"Error in main processing loop: {e}")
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Sink service error: {e}")
            raise
        finally:
            self.stop()
            
    def stop(self):
        """Stop the sink service."""
        logger.info("Stopping Kafka-TimescaleDB Sink")
        self.running = False
        
        # Flush any remaining data
        if self.batch_buffer:
            logger.info("Flushing remaining batch data...")
            self.flush_batch()
            
        if self.kafka_consumer:
            self.kafka_consumer.close()
            
        if self.timescale_conn:
            self.timescale_conn.close()
            
        logger.info("Kafka-TimescaleDB Sink stopped")
        
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start sink
    sink = KafkaTimescaleSink()
    sink.start()