#!/usr/bin/env python3
"""Parameter sensitivity sweeps (ephemeris timing error, measurement noise, handover delay, horizon,
environment, constellation density) and tuning grids for the A3 and predictive rules.

Usage (from the repository root):
    python experiments/run_sensitivity.py                                  # all sweeps in configs/starlink_like.yaml
    python experiments/run_sensitivity.py --sweeps timing_error,ho_delay   # a subset
    python experiments/run_sensitivity.py --seeds 5 --workers 4

Outputs (default: results/main/):
    csv/sensitivity_<name>_runs.csv, csv/sensitivity_<name>_summary.csv
    figures/fig3_sensitivity_<name>.png  (line plots with 95% CI bands) or
    figures/fig5_tuning_<name>_<metric>.png (heat-maps for grid sweeps)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from _common import MAIN_METRICS, load, parse_args, print_summary, summary_table, write_provenance  # noqa: E402

from leo_ntn_handover.evaluation.plotting import plot_grid_heatmap, plot_sensitivity  # noqa: E402
from leo_ntn_handover.experiments import run_sweep  # noqa: E402

X_LABELS = {
    "timing_error": "Ephemeris timing error [s]",
    "measurement_noise": "Measurement noise std [dB]",
    "ho_delay": "Handover execution delay [s]",
    "horizon": "Prediction horizon T_h [s]",
    "environment": "TR 38.811 environment",
    "density": "Constellation size",
}


def plot_sweep(name: str, spec: dict, summary: pd.DataFrame, out: Path, reference: pd.DataFrame | None,
               main_algorithms: list[str] | None = None) -> None:
    if "grid" in spec:
        keys = list(spec["grid"].keys())
        for metric in ("outage_prob", "ho_rate_per_h", "pingpong_rate"):
            for algo in summary["algorithm"].unique():
                s = summary[summary["algorithm"] == algo]
                plot_grid_heatmap(s, keys[0], keys[1], metric, out / "figures" / f"fig5_tuning_{name}_{metric}.png",
                                  title=f"{algo}: {metric} over {name.replace('_', ' ')}",
                                  fmt="{:.3f}" if metric != "ho_rate_per_h" else "{:.0f}")
        return
    ref = None
    if reference is not None and main_algorithms:
        # flat reference lines only for the *main* rules that the swept parameter cannot affect
        unaffected = [a for a in main_algorithms if a not in set(summary["algorithm"].unique())]
        ref = reference[reference["algorithm"].isin(unaffected)]
        if ref.empty:
            ref = None
    plot_sensitivity(summary, MAIN_METRICS, out / "figures" / f"fig3_sensitivity_{name}.png",
                     x_label=X_LABELS.get(name, name), title=f"Sensitivity: {name.replace('_', ' ')} (95% CI)",
                     log_x=(name == "timing_error"), reference=ref)


def main() -> None:
    args = parse_args(__doc__, "configs/starlink_like.yaml", "results/main",
                      add=lambda p: p.add_argument("--sweeps", default=None,
                                                   help="comma-separated sweep names (default: all in the config)"))
    cfg, seeds, out = load(args)
    names = [s.strip() for s in args.sweeps.split(",")] if args.sweeps else list(cfg.sweeps)
    unknown = [n for n in names if n not in cfg.sweeps]
    if unknown:
        raise SystemExit(f"unknown sweep(s) {unknown}; available: {list(cfg.sweeps)}")

    ref_path = out / "csv" / "comparison_summary.csv"
    reference = pd.read_csv(ref_path) if ref_path.exists() else None

    for name in names:
        spec = cfg.sweeps[name]
        print(f"\n=== sweep '{name}' ({len(seeds)} seeds) ===")
        runs = run_sweep(cfg, name, spec, seeds, args.cache, args.workers)
        runs.to_csv(out / "csv" / f"sensitivity_{name}_runs.csv", index=False)
        group = ["algorithm", "level", "level_label"] + ([k for k in spec["grid"]] if "grid" in spec else [])
        summary = summary_table(runs, group, confidence=cfg.evaluation.confidence)
        summary.to_csv(out / "csv" / f"sensitivity_{name}_summary.csv", index=False)
        print_summary(summary, label_col="level_label")
        plot_sweep(name, spec, summary, out, reference, list(cfg.handover.algorithms))
    write_provenance(out, cfg, seeds, {"experiment": "sensitivity", "sweeps": names},
                     name="provenance_sensitivity_" + "_".join(names) if args.sweeps else "provenance_sensitivity")
    print(f"\nWrote CSV files and figures to {out}/")


if __name__ == "__main__":
    main()
