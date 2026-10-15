# Methodology

This document describes the system model, the handover rules, the impairment
models and the evaluation protocol implemented in `src/leo_ntn_handover/`. Every
parameter named below is set in the YAML files under `configs/`.

## 1. Scope and research question

**Handover type.** We study *satellite-level handover* of a single connected
user equipment (UE): the choice of which visible LEO satellite serves the UE
and when to switch. Intra-satellite beam switching is assumed ideal (the UE is
always served by the beam centre, see §3), and no cell/PCI planning is
modelled, i.e. one satellite = one cell. The payload is transparent (the
decision logic sits conceptually in the gNB on the ground and in the UE's
conditional-handover evaluation), but the location of the decision logic does
not matter for the comparison because no signalling latency between gNB and UE
is modelled beyond the aggregate execution delay.

**Research question.** Does a lightweight ephemeris-aided predictive handover
rule that (i) predicts the geometry-only link quality of every candidate over a
short horizon, (ii) corrects the prediction with the measured residual and
(iii) switches only when the predicted utility gain exceeds an explicit
handover-cost margin, reduce handover count, ping-pong and service-outage
proxies compared with greedy max-SNR and 3GPP-style A3 (hysteresis +
time-to-trigger) handover — and how do its gains degrade under ephemeris timing
errors, measurement noise, NLOS blockage and handover execution delay?

**Hypotheses** (each is falsifiable by the experiments in `experiments/`):

* H1 – with error-free ephemeris the predictive rule needs fewer handovers and
  produces less ping-pong than greedy and A3 at equal or lower outage.
* H2 – the advantage degrades gracefully with ephemeris timing error; the
  measurement-based bias correction limits the degradation.
* H3 – under NLOS blockage, *pure* ephemeris prediction (no correction, as in
  the max-visibility baseline) is worse than A3 because it cannot see
  blockage; the corrected rule recovers.
* H4 – with longer execution delays every rule loses, but rules that hand
  over less often lose less.

## 2. Orbit and geometry model

* **Constellation.** Default: a Walker-delta constellation generated from
  (altitude, inclination, planes, satellites per plane, phasing) — e.g. the
  Starlink-shell-1-like 72 × 22 at 550 km / 53°. Each satellite is created as an
  SGP4 mean-element record (`sgp4init`), so synthetic and real constellations
  share one propagator; real element sets (TLE or CelesTrak OMM CSV/JSON) can
  be loaded instead (`data/README.md`).
* **Propagation.** `python-sgp4` (`SatrecArray`, WGS72 constants) on a 1-s
  grid; TEME → Earth-fixed rotation with GMST (IAU 1982); polar motion and
  UT1–UTC are neglected (sub-km effect). Geometry (elevation, slant range,
  range rate) is linearly interpolated to the 0.2-s simulation grid.
* **UE.** Static (default) or constant-velocity great-circle motion on the WGS84
  ellipsoid (lat/lon/alt → ECEF). Per seed, the UE longitude and the start time
  within one orbital period are randomised at fixed latitude (49.57° N,
  Erlangen), so the Monte-Carlo average is over constellation phases at one
  latitude.
* **Candidate set.** A satellite is a *candidate* (may serve) while its
  elevation is at least `link.min_elevation_deg` (default 25°). This is the
  service elevation mask; TR 38.821 uses 10° as the minimum for system-level
  studies, 25–30° is typical for handheld terminals and keeps the candidate
  set at a realistic size (≈ 7 satellites for 576, ≈ 20 for 1584 satellites).
* **Remaining visibility.** For every satellite and time step the time until
  it leaves the candidate set is pre-computed (a 900-s tail is propagated so
  that look-ahead near the end of the run is well defined).

## 3. Link budget (3GPP TR 38.821 Set-1, LEO-600, S-band, handheld UE)

Noise-only downlink SNR

```
SNR = EIRP_density − 60 + G/T − FSPL(d) − L_extra − 10 log10(k_B)      [dB]
G/T = G_UE − 10 log10( T_ant + (F − 1) · 290 K )                       [dB/K]
```

with EIRP density 34 dBW/MHz, UE gain 0 dBi, noise figure 7 dB, antenna
temperature 290 K (G/T = −31.6 dB/K) and carrier 2 GHz. This yields 16.9 dB at
nadir (600 km) and 6.8 dB at the 1932-km maximum slant range of the LEO-600
scenario (10° elevation). `tests/test_channel.py` and
`matlab/link_budget_check.m` assert these numbers. Not modelled: inter-beam /
inter-satellite interference (the quantity is an SNR, not a SINR), satellite
antenna roll-off (ideal beam steering, maximum gain), polarisation loss;
atmospheric and scintillation losses are an aggregate constant `extra_losses_db`.

## 4. Large-scale channel (simplified, TR 38.811-based)

For every tracked satellite link and 0.2-s step:

* **Blockage state** `{LOS, NLOS}` – two-state Markov chain whose stationary
  LOS probability equals the TR 38.811 Table 6.6.1-1 value at the current
  elevation (dense urban / urban / suburban), with a free mean NLOS sojourn
  time (default 4 s). While NLOS, the TR 38.811 S-band clutter loss of the
  environment is added (suburban ≈ 16–20 dB, urban/dense urban ≈ 25–34 dB).
* **Shadow fading** – unit-variance AR(1) process with decorrelation time 2 s,
  scaled by the TR 38.811 LOS/NLOS standard deviation at the current elevation
  (suburban LOS ≈ 0.7–1.8 dB, NLOS ≈ 9–11.5 dB).
* **Fast fading** is not modelled; decisions use L3-filtered measurements whose
  averaging is long compared with the fast-fading coherence time.

`true_SNR = geometry_SNR − clutter·[NLOS] − shadow`. The tables are listed in
`channel/tr38811.py`; the realisation is drawn from a seeded generator and is
identical for all rules of a seed (common random numbers).

## 5. Measurements and ephemeris knowledge

* **Measurement** of every candidate each step: `true_SNR + N(0, σ_meas²)`,
  default σ_meas = 1 dB, then the TS 38.331 layer-3 filter
  `F_n = (1−a)F_{n−1} + a·M_n`, `a = 1/2^(k/4)`, k = 4 (a = 0.5), reset when a
  satellite re-enters the candidate set.
* **Ephemeris oracle.** Rules C and P obtain predicted *geometry-only* SNR,
  elevation and remaining visibility. Imperfect ephemeris is modelled by an
  along-track **timing error** ε: the UE evaluates the orbit at `t + ε`
  (1 s ≈ 7.5 km along-track). SGP4/ephemeris errors are dominated by the
  along-track component, which motivates the single-parameter model.

## 6. Handover rules

All rules see the same observation (serving satellite, candidate set,
L3-filtered measurements); C and P additionally use the oracle. A rule returns
the satellite that should serve next.

| Rule | Logic | Parameters |
|---|---|---|
| **A – greedy max-SNR** | hand over whenever another candidate is measured stronger | `tolerance_db` (0) |
| **B – A3 hysteresis + TTT** | neighbour measured better than serving by `hysteresis_db` continuously for `ttt_s` → hand over to the strongest triggered neighbour (entering condition of TS 38.331 event A3; no RRC signalling modelled) | 3 dB, 0.4 s (tuned in a grid sweep) |
| **C – max remaining visibility** | keep serving until the ephemeris predicts it leaves the candidate set within `guard_time_s`, then choose the longest remaining visibility (ephemeris only; the classical "maximum service time" rule, in spirit a time-triggered CHO with `t-Service`) | 5 s |
| **P – predictive (proposed)** | horizon utility `U_i = (1/J) Σ_j g( ŝ_i(t+τ_j) + b_i e^{−τ_j/T_b} )`, `g(x)=min(x, x_cap)` if usable else `−penalty`; hand over to the best *currently usable* candidate if `U_best − U_serving > margin`, margin waived when the serving satellite is predicted to leave the candidate set within the horizon; `b_i` is an EWMA of measurement − prediction | T_h = 20 s, J = 5, margin 2 dB, α = 0.2, T_b = 10 s, cap 15 dB, penalty 20 dB |

Ablations: `predictive_nocorr` (b_i ≡ 0), `predictive_nomargin` (margin 0),
`predictive_h0` (T_h = 0, i.e. corrected current SNR with margin).

## 7. Handover execution and link-loss abstraction (simulation engine)

* A decided handover detaches the UE from the source for `execution_delay_s`
  (default 0.15 s; an abstraction of HO command + random access on the target;
  LEO-600 transparent-payload RTT is ≈ 26 ms in TR 38.821). At completion the
  target must be *usable* (candidate and true SNR ≥ `snr_min_db` = 0 dB);
  otherwise the handover **fails** and the UE is disconnected.
* A connected UE whose serving satellite is below the SNR threshold for
  `link_loss_timeout_s` (1 s) or leaves the candidate set loses the link
  (radio-link-failure proxy). A disconnected UE reconnects to the strongest
  candidate measured above the threshold after `recovery_delay_s` (0.5 s,
  re-establishment proxy).
* Service accounting per step: `service = (1 − interrupted fraction) ·
  [serving usable]`.

None of this is a protocol simulation: there are no RRC messages, timers T310/T311,
measurement reports or conditional-handover preparation. The KPIs are
therefore proxies (see `docs/assumptions.md`).

## 8. KPIs

Defined in `evaluation/metrics.py`: handover attempts per hour; handover failure
rate (target unusable at completion / attempts); ping-pong rate (A→B followed
by B→A within 10 s / successful handovers); short-stay rate; mean time of stay;
outage probability (1 − mean service fraction) with its decomposition into
execution interruption, below-threshold time and disconnected time; mean outage
duration; link losses per hour; service-weighted mean and 5th-percentile serving
SNR; capped-Shannon spectral-efficiency proxy `min(log2(1+SNR), 5.5)`; mean
decision time per call (complexity proxy).

## 9. Experimental protocol

* **Monte Carlo.** 20 seeds (main scenario) × 30 min; each seed fixes the UE
  longitude, start time, blockage/shadowing realisation and measurement noise.
  All rules and all sweep levels that do not alter the geometry re-use the same
  realisation, so differences are paired.
* **Statistics.** Mean ± 95 % Student-t confidence interval over seeds;
  paired same-seed differences versus the proposed rule with paired t-test
  p-values (`comparison_paired.csv`).
* **Sweeps** (`run_sensitivity.py`): ephemeris timing error −20 … +20 s,
  measurement noise 0–4 dB, execution delay 0.05–2 s, prediction horizon
  0–80 s, TR 38.811 environment, constellation size 576/792/1584; tuning grids
  for A3 (hysteresis × TTT) and the predictive rule (margin × cap) so that
  tuned baselines are compared with a tuned proposal.
* **Ablation** (`run_ablation.py` / part of `run_comparison.py`).
* **Quick start** (`run_quickstart.py`): 576 satellites, 10 min, 3 seeds.
