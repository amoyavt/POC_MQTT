#!/usr/bin/env python3
"""
Secure F2 Controller MQTT Client

This demonstrates how a registered F2 controller connects to the MQTT broker
using mTLS authentication with its device certificate.
"""

import ssl
import json
import time
import random
import argparse
import paho.mqtt.client as mqtt
from pathlib import Path

class SecureF2Client:
    def __init__(self, mac_address, certs_dir="./certs/devices"):
        self.mac_address = mac_address.replace(":", "-")
        self.client_id = f"f2-{self.mac_address}"
        self.certs_dir = Path(certs_dir)
        self.device_dir = self.certs_dir / self.mac_address
        
        # MQTT client setup
        self.client = mqtt.Client(self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        
        # Load certificates
        self._setup_tls()
        
        # Topic templates
        self.base_topic = f"f2-{self.mac_address}"
        
    def _setup_tls(self):
        """Configure TLS/SSL for mTLS authentication"""
        ca_cert = self.certs_dir.parent / "ca.crt"
        client_cert = self.device_dir / "device.crt"
        client_key = self.device_dir / "device.key"
        
        # Verify certificate files exist
        for cert_file in [ca_cert, client_cert, client_key]:
            if not cert_file.exists():
                raise FileNotFoundError(f"Certificate file not found: {cert_file}")
        
        print(f"🔐 Setting up mTLS with certificates:")
        print(f"   CA: {ca_cert}")
        print(f"   Client Cert: {client_cert}")
        print(f"   Client Key: {client_key}")
        
        # Configure TLS
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False  # Disable hostname checking for local development
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(str(ca_cert))
        context.load_cert_chain(str(client_cert), str(client_key))
        
        self.client.tls_set_context(context)
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to broker"""
        if rc == 0:
            print(f"✅ Connected to MQTT broker as {self.client_id}")
            self._subscribe_to_commands()
        else:
            print(f"❌ Failed to connect to MQTT broker: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects"""
        print(f"🔌 Disconnected from MQTT broker: {rc}")
        
    def _on_message(self, client, userdata, msg):
        """Callback for when message is received"""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        print(f"📨 Received command: {topic} -> {payload}")
        
        # Process commands and send responses
        self._process_command(topic, payload)
        
    def _on_publish(self, client, userdata, mid):
        """Callback for when message is published"""
        print(f"📤 Message published: {mid}")
        
    def _subscribe_to_commands(self):
        """Subscribe to command topics for this device"""
        command_topics = [
            f"cmnd/{self.base_topic}/+/+/strike-+",
            f"cmnd/{self.base_topic}/+/+/siren-+", 
            f"cmnd/{self.base_topic}/+/+/reader-+/success",
            "general",
            "system/status"
        ]
        
        for topic in command_topics:
            self.client.subscribe(topic)
            print(f"🔔 Subscribed to: {topic}")
            
    def _process_command(self, topic, payload):
        """Process received commands and send appropriate responses"""
        if "strike" in topic:
            self._handle_strike_command(topic, payload)
        elif "siren" in topic:
            self._handle_siren_command(topic, payload)
        elif "reader" in topic and "success" in topic:
            self._handle_reader_success(topic, payload)
        elif topic == "general":
            print(f"📢 General message: {payload}")
        elif topic == "system/status":
            self._send_status_response()
            
    def _handle_strike_command(self, topic, payload):
        """Handle electric strike commands"""
        # Extract component ID from topic
        parts = topic.split("/")
        component = parts[-1] if parts else "strike-1"
        
        # Send status response
        status_topic = topic.replace("cmnd/", "stat/")
        status = "open" if payload.lower() in ["1", "true", "on", "open"] else "closed"
        
        self.client.publish(status_topic, status)
        print(f"🚪 Strike {component}: {status}")
        
    def _handle_siren_command(self, topic, payload):
        """Handle siren commands"""
        parts = topic.split("/")
        component = parts[-1] if parts else "siren-1"
        
        status_topic = topic.replace("cmnd/", "stat/")
        status = "on" if payload.lower() in ["1", "true", "on"] else "off"
        
        self.client.publish(status_topic, status)
        print(f"🚨 Siren {component}: {status}")
        
    def _handle_reader_success(self, topic, payload):
        """Handle successful card/QR reads"""
        parts = topic.split("/")
        component = parts[-2] if len(parts) > 1 else "reader-1"
        
        # Send telemetry response
        tele_topic = f"tele/{self.base_topic}/{parts[2]}/{parts[3]}/{component}"
        response = {
            "timestamp": int(time.time()),
            "reader_id": component,
            "access_granted": True,
            "credential": payload
        }
        
        self.client.publish(tele_topic, json.dumps(response))
        print(f"💳 Reader {component} access granted: {payload}")
        
    def _send_status_response(self):
        """Send device status"""
        status = {
            "device_id": self.client_id,
            "mac_address": self.mac_address,
            "timestamp": int(time.time()),
            "uptime": int(time.time() % 86400),  # Fake uptime
            "connection": "secure_mqtt",
            "firmware_version": "1.2.3"
        }
        
        self.client.publish("system/status", json.dumps(status))
        print(f"📊 Status sent: {status}")
        
    def start_sensor_simulation(self):
        """Start publishing sensor data"""
        print(f"🔄 Starting sensor simulation for {self.client_id}")
        
        while True:
            try:
                # Door sensors
                door_status = {
                    "timestamp": int(time.time()),
                    "door_1": random.choice(["open", "closed"]),
                    "door_2": random.choice(["open", "closed"])
                }
                self.client.publish(f"stat/{self.base_topic}/access-control/conn1/door-sensors", 
                                  json.dumps(door_status))
                
                # Motion sensors
                motion_data = {
                    "timestamp": int(time.time()),
                    "motion_detected": random.choice([True, False]),
                    "sensor_id": "motion-sensor-1"
                }
                self.client.publish(f"stat/{self.base_topic}/alarm/conn1/motion-sensor-1", 
                                  json.dumps(motion_data))
                
                # Temperature sensor (RS-485)
                temp_data = {
                    "timestamp": int(time.time()),
                    "temperature": round(random.uniform(18.0, 25.0), 1),
                    "humidity": round(random.uniform(40.0, 60.0), 1),
                    "sensor_id": "sensor-3"
                }
                self.client.publish(f"tele/{self.base_topic}/sensor/conn1/sensor-3", 
                                  json.dumps(temp_data))
                
                print(f"📡 Sensor data published")
                time.sleep(30)  # Publish every 30 seconds
                
            except KeyboardInterrupt:
                print(f"\n🛑 Stopping sensor simulation")
                break
            except Exception as e:
                print(f"❌ Error in sensor simulation: {e}")
                time.sleep(5)
                
    def connect(self, host="localhost", port=8883):
        """Connect to MQTT broker"""
        try:
            print(f"🔌 Connecting to {host}:{port} as {self.client_id}")
            self.client.connect(host, port, 60)
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
            
    def publish(self, topic, payload, qos=0, retain=False):
        """Publish a message to the broker"""
        try:
            result = self.client.publish(topic, payload, qos, retain)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"❌ Publish failed: {e}")
            return False
        
    def disconnect(self):
        """Disconnect from broker"""
        self.client.disconnect()
        
    def loop_forever(self):
        """Start the MQTT loop"""
        self.client.loop_forever()

def main():
    parser = argparse.ArgumentParser(description="Secure F2 Controller MQTT Client")
    parser.add_argument("mac_address", help="MAC address of the F2 controller")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=8883, help="MQTT broker port")
    parser.add_argument("--simulate", action="store_true", help="Start sensor simulation")
    
    args = parser.parse_args()
    
    try:
        # Create secure client
        client = SecureF2Client(args.mac_address)
        
        # Connect to broker
        if not client.connect(args.host, args.port):
            return 1
            
        # Start appropriate mode
        if args.simulate:
            client.start_sensor_simulation()
        else:
            print("📱 Client ready, waiting for commands...")
            client.loop_forever()
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down client")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        if 'client' in locals():
            client.disconnect()
            
    return 0

if __name__ == "__main__":
    exit(main())