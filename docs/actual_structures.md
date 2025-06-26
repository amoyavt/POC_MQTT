# A deep dive in sensor data messages in mqtt topics

The DB has devices. Devices can work as controller or devices that can connnect to controllers.
Each device is created from a deviceTemplate. 
Each deviceTemplate has datapoints that helps to decoded the raw data.

public class Device
{
    public int DeviceId { get; set; }
    public string DeviceName { get; set; } = null!;
    public int DeviceTemplateId { get; set; }
    public virtual DeviceTemplate DeviceTemplate { get; set; } = null!;
    public string ClaimingCode { get; set; } = null!;
    public string? SerialNumber { get; set; } = null!;
    public string? Uuid { get; set; } = null!;
    public string? MacAddress { get; set; } = null!;
    public string? IpAddress { get; set; } = null!; // only for controller
    public string? PcbVersion { get; set; } // only for controller
    public virtual IEnumerable<DeviceConnectivity> DeviceConnectivities { get; set; } = null!; // only for controller
    public virtual DeviceClaim ClaimDevice { get; set; } = null!;
}
public class DeviceTemplate
{
    public int DeviceTemplateId { get; set; }
    public string Name { get; set; } = null!;
    public string Model { get; set; } = null!;
    public string Description { get; set; } = null!;
    public byte[]? Image { get; set; }
    public int DeviceTypeId { get; set; }
    public virtual DeviceType DeviceType { get; set; } = null!;
    public virtual IEnumerable<DeviceTemplateCommunication> Communications { get; set; } = null!;
    public virtual IEnumerable<DeviceTemplateAuthentication> Authentications { get; set; } = null!;
    public virtual IEnumerable<DeviceTemplatePower> Powers { get; set; } = null!;
    public virtual IEnumerable<DataPoint> DataPoints { get; set; } = null!;        
}
public class DataPoint
{
    public int DataPointId { get; set; }
    public int DeviceTemplateId { get; set; }
    public virtual DeviceTemplate DeviceTemplate { get; set; } = null!;
    public string Label { get; set; } = null!;
    public int DataPointIconId { get; set; }
    public virtual DataPointIcon DataPointIcon { get; set; } = null!;
    public DeviceManagementConstants.DataFormat DataFormat { get; set; }
    public DeviceManagementConstants.DataEncoding DataEncoding { get; set; }
    public int Offset { get; set; }
    public int Length { get; set; }
    public string Prepend { get; set; } = string.Empty;
    public string Append { get; set; } = string.Empty;
    public int WholeNumber { get; set; } = 0;
    public int Decimals { get; set; } = 0;
    public DeviceManagementConstants.ChartType RealTimeChart { get; set; }
    public DeviceManagementConstants.ChartType HistoricalChart { get; set; }
}

the mqtt topics has the MacAddress, that is unique. With the MAC Address we can get the deviceId.

A controller is a device and has connectors.
Each connector has pins. 
Each pin has a device connected that has different funtionality. Here we will focus on the type of serial sensors 

public class Connector
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int ConnectorId { get; set; }
    public int ControllerId { get; set; }
    public virtual Device Controller { get; set; } = null!;
    [Range(1, 5)]
    public int ConnectorNumber { get; set; }
    public int ConnectorTypeId { get; set; }
    public virtual ConnectorType ConnectorType { get; set; } = null!;
    public virtual IEnumerable<Pin> Pins { get; set; } = null!;
}
public class Pin
{
    [Key]
    [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
    public int PinId { get; set; }
    public int ConnectorId { get; set; }
    public virtual Connector Connector { get; set; } = null!;
    public int Position { get; set; }
    public int DeviceId { get; set; }
    public virtual Device Device { get; set; } = null!;
}


The message that the MQTT broker will get is
```
cmnd/f2-<MAC_ADDR>/<MODE>/<CONNECTOR>/sensor-<N>
``` 
with json payload
{ 
  "timestamp": "2023-05-25 15:13:10.543400", 
  "data": <hex value> 
}
where <hex value> is a string with a big HEX number like "01 03 0C 32 30 32 30 36 32 38 30 31 30 31 5B 18 28 01"

<MAC_ADDR> provides the MAC address of the controller.
<CONNECTOR> provide the ConnectorNumber
<N> is the pin Position. Where we have an unique device connected. 
The device belongs to an unique device template.
The devicetemplate has several datapoints.

We use the list of datapoints for generate decoded data. One decode record from each encoded data.
The datapoint has info that we can use to extract a HEX number using Offset and Lenght (in bytes)
That number can be decoded with the DataFormat in the datapoint. It could be 'Int16' or 'Uint16'.
Finally that number is stored in with format of decoded_iot_data (in value column).