"""Ephemeris oracle: what the UE *believes* about future satellite geometry.

The UE derives satellite positions from broadcast ephemeris (SIB19 in 3GPP
Rel-17 NTN). We model imperfect ephemeris knowledge with a single, physically
interpretable parameter: an along-track **timing error** ``timing_error_s``.
A stale or offset ephemeris makes the UE evaluate the orbit at the wrong
time, i.e. the predicted state at time ``t`` equals the true state at
``t + timing_error_s``. At LEO speeds (~7.5 km/s) one second of timing error
corresponds to ~7.5 km of along-track position error; SGP4 ephemeris errors
are dominated by the along-track component, which justifies the choice.

Predictions use the geometry-only SNR (free-space propagation, no fading or
blockage): the UE cannot predict shadowing from ephemeris, which is exactly
why a measurement-based correction is part of the proposed method.
"""

from __future__ import annotations

import numpy as np

from .geometry import GeometryTrace


class EphemerisOracle:
    """Interpolating access to predicted geometry with an optional timing error."""

    def __init__(self, trace: GeometryTrace, timing_error_s: float = 0.0,
                 max_lookahead_s: float = 900.0) -> None:
        self.trace = trace
        self.timing_error_s = float(timing_error_s)
        self.max_lookahead_s = float(max_lookahead_s)
        self._step = trace.step_s
        self._kmax = trace.elevation_deg.shape[1] - 1

    # ------------------------------------------------------------------ helpers
    def _frac_index(self, t_abs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x = np.clip((np.asarray(t_abs, dtype=np.float64) + self.timing_error_s) / self._step, 0.0, self._kmax)
        i0 = np.floor(x).astype(int)
        i1 = np.minimum(i0 + 1, self._kmax)
        w = x - i0
        return i0, i1, w

    def _interp(self, arr: np.ndarray, sats: np.ndarray, t_abs: np.ndarray) -> np.ndarray:
        """Linear interpolation of ``arr[sats, t]`` with broadcasting over sats x times."""
        sats = np.asarray(sats, dtype=int)
        i0, i1, w = self._frac_index(t_abs)
        s = sats[:, None] if sats.ndim == 1 else sats
        return (1.0 - w) * arr[s, i0] + w * arr[s, i1]

    # ------------------------------------------------------------------ API
    def predicted_snr_db(self, sats: np.ndarray, t_abs: np.ndarray) -> np.ndarray:
        """Predicted geometry-only SNR [dB], shape (len(sats), len(t_abs))."""
        return self._interp(self.trace.snr_geo_db, sats, t_abs)

    def predicted_elevation_deg(self, sats: np.ndarray, t_abs: np.ndarray) -> np.ndarray:
        """Predicted elevation [deg], shape (len(sats), len(t_abs))."""
        return self._interp(self.trace.elevation_deg, sats, t_abs)

    def predicted_remaining_visible_s(self, sats: np.ndarray, t_abs: float) -> np.ndarray:
        """Predicted time [s] each satellite stays above the minimum elevation (nearest grid point)."""
        i0, _i1, w = self._frac_index(np.asarray([t_abs]))
        i = i0[0] + int(w[0] >= 0.5)
        rem = self.trace.remaining_visible_s[np.asarray(sats, dtype=int), min(i, self._kmax)]
        return np.minimum(rem, self.max_lookahead_s)

    def predicted_candidate(self, sats: np.ndarray, t_abs: np.ndarray) -> np.ndarray:
        """Predicted eligibility (elevation above the minimum), shape (len(sats), len(t_abs))."""
        return self.predicted_elevation_deg(sats, t_abs) >= self.trace.min_elevation_deg
