#!/usr/bin/env python3
"""Print Markdown tables (mean ± 95 % CI) from the CSV summaries, for pasting into README/reports.

Usage (from the repository root):
    python experiments/make_results_table.py --out results/main
    python experiments/make_results_table.py --out results/main --sweep ho_delay
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

LABELS = {
    "greedy": "A greedy max-SNR", "a3": "B A3 (3 dB / 0.4 s)", "maxvis": "C max visibility",
    "predictive": "**P predictive**", "predictive_nocorr": "P w/o bias corr.",
    "predictive_nomargin": "P w/o margin", "predictive_h0": "P w/o look-ahead",
}
COLS = [
    ("ho_rate_per_h", "HO / h", "{:.1f}"), ("pingpong_rate", "ping-pong", "{:.3f}"),
    ("mean_time_of_stay_s", "stay [s]", "{:.1f}"), ("outage_prob", "outage", "{:.2%}"),
    ("link_loss_rate_per_h", "link losses / h", "{:.1f}"), ("ho_failure_rate", "HO fail", "{:.3f}"),
    ("mean_se_bps_hz", "SE proxy", "{:.2f}"), ("decision_time_us", "µs / decision", "{:.0f}"),
]


def fmt(mean: float, ci: float, f: str) -> str:
    if pd.isna(mean):
        return "–"
    if f.endswith("%}"):
        return f"{mean:.2%} ± {ci:.2%}" if pd.notna(ci) else f"{mean:.2%}"
    return f"{f.format(mean)} ± {f.format(ci)}" if pd.notna(ci) else f.format(mean)


def table(summary: pd.DataFrame, label_col: str, label_map: dict | None = None,
          cols: list = COLS) -> str:
    head = "| " + label_col + " | " + " | ".join(c[1] for c in cols) + " |"
    sep = "|" + "---|" * (len(cols) + 1)
    rows = [head, sep]
    for _, r in summary.iterrows():
        lab = str(r[label_col])
        lab = (label_map or {}).get(lab, lab)
        cells = " | ".join(fmt(r.get(f"{c}_mean"), r.get(f"{c}_ci"), f) for c, _, f in cols)
        rows.append("| " + lab + " | " + cells + " |")
    return "\n".join(rows)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="results/main")
    p.add_argument("--sweep", default=None, help="print the table of one sensitivity sweep instead")
    args = p.parse_args()
    csv = Path(args.out) / "csv"
    if args.sweep:
        s = pd.read_csv(csv / f"sensitivity_{args.sweep}_summary.csv")
        for algo, grp in s.groupby("algorithm", sort=False):
            print(f"\n**{LABELS.get(algo, algo)}** — sweep `{args.sweep}`\n")
            print(table(grp, "level_label"))
        return
    s = pd.read_csv(csv / "comparison_summary.csv")
    print(table(s, "algorithm", LABELS))


if __name__ == "__main__":
    main()
