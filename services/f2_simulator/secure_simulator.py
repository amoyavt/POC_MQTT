#!/usr/bin/env python3
"""
Secure F2 Device Simulator with mTLS Support

This simulator uses the secure F2 client implementation with mTLS certificates
to connect to the MQTT broker on the secure port 8883.
"""

import json
import logging
import os
import random
import time
import sys
from datetime import datetime
from typing import Dict, List
import signal

# Add the mqtt-security scripts directory to the path
sys.path.append('/app/mqtt-security/scripts')

try:
    from secure_f2_client import SecureF2Client
except ImportError:
    # Fallback for development environment
    sys.path.append('../../mqtt-security/scripts')
    from secure_f2_client import SecureF2Client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SecureF2DeviceSimulator:
    def __init__(self):
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'mosquitto:8883')  # Use secure port
        self.publish_interval = int(os.getenv('PUBLISH_INTERVAL', '5'))
        self.device_count = int(os.getenv('DEVICE_COUNT', '2'))
        
        # Path to device certificates (mounted in Docker)
        self.certs_path = os.getenv('CERTS_PATH', '/app/mqtt-security/certs/devices')
        
        # Get list of registered devices
        self.registered_devices = self._load_registered_devices()
        
        # Initialize secure clients for each registered device
        self.clients = {}
        self._initialize_secure_clients()
        
        # Simulation data generators
        self.simulation_data = {
            'sensor-mode': self._generate_sensor_data,
            'access-control-mode': self._generate_access_control_data,
            'alarm-mode': self._generate_alarm_data
        }
        
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_registered_devices(self):
        """Load registered devices from device registry"""
        registry_path = os.path.join(self.certs_path, '..', 'device_registry.json')
        
        try:
            with open(registry_path, 'r') as f:
                registry = json.load(f)
                
            # Limit to configured device count
            devices = list(registry.items())[:self.device_count]
            logger.info(f"Loaded {len(devices)} registered devices from registry")
            return dict(devices)
            
        except FileNotFoundError:
            logger.error(f"Device registry not found at {registry_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in device registry: {e}")
            return {}
    
    def _initialize_secure_clients(self):
        """Initialize secure MQTT clients for each registered device"""
        if not self.registered_devices:
            logger.error("No registered devices found. Please register devices first using register_f2_controller.py")
            return
        
        for mac_address, device_info in self.registered_devices.items():
            try:
                # Create secure client for this device
                client = SecureF2Client(
                    device_mac=mac_address,
                    certs_base_path=self.certs_path,
                    broker_host=self.mqtt_broker.split(':')[0],
                    broker_port=int(self.mqtt_broker.split(':')[1]) if ':' in self.mqtt_broker else 8883
                )
                
                # Connect the client
                if client.connect():
                    self.clients[mac_address] = {
                        'client': client,
                        'info': device_info,
                        'mode': random.choice(['sensor-mode', 'access-control-mode', 'alarm-mode']),
                        'connector': random.randint(1, 3),
                        'components': self._get_random_components()
                    }
                    logger.info(f"✅ Secure client initialized for device {mac_address}")
                else:
                    logger.error(f"❌ Failed to connect secure client for device {mac_address}")
                    
            except Exception as e:
                logger.error(f"Failed to initialize secure client for {mac_address}: {e}")
    
    def _get_random_components(self):
        """Get random components for simulation"""
        components = ['sensor', 'strike', 'door-sensors', 'reader', 'motion-sensor', 'siren']
        return random.sample(components, random.randint(1, 3))
    
    def _generate_sensor_data(self, device_mac: str, connector: int, component: str) -> Dict:
        """Generate sensor-mode data"""
        if component == 'sensor':
            return {
                'temperature': round(random.uniform(18.0, 28.0), 1),
                'humidity': random.randint(30, 80),
                'timestamp': datetime.now().isoformat()
            }
        elif component == 'motion-sensor':
            return {
                'motion_detected': random.choice([True, False]),
                'confidence': random.randint(70, 95),
                'timestamp': datetime.now().isoformat()
            }
        return {'value': random.randint(0, 100), 'timestamp': datetime.now().isoformat()}
    
    def _generate_access_control_data(self, device_mac: str, connector: int, component: str) -> Dict:
        """Generate access-control-mode data"""
        if component == 'door-sensors':
            return {
                'door_open': random.choice([True, False]),
                'tamper_detected': False,
                'timestamp': datetime.now().isoformat()
            }
        elif component == 'strike':
            return {
                'state': random.choice(['locked', 'unlocked']),
                'power_status': 'normal',
                'timestamp': datetime.now().isoformat()
            }
        elif component == 'reader':
            return {
                'card_id': f"CARD_{random.randint(1000, 9999)}",
                'access_granted': random.choice([True, False]),
                'timestamp': datetime.now().isoformat()
            }
        return {'status': 'active', 'timestamp': datetime.now().isoformat()}
    
    def _generate_alarm_data(self, device_mac: str, connector: int, component: str) -> Dict:
        """Generate alarm-mode data"""
        if component == 'motion-sensor':
            return {
                'alarm_triggered': random.choice([True, False]),
                'sensitivity': random.randint(1, 10),
                'timestamp': datetime.now().isoformat()
            }
        elif component == 'siren':
            return {
                'active': random.choice([True, False]),
                'volume': random.randint(1, 10),
                'timestamp': datetime.now().isoformat()
            }
        return {'alarm_status': 'normal', 'timestamp': datetime.now().isoformat()}
    
    def _publish_device_data(self, mac_address: str, device_config: Dict):
        """Publish data for a specific device"""
        client_info = device_config['client']
        mode = device_config['mode']
        connector = device_config['connector']
        components = device_config['components']
        
        for component in components:
            # Generate appropriate data based on mode
            data_generator = self.simulation_data.get(mode, self._generate_sensor_data)
            data = data_generator(mac_address, connector, component)
            
            # Construct topic based on F2 protocol
            topic = f"cmnd/f2-{mac_address}/{mode}/{connector}/{component}-1"
            
            # Publish data using secure client
            try:
                if client_info.publish(topic, json.dumps(data)):
                    logger.info(f"📤 [{mac_address}] Published to {topic}: {json.dumps(data, indent=2)}")
                else:
                    logger.warning(f"⚠️  [{mac_address}] Failed to publish to {topic}")
            except Exception as e:
                logger.error(f"❌ [{mac_address}] Error publishing to {topic}: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def run(self):
        """Main simulation loop"""
        if not self.clients:
            logger.error("No secure clients available. Exiting.")
            return
        
        logger.info(f"🚀 Starting secure F2 device simulator with {len(self.clients)} devices")
        logger.info(f"📊 Publishing every {self.publish_interval} seconds")
        logger.info(f"🔐 Using mTLS on {self.mqtt_broker}")
        
        try:
            while self.running:
                # Publish data for each connected device
                for mac_address, device_config in self.clients.items():
                    self._publish_device_data(mac_address, device_config)
                
                # Wait for next cycle
                time.sleep(self.publish_interval)
                
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        except Exception as e:
            logger.error(f"Simulation error: {e}")
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up secure clients...")
        for mac_address, device_config in self.clients.items():
            try:
                device_config['client'].disconnect()
                logger.info(f"✅ Disconnected secure client for {mac_address}")
            except Exception as e:
                logger.error(f"❌ Error disconnecting {mac_address}: {e}")

def main():
    """Main entry point"""
    logger.info("🔐 Secure F2 Device Simulator with mTLS")
    logger.info("====================================")
    
    simulator = SecureF2DeviceSimulator()
    simulator.run()

if __name__ == "__main__":
    main()