# Security Implementation Guide

> Complete security documentation for the MQTT Architecture POC

## 📋 Table of Contents
- [Security Overview](#security-overview)
- [Implemented Security Measures](#implemented-security-measures)
- [Secrets Management](#secrets-management)
- [MQTT Authentication](#mqtt-authentication)
- [Database Security](#database-security)
- [Container Security](#container-security)
- [Network Security](#network-security)
- [SQL Injection Prevention](#sql-injection-prevention)
- [Security Configuration](#security-configuration)
- [Testing Security](#testing-security)
- [Production Security Checklist](#production-security-checklist)

## 🔒 Security Overview

The MQTT Architecture POC implements comprehensive security measures to protect against common vulnerabilities and ensure production-ready deployment. All critical security issues identified in the initial assessment have been addressed.

### Security Improvements Implemented

| Issue | Status | Solution |
|-------|--------|----------|
| **Hardcoded credentials** | ✅ Fixed | Docker secrets management |
| **No MQTT authentication** | ✅ Fixed | Username/password authentication |
| **SQL injection risks** | ✅ Fixed | Parameterized queries + input validation |
| **Root containers** | ✅ Fixed | Non-root users in all containers |
| **Exposed database ports** | ✅ Fixed | Internal network only |
| **No connection pooling** | ✅ Fixed | PgBouncer + threaded pools |
| **Missing input validation** | ✅ Fixed | Strict validation + whitelisting |

## 🛡️ Implemented Security Measures

### 1. Credential Management

**Problem**: Hardcoded passwords in configuration files
**Solution**: Docker secrets with file-based authentication

```bash
# Secrets are stored in files, not environment variables
secrets/
├── postgres_password.txt
├── timescale_password.txt
├── mqtt_username.txt
└── mqtt_password.txt
```

**Benefits**:
- Passwords not visible in environment variables
- Proper file permissions (600)
- Easy rotation without code changes
- Not stored in version control

### 2. MQTT Authentication

**Problem**: Anonymous MQTT access allowed
**Solution**: Mandatory username/password authentication

```bash
# MQTT broker configuration
allow_anonymous false
password_file /mosquitto/config/passwd
```

**Implementation**:
- All MQTT clients must authenticate
- Hashed password storage
- Connection logging enabled
- Failed authentication attempts logged

### 3. SQL Injection Prevention

**Problem**: Dynamic query construction with user input
**Solution**: Parameterized queries with strict input validation

```python
# Before (vulnerable)
query = f"SELECT * FROM device WHERE mac = '{mac_addr}'"

# After (secure)
query = "SELECT * FROM device WHERE LOWER(mac) = LOWER(%s)"
cursor.execute(query, (validated_mac_addr,))
```

**Validation implemented**:
- MAC address format validation (12 hex characters)
- Numeric parameter bounds checking
- Input length limits
- Whitelist-based mode validation

### 4. Container Security

**Problem**: Containers running as root
**Solution**: Dedicated non-root users

```dockerfile
# Create and use non-root user
RUN groupadd -r iotuser && useradd -r -g iotuser iotuser
USER iotuser
```

**Security features**:
- All application containers run as `iotuser`
- Resource limits configured
- Health checks implemented
- Minimal base images

## 🔐 Secrets Management

### Setup Process

```bash
# 1. Initialize secrets
./setup-secrets.sh

# 2. Start secure deployment
make secure-setup

# 3. Verify security configuration
make security-check
```

### Secret Files

| Secret | Purpose | Location |
|--------|---------|----------|
| `postgres_password.txt` | PostgreSQL database access | `secrets/` |
| `timescale_password.txt` | TimescaleDB access | `secrets/` |
| `mqtt_username.txt` | MQTT broker username | `secrets/` |
| `mqtt_password.txt` | MQTT broker password | `secrets/` |

### Password Requirements

- **Length**: Minimum 24 characters
- **Complexity**: Base64 encoded random strings
- **Uniqueness**: Different passwords for each service
- **Rotation**: Easy to change without code modifications

### Access Control

```bash
# Proper file permissions
chmod 700 secrets/           # Directory: owner only
chmod 600 secrets/*.txt      # Files: owner read/write only
```

## 🦟 MQTT Authentication

### Configuration

The MQTT broker requires authentication for all connections:

```conf
# mosquitto.conf
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
```

### Password File Management

```bash
# Create hashed password file
mosquitto_passwd -c mosquitto/passwd username

# Add additional users
mosquitto_passwd mosquitto/passwd newuser

# Update existing password
mosquitto_passwd mosquitto/passwd username
```

### Client Authentication

All MQTT clients (connector, simulator) use authentication:

```python
# Client configuration
client.username_pw_set(username, password)
client.connect(host, port, keepalive)
```

### Testing Authentication

```bash
# Test with valid credentials
mosquitto_pub -h localhost -p 1883 \
  -u "$(cat secrets/mqtt_username.txt)" \
  -P "$(cat secrets/mqtt_password.txt)" \
  -t "test/topic" -m "test message"

# Test without credentials (should fail)
mosquitto_pub -h localhost -p 1883 \
  -t "test/topic" -m "test message"
```

## 🗄️ Database Security

### Connection Pooling

**PgBouncer** provides connection pooling and additional security:

```yaml
pgbouncer:
  environment:
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 100
    DEFAULT_POOL_SIZE: 20
```

**Benefits**:
- Limits concurrent connections
- Prevents connection exhaustion attacks
- Transaction-level isolation
- Connection reuse efficiency

### Network Isolation

```yaml
# Database ports not exposed externally
postgres:
  # ports:  # Commented out for security
  #   - "5432:5432"
  networks:
    - iot-network  # Internal network only
```

### Access Control

- Services connect through PgBouncer
- Direct database access only from container network
- No external port exposure
- Encrypted connections within Docker network

## 🐳 Container Security

### Non-Root Users

All application containers use dedicated users:

```dockerfile
# Create non-root user
RUN groupadd -r iotuser && useradd -r -g iotuser iotuser

# Set ownership
RUN chown -R iotuser:iotuser /app

# Switch to non-root user
USER iotuser
```

### Resource Limits

```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
    reservations:
      memory: 512M
      cpus: '0.5'
```

### Health Checks

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import psycopg2; exit(0)"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## 🌐 Network Security

### Network Segmentation

```yaml
networks:
  iot-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### Port Exposure Matrix

| Service | Internal Port | External Port | Purpose |
|---------|---------------|---------------|---------|
| MQTT Broker | 1883 | 1883 | MQTT protocol |
| MQTT WebSocket | 9001 | 9001 | Web clients |
| Kafka | 29092 | 9092 | External access |
| PostgreSQL | 5432 | ❌ None | Internal only |
| TimescaleDB | 5432 | ❌ None | Internal only |
| PgBouncer | 5432 | 6432 | Connection pooling |
| Redis | 6379 | ❌ None | Internal caching |

### Firewall Recommendations

```bash
# Production firewall rules
iptables -A INPUT -p tcp --dport 1883 -j ACCEPT  # MQTT
iptables -A INPUT -p tcp --dport 3000 -j ACCEPT  # Grafana
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT  # Health API
iptables -A INPUT -p tcp --dport 5432 -j DROP    # Block PostgreSQL
iptables -A INPUT -p tcp --dport 5433 -j DROP    # Block TimescaleDB
```

## 🛡️ SQL Injection Prevention

### Input Validation

```python
def _validate_mac_address(self, mac_addr: str) -> bool:
    """Validate MAC address format for security."""
    if not mac_addr or len(mac_addr) != 12:
        return False
    return all(c in '0123456789abcdefABCDEF' for c in mac_addr)

def _validate_input_parameters(self, mac_addr: str, connector_number: int, pin_position: int) -> bool:
    """Validate all input parameters to prevent SQL injection."""
    if not self._validate_mac_address(mac_addr):
        return False
    if connector_number < 0 or connector_number > 99:
        return False
    if pin_position < 0 or pin_position > 99:
        return False
    return True
```

### Parameterized Queries

```python
# Secure query with parameters
query = '''
SELECT dp."DataPointId", dp."Label", dp."Offset", dp."Length"
FROM "DataPoint" dp
WHERE LOWER(controller."MacAddress") = LOWER(%s)
  AND c."ConnectorNumber" = %s
  AND p."Position" = %s;
'''

cursor.execute(query, (mac_addr, connector_number, pin_position))
```

### Topic Parsing Security

```python
# Compiled regex for security and performance
self.topic_pattern = re.compile(r'^cmnd/f2-([a-fA-F0-9]{12})/([^/]+)/(\\d+)/sensor-(\\d+)$')

# Whitelist validation
allowed_modes = {'sensor-mode', 'access-control-mode', 'alarm-mode'}
if mode not in allowed_modes:
    logger.warning(f"Unknown mode '{mode}' in topic: {topic}")
```

## ⚙️ Security Configuration

### Environment Variables

```bash
# Security-related environment variables
ENABLE_MQTT_AUTH=true
EXPOSE_DATABASE_PORTS=false
USE_CONNECTION_POOLING=true
CACHE_TTL=600
```

### File Structure

```
mqtt_architecture_poc/
├── secrets/                    # Secret files (gitignored)
│   ├── postgres_password.txt
│   ├── timescale_password.txt
│   ├── mqtt_username.txt
│   └── mqtt_password.txt
├── mosquitto/
│   ├── mosquitto.conf         # Secure MQTT config
│   └── passwd                 # Hashed passwords
├── docker-compose.secrets.yml # Secure deployment
└── setup-secrets.sh          # Security setup script
```

### Git Security

```bash
# .gitignore entries for security
secrets/
*.key
*.pem
*.p12
.env.local
mosquitto/passwd
```

## 🧪 Testing Security

### MQTT Authentication Test

```bash
# Test authentication required
make mqtt-test

# Monitor authentication attempts
docker-compose logs mqtt-broker | grep -i auth
```

### Database Security Test

```bash
# Verify no external database access
nc -zv localhost 5432  # Should fail
nc -zv localhost 5433  # Should fail

# Verify internal access works
docker exec data-processor python -c "import psycopg2; print('DB accessible')"
```

### Container Security Test

```bash
# Verify non-root users
docker exec data-processor whoami                    # Should show: iotuser
docker exec kafka-timescale-sink whoami             # Should show: iotuser
docker exec mqtt-kafka-connector whoami             # Should show: iotuser
```

### Input Validation Test

```bash
# Test invalid MAC address rejection
docker-compose logs data-processor | grep "Invalid MAC address"

# Test SQL injection attempt (should be blocked)
# Attempts to inject malicious input through MQTT topics
```

## ✅ Production Security Checklist

### Pre-Deployment

- [ ] **Secrets configured**: All password files created with strong passwords
- [ ] **MQTT authentication**: Anonymous access disabled, password file configured
- [ ] **Database isolation**: External ports not exposed
- [ ] **Container users**: All containers run as non-root users
- [ ] **Resource limits**: Memory and CPU limits configured
- [ ] **Network segmentation**: Services isolated in Docker network

### Security Validation

- [ ] **Authentication tests**: MQTT auth working, database access secured
- [ ] **Input validation**: Invalid inputs properly rejected
- [ ] **Error handling**: No sensitive information in error messages
- [ ] **Logging security**: No passwords or sensitive data in logs
- [ ] **File permissions**: Secret files have correct permissions (600)

### Monitoring and Maintenance

- [ ] **Security monitoring**: Failed authentication attempts logged
- [ ] **Health checks**: All services have health checks configured
- [ ] **Update process**: Container images updated regularly
- [ ] **Backup security**: Database backups encrypted and secured
- [ ] **Incident response**: Procedures for security incidents defined

### Production Hardening

- [ ] **TLS encryption**: Consider adding TLS for MQTT and HTTP endpoints
- [ ] **Certificate management**: Implement proper certificate rotation
- [ ] **Network policies**: Additional firewall rules for production
- [ ] **Audit logging**: Comprehensive audit trail configuration
- [ ] **Penetration testing**: Regular security assessments

## 🔗 Related Documentation

- **[Developer Guide](DEVELOPER_GUIDE.md)** - Secure development practices
- **[Debugging Guide](DEBUGGING.md)** - Security-aware troubleshooting
- **[TimescaleDB Guide](TIMESCALE.md)** - Database security
- **[Architecture Overview](architecture/overview.md)** - Security architecture

## 📞 Security Support

### Reporting Security Issues

1. **Email**: Create security issue in private repository
2. **Include**: Detailed description, reproduction steps, impact assessment
3. **Response**: Security issues prioritized and addressed within 24 hours

### Security Best Practices

1. **Regular Updates**: Keep all dependencies and base images updated
2. **Principle of Least Privilege**: Minimal required permissions
3. **Defense in Depth**: Multiple security layers
4. **Security by Design**: Security considered in all development decisions
5. **Continuous Monitoring**: Regular security assessments and monitoring

---

**🔒 Security is Everyone's Responsibility** - Follow secure coding practices, report vulnerabilities, and keep security at the forefront of all development activities.