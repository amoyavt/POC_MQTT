-- TimescaleDB Initialization for time-series data

-- Drop existing objects to ensure a clean slate
DROP MATERIALIZED VIEW IF EXISTS iot_hourly_stats;
DROP TABLE IF EXISTS iot_measurements;

-- Create extension for TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create the main time-series table
CREATE TABLE IF NOT EXISTS iot_measurements (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    connector_mode VARCHAR(50) NOT NULL,
    datapoint_label VARCHAR(50) NOT NULL,
    pin_position VARCHAR(10),
    value DOUBLE PRECISION,
    unit VARCHAR(20),
    topic VARCHAR(255),
    PRIMARY KEY (timestamp, device_id, connector_mode, datapoint_label, pin_position)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('iot_measurements', 'timestamp', if_not_exists => TRUE);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_iot_device_id ON iot_measurements (device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_iot_datapoint ON iot_measurements (datapoint_label, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_iot_mode ON iot_measurements (connector_mode, timestamp DESC);

-- Create a continuous aggregate for hourly data
CREATE MATERIALIZED VIEW IF NOT EXISTS iot_hourly_stats
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', timestamp) AS bucket,
    device_id,
    connector_mode,
    datapoint_label,
    pin_position,
    unit,
    topic,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    COUNT(*) as measurement_count
FROM iot_measurements
GROUP BY bucket, device_id, connector_mode, datapoint_label, pin_position, unit, topic
WITH NO DATA;

-- Create retention policy (optional - keep raw data for 30 days)
-- SELECT add_retention_policy('iot_measurements', INTERVAL '30 days');

-- Create compression policy (optional - compress data older than 7 days)
-- ALTER TABLE iot_measurements SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'device_id'
-- );
-- SELECT add_compression_policy('iot_measurements', INTERVAL '7 days');