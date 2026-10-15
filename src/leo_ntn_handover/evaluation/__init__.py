"""Evaluation layer: KPIs, statistics and plots."""

from .metrics import METRIC_LABELS, compute_metrics
from .stats import mean_ci, paired_diff_ci, summarize

__all__ = ["METRIC_LABELS", "compute_metrics", "mean_ci", "paired_diff_ci", "summarize"]
