#!/usr/bin/env bash
# Reproduce every result in results/main (comparison, ablation, sensitivity sweeps, figures).
# Usage: bash experiments/run_all.sh [workers]   (default workers: all but one CPU core)
set -euo pipefail
cd "$(dirname "$0")/.."
WORKERS="${1:-$(( $(nproc 2>/dev/null || echo 2) - 1 ))}"
[ "$WORKERS" -lt 1 ] && WORKERS=1
echo "== comparison + ablation (workers=$WORKERS)"
python experiments/run_comparison.py --config configs/starlink_like.yaml --out results/main --workers "$WORKERS"
echo "== sensitivity sweeps"
python experiments/run_sensitivity.py --config configs/starlink_like.yaml --out results/main --workers "$WORKERS"
echo "== quick start"
python experiments/run_quickstart.py --config configs/quickstart.yaml --out results/quickstart --workers "$WORKERS"
echo "done"
