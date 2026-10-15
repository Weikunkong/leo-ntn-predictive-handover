import numpy as np

from leo_ntn_handover.evaluation import compute_metrics, mean_ci, paired_diff_ci
from leo_ntn_handover.handover import GreedyHandover, MaxVisibilityHandover, PredictiveHandover
from leo_ntn_handover.simulation.engine import SimulationEngine
from leo_ntn_handover.simulation.ephemeris import EphemerisOracle
from tests.conftest import make_trace


def engine_for(trace, true_snr, meas, delay=0.0, timeout=1.0, recovery=0.5):
    return SimulationEngine(trace, true_snr, meas, snr_min_db=0.0, execution_delay_s=delay,
                            link_loss_timeout_s=timeout, recovery_delay_s=recovery)


def test_greedy_crossing_produces_one_handover_without_outage(two_sat_trace):
    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps]
    eng = engine_for(tr, true, true, delay=0.0)
    res = eng.run(GreedyHandover())
    kinds = [e.kind for e in res.events]
    assert kinds.count("ho_start") == 1 and kinds.count("ho_success") == 1
    assert res.serving[0] == 0 and res.serving[-1] == 1
    m = compute_metrics(res)
    assert m["outage_prob"] == 0.0 and m["link_loss_rate_per_h"] == 0.0
    assert m["ho_rate_per_h"] == 60.0  # 1 handover per simulated minute


def test_execution_delay_is_booked_as_interruption(two_sat_trace):
    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps]
    res = engine_for(tr, true, true, delay=0.4).run(GreedyHandover())
    # one handover with 0.4 s interruption inside a 1 s step
    assert abs(res.interrupted.sum() - 0.4) < 1e-9
    m = compute_metrics(res)
    assert abs(m["outage_prob"] - 0.4 / tr.n_steps) < 1e-9
    assert abs(m["interruption_frac"] - 0.4 / tr.n_steps) < 1e-9
    assert abs(m["mean_outage_duration_s"] - 0.4) < 1e-9
    res2 = engine_for(tr, true, true, delay=2.5).run(GreedyHandover())
    assert abs(res2.interrupted.sum() - 2.5) < 1e-9  # multi-step execution


def test_handover_failure_when_target_unusable_at_completion(two_sat_trace):
    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps].copy()
    meas = true.copy()
    # make S1 look strong in the measurements at t=5 only, while it is truly unusable
    meas[1, 5] = 50.0
    res = engine_for(tr, true, meas, delay=0.0, recovery=0.0).run(GreedyHandover())
    kinds = [e.kind for e in res.events]
    assert "ho_fail" in kinds and "rec_start" in kinds
    m = compute_metrics(res)
    assert m["ho_failure_rate"] > 0


class StayHandover(GreedyHandover):
    """Never hands over (used to exercise the engine's link-loss / recovery logic)."""

    name = "stay"

    def decide(self, obs, oracle=None):
        return obs.serving


def test_link_loss_after_timeout_and_recovery(two_sat_trace):
    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps].copy()
    true[0, 10:14] = -20.0  # blockage of S0 for 4 s (t = 10..13); S1 is still unusable (-6 dB)
    meas = true.copy()
    res = engine_for(tr, true, meas, delay=0.0, timeout=2.0, recovery=0.5).run(StayHandover())
    kinds = [e.kind for e in res.events]
    # loss declared after 2 s below threshold (t = 11), no usable candidate until S0 recovers at t = 14,
    # then a recovery to S0 with 0.5 s delay
    assert kinds[:2] == ["link_loss", "rec_start"]
    loss = [e for e in res.events if e.kind == "link_loss"][0]
    assert loss.t == 11.0
    rec = [e for e in res.events if e.kind == "rec_start"][0]
    assert rec.t == 14.0 and rec.target == 0
    m = compute_metrics(res)
    assert m["quality_outage_frac"] > 0 and m["disconnected_frac"] > 0
    # outage: 2 s below threshold + 2 s disconnected + 0.5 s recovery, plus the S0 setting later
    assert m["outage_prob"] > 4.5 / tr.n_steps


def test_pingpong_detection():
    k = 40
    elev = np.full((2, k), 45.0)
    # S0 and S1 alternate as the strongest every 3 s
    snr = np.zeros((2, k))
    snr[0] = 10.0 + 2.0 * np.sign(np.sin(2 * np.pi * np.arange(k) / 6.0 + 1e-9))
    snr[1] = 10.0
    tr = make_trace(elev, snr)
    res = engine_for(tr, snr, snr, delay=0.0).run(GreedyHandover())
    m = compute_metrics(res, pingpong_window_s=10.0)
    assert m["n_ho_attempts"] >= 6
    assert m["pingpong_rate"] > 0.8
    assert m["mean_time_of_stay_s"] <= 3.0 + 1e-9
    m_short = compute_metrics(res, pingpong_window_s=1.0)
    assert m_short["pingpong_rate"] == 0.0


def test_predictive_avoids_setting_satellite_outage(two_sat_trace):
    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps]
    oracle = EphemerisOracle(tr)
    algo = PredictiveHandover(horizon_s=10.0, use_bias_correction=False)
    res = engine_for(tr, true, true, delay=0.0).run(algo, oracle)
    assert res.serving[-1] == 1
    assert not any(e.kind == "link_loss" for e in res.events)
    assert compute_metrics(res)["outage_prob"] == 0.0


def test_maxvis_hands_over_before_elevation_mask_but_ignores_link_quality(two_sat_trace):
    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps]
    oracle = EphemerisOracle(tr)
    # with a permissive SNR threshold the ephemeris-only rule hands over just before S0 sets (t = 45)
    eng = SimulationEngine(tr, true, true, snr_min_db=-15.0, execution_delay_s=0.0,
                           link_loss_timeout_s=1.0, recovery_delay_s=0.5)
    res = eng.run(MaxVisibilityHandover(5.0), oracle)
    starts = [e for e in res.events if e.kind == "ho_start"]
    assert len(starts) == 1 and starts[0].t == 45.0 and res.serving[-1] == 1
    # with the 0 dB threshold S0 becomes unusable at t ~ 35 s, which the rule cannot see -> link loss
    res2 = engine_for(tr, true, true, delay=0.0).run(MaxVisibilityHandover(5.0), oracle)
    assert any(e.kind == "link_loss" for e in res2.events)


def test_engine_rejects_decisions_outside_candidate_set(two_sat_trace):
    class Bad(GreedyHandover):
        def decide(self, obs, oracle=None):
            return 99

    tr = two_sat_trace
    true = tr.snr_geo_db[:, : tr.n_steps]
    try:
        engine_for(tr, true, true).run(Bad())
    except (RuntimeError, IndexError):
        return
    raise AssertionError("engine accepted an invalid target")


def test_statistics_helpers():
    m, h, n = mean_ci(np.array([1.0, 2.0, 3.0, 4.0]))
    assert m == 2.5 and n == 4 and 1.5 < h < 2.5
    m, h, p = paired_diff_ci(np.array([1.0, 2.0, 3.0]), np.array([0.0, 1.0, 2.0]))
    assert m == 1.0 and abs(h) < 1e-9 and p == 0.0
    m, h, n = mean_ci(np.array([np.nan, 1.0]))
    assert m == 1.0 and np.isnan(h) and n == 1
