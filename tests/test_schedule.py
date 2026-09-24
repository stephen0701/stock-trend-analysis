import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from trading_session import expected_session, require_session
from fetch_prices import fetch_with_retries, save_verified
import tempfile
import json


class ScheduleTests(unittest.TestCase):
    def test_taiwan_morning_requires_previous_us_day(self):
        self.assertEqual(expected_session("2026-09-24T06:17:00+08:00"), "2026-09-23")

    def test_weekend_and_monday_holiday(self):
        for now in ["2026-09-06T00:00:00Z", "2026-09-08T02:17:00Z"]:
            self.assertEqual(expected_session(now), "2026-09-04")

    def test_winter_close_and_early_close(self):
        self.assertEqual(expected_session("2026-12-02T06:17:00+08:00"), "2026-12-01")
        self.assertEqual(expected_session("2026-11-27T18:01:00Z"), "2026-11-27")
        self.assertEqual(expected_session("2026-11-27T17:59:00Z"), "2026-11-25")

    def test_old_but_valid_quote_rejected(self):
        frame = pd.DataFrame(index=pd.to_datetime(["2026-09-22"]))
        with self.assertRaisesRegex(ValueError, "2026-09-23"):
            require_session(frame, "2026-09-23")

    def test_retry_recovers_and_exhaustion_raises(self):
        frame = pd.DataFrame({"Open": 10, "High": 11, "Low": 9,
                              "Close": 10, "Volume": 100},
                             index=pd.date_range("2026-01-01", periods=65))
        expected = frame.index[-1].strftime("%Y-%m-%d")
        fetch, sleep = Mock(side_effect=[RuntimeError("network"), frame]), Mock()
        self.assertEqual(len(fetch_with_retries(fetch, expected, sleep=sleep)), 65)
        self.assertEqual(fetch.call_count, 2)
        fetch = Mock(side_effect=RuntimeError("network"))
        with self.assertRaises(RuntimeError):
            fetch_with_retries(fetch, expected, sleep=sleep)
        self.assertEqual(fetch.call_count, 3)

    def test_verified_cache_survives_separate_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".cache" / "bars.json"
            record = {"NVDA": {"2026-09-23": {"Close": 225.51}}}
            save_verified(path, record)
            self.assertEqual(json.loads(path.read_text()), record)
