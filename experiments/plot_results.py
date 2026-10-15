#!/usr/bin/env python3
"""Re-create every figure from the CSV files in a results directory (no simulation needed).

Usage (from the repository root):
    python experiments/plot_results.py --out results/main
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from _common import ABLATIONS, MAIN_METRICS  # noqa: E402
from run_sensitivity import plot_sweep  # noqa: E402

from leo_ntn_handover.evaluation.plotting import plot_metric_bars  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="results/main")
    p.add_argument("--config", default="configs/starlink_like.yaml", help="config holding the sweep definitions")
    args = p.parse_args()
    out = Path(args.out)
    csv = out / "csv"
    made = []

    comp = csv / "comparison_summary.csv"
    reference = None
    if comp.exists():
        summary = pd.read_csv(comp)
        reference = summary
        main_algos = [a for a in summary["algorithm"] if a not in ABLATIONS or a == "predictive"]
        made.append(plot_metric_bars(summary[summary["algorithm"].isin(main_algos)], MAIN_METRICS,
                                     out / "figures" / "fig2_comparison.png", title="Main comparison (95% CI)"))
        if summary["algorithm"].isin(ABLATIONS).sum() > 1:
            made.append(plot_metric_bars(summary[summary["algorithm"].isin(ABLATIONS)], MAIN_METRICS,
                                         out / "figures" / "fig4_ablation.png", title="Ablation (95% CI)"))
    abl = csv / "ablation_summary.csv"
    if abl.exists():
        summary = pd.read_csv(abl)
        made.append(plot_metric_bars(summary[summary["algorithm"].isin(ABLATIONS)], MAIN_METRICS,
                                     out / "figures" / "fig4_ablation.png", title="Ablation (95% CI)"))
    with open(args.config) as fh:
        raw = yaml.safe_load(fh) or {}
    sweeps = raw.get("sweeps", {})
    main_algorithms = list((raw.get("handover") or {}).get("algorithms") or [])
    for name, spec in sweeps.items():
        f = csv / f"sensitivity_{name}_summary.csv"
        if f.exists():
            plot_sweep(name, spec, pd.read_csv(f), out, reference, main_algorithms)
            made.append(out / "figures" / f"fig3_sensitivity_{name}.png")
    quick = csv / "quickstart_summary.csv"
    if quick.exists():
        made.append(plot_metric_bars(pd.read_csv(quick), MAIN_METRICS, out / "figures" / "quickstart_comparison.png",
                                     title="Quick start (95% CI)"))
    print("Figures written:" if made else "No CSV summaries found in", *made if made else [csv])


if __name__ == "__main__":
    main()
