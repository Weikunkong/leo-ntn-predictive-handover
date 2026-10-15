#!/usr/bin/env python3
"""Quick start: run all handover rules on the small quick-start scenario and plot the results.

Usage (from the repository root):
    python experiments/run_quickstart.py                 # ~1-3 min on a laptop CPU
    python experiments/run_quickstart.py --seeds 5 --workers 4

Outputs (default: results/quickstart/):
    csv/quickstart_runs.csv, csv/quickstart_summary.csv, csv/quickstart_paired.csv
    figures/quickstart_timeline.png, figures/quickstart_comparison.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    ABLATIONS,
    MAIN_METRICS,
    load,
    paired_table,
    parse_args,
    print_summary,
    summary_table,
    write_provenance,
)

from leo_ntn_handover.evaluation.plotting import plot_metric_bars, plot_timeline  # noqa: E402
from leo_ntn_handover.experiments import run_many  # noqa: E402
from leo_ntn_handover.simulation import build_scenario, run_algorithm  # noqa: E402


def main() -> None:
    args = parse_args(__doc__, "configs/quickstart.yaml", "results/quickstart")
    cfg, seeds, out = load(args)
    algorithms = list(dict.fromkeys(cfg.handover.algorithms + ABLATIONS))
    print(f"[quickstart] {cfg.name}: {len(seeds)} seeds, {cfg.time.duration_s:.0f} s, "
          f"{cfg.constellation.n_sats} satellites, algorithms {algorithms}")

    runs = run_many(cfg, algorithms, seeds, args.cache, args.workers)
    runs.to_csv(out / "csv" / "quickstart_runs.csv", index=False)
    summary = summary_table(runs, ["algorithm"], confidence=cfg.evaluation.confidence)
    summary.to_csv(out / "csv" / "quickstart_summary.csv", index=False)
    paired_table(runs).to_csv(out / "csv" / "quickstart_paired.csv", index=False)
    print("\nMean and 95% CI half-width over seeds:")
    print_summary(summary)

    # illustrative timeline for the first seed (first 300 s)
    sc = build_scenario(cfg, seeds[0], cache_dir=args.cache)
    results = {a: run_algorithm(sc, a) for a in cfg.handover.algorithms}
    plot_timeline(sc, results, out / "figures" / "quickstart_timeline.png", t_max_s=300.0)
    plot_metric_bars(summary, MAIN_METRICS, out / "figures" / "quickstart_comparison.png",
                     title=f"Quick start ({cfg.constellation.n_sats} satellites, {len(seeds)} seeds, 95% CI)")
    write_provenance(out, cfg, seeds, {"experiment": "quickstart"}, name="provenance_quickstart")
    print(f"\nWrote CSV files and figures to {out}/")


if __name__ == "__main__":
    main()
