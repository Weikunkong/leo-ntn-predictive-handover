import numpy as np

from leo_ntn_handover.constants import OMEGA_EARTH, WGS84_A, WGS84_B
from leo_ntn_handover.orbit.frames import (
    doppler_shift_hz,
    ecef_to_enu_matrix,
    geodetic_to_ecef,
    gmst_rad,
    look_angles,
    teme_to_ecef,
)


def test_gmst_at_j2000_matches_reference():
    # GMST at J2000.0 (2000-01-01 12:00 UT1) is 18h 41m 50.548s = 280.4606 deg (Vallado)
    assert abs(np.rad2deg(gmst_rad(2451545.0)) - 280.4606) < 1e-3


def test_geodetic_to_ecef_on_axes():
    np.testing.assert_allclose(geodetic_to_ecef(0.0, 0.0, 0.0), [WGS84_A / 1e3, 0, 0], atol=1e-9)
    np.testing.assert_allclose(geodetic_to_ecef(90.0, 0.0, 0.0), [0, 0, WGS84_B / 1e3], atol=1e-6)
    np.testing.assert_allclose(geodetic_to_ecef(0.0, 90.0, 1000.0), [0, WGS84_A / 1e3 + 1.0, 0], atol=1e-6)


def test_enu_matrix_is_orthonormal():
    m = ecef_to_enu_matrix(49.57, 11.03)
    np.testing.assert_allclose(m @ m.T, np.eye(3), atol=1e-12)


def test_look_angles_zenith_and_horizon():
    lat, lon = 30.0, 40.0
    r_ue = geodetic_to_ecef(lat, lon, 0.0)
    up = ecef_to_enu_matrix(lat, lon)[2]
    east = ecef_to_enu_matrix(lat, lon)[0]
    r_sat = np.stack([r_ue + 600.0 * up, r_ue + 2000.0 * east])[:, None, :]  # (2, 1, 3)
    v_sat = np.zeros_like(r_sat)
    el, az, rng, rr = look_angles(r_sat, v_sat, r_ue[None, :], np.zeros((1, 3)), lat, lon)
    assert abs(el[0, 0] - 90.0) < 1e-6
    assert abs(rng[0, 0] - 600.0) < 1e-9
    assert abs(el[1, 0]) < 1e-6 and abs(az[1, 0] - 90.0) < 1e-6
    assert np.allclose(rr, 0.0)


def test_range_rate_sign_and_doppler():
    lat, lon = 0.0, 0.0
    r_ue = geodetic_to_ecef(lat, lon, 0.0)
    up = ecef_to_enu_matrix(lat, lon)[2]
    r_sat = (r_ue + 600.0 * up)[None, None, :]
    v_sat = (7.5 * up)[None, None, :]  # moving straight up = receding
    _, _, _, rr = look_angles(r_sat, v_sat, r_ue[None, :], np.zeros((1, 3)), lat, lon)
    assert abs(rr[0, 0] - 7.5) < 1e-9
    assert doppler_shift_hz(rr, 2.0e9)[0, 0] < 0  # receding -> negative Doppler


def test_teme_to_ecef_removes_earth_rotation_velocity():
    # a point fixed in TEME has velocity -omega x r in the rotating frame
    jd = np.array([2451545.0])
    r = np.array([[[7000.0, 0.0, 0.0]]])
    v = np.zeros_like(r)
    r_e, v_e = teme_to_ecef(r, v, jd)
    assert abs(np.linalg.norm(r_e) - 7000.0) < 1e-9
    assert abs(np.linalg.norm(v_e) - OMEGA_EARTH * 7000.0) < 1e-9
