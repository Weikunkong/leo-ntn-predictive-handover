"""Common interface of all handover decision rules.

A rule receives, once per simulation step, an :class:`Observation` with the
current serving satellite, the candidate set (satellites above the minimum
elevation) and their L3-filtered measurements. Rules flagged with
``uses_ephemeris`` additionally get an :class:`EphemerisOracle`. A rule returns
the index of the satellite that should serve next; returning the current
serving index means "no handover".

The rules never see true (noise-free) link quality or the hidden blockage
state - only measurements and (possibly erroneous) ephemeris predictions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..simulation.ephemeris import EphemerisOracle


@dataclass
class Observation:
    k: int                        # step index
    t: float                      # time since start [s]
    step_s: float
    serving: int                  # index of the serving satellite (always a candidate when a decision is requested)
    candidates: np.ndarray        # (C,) indices of candidate satellites, includes ``serving``
    meas_db: np.ndarray           # (C,) L3-filtered measured SNR of each candidate [dB]
    snr_min_db: float             # minimum usable SNR (engine threshold)

    @property
    def serving_pos(self) -> int:
        """Position of the serving satellite inside ``candidates``."""
        return int(np.nonzero(self.candidates == self.serving)[0][0])

    @property
    def serving_meas_db(self) -> float:
        return float(self.meas_db[self.serving_pos])


class HandoverAlgorithm(ABC):
    """Base class. Subclasses implement :meth:`decide` and may keep internal state."""

    name: str = "base"
    uses_ephemeris: bool = False

    def reset(self) -> None:  # noqa: B027 - optional hook
        """Reset internal state before a new run."""

    @abstractmethod
    def decide(self, obs: Observation, oracle: EphemerisOracle | None = None) -> int:
        """Return the index of the satellite that should serve after this step."""

    def describe(self) -> dict:
        """Parameters for logging."""
        return {"name": self.name}
