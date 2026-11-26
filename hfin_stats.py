"""Return statistics for the HFIN dataset.

Small, dependency-free helpers (standard library only) so the unit
tests run without pandas. Used by hfin_analysis.py for the summary
panel and by tests/test_stats.py.
"""

import math
import statistics


def daily_returns(closes):
    """Simple daily returns in percent from a chronological close list."""
    closes = [float(c) for c in closes]
    if len(closes) < 2:
        raise ValueError("need at least two closes to compute returns")
    return [
        (closes[i] / closes[i - 1] - 1.0) * 100.0
        for i in range(1, len(closes))
    ]


def return_stats(closes):
    """Mean daily return, volatility and a one-sample t-test vs zero.

    Returns a dict with n (trading days), mean (%/day), volatility
    (sample standard deviation, %/day), t_stat and a two-sided p-value.
    The p-value uses the normal approximation, which is fine here
    (n is ~100 trading days).
    """
    rets = daily_returns(closes)
    n = len(rets)
    mean = statistics.fmean(rets)
    vol = statistics.stdev(rets) if n > 1 else 0.0
    if vol == 0.0:
        t_stat = 0.0
    else:
        t_stat = mean / (vol / math.sqrt(n))
    # Two-sided p-value under the normal approximation.
    p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
    return {
        "n": n,
        "mean": mean,
        "volatility": vol,
        "t_stat": t_stat,
        "p_value": p_value,
    }
