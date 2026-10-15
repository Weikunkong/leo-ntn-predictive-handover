# Forschungspraktikum extension plan (discussion document)

This repository is the **Phase A** (application / demonstration) version of the
project: it was built in a few weeks of individual work to show that the
research question is well posed, that the simulation chain is correct, and that
baselines and the proposed rule can be compared reproducibly. **Phase B** is the
Forschungspraktikum (FP) itself. The workload below is an estimate for a 10-ECTS
(≈ 300 h) FP as described for the M.Sc. EEI and M.Sc. CME programmes at FAU
(report ≥ 10 pages, ≥ 20-min presentation); the actual module rules of the
student's programme and the supervisor's wishes take precedence — nothing here
assumes a specific supervisor, topic or ECTS value.

## Phase A — what exists now (this repository)

* SGP4-based orbit layer (Walker-delta and TLE/OMM), TR 38.821 Set-1 S-band
  link budget, simplified TR 38.811 blockage/shadowing, measurement + L3 filter.
* Four handover rules (greedy, A3 hysteresis/TTT, max remaining visibility,
  ephemeris-aided predictive) with three ablations.
* Discrete-time engine with execution delay, handover-failure proxy, link-loss
  and recovery abstractions; 15+ KPIs; paired statistics with CIs.
* Monte-Carlo comparison (20 seeds × 30 min), six sensitivity sweeps, two tuning
  grids; 37 unit tests; GitHub Actions CI; documentation.

## Phase B — candidate research axes (choose **one** main axis with the supervisor)

### Core (one of these would fill an FP)

1. **Robustness under realistic ephemeris degradation.** Replace the single
   timing-error knob by a stale-SIB19 model (validity timer, re-acquisition,
   along-track/cross-track error growth from real TLE ageing measured with
   `python-sgp4` on CelesTrak history) and add UE GNSS error. Research
   question: how long may ephemeris be stale before the predictive rule falls
   back to A3-level performance, and can the bias-correction time constant be
   adapted online? *Deliverable:* error-growth model + adaptive rule + sweeps.
   *≈ 120–150 h.*
2. **Interference-aware link quality.** Add co-channel interference from
   neighbouring beams/satellites (frequency reuse pattern, TR 38.821 Set-1
   antenna pattern with the Bessel aperture model) so that the decision metric
   becomes SINR. Research question: does predicting *interference* (also
   deterministic from geometry) change the ranking of rules, and is a
   "predicted SINR" utility still lightweight? *≈ 130–160 h.*
3. **Signalling-cost-aware conditional handover.** Map the rule onto Rel-17/18
   CHO: candidate preparation (number of prepared cells), T1/D1/D2 triggers,
   execution conditions; compare signalling load vs. interruption, following
   the TR 38.821 / TS 38.331 trigger taxonomy. Research question: how many
   candidates must be prepared to retain the gains? *≈ 130–160 h.*

### Optional additions (combine one or two with the core axis)

* Mobile UEs (vehicle 30 m/s, aircraft 250 m/s) and other latitudes
  (polar/equatorial) — the mobility layer already supports constant-velocity
  motion. *≈ 20–30 h.*
* Real constellation element sets (Starlink/OneWeb from CelesTrak) and
  comparison with the Walker idealisation. *≈ 15–25 h.*
* Earth-fixed vs. Earth-moving cells (beam-level handover inside a pass). *≈ 40–60 h.*
* Comparison with a learning-based rule (e.g. a tabular Q-learning or small
  DQN baseline re-implemented from the literature) to quantify what the
  lightweight rule gives up. *≈ 50–80 h.*
* MATLAB cross-validation of the link budget and of the decision rule on
  exported traces. *≈ 10–15 h.*

### Out of scope for a 300-h FP (would need a thesis or more)

* Full 5G NR protocol-stack simulation (RRC, RLF timers, CHO signalling) in
  ns-3/5G-LENA or OpenAirInterface — the NTN support of these stacks is still
  limited and the build/integration effort alone exceeds the budget.
* Multi-user system-level simulation with scheduling, traffic models and
  inter-cell interference management (this is the domain of dedicated
  system-level simulators).
* Deep multi-agent RL for constellation-wide handover optimisation.
* Hardware/FPGA implementation of the decision rule (the rule is trivially
  cheap; an FPGA version has no research value by itself — hardware work is
  better invested in PHY blocks such as synchronisation under LEO Doppler).

## Suggested FP time budget (300 h, core axis 1 as example)

| Work package | Hours |
|---|---|
| Literature update and precise problem definition with the supervisor | 30 |
| Ephemeris-degradation model (TLE ageing study with real data, GNSS error) | 50 |
| Adaptive bias-correction / robust rule design | 60 |
| Experiments: sweeps, statistics, failure analysis | 60 |
| Code quality: tests, documentation, release | 30 |
| Report (≥ 10 pages) and presentation (≥ 20 min) | 50 |
| Buffer | 20 |

## Open questions to discuss with the supervisor

* Which impairment matters most in the group's own system-level simulator
  (e.g. interference vs. ephemeris error)?
* Should the target be a conference-style paper (e.g. a workshop) or an
  internal technical report? The current results are a proof of concept; a
  publication would need at least one of the core axes above.
* Is there interest in connecting the rule to an OpenAirInterface-based NTN
  testbed (trace-driven evaluation of recorded RSRP/ephemeris)?
