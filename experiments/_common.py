"""Shared helpers for the experiment scripts (argument parsing, output layout, summaries)."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import pandas as pd

from leo_ntn_handover import __version__
from leo_ntn_handover.config import SimConfig, load_config
from leo_ntn_handover.evaluation.stats import paired_diff_ci, summarize

ROOT = Path(__file__).resolve().parents[1]

MAIN_METRICS = ["ho_rate_per_h", "pingpong_rate", "outage_prob", "link_loss_rate_per_h",
                "mean_se_bps_hz", "ho_failure_rate"]
ALL_METRICS = MAIN_METRICS + ["short_stay_rate", "mean_time_of_stay_s", "interruption_frac",
                              "quality_outage_frac", "disconnected_frac", "mean_outage_duration_s",
                              "mean_snr_db", "p05_snr_db", "decision_time_us", "mean_candidates"]
ABLATIONS = ["predictive", "predictive_nocorr", "predictive_nomargin", "predictive_h0"]


def parse_args(description: str, default_config: str, default_out: str, add=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    if add is not None:
        add(p)
    p.add_argument("--config", default=default_config, help="YAML configuration file")
    p.add_argument("--out", default=default_out, help="output directory for CSV files and figures")
    p.add_argument("--seeds", type=int, default=None, help="override: use seeds 0..N-1")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                   help="parallel worker processes (default: CPU count - 1)")
    p.add_argument("--cache", default="data/cache", help="geometry cache directory")
    p.add_argument("--duration", type=float, default=None, help="override simulated duration [s]")
    return p.parse_args()


def load(args: argparse.Namespace) -> tuple[SimConfig, list[int], Path]:
    cfg = load_config(args.config)
    if args.duration is not None:
        cfg = cfg.with_override("time.duration_s", float(args.duration))
    seeds = list(range(args.seeds)) if args.seeds is not None else list(cfg.evaluation.seeds)
    out = Path(args.out)
    (out / "csv").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    return cfg, seeds, out


def write_provenance(out: Path, cfg: SimConfig, seeds: list[int], extra: dict | None = None) -> None:
    """Record software versions, config and seeds next to the results."""
    import matplotlib
    import numpy
    import scipy
    import sgp4

    info = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "package_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": numpy.__version__, "scipy": scipy.__version__, "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__, "sgp4": sgp4.__version__,
        "seeds": seeds, "command": " ".join(sys.argv),
        "config": cfg.to_dict(),
    }
    if extra:
        info.update(extra)
    with open(out / "provenance.json", "w") as fh:
        json.dump(info, fh, indent=2, default=str)


def summary_table(runs: pd.DataFrame, group_cols: list[str], metrics: list[str] = ALL_METRICS,
                  confidence: float = 0.95) -> pd.DataFrame:
    metrics = [m for m in metrics if m in runs.columns]
    return summarize(runs, group_cols, metrics, confidence)


def paired_table(runs: pd.DataFrame, reference: str = "predictive", metrics: list[str] = MAIN_METRICS,
                 confidence: float = 0.95) -> pd.DataFrame:
    """Paired (same-seed) differences ``algorithm - reference`` with CI and paired t-test p-value."""
    rows = []
    ref = runs[runs["algorithm"] == reference].set_index("seed")
    for a in runs["algorithm"].unique():
        if a == reference:
            continue
        other = runs[runs["algorithm"] == a].set_index("seed")
        common = ref.index.intersection(other.index)
        row = {"algorithm": a, "reference": reference, "n_seeds": len(common)}
        for m in metrics:
            if m not in runs.columns:
                continue
            d, h, p = paired_diff_ci(other.loc[common, m].to_numpy(), ref.loc[common, m].to_numpy(), confidence)
            row[f"{m}_diff"] = d
            row[f"{m}_ci"] = h
            row[f"{m}_p"] = p
        rows.append(row)
    return pd.DataFrame(rows)


def print_summary(summary: pd.DataFrame, metrics: list[str] = MAIN_METRICS, label_col: str = "algorithm") -> None:
    cols = [label_col] + [c for m in metrics for c in (f"{m}_mean", f"{m}_ci") if c in summary.columns]
    with pd.option_context("display.width", 200, "display.max_columns", 50, "display.float_format", "{:.3f}".format):
        print(summary[cols].to_string(index=False))
