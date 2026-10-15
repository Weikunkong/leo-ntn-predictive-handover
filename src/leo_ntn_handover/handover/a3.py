"""Baseline B: measurement-triggered handover with hysteresis and time-to-trigger (A3-style).

Mimics the entering condition of the 3GPP TS 38.331 event A3
("neighbour becomes offset better than serving"): a neighbour triggers a
handover when its L3-filtered measurement exceeds the serving measurement by
``hysteresis_db`` continuously for ``ttt_s`` seconds. Among simultaneously
triggered neighbours the strongest is chosen. Only the decision logic is
modelled - no RRC signalling, measurement reports or conditional-handover
preparation.
"""

from __future__ import annotations

import numpy as np

from ..simulation.ephemeris import EphemerisOracle
from .base import HandoverAlgorithm, Observation


class A3Handover(HandoverAlgorithm):
    name = "a3"

    def __init__(self, hysteresis_db: float = 3.0, ttt_s: float = 1.0) -> None:
        self.hysteresis_db = float(hysteresis_db)
        self.ttt_s = float(ttt_s)
        self._timers: dict[int, float] = {}

    def reset(self) -> None:
        self._timers = {}

    def decide(self, obs: Observation, oracle: EphemerisOracle | None = None) -> int:
        serving_meas = obs.serving_meas_db
        better = obs.meas_db > serving_meas + self.hysteresis_db
        new_timers: dict[int, float] = {}
        triggered: list[tuple[float, int]] = []
        for pos, sat in enumerate(obs.candidates.tolist()):
            if sat == obs.serving:
                continue
            if better[pos]:
                timer = self._timers.get(sat, 0.0) + obs.step_s
                new_timers[sat] = timer
                # TTT counted from the first step the condition holds; ttt_s = 0 triggers immediately
                if timer - obs.step_s + 1e-9 >= self.ttt_s:
                    triggered.append((float(obs.meas_db[pos]), sat))
        self._timers = new_timers
        if triggered:
            triggered.sort(reverse=True)
            self._timers = {}
            return triggered[0][1]
        return obs.serving

    def describe(self) -> dict:
        return {"name": self.name, "hysteresis_db": self.hysteresis_db, "ttt_s": self.ttt_s}
