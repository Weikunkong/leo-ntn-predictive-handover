"""Statistics over Monte-Carlo seeds: means, t-based confidence intervals, paired differences."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps


def mean_ci(values: np.ndarray, confidence: float = 0.95) -> tuple[float, float, int]:
    """Sample mean, half-width of the two-sided Student-t confidence interval and sample size.

    NaNs are ignored; with fewer than two valid samples the half-width is NaN.
    """
    x = np.asarray(values, dtype=np.float64)
    x = x[~np.isnan(x)]
    n = len(x)
    if n == 0:
        return float("nan"), float("nan"), 0
    m = float(x.mean())
    if n < 2:
        return m, float("nan"), n
    sem = float(x.std(ddof=1) / np.sqrt(n))
    h = float(sps.t.ppf(0.5 + confidence / 2.0, n - 1) * sem)
    return m, h, n


def paired_diff_ci(a: np.ndarray, b: np.ndarray, confidence: float = 0.95) -> tuple[float, float, float]:
    """Mean of ``a - b`` over paired samples (same seeds), CI half-width and paired t-test p-value."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    ok = ~(np.isnan(a) | np.isnan(b))
    d = a[ok] - b[ok]
    if len(d) < 2:
        return float(d.mean()) if len(d) else float("nan"), float("nan"), float("nan")
    m, h, _ = mean_ci(d, confidence)
    if np.allclose(d, d[0]):
        p = 1.0 if abs(d[0]) < 1e-12 else 0.0
    else:
        p = float(sps.ttest_rel(a[ok], b[ok]).pvalue)
    return m, h, p


def summarize(runs: pd.DataFrame, group_cols: list[str], metrics: list[str],
              confidence: float = 0.95) -> pd.DataFrame:
    """Aggregate per-seed rows into mean / CI half-width / n per group and metric."""
    rows = []
    for key, grp in runs.groupby(group_cols, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_cols, key))
        for m in metrics:
            mean, half, n = mean_ci(grp[m].to_numpy(), confidence)
            row[f"{m}_mean"] = mean
            row[f"{m}_ci"] = half
            row[f"{m}_n"] = n
        rows.append(row)
    return pd.DataFrame(rows)
