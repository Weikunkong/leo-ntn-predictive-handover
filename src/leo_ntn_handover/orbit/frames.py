"""Coordinate frames and look-angle geometry.

Conventions
-----------
* Positions in km, velocities in km/s, angles in radians unless the function
  name says ``_deg``.
* ``TEME`` is the inertial frame used by SGP4. It is rotated into an
  Earth-fixed frame with the Greenwich Mean Sidereal Time (GMST) only;
  polar motion and the UT1-UTC offset are neglected. The resulting frame is
  the "pseudo Earth-fixed" (PEF) frame, which differs from true ITRF/ECEF by
  a few hundred metres at LEO altitude - negligible for elevation/range
  geometry at the kilometre scale relevant to handover studies.
* Geodetic coordinates use the WGS84 ellipsoid.
"""

from __future__ import annotations

import numpy as np

from ..constants import JD_J2000, OMEGA_EARTH, WGS84_A, WGS84_E2


def gmst_rad(jd_ut1: np.ndarray | float) -> np.ndarray:
    """Greenwich Mean Sidereal Time (IAU 1982 expression, Vallado eq. 3-45).

    Parameters
    ----------
    jd_ut1:
        Julian date(s) in UT1 (UTC is used as an approximation).

    Returns
    -------
    GMST in radians, wrapped to [0, 2*pi).
    """
    jd = np.asarray(jd_ut1, dtype=np.float64)
    t_ut1 = (jd - JD_J2000) / 36525.0
    gmst_sec = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t_ut1
        + 0.093104 * t_ut1**2
        - 6.2e-6 * t_ut1**3
    )
    gmst = np.deg2rad((gmst_sec / 240.0) % 360.0)
    return gmst


def teme_to_ecef(
    r_teme: np.ndarray, v_teme: np.ndarray, jd_ut1: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Rotate TEME position/velocity into the Earth-fixed (PEF~ECEF) frame.

    Parameters
    ----------
    r_teme, v_teme:
        Arrays of shape (..., T, 3) [km, km/s].
    jd_ut1:
        Julian dates of shape (T,).

    Returns
    -------
    (r_ecef, v_ecef) with the same shapes as the inputs. The velocity is the
    velocity relative to the rotating Earth-fixed frame.
    """
    theta = gmst_rad(jd_ut1)
    c, s = np.cos(theta), np.sin(theta)
    x, y, z = r_teme[..., 0], r_teme[..., 1], r_teme[..., 2]
    r_ecef = np.stack([c * x + s * y, -s * x + c * y, z], axis=-1)
    vx, vy, vz = v_teme[..., 0], v_teme[..., 1], v_teme[..., 2]
    v_rot = np.stack([c * vx + s * vy, -s * vx + c * vy, vz], axis=-1)
    # subtract omega x r (omega along +z)
    omega_cross_r = np.stack(
        [-OMEGA_EARTH * r_ecef[..., 1], OMEGA_EARTH * r_ecef[..., 0], np.zeros_like(z)],
        axis=-1,
    )
    v_ecef = v_rot - omega_cross_r
    return r_ecef, v_ecef


def geodetic_to_ecef(lat_deg: np.ndarray | float, lon_deg: np.ndarray | float,
                     alt_m: np.ndarray | float = 0.0) -> np.ndarray:
    """Convert WGS84 geodetic coordinates to ECEF [km]. Broadcasts over inputs."""
    lat = np.deg2rad(np.asarray(lat_deg, dtype=np.float64))
    lon = np.deg2rad(np.asarray(lon_deg, dtype=np.float64))
    h = np.asarray(alt_m, dtype=np.float64)
    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat**2)
    x = (n + h) * cos_lat * np.cos(lon)
    y = (n + h) * cos_lat * np.sin(lon)
    z = (n * (1.0 - WGS84_E2) + h) * sin_lat
    return np.stack([x, y, z], axis=-1) / 1000.0


def ecef_to_enu_matrix(lat_deg: np.ndarray | float, lon_deg: np.ndarray | float) -> np.ndarray:
    """Rotation matrix (..., 3, 3) from ECEF to the local East-North-Up frame."""
    lat = np.deg2rad(np.asarray(lat_deg, dtype=np.float64))
    lon = np.deg2rad(np.asarray(lon_deg, dtype=np.float64))
    sl, cl = np.sin(lat), np.cos(lat)
    so, co = np.sin(lon), np.cos(lon)
    zero = np.zeros_like(lat)
    east = np.stack([-so, co, zero], axis=-1)
    north = np.stack([-sl * co, -sl * so, cl], axis=-1)
    up = np.stack([cl * co, cl * so, sl], axis=-1)
    return np.stack([east, north, up], axis=-2)


def look_angles(
    r_sat_ecef: np.ndarray,
    v_sat_ecef: np.ndarray,
    r_ue_ecef: np.ndarray,
    v_ue_ecef: np.ndarray,
    lat_deg: np.ndarray | float,
    lon_deg: np.ndarray | float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Elevation, azimuth, slant range and range rate of satellites seen from a UE.

    Parameters
    ----------
    r_sat_ecef, v_sat_ecef:
        Satellite ECEF position/velocity, shape (N, T, 3).
    r_ue_ecef, v_ue_ecef:
        UE ECEF position/velocity, shape (T, 3) (static UE: constant rows, zero velocity).
    lat_deg, lon_deg:
        UE geodetic latitude/longitude, shape (T,) or scalars.

    Returns
    -------
    elevation_deg (N, T), azimuth_deg (N, T), range_km (N, T), range_rate_km_s (N, T).
    A positive range rate means the satellite is receding from the UE.
    """
    d = r_sat_ecef - r_ue_ecef[None, :, :]
    rng = np.linalg.norm(d, axis=-1)
    unit = d / rng[..., None]
    rot = ecef_to_enu_matrix(lat_deg, lon_deg)  # (T,3,3) or (3,3)
    if rot.ndim == 2:
        enu = np.einsum("ij,ntj->nti", rot, unit)
    else:
        enu = np.einsum("tij,ntj->nti", rot, unit)
    elevation = np.rad2deg(np.arcsin(np.clip(enu[..., 2], -1.0, 1.0)))
    azimuth = np.rad2deg(np.arctan2(enu[..., 0], enu[..., 1])) % 360.0
    rel_v = v_sat_ecef - v_ue_ecef[None, :, :]
    range_rate = np.einsum("nti,nti->nt", unit, rel_v)
    return elevation, azimuth, rng, range_rate


def doppler_shift_hz(range_rate_km_s: np.ndarray, carrier_hz: float) -> np.ndarray:
    """Doppler shift [Hz] for a given range rate [km/s] (positive = approaching satellite)."""
    from ..constants import C_LIGHT

    return -(range_rate_km_s * 1000.0 / C_LIGHT) * carrier_hz
