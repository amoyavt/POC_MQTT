import os
import sys
import json
import time
import random
import logging
import ssl
from datetime import datetime
from typing import Dict, List
import requests
import paho.mqtt.client as mqtt

# Add shared models to path
sys.path.append('/app')
from shared.models import CertificateRequest, CertificateResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class F2Controller:
    def __init__(self, mac: str, mode: str = "sensor-mode"):
        self.mac = mac
        self.mode = mode
        self.client = None
        self.cert_files = {
            'client_cert': f'/app/certs/{mac.replace(":", "")}.crt',
            'private_key': f'/app/certs/{mac.replace(":", "")}.key',
            'ca_cert': f'/app/certs/ca.crt'
        }
        self.connectors = [1, 2, 3, 4]  # 4 connectors per device
        
    def provision_certificates(self):
        # Check if certificates exist
        if all(os.path.exists(f) for f in self.cert_files.values()):
            logger.info(f"Certificates already exist for {self.mac}")
            return True
            
        # Request certificates from certgen-api
        try:
            logger.info(f"Requesting certificates for {self.mac}")
            certgen_host = os.getenv('CERTGEN_API_HOST', 'certgen-api')
            response = requests.post(
                f'http://{certgen_host}:8080/issue',
                json={'mac': self.mac},
                timeout=30
            )
            response.raise_for_status()
            cert_data = response.json()
            
            # Ensure certs directory exists
            os.makedirs('/app/certs', exist_ok=True)
            
            # Save certificates
            with open(self.cert_files['client_cert'], 'w') as f:
                f.write(cert_data['client_cert'])
            with open(self.cert_files['private_key'], 'w') as f:
                f.write(cert_data['private_key'])
            with open(self.cert_files['ca_cert'], 'w') as f:
                f.write(cert_data['ca_cert'])
                
            logger.info(f"Certificates provisioned for {self.mac}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to provision certificates for {self.mac}: {e}")
            return False
    
    def setup_mqtt_client(self):
        try:
            # Create MQTT client
            client = mqtt.Client(client_id=f"f2-{self.mac}")
            
            # Configure TLS/SSL
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.load_verify_locations(self.cert_files['ca_cert'])
            context.load_cert_chain(self.cert_files['client_cert'], self.cert_files['private_key'])
            
            client.tls_set_context(context)
            client.on_connect = self.on_connect
            client.on_message = self.on_message
            client.on_disconnect = self.on_disconnect
            
            self.client = client
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup MQTT client for {self.mac}: {e}")
            return False
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"F2 Controller {self.mac} connected successfully")
            
            # Subscribe to command topics (matching ACL pattern)
            command_topic = f"cmnd/f2-{self.mac}/+/+/+"
            client.subscribe(command_topic)
            logger.info(f"Subscribed to: {command_topic}")
        else:
            logger.error(f"F2 Controller {self.mac} connection failed with code {rc}")
        
    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"F2 Controller {self.mac} disconnected with code {rc}")
        
    def on_message(self, client, userdata, msg):
        logger.info(f"F2 Controller {self.mac} received command: {msg.topic} - {msg.payload.decode()}")
        
    def publish_sensor_data(self):
        if not self.client or not self.client.is_connected():
            logger.warning(f"F2 Controller {self.mac} not connected, skipping sensor data publish")
            return
            
        # Publish sensor data for each connector
        for connector in self.connectors:
            for sensor_num in [1, 2]:  # 2 sensors per connector
                topic = f"stat/f2-{self.mac}/{self.mode}/{connector}/sensor-{sensor_num}"
                
                # Generate realistic RS-485 hex data
                hex_data = self.generate_hex_data()
                
                payload = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "data": hex_data
                }
                
                try:
                    self.client.publish(topic, json.dumps(payload))
                    logger.debug(f"Published sensor data: {topic}")
                except Exception as e:
                    logger.error(f"Failed to publish sensor data for {self.mac}: {e}")
        
    def generate_hex_data(self):
        # Generate realistic RS-485 hex data similar to the example
        # Example: "01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"
        hex_values = [
            "01", "03", "0C",  # Fixed header
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}",
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}",
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}",
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}",
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}",
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}",
            f"{random.randint(16, 99):02X}", f"{random.randint(16, 99):02X}"
        ]
        return " ".join(hex_values)
        
    def start(self):
        logger.info(f"Starting F2 Controller {self.mac}")
        
        if not self.provision_certificates():
            return False
            
        if not self.setup_mqtt_client():
            return False
            
        # Connect to MQTT broker
        try:
            broker_host = os.getenv('MQTT_BROKER_HOST', 'mqtt-broker')
            logger.info(f"Connecting to MQTT broker at {broker_host}:8883")
            self.client.connect(broker_host, 8883, 60)
            self.client.loop_start()
            
            # Wait for connection
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect F2 Controller {self.mac} to MQTT broker: {e}")
            return False

def main():
    logger.info("Starting FACES2 Controllers Simulator")
    
    # Define 4 F2 controllers with different MAC addresses
    controllers = [
        F2Controller("aa:bb:cc:dd:ee:01"),
        F2Controller("aa:bb:cc:dd:ee:02"),
        F2Controller("aa:bb:cc:dd:ee:03"),
        F2Controller("aa:bb:cc:dd:ee:04")
    ]
    
    # Start all controllers
    active_controllers = []
    for controller in controllers:
        if controller.start():
            logger.info(f"Started F2 Controller {controller.mac}")
            active_controllers.append(controller)
        else:
            logger.error(f"Failed to start F2 Controller {controller.mac}")
    
    if not active_controllers:
        logger.error("No controllers started successfully")
        return
    
    # Main loop - publish sensor data periodically
    try:
        publish_interval = int(os.getenv('PUBLISH_INTERVAL', '30'))
        logger.info(f"Starting sensor data publishing loop (interval: {publish_interval}s)")
        while True:
            time.sleep(publish_interval)
            
            for controller in active_controllers:
                controller.publish_sensor_data()
                    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for controller in active_controllers:
            if controller.client:
                controller.client.loop_stop()
                controller.client.disconnect()

if __name__ == "__main__":
    main()