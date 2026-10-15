import numpy as np
import pytest

from leo_ntn_handover.handover import (
    A3Handover,
    GreedyHandover,
    MaxVisibilityHandover,
    Observation,
    PredictiveHandover,
    build_algorithm,
)
from leo_ntn_handover.simulation.ephemeris import EphemerisOracle


def obs(serving: int, meas: list[float], t: float = 0.0, step: float = 1.0) -> Observation:
    return Observation(k=int(t / step), t=t, step_s=step, serving=serving,
                       candidates=np.arange(len(meas)), meas_db=np.array(meas, dtype=float), snr_min_db=0.0)


def test_greedy_switches_to_strongest():
    g = GreedyHandover()
    assert g.decide(obs(0, [10.0, 12.0])) == 1
    assert g.decide(obs(0, [12.0, 10.0])) == 0
    assert GreedyHandover(tolerance_db=3.0).decide(obs(0, [10.0, 12.0])) == 0


def test_a3_requires_hysteresis_and_time_to_trigger():
    a3 = A3Handover(hysteresis_db=3.0, ttt_s=2.0)
    a3.reset()
    # neighbour better by only 2 dB: never triggers
    for t in range(5):
        assert a3.decide(obs(0, [10.0, 12.0], t=t)) == 0
    a3.reset()
    # better by 4 dB: condition holds from t=0, trigger once it has held for 2 s (t=2)
    assert a3.decide(obs(0, [10.0, 14.0], t=0)) == 0
    assert a3.decide(obs(0, [10.0, 14.0], t=1)) == 0
    assert a3.decide(obs(0, [10.0, 14.0], t=2)) == 1
    a3.reset()
    # interruption of the condition resets the timer
    assert a3.decide(obs(0, [10.0, 14.0], t=0)) == 0
    assert a3.decide(obs(0, [10.0, 11.0], t=1)) == 0
    assert a3.decide(obs(0, [10.0, 14.0], t=2)) == 0
    assert a3.decide(obs(0, [10.0, 14.0], t=3)) == 0
    assert a3.decide(obs(0, [10.0, 14.0], t=4)) == 1
    # ttt = 0 triggers immediately
    assert A3Handover(3.0, 0.0).decide(obs(0, [10.0, 14.0])) == 1


def test_maxvis_keeps_serving_until_guard_time(two_sat_trace):
    o = EphemerisOracle(two_sat_trace)
    mv = MaxVisibilityHandover(guard_time_s=5.0)
    # S0 is a candidate until t = 50 s -> remaining 50 s at t=0: stay
    assert mv.decide(obs(0, [15.0, -10.0], t=0.0), o) == 0
    # at t = 46 s remaining = 4 s < guard -> switch to S1
    assert mv.decide(obs(0, [1.0, 9.0], t=46.0), o) == 1
    with pytest.raises(ValueError):
        mv.decide(obs(0, [1.0, 9.0]), None)


def test_predictive_prefers_rising_satellite_and_respects_margin(two_sat_trace):
    o = EphemerisOracle(two_sat_trace)
    p = PredictiveHandover(horizon_s=20.0, n_samples=5, margin_db=2.0, use_bias_correction=False)
    p.reset()
    # t = 28: S0 at ~3.2 dB falling, S1 at ~1.8 dB rising. Over the next 20 s S0 drops below 0 dB
    # (penalised) while S1 climbs -> predictive hands over although S0 is currently stronger.
    assert p.decide(obs(0, [3.2, 1.8], t=28.0), o) == 1
    # t = 0: S0 far better over the horizon -> stay
    assert p.decide(obs(0, [15.0, -10.0], t=0.0), o) == 0
    # with a huge margin no handover happens even when S1 is better, unless S0 is predicted to set
    p_big = PredictiveHandover(horizon_s=5.0, n_samples=2, margin_db=100.0, use_bias_correction=False)
    assert p_big.decide(obs(0, [10.0, 11.0], t=35.0), o) == 0
    assert p_big.decide(obs(0, [1.0, 10.0], t=47.0), o) == 1  # S0 leaves candidate set at 50 s (horizon 5 s)


def test_predictive_bias_correction_reacts_to_blockage(two_sat_trace):
    o = EphemerisOracle(two_sat_trace)
    p = PredictiveHandover(horizon_s=10.0, n_samples=5, margin_db=2.0, bias_alpha=1.0, use_bias_correction=True)
    p.reset()
    # Geometry says S0 (~15 dB) >> S1 (~-10 dB) at t=0, but S0 is measured blocked (-5 dB) while S1 is
    # measured at 12 dB: the corrected prediction must switch to S1.
    assert p.decide(obs(0, [-5.0, 12.0], t=0.0), o) == 1
    p2 = PredictiveHandover(horizon_s=10.0, n_samples=5, margin_db=2.0, use_bias_correction=False)
    assert p2.decide(obs(0, [-5.0, 12.0], t=0.0), o) == 0  # pure ephemeris ignores the measurement


def test_predictive_never_targets_currently_unusable_candidate(two_sat_trace):
    o = EphemerisOracle(two_sat_trace)
    p = PredictiveHandover(horizon_s=20.0, margin_db=0.0, eligibility_margin_db=1.0, use_bias_correction=False)
    # at t = 40 S1 is geometrically better but measured below the eligibility threshold
    assert p.decide(obs(0, [2.0, -3.0], t=40.0), o) == 0


def test_registry_builds_ablations_from_base_params():
    params = {"predictive": {"horizon_s": 30.0, "margin_db": 4.0}}
    base = build_algorithm("predictive", params)
    nocorr = build_algorithm("predictive_nocorr", params)
    nomargin = build_algorithm("predictive_nomargin", params)
    assert isinstance(base, PredictiveHandover) and base.horizon_s == 30.0 and base.use_bias_correction
    assert nocorr.name == "predictive_nocorr" and not nocorr.use_bias_correction and nocorr.horizon_s == 30.0
    assert nomargin.margin_db == 0.0 and nomargin.horizon_s == 30.0
    with pytest.raises(ValueError):
        build_algorithm("does_not_exist")
