"""Name -> algorithm factory, including ablation variants defined in the configuration."""

from __future__ import annotations

from typing import Any

from .a3 import A3Handover
from .base import HandoverAlgorithm
from .greedy import GreedyHandover
from .max_visibility import MaxVisibilityHandover
from .predictive import PredictiveHandover

ALGORITHMS: dict[str, type[HandoverAlgorithm]] = {
    "greedy": GreedyHandover,
    "a3": A3Handover,
    "maxvis": MaxVisibilityHandover,
    "predictive": PredictiveHandover,
}

#: Built-in ablation variants of the proposed method (overridable in YAML ``handover.params``).
ABLATIONS: dict[str, dict[str, Any]] = {
    "predictive_nocorr": {"base": "predictive", "use_bias_correction": False},
    "predictive_nomargin": {"base": "predictive", "margin_db": 0.0},
    "predictive_h0": {"base": "predictive", "horizon_s": 0.0, "n_samples": 1},
}


def build_algorithm(name: str, params: dict[str, dict[str, Any]] | None = None) -> HandoverAlgorithm:
    """Instantiate an algorithm by name.

    ``params`` is the ``handover.params`` mapping of the configuration. An entry may
    contain ``base: <registered name>`` to define a variant of an existing algorithm
    with different parameters (used for ablations).
    """
    params = dict(params or {})
    spec: dict[str, Any] = dict(ABLATIONS.get(name, {}))
    spec.update(params.get(name, {}))
    base = spec.pop("base", name)
    if base not in ALGORITHMS:
        raise ValueError(f"unknown handover algorithm {name!r} (base {base!r}); known: {sorted(ALGORITHMS)}")
    # variants inherit the base algorithm's configured parameters, then apply their own
    merged: dict[str, Any] = {}
    if base != name:
        merged.update({k: v for k, v in params.get(base, {}).items() if k != "base"})
    merged.update(spec)
    algo = ALGORITHMS[base](**merged)
    algo.name = name
    return algo
