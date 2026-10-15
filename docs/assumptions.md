# Assumptions, simplifications and how to read the KPIs

The framework is a *system-level abstraction* built to answer one question
(see `docs/methodology.md`). Every simplification below was made deliberately
to keep the model small, interpretable and fast; each one also marks a
possible extension (see `docs/fp_extension_plan.md`).

## Orbit / geometry

| Assumption | Consequence | Validity |
|---|---|---|
| Walker-delta constellation as SGP4 mean elements, no drag (B* = 0) | idealised, symmetric constellation; real Starlink shells have more scatter | fine for handover statistics; use `type: file` with CelesTrak elements for a real constellation |
| TEME → Earth-fixed with GMST only | ≤ a few hundred metres position error | negligible for elevation/range geometry |
| Geometry interpolated from a 1-s grid to 0.2 s | sub-metre range interpolation error | negligible |
| Single static UE at 49.6° N (longitude/start time randomised) | results are for one latitude band of a 53°-inclined shell | repeat with other latitudes if needed |
| Candidate = elevation ≥ 25° | service mask; no beam/cell planning | typical for handheld S-band service |

## Link and channel

| Assumption | Consequence | Validity |
|---|---|---|
| Noise-only SNR (no inter-beam / inter-satellite interference) | absolute SNR values are optimistic compared with TR 38.821 SINR calibration | the comparison between rules uses the same SNR for all rules |
| Ideal beam steering, UE at beam centre (max gain), no polarisation loss | no intra-satellite beam handover, no antenna roll-off | satellite-level handover only |
| Aggregate `extra_losses_db` (0.3 dB) instead of atmospheric/scintillation models | small constant offset | configurable |
| TR 38.811 LOS probability, S-band clutter loss and shadow-fading σ | large-scale statistics follow the 3GPP tables at the current elevation | the Markov sojourn time (4 s) and the AR(1) decorrelation time (2 s) are **not** from TR 38.811 (which gives no temporal model) — they are free parameters |
| No fast fading | fine for L3-filtered decision inputs; not for link-level BLER | — |
| Measurement noise N(0, σ²) per sample + L3 filter | σ = 1 dB default, swept 0–4 dB | measurement timing (SMTC) not modelled |

## Ephemeris knowledge

| Assumption | Consequence | Validity |
|---|---|---|
| Ephemeris error = along-track timing error ε (seconds) | 1 s ≈ 7.5 km | SGP4 errors are dominated by the along-track component; radial/cross-track errors, UE position (GNSS) error and clock error are not modelled separately |
| Ephemeris valid for the whole run | no validity timer / SIB19 re-acquisition | — |

## Handover procedure

| Abstraction | What it stands for | Not modelled |
|---|---|---|
| `execution_delay_s` (0.15 s) interruption on every handover | HO command, random access, path switch | RRC messages, DAPS, RACH-less HO, signalling load |
| target must be usable at completion, otherwise "handover failure" | HO failure because the target link is unusable | RLF timers (T310/N310), re-establishment procedure details |
| link loss after 1 s below threshold or when the serving satellite leaves the mask | radio-link failure | — |
| recovery to the strongest candidate measured above threshold after 0.5 s | RRC re-establishment / re-connection | — |
| decisions every 0.2 s on L3-filtered measurements | measurement/decision period | measurement report transmission, CHO preparation |

## How to read the KPIs

* **Outage probability** is the fraction of time without a *usable* link in the
  simplified model (below threshold, outside the mask, executing, or
  disconnected). It is **not** a 3GPP radio-link-failure probability and not a
  packet-level availability figure; use it to compare rules, not to quote
  absolute availability.
* **Handover failure rate** counts handovers whose target was unusable at
  completion; it is a *proxy* for too-late/too-early handover failures, not a
  3GPP HOF statistic.
* **Ping-pong rate** uses a fixed 10-s window (3GPP ping-pong definitions use a
  minimum-time-of-stay; both are configurable).
* **Spectral-efficiency proxy** is capped Shannon capacity weighted by the
  service fraction; it is not a throughput from a scheduler/link-adaptation
  model.
* **Decision time** is wall-clock time of the Python decision call; it ranks
  the rules by complexity but is not an implementation-grade cost estimate.

## What would change the conclusions

* Interference would reduce the SNR gap between candidates and could change
  the relative value of "predicting SNR" versus "predicting visibility".
* A real signalling model would add a cost per handover (CHO preparation of
  several candidates) that the explicit margin only approximates.
* Earth-fixed beams / cells with PCI planning would introduce beam-level
  handovers inside a satellite pass that this model treats as free.
