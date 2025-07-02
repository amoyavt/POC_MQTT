# MQTT Architecture POC - Enhanced Makefile
# Provides commands for development, secure deployment, and operations

.PHONY: help setup full-setup secure-setup status health logs clean
.DEFAULT_GOAL := help

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

help: ## Show this help message
	@echo "$(BLUE)MQTT Architecture POC - Available Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Setup Commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(setup|init)" | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Development Commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -v -E "(setup|init|clean|stop)" | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Management Commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(clean|stop)" | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'

# Setup Commands
setup: ## Start basic development environment
	@echo "$(BLUE)Starting MQTT Architecture POC (Development Mode)$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)✅ Basic services started$(RESET)"

full-setup: ## Start complete system with monitoring
	@echo "$(BLUE)Starting MQTT Architecture POC (Full Stack)$(RESET)"
	docker-compose up -d
	@echo "$(YELLOW)⏳ Waiting for core services...$(RESET)"
	@sleep 15
	docker-compose -f monitoring/docker-compose.monitoring.yml up -d
	@echo "$(YELLOW)⏳ Waiting for monitoring stack...$(RESET)"
	@sleep 10
	@echo "$(GREEN)✅ Full stack ready!$(RESET)"
	@echo ""
	@echo "$(BLUE)📊 Access Points:$(RESET)"
	@echo "  • Grafana:       http://localhost:3000 (admin/admin)"
	@echo "  • Prometheus:    http://localhost:9090"
	@echo "  • Health API:    http://localhost:8000"
	@echo "  • cAdvisor:      http://localhost:8080"

secure-setup: ## Start secure production environment with secrets
	@echo "$(BLUE)Setting up Secure MQTT Architecture POC$(RESET)"
	@echo "$(YELLOW)🔐 Initializing security...$(RESET)"
	@if [ ! -d "secrets" ]; then \
		./setup-secrets.sh; \
	else \
		echo "$(GREEN)✅ Secrets already configured$(RESET)"; \
	fi
	@echo "$(YELLOW)🚀 Starting secure services...$(RESET)"
	docker-compose -f docker-compose.secrets.yml up -d
	@echo "$(YELLOW)⏳ Waiting for secure services...$(RESET)"
	@sleep 20
	docker-compose -f monitoring/docker-compose.monitoring.yml up -d
	@echo "$(YELLOW)⏳ Initializing monitoring...$(RESET)"
	@sleep 10
	@echo "$(GREEN)🔒 Secure stack ready!$(RESET)"
	@echo ""
	@echo "$(BLUE)📊 Secure Access Points:$(RESET)"
	@echo "  • Grafana:       http://localhost:3000 (admin/admin)"
	@echo "  • Health API:    http://localhost:8000"
	@echo ""
	@echo "$(YELLOW)⚠️  Security Notes:$(RESET)"
	@echo "  • Database ports not exposed externally"
	@echo "  • MQTT authentication enabled"
	@echo "  • Resource limits configured"
	@echo "  • Non-root containers"

# Status and Health
status: ## Show status of all services
	@echo "$(BLUE)Service Status$(RESET)"
	@echo "$(YELLOW)Core Services:$(RESET)"
	@docker-compose ps
	@echo ""
	@echo "$(YELLOW)Monitoring Services:$(RESET)"
	@docker-compose -f monitoring/docker-compose.monitoring.yml ps 2>/dev/null || echo "Monitoring stack not running"

health: ## Check system health
	@echo "$(BLUE)System Health Check$(RESET)"
	@if curl -s http://localhost:8000/health > /dev/null 2>&1; then \
		echo "$(GREEN)✅ Health API accessible$(RESET)"; \
		curl -s http://localhost:8000/health | jq . 2>/dev/null || curl -s http://localhost:8000/health; \
	else \
		echo "$(RED)❌ Health API not accessible$(RESET)"; \
	fi

# Logging Commands
logs: ## Show logs from all services
	docker-compose logs --tail=100 -f

logs-connector: ## Show MQTT-Kafka connector logs
	docker-compose logs --tail=100 -f mqtt-kafka-connector

logs-processor: ## Show data processor logs
	docker-compose logs --tail=100 -f data-processor

logs-sink: ## Show TimescaleDB sink logs
	docker-compose logs --tail=100 -f kafka-timescale-sink

logs-simulator: ## Show F2 simulator logs
	docker-compose logs --tail=100 -f f2-simulator

logs-health: ## Show health monitor logs
	docker-compose -f monitoring/docker-compose.monitoring.yml logs --tail=100 -f health-monitor

# Database Access
db-params: ## Connect to PostgreSQL (device parameters)
	@echo "$(BLUE)Connecting to PostgreSQL...$(RESET)"
	docker exec -it device-params-db psql -U iot_user -d device_params

db-timescale: ## Connect to TimescaleDB (time-series data)
	@echo "$(BLUE)Connecting to TimescaleDB...$(RESET)"
	docker exec -it timescale-db psql -U ts_user -d timeseries

# Kafka Operations
kafka-topics: ## List Kafka topics
	docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

kafka-raw: ## Monitor raw IoT data topic
	@echo "$(BLUE)Monitoring raw_iot_data topic (Press Ctrl+C to stop)$(RESET)"
	docker exec kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic raw_iot_data \
		--from-beginning \
		--max-messages 10

kafka-decoded: ## Monitor decoded IoT data topic
	@echo "$(BLUE)Monitoring decoded_iot_data topic (Press Ctrl+C to stop)$(RESET)"
	docker exec kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic decoded_iot_data \
		--from-beginning \
		--max-messages 10

# MQTT Operations
mqtt-monitor: ## Monitor MQTT messages
	@echo "$(BLUE)Monitoring MQTT messages (Press Ctrl+C to stop)$(RESET)"
	@if [ -f "secrets/mqtt_username.txt" ] && [ -f "secrets/mqtt_password.txt" ]; then \
		docker exec mqtt-broker mosquitto_sub -t "cmnd/#" -v \
			-u "$$(cat secrets/mqtt_username.txt)" \
			-P "$$(cat secrets/mqtt_password.txt)"; \
	else \
		docker exec mqtt-broker mosquitto_sub -t "cmnd/#" -v; \
	fi

mqtt-test: ## Test MQTT publishing with authentication
	@echo "$(BLUE)Testing MQTT publish with authentication$(RESET)"
	@if [ -f "secrets/mqtt_username.txt" ] && [ -f "secrets/mqtt_password.txt" ]; then \
		docker exec mqtt-broker mosquitto_pub \
			-t "cmnd/f2-test123456/sensor-mode/1/sensor-1" \
			-m '{"data":"1234abcd","timestamp":"'$$(date +%s)'"}' \
			-u "$$(cat secrets/mqtt_username.txt)" \
			-P "$$(cat secrets/mqtt_password.txt)"; \
		echo "$(GREEN)✅ MQTT test message published$(RESET)"; \
	else \
		echo "$(RED)❌ MQTT secrets not found. Run 'make secure-setup' first.$(RESET)"; \
	fi

# Performance and Monitoring
performance: ## Show system performance metrics
	@echo "$(BLUE)System Performance$(RESET)"
	@echo "$(YELLOW)Container Resource Usage:$(RESET)"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
	@echo ""
	@echo "$(YELLOW)Disk Usage:$(RESET)"
	@df -h | head -1 && df -h | grep -E "(docker|var)"

benchmarks: ## Run performance benchmarks
	@echo "$(BLUE)Running Performance Benchmarks$(RESET)"
	@echo "$(YELLOW)Kafka Topic Throughput:$(RESET)"
	@docker exec kafka kafka-producer-perf-test.sh \
		--topic raw_iot_data \
		--num-records 1000 \
		--record-size 100 \
		--throughput 100 \
		--producer-props bootstrap.servers=localhost:9092
	@echo ""
	@echo "$(YELLOW)TimescaleDB Connection Test:$(RESET)"
	@docker exec timescale-db psql -U ts_user -d timeseries -c "SELECT COUNT(*) as total_records FROM iot_measurements;"

# Security Operations
security-check: ## Check security configuration
	@echo "$(BLUE)Security Configuration Check$(RESET)"
	@echo "$(YELLOW)Checking secrets...$(RESET)"
	@if [ -d "secrets" ]; then \
		echo "$(GREEN)✅ Secrets directory exists$(RESET)"; \
		ls -la secrets/ | grep -E "\.(txt)$$" | wc -l | xargs echo "  Secret files:"; \
	else \
		echo "$(RED)❌ Secrets directory missing$(RESET)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Checking MQTT authentication...$(RESET)"
	@if [ -f "mosquitto/passwd" ]; then \
		echo "$(GREEN)✅ MQTT password file exists$(RESET)"; \
	else \
		echo "$(RED)❌ MQTT password file missing$(RESET)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Checking container users...$(RESET)"
	@docker exec data-processor whoami | xargs echo "  Data Processor runs as:"
	@docker exec kafka-timescale-sink whoami | xargs echo "  TimescaleDB Sink runs as:"

# Cleanup Commands
clean: ## Stop and remove all containers
	@echo "$(BLUE)Stopping MQTT Architecture POC$(RESET)"
	@echo "$(YELLOW)Stopping monitoring stack...$(RESET)"
	@docker-compose -f monitoring/docker-compose.monitoring.yml down 2>/dev/null || true
	@echo "$(YELLOW)Stopping core services...$(RESET)"
	@docker-compose down
	@docker-compose -f docker-compose.secrets.yml down 2>/dev/null || true
	@echo "$(GREEN)✅ All services stopped$(RESET)"

clean-data: ## Stop containers and remove all data (WARNING: Destructive)
	@echo "$(RED)⚠️  WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo ""; \
		echo "$(YELLOW)Removing all data...$(RESET)"; \
		docker-compose -f monitoring/docker-compose.monitoring.yml down -v 2>/dev/null || true; \
		docker-compose down -v; \
		docker-compose -f docker-compose.secrets.yml down -v 2>/dev/null || true; \
		echo "$(GREEN)✅ All data removed$(RESET)"; \
	else \
		echo ""; \
		echo "$(GREEN)Operation cancelled$(RESET)"; \
	fi

restart: ## Restart all services
	@echo "$(BLUE)Restarting MQTT Architecture POC$(RESET)"
	$(MAKE) clean
	@sleep 5
	$(MAKE) full-setup

restart-secure: ## Restart all services in secure mode
	@echo "$(BLUE)Restarting MQTT Architecture POC (Secure Mode)$(RESET)"
	$(MAKE) clean
	@sleep 5
	$(MAKE) secure-setup

# Development Helpers
dev-setup: ## Setup development environment with hot reload
	@echo "$(BLUE)Setting up development environment$(RESET)"
	$(MAKE) setup
	@echo "$(GREEN)✅ Development environment ready$(RESET)"
	@echo ""
	@echo "$(YELLOW)Development Tips:$(RESET)"
	@echo "  • Use 'make logs-[service]' to monitor specific services"
	@echo "  • Restart individual services: docker-compose restart [service]"
	@echo "  • Rebuild after code changes: docker-compose build [service]"

build: ## Build all Docker images
	@echo "$(BLUE)Building Docker images$(RESET)"
	docker-compose build
	docker-compose -f docker-compose.secrets.yml build

update: ## Pull latest images and rebuild
	@echo "$(BLUE)Updating Docker images$(RESET)"
	docker-compose pull
	docker-compose -f docker-compose.secrets.yml pull
	$(MAKE) build

# Documentation
docs: ## Open documentation in browser
	@echo "$(BLUE)Opening documentation$(RESET)"
	@if command -v xdg-open > /dev/null; then \
		xdg-open docs/; \
	elif command -v open > /dev/null; then \
		open docs/; \
	else \
		echo "$(YELLOW)Documentation available in: docs/$(RESET)"; \
	fi

# Backup and Restore
backup: ## Create backup of databases
	@echo "$(BLUE)Creating database backups$(RESET)"
	@mkdir -p backups
	@echo "$(YELLOW)Backing up PostgreSQL...$(RESET)"
	@docker exec device-params-db pg_dump -U iot_user device_params > backups/postgres_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(YELLOW)Backing up TimescaleDB...$(RESET)"
	@docker exec timescale-db pg_dump -U ts_user timeseries > backups/timescale_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Backups created in backups/ directory$(RESET)"

# Environment info
info: ## Show environment information
	@echo "$(BLUE)Environment Information$(RESET)"
	@echo "$(YELLOW)Docker:$(RESET)"
	@docker --version
	@docker-compose --version
	@echo ""
	@echo "$(YELLOW)System:$(RESET)"
	@echo "  OS: $$(uname -s)"
	@echo "  Arch: $$(uname -m)"
	@echo "  Available Memory: $$(free -h | awk '/^Mem:/ {print $$2}' 2>/dev/null || echo 'N/A')"
	@echo "  Available Disk: $$(df -h . | awk 'NR==2 {print $$4}' 2>/dev/null || echo 'N/A')"
	@echo ""
	@echo "$(YELLOW)Project:$(RESET)"
	@echo "  Directory: $$(pwd)"
	@echo "  Git Branch: $$(git branch --show-current 2>/dev/null || echo 'N/A')"
	@echo "  Git Commit: $$(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"