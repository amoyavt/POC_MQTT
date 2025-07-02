#!/usr/bin/env python3
"""
Test F2 Controller Registration

This script demonstrates registering multiple F2 controllers with different MAC addresses.
"""

import subprocess
import sys

# Test MAC addresses for demo F2 controllers
test_devices = [
    {"mac": "e4:fd:45:f6:54:be", "serial": "F2-001234"},
    {"mac": "a8:b2:c3:d4:e5:f6", "serial": "F2-001235"},
    {"mac": "12:34:56:78:9a:bc", "serial": "F2-001236"}
]

def register_device(mac, serial):
    """Register a single device"""
    print(f"\n🔧 Registering F2 Controller: {mac}")
    
    try:
        result = subprocess.run([
            "python3", "register_f2_controller.py", 
            mac, "--serial-number", serial
        ], check=True, capture_output=True, text=True)
        
        print(f"✅ Successfully registered {mac}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to register {mac}")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("🚀 F2 Controller Registration Test")
    print("=" * 50)
    
    success_count = 0
    total_count = len(test_devices)
    
    for device in test_devices:
        if register_device(device["mac"], device["serial"]):
            success_count += 1
    
    print(f"\n📊 Registration Summary:")
    print(f"✅ Successful: {success_count}/{total_count}")
    print(f"❌ Failed: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 All devices registered successfully!")
        print("Devices can now connect to MQTT broker using mTLS")
    else:
        print(f"\n⚠️  {total_count - success_count} devices failed registration")
        sys.exit(1)

if __name__ == "__main__":
    main()