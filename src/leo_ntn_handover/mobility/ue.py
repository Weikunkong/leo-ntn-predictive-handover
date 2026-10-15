"""Ground-user (UE) trajectory model.

The study considers a single UE that is either static or moves with constant
speed along a constant compass heading (great-circle motion on a sphere of
the local Earth radius). Because LEO satellites move at ~7.5 km/s relative
to the ground, even vehicular UE speeds (30 m/s) change the handover
geometry only marginally; the UE speed mainly matters through the temporal
correlation of shadowing, which is handled in the channel layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..orbit.frames import geodetic_to_ecef


@dataclass
class UETrajectory:
    """UE position over the simulation time grid."""

    t_s: np.ndarray           # (T,) time since start [s]
    lat_deg: np.ndarray       # (T,)
    lon_deg: np.ndarray       # (T,)
    alt_m: float
    r_ecef_km: np.ndarray     # (T, 3)
    v_ecef_km_s: np.ndarray   # (T, 3)

    @property
    def is_static(self) -> bool:
        return bool(np.allclose(self.v_ecef_km_s, 0.0))


def constant_velocity_trajectory(
    t_s: np.ndarray,
    lat0_deg: float,
    lon0_deg: float,
    alt_m: float = 0.0,
    speed_mps: float = 0.0,
    heading_deg: float = 90.0,
    earth_radius_m: float = 6_371_000.0,
) -> UETrajectory:
    """Great-circle motion with constant speed and initial heading.

    Parameters
    ----------
    t_s:
        Time grid [s].
    lat0_deg, lon0_deg, alt_m:
        Initial geodetic position.
    speed_mps:
        Ground speed [m/s]; 0 gives a static UE.
    heading_deg:
        Initial compass heading (0 = north, 90 = east).
    """
    t = np.asarray(t_s, dtype=np.float64)
    if speed_mps <= 0.0:
        lat = np.full_like(t, lat0_deg)
        lon = np.full_like(t, lon0_deg)
    else:
        d = speed_mps * t / earth_radius_m  # angular distance travelled [rad]
        phi1 = np.deg2rad(lat0_deg)
        lam1 = np.deg2rad(lon0_deg)
        theta = np.deg2rad(heading_deg)
        phi2 = np.arcsin(np.sin(phi1) * np.cos(d) + np.cos(phi1) * np.sin(d) * np.cos(theta))
        lam2 = lam1 + np.arctan2(np.sin(theta) * np.sin(d) * np.cos(phi1),
                                 np.cos(d) - np.sin(phi1) * np.sin(phi2))
        lat = np.rad2deg(phi2)
        lon = (np.rad2deg(lam2) + 180.0) % 360.0 - 180.0
    r = geodetic_to_ecef(lat, lon, alt_m)
    if speed_mps <= 0.0 or len(t) < 2:
        v = np.zeros_like(r)
    else:
        v = np.gradient(r, t, axis=0)
    return UETrajectory(t_s=t, lat_deg=lat, lon_deg=lon, alt_m=alt_m, r_ecef_km=r, v_ecef_km_s=v)
