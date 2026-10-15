"""Baseline C: ephemeris-only "longest remaining visibility" handover.

A classical satellite-handover criterion (maximum remaining service time):
the UE keeps its serving satellite until the ephemeris predicts that it will
leave the minimum-elevation cone within ``guard_time_s``; it then hands over
to the candidate with the longest predicted remaining visibility. The rule is
purely ephemeris-driven and ignores measurements, which makes it the natural
reference for the contribution of measurement-based correction. In spirit it
corresponds to a time-triggered conditional handover (3GPP CondEvent T1 with
the cell stop time ``t-Service``) whose target is chosen by visibility.
"""

from __future__ import annotations

import numpy as np

from ..simulation.ephemeris import EphemerisOracle
from .base import HandoverAlgorithm, Observation


class MaxVisibilityHandover(HandoverAlgorithm):
    name = "maxvis"
    uses_ephemeris = True

    def __init__(self, guard_time_s: float = 5.0) -> None:
        self.guard_time_s = float(guard_time_s)

    def decide(self, obs: Observation, oracle: EphemerisOracle | None = None) -> int:
        if oracle is None:
            raise ValueError("MaxVisibilityHandover requires an EphemerisOracle")
        rem = oracle.predicted_remaining_visible_s(obs.candidates, obs.t)
        serving_rem = float(rem[obs.serving_pos])
        if serving_rem > self.guard_time_s:
            return obs.serving
        best = int(np.argmax(rem))
        if rem[best] <= serving_rem:
            return obs.serving
        return int(obs.candidates[best])

    def describe(self) -> dict:
        return {"name": self.name, "guard_time_s": self.guard_time_s}
