#!/bin/sh
set -e

# Set permissions for the ACL file
chmod 0700 /mosquitto/config/acl

# Fix certificate permissions for mosquitto to read
chmod 644 /mosquitto/certs/server.key /mosquitto/certs/server.crt /mosquitto/certs/ca.crt

# Execute the original command
exec "$@"
