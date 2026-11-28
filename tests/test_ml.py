"""Tests for hfin_ml next-day direction baseline."""

import unittest
from pathlib import Path

from hfin_ml import (
    accuracy,
    build_dataset,
    load_closes,
    logistic_accuracy,
    majority_predictions,
    persistence_predictions,
    run,
    train_test_split_by_date,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Steady ~+1% a day: every next-day move is up.
STEADY_UP = [100 + i for i in range(12)]

# Alternating +10% / -10% days: tomorrow always reverses today.
ALTERNATING = [100.0]
for _ in range(11):
    ALTERNATING.append(
        ALTERNATING[-1] * 1.10 if len(ALTERNATING) % 2 == 1 else ALTERNATING[-1] * 0.90
    )


class TestBuildDataset(unittest.TestCase):
    def test_steady_up_features(self):
        features, targets = build_dataset(STEADY_UP)
        self.assertEqual(len(features), 6)
        self.assertEqual(targets, [1] * 6)
        # First sample: yesterday's return = 105/104 - 1, 5-day mean
        # of the first five returns.
        self.assertAlmostEqual(features[0][0], 0.961538, places=4)
        self.assertAlmostEqual(features[0][1], 0.980581, places=4)

    def test_alternating_targets(self):
        features, targets = build_dataset(ALTERNATING)
        self.assertEqual(len(features), 6)
        # Tomorrow always reverses today, so every target is the
        # opposite of yesterday's direction.
        self.assertEqual(targets, [0, 1, 0, 1, 0, 1])

    def test_needs_enough_closes(self):
        with self.assertRaises(ValueError):
            build_dataset([100] * 7)

    def test_no_lookahead(self):
        # Changing only the LAST close must change only the last
        # target -- earlier features/targets use earlier data only.
        base_features, base_targets = build_dataset(STEADY_UP)
        changed = STEADY_UP[:-1] + [50]
        new_features, new_targets = build_dataset(changed)
        self.assertEqual(new_features[:-1], base_features[:-1])
        self.assertEqual(new_targets[:-1], base_targets[:-1])
        self.assertNotEqual(new_targets[-1], base_targets[-1])


class TestSplit(unittest.TestCase):
    def test_chronological_split(self):
        features, targets = build_dataset(STEADY_UP)
        x_train, y_train, x_test, y_test = train_test_split_by_date(
            features, targets, 0.25
        )
        self.assertEqual(len(y_train), 4)
        self.assertEqual(len(y_test), 2)
        # Order preserved: train first, test last, nothing shuffled.
        self.assertEqual(y_train + y_test, targets)
        self.assertEqual(x_train + x_test, features)

    def test_bad_fraction(self):
        features, targets = build_dataset(STEADY_UP)
        with self.assertRaises(ValueError):
            train_test_split_by_date(features, targets, 1.5)


class TestBaselines(unittest.TestCase):
    def test_persistence_wrong_on_reversal(self):
        # On the alternating series, "tomorrow = today" is always wrong.
        features, targets = build_dataset(ALTERNATING)
        self.assertAlmostEqual(
            accuracy(persistence_predictions(features), targets), 0.0
        )

    def test_persistence_right_on_trend(self):
        features, targets = build_dataset(STEADY_UP)
        self.assertAlmostEqual(
            accuracy(persistence_predictions(features), targets), 1.0
        )

    def test_majority_baseline(self):
        self.assertEqual(majority_predictions([1, 1, 0], 2), [1, 1])
        self.assertEqual(majority_predictions([0, 0, 0, 1], 3), [0, 0, 0])

    def test_accuracy_helper(self):
        self.assertAlmostEqual(accuracy([1, 0, 1], [1, 1, 1]), 2 / 3)
        with self.assertRaises(ValueError):
            accuracy([1, 0], [1])
        with self.assertRaises(ValueError):
            accuracy([], [])


class TestLogistic(unittest.TestCase):
    def test_learns_perfect_reversal(self):
        # Alternating series: the sign of yesterday's return perfectly
        # predicts tomorrow, so logistic regression should nail it.
        features, targets = build_dataset(ALTERNATING)
        x_train, y_train, x_test, y_test = train_test_split_by_date(
            features, targets, 0.25
        )
        self.assertAlmostEqual(
            logistic_accuracy(x_train, y_train, x_test, y_test), 1.0
        )


class TestRealDataset(unittest.TestCase):
    def test_real_csv_run(self):
        results = run(REPO_ROOT / "hfin_stock_data.csv")
        self.assertEqual(results["n_days"], 106)
        self.assertEqual(results["n_samples"], 100)
        self.assertEqual(results["n_train"], 80)
        self.assertEqual(results["n_test"], 20)
        for key in ("logistic", "persistence", "majority"):
            self.assertGreaterEqual(results[key], 0.0)
            self.assertLessEqual(results[key], 1.0)

    def test_run_is_deterministic(self):
        first = run(REPO_ROOT / "hfin_stock_data.csv")
        second = run(REPO_ROOT / "hfin_stock_data.csv")
        self.assertEqual(first, second)

    def test_load_closes_is_chronological(self):
        pairs = load_closes(REPO_ROOT / "hfin_stock_data.csv")
        self.assertEqual(len(pairs), 106)
        dates = [d for d, _ in pairs]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(str(dates[0]), "2026-03-15")
        self.assertEqual(str(dates[-1]), "2026-11-06")


if __name__ == "__main__":
    unittest.main()
