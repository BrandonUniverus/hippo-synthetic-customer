using System.IO.BACnet;
using System.IO.BACnet.Serialize;
using System.Text.Json;
using EEMSuite.Tasks.Gateways.Bacnet;
using Northlake.Bacnet;

if (args.Length is < 3 or > 4) throw new ArgumentException("Usage: Probe <bindings.json> <values.json> <Workers-local-IPv4> [--expect-stale]");
bool expectStale = args.Length == 4 && args[3] == "--expect-stale";
if (args.Length == 4 && !expectStale) throw new ArgumentException("Unknown probe option");
SourceConfig config = SourceConfig.Load(args[0]);
ValueSnapshot expected = JsonSerializer.Deserialize<ValueSnapshot>(File.ReadAllText(args[1]), SourceConfig.JsonOptions) ?? throw new InvalidDataException("No expected values");
var factory = new SystemIoBacnetClientFactory();
int count = 0;
foreach (DeviceConfig device in config.Devices)
{
    using IBacnetClient client = await factory.CreateAsync(args[2], config.BroadcastPort, 1, 0, 7000, 7000);
    if (expectStale)
    {
        ObjectConfig first = device.Objects[0];
        await ExpectError(() => client.ReadPresentValueAsync(device.DeviceId, (BacnetGatewayObjectKindCode)first.ObjectType, first.ObjectId, null, 2000), "ERROR_CLASS_DEVICE - ERROR_CODE_OTHER");
        continue;
    }
    foreach (ObjectConfig point in device.Objects)
    {
        double value = await client.ReadPresentValueAsync(device.DeviceId, (BacnetGatewayObjectKindCode)point.ObjectType, point.ObjectId, null, 7000);
        double required = (float)expected.Values[point.ValueKey].Value;
        if (value != required) throw new InvalidDataException($"{device.DeviceId}/{point.ObjectId}: expected {required}, got {value}");
        count++;
        Console.WriteLine(JsonSerializer.Serialize(new { device.DeviceId, point.ObjectId, point.ObjectType, point.Channel, value, passed = true }));
    }
    await ExpectError(() => client.WritePresentValueAsync(device.DeviceId, BacnetGatewayObjectKindCode.AnalogValue, device.Objects[0].ObjectId, null, 123, 16, 2000), "ERROR_CLASS_PROPERTY - ERROR_CODE_WRITE_ACCESS_DENIED");
    await ExpectError(() => client.ReadPresentValueAsync(device.DeviceId, BacnetGatewayObjectKindCode.AnalogValue, 4194302, null, 2000), "ERROR_CLASS_OBJECT - ERROR_CODE_UNKNOWN_OBJECT");
    await ExpectError(() => client.ReadPresentValueAsync(device.DeviceId, (BacnetGatewayObjectKindCode)device.Objects[0].ObjectType, device.Objects[0].ObjectId, 0, 2000), "ERROR_CLASS_PROPERTY - ERROR_CODE_INVALID_ARRAY_INDEX");
}
// Status properties and ReadPropertyMultiple, read with the BACnet library itself. EnergyHippo's collector reads
// only Present_Value today, so these checks prepare for that change rather than prove the collector.
int statusCount = 0;
if (!expectStale)
{
    var transport = new BacnetIpUdpProtocolTransport(47830, useExclusivePort: true, dontFragment: false, maxPayload: 1472, localEndpointIp: args[2]);
    using var raw = new System.IO.BACnet.BacnetClient(transport);
    raw.Start();
    foreach (DeviceConfig device in config.Devices)
    {
        var address = new BacnetAddress(BacnetAddressTypes.IP, $"{args[2]}:{device.UnicastPort}", 0);
        var deviceId = new BacnetObjectId(BacnetObjectTypes.OBJECT_DEVICE, device.DeviceId);
        var services = (BacnetBitString)(await Read(raw, address, deviceId, BacnetPropertyIds.PROP_PROTOCOL_SERVICES_SUPPORTED)).Value;
        if (services.GetBit((byte)BacnetServicesSupported.SERVICE_SUPPORTED_READ_PROP_MULTIPLE) != device.ReadPropertyMultiple)
            throw new InvalidDataException($"{device.DeviceId}: Protocol_Services_Supported disagrees with ReadPropertyMultiple={device.ReadPropertyMultiple}");
        foreach (ObjectConfig point in device.Objects)
        {
            SourceStatus status = expected.Values[point.ValueKey].Status ?? throw new InvalidDataException($"{point.ValueKey}: the snapshot has no status");
            var id = new BacnetObjectId((BacnetObjectTypes)point.ObjectType, point.ObjectId);
            string flags = ((BacnetBitString)(await Read(raw, address, id, BacnetPropertyIds.PROP_STATUS_FLAGS)).Value).ToString();
            var eventState = (uint)(await Read(raw, address, id, BacnetPropertyIds.PROP_EVENT_STATE)).Value;
            var outOfService = (bool)(await Read(raw, address, id, BacnetPropertyIds.PROP_OUT_OF_SERVICE)).Value;
            var reliability = (uint)(await Read(raw, address, id, BacnetPropertyIds.PROP_RELIABILITY)).Value;
            if (flags != status.StatusFlags.ToString() || eventState != (uint)status.EventStateCode || outOfService != status.OutOfService || reliability != (uint)status.ReliabilityCode)
                throw new InvalidDataException($"{device.DeviceId}/{point.ObjectId}: status {flags}/{eventState}/{outOfService}/{reliability} does not match the snapshot");
            statusCount++;
            Console.WriteLine(JsonSerializer.Serialize(new { device.DeviceId, point.ObjectId, statusFlags = flags, status.EventState, status.OutOfService, status.Reliability, status.Scenario, passed = true }));
        }
        List<BacnetReadAccessSpecification> request = device.Objects.Select(o => new BacnetReadAccessSpecification(
            new BacnetObjectId((BacnetObjectTypes)o.ObjectType, o.ObjectId),
            [new BacnetPropertyReference((uint)BacnetPropertyIds.PROP_PRESENT_VALUE, ASN1.BACNET_ARRAY_ALL), new BacnetPropertyReference((uint)BacnetPropertyIds.PROP_STATUS_FLAGS, ASN1.BACNET_ARRAY_ALL)])).ToList();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(7));
        if (device.ReadPropertyMultiple)
        {
            IList<BacnetReadAccessResult> results = await raw.ReadPropertyMultipleAsync(address, request, invokeId: 0, cancellationToken: timeout.Token);
            foreach (BacnetReadAccessResult result in results)
            {
                ObjectConfig point = device.Objects.Single(o => (uint)o.ObjectType == (uint)result.objectIdentifier.Type && o.ObjectId == result.objectIdentifier.Instance);
                SourceValue source = expected.Values[point.ValueKey];
                float value = (float)result.values.Single(v => v.property.propertyIdentifier == (uint)BacnetPropertyIds.PROP_PRESENT_VALUE).value[0].Value;
                string flags = ((BacnetBitString)result.values.Single(v => v.property.propertyIdentifier == (uint)BacnetPropertyIds.PROP_STATUS_FLAGS).value[0].Value).ToString();
                if (value != (float)source.Value || flags != source.Status!.StatusFlags.ToString())
                    throw new InvalidDataException($"{device.DeviceId}/{point.ObjectId}: ReadPropertyMultiple returned {value}/{flags}");
            }
            Console.WriteLine(JsonSerializer.Serialize(new { device.DeviceId, readPropertyMultiple = true, objects = results.Count, passed = true }));
        }
        else
        {
            try
            {
                await raw.ReadPropertyMultipleAsync(address, request, invokeId: 0, cancellationToken: timeout.Token);
            }
            catch (Exception error) when (error.Message.Contains("reject", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine(JsonSerializer.Serialize(new { device.DeviceId, readPropertyMultiple = false, rejected = error.Message, passed = true }));
                continue;
            }
            throw new InvalidDataException($"{device.DeviceId}: ReadPropertyMultiple should be rejected by a device without the service");
        }
    }
}
Console.WriteLine(JsonSerializer.Serialize(new { passed = true, actualCollectorClient = true, deviceCount = config.Devices.Length, readCount = count, statusCount, expectStale, localIpAddress = args[2] }));

static async Task<BacnetValue> Read(System.IO.BACnet.BacnetClient client, BacnetAddress address, BacnetObjectId id, BacnetPropertyIds property)
{
    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(7));
    IList<BacnetValue> values = await client.ReadPropertyAsync(address, id, property, invokeId: 0, arrayIndex: ASN1.BACNET_ARRAY_ALL, cancellationToken: timeout.Token);
    return values.Single();
}

static async Task ExpectError(Func<Task> operation, string code)
{
    try { await operation(); }
    // BACnet 4.0.0 exposes protocol errors as System.Exception with this error class/code.
    catch (Exception error) when (error.Message == "Error from device: " + code)
    {
        Console.WriteLine(JsonSerializer.Serialize(new { expectedProtocolError = code, passed = true }));
        return;
    }
    throw new InvalidDataException("Expected BACnet error: " + code);
}
