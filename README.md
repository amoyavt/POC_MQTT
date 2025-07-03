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

## Secure Architecture with Performance Optimization

```mermaid
graph TB
    subgraph "IoT Devices"
        A[F2 Smart Controllers<br/>🔐 MQTT Auth Required]
    end
    
    subgraph "Message Ingestion"
        B[MQTT Broker<br/>🔐 Port: 1883<br/>Auth Required]
        C[MQTT-Kafka Connector<br/>⚡ Optimized Batching]
    end
    
    subgraph "Stream Processing"
        D[Apache Kafka<br/>⚡ Port: 9092<br/>Enhanced Config]
        E[Data Processor<br/>🗄️ Redis Cache<br/>🔒 Input Validation]
        F[Kafka-TimescaleDB Sink<br/>⚡ 10x Larger Batches]
    end
    
    subgraph "Data Storage"
        G[(PostgreSQL<br/>🔒 Internal Only<br/>Connection Pool)]
        R[Redis Cache<br/>⚡ Device Parameters]
        H[(TimescaleDB<br/>🔒 Internal Only<br/>Compression)]
    end
    
    A -->|🔐 Authenticated MQTT| B
    B --> C
    C -->|Raw IoT Data Topic| D
    D --> E
    E <-->|⚡ Cached Lookups| R
    E -->|🔒 Secure Queries| G
    E -->|Decoded Data Topic| D
    D --> F
    F -->|⚡ Batch Insert| H
    
    class A,B,E,G,H security
    class C,D,F,R performance
```
