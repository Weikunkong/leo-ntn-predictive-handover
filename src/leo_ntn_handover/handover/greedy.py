"""Baseline A: greedy maximum-measured-SNR selection."""

from __future__ import annotations

import numpy as np

from ..simulation.ephemeris import EphemerisOracle
from .base import HandoverAlgorithm, Observation


class GreedyHandover(HandoverAlgorithm):
    """Hand over whenever another candidate is measured stronger than the serving satellite.

    This "max-RSRP / max-channel-gain" rule is the usual naive baseline in the
    LEO handover literature. A tiny ``tolerance_db`` avoids chattering on exact ties.
    """

    name = "greedy"

    def __init__(self, tolerance_db: float = 0.0) -> None:
        self.tolerance_db = float(tolerance_db)

    def decide(self, obs: Observation, oracle: EphemerisOracle | None = None) -> int:
        best = int(np.argmax(obs.meas_db))
        if obs.meas_db[best] > obs.serving_meas_db + self.tolerance_db:
            return int(obs.candidates[best])
        return obs.serving

    def describe(self) -> dict:
        return {"name": self.name, "tolerance_db": self.tolerance_db}
