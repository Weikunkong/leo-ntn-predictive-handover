"""Walker-delta constellation generator.

A Walker-delta constellation ``i: T/P/F`` has ``T`` satellites in ``P``
equally spaced circular orbital planes of inclination ``i``; the phasing
parameter ``F`` sets the relative in-plane offset between neighbouring
planes. The satellites are created as SGP4 records (mean elements) so that
synthetic and real (TLE/OMM) constellations share the same propagator.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sgp4.api import WGS72, Satrec, jday

from ..constants import EARTH_RADIUS_KM, JD_1949_12_31, MU_EARTH_KM3_S2


def mean_motion_rad_per_min(altitude_km: float) -> float:
    """Keplerian mean motion [rad/min] of a circular orbit at ``altitude_km``."""
    a = EARTH_RADIUS_KM + altitude_km
    n_rad_s = math.sqrt(MU_EARTH_KM3_S2 / a**3)
    return n_rad_s * 60.0


def orbital_period_s(altitude_km: float) -> float:
    """Keplerian orbital period [s] of a circular orbit at ``altitude_km``."""
    return 2.0 * math.pi / (mean_motion_rad_per_min(altitude_km) / 60.0)


def walker_delta_satrecs(
    altitude_km: float,
    inclination_deg: float,
    n_planes: int,
    sats_per_plane: int,
    phasing: int = 1,
    epoch: datetime | None = None,
    raan_offset_deg: float = 0.0,
    eccentricity: float = 1e-4,
) -> tuple[list[Satrec], list[str]]:
    """Create SGP4 satellite records for a Walker-delta constellation.

    Parameters
    ----------
    altitude_km, inclination_deg:
        Orbit altitude above the mean Earth radius and inclination.
    n_planes, sats_per_plane:
        Number of orbital planes and satellites per plane.
    phasing:
        Walker phasing parameter F (0 <= F < n_planes).
    epoch:
        Epoch (UTC) of the mean elements. Default: 2026-01-01T00:00:00Z.
    raan_offset_deg:
        Rotation applied to all RAAN values (constellation phase).
    eccentricity:
        Small eccentricity used for numerical robustness of SGP4 (default 1e-4).

    Returns
    -------
    (satrecs, names) where ``names`` are ``"W{plane:02d}-{index:02d}"``.
    """
    if not (0 <= phasing < n_planes):
        raise ValueError("phasing must satisfy 0 <= F < n_planes")
    if epoch is None:
        epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)
    jd, fr = jday(epoch.year, epoch.month, epoch.day, epoch.hour, epoch.minute,
                  epoch.second + epoch.microsecond * 1e-6)
    epoch_days_1949 = (jd - JD_1949_12_31) + fr

    total = n_planes * sats_per_plane
    no_kozai = mean_motion_rad_per_min(altitude_km)
    inclo = math.radians(inclination_deg)

    satrecs: list[Satrec] = []
    names: list[str] = []
    satnum = 1
    for p in range(n_planes):
        raan = math.radians((360.0 * p / n_planes + raan_offset_deg) % 360.0)
        for s in range(sats_per_plane):
            mean_anomaly = (2.0 * math.pi * s / sats_per_plane
                            + 2.0 * math.pi * phasing * p / total) % (2.0 * math.pi)
            rec = Satrec()
            rec.sgp4init(
                WGS72,          # gravity model (TLE standard)
                "i",            # improved mode
                satnum,         # satellite number
                epoch_days_1949,
                0.0,            # bstar [1/earth radii] - no drag for the synthetic constellation
                0.0,            # ndot (unused by SGP4)
                0.0,            # nddot (unused by SGP4)
                eccentricity,
                0.0,            # argument of perigee [rad]
                inclo,
                mean_anomaly,
                no_kozai,
                raan,
            )
            satrecs.append(rec)
            names.append(f"W{p:02d}-{s:02d}")
            satnum += 1
    return satrecs, names
