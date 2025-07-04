#!/bin/sh
set -e

# Set permissions for the ACL file
chmod 0700 /mosquitto/config/acl

# Execute the original command
exec "$@"
