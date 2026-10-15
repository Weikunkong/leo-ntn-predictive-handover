"""Proposed method: ephemeris-aided, measurement-corrected, cost-aware predictive handover (PCH).

For every candidate ``i`` the rule forms a *horizon utility*

    U_i(t) = (1/(J+1)) * sum_{j=0..J} g( s_i(t + tau_j) + b_i(t) * exp(-tau_j / T_b) )

where ``s_i`` is the geometry-only SNR predicted from the ephemeris at the
horizon samples ``tau_j = j * T_h / J`` (the current instant ``tau_0 = 0`` is
included so that a serving link that is blocked *now* is penalised
immediately), ``b_i(t)`` is an exponentially weighted estimate of the
measurement-minus-prediction residual (shadowing, blockage, calibration
offsets) that is assumed to fade out with time constant ``T_b``, and

    g(x) = min(x, x_cap)          if x >= SNR_min
    g(x) = -penalty               otherwise.

The cap removes the incentive to chase very strong links, while the penalty
makes candidates that are predicted to become unusable within the horizon
unattractive (a setting satellite). A handover is executed only if

    U_best - U_serving > margin_db

(explicit handover-cost margin) and the target is currently measured as
usable (``meas >= SNR_min + eligibility_margin_db``). If the serving
satellite is predicted to leave the candidate set within the horizon, the
margin is waived so that the handover happens proactively.

Ablation switches: ``use_bias_correction=False`` (pure ephemeris prediction),
``margin_db=0`` (no handover cost) and ``horizon_s=0`` (no look-ahead).
"""

from __future__ import annotations

import numpy as np

from ..simulation.ephemeris import EphemerisOracle
from .base import HandoverAlgorithm, Observation


class PredictiveHandover(HandoverAlgorithm):
    name = "predictive"
    uses_ephemeris = True

    def __init__(
        self,
        horizon_s: float = 20.0,
        n_samples: int = 5,
        margin_db: float = 2.0,
        bias_alpha: float = 0.3,
        bias_decay_s: float = 10.0,
        snr_cap_db: float = 20.0,
        outage_penalty_db: float = 20.0,
        eligibility_margin_db: float = 1.0,
        use_bias_correction: bool = True,
    ) -> None:
        self.horizon_s = float(horizon_s)
        self.n_samples = max(1, int(n_samples))
        self.margin_db = float(margin_db)
        self.bias_alpha = float(bias_alpha)
        self.bias_decay_s = float(bias_decay_s)
        self.snr_cap_db = float(snr_cap_db)
        self.outage_penalty_db = float(outage_penalty_db)
        self.eligibility_margin_db = float(eligibility_margin_db)
        self.use_bias_correction = bool(use_bias_correction)
        self._bias: dict[int, float] = {}

    def reset(self) -> None:
        self._bias = {}

    # ------------------------------------------------------------------
    def _horizon_offsets(self) -> np.ndarray:
        """Horizon sample offsets 0, T_h/J, ..., T_h (only 0 when the horizon is zero)."""
        if self.horizon_s <= 0.0:
            return np.zeros(1)
        return np.linspace(0.0, self.horizon_s, self.n_samples + 1)

    def _update_bias(self, obs: Observation, oracle: EphemerisOracle) -> np.ndarray:
        """EWMA of measurement minus ephemeris prediction for each candidate; returns (C,)."""
        pred_now = oracle.predicted_snr_db(obs.candidates, np.asarray([obs.t]))[:, 0]
        resid = obs.meas_db - pred_now
        new_bias: dict[int, float] = {}
        out = np.zeros(len(obs.candidates))
        for pos, sat in enumerate(obs.candidates.tolist()):
            prev = self._bias.get(sat)
            b = float(resid[pos]) if prev is None else (1.0 - self.bias_alpha) * prev + self.bias_alpha * float(resid[pos])
            new_bias[sat] = b
            out[pos] = b
        self._bias = new_bias
        return out

    def utilities(self, obs: Observation, oracle: EphemerisOracle) -> tuple[np.ndarray, np.ndarray]:
        """Return (utility per candidate, predicted-candidate flag at the end of the horizon)."""
        taus = self._horizon_offsets()
        t_future = obs.t + taus
        pred = oracle.predicted_snr_db(obs.candidates, t_future)          # (C, J)
        cand_future = oracle.predicted_candidate(obs.candidates, t_future)  # (C, J)
        if self.use_bias_correction:
            bias = self._update_bias(obs, oracle)
            decay = np.exp(-taus / max(self.bias_decay_s, 1e-9))
            pred = pred + bias[:, None] * decay[None, :]
        usable = cand_future & (pred >= obs.snr_min_db)
        g = np.where(usable, np.minimum(pred, self.snr_cap_db), -self.outage_penalty_db)
        return g.mean(axis=1), cand_future[:, -1]

    def decide(self, obs: Observation, oracle: EphemerisOracle | None = None) -> int:
        if oracle is None:
            raise ValueError("PredictiveHandover requires an EphemerisOracle")
        util, cand_end = self.utilities(obs, oracle)
        serving_pos = obs.serving_pos
        eligible = obs.meas_db >= obs.snr_min_db + self.eligibility_margin_db
        eligible[serving_pos] = True
        util_masked = np.where(eligible, util, -np.inf)
        best = int(np.argmax(util_masked))
        if best == serving_pos:
            return obs.serving
        margin = self.margin_db
        if not cand_end[serving_pos]:
            margin = 0.0  # serving satellite predicted to set within the horizon: hand over proactively
        if util_masked[best] - util[serving_pos] > margin:
            return int(obs.candidates[best])
        return obs.serving

    def describe(self) -> dict:
        return {
            "name": self.name, "horizon_s": self.horizon_s, "n_samples": self.n_samples,
            "margin_db": self.margin_db, "bias_alpha": self.bias_alpha, "bias_decay_s": self.bias_decay_s,
            "snr_cap_db": self.snr_cap_db, "outage_penalty_db": self.outage_penalty_db,
            "eligibility_margin_db": self.eligibility_margin_db, "use_bias_correction": self.use_bias_correction,
        }
