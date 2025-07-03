# This script is the entrypoint for the certgen container.
# It ensures that a Certificate Authority (CA) exists before starting the API server.
# If no CA key is found, it initializes a new CA by generating a private key and a self-signed certificate.
# This allows the service to be self-contained and idempotent.

#!/bin/bash
set -e
CA_DIR=/ca

# Check if the CA private key does not exist.
if [ ! -f "$CA_DIR/ca.key" ]; then
    echo "[INFO] Generating new CA..."
    # Create the initial files required by OpenSSL for managing a CA.
    touch "$CA_DIR/index.txt"
    echo 1000 > "$CA_DIR/serial"
    # Generate the CA's private key.
    openssl genrsa -out "$CA_DIR/ca.key" 4096
    # Generate the self-signed root CA certificate, valid for 10 years.
    openssl req -x509 -new -nodes -key "$CA_DIR/ca.key" -sha256 \
        -days 3650 -out "$CA_DIR/ca.crt" -config "$CA_DIR/openssl.cnf"
else
    echo "[INFO] Using existing CA..."
fi

# Start the FastAPI application using uvicorn.
# It listens on all network interfaces on port 8080.
exec uvicorn server:app --host 0.0.0.0 --port 8080