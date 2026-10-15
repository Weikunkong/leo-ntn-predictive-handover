"""SGP4 propagation of a set of satellites and conversion to the Earth-fixed frame."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sgp4.api import Satrec, SatrecArray, jday

from .frames import teme_to_ecef


def julian_dates(start_utc: datetime, t_seconds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Julian date pairs ``(jd, fr)`` for ``start_utc + t_seconds`` (SGP4 convention)."""
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    jd0, fr0 = jday(start_utc.year, start_utc.month, start_utc.day, start_utc.hour,
                    start_utc.minute, start_utc.second + start_utc.microsecond * 1e-6)
    t = np.asarray(t_seconds, dtype=np.float64)
    jd = np.full_like(t, jd0)
    fr = fr0 + t / 86400.0
    return jd, fr


@dataclass
class Constellation:
    """A set of SGP4 satellite records with vectorised propagation."""

    satrecs: list[Satrec]
    names: list[str]

    def __post_init__(self) -> None:
        if len(self.satrecs) != len(self.names):
            raise ValueError("satrecs and names must have the same length")
        self._array = SatrecArray(self.satrecs)

    def __len__(self) -> int:
        return len(self.satrecs)

    def propagate_teme(self, jd: np.ndarray, fr: np.ndarray,
                       chunk: int = 256) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Propagate all satellites to the given epochs.

        Returns ``(r_teme, v_teme, err)`` with shapes (N, T, 3), (N, T, 3), (N, T)
        in km and km/s. Non-zero ``err`` entries flag SGP4 failures (e.g. decayed orbits).
        """
        n = len(self.satrecs)
        t = len(jd)
        r = np.empty((n, t, 3), dtype=np.float64)
        v = np.empty((n, t, 3), dtype=np.float64)
        err = np.empty((n, t), dtype=np.int8)
        # chunk over time to bound memory; SatrecArray handles all satellites at once
        for i0 in range(0, t, chunk):
            sl = slice(i0, min(i0 + chunk, t))
            e, rr, vv = self._array.sgp4(jd[sl], fr[sl])
            r[:, sl, :] = rr
            v[:, sl, :] = vv
            err[:, sl] = e
        return r, v, err

    def propagate_ecef(self, start_utc: datetime, t_seconds: np.ndarray
                       ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Propagate and rotate into the Earth-fixed frame.

        Returns ``(r_ecef, v_ecef, err)``; see :meth:`propagate_teme` for shapes.
        """
        jd, fr = julian_dates(start_utc, t_seconds)
        r_teme, v_teme, err = self.propagate_teme(jd, fr)
        r_ecef, v_ecef = teme_to_ecef(r_teme, v_teme, jd + fr)
        return r_ecef, v_ecef, err
