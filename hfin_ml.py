"""Next-day direction baseline for the HFIN dataset.

First ML step for the repo (3-year plan: HFIN -> HFIN-ML): predict
whether tomorrow's close is up or down, using only past prices.
Features are yesterday's return and the 5-day mean return; the model
is a logistic regression from Scikit-learn, evaluated on a
chronological train/test split (no shuffling -- this is a time
series, so the test set must come after the training set).

Two baselines are reported alongside the model, because a model that
cannot beat "tomorrow moves like today" has learned nothing:
  * persistence -- predict tomorrow's direction = today's direction
  * majority   -- always predict the more common direction in training

With only 106 trading days this is a baseline, not a trading signal.
The honest result (see README) is that none of the three beats ~50%
by much on this sample -- which is itself the finding: daily HFIN
moves are close to unpredictable from price history alone.
"""

import csv
from datetime import date

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CSV_PATH = "hfin_stock_data.csv"


def load_closes(csv_path=CSV_PATH):
    """Chronological (date, close) pairs, skipping MARKET CLOSED rows."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            close = row["CLOSE PRICE"].strip()
            if close.upper() == "MARKET CLOSED":
                continue
            rows.append((date.fromisoformat(row["BUSINESS DATE"].strip()),
                         float(close)))
    rows.sort(key=lambda pair: pair[0])
    return rows


def build_dataset(closes):
    """Features/targets for next-day direction prediction.

    For each trading day i (with at least 5 prior returns available):
      features = [yesterday's return %, mean return % over the last 5 days]
      target   = 1 if the close rises from day i to day i+1, else 0
    Returns (features, targets). Sample i is the prediction made at
    the close of day i, using only returns known by then -- no
    look-ahead: the target is the *next* day's move.
    """
    closes = [float(c) for c in closes]
    if len(closes) < 8:
        raise ValueError("need at least 8 closes to build features")
    returns = [
        (closes[i] / closes[i - 1] - 1.0) * 100.0
        for i in range(1, len(closes))
    ]
    features, targets = [], []
    for i in range(5, len(returns)):
        # returns[i] is the move from day i to day i+1; features use
        # returns up to i (known at the close of day i).
        window = returns[i - 5:i]
        features.append([returns[i - 1], sum(window) / len(window)])
        targets.append(1 if returns[i] > 0 else 0)
    return features, targets


def train_test_split_by_date(features, targets, test_fraction=0.2):
    """Chronological split: the last test_fraction is the test set."""
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be between 0 and 1")
    n_test = max(1, round(len(targets) * test_fraction))
    cut = len(targets) - n_test
    return (
        features[:cut], targets[:cut],
        features[cut:], targets[cut:],
    )


def accuracy(predictions, targets):
    """Share of correct predictions (0.0-1.0)."""
    if len(predictions) != len(targets) or not targets:
        raise ValueError("predictions and targets must be non-empty and equal length")
    correct = sum(1 for p, t in zip(predictions, targets) if p == t)
    return correct / len(targets)


def persistence_predictions(features):
    """Tomorrow moves the same way as today: up if yesterday's return > 0."""
    return [1 if row[0] > 0 else 0 for row in features]


def majority_predictions(train_targets, n):
    """Always predict the more common direction in the training set."""
    up = sum(train_targets)
    majority = 1 if up * 2 >= len(train_targets) else 0
    return [majority] * n


def logistic_accuracy(x_train, y_train, x_test, y_test):
    """Accuracy of a scaled logistic regression on the test set."""
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000),
    )
    model.fit(x_train, y_train)
    return accuracy(model.predict(x_test).tolist(), y_test)


def run(csv_path=CSV_PATH, test_fraction=0.2):
    """Full baseline run on the CSV; returns a results dict."""
    pairs = load_closes(csv_path)
    closes = [close for _, close in pairs]
    features, targets = build_dataset(closes)
    x_train, y_train, x_test, y_test = train_test_split_by_date(
        features, targets, test_fraction
    )
    return {
        "n_days": len(closes),
        "n_samples": len(targets),
        "n_train": len(y_train),
        "n_test": len(y_test),
        "up_share_test": sum(y_test) / len(y_test),
        "logistic": logistic_accuracy(x_train, y_train, x_test, y_test),
        "persistence": accuracy(
            persistence_predictions(x_test), y_test
        ),
        "majority": accuracy(
            majority_predictions(y_train, len(y_test)), y_test
        ),
    }


def main():
    results = run()
    print(
        f"HFIN next-day direction baseline "
        f"({results['n_days']} trading days, "
        f"{results['n_samples']} samples)"
    )
    print(
        f"Train {results['n_train']} / test {results['n_test']} "
        f"(chronological split; test up-days "
        f"{results['up_share_test']:.0%})"
    )
    print(f"Logistic regression: {results['logistic']:.1%} accuracy")
    print(f"Persistence baseline: {results['persistence']:.1%} accuracy")
    print(f"Majority baseline:    {results['majority']:.1%} accuracy")


if __name__ == "__main__":
    main()
