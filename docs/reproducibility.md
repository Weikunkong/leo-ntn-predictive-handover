# Reproducibility

## Determinism

* Every random quantity is drawn from `numpy.random.default_rng` generators
  seeded from the run seed: UE longitude and start-time offset (`seed`),
  blockage/shadowing (`[seed, 1000003]`), measurement noise (`[seed, 2000003]`).
  All handover rules of a seed, and all sweep levels that do not change the
  orbit geometry, see identical channel and noise realisations (common random
  numbers), which is why paired differences are reported.
* Deterministic geometry traces are cached in `data/cache/geometry_<hash>.npz`;
  the hash covers the constellation, UE, time and elevation-mask configuration
  and the seed. Delete the directory to force re-computation.
* `tests/test_config_and_reproducibility.py` checks that two independent builds
  of a scenario and two runs of each rule produce identical results.
* Parallel execution (`--workers N`) distributes seeds over processes and does
  not change results.

## Provenance

Every experiment script writes `provenance_<experiment>.json` next to its CSV
files with the package version, Python/NumPy/SciPy/pandas/matplotlib/sgp4 versions, platform,
command line, seeds and the full resolved configuration.

## Commands

```bash
python -m pytest                                   # unit tests (~10 s)
python experiments/run_quickstart.py               # small scenario, 3 seeds, figures in results/quickstart/
python experiments/run_comparison.py               # main comparison + ablation, results/main/
python experiments/run_sensitivity.py              # all sweeps of configs/starlink_like.yaml
python experiments/run_sensitivity.py --sweeps timing_error,measurement_noise
python experiments/run_ablation.py                 # ablation only
python experiments/plot_results.py --out results/main   # figures from CSV only
bash experiments/run_all.sh                        # everything
```

Options common to all scripts: `--config`, `--out`, `--seeds N` (use seeds
0..N−1), `--duration S`, `--workers N`, `--cache DIR`.

## Expected run times

Measured in the development environment (2 vCPU container, Python 3.13):

| Command | Time |
|---|---|
| `python -m pytest` | ≈ 8 s |
| `run_quickstart.py` (576 satellites, 3 seeds × 10 min, 7 rules) | ≈ 10 s |
| `run_comparison.py` (1584 satellites, 20 seeds × 30 min, 7 rules, 2 workers) | ≈ 3 min geometry (once, cached) + ≈ 2.5 min runs |
| `run_sensitivity.py` (all eight sweeps, 20 seeds, 2 workers) | ≈ 40 min (≈ 1 s per predictive run of 9000 steps; A3/greedy 0.1–0.4 s) |

A laptop with 4–8 cores runs the complete set in well under an hour.

## Versions

Pinned lower bounds are in `pyproject.toml`; the exact versions used for the
committed results are in `results/*/provenance_*.json`.
