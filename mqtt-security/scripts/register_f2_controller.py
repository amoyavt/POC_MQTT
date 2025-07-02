#!/usr/bin/env python3
"""
F2 Controller Registration and Certificate Provisioning

This script simulates the real-world process of registering an F2 Smart Controller
when it's sold/deployed. It generates device-specific certificates and ACL entries.

Usage:
    python register_f2_controller.py <MAC_ADDRESS> [--serial-number <SN>]
    
Example:
    python register_f2_controller.py e4:fd:45:f6:54:be --serial-number F2-001234
"""

import os
import sys
import subprocess
import argparse
import json
from datetime import datetime, timedelta

# Configuration
CA_KEY = "../certs/ca.key"
CA_CERT = "../certs/ca.crt"
DEVICES_DIR = "../certs/devices"
ACL_FILE = "../mosquitto/acl_file.conf"
REGISTRY_FILE = "../certs/device_registry.json"

def validate_mac_address(mac):
    """Validate and normalize MAC address format"""
    import re
    # Remove common separators and normalize
    mac_clean = re.sub(r'[:-]', '', mac.lower())
    if len(mac_clean) != 12:
        raise ValueError(f"Invalid MAC address length: {mac}")
    
    # Convert to standard format with dashes
    mac_formatted = '-'.join([mac_clean[i:i+2] for i in range(0, 12, 2)])
    return mac_formatted

def check_ca_exists():
    """Ensure CA certificate and key exist"""
    if not os.path.exists(CA_KEY) or not os.path.exists(CA_CERT):
        print("ERROR: CA certificate or key not found!")
        print(f"Expected: {CA_KEY} and {CA_CERT}")
        return False
    return True

def device_already_registered(mac):
    """Check if device is already registered"""
    device_dir = os.path.join(DEVICES_DIR, mac)
    return os.path.exists(device_dir)

def create_device_certificate(mac, serial_number=None):
    """Generate certificate for F2 controller"""
    print(f"Generating certificate for device: {mac}")
    
    # Create device directory
    device_dir = os.path.join(DEVICES_DIR, mac)
    os.makedirs(device_dir, exist_ok=True)
    
    # File paths
    device_key = os.path.join(device_dir, "device.key")
    device_csr = os.path.join(device_dir, "device.csr")
    device_crt = os.path.join(device_dir, "device.crt")
    
    # Subject for certificate (MAC as CN)
    subject = f"/C=US/ST=State/L=City/O=F2-Controllers/OU=IoT-Devices/CN={mac}"
    if serial_number:
        subject += f"/serialNumber={serial_number}"
    
    try:
        # Generate private key
        subprocess.run([
            "openssl", "genrsa", "-out", device_key, "2048"
        ], check=True, capture_output=True)
        
        # Generate CSR
        subprocess.run([
            "openssl", "req", "-new", "-key", device_key, "-out", device_csr,
            "-subj", subject
        ], check=True, capture_output=True)
        
        # Sign certificate with CA
        subprocess.run([
            "openssl", "x509", "-req", "-in", device_csr, 
            "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
            "-out", device_crt, "-days", "365"
        ], check=True, capture_output=True)
        
        # Set proper permissions
        os.chmod(device_key, 0o600)
        os.chmod(device_crt, 0o644)
        
        print(f"✓ Certificate generated: {device_crt}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Certificate generation failed: {e}")
        return False

def create_acl_entry(mac):
    """Add ACL entry for the device"""
    print(f"Adding ACL entry for device: {mac}")
    
    topic_base = f"f2-{mac}"
    acl_block = f"""
# Device: {mac} (registered {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
user {mac}
topic readwrite general
topic readwrite system/status
topic readwrite system/heartbeat

# Electric Strike Control
topic read    cmnd/{topic_base}/+/+/strike-+
topic write   stat/{topic_base}/+/+/strike-+

# Door Sensors Status
topic write   stat/{topic_base}/+/+/door-sensors

# QR/NFC Reader
topic read    cmnd/{topic_base}/+/+/reader-+/success
topic write   tele/{topic_base}/+/+/reader-+

# Exit Buttons
topic write   stat/{topic_base}/+/+/exit-buttons

# Siren Control
topic read    cmnd/{topic_base}/+/+/siren-+
topic write   stat/{topic_base}/+/+/siren-+

# Motion Sensors
topic write   stat/{topic_base}/+/+/motion-sensor-+

# RS-485 Sensors
topic write   tele/{topic_base}/+/+/sensor-+

"""
    
    try:
        with open(ACL_FILE, "a") as f:
            f.write(acl_block)
        print(f"✓ ACL entry added to {ACL_FILE}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to add ACL entry: {e}")
        return False

def update_device_registry(mac, serial_number=None):
    """Update device registry with registration info"""
    registry = {}
    
    # Load existing registry
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                registry = json.load(f)
        except:
            registry = {}
    
    # Add device entry
    registry[mac] = {
        "mac_address": mac,
        "serial_number": serial_number,
        "registered_at": datetime.now().isoformat(),
        "certificate_expires": (datetime.now() + timedelta(days=365)).isoformat(),
        "status": "active"
    }
    
    # Save registry
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)
        print(f"✓ Device registry updated: {REGISTRY_FILE}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to update registry: {e}")
        return False

def generate_client_config(mac):
    """Generate client connection configuration"""
    device_dir = os.path.join(DEVICES_DIR, mac)
    config_file = os.path.join(device_dir, "mqtt_config.json")
    
    config = {
        "mqtt": {
            "host": "mqtt-broker",
            "port": 8883,
            "client_id": f"f2-{mac}",
            "username": mac,
            "tls": {
                "ca_cert": "/certs/ca.crt",
                "client_cert": "/certs/device.crt", 
                "client_key": "/certs/device.key",
                "verify_mode": "required"
            }
        },
        "topics": {
            "base": f"f2-{mac}",
            "general": "general",
            "status": "system/status",
            "heartbeat": "system/heartbeat"
        }
    }
    
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"✓ Client config generated: {config_file}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to generate client config: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Register F2 Smart Controller")
    parser.add_argument("mac_address", help="MAC address of the F2 controller")
    parser.add_argument("--serial-number", help="Serial number of the device")
    parser.add_argument("--force", action="store_true", help="Force re-registration")
    
    args = parser.parse_args()
    
    try:
        # Validate MAC address
        mac = validate_mac_address(args.mac_address)
        print(f"Registering F2 Controller: {mac}")
        
        # Check prerequisites
        if not check_ca_exists():
            sys.exit(1)
        
        # Check if already registered
        if device_already_registered(mac) and not args.force:
            print(f"ERROR: Device {mac} is already registered!")
            print("Use --force to re-register")
            sys.exit(1)
        
        # Create directories
        os.makedirs(DEVICES_DIR, exist_ok=True)
        
        # Registration process
        success = True
        success &= create_device_certificate(mac, args.serial_number)
        success &= create_acl_entry(mac)
        success &= update_device_registry(mac, args.serial_number)
        success &= generate_client_config(mac)
        
        if success:
            print(f"\n✅ F2 Controller {mac} registered successfully!")
            print(f"📁 Certificate location: {DEVICES_DIR}/{mac}/")
            print(f"🔐 Device can now connect using mTLS on port 8883")
            print(f"📋 Device topics: f2-{mac}/*")
        else:
            print(f"\n❌ Registration failed for {mac}")
            sys.exit(1)
            
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nRegistration cancelled by user")
        sys.exit(1)

if __name__ == "__main__":
    main()