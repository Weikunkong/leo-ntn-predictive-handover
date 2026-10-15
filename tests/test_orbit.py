import os

import numpy as np
import sgp4
from datetime import datetime, timezone

from leo_ntn_handover.orbit import Constellation, julian_dates, load_satellites, walker_delta_satrecs
from leo_ntn_handover.orbit.tle import write_tle_file
from leo_ntn_handover.orbit.walker import orbital_period_s


def test_walker_constellation_size_and_geometry():
    sats, names = walker_delta_satrecs(550.0, 53.0, 6, 4, phasing=1)
    assert len(sats) == 24 and len(set(names)) == 24
    con = Constellation(sats, names)
    t = np.arange(0, 6000, 60.0)
    r, v, err = con.propagate_ecef(datetime(2026, 1, 1, tzinfo=timezone.utc), t)
    assert not err.any()
    radius = np.linalg.norm(r, axis=-1)
    # circular orbit at 550 km above the 6371 km mean radius (SGP4 periodic terms: a few km)
    assert radius.min() > 6371 + 550 - 25 and radius.max() < 6371 + 550 + 25
    speed = np.linalg.norm(v, axis=-1)
    assert 6.8 < speed.mean() < 7.8  # ECEF speed (inertial ~7.59 km/s minus Earth rotation)
    # latitude never exceeds the inclination
    lat = np.rad2deg(np.arcsin(r[..., 2] / radius))
    assert np.abs(lat).max() < 53.0 + 0.5


def test_walker_period_matches_kepler():
    sats, names = walker_delta_satrecs(550.0, 53.0, 1, 1, phasing=0)
    con = Constellation(sats, names)
    period = orbital_period_s(550.0)
    t = np.array([0.0, period])
    jd, fr = julian_dates(datetime(2026, 1, 1, tzinfo=timezone.utc), t)
    r, _, _ = con.propagate_teme(jd, fr)
    # after one Keplerian period the satellite is close to its initial inertial position
    # (J2 nodal/apsidal drift of a few km per orbit is expected)
    assert np.linalg.norm(r[0, 1] - r[0, 0]) < 60.0


def test_tle_loader_on_sgp4_verification_set(tmp_path):
    path = os.path.join(os.path.dirname(sgp4.__file__), "SGP4-VER.TLE")
    sats, names = load_satellites(path)
    assert len(sats) > 10 and names[0].startswith("NORAD")
    # round trip through the 3-line writer
    out = tmp_path / "subset.tle"
    write_tle_file(out, sats[:3], ["A", "B", "C"])
    sats2, names2 = load_satellites(out)
    assert names2 == ["A", "B", "C"]
    assert [s.satnum for s in sats2] == [s.satnum for s in sats[:3]]
    assert load_satellites(out, name_filter="b")[1] == ["B"]
    assert len(load_satellites(out, max_sats=2)[0]) == 2
