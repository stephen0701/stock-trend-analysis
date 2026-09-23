import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from price_validation import validate_prices, read_prices, prepare_download
import build_app_data as build
import fetch_prices

class PriceTests(unittest.TestCase):
    def setUp(self):
        self.df = read_prices(ROOT / "data/raw/DRAM.csv")

    def test_reject_nonfinite_and_zero(self):
        for value in (np.nan, np.inf, -np.inf, 0, -1):
            df = self.df.copy()
            df.iloc[-1, df.columns.get_loc("Close")] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_prices(df)

    def test_reject_missing_volume(self):
        df = self.df.copy()
        df.iloc[-1, df.columns.get_loc("Volume")] = np.nan
        with self.assertRaises(ValueError): validate_prices(df)

    def test_sort_and_duplicate_dates(self):
        self.assertTrue(validate_prices(self.df.iloc[::-1]).index.is_monotonic_increasing)
        with self.assertRaises(ValueError): validate_prices(pd.concat([self.df, self.df.tail(1)]))

    def test_missing_tail_uses_previous_complete_session(self):
        df = self.df.copy()
        df.iloc[-1, df.columns.get_loc("Close")] = np.nan
        result = prepare_download(df, today=df.index[-1])
        self.assertEqual(result.index[-1], df.index[-2])
        self.assertEqual(result.attrs["missingDates"], [df.index[-1].strftime("%Y-%m-%d")])
        self.assertEqual(result.Close.iloc[-1], df.Close.iloc[-2])

    def test_interior_corruption_and_old_data_rejected(self):
        df = self.df.copy()
        df.iloc[-3, df.columns.get_loc("Close")] = np.nan
        with self.assertRaises(ValueError): prepare_download(df, today=df.index[-1])
        with self.assertRaises(ValueError): prepare_download(self.df, today="2026-09-23")
        df.iloc[-4:, df.columns.get_loc("Close")] = np.nan
        with self.assertRaises(ValueError): prepare_download(df, today=df.index[-1])

    def test_retry_recovers_or_returns_recent_partial(self):
        partial = self.df.iloc[:-1].copy()
        partial.attrs["missingDates"] = ["2026-07-09"]
        with patch.object(fetch_prices, "fetch_yfinance", side_effect=[partial, self.df]), patch.object(fetch_prices.time, "sleep"), patch.object(fetch_prices, "fetch_stooq") as backup:
            result, source = fetch_prices.fetch_best("DRAM")
            self.assertEqual(result.index[-1], self.df.index[-1])
            backup.assert_not_called()
        with patch.object(fetch_prices, "fetch_yfinance", return_value=partial), patch.object(fetch_prices.time, "sleep"), patch.object(fetch_prices, "fetch_stooq", side_effect=ValueError("404")):
            result, source = fetch_prices.fetch_best("DRAM")
            self.assertEqual(result.attrs["missingDates"], ["2026-07-09"])

    def test_benchmark_later_day_does_not_change_relative_return(self):
        original = build.technicals(self.df, self.df.Close)
        benchmark = pd.concat([self.df.Close, pd.Series([9999.], index=[self.df.index[-1] + pd.Timedelta(days=1)])])
        actual = build.technicals(self.df, benchmark)
        self.assertEqual(original["indicators"][1], actual["indicators"][1])

    def test_empty(self):
        with self.assertRaises(ValueError): validate_prices(self.df.iloc[:0])

    def test_short_history(self):
        with self.assertRaises(ValueError): build.technicals(self.df.head(10), self.df.Close)

    def test_flat_prices_have_finite_indicators(self):
        df = self.df.copy()
        df.loc[:, ["Open", "High", "Low", "Close"]] = 10.
        result = build.technicals(df, df.Close)
        self.assertNotIn("nan", str(result).lower())
        self.assertNotIn("inf", str(result).lower())

    def test_failed_build_preserves_previous_data(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "data.js"
            target.write_text("previous good data")
            with patch.object(build, "APP", folder), patch.object(build.json, "dumps", side_effect=ValueError("nonfinite")):
                with self.assertRaises(ValueError): build.main()
            self.assertEqual(target.read_text(), "previous good data")

    def test_fallback_and_failed_fetch_preserves_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(fetch_prices.time, "sleep"), patch.object(fetch_prices, "RAW_DIR", folder), patch.object(fetch_prices, "WATCHLIST", []), patch.object(fetch_prices, "fetch_yfinance", side_effect=ValueError("bad quote")), patch.object(fetch_prices, "fetch_stooq", return_value=self.df):
                with self.assertRaises(SystemExit) as status: fetch_prices.main()
                self.assertEqual(status.exception.code, 0)
                target = Path(folder) / "GSPC.csv"
                before = target.read_bytes()
                with patch.object(fetch_prices, "fetch_stooq", side_effect=ValueError("bad quote")):
                    with self.assertRaises(SystemExit) as status: fetch_prices.main()
                    self.assertEqual(status.exception.code, 1)
                self.assertEqual(target.read_bytes(), before)

if __name__ == "__main__": unittest.main()
