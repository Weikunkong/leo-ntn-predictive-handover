"""Large-scale channel parameters from 3GPP TR 38.811 (S-band).

Implemented: elevation-dependent line-of-sight probability (TR 38.811
Table 6.6.1-1) and the S-band shadow-fading standard deviation and clutter
loss (Tables 6.6.2-1 dense urban, 6.6.2-2 urban, 6.6.2-3 suburban/rural).
Values are tabulated for elevation angles 10°, 20°, ..., 90° and linearly
interpolated in between; below 10° the 10° value is used.

Not implemented: TR 38.811 fast-fading (CDL/TDL) models, the frequency
dependence of clutter loss, and the Ka-band tables. The tables were
transcribed from a public rendering of TR 38.811 and cross-checked against
the ns-3 implementation of the same model; see ``docs/literature_review.md``.
"""

from __future__ import annotations

import numpy as np

ELEVATIONS_DEG = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0])

# Table 6.6.1-1: LOS probability [%]
_LOS_PROB = {
    "dense_urban": [28.2, 33.1, 39.8, 46.8, 53.7, 61.2, 73.8, 82.0, 98.1],
    "urban": [24.6, 38.6, 49.3, 61.3, 72.6, 80.5, 91.9, 96.8, 99.2],
    "suburban": [78.2, 86.9, 91.9, 92.9, 93.5, 94.0, 94.9, 95.2, 99.8],
}

# Tables 6.6.2-1/-2/-3, S-band: shadow-fading sigma LOS [dB], sigma NLOS [dB], clutter loss NLOS [dB]
_SF_SIGMA_LOS = {
    "dense_urban": [3.5, 3.4, 2.9, 3.0, 3.1, 2.7, 2.5, 2.3, 1.2],
    "urban": [4.0] * 9,
    "suburban": [1.79, 1.14, 1.14, 0.92, 1.42, 1.56, 0.85, 0.72, 0.72],
}
_SF_SIGMA_NLOS = {
    "dense_urban": [15.5, 13.9, 12.4, 11.7, 10.6, 10.5, 10.1, 9.2, 9.2],
    "urban": [6.0] * 9,
    "suburban": [8.93, 9.08, 8.78, 10.25, 10.56, 10.74, 10.17, 11.52, 11.52],
}
_CLUTTER_LOSS = {
    "dense_urban": [34.3, 30.9, 29.0, 27.7, 26.8, 26.2, 25.8, 25.5, 25.5],
    "urban": [34.3, 30.9, 29.0, 27.7, 26.8, 26.2, 25.8, 25.5, 25.5],
    "suburban": [19.52, 18.17, 18.42, 18.28, 18.63, 17.68, 16.50, 16.30, 16.30],
}

ENVIRONMENTS = tuple(_LOS_PROB.keys())


def _check_env(environment: str) -> str:
    env = environment.lower()
    if env in ("rural", "suburban_rural"):
        env = "suburban"
    if env not in _LOS_PROB:
        raise ValueError(f"unknown environment {environment!r}; choose from {ENVIRONMENTS}")
    return env


def _interp(table: list[float], elevation_deg: np.ndarray | float) -> np.ndarray:
    el = np.clip(np.asarray(elevation_deg, dtype=np.float64), ELEVATIONS_DEG[0], ELEVATIONS_DEG[-1])
    return np.interp(el, ELEVATIONS_DEG, np.asarray(table, dtype=np.float64))


def los_probability(environment: str, elevation_deg: np.ndarray | float) -> np.ndarray:
    """LOS probability in [0, 1] (TR 38.811 Table 6.6.1-1, linearly interpolated)."""
    return _interp(_LOS_PROB[_check_env(environment)], elevation_deg) / 100.0


def shadow_fading_sigma_db(environment: str, elevation_deg: np.ndarray | float,
                           los: np.ndarray | bool) -> np.ndarray:
    """Shadow-fading standard deviation [dB] for LOS (``los=True``) or NLOS conditions."""
    env = _check_env(environment)
    s_los = _interp(_SF_SIGMA_LOS[env], elevation_deg)
    s_nlos = _interp(_SF_SIGMA_NLOS[env], elevation_deg)
    return np.where(np.asarray(los, dtype=bool), s_los, s_nlos)


def clutter_loss_db(environment: str, elevation_deg: np.ndarray | float) -> np.ndarray:
    """NLOS clutter loss [dB] (S-band). Zero clutter loss applies in LOS."""
    return _interp(_CLUTTER_LOSS[_check_env(environment)], elevation_deg)
