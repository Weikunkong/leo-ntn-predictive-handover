from pathlib import Path

import numpy as np
import pytest

from leo_ntn_handover.config import SimConfig, load_config
from leo_ntn_handover.evaluation import compute_metrics
from leo_ntn_handover.simulation import build_scenario, run_algorithm

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "quickstart.yaml"


def test_config_loads_with_type_coercion_and_rejects_unknown_keys():
    cfg = load_config(CONFIG)
    assert isinstance(cfg.link.carrier_hz, float) and cfg.link.carrier_hz == 2.0e9
    assert cfg.constellation.n_sats == cfg.constellation.n_planes * cfg.constellation.sats_per_plane
    with pytest.raises(ValueError):
        SimConfig.from_dict({"link": {"not_a_key": 1}})
    new = cfg.with_override("measurement.noise_std_db", 3.0)
    assert new.measurement.noise_std_db == 3.0 and cfg.measurement.noise_std_db == 1.0
    new2 = cfg.with_override("constellation", {"n_planes": 3, "sats_per_plane": 4})
    assert new2.constellation.n_sats == 12
    assert cfg.geometry_key(0) != cfg.geometry_key(1)
    assert cfg.geometry_key(0) == new.geometry_key(0)  # noise does not change geometry
    assert cfg.geometry_key(0) != new2.geometry_key(0)


@pytest.mark.slow
def test_end_to_end_run_is_reproducible(tmp_path):
    cfg = load_config(CONFIG).with_override("time.duration_s", 60.0).with_override("time.tail_s", 300.0)
    cfg = cfg.with_override("constellation", {"n_planes": 12, "sats_per_plane": 12})
    sc1 = build_scenario(cfg, seed=3, cache_dir=tmp_path)
    sc2 = build_scenario(cfg, seed=3, cache_dir=tmp_path)  # second call hits the cache
    np.testing.assert_allclose(sc1.true_snr_db, sc2.true_snr_db)
    np.testing.assert_allclose(sc1.meas_db, sc2.meas_db, equal_nan=True)
    for name in ["greedy", "a3", "maxvis", "predictive"]:
        r1 = run_algorithm(sc1, name)
        r2 = run_algorithm(sc2, name)
        np.testing.assert_array_equal(r1.serving, r2.serving)
        m1, m2 = compute_metrics(r1), compute_metrics(r2)
        for key in ("ho_rate_per_h", "outage_prob", "mean_se_bps_hz"):
            assert m1[key] == m2[key]
        assert 0.0 <= m1["outage_prob"] <= 1.0
