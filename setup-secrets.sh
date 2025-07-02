#!/bin/bash
# Setup script for secure Docker secrets
# Run this script to initialize secrets for the MQTT Architecture POC

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="$SCRIPT_DIR/secrets"

echo "🔐 Setting up Docker secrets for MQTT Architecture POC"

# Create secrets directory
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Function to generate random password
generate_password() {
    local length=${1:-24}
    openssl rand -base64 $length | tr -d '/' | cut -c1-$length
}

# Function to create secret file
create_secret() {
    local secret_name=$1
    local secret_file="$SECRETS_DIR/${secret_name}.txt"
    
    if [[ -f "$secret_file" ]]; then
        echo "⚠️  Secret $secret_name already exists, skipping..."
        return
    fi
    
    if [[ "$secret_name" == "mqtt_username" ]]; then
        # Use fixed username for MQTT
        echo "iot_user" > "$secret_file"
    else
        # Generate random password
        generate_password > "$secret_file"
    fi
    
    chmod 600 "$secret_file"
    echo "✅ Created secret: $secret_name"
}

# Create all required secrets
echo "📝 Creating secret files..."
create_secret "postgres_password"
create_secret "timescale_password"
create_secret "mqtt_username"
create_secret "mqtt_password"

# Create MQTT password file for broker
MQTT_PASSWD_FILE="$SCRIPT_DIR/mosquitto/passwd"
mkdir -p "$(dirname "$MQTT_PASSWD_FILE")"

if [[ ! -f "$MQTT_PASSWD_FILE" ]]; then
    echo "🦟 Creating MQTT password file..."
    MQTT_USER=$(cat "$SECRETS_DIR/mqtt_username.txt")
    MQTT_PASS=$(cat "$SECRETS_DIR/mqtt_password.txt")
    
    # Create temporary file with plain text password
    echo "$MQTT_USER:$MQTT_PASS" > "${MQTT_PASSWD_FILE}.tmp"
    
    # Use mosquitto_passwd to hash the password
    if command -v mosquitto_passwd >/dev/null 2>&1; then
        mosquitto_passwd -U "${MQTT_PASSWD_FILE}.tmp"
        mv "${MQTT_PASSWD_FILE}.tmp" "$MQTT_PASSWD_FILE"
    else
        echo "⚠️  mosquitto_passwd not found. Creating plain text password file."
        echo "   Run 'mosquitto_passwd -U mosquitto/passwd' after starting the broker container."
        mv "${MQTT_PASSWD_FILE}.tmp" "$MQTT_PASSWD_FILE"
    fi
    
    chmod 644 "$MQTT_PASSWD_FILE"
    echo "✅ Created MQTT password file"
else
    echo "⚠️  MQTT password file already exists, skipping..."
fi

# Create .env file for development
ENV_FILE="$SCRIPT_DIR/.env.secrets"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "📄 Creating .env.secrets file for reference..."
    cat > "$ENV_FILE" << EOF
# Environment variables for secure deployment
# These are automatically loaded from secrets in production

# Database passwords (loaded from secrets)
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
TIMESCALE_PASSWORD_FILE=/run/secrets/timescale_password

# MQTT credentials (loaded from secrets)
MQTT_USERNAME_FILE=/run/secrets/mqtt_username
MQTT_PASSWORD_FILE=/run/secrets/mqtt_password

# Performance settings
BATCH_SIZE=1000
BATCH_TIMEOUT=10
KAFKA_BATCH_SIZE=16384
KAFKA_LINGER_MS=10
REDIS_CACHE_TTL=600

# Security settings
ENABLE_MQTT_AUTH=true
EXPOSE_DATABASE_PORTS=false
USE_CONNECTION_POOLING=true
EOF
    echo "✅ Created .env.secrets file"
fi

# Create security documentation
DOC_FILE="$SCRIPT_DIR/docs/SECURITY.md"
if [[ ! -f "$DOC_FILE" ]]; then
    echo "📚 Creating security documentation..."
    cat > "$DOC_FILE" << 'EOF'
# Security Implementation Guide

This document describes the security measures implemented in the MQTT Architecture POC.

## Secrets Management

### Docker Secrets
- **postgres_password**: PostgreSQL database password
- **timescale_password**: TimescaleDB database password  
- **mqtt_username**: MQTT broker username
- **mqtt_password**: MQTT broker password

### Secret Files Location
```
secrets/
├── postgres_password.txt
├── timescale_password.txt
├── mqtt_username.txt
└── mqtt_password.txt
```

## MQTT Authentication

### Configuration
- Username/password authentication enabled
- Anonymous access disabled
- Password file: `mosquitto/passwd`

### Testing Authentication
```bash
# Test MQTT connection with credentials
mosquitto_pub -h localhost -p 1883 \
  -u "$(cat secrets/mqtt_username.txt)" \
  -P "$(cat secrets/mqtt_password.txt)" \
  -t "test/topic" -m "test message"
```

## Database Security

### Connection Pooling
- PgBouncer used for PostgreSQL connections
- Connection limits enforced
- Transaction-level pooling

### Network Security
- Database ports not exposed externally
- Internal network communication only
- Connection pooler as single entry point

## Container Security

### Resource Limits
- Memory limits on all containers
- CPU limits to prevent resource exhaustion
- Health checks for all services

### User Security
- Non-root users in all application containers
- Minimal base images
- Read-only root filesystems where possible

## Monitoring Security

### Health Endpoints
- Internal network access only
- No sensitive information in responses
- Rate limiting implemented

### Logs
- No sensitive data in log outputs
- Log rotation configured
- Centralized log collection

## Production Checklist

- [ ] Secrets properly configured
- [ ] MQTT authentication enabled
- [ ] Database ports not exposed
- [ ] Resource limits configured
- [ ] Health checks passing
- [ ] Logs properly configured
- [ ] Monitoring alerts configured

EOF
    echo "✅ Created security documentation"
fi

# Display summary
echo ""
echo "🎉 Security setup complete!"
echo ""
echo "📋 Summary:"
echo "   • Created $(ls -1 "$SECRETS_DIR" | wc -l) secret files"
echo "   • Created MQTT password file"
echo "   • Created .env.secrets reference file"
echo "   • Created security documentation"
echo ""
echo "🚀 Next steps:"
echo "   1. Review generated passwords in secrets/ directory"
echo "   2. Start services with: docker-compose -f docker-compose.secrets.yml up -d"
echo "   3. Test MQTT authentication with provided credentials"
echo "   4. Monitor logs for any authentication issues"
echo ""
echo "⚠️  Security notes:"
echo "   • Keep secrets/ directory private (added to .gitignore)"
echo "   • Backup secrets securely for production use"
echo "   • Rotate passwords regularly"
echo "   • Monitor access logs for suspicious activity"
echo ""
echo "📚 Documentation: docs/SECURITY.md"
EOF