.PHONY: build up down logs clean test

# Build all services
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d

# Stop all services  
down:
	docker-compose down

# View logs for all services
logs:
	docker-compose logs -f

# Clean up everything (containers, volumes, networks)
clean:
	@echo "Stopping and cleaning up all services..."
	docker-compose down -v --remove-orphans
	docker-compose -f monitoring/docker-compose.monitoring.yml down -v --remove-orphans 2>/dev/null || true
	@echo "Cleaning up Docker system..."
	docker system prune -f
	@echo "Cleanup complete!"

# Test the system by checking if all services are running
test:
	@echo "Checking service health..."
	@docker-compose ps
	@echo "\nWaiting for services to be ready..."
	@sleep 10
	@echo "\nChecking Kafka topics..."
	@docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list || true
	@echo "\nChecking database connections..."
	@docker exec device-params-db pg_isready -U iot_user || true
	@docker exec timescale-db pg_isready -U ts_user || true

# Start only infrastructure services (no data processing)
infra:
	docker-compose up -d mosquitto zookeeper kafka postgres timescaledb

# Start data processing services
services:
	docker-compose up -d mqtt-kafka-connector data-processor kafka-timescale-sink

# Start simulator
simulate:
	docker-compose up -d f2-simulator

# View specific service logs
logs-connector:
	docker-compose logs -f mqtt-kafka-connector

logs-processor:
	docker-compose logs -f data-processor

logs-sink:
	docker-compose logs -f kafka-timescale-sink

logs-simulator:
	docker-compose logs -f f2-simulator

# Database access shortcuts
db-params:
	docker exec -it device-params-db psql -U iot_user -d device_params

db-timescale:
	docker exec -it timescale-db psql -U ts_user -d timeseries

# Kafka monitoring shortcuts
kafka-topics:
	docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

kafka-raw:
	docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic raw_iot_data --from-beginning

kafka-decoded:
	docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic decoded_iot_data --from-beginning

# MQTT monitoring
mqtt-monitor:
	docker exec mosquitto mosquitto_sub -h localhost -t "cmnd/f2-#"

# Monitoring commands
monitoring-up:
	./monitoring-start.sh

monitoring-down:
	docker-compose -f monitoring/docker-compose.monitoring.yml down -v

monitoring-logs:
	docker-compose -f monitoring/docker-compose.monitoring.yml logs -f

# Health check
health:
	@echo "Checking system health..."
	@curl -s http://localhost:8000/health | jq '.' || echo "Health monitor not available"

# Container status
status:
	@echo "Container Status:"
	@docker-compose ps
	@echo "\nMonitoring Stack:"
	@docker-compose -f monitoring/docker-compose.monitoring.yml ps 2>/dev/null || echo "Monitoring stack not running"

# Complete setup with monitoring
full-setup:
	@echo "Setting up complete IoT architecture with monitoring..."
	make monitoring-up
	@echo "Setup complete! Check status with 'make status'"

# Nuclear cleanup - force remove everything
nuclear-clean:
	@echo "Nuclear cleanup - removing ALL containers and data..."
	docker-compose down -v --remove-orphans 2>/dev/null || true
	docker-compose -f monitoring/docker-compose.monitoring.yml down -v --remove-orphans 2>/dev/null || true
	@echo "Stopping all IoT project containers..."
	docker stop $$(docker ps -q --filter "name=mosquitto") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=kafka") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=zookeeper") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=postgres") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=timescale") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=prometheus") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=grafana") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=cadvisor") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=node-exporter") 2>/dev/null || true
	docker stop $$(docker ps -q --filter "name=health-monitor") 2>/dev/null || true
	@echo "Removing stopped containers..."
	docker container prune -f
	@echo "Removing unused volumes..."
	docker volume prune -f
	@echo "Removing unused networks..."
	docker network prune -f
	@echo "Nuclear cleanup complete!"