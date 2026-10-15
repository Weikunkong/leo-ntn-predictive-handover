# Short project description (for GitHub "About", CV and application e-mails)

## One-liner (GitHub description)

Reproducible Python framework for ephemeris-aided predictive satellite handover in LEO 5G non-terrestrial networks: SGP4 constellations, 3GPP TR 38.821/38.811 link and channel parameters, greedy / A3 / max-visibility baselines, Monte-Carlo evaluation with confidence intervals.

## CV entry (project section)

**LEO-NTN Predictive Handover — open-source research framework (Python)**, 2026, individual project.
Designed and implemented a system-level simulation of satellite handover for a single user in LEO constellations (SGP4 propagation of Walker-delta and TLE/OMM constellations, 3GPP TR 38.821 Set-1 S-band link budget, TR 38.811-based LOS/NLOS blockage and shadow fading, L3-filtered measurements). Implemented three baseline rules (greedy max-SNR, 3GPP-style A3 hysteresis/time-to-trigger, maximum remaining visibility) and a lightweight ephemeris-aided predictive rule with measurement-based bias correction and an explicit handover-cost margin; evaluated handover rate, ping-pong, outage, link-loss and throughput proxies over 20 seeds with paired confidence intervals, including sensitivity sweeps over ephemeris timing error, measurement noise, execution delay and blockage environment. Python/NumPy/SciPy/pandas/matplotlib, 37 unit tests, GitHub Actions CI, MIT licence.

## Abstract-style paragraph (application e-mail / README teaser)

Handover is one of the critical mobility-management problems of LEO non-terrestrial networks: a satellite serves a user for only a few minutes, candidate links are many and similar, and 3GPP Rel-17/18 provides both measurement-based and ephemeris-based (time/location) conditional-handover triggers without prescribing how to combine them. This project asks whether a *lightweight* ephemeris-aided rule — predicted geometry-only link quality over a short horizon, corrected by the measured residual and gated by a handover-cost margin — outperforms greedy and A3-style handover, and how robust it is to stale ephemeris, measurement noise, NLOS blockage and execution delay. In a Starlink-shell-like scenario (1584 satellites, 20 seeds × 30 min) the rule reduces the handover rate by a factor of 4 and ping-pong by an order of magnitude compared with a 3-dB/0.4-s A3 rule while lowering the outage proxy from 1.3 % to 0.5 %, at the cost of a 3 % lower throughput proxy; ablations show that the measurement-based correction is what makes ephemeris prediction survive blockage, and the margin is what removes ping-pong. All models, assumptions and limitations (no interference, no protocol stack) are documented and every figure is reproducible from YAML configurations.

## Skills demonstrated (for a cover letter)

* satellite communications: orbit propagation, visibility geometry, link budget, Doppler/range-rate, 3GPP NTN parameterisation;
* communication-system modelling and algorithm design (handover decision rules, filtering, prediction with uncertainty);
* scientific experiment design: baselines, ablations, parameter sweeps, Monte Carlo with paired confidence intervals, honest reporting of trade-offs;
* research software engineering in Python: modular package, typed interfaces, configuration-driven experiments, unit tests, CI, documentation;
* complementary background: MATLAB for communication-system simulation (link-budget cross-check script included) and VHDL/FPGA RTL design with hardware validation from laboratory projects.
