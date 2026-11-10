import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from services.historian.__main__ import next_run, publish, replace, window
from services.historian.rows import load_config
from services.historian.tests.test_rows import StubModel

UTC = timezone.utc
# Stands in for the Java writer: appends the rows file to the database file and reports like the writer.
FAKE_WRITER = (sys.executable, "-c",
               "import sys, json; rows = open(sys.argv[1]).read().splitlines()[1:]; "
               "open(sys.argv[2], 'a').write('\\n'.join(rows) + '\\n'); print(json.dumps({'added': len(rows)}))")


class HistorianServiceTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.target = Path(directory.name) / self.config["database"]

    def test_first_write_covers_the_history_then_only_the_refresh_window(self):
        now = datetime(2026, 11, 7, 18, 47, tzinfo=UTC)
        start, end = window(self.config, self.target, now)
        self.assertEqual(datetime(2024, 1, 1, 8, 0, tzinfo=UTC), start)  # midnight on 1 January 2024, Pacific
        self.assertEqual(datetime(2026, 11, 7, 18, 30, tzinfo=UTC), end)  # the last closed half hour
        self.target.write_text("existing")
        start, end = window(self.config, self.target, now)
        self.assertEqual(end - timedelta(hours=48), start)

    def test_publish_stages_a_copy_and_replaces_the_database(self):
        now = datetime(2026, 11, 7, 18, 47, tzinfo=UTC)
        self.target.write_text("existing\n")
        result = publish(StubModel(), self.config, self.target, now, writer=FAKE_WRITER)
        self.assertEqual(96, result["rows"])  # 48 hours of half-hours
        self.assertEqual(48, result["flagged"])  # the provisional last day
        self.assertEqual(96, result["writer"]["added"])
        lines = self.target.read_text().splitlines()
        self.assertEqual("existing", lines[0])
        self.assertEqual(97, len(lines))
        self.assertEqual([], [p.name for p in self.target.parent.iterdir() if p.name.startswith(".writing-")])

    def test_replace_retries_while_a_reader_holds_the_file(self):
        staged = self.target.with_suffix(".staged")
        staged.write_text("new")
        failures = iter([PermissionError("in use"), PermissionError("in use")])
        real_replace = __import__("os").replace

        def flaky(source, destination):
            error = next(failures, None)
            if error:
                raise error
            real_replace(source, destination)

        with patch("services.historian.__main__.os.replace", side_effect=flaky), patch("services.historian.__main__.time.sleep"):
            replace(staged, self.target)
        self.assertEqual("new", self.target.read_text())

    def test_next_run_is_a_minute_after_the_next_half_hour(self):
        self.assertEqual(datetime(2026, 11, 7, 19, 1, tzinfo=UTC), next_run(datetime(2026, 11, 7, 18, 47, tzinfo=UTC)))
        self.assertEqual(datetime(2026, 11, 7, 18, 31, tzinfo=UTC), next_run(datetime(2026, 11, 7, 18, 0, 5, tzinfo=UTC)))

    def test_the_eem_settings_name_the_access_driver_and_the_database_file(self):
        eem = self.config["eem"]
        self.assertEqual("ODBC", eem["profile"]["DatabaseType"])
        self.assertIn(self.config["database"], eem["profile"]["Options"])
        self.assertIn("|LastTimeStamp|", eem["query"])
        self.assertEqual(json.loads(json.dumps(eem["nodeParameters"])), eem["nodeParameters"])


if __name__ == "__main__":
    unittest.main()
