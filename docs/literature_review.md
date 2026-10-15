# Literature and standards review (status: October 2026)

This review was compiled from the cited sources while scoping the project. It
separates **what is established**, **what is only partially studied** and
**what this project tests**. Numbers quoted from 3GPP reports were read from
public renderings of the specifications and cross-checked against the ns-3
implementation of the same model; the original documents are available from
the 3GPP specification archive.

## 1. 3GPP NTN standardisation relevant to handover

| Item | Content relevant to this work | Source |
|---|---|---|
| TR 38.811 (Rel-15 study) | NTN deployment scenarios; satellite antenna pattern (Bessel-function aperture model); LOS probability vs. elevation for dense-urban / urban / suburban-rural (Table 6.6.1-1); shadow-fading σ and clutter loss vs. elevation, S- and Ka-band (Tables 6.6.2-1/-2/-3) | [3GPP archive 38.811](https://www.3gpp.org/ftp/Specs/archive/38_series/38.811/), rendering [§6.6.1](https://itecspec.com/3gpp/38.811/s/6.6.1), [§6.6.2](https://itecspec.com/3gpp/38.811/s/6.6.2); cross-check [ns-3 TR 38.811 tables](https://www.nsnam.org/doxygen/d9/de8/namespaceanonymous__namespace_02three-gpp-propagation-loss-model_8cc_03.html) |
| TR 38.821 (Rel-16 study) | system-level assumptions: Set-1 LEO-600 S-band satellite (EIRP density 34 dBW/MHz, 30 dBi, 4.41° beamwidth, 50-km beam), handheld UE (0 dBi, NF 7 dB, 290 K, 23 dBm), 30 MHz per beam, minimum elevation 10°, LEO-600 maximum slant range 1932 km and transparent RTD 25.77 ms; candidate CHO triggers listed in §7.3.2.2.2: measurement-based, UE/satellite location, time, timing advance, elevation | [§6.1.1.1](https://itecspec.com/3gpp/38.821/s/6.1.1.1), [§4.2](https://itecspec.com/3gpp/38.821/s/4.2), [§7.3.2.2.2](https://www.itecspec.com/3gpp/38.821/s/7.3.2.2.2) |
| TS 38.300 §16.14 (Rel-17/18 NTN) | CHO execution conditions in NTN: measurement event A4 plus a time-based and a location-based condition; RACH-less handover supported, DAPS not supported; satellite switch with re-synchronisation (Rel-18) | [§16.14.3.2.2](https://whatthespec.net/sos/spec/nr-38300/16.14.3.2.2), [§16.14.3.2.1](https://www.itecspec.com/3gpp/38.300/s/16.14.3.2.1), [§16.14.3.2.3](https://www.itecspec.com/3gpp/38.300/s/16.14.3.2.3) |
| TS 38.331 | CondEvent T1 (time window), event/CondEvent D1 (distance to reference locations, hysteresis in metres), CondEvent D2 (Rel-18, moving reference location); SIB19 carries satellite ephemeris (position/velocity or orbital elements), epoch time, uplink-sync validity duration (5–900 s), cell stop time `t-Service`, neighbour-cell configuration | [§5.5.4.16](https://itecspec.com/3gpp/38.331/s/5.5.4.16), [§5.5.4.15](https://itecspec.com/3gpp/38.331/s/5.5.4.15), [SIB19](https://itecspec.com/3gpp/38.331/s/sib19), [NTN-Config](https://itecspec.com/3gpp/38.331/s/ntn-config) |
| Rel-18 NR_NTN_enh | completed work item: CHO for Earth-moving cells with time/location triggers, satellite switch with re-sync, RACH-less HO, SIB19 broadcast from TN cells, network-verified UE location | [work item 941006](https://whatthespec.net/3gpp/wi/941006-nr-ntn-enh), [TR 21.918 §5.3.1](https://www.itecspec.com/3gpp/21.918/s/5.3.1) |
| Rel-19 NR_NTN_Ph3 | ongoing: regenerative payload, uplink capacity, RedCap, coverage; status pages | [work item 1020097](https://whatthespec.net/3gpp/wi/1020097-nr-ntn-ph3), [3GPP 5G NTN page](https://www.3gpp.org/technologies/5g-ntn) |

Take-away for the model: the standard already provides **both** measurement-
and ephemeris-based triggers for LEO handover, and it leaves the combination
(how a UE should weigh ephemeris predictions against measurements, and how to
avoid unnecessary handovers) to implementation. This is exactly the design
space of the rules compared here.

## 2. Research literature (2022–2026)

### 2.1 What is established

* **Ephemeris/location-based triggers remove most unnecessary handovers in
  clean geometry.** Juan et al. show for LEO that location-based triggering
  largely eliminates handover failures, unnecessary handovers and ping-pong and
  increases the time of stay compared with measurement-based triggering
  ([VTC 2022-Spring](https://vbn.aau.dk/en/publications/location-based-handover-triggering-for-low-earth-orbit-satellite-),
  [IEEE Access 2022](https://vbn.aau.dk/ws/files/489313978/Handover_Solutions_for_5G_Low_Earth_Orbit_Satellite_Networks.pdf));
  Kodheli, Solaija and Arslan reach the same conclusion when comparing power-,
  elevation- and distance-based triggers ([WCNC 2024](https://acikerisim.medipol.edu.tr/items/bbe099ea-5eea-4e49-92e4-943d980caea9/full)).
* **Conditional handover (CHO) avoids failures but needs control of
  unnecessary handovers.** Juan et al. report that CHO in LEO removes
  radio-link failures at the price of a large increase of unnecessary
  handovers ([WCNC 2022](https://vbn.aau.dk/en/publications/performance-evaluation-of-the-5g-nr-conditional-handover-in-leo-b));
  Zhang et al. formulate signalling-load-aware CHO target selection as an
  integer programme plus a decentralised heuristic ([CNSM 2024](https://dl.ifip.org/db/conf/cnsm/cnsm2024/1571049943.pdf)).
* **Hysteresis / time-to-trigger tuning controls ping-pong of measurement
  handover** ([Demir, Solaija, Arslan, arXiv 2201.04904](https://arxiv.org/abs/2201.04904);
  [Seeram et al., arXiv 2501.17331 / Frontiers 2025](https://arxiv.org/abs/2501.17331)),
  and a handover margin applied to predicted link quality cuts the handover
  count substantially ([Eydian, Hosseini, Karabulut Kurt, IEEE OJCOMS 2025](https://publications.polymtl.ca/62709/1/2025_Eydian_Handover_Strategy_LEO_Satellite_Networks.pdf)).
* **Classical multi-criteria rules** (closest satellite, longest remaining
  visibility, CINR-drop thresholds) trade handover count against link quality
  and their ranking depends on the constellation ([Voicu, Bhattacharya, Petrova, IEEE Access 2024](https://doaj.org/article/df0b0edc3c3a4b0e88b362225672f3a8));
  a "maximum serving capacity" rule is close to optimal in an optimisation
  framing ([McBain, Hong, Viterbo, arXiv 2512.02449](https://arxiv.org/abs/2512.02449));
  demand-aware handover reduces handovers by tens of percent ([Abdu et al., ICC WS 2023](https://orbilu.uni.lu/bitstream/10993/54766/1/ICC_2023_Tedros.pdf)).
* **Learning-based handover is heavily studied**: multi-agent DQN/DDQN
  ([Lee et al., IEEE Comm. Lett. 2025](https://wicl.ajou.ac.kr/wp-content/DB/International%20Journal/2025_05_Multi-Agent_Deep_Reinforcement_Learning_Based_Handover_Strategy_for_LEO_Satellite_Networks.pdf),
  [Yang et al., IEEE TVT 2024](https://api.openalex.org/works/doi:10.1109/TVT.2024.3412287)),
  Q-learning ([Ntabeni et al., IEEE OJCOMS 2025](https://oulurepo.oulu.fi/handle/10024/57826?show=full)),
  measurement-report-free DRL ([Lee et al., arXiv 2310.20215](https://arxiv.org/abs/2310.20215)),
  pre-planned handover by alternating optimisation ([He et al., "PreHO", arXiv 2603.07987](https://arxiv.org/abs/2603.07987)).
  These typically compare against max-channel-gain or max-visible-time rules
  rather than against a tuned 3GPP A3 baseline.
* **Measurement-aided correction of geometric predictions exists in ML
  form**: LSTM-predicted SINR setting the distance offset of a D1-like trigger
  ([Ahn et al., ICTC 2024](https://api.openalex.org/works/doi:10.1109%2FICTC62082.2024.10827489)),
  particle-filter distance with RL-tuned hysteresis/TTT ([Chen, Liao, Cho, Electronics 2025](https://www.mdpi.com/2079-9292/14/8/1494)),
  and a learned line-of-sight skyline combined with ephemeris for proactive
  handover ([Corici et al., arXiv 2608.00125](https://arxiv.org/abs/2608.00125)).
* Surveys: [Liu et al., ICCCAS 2024](https://pure.bit.edu.cn/en/publications/handover-technique-in-leo-satellite-networks-a-review/);
  [Saad, Tariq, Khan, IEEE IoT Magazine 2024 (Rel-17/18 overview)](https://avesis.metu.edu.tr/yayin/0bcc85df-20a5-4354-a217-cfa796b4f26c/non-terrestrial-networks-an-overview-of-3gpp-release-17-18).

### 2.2 Why handover can still fail with predictable orbits

Even with perfect orbit knowledge, (i) blockage and shadowing are not
predictable from ephemeris — geometry-only triggers were shown to produce
radio-link failures in urban environments because they miss LOS→NLOS
transitions ([Juan et al., IEEE Access 2022](https://vbn.aau.dk/ws/files/489313978/Handover_Solutions_for_5G_Low_Earth_Orbit_Satellite_Networks.pdf));
(ii) the execution itself takes tens to hundreds of milliseconds depending on
the architecture, during which the serving link keeps degrading
([Seeram et al. 2025](https://arxiv.org/abs/2501.17331)); (iii) the ephemeris
known to the UE can be stale or offset (SIB19 validity windows of seconds to
minutes), which shifts every predicted event in time; (iv) measurement noise
and fading make near-equal candidates swap order and cause ping-pong.

### 2.3 What is only partially studied (the gap)

* Sensitivity of ephemeris-assisted handover to **ephemeris/timing error**
  was not found in the surveyed work: Juan et al. vary UE-location, pointing
  and antenna errors but not ephemeris error; Zhang et al., Kodheli et al. and
  Seeram et al. assume error-free geometry.
* **Measurement noise** is either absent or fixed, never swept, in the
  surveyed LEO handover evaluations.
* No surveyed study evaluates a **lightweight, non-learning** ephemeris-aided
  rule with measurement-based correction and an explicit handover-cost margin
  against **both** greedy max-SNR and a tuned A3 baseline under the **joint**
  presence of ephemeris error, measurement noise, TR 38.811 blockage and
  execution delay.
* Closest open-source precedent: an uncertainty-aware CHO *timing* study using
  a confidence bound on the predicted remaining link time for a single
  location and 100 Starlink satellites
  ([shaifiqbal/uncertainty-aware-ntn-conditional-handover](https://github.com/shaifiqbal/uncertainty-aware-ntn-conditional-handover)).
  It addresses *when* to execute a pre-selected handover, not target selection
  under measurement/ephemeris impairments.

### 2.4 What this project tests (hypotheses H1–H4 in `docs/methodology.md`)

A 3GPP-parameterised (TR 38.821 Set-1, TR 38.811 S-band tables) robustness
study of a lightweight ephemeris-aided predictive rule with ablations, against
greedy and tuned A3 baselines and the classical max-visibility rule, with
sweeps over ephemeris timing error, measurement noise, execution delay,
prediction horizon, environment and constellation size. The project does
**not** claim novelty of ephemeris-based handover itself, nor does it
guarantee publishable results; it provides the reproducible evidence needed to
judge whether the lightweight rule is worth pursuing.

## 3. Match with the Fraunhofer IIS / FAU LIKE research environment

* Christian Rohde teaches *Satellitenkommunikation* at FAU LIKE as
  Lehrbeauftragter and is Chief Scientist in the RF and SatCom Systems
  department of Fraunhofer IIS (HTS, DVB-S2X, beam hopping, LEO constellation
  simulation) — [FAU LIKE](https://www.like.tf.fau.de/faudir/dr-ing-christian-rohde/),
  [Fraunhofer IIS HTS](https://www.iis.fraunhofer.de/en/ff/kom/satkom/hts.html).
* Fraunhofer IIS publishes on exactly this topic: *Handover Management in 5G
  Non-Terrestrial Networks: Simulations and Testbeds* (Raghunandan, Roshdi,
  Begaj, Heyn, Rohde; WSA 2025, [DOI 10.1109/wsa65299.2025.11202782](https://doi.org/10.1109/wsa65299.2025.11202782))
  and *Performance Analysis of Integrated 5G-NR Terrestrial and Non-Terrestrial
  Networks Using System Level Simulations* (Roshdi, Roy, Raghunandan, Heyn;
  6GNet 2024, [DOI 10.1109/6gnet63182.2024.10765660](https://doi.org/10.1109/6gnet63182.2024.10765660));
  in April 2026 the institute demonstrated 5G NTN over a GEO satellite with an
  OpenAirInterface gNB/UE including inter-beam handover
  ([press release](https://www.iis.fraunhofer.de/en/pr/2026/press-release-high-bandwidth-GEO-satellites.html));
  the NTN hub lists system-level simulation and TN/NTN handover projects
  ([NTN Hub](https://www.iis.fraunhofer.de/de/ff/kom/satkom/sat-5g.html)).

## 4. Open-source landscape used or considered

| Project | Language / licence | Used here? | Why / why not |
|---|---|---|---|
| [python-sgp4](https://github.com/brandon-rhodes/python-sgp4) | Python+C++, MIT | **yes** (propagator, TLE/OMM parsing) | vectorised, standard SGP4, no data download |
| [Skyfield](https://github.com/skyfielders/python-skyfield) | Python, MIT | no | convenient `altaz`/pass finding, but adds a dependency on timescale data; sgp4 + own frames suffice |
| [OpenNTN](https://github.com/ant-uni-bremen/OpenNTN) (Uni Bremen) | Python, MIT (needs Sionna) | no | TR 38.811 link-level channels, no mobility/system-level; too heavy for the question |
| [Sionna](https://github.com/NVlabs/sionna) | Python, Apache-2.0 | no | PHY/SYS/RT library, no NTN mobility |
| [gti-uvigo/5g-handover-sim](https://github.com/gti-uvigo/5g-handover-sim) | Python/C++, MIT/GPL | design reference only | terrestrial A3/CHO/DDQN control logic on ns-3 traces |
| [Fundacio-i2CAT/LEOPath](https://github.com/Fundacio-i2CAT/LEOPath) | Python, AGPL-3.0 | no | routing, not handover; AGPL |
| [snkas/hypatia](https://github.com/snkas/hypatia) | Python/C++, MIT/GPL | no | networking (routing/RTT), no handover |
| [sns3/sns3-satellite](https://github.com/sns3/sns3-satellite), [5G-LENA](https://gitlab.com/cttc-lena/nr) | C++ ns-3, GPL | no | full-stack simulators; 5G-LENA has no NTN mobility; weeks of build effort |
| [shaifiqbal/uncertainty-aware-ntn-conditional-handover](https://github.com/shaifiqbal/uncertainty-aware-ntn-conditional-handover) | Python | no (prior art) | CHO timing under uncertainty, single site |
| [haodpsut/leo-handover-testbed](https://github.com/haodpsut/leo-handover-testbed) | Python, MIT | no (prior art) | DP-optimal offline handover vs. A3 and learned rules |
| [Muhammaduazir69/ntn-cho-framework](https://github.com/Muhammaduazir69/ntn-cho-framework) | C++ ns-3, GPL-2.0 | no | Rel-17/18 CHO trigger taxonomy reference |
| [jtlee-97/LeoHoSim_MATLAB_2024](https://github.com/jtlee-97/LeoHoSim_MATLAB_2024) | MATLAB, MIT + usage policy | no | TR 38.821 Earth-moving cell A3/CHO/D2 KPIs |
| [jwwthu/Satellite-Open-Source](https://github.com/jwwthu/Satellite-Open-Source) | list, Apache-2.0 | no | curated list of satellite-network code |

All code in this repository was written for the project; only the MIT-licensed
`sgp4` package is imported (plus NumPy/SciPy/pandas/matplotlib/PyYAML).
