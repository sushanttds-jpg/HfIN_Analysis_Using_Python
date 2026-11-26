"""Tests for hfin_stats return statistics."""

import unittest

from hfin_stats import daily_returns, return_stats


class TestDailyReturns(unittest.TestCase):
    def test_simple_returns(self):
        self.assertEqual(
            [round(r, 6) for r in daily_returns([100, 110, 99])],
            [10.0, -10.0],
        )

    def test_needs_two_closes(self):
        with self.assertRaises(ValueError):
            daily_returns([100])


class TestReturnStats(unittest.TestCase):
    def test_known_values(self):
        # Closes chosen so returns are exactly +10, -10, +10, -10.
        stats = return_stats([100, 110, 99, 108.9, 98.01])
        self.assertEqual(stats["n"], 4)
        self.assertAlmostEqual(stats["mean"], 0.0, places=6)
        self.assertAlmostEqual(stats["volatility"], 11.547005, places=4)
        self.assertAlmostEqual(stats["t_stat"], 0.0, places=6)
        self.assertAlmostEqual(stats["p_value"], 1.0, places=6)

    def test_positive_drift_is_significant(self):
        # Steady +1% a day: mean clearly above zero.
        closes = [100 * (1.01 ** i) for i in range(30)]
        stats = return_stats(closes)
        self.assertGreater(stats["t_stat"], 10)
        self.assertLess(stats["p_value"], 0.001)

    def test_flat_series(self):
        stats = return_stats([50, 50, 50, 50])
        self.assertEqual(stats["mean"], 0.0)
        self.assertEqual(stats["volatility"], 0.0)
        self.assertEqual(stats["t_stat"], 0.0)


if __name__ == "__main__":
    unittest.main()
