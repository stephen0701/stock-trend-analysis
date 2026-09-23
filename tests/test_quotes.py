import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from fetch_prices import repair_yahoo_history
from tiingo_prices import parse_prices, fetch_tiingo

class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.history = pd.DataFrame({"Open":[98.,100.], "High":[102.,105.],
            "Low":[97.,99.], "Close":[100.,np.nan], "Adj Close":[50.,np.nan],
            "Volume":[200.,300.]}, index=pd.to_datetime(["2026-09-21","2026-09-22"]))
        self.day = self.history.tail(1).copy()
        self.day["Close"], self.day["Adj Close"] = 104.,104.
        self.end = pd.Timestamp("2026-09-22T20:00:00Z")
        self.metadata = {"exchangeTimezoneName":"America/New_York",
                         "currentTradingPeriod":{"regular":{"end":self.end}}}
        self.now = "2026-09-23T01:00:00Z"

    def repair(self):
        return repair_yahoo_history(self.history,self.day,self.metadata,self.now)

    def test_real_same_day_repair_and_adjustment(self):
        df=self.repair()
        self.assertEqual(df.Close.tolist(), [50.,104.])
        self.assertEqual(df.Open.tolist(), [49.,100.])
        self.assertEqual(df.Volume.tolist(), [200.,300.])
        self.assertEqual(len(df),2)

    def test_numeric_metadata_timestamp(self):
        self.metadata["currentTradingPeriod"]["regular"]["end"] = int(self.end.timestamp())
        self.assertEqual(self.repair().Close.iloc[-1],104.)

    def test_wrong_date_rejected(self):
        self.day.index = pd.to_datetime(["2026-09-21"])
        with self.assertRaises(ValueError):self.repair()

    def test_incomplete_day_rejected(self):
        self.day["Close"] = np.nan
        with self.assertRaises(ValueError):self.repair()

    def test_open_session_rejected(self):
        self.now = "2026-09-22T19:00:00Z"
        with self.assertRaises(ValueError):self.repair()

    def test_interior_gap_not_filled(self):
        self.history.iloc[0,self.history.columns.get_loc("Close")] = np.nan
        with self.assertRaises(ValueError):self.repair()

    def test_tiingo_uses_adjusted_prices(self):
        rows=[{"date":"2026-09-22T00:00:00Z","open":200,"high":220,"low":180,"close":210,
               "adjOpen":100,"adjHigh":110,"adjLow":90,"adjClose":105,"volume":300,"adjVolume":600}]
        df=parse_prices(rows)
        self.assertEqual(df.Close.iloc[0],105)
        self.assertEqual(df.Volume.iloc[0],300)
        rows[0]["adjClose"] = None
        with self.assertRaises(ValueError):parse_prices(rows)

    def test_tiingo_missing_token_does_not_make_request(self):
        with patch("tiingo_prices.load_token",side_effect=ValueError("missing")), patch("tiingo_prices.urlopen") as req:
            with self.assertRaises(ValueError):fetch_tiingo("NVDA")
            req.assert_not_called()

if __name__ == "__main__": unittest.main()
