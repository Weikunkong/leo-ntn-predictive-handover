"""Downlink link budget for a LEO satellite -> handheld UE link.

The parameterisation follows the structure of the system-level evaluation
assumptions in 3GPP TR 38.821 (NTN "Set-1", LEO-600, S-band): the satellite is
characterised by an EIRP *density* per beam [dBW/MHz] and the UE by its
antenna gain, noise figure and antenna temperature, from which G/T follows.

    SNR [dB] = EIRP_density [dBW/MHz] - 60 + G/T [dB/K] - FSPL [dB]
               - L_extra [dB] - 10*log10(k_B [J/K])

Because an EIRP density is used, the noise-only SNR does not depend on the
channel bandwidth. Interference from other beams/satellites is **not**
modelled, so the figure is an SNR, not a SINR.

Assumptions (see ``docs/assumptions.md``): ideal beam pointing / UE located
at the beam centre (maximum satellite antenna gain), no polarisation
mismatch, free-space propagation plus an aggregate ``extra_losses_db``
term for atmospheric/scintillation margins.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..constants import C_LIGHT, K_BOLTZMANN_DBW


def free_space_path_loss_db(range_km: np.ndarray | float, carrier_hz: float) -> np.ndarray:
    """Free-space path loss ``20 log10(4 pi d f / c)`` in dB."""
    d_m = np.asarray(range_km, dtype=np.float64) * 1000.0
    return 20.0 * np.log10(4.0 * np.pi * d_m * carrier_hz / C_LIGHT)


def ue_g_over_t_db(antenna_gain_dbi: float, noise_figure_db: float,
                   antenna_temp_k: float = 290.0, reference_temp_k: float = 290.0) -> float:
    """Receiver figure of merit G/T [dB/K].

    ``T_sys = T_antenna + (F - 1) * T_0`` with the noise factor ``F`` from the noise figure.
    For the TR 38.821 handheld UE (0 dBi, NF 7 dB, 290 K) this gives about -31.6 dB/K.
    """
    noise_factor = 10.0 ** (noise_figure_db / 10.0)
    t_sys = antenna_temp_k + (noise_factor - 1.0) * reference_temp_k
    return antenna_gain_dbi - 10.0 * np.log10(t_sys)


@dataclass(frozen=True)
class LinkBudget:
    """Static downlink link-budget parameters."""

    carrier_hz: float = 2.0e9
    eirp_density_dbw_per_mhz: float = 34.0   # TR 38.821 Set-1 LEO-600 S-band
    ue_antenna_gain_dbi: float = 0.0          # TR 38.821 handheld UE
    ue_noise_figure_db: float = 7.0           # TR 38.821 handheld UE
    ue_antenna_temp_k: float = 290.0          # TR 38.821 handheld UE
    extra_losses_db: float = 0.3              # aggregate atmospheric / margin term

    @property
    def g_over_t_db(self) -> float:
        return ue_g_over_t_db(self.ue_antenna_gain_dbi, self.ue_noise_figure_db, self.ue_antenna_temp_k)

    def snr_db(self, range_km: np.ndarray | float, additional_loss_db: np.ndarray | float = 0.0) -> np.ndarray:
        """Noise-only SNR [dB] at a given slant range, with optional additional losses (clutter, shadowing)."""
        fspl = free_space_path_loss_db(range_km, self.carrier_hz)
        return (self.eirp_density_dbw_per_mhz - 60.0 + self.g_over_t_db - fspl
                - self.extra_losses_db - K_BOLTZMANN_DBW - np.asarray(additional_loss_db))

    def cn0_dbhz(self, range_km: np.ndarray | float) -> np.ndarray:
        """Carrier-to-noise-density ratio C/N0 [dB-Hz] per MHz of EIRP density (bandwidth-free)."""
        return self.snr_db(range_km) + 60.0


def spectral_efficiency_proxy(snr_db: np.ndarray | float, cap_bits_per_hz: float = 5.5) -> np.ndarray:
    """Capped Shannon spectral efficiency ``min(log2(1 + SNR), cap)`` used as a throughput proxy.

    The cap mimics the highest modulation-and-coding scheme; values are a proxy, not
    a link-adaptation model.
    """
    snr_lin = 10.0 ** (np.asarray(snr_db, dtype=np.float64) / 10.0)
    return np.minimum(np.log2(1.0 + snr_lin), cap_bits_per_hz)
