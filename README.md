# MQTT Architecture POC

> A secure, production-ready IoT data pipeline using MQTT, Kafka, and TimescaleDB

[![Docker](https://img.shields.io/badge/Docker-20.10+-blue.svg)](https://docs.docker.com/install/)
[![Security](https://img.shields.io/badge/Security-mTLS%20%2B%20Auth-green.svg)](https://docs.docker.com/install/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2.0+-orange.svg)](https://docs.timescale.com/)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-2.8+-red.svg)](https://kafka.apache.org/)

## Overview

This system ingests, processes, and stores IoT data from F2 Smart Controller devices, transforming raw MQTT messages into structured time-series data for analytics and monitoring. All services run with security-first approach including mTLS authentication, non-root containers, and comprehensive access controls.

**Key Features:**
- 🔒 **Security First**: mTLS authentication, ACL-based authorization, non-root containers
- ⚡ **High Performance**: Optimized batching, connection pooling, Redis caching
- 📊 **Real-time Processing**: Stream processing with Kafka and TimescaleDB
- 🐛 **Developer Friendly**: Comprehensive logging, health checks, easy debugging
- 📈 **Production Ready**: Monitoring, metrics, horizontal scaling support


### Setup
```bash
docker-compose up -d
```

## Secure Architecture with Performance Optimization

```mermaid
graph TB
    subgraph "MQTT Network"
        CA_API[Certificate Generation API]
        FACES2[FACES2 Smart Controllers]
        MQTT_BROKER[MQTT Broker]
        KAFKA_CONNECTOR[MQTT-Kafka Connector]
    end
    
    subgraph "Stream Processing"
        KAFKA[Apache Kafka]
        PROCESSOR[Processor]
        TIMESCALEDB_SINK[Kafka-TimescaleDB Sink<br/> 10x Larger Batches]
    end
    
    subgraph "Data Storage"
        PostgreSQL[PostgreSQL]
        REDIS[Redis Cache]
        TIMESCALEDB[TimescaleDB]
    end

    FACES2 -->|🔐 mTLS Authenticated MQTT| MQTT_BROKER
    MQTT_BROKER --> KAFKA_CONNECTOR    
    KAFKA_CONNECTOR -->|Raw IoT Data Topic| KAFKA
    KAFKA --> |Raw Data|PROCESSOR
    PROCESSOR --> |Processed Data| KAFKA
    PROCESSOR -->|DataPoint params| PostgreSQL
    PROCESSOR <-->|Cache Lookups| REDIS
    KAFKA --> TIMESCALEDB_SINK --> |Batch Insert| TIMESCALEDB
    
```
