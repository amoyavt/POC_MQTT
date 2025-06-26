import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List
import paho.mqtt.client as mqtt
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class F2DeviceSimulator:
    def __init__(self):
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'mosquitto:1883')
        self.publish_interval = int(os.getenv('PUBLISH_INTERVAL', '5'))
        
        # Simulated F2 devices with connectors and pins, based on docs/actual_structures.md
        self.devices = [
            {
                'mac': 'e4fd45f654be',
                'mode': 'sensor-mode',
                'connectors': [
                    {
                        'number': 1,
                        'pins': [1] # Living Room Env Sensor
                    }
                ]
            },
            {
                'mac': 'abc123def456', 
                'mode': 'sensor-mode',
                'connectors': [
                    {
                        'number': 2,
                        'pins': [2] # Kitchen Power Monitor
                    }
                ]
            },
            {
                'mac': '123456abcdef',
                'mode': 'sensor-mode',
                'connectors': [
                    {
                        'number': 4,
                        'pins': [3] # Bedroom Env Sensor
                    }
                ]
            }
        ]
        
        self.mqtt_client = None
        self.running = True
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, _frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _get_current_timestamp(self) -> str:
        # The timestamp format in the example is "2023-05-25 15:13:10.543400"
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

    def _generate_sensor_hex_data(self) -> str:
        """
        Generates a random hex string similar to the example in the documentation.
        Example: "01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"
        This generates a string of 16 random hex bytes separated by spaces.
        """
        num_bytes = 16
        hex_bytes = [f"{random.randint(0, 255):02x}" for _ in range(num_bytes)]
        return " ".join(hex_bytes)

    def _on_mqtt_connect(self, _client, _userdata, _flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _setup_mqtt_client(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        
        broker_parts = self.mqtt_broker.split(':')
        host = broker_parts[0]
        port = int(broker_parts[1]) if len(broker_parts) > 1 else 1883
        
        logger.info(f"Connecting to MQTT broker at {host}:{port}")
        self.mqtt_client.connect(host, port, 60)
        self.mqtt_client.loop_start()

    def _publish_device_data(self):
        """
        Publish sensor data for all simulated devices, connectors, and pins.
        """
        for device in self.devices:
            mac = device['mac']
            mode = device['mode']
            
            for connector in device['connectors']:
                connector_number = connector['number']
                
                for pin in connector['pins']:
                    # Topic format: cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/sensor-<N>
                    topic = f"cmnd/f2-{mac}/{mode}/{connector_number}/sensor-{pin}"
                    
                    hex_data = self._generate_sensor_hex_data()
                    payload_dict = {
                        "timestamp": self._get_current_timestamp(),
                        "data": hex_data
                    }
                    payload_json = json.dumps(payload_dict)
                    
                    try:
                        self.mqtt_client.publish(topic, payload_json)
                        logger.info(f"Published to {topic}")
                    except Exception as e:
                        logger.error(f"Error publishing to {topic}: {e}")

    def run(self):
        logger.info("Starting F2 Device Simulator")
        
        # Wait for MQTT broker to be ready
        time.sleep(5)
        
        try:
            self._setup_mqtt_client()
            
            logger.info(f"Simulator started, publishing every {self.publish_interval} seconds")
            
            while self.running:
                self._publish_device_data()
                time.sleep(self.publish_interval)
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        logger.info("Cleaning up connections...")
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

if __name__ == "__main__":
    simulator = F2DeviceSimulator()
    simulator.run()