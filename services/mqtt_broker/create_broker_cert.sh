#!/bin/bash
# This script generates the server certificate for the MQTT broker.
# It should be run once during the initial setup of the system to create the
# server's identity, which is required for the TLS handshake with clients.
# Without the server certificate and key, the broker cannot start in TLS mode.

# Exit immediately if a command exits with a non-zero status.
set -e

# The hostname for the broker, which will be the Common Name (CN) in the certificate.
# This should match the service name used by clients to connect (e.g., 'mqtt-broker' or 'localhost').
HOSTNAME=$1
if [ -z "$HOSTNAME" ]; then
  echo "Usage: $0 <hostname>"
  echo "Example: $0 mqtt-broker"
  exit 1
fi

# Define paths relative to this script's location (services/mqtt_broker/).
# The CA directory is expected to be at the project root.
CA_DIR="../../ca"
# The OpenSSL config is located in the certgen service directory.
OPENSSL_CNF="../certgen/openssl.cnf"

# Verify that the Certificate Authority has been created first.
# The certgen-api service's entrypoint script creates the CA.
if [ ! -f "$CA_DIR/ca.key" ]; then
    echo "[ERROR] CA not found in $CA_DIR. Please run the certgen-api service first to create the CA."
    exit 1
fi

echo "[INFO] Generating broker certificate for hostname: $HOSTNAME"

# Define the full paths for the server's key, CSR, and certificate files.
# These will be created in the main 'ca' directory so the broker container can access them.
KEY="$CA_DIR/server.key"
CSR="$CA_DIR/server.csr"
CRT="$CA_DIR/server.crt"

# 1. Generate a 2048-bit RSA private key for the MQTT broker.
openssl genrsa -out "$KEY" 2048

# 2. Create a Certificate Signing Request (CSR) for the broker.
# The Common Name (CN) is set to the hostname, which identifies the server.
openssl req -new -key "$KEY" -out "$CSR" -subj "/CN=$HOSTNAME"

# 3. Sign the CSR with the root CA to create the server certificate.
# This step uses the CA's key and certificate to vouch for the server's identity.
# The '-extensions usr_cert' flag applies the 'serverAuth' and 'clientAuth' extensions
# from the openssl.cnf file, marking this as a valid server certificate.
openssl ca -batch -config "$OPENSSL_CNF" \
  -keyfile "$CA_DIR/ca.key" -cert "$CA_DIR/ca.crt" \
  -in "$CSR" -out "$CRT" -extensions usr_cert

# 4. Clean up the temporary CSR file as it is no longer needed.
rm "$CSR"

echo "[SUCCESS] Broker certificate and key created in $CA_DIR"
echo "  - Key: $KEY"
echo "  - Certificate: $CRT"
