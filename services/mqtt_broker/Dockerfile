FROM eclipse-mosquitto:2

# Copy certificates from ca/ directory
COPY ca/ca.crt /mosquitto/certs/ca.crt
COPY ca/server.crt /mosquitto/certs/server.crt
COPY ca/server.key /mosquitto/certs/server.key

# Copy configuration files
COPY services/mqtt_broker/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY services/mqtt_broker/acl /mosquitto/config/acl

# Set correct permissions
RUN chown -R mosquitto:mosquitto /mosquitto/certs /mosquitto/config && \
    chmod 600 /mosquitto/certs/server.key && \
    chmod 644 /mosquitto/certs/ca.crt /mosquitto/certs/server.crt && \
    chmod 600 /mosquitto/config/acl

# Use standard mosquitto command
CMD ["/usr/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
