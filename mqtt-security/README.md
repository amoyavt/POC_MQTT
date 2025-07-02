# MQTT Security Implementation Guide

## Overview

This implementation provides mTLS-based authentication and MAC address authorization for F2 Smart Controllers. Each device gets a unique certificate during registration and can only access its own topics.

## 🔐 Security Features

- **mTLS Authentication**: Devices authenticate using client certificates
- **MAC-based Identity**: Device MAC address is embedded in certificate CN
- **Topic-level Authorization**: Each device can only access its own topics
- **Certificate Lifecycle**: Automated certificate generation during registration

## 📁 Directory Structure

```
mqtt-security/
├── certs/
│   ├── ca.crt                    # Root CA certificate
│   ├── ca.key                    # Root CA private key
│   ├── server.crt                # MQTT broker certificate
│   ├── server.key                # MQTT broker private key
│   ├── device_registry.json      # Device registration database
│   └── devices/
│       └── <MAC>/
│           ├── device.key        # Device private key
│           ├── device.csr        # Device certificate request
│           ├── device.crt        # Device certificate
│           └── mqtt_config.json  # Device MQTT configuration
├── mosquitto/
│   ├── mosquitto.conf           # Mosquitto configuration
│   └── acl_file.conf           # Access control list
└── scripts/
    ├── register_f2_controller.py # Device registration script
    ├── test_registration.py      # Registration testing
    └── secure_f2_client.py      # Secure client example
```

## 🚀 Quick Start

### 1. Register F2 Controllers

```bash
# Register a single device
cd mqtt-security/scripts
python3 register_f2_controller.py e4:fd:45:f6:54:be --serial-number F2-001234

# Register multiple test devices
python3 test_registration.py
```

### 2. Start Secure MQTT Broker

```bash
# From project root
docker-compose up mosquitto
```

### 3. Test Secure Connection

```bash
# Start secure F2 client simulation
cd mqtt-security/scripts
python3 secure_f2_client.py e4:fd:45:f6:54:be --simulate
```

## 📋 Registration Process

### Real-world Scenario
1. F2 Controller is manufactured with embedded MAC address
2. During sales/deployment, controller is registered using registration script
3. Certificate and ACL entry are generated automatically
4. Controller receives certificate through secure provisioning channel
5. Controller connects to MQTT broker using mTLS

### Registration Command
```bash
python3 register_f2_controller.py <MAC_ADDRESS> --serial-number <SERIAL>
```

### What Happens During Registration
1. ✅ Validates MAC address format
2. 🔑 Generates RSA 2048-bit private key
3. 📝 Creates certificate signing request (CSR)
4. 🔒 Signs certificate with CA (365 days validity)
5. 📋 Adds ACL entry for device topics
6. 📊 Updates device registry
7. ⚙️ Generates MQTT client configuration

## 🔑 Certificate Details

### CA Certificate
- **Algorithm**: RSA 4096-bit
- **Validity**: 10 years
- **Usage**: Signs all device certificates

### Device Certificates
- **Algorithm**: RSA 2048-bit
- **Validity**: 1 year
- **CN**: Device MAC address (e.g., `e4-fd-45-f6-54-be`)
- **Usage**: mTLS authentication

## 🛡️ Access Control

### Global Topics (All Devices)
- `general` - General announcements
- `system/status` - System status requests
- `system/heartbeat` - Heartbeat messages

### Device-Specific Topics
Each device with MAC `XX-XX-XX-XX-XX-XX` can access:

#### Electric Strike Control
- **Read**: `cmnd/f2-XX-XX-XX-XX-XX-XX/+/+/strike-+`
- **Write**: `stat/f2-XX-XX-XX-XX-XX-XX/+/+/strike-+`

#### Door Sensors
- **Write**: `stat/f2-XX-XX-XX-XX-XX-XX/+/+/door-sensors`

#### QR/NFC Reader
- **Read**: `cmnd/f2-XX-XX-XX-XX-XX-XX/+/+/reader-+/success`
- **Write**: `tele/f2-XX-XX-XX-XX-XX-XX/+/+/reader-+`

#### Exit Buttons
- **Write**: `stat/f2-XX-XX-XX-XX-XX-XX/+/+/exit-buttons`

#### Siren Control
- **Read**: `cmnd/f2-XX-XX-XX-XX-XX-XX/+/+/siren-+`
- **Write**: `stat/f2-XX-XX-XX-XX-XX-XX/+/+/siren-+`

#### Motion Sensors
- **Write**: `stat/f2-XX-XX-XX-XX-XX-XX/+/+/motion-sensor-+`

#### RS-485 Sensors
- **Write**: `tele/f2-XX-XX-XX-XX-XX-XX/+/+/sensor-+`

## 🔌 Connection Configuration

### MQTT Broker Ports
- **1883**: Insecure port (internal services only)
- **8883**: Secure mTLS port (F2 controllers)
- **9001**: WebSocket port

### Client Configuration Example
```json
{
  "mqtt": {
    "host": "mqtt-broker",
    "port": 8883,
    "client_id": "f2-e4-fd-45-f6-54-be",
    "username": "e4-fd-45-f6-54-be",
    "tls": {
      "ca_cert": "/certs/ca.crt",
      "client_cert": "/certs/device.crt",
      "client_key": "/certs/device.key",
      "verify_mode": "required"
    }
  }
}
```

## 🧪 Testing

### Manual Certificate Test
```bash
# Test certificate connection
mosquitto_pub \
  --cafile certs/ca.crt \
  --cert certs/devices/e4-fd-45-f6-54-be/device.crt \
  --key certs/devices/e4-fd-45-f6-54-be/device.key \
  -h localhost -p 8883 \
  -t "stat/f2-e4-fd-45-f6-54-be/access-control/conn1/strike-1" \
  -m "open"
```

### Automated Testing
```bash
# Register test devices
python3 scripts/test_registration.py

# Start multiple secure clients
python3 scripts/secure_f2_client.py e4:fd:45:f6:54:be --simulate &
python3 scripts/secure_f2_client.py a8:b2:c3:d4:e5:f6 --simulate &
```

## 🔄 Certificate Lifecycle

### Certificate Renewal
```bash
# Re-register device (generates new certificate)
python3 register_f2_controller.py <MAC> --force
```

### Certificate Revocation
1. Remove device certificate files
2. Remove ACL entry from `acl_file.conf`
3. Update device registry status to "revoked"
4. Restart mosquitto broker

## 📊 Monitoring

### Device Registry
All registered devices are tracked in `certs/device_registry.json`:
```json
{
  "e4-fd-45-f6-54-be": {
    "mac_address": "e4-fd-45-f6-54-be",
    "serial_number": "F2-001234",
    "registered_at": "2025-07-02T14:30:00",
    "certificate_expires": "2026-07-02T14:30:00",
    "status": "active"
  }
}
```

### Connection Logs
Monitor MQTT broker logs for authentication events:
```bash
docker logs mqtt-broker | grep -E "(Connected|Disconnected|Certificate)"
```

## 🔧 Production Considerations

### Security Hardening
- Use HSM for CA key storage
- Implement certificate pinning
- Add certificate revocation list (CRL)
- Enable audit logging
- Use separate CA for production

### Scalability
- Implement automated certificate rotation
- Use certificate provisioning API
- Add load balancing for MQTT brokers
- Implement certificate templates

### Operational
- Monitor certificate expiration dates
- Implement automated device onboarding
- Add device lifecycle management
- Create certificate backup procedures

## 🚨 Troubleshooting

### Common Issues

**Connection Refused**
- Check certificate files exist and are readable
- Verify CA certificate matches server certificate
- Confirm MQTT broker is running on port 8883

**Authentication Failed**
- Verify device MAC matches certificate CN
- Check ACL file contains device entry
- Confirm certificate hasn't expired

**Topic Access Denied**
- Verify topic format matches ACL patterns
- Check device MAC in topic path
- Confirm ACL file is loaded by mosquitto

### Debug Commands
```bash
# Verify certificate
openssl x509 -in certs/devices/<MAC>/device.crt -text -noout

# Test CA chain
openssl verify -CAfile certs/ca.crt certs/devices/<MAC>/device.crt

# Check MQTT connectivity
mosquitto_sub --cafile certs/ca.crt -h localhost -p 8883 -t "general"
```

This implementation provides a production-ready MQTT security solution for F2 Smart Controllers with proper certificate lifecycle management and access control.