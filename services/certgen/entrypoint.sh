#!/bin/bash
# This script is the entrypoint for the certgen container.
# It ensures that a Certificate Authority (CA) exists before starting the API server.
# If no CA key is found, it initializes a new CA by generating a private key and a self-signed certificate.
# This allows the service to be self-contained and idempotent.
set -e
CA_DIR=/ca

# Check if the CA private key does not exist.
if [ ! -f "$CA_DIR/ca.key" ]; then
    echo "[INFO] Generating new CA..."
    # Create the initial files required by OpenSSL for managing a CA.
    touch "$CA_DIR/index.txt"
    echo 1000 > "$CA_DIR/serial"
    # Copy OpenSSL config to CA directory and substitute environment variables
    # Prepare OpenSSL configuration with substituted environment variables
    sed \
        -e "s/CN = MyIoTCA/CN = ${CA_CN:-MyIoTCA}/g" \
        -e "s/default_days      = 3650/default_days      = ${DEVICE_EXPIRY:-365}/g" \
        /app/openssl.cnf > "$CA_DIR/openssl.cnf"
    # Generate the CA's private key.
    openssl genrsa -out "$CA_DIR/ca.key" 4096
    # Generate the self-signed root CA certificate using environment variables.
    openssl req -x509 -new -nodes -key "$CA_DIR/ca.key" -sha256 \
        -days "${CA_EXPIRY:-3650}" -out "$CA_DIR/ca.crt" -config "$CA_DIR/openssl.cnf"
else
    echo "[INFO] Using existing CA..."
fi

# Generate MQTT broker server certificate if it doesn't exist
if [ ! -f "$CA_DIR/server.crt" ]; then
    echo "[INFO] Generating MQTT broker server certificate..."
    # Generate server private key
    openssl genrsa -out "$CA_DIR/server.key" 2048
    # Create certificate signing request
    openssl req -new -key "$CA_DIR/server.key" -out "$CA_DIR/server.csr" -subj "/CN=${BROKER_CN:-mqtt-broker}"
    # Sign with CA to create server certificate
    cd "$CA_DIR"
    openssl ca -batch -config "openssl.cnf" \
        -keyfile "ca.key" -cert "ca.crt" \
        -in "server.csr" -out "server.crt" -extensions usr_cert \
        -days "${BROKER_EXPIRY:-3650}"
    # Clean up temporary CSR
    rm "server.csr"
    echo "[SUCCESS] MQTT broker certificate generated"
else
    echo "[INFO] Using existing MQTT broker certificate..."
fi

# Start the FastAPI application using uvicorn.
# It listens on all network interfaces on port 8080.
cd /app
exec uvicorn api:app --host 0.0.0.0 --port 8080