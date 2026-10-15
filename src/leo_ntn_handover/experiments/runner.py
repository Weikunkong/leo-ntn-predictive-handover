"""Run handover algorithms over many seeds (optionally in parallel) and collect KPIs.

Every row of the returned ``pandas.DataFrame`` is one (seed, algorithm) run with
all KPIs from :func:`compute_metrics`; sweep runs carry additional ``sweep``,
``level`` and ``level_label`` columns. Seeds are paired across algorithms and
sweep levels (common random numbers), which the statistics in
:mod:`leo_ntn_handover.evaluation.stats` exploit.
"""

from __future__ import annotations

import itertools
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import SimConfig
from ..evaluation.metrics import compute_metrics
from ..simulation.scenario import build_scenario, run_algorithm


def _run_seed(args: tuple[SimConfig, int, list[str], str | None, dict[str, Any]]) -> list[dict[str, Any]]:
    """Worker: build one seeded scenario and run all requested algorithms on it."""
    cfg, seed, algorithms, cache_dir, labels = args
    t0 = time.perf_counter()
    sc = build_scenario(cfg, seed, cache_dir=cache_dir)
    build_s = time.perf_counter() - t0
    rows = []
    for name in algorithms:
        t1 = time.perf_counter()
        res = run_algorithm(sc, name)
        m = compute_metrics(res, cfg.handover.pingpong_window_s, cfg.evaluation.se_cap_bits_per_hz)
        row = {"seed": seed, "algorithm": name, **labels, **m,
               "run_time_s": time.perf_counter() - t1, "scenario_build_s": build_s,
               "n_tracked_sats": sc.trace.n_sats, "ue_lon_deg": float(sc.trace.ue_lon_deg[0])}
        rows.append(row)
    return rows


def run_many(cfg: SimConfig, algorithms: list[str] | None = None, seeds: list[int] | None = None,
             cache_dir: str | Path | None = "data/cache", workers: int = 1,
             labels: dict[str, Any] | None = None, verbose: bool = True) -> pd.DataFrame:
    """Run ``algorithms`` on every seed; returns one row per (seed, algorithm)."""
    algorithms = list(algorithms or cfg.handover.algorithms)
    seeds = list(seeds if seeds is not None else cfg.evaluation.seeds)
    labels = dict(labels or {})
    jobs = [(cfg, s, algorithms, str(cache_dir) if cache_dir else None, labels) for s in seeds]
    t0 = time.perf_counter()
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_run_seed, jobs))
    else:
        results = [_run_seed(j) for j in jobs]
    rows = [r for rr in results for r in rr]
    if verbose:
        print(f"  {len(rows)} runs ({len(seeds)} seeds x {len(algorithms)} algorithms) "
              f"in {time.perf_counter() - t0:.1f} s {labels if labels else ''}")
    return pd.DataFrame(rows)


def sweep_levels(spec: dict[str, Any]) -> list[tuple[dict[str, Any], str, Any]]:
    """Expand a sweep specification into (overrides, label, level) tuples.

    Two forms are supported::

        path: measurement.noise_std_db          # one parameter
        values: [0, 1, 2]
        labels: ["0 dB", "1 dB", "2 dB"]        # optional

        grid:                                   # cartesian product of parameters
          handover.params.a3.hysteresis_db: [1, 3]
          handover.params.a3.ttt_s: [0, 0.4]
    """
    if "grid" in spec:
        keys = list(spec["grid"].keys())
        combos = list(itertools.product(*[spec["grid"][k] for k in keys]))
        out = []
        for combo in combos:
            overrides = dict(zip(keys, combo))
            label = ", ".join(f"{k.split('.')[-1]}={v}" for k, v in overrides.items())
            out.append((overrides, label, combo[0] if len(combo) == 1 else label))
        return out
    values = list(spec["values"])
    labels = spec.get("labels") or [str(v) for v in values]
    return [({spec["path"]: v}, str(lab), v) for v, lab in zip(values, labels)]


def run_sweep(cfg: SimConfig, name: str, spec: dict[str, Any], seeds: list[int] | None = None,
              cache_dir: str | Path | None = "data/cache", workers: int = 1,
              verbose: bool = True) -> pd.DataFrame:
    """Run a parameter sweep defined in ``cfg.sweeps[name]``-style ``spec``."""
    algorithms = list(spec.get("algorithms") or cfg.handover.algorithms)
    frames = []
    for overrides, label, level in sweep_levels(spec):
        if verbose:
            print(f"[sweep {name}] {label}")
        cfg_l = cfg.with_overrides(overrides)
        level_value = level if isinstance(level, (int, float, str)) else str(level)
        df = run_many(cfg_l, algorithms, seeds, cache_dir, workers,
                      labels={"sweep": name, "level": level_value, "level_label": label}, verbose=verbose)
        for k, v in overrides.items():
            df[k] = str(v) if isinstance(v, dict) else v
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
