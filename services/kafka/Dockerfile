FROM confluentinc/cp-kafka:7.4.0

# Copy entrypoint script with executable permissions
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]