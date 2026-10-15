"""Deterministic geometry traces: elevation, range, range rate and geometry-only SNR over time.

A :class:`GeometryTrace` is computed once per (configuration, seed) and cached
under ``data/cache``; it is shared by all handover algorithms and by all
parameter sweeps that do not change the orbit/UE geometry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..channel.link_budget import LinkBudget
from ..config import SimConfig
from ..mobility.ue import UETrajectory, constant_velocity_trajectory
from ..orbit.frames import look_angles
from ..orbit.propagation import Constellation
from ..orbit.tle import load_satellites
from ..orbit.walker import orbital_period_s, walker_delta_satrecs


@dataclass
class GeometryTrace:
    """Geometry of the tracked satellites (those that ever exceed the minimum elevation)."""

    t_s: np.ndarray                 # (K_total,) time grid incl. tail
    n_steps: int                    # simulated steps (K <= K_total)
    step_s: float
    sat_ids: np.ndarray             # (N,) indices into the full constellation
    sat_names: list[str]
    elevation_deg: np.ndarray       # (N, K_total)
    range_km: np.ndarray            # (N, K_total)
    range_rate_km_s: np.ndarray     # (N, K_total)
    snr_geo_db: np.ndarray          # (N, K_total) geometry-only (free-space, LOS) SNR
    remaining_visible_s: np.ndarray # (N, K_total) time the satellite stays >= min elevation from step k on
    min_elevation_deg: float
    ue_lat_deg: np.ndarray          # (K_total,)
    ue_lon_deg: np.ndarray          # (K_total,)
    meta: dict = field(default_factory=dict)

    @property
    def n_sats(self) -> int:
        return len(self.sat_ids)

    @property
    def candidate_mask(self) -> np.ndarray:
        """Boolean (N, K_total): satellite above the minimum elevation (eligible to serve)."""
        return self.elevation_deg >= self.min_elevation_deg

    def save(self, path: str | Path) -> None:
        np.savez_compressed(
            path,
            t_s=self.t_s, n_steps=self.n_steps, step_s=self.step_s, sat_ids=self.sat_ids,
            sat_names=np.array(self.sat_names), elevation_deg=self.elevation_deg,
            range_km=self.range_km, range_rate_km_s=self.range_rate_km_s,
            snr_geo_db=self.snr_geo_db, remaining_visible_s=self.remaining_visible_s,
            min_elevation_deg=self.min_elevation_deg, ue_lat_deg=self.ue_lat_deg,
            ue_lon_deg=self.ue_lon_deg, meta=np.array(repr(self.meta)),
        )

    @classmethod
    def load(cls, path: str | Path) -> "GeometryTrace":
        with np.load(path, allow_pickle=False) as z:
            return cls(
                t_s=z["t_s"], n_steps=int(z["n_steps"]), step_s=float(z["step_s"]),
                sat_ids=z["sat_ids"], sat_names=[str(s) for s in z["sat_names"]],
                elevation_deg=z["elevation_deg"], range_km=z["range_km"],
                range_rate_km_s=z["range_rate_km_s"], snr_geo_db=z["snr_geo_db"],
                remaining_visible_s=z["remaining_visible_s"],
                min_elevation_deg=float(z["min_elevation_deg"]),
                ue_lat_deg=z["ue_lat_deg"], ue_lon_deg=z["ue_lon_deg"],
                meta={"loaded_from": str(path)},
            )


def remaining_visible_time(candidate_mask: np.ndarray, step_s: float) -> np.ndarray:
    """Consecutive time [s] a satellite remains a candidate starting at each step (backward scan)."""
    n, k = candidate_mask.shape
    rem = np.zeros((n, k), dtype=np.float64)
    nxt = np.zeros(n, dtype=np.float64)
    for j in range(k - 1, -1, -1):
        nxt = np.where(candidate_mask[:, j], nxt + step_s, 0.0)
        rem[:, j] = nxt
    return rem


def build_constellation(cfg: SimConfig) -> Constellation:
    """Create the constellation from the configuration (synthetic Walker-delta or element file)."""
    c = cfg.constellation
    if c.type == "walker_delta":
        epoch = datetime.fromisoformat(c.epoch_utc).replace(tzinfo=timezone.utc)
        sats, names = walker_delta_satrecs(c.altitude_km, c.inclination_deg, c.n_planes,
                                           c.sats_per_plane, c.phasing, epoch=epoch)
    elif c.type == "file":
        if not c.file:
            raise ValueError("constellation.file must be set for type 'file'")
        sats, names = load_satellites(c.file, name_filter=c.name_filter, max_sats=c.max_sats)
    else:
        raise ValueError(f"unknown constellation type {c.type!r}")
    return Constellation(sats, names)


def seed_randomization(cfg: SimConfig, seed: int) -> tuple[float, float]:
    """Per-seed UE longitude and start-time offset (deterministic in the seed)."""
    rng = np.random.default_rng(seed)
    lon = cfg.ue.lon_deg
    if cfg.ue.randomize_longitude:
        lon = float(rng.uniform(-180.0, 180.0))
    t_off = 0.0
    if cfg.ue.randomize_start_time:
        if cfg.constellation.type == "walker_delta":
            period = orbital_period_s(cfg.constellation.altitude_km)
        else:
            period = 6000.0
        t_off = float(rng.uniform(0.0, period))
    return lon, t_off


def build_geometry_trace(cfg: SimConfig, seed: int, cache_dir: str | Path | None = "data/cache",
                         verbose: bool = False) -> GeometryTrace:
    """Compute (or load from cache) the geometry trace for one seed."""
    key = cfg.geometry_key(seed)
    cache_path = Path(cache_dir) / f"geometry_{key}.npz" if cache_dir else None
    if cache_path is not None and cache_path.exists():
        return GeometryTrace.load(cache_path)

    t0 = time.perf_counter()
    con = build_constellation(cfg)
    lon, t_off = seed_randomization(cfg, seed)
    step = cfg.time.step_s
    gstep = max(cfg.time.geometry_step_s, step)
    n_steps = int(round(cfg.time.duration_s / step))
    n_total = n_steps + int(round(cfg.time.tail_s / step))
    t_s = np.arange(n_total) * step
    # coarse propagation grid (covering the fine grid), geometry is interpolated afterwards
    t_coarse = np.arange(0.0, t_s[-1] + gstep, gstep)

    if cfg.constellation.type == "walker_delta":
        start = datetime.fromisoformat(cfg.constellation.epoch_utc).replace(tzinfo=timezone.utc)
    else:
        # for real element sets start at the median epoch of the loaded records
        epochs = [s.jdsatepoch + s.jdsatepochF for s in con.satrecs]
        jd_med = float(np.median(epochs))
        start = datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd_med - 2451545.0)
    start = start + timedelta(seconds=t_off)

    ue_c: UETrajectory = constant_velocity_trajectory(t_coarse, cfg.ue.lat_deg, lon, cfg.ue.alt_m,
                                                      cfg.ue.speed_mps, cfg.ue.heading_deg)
    r_ecef, v_ecef, err = con.propagate_ecef(start, t_coarse)
    ok = ~(err != 0).any(axis=1)
    el_c, _az, rng_c, rr_c = look_angles(r_ecef, v_ecef, ue_c.r_ecef_km, ue_c.v_ecef_km_s,
                                         ue_c.lat_deg, ue_c.lon_deg)
    del r_ecef, v_ecef
    keep = ok & (el_c.max(axis=1) >= cfg.link.min_elevation_deg)
    idx = np.nonzero(keep)[0]
    if len(idx) == 0:
        raise RuntimeError("no satellite ever exceeds the minimum elevation in this scenario")

    def resample(a: np.ndarray) -> np.ndarray:
        return np.stack([np.interp(t_s, t_coarse, row) for row in a[idx]])

    el, rng, rr = resample(el_c), resample(rng_c), resample(rr_c)
    ue: UETrajectory = constant_velocity_trajectory(t_s, cfg.ue.lat_deg, lon, cfg.ue.alt_m,
                                                    cfg.ue.speed_mps, cfg.ue.heading_deg)
    lb = LinkBudget(cfg.link.carrier_hz, cfg.link.eirp_density_dbw_per_mhz, cfg.link.ue_antenna_gain_dbi,
                    cfg.link.ue_noise_figure_db, cfg.link.ue_antenna_temp_k, cfg.link.extra_losses_db)
    snr_geo = lb.snr_db(rng)
    cand = el >= cfg.link.min_elevation_deg
    trace = GeometryTrace(
        t_s=t_s, n_steps=n_steps, step_s=step, sat_ids=idx, sat_names=[con.names[i] for i in idx],
        elevation_deg=el, range_km=rng, range_rate_km_s=rr, snr_geo_db=snr_geo,
        remaining_visible_s=remaining_visible_time(cand, step),
        min_elevation_deg=cfg.link.min_elevation_deg, ue_lat_deg=ue.lat_deg, ue_lon_deg=ue.lon_deg,
        meta={"seed": seed, "start_utc": start.isoformat(), "n_constellation": len(con),
              "geometry_step_s": gstep, "build_time_s": time.perf_counter() - t0},
    )
    if verbose:
        print(f"[geometry] seed={seed} tracked {trace.n_sats}/{len(con)} satellites, "
              f"{trace.meta['build_time_s']:.1f} s")
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        trace.save(cache_path)
    return trace
