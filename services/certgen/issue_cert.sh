# This script handles the issuance of a client certificate for a given MAC address.
# It's called by the FastAPI server when a request is made to the /issue endpoint.
# The script automates the process of generating a private key, a CSR,
# and signing the CSR with the root CA to create a client certificate.

#!/bin/bash
# The first argument to the script is the device's MAC address.
MAC=$1
# Define the output directory for the generated certificate files.
OUTDIR=/issued
# Define file paths for the key, CSR, and certificate.
KEY="$OUTDIR/$MAC.key"
CSR="$OUTDIR/$MAC.csr"
CRT="$OUTDIR/$MAC.crt"

# Generate a 2048-bit RSA private key for the client.
openssl genrsa -out "$KEY" 2048
# Create a Certificate Signing Request (CSR).
# The Common Name (CN) of the certificate is set to the MAC address,
# which is later used by Mosquitto as the username.
openssl req -new -key "$KEY" -out "$CSR" -subj "/CN=$MAC"
# Sign the CSR with the CA's key and certificate.
# The -batch flag allows the command to run non-interactively.
# The -extensions usr_cert flag applies the extensions defined in the openssl.cnf file.
openssl ca -batch -config "$OPENSSL_CNF" -keyfile "$CA_KEY" -cert "$CA_CERT" \
  -in "$CSR" -out "$CRT" -extensions usr_cert -days "${DEVICE_EXPIRY:-365}"