"""Time-correlated LOS/NLOS blockage and shadow fading for every tracked satellite link.

Model (simplified, TR 38.811-inspired; see ``docs/methodology.md``):

* **Blockage state** - a two-state Markov chain {LOS, NLOS} per satellite link,
  sampled on the simulation time grid. Its stationary LOS probability equals
  the TR 38.811 LOS probability at the current elevation angle and the mean
  NLOS sojourn time ``nlos_mean_duration_s`` is a free parameter. The LOS
  sojourn time follows from the stationary distribution.
* **Shadow fading** - a unit-variance first-order Gauss-Markov (AR(1)) process
  with decorrelation time ``shadow_decorr_time_s``, scaled by the TR 38.811
  LOS/NLOS standard deviation at the current elevation (the scaling jumps at
  blockage transitions, so that the fading statistics are exactly the
  tabulated ones in each state).
* **Clutter loss** - the TR 38.811 NLOS clutter loss is added while the link is in NLOS.

The resulting *additional loss* is ``clutter_loss * [NLOS] + shadow_fading`` and is
subtracted from the geometry-only SNR. Fast fading is not modelled: the handover
decisions operate on L3-filtered measurements whose averaging window is long
compared with the fast-fading coherence time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .tr38811 import clutter_loss_db, los_probability, shadow_fading_sigma_db


@dataclass
class ChannelRealization:
    """One random realisation of the large-scale channel for all tracked satellites."""

    nlos: np.ndarray             # (N, K) bool, True while the link is blocked
    shadow_db: np.ndarray        # (N, K) shadow fading [dB] (positive = extra loss)
    clutter_db: np.ndarray       # (N, K) clutter loss [dB] applied (0 in LOS)

    @property
    def extra_loss_db(self) -> np.ndarray:
        return self.clutter_db + self.shadow_db


def generate_channel_realization(
    elevation_deg: np.ndarray,
    step_s: float,
    rng: np.random.Generator,
    environment: str = "suburban",
    enable_blockage: bool = True,
    enable_shadowing: bool = True,
    nlos_mean_duration_s: float = 4.0,
    shadow_decorr_time_s: float = 2.0,
) -> ChannelRealization:
    """Sample blockage states and shadow fading on the time grid.

    Parameters
    ----------
    elevation_deg:
        Elevation of every tracked satellite over time, shape (N, K). Entries below the
        horizon are irrelevant (the link is unusable anyway) but are processed for simplicity.
    step_s:
        Simulation step [s].
    rng:
        Seeded NumPy random generator (reproducibility).
    """
    n, k = elevation_deg.shape
    nlos = np.zeros((n, k), dtype=bool)
    shadow = np.zeros((n, k), dtype=np.float64)
    clutter = np.zeros((n, k), dtype=np.float64)
    if not (enable_blockage or enable_shadowing):
        return ChannelRealization(nlos, shadow, clutter)

    p_los = los_probability(environment, elevation_deg)  # (N, K)
    rho = float(np.exp(-step_s / max(shadow_decorr_time_s, 1e-9)))
    innov_scale = np.sqrt(1.0 - rho**2)

    # Markov transition probabilities per step
    p_nlos_to_los = min(1.0, step_s / max(nlos_mean_duration_s, 1e-9))

    state_nlos = rng.random(n) > p_los[:, 0] if enable_blockage else np.zeros(n, dtype=bool)
    x = rng.standard_normal(n) if enable_shadowing else np.zeros(n)  # unit-variance AR(1) state

    for j in range(k):
        if enable_blockage and j > 0:
            p = np.clip(p_los[:, j], 1e-6, 1.0 - 1e-6)
            # stationarity: tau_LOS = tau_NLOS * p / (1 - p)  =>  P(LOS->NLOS) = step / tau_LOS
            p_los_to_nlos = np.minimum(1.0, p_nlos_to_los * (1.0 - p) / p)
            u = rng.random(n)
            leave_los = (~state_nlos) & (u < p_los_to_nlos)
            leave_nlos = state_nlos & (u < p_nlos_to_los)
            state_nlos = np.where(leave_los, True, np.where(leave_nlos, False, state_nlos))
        if enable_shadowing:
            if j > 0:
                x = rho * x + innov_scale * rng.standard_normal(n)
            sigma = shadow_fading_sigma_db(environment, elevation_deg[:, j], ~state_nlos)
            shadow[:, j] = sigma * x
        nlos[:, j] = state_nlos
        if enable_blockage:
            clutter[:, j] = np.where(state_nlos, clutter_loss_db(environment, elevation_deg[:, j]), 0.0)
    return ChannelRealization(nlos=nlos, shadow_db=shadow, clutter_db=clutter)
