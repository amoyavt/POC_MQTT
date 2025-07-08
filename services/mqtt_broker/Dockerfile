FROM eclipse-mosquitto:2

# Copy configuration files
COPY services/mqtt_broker/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY services/mqtt_broker/acl /mosquitto/config/acl

# Create certs directory and set permissions
RUN mkdir -p /mosquitto/certs && \
    chown -R mosquitto:mosquitto /mosquitto/certs /mosquitto/config && \
    chmod 600 /mosquitto/config/acl

# Use standard mosquitto command
CMD ["/usr/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
