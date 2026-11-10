using System.IO.BACnet;
using System.IO.BACnet.Serialize;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;

namespace Northlake.Bacnet;

internal static class Program
{
    private static async Task<int> Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.Error.WriteLine("Usage: Northlake.Bacnet <bindings.json> <state-directory> <local-IPv4> [--health]");
            return 2;
        }
        SourceConfig config = SourceConfig.Load(args[0]);
        string state = Path.GetFullPath(args[1]);
        if (!IPAddress.TryParse(args[2], out IPAddress? address) || address.AddressFamily != AddressFamily.InterNetwork) throw new ArgumentException("A local IPv4 address is required.");
        if (args.Contains("--health"))
        {
            using JsonDocument health = JsonDocument.Parse(File.ReadAllText(Path.Combine(state, "server-health.json")));
            DateTimeOffset heartbeat = health.RootElement.GetProperty("heartbeatAtUtc").GetDateTimeOffset();
            TimeSpan age = DateTimeOffset.UtcNow - heartbeat;
            bool ok = health.RootElement.GetProperty("sourceFresh").GetBoolean() && age >= TimeSpan.Zero && age < TimeSpan.FromSeconds(45);
            Console.WriteLine(health.RootElement.GetRawText());
            return ok ? 0 : 1;
        }
        Directory.CreateDirectory(state);
        using var serverLock = new FileStream(Path.Combine(state, "server.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        using var cancel = new CancellationTokenSource();
        Console.CancelKeyPress += (_, e) => { e.Cancel = true; cancel.Cancel(); };
        var devices = new List<SourceDevice>();
        try
        {
            foreach (DeviceConfig device in config.Devices) devices.Add(new SourceDevice(config, device, state, address.ToString()));
            while (!cancel.IsCancellationRequested)
            {
                bool fresh;
                try { fresh = LoadSnapshot(config, state) is not null; }
                catch (IOException) { fresh = false; }
                catch (JsonException) { fresh = false; }
                string path = Path.Combine(state, "server-health.json");
                string json = JsonSerializer.Serialize(new { heartbeatAtUtc = DateTimeOffset.UtcNow, sourceFresh = fresh, localIpAddress = address.ToString(), config.BroadcastPort, devices = devices.Select(d => d.Status).ToArray() });
                File.WriteAllText(path + ".partial", json);
                File.Move(path + ".partial", path, overwrite: true);
                await Task.Delay(TimeSpan.FromSeconds(10), cancel.Token);
            }
        }
        catch (OperationCanceledException) when (cancel.IsCancellationRequested) { }
        finally { foreach (SourceDevice device in devices) device.Dispose(); }
        return 0;
    }

    internal static ValueSnapshot? LoadSnapshot(SourceConfig config, string state)
    {
        ValueSnapshot? snapshot = JsonSerializer.Deserialize<ValueSnapshot>(File.ReadAllText(Path.Combine(state, "values.json")), SourceConfig.JsonOptions);
        if (snapshot is null || snapshot.Version != config.Version || snapshot.ConfigHash != config.Hash) return null;
        if (DateTimeOffset.UtcNow - snapshot.GeneratedAtUtc > TimeSpan.FromSeconds(120) || snapshot.GeneratedAtUtc > DateTimeOffset.UtcNow.AddSeconds(30)) return null;
        foreach (ObjectConfig point in config.Devices.SelectMany(d => d.Objects))
        {
            if (!snapshot.Values.TryGetValue(point.ValueKey, out SourceValue? value) || !float.IsFinite((float)value.Value)) return null;
            if (value.Status is not { IsConsistent: true }) return null;
            long intervalTicks = TimeSpan.FromMinutes(point.IntervalMinutes).Ticks;
            long closedAtTicks = snapshot.GeneratedAtUtc.UtcTicks / intervalTicks * intervalTicks;
            if (value.IntervalEndUtc.UtcTicks != closedAtTicks) return null;
        }
        return snapshot;
    }
}

internal sealed class SourceDevice : IDisposable
{
    // The properties each object answers. ReadPropertyMultiple's ALL returns all of them, REQUIRED all but Reliability.
    private static readonly BacnetPropertyIds[] _objectProperties =
    [
        BacnetPropertyIds.PROP_OBJECT_IDENTIFIER, BacnetPropertyIds.PROP_OBJECT_NAME, BacnetPropertyIds.PROP_OBJECT_TYPE,
        BacnetPropertyIds.PROP_PRESENT_VALUE, BacnetPropertyIds.PROP_STATUS_FLAGS, BacnetPropertyIds.PROP_EVENT_STATE,
        BacnetPropertyIds.PROP_OUT_OF_SERVICE, BacnetPropertyIds.PROP_RELIABILITY,
    ];

    private static readonly BacnetPropertyIds[] _deviceProperties =
    [
        BacnetPropertyIds.PROP_OBJECT_IDENTIFIER, BacnetPropertyIds.PROP_OBJECT_NAME, BacnetPropertyIds.PROP_OBJECT_TYPE,
        BacnetPropertyIds.PROP_OBJECT_LIST, BacnetPropertyIds.PROP_PROTOCOL_SERVICES_SUPPORTED,
    ];

    private readonly SourceConfig _config;
    private readonly DeviceConfig _device;
    private readonly string _state;
    private readonly BacnetClient _client;
    private long _discoveries;
    private long _reads;
    private long _statusReads;
    private long _multipleReads;
    private long _rejectedMultipleReads;
    private long _deniedWrites;

    public SourceDevice(SourceConfig config, DeviceConfig device, string state, string localIp)
    {
        _config = config;
        _device = device;
        _state = state;
        var transport = new BacnetIpUdpProtocolTransport(config.BroadcastPort, device.UnicastPort, localEndpointIp: localIp);
        _client = new BacnetClient(transport);
        _client.OnWhoIs += OnWhoIs;
        _client.OnReadPropertyRequest += OnRead;
        _client.OnReadPropertyMultipleRequest += OnReadMultiple;
        _client.OnWritePropertyRequest += OnWrite;
        _client.Start();
        Console.WriteLine(JsonSerializer.Serialize(new { eventType = "listening", device.DeviceId, device.UnicastPort, localIp, config.BroadcastPort, device.ReadPropertyMultiple }));
    }

    public object Status => new
    {
        _device.DeviceId,
        _device.UnicastPort,
        _device.ReadPropertyMultiple,
        discoveries = Interlocked.Read(ref _discoveries),
        reads = Interlocked.Read(ref _reads),
        statusReads = Interlocked.Read(ref _statusReads),
        multipleReads = Interlocked.Read(ref _multipleReads),
        rejectedMultipleReads = Interlocked.Read(ref _rejectedMultipleReads),
        deniedWrites = Interlocked.Read(ref _deniedWrites)
    };

    private void OnWhoIs(BacnetClient sender, BacnetAddress address, int low, int high)
    {
        if ((low >= 0 && _device.DeviceId < low) || (high >= 0 && _device.DeviceId > high)) return;
        Interlocked.Increment(ref _discoveries);
        sender.Iam(_device.DeviceId, BacnetSegmentations.SEGMENTATION_NONE, receiver: address);
        Console.WriteLine(JsonSerializer.Serialize(new { eventType = "whoIs", _device.DeviceId, requester = address.ToString() }));
    }

    private void OnRead(BacnetClient sender, BacnetAddress address, byte invoke, BacnetObjectId id, BacnetPropertyReference property, BacnetMaxSegments segments)
    {
        if (TryRead(id, property, address, out IList<BacnetValue> values, out BacnetError error))
            sender.ReadPropertyResponse(address, invoke, sender.GetSegmentBuffer(segments), id, property, values);
        else
            sender.ErrorResponse(address, BacnetConfirmedServices.SERVICE_CONFIRMED_READ_PROPERTY, invoke, error.error_class, error.error_code);
    }

    private void OnReadMultiple(BacnetClient sender, BacnetAddress address, byte invoke, IList<BacnetReadAccessSpecification> specifications, BacnetMaxSegments segments)
    {
        if (!_device.ReadPropertyMultiple)
        {
            // A device without the service rejects it, so a client falls back to one ReadProperty per value.
            Interlocked.Increment(ref _rejectedMultipleReads);
            sender.SendConfirmedServiceReject(address, invoke, BacnetRejectReason.UNRECOGNIZED_SERVICE);
            Console.WriteLine(JsonSerializer.Serialize(new { eventType = "readMultipleRejected", _device.DeviceId, requester = address.ToString() }));
            return;
        }
        var results = new List<BacnetReadAccessResult>();
        foreach (BacnetReadAccessSpecification specification in specifications)
        {
            BacnetObjectId id = specification.objectIdentifier;
            var values = new List<BacnetPropertyValue>();
            foreach (BacnetPropertyReference reference in Expand(id, specification.propertyReferences))
            {
                IList<BacnetValue> value = TryRead(id, reference, address, out IList<BacnetValue> read, out BacnetError error)
                    ? read
                    : [new BacnetValue(BacnetApplicationTags.BACNET_APPLICATION_TAG_ERROR, error)];
                values.Add(new BacnetPropertyValue { property = reference, value = value });
            }
            results.Add(new BacnetReadAccessResult(id, values));
        }
        Interlocked.Increment(ref _multipleReads);
        sender.ReadPropertyMultipleResponse(address, invoke, sender.GetSegmentBuffer(segments), results);
        Console.WriteLine(JsonSerializer.Serialize(new { eventType = "readMultiple", _device.DeviceId, objects = results.Count, requester = address.ToString() }));
    }

    private IEnumerable<BacnetPropertyReference> Expand(BacnetObjectId id, IList<BacnetPropertyReference> references)
    {
        bool isDevice = id.Type == BacnetObjectTypes.OBJECT_DEVICE && id.Instance == _device.DeviceId;
        bool isObject = _device.Objects.Any(o => (int)id.Type == o.ObjectType && id.Instance == o.ObjectId);
        foreach (BacnetPropertyReference reference in references)
        {
            var property = (BacnetPropertyIds)reference.propertyIdentifier;
            if (!(isDevice || isObject) || property is not (BacnetPropertyIds.PROP_ALL or BacnetPropertyIds.PROP_REQUIRED or BacnetPropertyIds.PROP_OPTIONAL))
            {
                yield return reference;
                continue;
            }
            IEnumerable<BacnetPropertyIds> expanded = (isDevice, property) switch
            {
                (true, BacnetPropertyIds.PROP_OPTIONAL) => [],
                (true, _) => _deviceProperties,
                (false, BacnetPropertyIds.PROP_ALL) => _objectProperties,
                (false, BacnetPropertyIds.PROP_REQUIRED) => _objectProperties.Where(p => p != BacnetPropertyIds.PROP_RELIABILITY),
                _ => [BacnetPropertyIds.PROP_RELIABILITY],
            };
            foreach (BacnetPropertyIds item in expanded) yield return new BacnetPropertyReference((uint)item, ASN1.BACNET_ARRAY_ALL);
        }
    }

    private bool TryRead(BacnetObjectId id, BacnetPropertyReference property, BacnetAddress requester, out IList<BacnetValue> values, out BacnetError error)
    {
        values = [];
        ObjectConfig? point = _device.Objects.SingleOrDefault(o => (int)id.Type == o.ObjectType && id.Instance == o.ObjectId);
        bool isDevice = id.Type == BacnetObjectTypes.OBJECT_DEVICE && id.Instance == _device.DeviceId;
        if (!isDevice && point is null)
        {
            error = new BacnetError(BacnetErrorClasses.ERROR_CLASS_OBJECT, BacnetErrorCodes.ERROR_CODE_UNKNOWN_OBJECT);
            return false;
        }
        IList<BacnetValue>? read = null;
        var prop = (BacnetPropertyIds)property.propertyIdentifier;
        if (prop == BacnetPropertyIds.PROP_OBJECT_IDENTIFIER) read = [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_OBJECT_ID, id)];
        else if (prop == BacnetPropertyIds.PROP_OBJECT_NAME) read = [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_CHARACTER_STRING, isDevice ? _device.Name : point!.Channel)];
        else if (prop == BacnetPropertyIds.PROP_OBJECT_TYPE) read = [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_ENUMERATED, (uint)id.Type)];
        else if (prop == BacnetPropertyIds.PROP_PROTOCOL_SERVICES_SUPPORTED && isDevice) read = [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_BIT_STRING, ServicesSupported())];
        else if (prop == BacnetPropertyIds.PROP_OBJECT_LIST && isDevice)
        {
            var objects = new[] { new BacnetObjectId(BacnetObjectTypes.OBJECT_DEVICE, _device.DeviceId) }.Concat(_device.Objects.Select(o => new BacnetObjectId((BacnetObjectTypes)o.ObjectType, o.ObjectId))).ToArray();
            if (property.propertyArrayIndex == 0) values = [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_UNSIGNED_INT, (uint)objects.Length)];
            else if (property.propertyArrayIndex == ASN1.BACNET_ARRAY_ALL) values = objects.Select(o => new BacnetValue(BacnetApplicationTags.BACNET_APPLICATION_TAG_OBJECT_ID, o)).ToArray();
            else if (property.propertyArrayIndex <= objects.Length) values = [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_OBJECT_ID, objects[property.propertyArrayIndex - 1])];
            else
            {
                error = new BacnetError(BacnetErrorClasses.ERROR_CLASS_PROPERTY, BacnetErrorCodes.ERROR_CODE_INVALID_ARRAY_INDEX);
                return false;
            }
            error = default;
            return true;
        }
        else if (point is not null && prop is BacnetPropertyIds.PROP_PRESENT_VALUE or BacnetPropertyIds.PROP_STATUS_FLAGS
                 or BacnetPropertyIds.PROP_EVENT_STATE or BacnetPropertyIds.PROP_OUT_OF_SERVICE or BacnetPropertyIds.PROP_RELIABILITY)
        {
            ValueSnapshot? snapshot = null;
            try { snapshot = Program.LoadSnapshot(_config, _state); }
            catch (IOException) { }
            catch (JsonException) { }
            if (snapshot is null)
            {
                error = new BacnetError(BacnetErrorClasses.ERROR_CLASS_DEVICE, BacnetErrorCodes.ERROR_CODE_OTHER);
                return false;
            }
            SourceValue value = snapshot.Values[point.ValueKey];
            SourceStatus status = value.Status!;
            read = prop switch
            {
                BacnetPropertyIds.PROP_PRESENT_VALUE => [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_REAL, (float)value.Value)],
                BacnetPropertyIds.PROP_STATUS_FLAGS => [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_BIT_STRING, status.StatusFlags)],
                BacnetPropertyIds.PROP_EVENT_STATE => [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_ENUMERATED, (uint)status.EventStateCode)],
                BacnetPropertyIds.PROP_OUT_OF_SERVICE => [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_BOOLEAN, status.OutOfService)],
                _ => [new(BacnetApplicationTags.BACNET_APPLICATION_TAG_ENUMERATED, (uint)status.ReliabilityCode)],
            };
            if (prop == BacnetPropertyIds.PROP_PRESENT_VALUE)
            {
                Interlocked.Increment(ref _reads);
                Console.WriteLine(JsonSerializer.Serialize(new { eventType = "read", _device.DeviceId, point.ObjectType, point.ObjectId, value.Value, value.IntervalEndUtc, status.Scenario, requester = requester.ToString() }));
            }
            else
            {
                Interlocked.Increment(ref _statusReads);
            }
        }
        if (read is null)
        {
            error = new BacnetError(BacnetErrorClasses.ERROR_CLASS_PROPERTY, BacnetErrorCodes.ERROR_CODE_UNKNOWN_PROPERTY);
            return false;
        }
        if (property.propertyArrayIndex != ASN1.BACNET_ARRAY_ALL)
        {
            error = new BacnetError(BacnetErrorClasses.ERROR_CLASS_PROPERTY, BacnetErrorCodes.ERROR_CODE_INVALID_ARRAY_INDEX);
            return false;
        }
        values = read;
        error = default;
        return true;
    }

    /// <summary>Protocol_Services_Supported, in BACnet's bit numbering; ReadPropertyMultiple only where the device answers it.</summary>
    private BacnetBitString ServicesSupported()
    {
        char[] bits = new string('0', 40).ToCharArray();
        BacnetServicesSupported[] services = _device.ReadPropertyMultiple
            ? [BacnetServicesSupported.SERVICE_SUPPORTED_READ_PROPERTY, BacnetServicesSupported.SERVICE_SUPPORTED_READ_PROP_MULTIPLE, BacnetServicesSupported.SERVICE_SUPPORTED_WRITE_PROPERTY, BacnetServicesSupported.SERVICE_SUPPORTED_I_AM, BacnetServicesSupported.SERVICE_SUPPORTED_WHO_IS]
            : [BacnetServicesSupported.SERVICE_SUPPORTED_READ_PROPERTY, BacnetServicesSupported.SERVICE_SUPPORTED_WRITE_PROPERTY, BacnetServicesSupported.SERVICE_SUPPORTED_I_AM, BacnetServicesSupported.SERVICE_SUPPORTED_WHO_IS];
        foreach (BacnetServicesSupported service in services) bits[(int)service] = '1';
        return BacnetBitString.Parse(new string(bits));
    }

    private void OnWrite(BacnetClient sender, BacnetAddress address, byte invoke, BacnetObjectId id, BacnetPropertyValue value, BacnetMaxSegments segments)
    {
        Interlocked.Increment(ref _deniedWrites);
        sender.ErrorResponse(address, BacnetConfirmedServices.SERVICE_CONFIRMED_WRITE_PROPERTY, invoke, BacnetErrorClasses.ERROR_CLASS_PROPERTY, BacnetErrorCodes.ERROR_CODE_WRITE_ACCESS_DENIED);
    }

    public void Dispose() => _client.Dispose();
}
