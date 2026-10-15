#!/usr/bin/env python3
"""Ablation study of the proposed predictive rule: full rule vs. no bias correction, no handover-cost
margin and no look-ahead, plus the two ephemeris-only/measurement-only references (C and B).

Usage (from the repository root):
    python experiments/run_ablation.py --seeds 10 --workers 4

Outputs (default: results/main/): csv/ablation_runs.csv, csv/ablation_summary.csv, csv/ablation_paired.csv,
figures/fig4_ablation.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import ABLATIONS, MAIN_METRICS, load, paired_table, parse_args, print_summary, summary_table, write_provenance  # noqa: E402

from leo_ntn_handover.evaluation.plotting import plot_metric_bars  # noqa: E402
from leo_ntn_handover.experiments import run_many  # noqa: E402


def main() -> None:
    args = parse_args(__doc__, "configs/starlink_like.yaml", "results/main")
    cfg, seeds, out = load(args)
    algorithms = ["a3", "maxvis"] + ABLATIONS
    print(f"[ablation] {cfg.name}: {len(seeds)} seeds, rules {algorithms}")
    runs = run_many(cfg, algorithms, seeds, args.cache, args.workers)
    runs.to_csv(out / "csv" / "ablation_runs.csv", index=False)
    summary = summary_table(runs, ["algorithm"], confidence=cfg.evaluation.confidence)
    summary.to_csv(out / "csv" / "ablation_summary.csv", index=False)
    paired_table(runs, reference="predictive").to_csv(out / "csv" / "ablation_paired.csv", index=False)
    print_summary(summary)
    plot_metric_bars(summary[summary["algorithm"].isin(ABLATIONS)], MAIN_METRICS,
                     out / "figures" / "fig4_ablation.png",
                     title=f"Ablation of the predictive rule ({len(seeds)} seeds, 95% CI)")
    write_provenance(out, cfg, seeds, {"experiment": "ablation"})
    print(f"\nWrote CSV files and figures to {out}/")


if __name__ == "__main__":
    main()
