
-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS "${DEVICE_SCHEMA}";

-- Set search path to use the schema
SET search_path TO "${DEVICE_SCHEMA}";

-- Drop existing tables if they exist to ensure a clean slate
DROP TABLE IF EXISTS pins, connectors, devices, devicetemplates, datapoints, devicetypes, datapointicons CASCADE;

-- Create devicetypes table
CREATE TABLE IF NOT EXISTS devicetypes (
    devicetypeid SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

-- Create devicetemplates table
CREATE TABLE IF NOT EXISTS devicetemplates (
    devicetemplateid SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    model VARCHAR(255) NOT NULL,
    description TEXT,
    image BYTEA,
    devicetypeid INT NOT NULL,
    FOREIGN KEY (devicetypeid) REFERENCES devicetypes(devicetypeid)
);

-- Create devices table
CREATE TABLE IF NOT EXISTS devices (
    deviceid SERIAL PRIMARY KEY,
    devicename VARCHAR(255) NOT NULL,
    devicetemplateid INT NOT NULL,
    claimingcode VARCHAR(255) NOT NULL,
    serialnumber VARCHAR(255),
    uuid VARCHAR(255),
    macaddress VARCHAR(255),
    ipaddress VARCHAR(255),
    pcbversion VARCHAR(255),
    FOREIGN KEY (devicetemplateid) REFERENCES devicetemplates(devicetemplateid)
);

-- Create connectors table
CREATE TABLE IF NOT EXISTS connectors (
    connectorid SERIAL PRIMARY KEY,
    controllerid INT NOT NULL,
    connectornumber INT NOT NULL CHECK (connectornumber >= 1 AND connectornumber <= 5),
    connectortypeid INT,
    FOREIGN KEY (controllerid) REFERENCES devices(deviceid)
);

-- Create pins table
CREATE TABLE IF NOT EXISTS pins (
    pinid SERIAL PRIMARY KEY,
    connectorid INT NOT NULL,
    position INT NOT NULL,
    deviceid INT NOT NULL,
    FOREIGN KEY (connectorid) REFERENCES connectors(connectorid),
    FOREIGN KEY (deviceid) REFERENCES devices(deviceid)
);

-- Create datapointicons table
CREATE TABLE IF NOT EXISTS datapointicons (
    datapointiconid SERIAL PRIMARY KEY,
    iconname VARCHAR(255) NOT NULL
);

-- Create datapoints table
CREATE TABLE IF NOT EXISTS datapoints (
    datapointid SERIAL PRIMARY KEY,
    devicetemplateid INT NOT NULL,
    label VARCHAR(255) NOT NULL,
    datapointiconid INT NOT NULL,
    dataformat VARCHAR(50) NOT NULL,
    dataencoding VARCHAR(50),
    offset INT NOT NULL,
    length INT NOT NULL,
    prepend VARCHAR(50) DEFAULT '',
    append VARCHAR(50) DEFAULT '',
    wholenumber INT DEFAULT 0,
    decimals INT DEFAULT 0,
    realtimechart VARCHAR(50),
    historicalchart VARCHAR(50),
    FOREIGN KEY (devicetemplateid) REFERENCES devicetemplates(devicetemplateid),
    FOREIGN KEY (datapointiconid) REFERENCES datapointicons(datapointiconid)
);

-- Insert sample data to match the simulation and processing logic
-- Device Templates
INSERT INTO "VtDevice".devicetemplates (name, model, description, devicetypeid) VALUES 
('Environmental Sensor', 'ENV-S1', 'Environmental Sensor for Temp, Humidity, and CO2', 2),
('Power Monitor', 'PM-100', 'Power Monitoring Unit for Voltage and Current', 3);

-- Devices (Controllers and Sensors)
-- Controllers (MAC addresses without f2- prefix for database storage)
INSERT INTO "VtDevice".devices (devicename, devicetemplateid, claimingcode, macaddress) VALUES 
('F2 Controller 1', 1, 'claim-abc', 'aabbccddee01'),
('F2 Controller 2', 1, 'claim-def', 'aabbccddee02'),
('F2 Controller 3', 1, 'claim-ghi', 'aabbccddee03'),
('F2 Controller 4', 1, 'claim-jkl', 'aabbccddee04');

-- Sensors
INSERT INTO "VtDevice".devices (devicename, devicetemplateid, claimingcode) VALUES 
('Living Room Env Sensor', 2, 'claim-env1'),
('Kitchen Power Monitor', 3, 'claim-pm1'),
('Bedroom Env Sensor', 2, 'claim-env2');

-- Connectors for the Controllers (J1-J4 for each controller)
INSERT INTO "VtDevice".connectors (controllerid, connectornumber, connectortypeid) VALUES 
-- Controller 1 connectors
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee01'), 1, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee01'), 2, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee01'), 3, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee01'), 4, 3),
-- Controller 2 connectors
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee02'), 1, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee02'), 2, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee02'), 3, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee02'), 4, 3),
-- Controller 3 connectors
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee03'), 1, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee03'), 2, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee03'), 3, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee03'), 4, 3),
-- Controller 4 connectors
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee04'), 1, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee04'), 2, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee04'), 3, 3),
((SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee04'), 4, 3);

-- Pins: mapping sensors to controller connectors
INSERT INTO "VtDevice".pins (connectorid, position, deviceid) VALUES 
-- Controller 1, Connector 1, Pin 1 -> Living Room Env Sensor
((SELECT connectorid FROM "VtDevice".connectors WHERE controllerid = (SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee01') AND connectornumber = 1), 1, (SELECT deviceid FROM "VtDevice".devices WHERE devicename = 'Living Room Env Sensor')),
-- Controller 2, Connector 2, Pin 2 -> Kitchen Power Monitor
((SELECT connectorid FROM "VtDevice".connectors WHERE controllerid = (SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee02') AND connectornumber = 2), 2, (SELECT deviceid FROM "VtDevice".devices WHERE devicename = 'Kitchen Power Monitor')),
-- Controller 3, Connector 4, Pin 3 -> Bedroom Env Sensor
((SELECT connectorid FROM "VtDevice".connectors WHERE controllerid = (SELECT deviceid FROM "VtDevice".devices WHERE macaddress = 'aabbccddee03') AND connectornumber = 4), 3, (SELECT deviceid FROM "VtDevice".devices WHERE devicename = 'Bedroom Env Sensor'));

-- Data Points for the Sensor Templates
-- Environmental Sensor
INSERT INTO "VtDevice".datapoints (devicetemplateid, "label", datapointiconid, dataformat, dataencoding, "offset", length, decimals, prepend, append, realtimechart, historicalchart) VALUES
((SELECT devicetemplateid FROM "VtDevice".devicetemplates WHERE name = 'Environmental Sensor'), 'Temperature', 10, 0, 'Int16', 6, 2, 2, '', ' °C', 'gauge', 'line'),
((SELECT devicetemplateid FROM "VtDevice".devicetemplates WHERE name = 'Environmental Sensor'), 'Humidity', 5, 0, 'Uint16', 8, 2, 2, '', ' %', 'gauge', 'line'),
((SELECT devicetemplateid FROM "VtDevice".devicetemplates WHERE name = 'Environmental Sensor'), 'CO2', 3, 0, 'Uint16', 10, 2, 0, '',  ' ppm', 'gauge', 'line');

-- Power Monitor
INSERT INTO "VtDevice".datapoints (devicetemplateid, "label", datapointiconid, dataformat, dataencoding, "offset", length, decimals, prepend, append, realtimechart, historicalchart) VALUES
((SELECT devicetemplateid FROM "VtDevice".devicetemplates WHERE name = 'Power Monitor'), 'Voltage', 2, 0, 'Uint16', 0, 2, 1, '',  ' V',  'gauge', 'line'),
((SELECT devicetemplateid FROM "VtDevice".devicetemplates WHERE name = 'Power Monitor'), 'Current', 2, 0, 'Int16', 2, 2, 3,'',  ' A',  'gauge', 'line');

