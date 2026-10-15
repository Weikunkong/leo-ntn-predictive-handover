"""Shared fixtures: a tiny hand-made geometry trace for deterministic engine/algorithm tests."""

from __future__ import annotations

import numpy as np
import pytest

from leo_ntn_handover.simulation.geometry import GeometryTrace, remaining_visible_time


def make_trace(elevation: np.ndarray, snr_geo: np.ndarray, step_s: float = 1.0,
               n_steps: int | None = None, min_elevation_deg: float = 10.0) -> GeometryTrace:
    """Build a GeometryTrace from explicit elevation (N, K) and geometry SNR (N, K) arrays."""
    n, k = elevation.shape
    t = np.arange(k) * step_s
    cand = elevation >= min_elevation_deg
    return GeometryTrace(
        t_s=t, n_steps=k if n_steps is None else n_steps, step_s=step_s, sat_ids=np.arange(n),
        sat_names=[f"S{i}" for i in range(n)], elevation_deg=elevation.astype(float),
        range_km=np.full((n, k), 1000.0), range_rate_km_s=np.zeros((n, k)), snr_geo_db=snr_geo.astype(float),
        remaining_visible_s=remaining_visible_time(cand, step_s), min_elevation_deg=min_elevation_deg,
        ue_lat_deg=np.zeros(k), ue_lon_deg=np.zeros(k), meta={"synthetic": True},
    )


@pytest.fixture
def two_sat_trace() -> GeometryTrace:
    """Two satellites: S0 sets (SNR falls 15 -> -10 dB), S1 rises (SNR -10 -> 15 dB) over 60 s."""
    k = 60
    t = np.arange(k)
    snr0 = 15.0 - 25.0 * t / (k - 1)
    snr1 = -10.0 + 25.0 * t / (k - 1)
    elev = np.full((2, k), 45.0)
    elev[0, 50:] = 5.0  # S0 leaves the candidate set at t = 50 s
    return make_trace(elev, np.stack([snr0, snr1]), step_s=1.0)
