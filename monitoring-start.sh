#!/bin/bash

echo "Starting IoT Architecture with Monitoring..."

# Create external network if it doesn't exist
docker network create iot-network 2>/dev/null || true

# Start main architecture
echo "Starting main IoT architecture..."
docker-compose up -d

# Wait a bit for services to start
echo "Waiting for core services to initialize..."
sleep 15

# Start monitoring stack
echo "Starting monitoring stack..."
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

echo "All services started!"
echo ""
echo "Access points:"
echo "- Grafana Dashboard: http://localhost:3000 (admin/admin)"
echo "- Prometheus: http://localhost:9090"
echo "- Health Monitor API: http://localhost:8000"
echo "- cAdvisor: http://localhost:8080"
echo ""
echo "Useful commands:"
echo "- View logs: docker-compose logs -f"
echo "- Monitor health: curl http://localhost:8000/health"
echo "- Stop all: docker-compose down && docker-compose -f monitoring/docker-compose.monitoring.yml down"