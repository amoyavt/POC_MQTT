import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class F2DeviceSimulator:
    def __init__(self):
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'mosquitto:1883')
        self.publish_interval = int(os.getenv('PUBLISH_INTERVAL', '5'))
        
        # MQTT authentication
        self.mqtt_username = self._load_secret_from_docker_file(
            os.getenv('MQTT_USERNAME_FILE'), 
            os.getenv('MQTT_USERNAME', 'iot_user'),
            "MQTT username"
        )
        self.mqtt_password = self._load_secret_from_docker_file(
            os.getenv('MQTT_PASSWORD_FILE'),
            os.getenv('MQTT_PASSWORD', 'iot_password'),
            "MQTT password"
        )
        
        # Simulated F2 devices with multiple modes and components
        self.devices = [
            # Sensor mode devices
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
            },
            # Access control mode devices
            {
                'mac': 'ac1234567890',
                'mode': 'access-control-mode',
                'connectors': [
                    {
                        'number': 1,
                        'strikes': [1, 2],  # Electric strikes
                        'door_sensors': True,
                        'readers': [1],     # QR/NFC readers
                        'exit_buttons': True
                    },
                    {
                        'number': 2,
                        'strikes': [1],
                        'door_sensors': True,
                        'readers': [1, 2],
                        'exit_buttons': True
                    }
                ]
            },
            {
                'mac': 'ac9876543210',
                'mode': 'access-control-mode',
                'connectors': [
                    {
                        'number': 1,
                        'strikes': [1],
                        'door_sensors': True,
                        'readers': [1],
                        'exit_buttons': True
                    }
                ]
            },
            # Alarm mode devices
            {
                'mac': 'al1111222233',
                'mode': 'alarm-mode',
                'connectors': [
                    {
                        'number': 1,
                        'motion_sensors': [1, 2],
                        'sirens': [1]
                    },
                    {
                        'number': 2,
                        'motion_sensors': [1],
                        'sirens': [1, 2]
                    }
                ]
            },
            {
                'mac': 'al4444555566',
                'mode': 'alarm-mode',
                'connectors': [
                    {
                        'number': 1,
                        'motion_sensors': [1],
                        'sirens': [1]
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

    def _generate_strike_data(self) -> Dict:
        """Generate electric strike status data"""
        return {
            "timestamp": self._get_current_timestamp(),
            "state": random.choice(["locked", "unlocked"]),
            "voltage": round(random.uniform(11.5, 12.5), 1),
            "current": round(random.uniform(0.1, 2.0), 2)
        }

    def _generate_door_sensor_data(self) -> Dict:
        """Generate door sensor status data"""
        return {
            "timestamp": self._get_current_timestamp(),
            "door_1": random.choice(["open", "closed"]),
            "door_2": random.choice(["open", "closed"]),
            "tamper": random.choice([True, False])
        }

    def _generate_reader_data(self) -> Dict:
        """Generate QR/NFC reader data"""
        card_ids = ["A1B2C3D4", "E5F6G7H8", "I9J0K1L2", "M3N4O5P6"]
        return {
            "timestamp": self._get_current_timestamp(),
            "card_id": random.choice(card_ids),
            "read_type": random.choice(["qr", "nfc"]),
            "signal_strength": random.randint(50, 100)
        }

    def _generate_exit_button_data(self) -> Dict:
        """Generate exit button status data"""
        return {
            "timestamp": self._get_current_timestamp(),
            "button_pressed": random.choice([True, False]),
            "button_id": random.randint(1, 4)
        }

    def _generate_motion_sensor_data(self) -> Dict:
        """Generate motion sensor data"""
        return {
            "timestamp": self._get_current_timestamp(),
            "motion_detected": random.choice([True, False]),
            "sensitivity": random.randint(1, 10),
            "zone": random.choice(["zone_1", "zone_2", "zone_3"])
        }

    def _generate_siren_data(self) -> Dict:
        """Generate siren status data"""
        return {
            "timestamp": self._get_current_timestamp(),
            "state": random.choice(["active", "inactive"]),
            "volume": random.randint(70, 120),
            "pattern": random.choice(["steady", "pulsing", "warble"])
        }

    def _on_mqtt_connect(self, _client, _userdata, _flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def _load_secret_from_docker_file(self, secret_file_path: Optional[str], 
                                     fallback_value: str, 
                                     secret_name: str = "credential") -> str:
        """
        Load sensitive data from Docker secrets file or fallback to environment variable.
        
        This method implements the Docker secrets security pattern, where sensitive data
        is mounted as read-only files in containers instead of being exposed through
        environment variables.
        
        Args:
            secret_file_path: Path to Docker secret file (e.g., /run/secrets/mqtt_username)
            fallback_value: Fallback value from environment variable
            secret_name: Name of secret for logging purposes
            
        Returns:
            Secret value from file or fallback
        """
        if secret_file_path and os.path.exists(secret_file_path):
            try:
                with open(secret_file_path, 'r') as f:
                    logger.info(f"Successfully loaded {secret_name} from Docker secret file")
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"Failed to read {secret_name} from {secret_file_path}: {e}")
        
        logger.info(f"Using {secret_name} from environment variable fallback")
        return fallback_value
    
    def _setup_mqtt_client(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        
        # Set authentication credentials
        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            logger.info(f"MQTT authentication configured for user: {self.mqtt_username}")
        
        broker_parts = self.mqtt_broker.split(':')
        host = broker_parts[0]
        port = int(broker_parts[1]) if len(broker_parts) > 1 else 1883
        
        logger.info(f"Connecting to MQTT broker at {host}:{port} with authentication")
        self.mqtt_client.connect(host, port, 60)
        self.mqtt_client.loop_start()

    def _publish_device_data(self):
        """
        Publish data for all simulated devices, connectors, and components.
        """
        for device in self.devices:
            mac = device['mac']
            mode = device['mode']
            
            for connector in device['connectors']:
                connector_number = connector['number']
                
                if mode == 'sensor-mode':
                    self._publish_sensor_data(mac, mode, connector_number, connector)
                elif mode == 'access-control-mode':
                    self._publish_access_control_data(mac, mode, connector_number, connector)
                elif mode == 'alarm-mode':
                    self._publish_alarm_data(mac, mode, connector_number, connector)

    def _publish_sensor_data(self, mac: str, mode: str, connector_number: int, connector: Dict):
        """Publish RS-485 sensor data"""
        if 'pins' in connector:
            for pin in connector['pins']:
                topic = f"cmnd/f2-{mac}/{mode}/{connector_number}/sensor-{pin}"
                hex_data = self._generate_sensor_hex_data()
                payload_dict = {
                    "timestamp": self._get_current_timestamp(),
                    "data": hex_data
                }
                self._publish_to_topic(topic, payload_dict)

    def _publish_access_control_data(self, mac: str, mode: str, connector_number: int, connector: Dict):
        """Publish access control component data"""
        
        # Electric strikes
        if 'strikes' in connector:
            for strike_id in connector['strikes']:
                # Command topic for strike control
                cmd_topic = f"cmnd/f2-{mac}/{mode}/{connector_number}/strike-{strike_id}"
                # Status topic for strike status
                stat_topic = f"stat/f2-{mac}/{mode}/{connector_number}/strike-{strike_id}"
                
                strike_data = self._generate_strike_data()
                self._publish_to_topic(stat_topic, strike_data)
        
        # Door sensors
        if connector.get('door_sensors'):
            topic = f"stat/f2-{mac}/{mode}/{connector_number}/door-sensors"
            door_data = self._generate_door_sensor_data()
            self._publish_to_topic(topic, door_data)
        
        # QR/NFC readers
        if 'readers' in connector:
            for reader_id in connector['readers']:
                # Command topic for reader success
                cmd_topic = f"cmnd/f2-{mac}/{mode}/{connector_number}/reader-{reader_id}/success"
                # Telemetry topic for reader data
                tele_topic = f"tele/f2-{mac}/{mode}/{connector_number}/reader-{reader_id}"
                
                reader_data = self._generate_reader_data()
                self._publish_to_topic(tele_topic, reader_data)
        
        # Exit buttons
        if connector.get('exit_buttons'):
            topic = f"stat/f2-{mac}/{mode}/{connector_number}/exit-buttons"
            button_data = self._generate_exit_button_data()
            self._publish_to_topic(topic, button_data)

    def _publish_alarm_data(self, mac: str, mode: str, connector_number: int, connector: Dict):
        """Publish alarm system component data"""
        
        # Motion sensors
        if 'motion_sensors' in connector:
            for sensor_id in connector['motion_sensors']:
                topic = f"stat/f2-{mac}/{mode}/{connector_number}/motion-sensor-{sensor_id}"
                motion_data = self._generate_motion_sensor_data()
                self._publish_to_topic(topic, motion_data)
        
        # Sirens
        if 'sirens' in connector:
            for siren_id in connector['sirens']:
                # Command topic for siren control
                cmd_topic = f"cmnd/f2-{mac}/{mode}/{connector_number}/siren-{siren_id}"
                # Status topic for siren status
                stat_topic = f"stat/f2-{mac}/{mode}/{connector_number}/siren-{siren_id}"
                
                siren_data = self._generate_siren_data()
                self._publish_to_topic(stat_topic, siren_data)

    def _publish_to_topic(self, topic: str, payload_dict: Dict):
        """Helper method to publish JSON payload to MQTT topic"""
        try:
            payload_json = json.dumps(payload_dict)
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