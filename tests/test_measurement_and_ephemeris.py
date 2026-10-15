import numpy as np

from leo_ntn_handover.simulation.ephemeris import EphemerisOracle
from leo_ntn_handover.simulation.measurement import l3_filter, l3_filter_coefficient, measurement_stream
from tests.conftest import make_trace


def test_l3_filter_coefficient_and_recursion():
    assert l3_filter_coefficient(4) == 0.5
    assert l3_filter_coefficient(0) == 1.0
    meas = np.array([[10.0, 10.0, 10.0, 10.0]])
    valid = np.array([[False, True, True, True]])
    f = l3_filter(meas, valid, 4)
    assert np.isnan(f[0, 0]) and f[0, 1] == 10.0 and f[0, 3] == 10.0
    meas = np.array([[0.0, 10.0, 10.0]])
    valid = np.ones_like(meas, dtype=bool)
    f = l3_filter(meas, valid, 4)
    np.testing.assert_allclose(f[0], [0.0, 5.0, 7.5])


def test_measurement_stream_is_noise_free_when_std_zero():
    true = np.array([[1.0, 2.0, 3.0]])
    valid = np.ones_like(true, dtype=bool)
    m = measurement_stream(true, valid, 0.0, 0, np.random.default_rng(0))
    np.testing.assert_allclose(m, true)


def test_ephemeris_oracle_interpolation_and_timing_error():
    k = 11
    elev = np.full((1, k), 40.0)
    snr = np.arange(k, dtype=float)  # SNR = t (1 s grid)
    trace = make_trace(elev, snr[None, :], step_s=1.0)
    o = EphemerisOracle(trace)
    np.testing.assert_allclose(o.predicted_snr_db(np.array([0]), np.array([2.5, 7.0])), [[2.5, 7.0]])
    o_err = EphemerisOracle(trace, timing_error_s=2.0)
    np.testing.assert_allclose(o_err.predicted_snr_db(np.array([0]), np.array([2.5])), [[4.5]])
    # clipped at the end of the trace
    np.testing.assert_allclose(o.predicted_snr_db(np.array([0]), np.array([50.0])), [[10.0]])


def test_remaining_visible_time():
    elev = np.array([[45.0, 45.0, 45.0, 5.0, 5.0, 45.0]])
    trace = make_trace(elev, np.zeros_like(elev), step_s=2.0)
    np.testing.assert_allclose(trace.remaining_visible_s[0], [6.0, 4.0, 2.0, 0.0, 0.0, 2.0])
    o = EphemerisOracle(trace)
    assert o.predicted_remaining_visible_s(np.array([0]), 0.0)[0] == 6.0
    assert o.predicted_remaining_visible_s(np.array([0]), 2.0)[0] == 4.0
