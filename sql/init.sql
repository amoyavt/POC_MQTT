-- Device Parameters Database Initialization

CREATE TABLE IF NOT EXISTS device_parameters (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    connector_mode VARCHAR(50) NOT NULL,
    component_type VARCHAR(50) NOT NULL,
    component_id VARCHAR(10),
    encoding_type VARCHAR(50) NOT NULL,
    units VARCHAR(20) NOT NULL,
    scaling_factor DECIMAL(10,4) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, connector_mode, component_type, component_id)
);

-- Insert sample device parameters based on the architecture document
INSERT INTO device_parameters (device_id, connector_mode, component_type, component_id, encoding_type, units, scaling_factor) VALUES
('f2-e4fd45f654be', 'access-control-mode', 'door-sensors', NULL, 'boolean_map', 'state', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'strike', '1', 'boolean', 'state', 1.0),
('f2-e4fd45f654be', 'sensor-mode', 'sensor', '3', 'hex_to_float', 'celsius', 0.1),
('f2-e4fd45f654be', 'alarm-mode', 'motion-sensor', '1', 'boolean', 'presence', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'reader', '1', 'raw_string', 'text', 1.0),
('f2-e4fd45f654be', 'access-control-mode', 'exit-buttons', NULL, 'boolean_map', 'state', 1.0),
('f2-e4fd45f654be', 'alarm-mode', 'siren', '1', 'boolean', 'state', 1.0),
('f2-abc123def456', 'sensor-mode', 'sensor', '1', 'hex_to_float', 'humidity', 0.01),
('f2-abc123def456', 'sensor-mode', 'sensor', '2', 'hex_to_float', 'pressure', 0.1),
('f2-abc123def456', 'access-control-mode', 'door-sensors', NULL, 'boolean_map', 'state', 1.0);

-- Create indexes for better query performance
CREATE INDEX idx_device_params_lookup ON device_parameters(device_id, connector_mode, component_type, component_id);

-- View to help with debugging
CREATE VIEW device_config_view AS 
SELECT 
    device_id,
    connector_mode,
    component_type,
    component_id,
    encoding_type,
    units,
    scaling_factor
FROM device_parameters
ORDER BY device_id, connector_mode, component_type, component_id;