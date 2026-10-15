"""Key performance indicators computed from a :class:`RunResult`.

All KPIs are *proxies* defined on the simplified system model (no RRC, no
traffic model, no radio-link-failure timers of TS 38.331). Definitions:

* ``ho_rate_per_h``        handover attempts per hour of simulated time
* ``ho_failure_rate``      attempts whose target link was unusable when execution completed / attempts
* ``pingpong_rate``        successful handovers A->B that are followed by B->A within
                           ``pingpong_window_s`` / successful handovers (fraction of the *return* handovers)
* ``short_stay_rate``      successful handovers after which the next handover attempt starts within
                           ``pingpong_window_s`` / successful handovers ("unnecessary handover" proxy)
* ``mean_time_of_stay_s``  mean time between consecutive successful handovers
* ``outage_prob``          1 - mean service fraction (no usable link: below SNR threshold,
                           outside the candidate set, executing a handover/recovery, or disconnected)
* ``interruption_frac``    fraction of time spent executing handovers/recoveries
* ``quality_outage_frac``  fraction of time connected but below the SNR threshold
* ``disconnected_frac``    fraction of time without any serving satellite (excluding executions)
* ``mean_outage_duration_s``  mean duration of outage episodes (contiguous steps with service < 1)
* ``link_loss_rate_per_h`` link-loss (radio-link-failure proxy) events per hour
* ``mean_snr_db`` / ``p05_snr_db``   service-weighted mean and 5th percentile of the serving SNR
* ``mean_se_bps_hz``       service-weighted capped Shannon spectral-efficiency proxy
* ``decision_time_us``     mean wall-clock time of one decision call (algorithm complexity proxy)
"""

from __future__ import annotations

import numpy as np

from ..simulation.engine import NO_SAT, RunResult, throughput_proxy

METRIC_LABELS: dict[str, str] = {
    "ho_rate_per_h": "Handover attempts per hour",
    "ho_failure_rate": "Handover failure rate (proxy)",
    "pingpong_rate": "Ping-pong rate",
    "short_stay_rate": "Short-stay handover rate",
    "mean_time_of_stay_s": "Mean time of stay [s]",
    "outage_prob": "Outage probability (proxy)",
    "interruption_frac": "Handover interruption fraction",
    "quality_outage_frac": "Below-threshold fraction",
    "disconnected_frac": "Disconnected fraction",
    "mean_outage_duration_s": "Mean outage duration [s]",
    "link_loss_rate_per_h": "Link losses per hour",
    "mean_snr_db": "Mean serving SNR [dB]",
    "p05_snr_db": "5th-percentile serving SNR [dB]",
    "mean_se_bps_hz": "Spectral-efficiency proxy [bit/s/Hz]",
    "decision_time_us": "Decision time [us]",
}


def _outage_episodes(service: np.ndarray, step_s: float) -> list[float]:
    """Durations [s] of contiguous outage episodes (steps with service fraction < 1)."""
    out = service < 1.0 - 1e-9
    episodes: list[float] = []
    acc = 0.0
    for s, o in zip(service, out):
        if o:
            acc += (1.0 - float(s)) * step_s
        elif acc > 0:
            episodes.append(acc)
            acc = 0.0
    if acc > 0:
        episodes.append(acc)
    return episodes


def compute_metrics(result: RunResult, pingpong_window_s: float = 10.0,
                    se_cap_bits_per_hz: float = 5.5) -> dict[str, float]:
    """Compute all KPIs of a run."""
    dt = result.step_s
    duration_h = result.duration_s / 3600.0
    ev = result.events
    ho_start = [e for e in ev if e.kind == "ho_start"]
    ho_success = [e for e in ev if e.kind == "ho_success"]
    ho_fail = [e for e in ev if e.kind == "ho_fail"]
    link_loss = [e for e in ev if e.kind == "link_loss"]
    n_att = len(ho_start)
    n_ok = len(ho_success)

    # ping-pong / short stay on successful handovers (ordered by time)
    pingpong = 0
    short_stay = 0
    stays: list[float] = []
    starts_after = [e.t for e in ho_start]
    for i, e in enumerate(ho_success):
        later = [t for t in starts_after if t > e.t + 1e-9]
        if later:
            stay = later[0] - e.t
            stays.append(stay)
            if stay <= pingpong_window_s:
                short_stay += 1
        if i > 0:
            prev = ho_success[i - 1]
            if prev.source == e.target and prev.target == e.source and e.t - prev.t <= pingpong_window_s:
                pingpong += 1

    service = result.service
    connected = result.serving != NO_SAT
    usable = service > 0
    snr = result.snr_serving_db
    quality_out = connected & ~np.isnan(snr) & (service == 0) & (result.interrupted < 1.0)
    disconnected = ~connected & (result.interrupted < 1.0 - 1e-9)
    weights = service
    if weights.sum() > 0:
        mean_snr = float(np.nansum(np.where(usable, snr, 0.0) * weights) / weights.sum())
        p05 = float(np.nanpercentile(snr[usable], 5))
    else:
        mean_snr, p05 = float("nan"), float("nan")
    episodes = _outage_episodes(service, dt)
    se = throughput_proxy(result, se_cap_bits_per_hz)

    return {
        "ho_rate_per_h": n_att / duration_h,
        "ho_failure_rate": len(ho_fail) / n_att if n_att else float("nan"),
        "pingpong_rate": pingpong / n_ok if n_ok else float("nan"),
        "short_stay_rate": short_stay / n_ok if n_ok else float("nan"),
        "mean_time_of_stay_s": float(np.mean(stays)) if stays else float("nan"),
        "outage_prob": float(1.0 - service.mean()),
        "interruption_frac": float(result.interrupted.mean()),
        "quality_outage_frac": float(quality_out.mean()),
        "disconnected_frac": float(np.mean(disconnected * (1.0 - result.interrupted))),
        "mean_outage_duration_s": float(np.mean(episodes)) if episodes else 0.0,
        "link_loss_rate_per_h": len(link_loss) / duration_h,
        "mean_snr_db": mean_snr,
        "p05_snr_db": p05,
        "mean_se_bps_hz": float(se.mean()),
        "decision_time_us": 1e6 * result.decide_time_s / result.n_decisions if result.n_decisions else float("nan"),
        "n_ho_attempts": float(n_att),
        "n_ho_success": float(n_ok),
        "n_link_loss": float(len(link_loss)),
        "mean_candidates": float(result.n_candidates.mean()),
    }
