
-- Drop existing tables if they exist to ensure a clean slate
DROP TABLE IF EXISTS "Pin", "Connector", "Device", "DeviceTemplate", "DataPoint", "DeviceType", "DataPointIcon", "DeviceTemplateCommunication", "DeviceTemplateAuthentication", "DeviceTemplatePower", "DeviceClaim" CASCADE;

-- Create DeviceType table
CREATE TABLE "DeviceType" (
    "DeviceTypeId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(255) NOT NULL
);

-- Create DeviceTemplate table
CREATE TABLE "DeviceTemplate" (
    "DeviceTemplateId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(255) NOT NULL,
    "Model" VARCHAR(255) NOT NULL,
    "Description" TEXT,
    "Image" BYTEA,
    "DeviceTypeId" INT NOT NULL,
    FOREIGN KEY ("DeviceTypeId") REFERENCES "DeviceType"("DeviceTypeId")
);

-- Create Device table
CREATE TABLE "Device" (
    "DeviceId" SERIAL PRIMARY KEY,
    "DeviceName" VARCHAR(255) NOT NULL,
    "DeviceTemplateId" INT NOT NULL,
    "ClaimingCode" VARCHAR(255) NOT NULL,
    "SerialNumber" VARCHAR(255),
    "Uuid" VARCHAR(255),
    "MacAddress" VARCHAR(255),
    "IpAddress" VARCHAR(255),
    "PcbVersion" VARCHAR(255),
    FOREIGN KEY ("DeviceTemplateId") REFERENCES "DeviceTemplate"("DeviceTemplateId")
);

-- Create Connector table
CREATE TABLE "Connector" (
    "ConnectorId" SERIAL PRIMARY KEY,
    "ControllerId" INT NOT NULL,
    "ConnectorNumber" INT NOT NULL CHECK ("ConnectorNumber" >= 1 AND "ConnectorNumber" <= 5),
    "ConnectorTypeId" INT, -- Assuming ConnectorType table would exist in a full schema
    FOREIGN KEY ("ControllerId") REFERENCES "Device"("DeviceId")
);

-- Create Pin table
CREATE TABLE "Pin" (
    "PinId" SERIAL PRIMARY KEY,
    "ConnectorId" INT NOT NULL,
    "Position" INT NOT NULL,
    "DeviceId" INT NOT NULL,
    FOREIGN KEY ("ConnectorId") REFERENCES "Connector"("ConnectorId"),
    FOREIGN KEY ("DeviceId") REFERENCES "Device"("DeviceId")
);

-- Create DataPointIcon table
CREATE TABLE "DataPointIcon" (
    "DataPointIconId" SERIAL PRIMARY KEY,
    "IconName" VARCHAR(255) NOT NULL
);

-- Create DataPoint table
CREATE TABLE "DataPoint" (
    "DataPointId" SERIAL PRIMARY KEY,
    "DeviceTemplateId" INT NOT NULL,
    "Label" VARCHAR(255) NOT NULL,
    "DataPointIconId" INT NOT NULL,
    "DataFormat" VARCHAR(50) NOT NULL, -- e.g., 'Int16', 'Uint16'
    "DataEncoding" VARCHAR(50),
    "Offset" INT NOT NULL,
    "Length" INT NOT NULL,
    "Prepend" VARCHAR(50) DEFAULT '',
    "Append" VARCHAR(50) DEFAULT '',
    "WholeNumber" INT DEFAULT 0,
    "Decimals" INT DEFAULT 0,
    "RealTimeChart" VARCHAR(50),
    "HistoricalChart" VARCHAR(50),
    FOREIGN KEY ("DeviceTemplateId") REFERENCES "DeviceTemplate"("DeviceTemplateId"),
    FOREIGN KEY ("DataPointIconId") REFERENCES "DataPointIcon"("DataPointIconId")
);

-- Insert sample data to match the simulation and processing logic

-- Device Types
INSERT INTO "DeviceType" ("Name") VALUES ('Controller'), ('Sensor'), ('Power Monitor');

-- Data Point Icons
INSERT INTO "DataPointIcon" ("IconName") VALUES ('Temperature'), ('Humidity'), ('Pressure'), ('Voltage'), ('Current'), ('CO2');

-- Device Templates
INSERT INTO "DeviceTemplate" ("Name", "Model", "Description", "DeviceTypeId") VALUES 
('F2 Controller', 'F2-rev1', 'Main controller board', 1),
('Environmental Sensor', 'ENV-S1', 'Environmental Sensor for Temp, Humidity, and CO2', 2),
('Power Monitor', 'PM-100', 'Power Monitoring Unit for Voltage and Current', 3);

-- Devices (Controllers and Sensors)
-- Controllers
INSERT INTO "Device" ("DeviceName", "DeviceTemplateId", "ClaimingCode", "MacAddress") VALUES 
('F2 Controller 1', 1, 'claim-abc', 'e4fd45f654be'),
('F2 Controller 2', 1, 'claim-def', 'abc123def456'),
('F2 Controller 3', 1, 'claim-ghi', '123456abcdef');

-- Sensors
INSERT INTO "Device" ("DeviceName", "DeviceTemplateId", "ClaimingCode") VALUES 
('Living Room Env Sensor', 2, 'claim-env1'),
('Kitchen Power Monitor', 3, 'claim-pm1'),
('Bedroom Env Sensor', 2, 'claim-env2');

-- Connectors for the Controllers
INSERT INTO "Connector" ("ControllerId", "ConnectorNumber") VALUES 
((SELECT "DeviceId" FROM "Device" WHERE "MacAddress" = 'e4fd45f654be'), 1),
((SELECT "DeviceId" FROM "Device" WHERE "MacAddress" = 'abc123def456'), 2),
((SELECT "DeviceId" FROM "Device" WHERE "MacAddress" = '123456abcdef'), 4);

-- Pins: mapping sensors to controller connectors
INSERT INTO "Pin" ("ConnectorId", "Position", "DeviceId") VALUES 
-- Controller 1, Connector 1, Pin 1 -> Living Room Env Sensor
((SELECT "ConnectorId" FROM "Connector" WHERE "ControllerId" = (SELECT "DeviceId" FROM "Device" WHERE "MacAddress" = 'e4fd45f654be') AND "ConnectorNumber" = 1), 1, (SELECT "DeviceId" FROM "Device" WHERE "DeviceName" = 'Living Room Env Sensor')),
-- Controller 2, Connector 2, Pin 2 -> Kitchen Power Monitor
((SELECT "ConnectorId" FROM "Connector" WHERE "ControllerId" = (SELECT "DeviceId" FROM "Device" WHERE "MacAddress" = 'abc123def456') AND "ConnectorNumber" = 2), 2, (SELECT "DeviceId" FROM "Device" WHERE "DeviceName" = 'Kitchen Power Monitor')),
-- Controller 3, Connector 4, Pin 3 -> Bedroom Env Sensor
((SELECT "ConnectorId" FROM "Connector" WHERE "ControllerId" = (SELECT "DeviceId" FROM "Device" WHERE "MacAddress" = '123456abcdef') AND "ConnectorNumber" = 4), 3, (SELECT "DeviceId" FROM "Device" WHERE "DeviceName" = 'Bedroom Env Sensor'));

-- Data Points for the Sensor Templates
-- Environmental Sensor
INSERT INTO "DataPoint" ("DeviceTemplateId", "Label", "DataPointIconId", "DataFormat", "DataEncoding", "Offset", "Length", "Decimals", "Append") VALUES
((SELECT "DeviceTemplateId" FROM "DeviceTemplate" WHERE "Name" = 'Environmental Sensor'), 'Temperature', 1, 'numeric', 'Int16', 0, 2, 2, ' °C'),
((SELECT "DeviceTemplateId" FROM "DeviceTemplate" WHERE "Name" = 'Environmental Sensor'), 'Humidity', 2, 'numeric', 'Uint16', 2, 2, 2, ' %'),
((SELECT "DeviceTemplateId" FROM "DeviceTemplate" WHERE "Name" = 'Environmental Sensor'), 'CO2', 6, 'numeric', 'Uint16', 4, 2, 0, ' ppm');

-- Power Monitor
INSERT INTO "DataPoint" ("DeviceTemplateId", "Label", "DataPointIconId", "DataFormat", "DataEncoding", "Offset", "Length", "Decimals", "Append") VALUES
((SELECT "DeviceTemplateId" FROM "DeviceTemplate" WHERE "Name" = 'Power Monitor'), 'Voltage', 4, 'numeric', 'Uint16', 0, 2, 1, ' V'),
((SELECT "DeviceTemplateId" FROM "DeviceTemplate" WHERE "Name" = 'Power Monitor'), 'Current', 5, 'numeric', 'Int16', 2, 2, 3, ' A');

