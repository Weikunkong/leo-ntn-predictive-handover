"""Measurement model: noisy per-step link-quality measurements with 3GPP-style L3 filtering.

Each simulation step the UE obtains one measurement of the serving and
neighbour satellite links (all satellites above the minimum elevation are
assumed measurable, e.g. via SIB19 neighbour assistance). The measured value
is the true SNR plus zero-mean Gaussian noise (``noise_std_db``), then
smoothed with the layer-3 filter of TS 38.331 §5.5.3.2:

    F_n = (1 - a) F_{n-1} + a M_n,   a = 1 / 2^(k/4)

The filter is (re-)initialised with the first measurement whenever a satellite
becomes a candidate again.
"""

from __future__ import annotations

import numpy as np


def l3_filter_coefficient(k: int) -> float:
    """TS 38.331 filter coefficient ``a = 1/2^(k/4)`` (k = 0 disables filtering)."""
    return float(1.0 / 2.0 ** (k / 4.0))


def l3_filter(meas: np.ndarray, valid: np.ndarray, k: int) -> np.ndarray:
    """Apply the L3 filter along the time axis of ``meas`` (N, K), resetting when ``valid`` turns on."""
    a = l3_filter_coefficient(k)
    n, kk = meas.shape
    out = np.full_like(meas, np.nan)
    prev = np.full(n, np.nan)
    prev_valid = np.zeros(n, dtype=bool)
    for j in range(kk):
        m = meas[:, j]
        v = valid[:, j]
        fresh = v & ~prev_valid
        cont = v & prev_valid
        cur = np.where(fresh, m, np.where(cont, (1.0 - a) * prev + a * m, np.nan))
        out[:, j] = cur
        prev = np.where(v, cur, np.nan)
        prev_valid = v
    return out


def measurement_stream(true_snr_db: np.ndarray, candidate_mask: np.ndarray, noise_std_db: float,
                       l3_k: int, rng: np.random.Generator) -> np.ndarray:
    """Noisy, L3-filtered measurements (N, K); NaN where the satellite is not a candidate."""
    noise = rng.standard_normal(true_snr_db.shape) * noise_std_db if noise_std_db > 0 else 0.0
    raw = true_snr_db + noise
    return l3_filter(raw, candidate_mask, l3_k)
