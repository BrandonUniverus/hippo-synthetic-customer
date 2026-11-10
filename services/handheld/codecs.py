"""Native return layouts verified against EnergyHippo collectors, not vendor certification."""
from .contracts import ascii_text, native_time, validate_observation


def record(length, *fields):
    result = [" "] * length
    occupied = set()
    for offset, width, value in fields:
        value = ascii_text(str(value), "Native field", width, empty=True)
        if offset < 0 or offset + width > length or occupied.intersection(range(offset, offset + width)):
            raise ValueError("Overlapping or out-of-range native field")
        occupied.update(range(offset, offset + width))
        result[offset:offset + width] = value.ljust(width)
    return "".join(result)


def encode(channel, observation):
    o = validate_observation(channel, observation)
    t = native_time(o["observed_at"])
    current, previous = str(o["value"]).zfill(10), str(o["previous"]).zfill(10)
    skipped = o["action"] == "skip"
    if channel["return_format"] == "neptune":
        lines = [record(60, (0, 5, "COMHD"), (5, 4, "0001"), (9, 8, t.strftime("%Y%m%d")), (17, 40, "Northlake controlled pilot")),
                 record(120, (0, 5, "RTEHD"), (5, 4, "0001"), (9, 4, "0001"), (13, 10, channel["route"]),
                        (23, 8, t.strftime("%Y%m%d")), (31, 8, t.strftime("%Y%m%d"))),
                 record(260, (0, 5, "MTRDT"), (11, 6, str(channel["sequence"]).zfill(6)), (17, 20, channel["meter_id"]),
                        (37, 20, channel["meter_number"]), (77, 4, "WTR"), (244, 8, t.strftime("%Y%m%d")), (252, 6, "1")),
                 record(120, (0, 5, "RDGDT"), (5, 4, channel["text_prompt"]), (53, 2, "00"), (78, 10, previous), (88, 10, current)),
                 record(187, (0, 5, "ORDST"), (5, 14, t.strftime("%Y%m%d%H%M%S")), (24, 20, o["reader"]),
                        (44, 2, "SK" if skipped else "CO"), (58, 128, o["note"])), record(60, (0, 5, "COMTR"))]
    elif channel["return_format"] == "mvrs":
        # MTR's twelve-character serial is informational; physical MetaWorldID is authoritative.
        lines = [record(126, (0, 3, "FHD")),
                 record(125, (0, 3, "MTR"), (45, 12, channel["export_meter"]), (101, 19, channel["meter_id"])),
                 record(120, (0, 3, "RDG"), (11, 4, channel["text_prompt"]), (23, 2, channel["channel"]),
                        (26, 6, "1"), (33, 10, current), (47, 8, t.strftime("%m%d%Y")), (55, 6, t.strftime("%H%M%S")),
                        (61, 1, "S" if skipped else o["read_code"]), (63, 2, o["skip_code"] if skipped else "00"),
                        (65, 1, "0" if skipped else o["audit_code"]),
                        (75, 8, o["reader"]), (91, 2, "00"), (105, 10, previous))]
        if o["note"]:
            lines.append(record(65, (0, 3, "MTM"), (23, 40, o["note"])))
        lines.append(record(126, (0, 3, "FTR")))
    else:
        raise ValueError("Unsupported native return format")
    return ("\r\n".join(lines) + "\r\n").encode("ascii")
