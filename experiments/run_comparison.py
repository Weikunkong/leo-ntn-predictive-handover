#!/usr/bin/env python3
"""Main comparison: baselines A/B/C, the proposed predictive rule and its ablations, over many seeds.

Usage (from the repository root):
    python experiments/run_comparison.py                         # configs/starlink_like.yaml, 20 seeds
    python experiments/run_comparison.py --seeds 5 --workers 4   # faster

Outputs (default: results/main/):
    csv/comparison_runs.csv       one row per (seed, algorithm) with all KPIs
    csv/comparison_summary.csv    mean, 95% CI half-width and n per algorithm and KPI
    csv/comparison_paired.csv     paired (same-seed) differences vs. the proposed rule, with p-values
    figures/fig1_timeline.png     illustrative serving-satellite timeline (first seed, first 300 s)
    figures/fig2_comparison.png   KPI bars with 95% CIs (A, B, C, P)
    figures/fig4_ablation.png     KPI bars with 95% CIs (P and its ablations)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import ABLATIONS, MAIN_METRICS, load, paired_table, parse_args, print_summary, summary_table, write_provenance  # noqa: E402

from leo_ntn_handover.evaluation.plotting import plot_metric_bars, plot_timeline  # noqa: E402
from leo_ntn_handover.experiments import run_many  # noqa: E402
from leo_ntn_handover.simulation import build_scenario, run_algorithm  # noqa: E402


def main() -> None:
    args = parse_args(__doc__, "configs/starlink_like.yaml", "results/main")
    cfg, seeds, out = load(args)
    main_algos = list(cfg.handover.algorithms)
    algorithms = list(dict.fromkeys(main_algos + ABLATIONS))
    print(f"[comparison] {cfg.name}: {len(seeds)} seeds x {cfg.time.duration_s:.0f} s, "
          f"{cfg.constellation.n_sats} satellites, {len(algorithms)} rules, {args.workers} workers")

    runs = run_many(cfg, algorithms, seeds, args.cache, args.workers)
    runs.to_csv(out / "csv" / "comparison_runs.csv", index=False)
    summary = summary_table(runs, ["algorithm"], confidence=cfg.evaluation.confidence)
    summary.to_csv(out / "csv" / "comparison_summary.csv", index=False)
    paired = paired_table(runs, reference="predictive", confidence=cfg.evaluation.confidence)
    paired.to_csv(out / "csv" / "comparison_paired.csv", index=False)
    print("\nMean and 95% CI half-width over seeds:")
    print_summary(summary)

    sc = build_scenario(cfg, seeds[0], cache_dir=args.cache)
    results = {a: run_algorithm(sc, a) for a in main_algos}
    plot_timeline(sc, results, out / "figures" / "fig1_timeline.png", t_max_s=300.0)
    plot_metric_bars(summary[summary["algorithm"].isin(main_algos)], MAIN_METRICS,
                     out / "figures" / "fig2_comparison.png",
                     title=f"{cfg.name}: {cfg.constellation.n_sats} satellites, {len(seeds)} seeds, 95% CI")
    plot_metric_bars(summary[summary["algorithm"].isin(ABLATIONS)], MAIN_METRICS,
                     out / "figures" / "fig4_ablation.png",
                     title=f"Ablation of the predictive rule ({len(seeds)} seeds, 95% CI)")
    write_provenance(out, cfg, seeds, {"experiment": "comparison"})
    print(f"\nWrote CSV files and figures to {out}/")


if __name__ == "__main__":
    main()
