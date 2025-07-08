-- TimescaleDB Initialization for optimized time-series data storage
-- Space-optimized structure using integer IDs instead of strings

-- Drop existing objects to ensure a clean slate
DROP MATERIALIZED VIEW IF EXISTS iot_hourly_stats;
DROP TABLE IF EXISTS iot_measurements;
DROP TABLE IF EXISTS decoded_data;

-- Create extension for TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create the optimized time-series table (space-efficient structure)
CREATE TABLE IF NOT EXISTS decoded_data (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id INTEGER NOT NULL,
    datapoint_id INTEGER NOT NULL,
    value DOUBLE PRECISION,
    PRIMARY KEY (timestamp, device_id, datapoint_id)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('decoded_data', 'timestamp', if_not_exists => TRUE);

-- Create indexes for optimal query performance
CREATE INDEX IF NOT EXISTS idx_decoded_device_id ON decoded_data (device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decoded_datapoint_id ON decoded_data (datapoint_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decoded_device_datapoint ON decoded_data (device_id, datapoint_id, timestamp DESC);

-- Create a continuous aggregate for hourly statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS decoded_hourly_stats
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', timestamp) AS bucket,
    device_id,
    datapoint_id,
    AVG(value) as avg_value,
    MIN(value) as min_value,
    MAX(value) as max_value,
    COUNT(*) as measurement_count,
    STDDEV(value) as stddev_value
FROM decoded_data
GROUP BY bucket, device_id, datapoint_id
WITH NO DATA;

-- Create retention policy (optional - keep raw data for 90 days)
-- SELECT add_retention_policy('decoded_data', INTERVAL '90 days');

-- Create compression policy (optional - compress data older than 7 days)
-- Space optimization: compress by device_id for better compression ratio
-- ALTER TABLE decoded_data SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'device_id'
-- );
-- SELECT add_compression_policy('decoded_data', INTERVAL '7 days');

-- Enable automatic refresh for continuous aggregates
-- SELECT add_continuous_aggregate_policy('decoded_hourly_stats',
--     start_offset => INTERVAL '1 day',
--     end_offset => INTERVAL '1 hour',
--     schedule_interval => INTERVAL '1 hour');