"""Discrete-time handover simulation engine.

The engine is deliberately simple and transparent: at every step it

1. completes a pending handover/recovery whose execution delay has elapsed
   (success if the target link is usable at that moment, failure otherwise);
2. checks the serving link (candidate set and SNR threshold) and declares a
   link loss after ``link_loss_timeout_s`` of unusable service or
   immediately when the serving satellite leaves the candidate set;
3. asks the handover rule for a decision when the UE is connected and no
   handover is in progress; a decided handover starts immediately and
   detaches the UE from the source for ``execution_delay_s``;
4. books the service fraction of the step (interruption, outage).

Execution delay, link-loss timeout and recovery delay are *abstractions* of
the 3GPP procedures (handover execution with random access, radio-link-failure
detection, RRC re-establishment); they are not protocol simulations.
See ``docs/assumptions.md`` for the interpretation of each KPI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ..channel.link_budget import spectral_efficiency_proxy
from ..handover.base import HandoverAlgorithm, Observation
from .ephemeris import EphemerisOracle
from .geometry import GeometryTrace

NO_SAT = -1


@dataclass
class Event:
    t: float
    kind: str          # ho_start | ho_success | ho_fail | link_loss | rec_start | rec_success | rec_fail
    source: int
    target: int


@dataclass
class Pending:
    kind: str          # "ho" or "rec"
    source: int
    target: int
    t_start: float
    t_complete: float


@dataclass
class RunResult:
    algorithm: str
    step_s: float
    serving: np.ndarray            # (K,) serving satellite at the end of each step (-1 = none / executing)
    snr_serving_db: np.ndarray     # (K,) true SNR of the serving satellite at the end of each step (nan if none)
    service: np.ndarray            # (K,) fraction of the step with usable service in [0, 1]
    interrupted: np.ndarray        # (K,) fraction of the step spent in handover/recovery execution
    n_candidates: np.ndarray       # (K,) number of candidate satellites
    events: list[Event] = field(default_factory=list)
    n_decisions: int = 0
    decide_time_s: float = 0.0
    params: dict = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        return float(len(self.serving) * self.step_s)


class SimulationEngine:
    """Runs one handover rule over one channel realisation of a geometry trace."""

    def __init__(
        self,
        trace: GeometryTrace,
        true_snr_db: np.ndarray,
        meas_db: np.ndarray,
        snr_min_db: float,
        execution_delay_s: float,
        link_loss_timeout_s: float,
        recovery_delay_s: float,
    ) -> None:
        self.trace = trace
        self.true_snr = true_snr_db
        self.meas = meas_db
        self.cand = trace.candidate_mask
        self.snr_min = float(snr_min_db)
        self.d_ho = float(execution_delay_s)
        self.t_loss = float(link_loss_timeout_s)
        self.d_rec = float(recovery_delay_s)
        self.K = trace.n_steps
        self.dt = trace.step_s

    # ------------------------------------------------------------------
    def _usable(self, sat: int, k: int) -> bool:
        return sat != NO_SAT and bool(self.cand[sat, k]) and bool(self.true_snr[sat, k] >= self.snr_min)

    def _best_measured(self, k: int, require_usable: bool = True) -> int:
        """Strongest measured candidate; with ``require_usable`` only candidates measured above the threshold."""
        cands = np.nonzero(self.cand[:, k])[0]
        if len(cands) == 0:
            return NO_SAT
        m = self.meas[cands, k]
        if require_usable:
            ok = ~np.isnan(m) & (m >= self.snr_min)
            if not ok.any():
                return NO_SAT
            cands, m = cands[ok], m[ok]
        elif np.all(np.isnan(m)):
            return NO_SAT
        return int(cands[np.nanargmax(m)])

    # ------------------------------------------------------------------
    def run(self, algorithm: HandoverAlgorithm, oracle: EphemerisOracle | None = None,
            initial_serving: int | None = None) -> RunResult:
        K, dt = self.K, self.dt
        serving_arr = np.full(K, NO_SAT, dtype=int)
        snr_arr = np.full(K, np.nan)
        service = np.zeros(K)
        interrupted = np.zeros(K)
        n_cand = self.cand[:, :K].sum(axis=0)
        events: list[Event] = []

        algorithm.reset()
        if initial_serving is None:
            serving = self._best_measured(0)
            if serving == NO_SAT:
                serving = self._best_measured(0, require_usable=False)
        else:
            serving = int(initial_serving)
        pending: Pending | None = None
        loss_timer = 0.0
        n_dec = 0
        dec_time = 0.0

        def complete(p: Pending, k: int) -> int:
            """Finish a pending execution at step k; returns the new serving satellite."""
            if self._usable(p.target, k):
                events.append(Event(p.t_complete, f"{p.kind}_success", p.source, p.target))
                return p.target
            events.append(Event(p.t_complete, f"{p.kind}_fail", p.source, p.target))
            return NO_SAT

        for k in range(K):
            t = k * dt
            t_end = t + dt
            cands = np.nonzero(self.cand[:, k])[0]

            # 1. pending execution (started in an earlier step) completing within this step
            if pending is not None and pending.t_complete < t_end:
                interrupted[k] += (pending.t_complete - t) / dt
                serving = complete(pending, k)
                loss_timer = 0.0
                pending = None

            # 2. serving-link check (only when not executing)
            if pending is None and serving != NO_SAT:
                if not self.cand[serving, k]:
                    events.append(Event(t, "link_loss", serving, NO_SAT))
                    serving = NO_SAT
                    loss_timer = 0.0
                elif self.true_snr[serving, k] < self.snr_min:
                    loss_timer += dt
                    if loss_timer >= self.t_loss - 1e-9:
                        events.append(Event(t, "link_loss", serving, NO_SAT))
                        serving = NO_SAT
                        loss_timer = 0.0
                else:
                    loss_timer = 0.0

            # 3a. recovery when disconnected: reconnect to the strongest candidate measured as usable
            if pending is None and serving == NO_SAT:
                target = self._best_measured(k, require_usable=True)
                if target != NO_SAT:
                    events.append(Event(t, "rec_start", NO_SAT, target))
                    pending = Pending("rec", NO_SAT, target, t, t + self.d_rec)

            # 3b. handover decision when connected
            elif pending is None and len(cands) > 0:
                obs = Observation(k=k, t=t, step_s=dt, serving=serving, candidates=cands,
                                  meas_db=self.meas[cands, k], snr_min_db=self.snr_min)
                t0 = time.perf_counter()
                target = int(algorithm.decide(obs, oracle))
                dec_time += time.perf_counter() - t0
                n_dec += 1
                if target != serving:
                    if not self.cand[target, k]:
                        raise RuntimeError(f"{algorithm.name} selected a non-candidate satellite {target}")
                    events.append(Event(t, "ho_start", serving, target))
                    pending = Pending("ho", serving, target, t, t + self.d_ho)

            # execution started in this step: completes within it, or spans into later steps
            if pending is not None:
                if pending.t_complete < t_end:
                    interrupted[k] += (pending.t_complete - pending.t_start) / dt
                    serving = complete(pending, k)
                    loss_timer = 0.0
                    pending = None
                else:
                    interrupted[k] += (t_end - max(pending.t_start, t)) / dt

            # 4. bookkeeping
            interrupted[k] = min(1.0, interrupted[k])
            if pending is None and serving != NO_SAT:
                serving_arr[k] = serving
                snr_arr[k] = self.true_snr[serving, k]
                service[k] = (1.0 - interrupted[k]) * float(self._usable(serving, k))

        return RunResult(
            algorithm=algorithm.name, step_s=dt, serving=serving_arr, snr_serving_db=snr_arr,
            service=service, interrupted=interrupted, n_candidates=n_cand, events=events,
            n_decisions=n_dec, decide_time_s=dec_time, params=algorithm.describe(),
        )


def throughput_proxy(result: RunResult, cap_bits_per_hz: float = 5.5) -> np.ndarray:
    """Per-step spectral-efficiency proxy [bit/s/Hz] weighted by the service fraction."""
    snr = np.where(np.isnan(result.snr_serving_db), -np.inf, result.snr_serving_db)
    se = spectral_efficiency_proxy(snr, cap_bits_per_hz)
    return result.service * se
