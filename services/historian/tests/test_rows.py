import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.historian.rows import binding, load_config, rows, to_csv, to_sql
from services.sources.generation import create_model

UTC = timezone.utc
CHANNEL = "ch_odbc_library_electric_kwh_30m"


class StubModel:
    """Half-hourly readings whose value is the interval end's minute of the day, so rows are easy to check."""

    def readings(self, item, start, end):
        step = timedelta(minutes=item["interval_minutes"])
        stamp = start + step - timedelta(seconds=start.timestamp() % step.total_seconds())
        while stamp <= end:
            yield {"timestamp_utc": stamp, "value": Decimal(stamp.hour * 60 + stamp.minute)}
            stamp += step


def at(text):
    return datetime.fromisoformat(text)


# Historical slices are written long after they happened, so none of their readings is provisional.
LATER = at("2026-11-07T12:00:00-08:00")


class HistorianRowTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def by_local(self, start, end):
        return {row["TimeStamp"]: row for row in rows(StubModel(), self.config, at(start), at(end), LATER)}

    def test_flag_windows_mark_only_the_intervals_inside_them(self):
        day = self.by_local("2025-06-03T00:00:00-07:00", "2025-06-04T00:00:00-07:00")
        self.assertIsNone(day["2025-06-03 08:00:00"]["SourceCode"])  # 07:30-08:00 ends as the window opens
        first = day["2025-06-03 08:30:00"]
        self.assertEqual(("Estimated", "EST1", "Interpolated", "bms-historian"),
                         (first["SourceClassification"], first["SourceCode"], first["Method"], first["Reader"]))
        self.assertEqual("EST1", day["2025-06-03 14:00:00"]["SourceCode"])  # 13:30-14:00 is the last inside
        self.assertIsNone(day["2025-06-03 14:30:00"]["SourceCode"])
        self.assertEqual(12, sum(1 for row in day.values() if row["SourceCode"] == "EST1"))
        exchange = self.by_local("2024-08-14T00:00:00-07:00", "2024-08-15T00:00:00-07:00")
        self.assertEqual(4, sum(1 for row in exchange.values() if (row["SourceClassification"], row["SourceCode"]) == ("Substituted", "SUB1")))

    def test_plain_readings_carry_only_the_historian_tag(self):
        row = self.by_local("2025-06-02T00:00:00-07:00", "2025-06-02T06:00:00-07:00")["2025-06-02 01:00:00"]
        self.assertEqual((None, None, None, None), (row["SourceClassification"], row["SourceCode"], row["Reader"], row["Method"]))
        self.assertEqual("LIB.ELEC.KWH.30M", row["HistorianTag"])

    def test_the_last_day_is_provisional_until_it_ages(self):
        end = at("2026-11-07T12:00:00-08:00")
        recent = list(rows(StubModel(), self.config, end - timedelta(hours=30), end))
        provisional = [row for row in recent if row["SourceCode"] == "PROV"]
        self.assertEqual(48, len(provisional))  # 24 hours of half-hours
        self.assertTrue(all(row["SourceClassification"] == "Actual" for row in provisional))
        later = {row["UtcTimeStamp"]: row for row in rows(StubModel(), self.config, end - timedelta(hours=30), end + timedelta(days=2))}
        for row in provisional:
            aged = later[row["UtcTimeStamp"]]
            self.assertEqual(row["Value"], aged["Value"])  # the same value, now with no code: the recode path
            self.assertIsNone(aged["SourceCode"])

    def test_the_repeated_autumn_hour_keeps_two_utc_rows(self):
        items = list(rows(StubModel(), self.config, at("2026-11-01T00:00:00-07:00"), at("2026-11-01T03:00:00-08:00")))
        repeated = [row for row in items if row["TimeStamp"] == "2026-11-01 01:30:00"]
        self.assertEqual(["2026-11-01 08:30:00", "2026-11-01 09:30:00"], [row["UtcTimeStamp"] for row in repeated])

    def test_invalid_calendars_fail(self):
        for change in ({"code": "X" * 17}, {"code": "TWO WORDS"}, {"classification": "Forecast"}, {"channels": ["nothing"]},
                       {"startLocal": "2025-06-03T14:00", "endLocal": "2025-06-03T08:00"}):
            with self.subTest(change=change):
                config = copy.deepcopy(self.config)
                config["flags"][0].update(change)
                path = self._write(config)
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_sql_batches_quote_text_and_null_missing_columns(self):
        items = list(rows(StubModel(), self.config, at("2025-06-03T07:00:00-07:00"), at("2025-06-03T09:00:00-07:00"), LATER))
        sql = to_sql(items, "SyntheticIntervalReadings", batch=3)
        self.assertEqual(2, sql.count("INSERT INTO SyntheticIntervalReadings"))
        self.assertIn("NULL, NULL, NULL, NULL, 'LIB.ELEC.KWH.30M'", sql)
        self.assertIn("'Estimated', 'EST1', 'bms-historian', 'Interpolated'", sql)
        self.assertEqual(len(items) + 1, len(to_csv(items).splitlines()))

    def test_values_are_the_source_model_values(self):
        model = create_model(".")
        start, end = at("2025-06-03T07:00:00-07:00"), at("2025-06-03T09:00:00-07:00")
        expected = [format(Decimal(str(item["value"])), "f") for item in model.readings(binding(self.config["channels"][0]), start, end)]
        self.assertEqual(expected, [row["Value"] for row in rows(model, self.config, start, end)])
        self.assertTrue(expected)

    def _write(self, config):
        import json
        import tempfile
        from pathlib import Path

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "historian.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
