"""
Shared data models for the IoT Architecture PoC

This module contains Pydantic models used across multiple services
to ensure consistent data validation and transformation.

Models:
- DecodedData: Optimized TimescaleDB storage (4 columns: timestamp, device_id, datapoint_id, value)
- DeviceLookup: MAC address to device_id mapping
- DataPointLookup: Sensor label to datapoint_id mapping
- Certificate models: For certificate generation API
"""

import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class DecodedData(BaseModel):
    """
    Optimized Pydantic model for decoded IoT data storage.
    
    This model represents the space-optimized structure for TimescaleDB storage
    using integer IDs instead of strings for better performance and reduced storage.
    
    Attributes:
        timestamp: When the measurement was taken
        deviceid: Integer ID mapped from MAC address via PostgreSQL lookup
        datapointid: Integer ID mapped from datapoint label via PostgreSQL lookup
        value: Numeric measurement value
    """
    timestamp: datetime
    deviceid: int
    datapointid: int
    value: Optional[float] = None
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def convert_timestamp(cls, v):
        """Convert various timestamp formats to datetime objects."""
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
    
    def dict_for_timescale(self):
        """Return a dictionary representation suitable for TimescaleDB insertion."""
        return {
            'timestamp': self.timestamp,
            'deviceid': self.deviceid,
            'datapointid': self.datapointid,
            'value': self.value
        }
    
    class Config:
        """Pydantic configuration for the model."""
        from_attributes = True


class DeviceLookup(BaseModel):
    """
    Model for device lookup operations.
    
    Used for mapping MAC addresses to device IDs in the PostgreSQL metadata database.
    
    Attributes:
        macaddress: MAC address of the device
        deviceid: Integer ID of the device
        devicename: Human-readable name of the device
    """
    macaddress: str
    deviceid: int
    devicename: str
    
    class Config:
        """Pydantic configuration for the model."""
        from_attributes = True


class DataPointLookup(BaseModel):
    """
    Model for datapoint lookup operations.
    
    Used for mapping datapoint labels to datapoint IDs in the PostgreSQL metadata database.
    
    Attributes:
        datapointid: Integer ID of the datapoint
        label: Human-readable label of the datapoint
        devicetemplateid: ID of the device template this datapoint belongs to
    """
    datapointid: int
    label: str
    devicetemplateid: int
    
    class Config:
        """Pydantic configuration for the model."""
        from_attributes = True


class CertificateResponse(BaseModel):
    """
    Response model for certificate issuance endpoint.
    
    This model structures the response from the certificate generation service,
    providing all necessary certificate data for F2 controller provisioning.
    
    Attributes:
        mac: MAC address of the device
        client_cert: PEM-encoded client certificate
        private_key: PEM-encoded private key
        ca_cert: PEM-encoded CA certificate
        expires_at: Certificate expiration timestamp in ISO format
    """
    mac: str = Field(..., description="MAC address of the device")
    client_cert: str = Field(..., description="PEM-encoded client certificate")
    private_key: str = Field(..., description="PEM-encoded private key")
    ca_cert: str = Field(..., description="CA certificate")
    expires_at: str = Field(..., description="Certificate expiration timestamp in ISO format")


class CertificateRequest(BaseModel):
    """
    Request model for certificate issuance endpoint.
    
    This model validates the request body for certificate generation,
    ensuring proper MAC address format for F2 controller provisioning.
    
    Attributes:
        mac: MAC address of the device requesting certificate
    """
    mac: str = Field(..., description="MAC address of the device requesting certificate")