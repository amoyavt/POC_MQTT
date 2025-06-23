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
        
        # Simulated F2 devices
        self.devices = [
            {
                'mac': 'e4fd45f654be',
                'modes': ['access-control-mode', 'alarm-mode', 'sensor-mode']
            },
            {
                'mac': 'abc123def456', 
                'modes': ['sensor-mode', 'access-control-mode']
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
        return datetime.now().isoformat()

    def _generate_door_sensor_data(self) -> Dict:
        """Generate door sensor status data."""
        return {
            "timestamp": self._get_current_timestamp(),
            "door-sensor-1": random.choice([True, False]),
            "door-sensor-2": random.choice([True, False])
        }

    def _generate_strike_data(self) -> Dict:
        """Generate electric strike status data."""
        return {
            "timestamp": self._get_current_timestamp(),
            "status": random.choice([True, False])
        }

    def _generate_exit_buttons_data(self) -> Dict:
        """Generate exit buttons status data."""
        return {
            "timestamp": self._get_current_timestamp(),
            "exit-button-1": random.choice([True, False]),
            "exit-button-2": random.choice([True, False])
        }

    def _generate_motion_sensor_data(self) -> Dict:
        """Generate motion sensor data."""
        return {
            "timestamp": self._get_current_timestamp(),
            "status": random.choice([True, False])
        }

    def _generate_siren_data(self) -> Dict:
        """Generate siren status data."""
        return {
            "timestamp": self._get_current_timestamp(),
            "status": random.choice([True, False])
        }

    def _generate_reader_data(self) -> Dict:
        """Generate QR/NFC reader data."""
        sample_data = [
            "b'\"Hello World\"'",
            "b'\"USER12345\"'",
            "b'\"ACCESS_CARD_789\"'",
            "b'\"QR_CODE_ABC123\"'"
        ]
        return {
            "timestamp": self._get_current_timestamp(),
            "data": random.choice(sample_data)
        }

    def _generate_rs485_sensor_data(self) -> Dict:
        """Generate RS-485 sensor data (temperature, humidity, pressure)."""
        # Generate random hex values for different sensor types
        if random.choice([True, False]):
            # Temperature sensor (celsius * 10)
            temp_celsius = random.uniform(15.0, 35.0)
            hex_value = hex(int(temp_celsius * 10))
        else:
            # Humidity sensor (percentage * 100) or pressure (hPa * 10)
            value = random.uniform(300, 1200)
            hex_value = hex(int(value))
        
        return {
            "timestamp": self._get_current_timestamp(),
            "data": hex_value
        }

    def _get_message_generators(self) -> Dict:
        """Return mapping of component types to their data generators."""
        return {
            'door-sensors': self._generate_door_sensor_data,
            'strike': self._generate_strike_data,
            'exit-buttons': self._generate_exit_buttons_data,
            'motion-sensor': self._generate_motion_sensor_data,
            'siren': self._generate_siren_data,
            'reader': self._generate_reader_data,
            'sensor': self._generate_rs485_sensor_data
        }

    def _get_topics_for_mode(self, device_mac: str, mode: str) -> List[str]:
        """Get list of topics for a given device and mode."""
        base = f"cmnd/f2-{device_mac}/{mode}/J1"
        
        if mode == 'access-control-mode':
            return [
                f"{base}/door-sensors",
                f"{base}/strike-1",
                f"{base}/exit-buttons",
                f"{base}/reader-1"
            ]
        elif mode == 'alarm-mode':
            return [
                f"{base}/motion-sensor-1",
                f"{base}/siren-1"
            ]
        elif mode == 'sensor-mode':
            return [
                f"{base}/sensor-1",
                f"{base}/sensor-2",
                f"{base}/sensor-3"
            ]
        else:
            return []

    def _extract_component_info(self, topic: str) -> tuple:
        """Extract component type and ID from topic."""
        parts = topic.split('/')
        if len(parts) >= 5:
            component_part = parts[-1]
            if '-' in component_part:
                component_type, component_id = component_part.rsplit('-', 1)
                return component_type, component_id
            else:
                return component_part, None
        return 'unknown', None

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
        """Publish data for all simulated devices."""
        generators = self._get_message_generators()
        
        for device in self.devices:
            mac = device['mac']
            modes = device['modes']
            
            # Randomly select a mode for this iteration
            mode = random.choice(modes)
            topics = self._get_topics_for_mode(mac, mode)
            
            # Publish to a random subset of topics for this device
            num_topics = random.randint(1, min(3, len(topics)))
            selected_topics = random.sample(topics, num_topics)
            
            for topic in selected_topics:
                component_type, _component_id = self._extract_component_info(topic)
                
                if component_type in generators:
                    data = generators[component_type]()
                    payload = json.dumps(data)
                    
                    try:
                        self.mqtt_client.publish(topic, payload)
                        logger.info(f"Published to {topic}: {component_type}")
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