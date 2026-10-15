"""Publication-style figures (matplotlib, Agg backend, PNG).

Colours follow the algorithm identity in every figure (one fixed colour per
rule), confidence intervals are drawn as error bars / bands, and every axis
carries units. All plotting functions take data frames produced by
:mod:`leo_ntn_handover.experiments.runner` and the summaries of
:func:`leo_ntn_handover.evaluation.stats.summarize`.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..simulation.engine import NO_SAT, RunResult  # noqa: E402
from ..simulation.scenario import ScenarioData  # noqa: E402
from .metrics import METRIC_LABELS  # noqa: E402

ALGO_LABELS: dict[str, str] = {
    "greedy": "A: greedy max-SNR",
    "a3": "B: A3 hysteresis+TTT",
    "maxvis": "C: max remaining visibility",
    "predictive": "P: predictive (proposed)",
    "predictive_nocorr": "P w/o bias correction",
    "predictive_nomargin": "P w/o HO-cost margin",
    "predictive_h0": "P w/o look-ahead (T_h = 0)",
}
ALGO_COLORS: dict[str, str] = {
    "greedy": "#eb6834",
    "a3": "#2a78d6",
    "maxvis": "#eda100",
    "predictive": "#008300",
    "predictive_nocorr": "#6250d6",
    "predictive_nomargin": "#e87ba4",
    "predictive_h0": "#1baf7a",
}
ALGO_SHORT: dict[str, str] = {
    "greedy": "A", "a3": "B", "maxvis": "C", "predictive": "P",
    "predictive_nocorr": "P-nc", "predictive_nomargin": "P-nm", "predictive_h0": "P-h0",
}
ALGO_MARKERS: dict[str, str] = {
    "greedy": "o", "a3": "s", "maxvis": "^", "predictive": "D",
    "predictive_nocorr": "v", "predictive_nomargin": "P", "predictive_h0": "X",
}
ALGO_ORDER = list(ALGO_LABELS)

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "legend.fontsize": 8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#e3e3e0", "grid.linewidth": 0.6, "figure.dpi": 150, "savefig.dpi": 150,
})


def _label(a: str) -> str:
    return ALGO_LABELS.get(a, a)


def _color(a: str) -> str:
    return ALGO_COLORS.get(a, "#555555")


def _order(algos: list[str]) -> list[str]:
    return sorted(set(algos), key=lambda a: ALGO_ORDER.index(a) if a in ALGO_ORDER else 99)


def _save(fig: plt.Figure, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- timeline
def plot_timeline(sc: ScenarioData, results: dict[str, RunResult], path: str | Path,
                  t_max_s: float | None = None, title: str | None = None) -> Path:
    """True SNR of all candidates, serving SNR per rule and the serving-satellite timeline."""
    K = sc.n_steps
    t = sc.trace.t_s[:K]
    if t_max_s is not None:
        K = int(min(K, round(t_max_s / sc.trace.step_s)))
        t = t[:K]
    cand = sc.trace.candidate_mask[:, :K]
    true = sc.true_snr_db[:, :K]
    algos = _order(list(results))

    fig, axes = plt.subplots(2 + len(algos), 1, figsize=(8.5, 2.0 * (2 + len(algos)) + 0.5), sharex=True,
                             gridspec_kw={"height_ratios": [2.2, 2.2] + [0.9] * len(algos)})
    ax = axes[0]
    for i in range(sc.trace.n_sats):
        y = np.where(cand[i], true[i], np.nan)
        if np.isfinite(y).any():
            ax.plot(t, y, color="#b8b8b4", lw=0.7, alpha=0.9)
    ax.axhline(sc.cfg.handover.snr_min_db, color="#e34948", lw=0.8, ls="--")
    ax.text(t[-1], sc.cfg.handover.snr_min_db, " SNR threshold", color="#e34948", va="bottom", ha="right", fontsize=7)
    ax.set_ylabel("Candidate SNR [dB]")
    ax.set_title(title or f"Seed {sc.seed}: candidate links (grey, elevation >= {sc.trace.min_elevation_deg:g} deg)")

    ax = axes[1]
    for a in algos:
        r = results[a]
        y = np.where(r.service[:K] > 0, r.snr_serving_db[:K], np.nan)
        ax.plot(t, y, color=_color(a), lw=1.0, label=_label(a))
    ax.set_ylabel("Serving SNR [dB]")
    ax.legend(ncol=2, loc="lower left", framealpha=0.9)

    for j, a in enumerate(algos):
        ax = axes[2 + j]
        r = results[a]
        s = r.serving[:K].astype(float)
        s[s == NO_SAT] = np.nan
        ax.step(t, s, where="post", color=_color(a), lw=1.0)
        ho_t = [e.t for e in r.events if e.kind == "ho_start" and e.t <= t[-1]]
        ax.plot(ho_t, np.interp(ho_t, t, np.nan_to_num(s, nan=-1)), ls="none", marker="|", color="black",
                ms=6, mew=0.8)
        loss_t = [e.t for e in r.events if e.kind == "link_loss" and e.t <= t[-1]]
        for lt in loss_t:
            ax.axvline(lt, color="#e34948", lw=0.8, alpha=0.7)
        ax.set_ylabel("sat idx", fontsize=7)
        ax.set_title(f"{_label(a)}: {len(ho_t)} handovers, {len(loss_t)} link losses", fontsize=8, loc="left")
        ax.grid(False)
    axes[-1].set_xlabel("Time [s]")
    return _save(fig, path)


# --------------------------------------------------------------------------- bars
def plot_metric_bars(summary: pd.DataFrame, metrics: list[str], path: str | Path,
                     title: str | None = None, ncols: int = 3,
                     log_metrics: tuple[str, ...] = ("ho_rate_per_h",)) -> Path:
    """One bar panel per metric with 95% CI error bars; bars coloured by algorithm.

    Metrics listed in ``log_metrics`` use a logarithmic axis when the bars span more than
    a factor of 50 (e.g. the greedy handover rate versus the others).
    """
    algos = _order(summary["algorithm"].tolist())
    n = len(metrics)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 2.6 * nrows + 0.6))
    axes = np.atleast_1d(axes).ravel()
    for ax, m in zip(axes, metrics):
        means = summary.set_index("algorithm").reindex(algos)[f"{m}_mean"].to_numpy(dtype=float)
        finite = means[np.isfinite(means) & (means > 0)]
        use_log = m in log_metrics and len(finite) >= 2 and finite.max() / finite.min() > 50
        for i, a in enumerate(algos):
            row = summary[summary["algorithm"] == a].iloc[0]
            mean, ci = row[f"{m}_mean"], row[f"{m}_ci"]
            ax.bar(i, mean, yerr=ci if np.isfinite(ci) else None, color=_color(a), width=0.7,
                   error_kw={"elinewidth": 0.9, "capsize": 2.5, "ecolor": "#333333"})
            if np.isfinite(mean):
                txt = f"{mean:.3g}" if abs(mean) < 100 else f"{mean:.0f}"
                top = mean + (ci if np.isfinite(ci) else 0.0)
                ax.annotate(txt, (i, top), xytext=(0, 2), textcoords="offset points", ha="center",
                            va="bottom", fontsize=6.5, color="#333333")
        ax.set_xticks(range(len(algos)))
        ax.set_xticklabels([ALGO_SHORT.get(a, a) for a in algos], fontsize=8)
        ax.set_title(METRIC_LABELS.get(m, m) + (" (log)" if use_log else ""), fontsize=9)
        ax.set_axisbelow(True)
        if use_log:
            ax.set_yscale("log")
            ax.set_ylim(bottom=max(finite.min() / 3, 1e-4))
        elif (summary[f"{m}_mean"].dropna() >= 0).all():
            ax.set_ylim(bottom=0)
            ax.margins(y=0.15)
    for ax in axes[n:]:
        ax.axis("off")
    handles = [plt.Rectangle((0, 0), 1, 1, color=_color(a)) for a in algos]
    fig.legend(handles, [_label(a) for a in algos], loc="lower center", ncol=min(4, len(algos)),
               bbox_to_anchor=(0.5, -0.02), frameon=False)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- sensitivity
def plot_sensitivity(summary: pd.DataFrame, metrics: list[str], path: str | Path, x_label: str,
                     title: str | None = None, log_x: bool = False, reference: pd.DataFrame | None = None,
                     ncols: int = 3, log_metrics: tuple[str, ...] = ("ho_rate_per_h", "outage_prob")) -> Path:
    """Metric vs sweep level, one line per algorithm with a 95% CI band.

    ``summary`` must contain ``level`` (numeric or categorical) and ``algorithm`` columns.
    ``reference`` (optional) gives flat baseline values for algorithms that are unaffected
    by the swept parameter; they are drawn as dashed horizontal lines. Metrics in
    ``log_metrics`` get a logarithmic y-axis when the values span more than a factor of 50.
    """
    algos = _order(summary["algorithm"].tolist())
    levels = summary["level"].drop_duplicates().tolist()
    numeric = all(isinstance(v, (int, float, np.integer, np.floating)) for v in levels)
    n = len(metrics)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 2.7 * nrows + 0.6))
    axes = np.atleast_1d(axes).ravel()
    xs = np.array(levels, dtype=float) if numeric else np.arange(len(levels))
    for ax, m in zip(axes, metrics):
        for a in algos:
            d = summary[summary["algorithm"] == a].set_index("level").reindex(levels)
            y = d[f"{m}_mean"].to_numpy(dtype=float)
            ci = d[f"{m}_ci"].to_numpy(dtype=float)
            ax.plot(xs, y, color=_color(a), marker=ALGO_MARKERS.get(a, "o"), ms=4, lw=1.3, label=_label(a))
            ax.fill_between(xs, y - np.nan_to_num(ci), y + np.nan_to_num(ci), color=_color(a), alpha=0.15, lw=0)
        swept = (summary[f"{m}_mean"] + summary[f"{m}_ci"].fillna(0.0)).to_numpy(dtype=float)
        swept_max = float(np.nanmax(swept)) if np.isfinite(swept).any() else 0.0
        off_scale: list[str] = []
        if reference is not None:
            for a in _order(reference["algorithm"].tolist()):
                if a in algos:
                    continue
                row = reference[reference["algorithm"] == a].iloc[0]
                val = float(row[f"{m}_mean"])
                if np.isfinite(val) and val > 3.0 * max(swept_max, 1e-12):
                    off_scale.append(f"{ALGO_SHORT.get(a, a)}: {val:.3g} (off scale)")
                    continue
                ax.axhline(val, color=_color(a), ls="--", lw=1.0, label=f"{_label(a)} (unaffected)")
        if off_scale:
            ax.text(0.98, 0.97, "\n".join(off_scale), transform=ax.transAxes, ha="right", va="top",
                    fontsize=6.5, color="#555555")
        vals = summary[f"{m}_mean"].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        if m in log_metrics and len(vals) >= 2 and vals.min() > 0 and vals.max() / vals.min() > 50:
            ax.set_yscale("log")
            ax.set_title(METRIC_LABELS.get(m, m) + " (log)", fontsize=9)
        else:
            ax.set_title(METRIC_LABELS.get(m, m), fontsize=9)
        ax.set_xlabel(x_label)
        if numeric and log_x:
            ax.set_xscale("symlog", linthresh=max(1e-3, float(np.min(xs[xs > 0])) if (xs > 0).any() else 1.0))
        if not numeric:
            ax.set_xticks(xs)
            ax.set_xticklabels([str(v) for v in levels], rotation=0, fontsize=8)
    for ax in axes[n:]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=min(4, len(labels)), bbox_to_anchor=(0.5, -0.02),
               frameon=False)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- tuning heat-map
def plot_grid_heatmap(summary: pd.DataFrame, x_key: str, y_key: str, metric: str, path: str | Path,
                      title: str | None = None, fmt: str = "{:.2f}") -> Path:
    """Heat-map of ``metric`` over a two-parameter grid (one algorithm)."""
    xs = sorted(summary[x_key].unique())
    ys = sorted(summary[y_key].unique())
    z = np.full((len(ys), len(xs)), np.nan)
    for i, yv in enumerate(ys):
        for j, xv in enumerate(xs):
            rows = summary[(summary[x_key] == xv) & (summary[y_key] == yv)]
            if len(rows):
                z[i, j] = rows.iloc[0][f"{metric}_mean"]
    fig, ax = plt.subplots(figsize=(1.0 + 0.9 * len(xs), 0.8 + 0.6 * len(ys)))
    im = ax.imshow(z, cmap="Blues", aspect="auto", origin="lower")
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([str(v) for v in xs])
    ax.set_yticks(range(len(ys)))
    ax.set_yticklabels([str(v) for v in ys])
    ax.set_xlabel(x_key.split(".")[-1])
    ax.set_ylabel(y_key.split(".")[-1])
    ax.grid(False)
    for i in range(len(ys)):
        for j in range(len(xs)):
            if np.isfinite(z[i, j]):
                ax.text(j, i, fmt.format(z[i, j]), ha="center", va="center", fontsize=7,
                        color="white" if z[i, j] > np.nanmean(z) else "black")
    fig.colorbar(im, ax=ax, label=METRIC_LABELS.get(metric, metric))
    ax.set_title(title or METRIC_LABELS.get(metric, metric), fontsize=9)
    return _save(fig, path)
