"""
Shared data models for the IoT Architecture PoC

This module contains Pydantic models used across multiple services
to ensure consistent data validation and transformation.
"""

import re
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class IotMeasurement(BaseModel):
    """
    Pydantic model for an IoT measurement record.
    
    This model validates and transforms IoT sensor data from Kafka messages
    before insertion into TimescaleDB. It handles various data type conversions
    and provides sensible defaults for missing fields.
    
    Attributes:
        timestamp: When the measurement was taken
        device_id: Unique identifier for the device (maps from mac_address)
        connector_mode: Operating mode of the connector (e.g., 'sensor-mode')
        datapoint_label: Label of the DataPoint generating the data (e.g., 'Temperature')
        pin_position: Physical pin position on the device (as string)
        value: Numeric measurement value (extracted from strings with units)
        unit: Unit of measurement (e.g., '°C', 'V')
        topic: Original MQTT topic where the data was published
    """
    timestamp: datetime
    device_id: str = Field(..., alias='mac_address')
    connector_mode: str = Field('unknown', alias='mode')
    datapoint_label: str = Field('unknown', alias='data_point_label')
    pin_position: str = Field('-1', alias='pin')
    value: Optional[float] = None
    unit: str = ''
    topic: str = Field('', alias='original_topic')

    @validator('timestamp', pre=True)
    def convert_timestamp(cls, v):
        """
        Convert various timestamp formats to datetime objects.
        
        Handles:
        - Unix timestamps (int/float)
        - ISO format strings
        - Fallback to current time if conversion fails
        """
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return datetime.fromtimestamp(float(v))
                except (ValueError, TypeError):
                    pass
        return datetime.now()

    @validator('pin_position', pre=True)
    def convert_pin_to_string(cls, v):
        """
        Convert pin position from integer to string.
        
        Ensures consistency with database schema expectations.
        """
        return str(v)

    @validator('value', pre=True)
    def convert_value_to_float(cls, v):
        """
        Extract numeric values from various formats.
        
        Handles:
        - Direct numeric values (int/float)
        - Strings with units (e.g., "27.93 °C" -> 27.93)
        - Complex strings by extracting the first numeric part
        
        Returns None for values that cannot be converted.
        """
        if v is None:
            return None
        
        # If it's already a number, return it
        if isinstance(v, (int, float)):
            return float(v)
            
        # If it's a string, try to extract the numeric part
        if isinstance(v, str):
            # Extract numeric part (including negative and decimal numbers)
            match = re.match(r'^(-?\d+\.?\d*)', v.strip())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
        
        logger.warning(f"Could not convert value '{v}' to float, setting to None")
        return None
    
    def dict_for_kafka(self):
        """
        Return a dictionary representation suitable for Kafka JSON serialization.
        
        Converts datetime objects to ISO format strings and uses field aliases.
        """
        data = self.dict(by_alias=True)
        # Convert datetime to ISO string for JSON serialization
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data
            
    class Config:
        """Pydantic configuration for the model."""
        orm_mode = True
        # Allow population by field name or alias
        allow_population_by_field_name = True
