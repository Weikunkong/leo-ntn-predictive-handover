"""Assemble a complete, seeded scenario (geometry + channel + measurements) and run algorithms on it.

Common random numbers: the channel realisation and the measurement noise of a
seed are drawn from generators derived from ``(seed, salt)``, so that all
algorithms - and all sweep levels that do not change the geometry - see
identical fading and noise. The measurement noise is generated as unit-variance
noise and scaled by ``noise_std_db``, hence noise-level sweeps are paired as well.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..channel.fading import ChannelRealization, generate_channel_realization
from ..config import SimConfig
from ..handover.base import HandoverAlgorithm
from ..handover.registry import build_algorithm
from .engine import RunResult, SimulationEngine
from .ephemeris import EphemerisOracle
from .geometry import GeometryTrace, build_geometry_trace
from .measurement import l3_filter

CHANNEL_SALT = 1_000_003
MEASUREMENT_SALT = 2_000_003


@dataclass
class ScenarioData:
    cfg: SimConfig
    seed: int
    trace: GeometryTrace
    channel: ChannelRealization
    true_snr_db: np.ndarray      # (N, K)
    meas_db: np.ndarray          # (N, K) L3-filtered measurements (nan when not a candidate)
    oracle: EphemerisOracle

    @property
    def n_steps(self) -> int:
        return self.trace.n_steps


def build_scenario(cfg: SimConfig, seed: int, cache_dir: str | Path | None = "data/cache",
                   trace: GeometryTrace | None = None) -> ScenarioData:
    """Build all seed-dependent inputs for one simulation run."""
    if trace is None:
        trace = build_geometry_trace(cfg, seed, cache_dir=cache_dir)
    K = trace.n_steps
    elev = trace.elevation_deg[:, :K]
    cand = trace.candidate_mask[:, :K]

    rng_ch = np.random.default_rng([seed, CHANNEL_SALT])
    channel = generate_channel_realization(
        elev, trace.step_s, rng_ch, environment=cfg.channel.environment,
        enable_blockage=cfg.channel.enable_blockage, enable_shadowing=cfg.channel.enable_shadowing,
        nlos_mean_duration_s=cfg.channel.nlos_mean_duration_s,
        shadow_decorr_time_s=cfg.channel.shadow_decorr_time_s,
    )
    true_snr = trace.snr_geo_db[:, :K] - channel.extra_loss_db

    rng_m = np.random.default_rng([seed, MEASUREMENT_SALT])
    unit_noise = rng_m.standard_normal(true_snr.shape)
    raw = true_snr + cfg.measurement.noise_std_db * unit_noise
    meas = l3_filter(raw, cand, cfg.measurement.l3_filter_k)

    oracle = EphemerisOracle(trace, timing_error_s=cfg.ephemeris.timing_error_s,
                             max_lookahead_s=cfg.ephemeris.max_lookahead_s)
    return ScenarioData(cfg=cfg, seed=seed, trace=trace, channel=channel, true_snr_db=true_snr,
                        meas_db=meas, oracle=oracle)


def make_engine(sc: ScenarioData) -> SimulationEngine:
    h = sc.cfg.handover
    return SimulationEngine(sc.trace, sc.true_snr_db, sc.meas_db, h.snr_min_db, h.execution_delay_s,
                            h.link_loss_timeout_s, h.recovery_delay_s)


def run_algorithm(sc: ScenarioData, algorithm: str | HandoverAlgorithm) -> RunResult:
    """Run one algorithm (by name or instance) on a prepared scenario."""
    algo = build_algorithm(algorithm, sc.cfg.handover.params) if isinstance(algorithm, str) else algorithm
    engine = make_engine(sc)
    oracle = sc.oracle if algo.uses_ephemeris else None
    return engine.run(algo, oracle)
