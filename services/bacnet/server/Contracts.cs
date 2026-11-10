using System.IO.BACnet;
using System.Text.Json;
using System.Security.Cryptography;

namespace Northlake.Bacnet;

public sealed record SourceConfig(string Version, int BroadcastPort, DeviceConfig[] Devices)
{
    public static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };
    public string Hash { get; init; } = "";

    public static SourceConfig Load(string path)
    {
        byte[] bytes = File.ReadAllBytes(path);
        SourceConfig config = JsonSerializer.Deserialize<SourceConfig>(bytes, JsonOptions) ?? throw new InvalidDataException("Missing source configuration.");
        if (config.BroadcastPort is < 1 or > 65535 || config.Devices.Length == 0) throw new InvalidDataException("Invalid BACnet source ports/devices.");
        var ids = new HashSet<uint>();
        var ports = new HashSet<int> { config.BroadcastPort };
        foreach (DeviceConfig device in config.Devices)
        {
            if (device.DeviceId > 4194302 || !ids.Add(device.DeviceId)) throw new InvalidDataException($"Invalid or duplicate device instance {device.DeviceId}.");
            if (device.UnicastPort is < 1 or > 65535 || !ports.Add(device.UnicastPort)) throw new InvalidDataException("Device unicast ports must be distinct.");
            if (device.Objects.Length == 0 || device.Objects.Select(o => (o.ObjectType, o.ObjectId)).Distinct().Count() != device.Objects.Length) throw new InvalidDataException("Empty or duplicate object table.");
            if (device.Objects.Any(o => o.ObjectType is not (0 or 2) || o.ObjectId > 4194302)) throw new InvalidDataException("Unsupported object type or instance.");
            if (device.Objects.Any(o => o.IntervalMinutes is not (15 or 60))) throw new InvalidDataException("Unsupported native interval.");
        }
        return config with { Hash = Convert.ToHexStringLower(SHA256.HashData(bytes)) };
    }
}

/// <summary>A device answers ReadPropertyMultiple only when <paramref name="ReadPropertyMultiple"/> is set; otherwise it rejects the service.</summary>
public sealed record DeviceConfig(uint DeviceId, uint LegacyDeviceId, int NodeId, string Name, int UnicastPort, ObjectConfig[] Objects, bool ReadPropertyMultiple = false);
public sealed record ObjectConfig(int ObjectType, uint ObjectId, int PointId, string Channel, string ValueKey, string Unit, int IntervalMinutes);
public sealed record ValueSnapshot(string Version, DateTimeOffset GeneratedAtUtc, string SourceHash, string ConfigHash, Dictionary<string, SourceValue> Values);
public sealed record SourceValue(double Value, DateTimeOffset IntervalEndUtc, SourceStatus? Status = null);

/// <summary>An object's BACnet status as the producer reports it, beside its value.</summary>
public sealed record SourceStatus(bool InAlarm, bool Fault, bool Overridden, bool OutOfService, string EventState, string Reliability, string? Scenario = null)
{
    private static readonly Dictionary<string, BacnetEventStates> _eventStates = new(StringComparer.Ordinal)
    {
        ["normal"] = BacnetEventStates.EVENT_STATE_NORMAL,
        ["fault"] = BacnetEventStates.EVENT_STATE_FAULT,
        ["offnormal"] = BacnetEventStates.EVENT_STATE_OFFNORMAL,
        ["high-limit"] = BacnetEventStates.EVENT_STATE_HIGH_LIMIT,
        ["low-limit"] = BacnetEventStates.EVENT_STATE_LOW_LIMIT,
    };

    private static readonly Dictionary<string, BacnetReliability> _reliabilities = new(StringComparer.Ordinal)
    {
        ["no-fault-detected"] = BacnetReliability.RELIABILITY_NO_FAULT_DETECTED,
        ["no-sensor"] = BacnetReliability.RELIABILITY_NO_SENSOR,
        ["over-range"] = BacnetReliability.RELIABILITY_OVER_RANGE,
        ["under-range"] = BacnetReliability.RELIABILITY_UNDER_RANGE,
        ["open-loop"] = BacnetReliability.RELIABILITY_OPEN_LOOP,
        ["shorted-loop"] = BacnetReliability.RELIABILITY_SHORTED_LOOP,
        ["no-output"] = BacnetReliability.RELIABILITY_NO_OUTPUT,
        ["unreliable-other"] = BacnetReliability.RELIABILITY_UNRELIABLE_OTHER,
    };

    /// <summary>Known names, and the two derived flags agree with BACnet: in alarm unless normal, fault unless no fault is detected.</summary>
    public bool IsConsistent => _eventStates.ContainsKey(EventState) && _reliabilities.ContainsKey(Reliability)
        && InAlarm == (EventState != "normal") && Fault == (Reliability != "no-fault-detected");

    public BacnetEventStates EventStateCode => _eventStates[EventState];

    public BacnetReliability ReliabilityCode => _reliabilities[Reliability];

    /// <summary>Status_Flags as BACnet numbers its bits: 0 in alarm, 1 fault, 2 overridden, 3 out of service.</summary>
    public BacnetBitString StatusFlags => BacnetBitString.Parse(string.Concat(Bit(InAlarm), Bit(Fault), Bit(Overridden), Bit(OutOfService)));

    private static char Bit(bool value) => value ? '1' : '0';
}
