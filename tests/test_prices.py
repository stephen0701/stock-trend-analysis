import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from price_validation import validate_prices, read_prices
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
            with patch.object(fetch_prices, "RAW_DIR", folder), patch.object(fetch_prices, "WATCHLIST", []), patch.object(fetch_prices, "fetch_yfinance", side_effect=ValueError("bad quote")), patch.object(fetch_prices, "fetch_stooq", return_value=self.df):
                with self.assertRaises(SystemExit) as status: fetch_prices.main()
                self.assertEqual(status.exception.code, 0)
                target = Path(folder) / "GSPC.csv"
                before = target.read_bytes()
                with patch.object(fetch_prices, "fetch_stooq", side_effect=ValueError("bad quote")):
                    with self.assertRaises(SystemExit) as status: fetch_prices.main()
                    self.assertEqual(status.exception.code, 1)
                self.assertEqual(target.read_bytes(), before)

if __name__ == "__main__": unittest.main()
