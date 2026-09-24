import sys
import unittest
import json
from pathlib import Path
import pandas as pd
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from yahoo_history import restore_history
from price_validation import validate_prices

class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({"Open":[100., np.nan, 103.], "High":[105.,np.nan,108.],
            "Low":[98.,np.nan,101.], "Close":[102.,np.nan,106.],
            "Adj Close":[102.,np.nan,106.], "Volume":[100.,0.,300.],
            "Dividends":[0.,0.,0.], "Stock Splits":[0.,0.,0.]},
            index=pd.to_datetime(["2026-09-21","2026-09-22","2026-09-23"]))
        self.record = {"Open":102.,"High":107.,"Low":100.,"Close":104.,"Volume":200.}
        self.records = {"2026-09-22":self.record}

    def test_yesterday_becomes_an_interior_gap(self):
        result = restore_history(self.df, self.records)
        validate_prices(result)
        self.assertEqual(result.Close.tolist(), [102.,104.,106.])
        self.assertEqual(result.Volume.tolist(), [100.,200.,300.])
        self.assertEqual(result["Adj Close"].tolist(), [102.,104.,106.])

    def test_persisted_bar_repairs_another_day(self):
        records = json.loads(json.dumps(self.records))
        records["2026-09-23"] = {"Open":103.,"High":108.,"Low":101.,"Close":106.,"Volume":300.}
        df=self.df.copy()
        df.loc[pd.Timestamp("2026-09-24")] = [106.,110.,104.,108.,108.,400.,0.,0.]
        df.loc[pd.Timestamp("2026-09-23"),["Open","High","Low","Close","Adj Close"]] = np.nan
        result=restore_history(df, records)
        self.assertEqual(result.Close.tolist(), [102.,104.,106.,108.])

    def test_dividend_does_not_reuse_old_adjusted_close(self):
        self.df.loc[pd.Timestamp("2026-09-23"),"Dividends"] = 2.
        result=restore_history(self.df, self.records)
        self.assertEqual(result.Close.iloc[1],104.)
        self.assertAlmostEqual(result["Adj Close"].iloc[1],102.)

    def test_split_adjusts_cached_prices_and_volume(self):
        self.df.loc[pd.Timestamp("2026-09-23"),"Stock Splits"] = 2.
        result=restore_history(self.df, self.records)
        self.assertEqual(result.Close.iloc[1],52.)
        self.assertEqual(result.Volume.iloc[1],400.)

    def test_conflicting_source_price_rejected(self):
        self.df.loc[pd.Timestamp("2026-09-22"),"High"] = 999.
        with self.assertRaises(ValueError):restore_history(self.df, self.records)

    def test_no_verified_record_does_not_invent_price(self):
        result=restore_history(self.df,{})
        with self.assertRaises(ValueError):validate_prices(result)

    def test_good_source_correction_is_preserved(self):
        self.df.loc[pd.Timestamp("2026-09-22")] = [103.,108.,101.,105.,105.,201.,0.,0.]
        result=restore_history(self.df,self.records)
        self.assertEqual(result.Close.iloc[1],105.)

if __name__ == "__main__":unittest.main()
