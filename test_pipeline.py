#!/usr/bin/env python3
"""
End-to-End Pipeline Test Script

Tests the complete IoT data pipeline from MQTT to TimescaleDB.
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, Any

import paho.mqtt.client as mqtt
import psycopg2
from kafka import KafkaConsumer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mqtt_publish():
    """Test MQTT message publishing."""
    logger.info("Testing MQTT message publishing...")
    
    # Create MQTT client
    client = mqtt.Client()
    client.connect("localhost", 1883, 60)
    
    # Test message
    test_message = {
        "timestamp": datetime.now().isoformat(),
        "data": "01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"
    }
    
    # Publish test message
    topic = "stat/f2-aa:bb:cc:dd:ee:01/sensor-mode/1/sensor-1"
    client.publish(topic, json.dumps(test_message))
    
    logger.info(f"Published test message to {topic}")
    client.disconnect()

def test_kafka_consumption():
    """Test Kafka topic consumption."""
    logger.info("Testing Kafka topic consumption...")
    
    try:
        # Consumer for raw data
        consumer = KafkaConsumer(
            'raw-iot-data',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=5000
        )
        
        raw_messages = []
        for message in consumer:
            raw_messages.append(message.value)
            logger.info(f"Raw message: {message.value}")
            break
            
        consumer.close()
        
        # Consumer for processed data
        consumer = KafkaConsumer(
            'processed-iot-data',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=5000
        )
        
        processed_messages = []
        for message in consumer:
            processed_messages.append(message.value)
            logger.info(f"Processed message: {message.value}")
            break
            
        consumer.close()
        
        return len(raw_messages) > 0, len(processed_messages) > 0
        
    except Exception as e:
        logger.error(f"Error testing Kafka: {e}")
        return False, False

def test_timescale_data():
    """Test TimescaleDB data insertion."""
    logger.info("Testing TimescaleDB data...")
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5433,
            user="iot_user",
            password="iot_password",
            database="iot_timeseries"
        )
        
        with conn.cursor() as cursor:
            # Check if data exists
            cursor.execute("SELECT COUNT(*) FROM decoded_data")
            count = cursor.fetchone()[0]
            logger.info(f"TimescaleDB records count: {count}")
            
            # Check recent data
            cursor.execute("""
                SELECT timestamp, device_id, datapoint_id, value 
                FROM decoded_data 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent_data = cursor.fetchall()
            
            for row in recent_data:
                logger.info(f"Recent data: {row}")
                
        conn.close()
        return count > 0
        
    except Exception as e:
        logger.error(f"Error testing TimescaleDB: {e}")
        return False

def test_postgresql_metadata():
    """Test PostgreSQL metadata access."""
    logger.info("Testing PostgreSQL metadata...")
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="iot_user",
            password="iot_password",
            database="iot_metadata"
        )
        
        with conn.cursor() as cursor:
            # Check devices
            cursor.execute('SELECT "DeviceId", "MacAddress" FROM "Device" LIMIT 5')
            devices = cursor.fetchall()
            
            for device in devices:
                logger.info(f"Device: ID={device[0]}, MAC={device[1]}")
                
            # Check datapoints
            cursor.execute('SELECT "DataPointId", "Label" FROM "DataPoint" LIMIT 5')
            datapoints = cursor.fetchall()
            
            for datapoint in datapoints:
                logger.info(f"DataPoint: ID={datapoint[0]}, Label={datapoint[1]}")
                
        conn.close()
        return len(devices) > 0 and len(datapoints) > 0
        
    except Exception as e:
        logger.error(f"Error testing PostgreSQL: {e}")
        return False

def run_complete_test():
    """Run complete end-to-end test."""
    logger.info("Starting complete pipeline test...")
    
    results = {
        "mqtt_publish": False,
        "kafka_raw": False,
        "kafka_processed": False,
        "postgresql_metadata": False,
        "timescale_data": False
    }
    
    try:
        # Test PostgreSQL metadata first
        results["postgresql_metadata"] = test_postgresql_metadata()
        
        # Test MQTT publishing
        test_mqtt_publish()
        results["mqtt_publish"] = True
        
        # Wait for message processing
        time.sleep(10)
        
        # Test Kafka consumption
        results["kafka_raw"], results["kafka_processed"] = test_kafka_consumption()
        
        # Wait for data insertion
        time.sleep(5)
        
        # Test TimescaleDB data
        results["timescale_data"] = test_timescale_data()
        
    except Exception as e:
        logger.error(f"Error in complete test: {e}")
    
    # Print results
    logger.info("\n" + "="*50)
    logger.info("PIPELINE TEST RESULTS")
    logger.info("="*50)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
    
    # Overall result
    all_passed = all(results.values())
    overall_status = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    logger.info(f"\nOverall: {overall_status}")
    
    return all_passed

if __name__ == "__main__":
    success = run_complete_test()
    exit(0 if success else 1)