import numpy as np

from leo_ntn_handover.channel import (
    LinkBudget,
    clutter_loss_db,
    free_space_path_loss_db,
    generate_channel_realization,
    los_probability,
    shadow_fading_sigma_db,
    ue_g_over_t_db,
)
from leo_ntn_handover.channel.link_budget import spectral_efficiency_proxy


def test_fspl_reference_values():
    # 20 log10(d_km) + 20 log10(f_MHz) + 32.45 : 1000 km at 2 GHz -> 158.47 dB
    assert abs(free_space_path_loss_db(1000.0, 2.0e9) - 158.47) < 0.02
    assert abs(free_space_path_loss_db(600.0, 2.0e9) - 154.03) < 0.02


def test_handheld_g_over_t_matches_tr38821_style_value():
    # 0 dBi, NF 7 dB, 290 K antenna temperature -> approx -31.6 dB/K
    assert abs(ue_g_over_t_db(0.0, 7.0, 290.0) - (-31.62)) < 0.05


def test_snr_set1_leo600_sband():
    lb = LinkBudget(extra_losses_db=0.0)
    # EIRP density 34 dBW/MHz, G/T -31.62 dB/K, FSPL at 600 km nadir 154.03 dB:
    # SNR = 34 - 60 - 31.62 - 154.03 + 228.6 = 16.95 dB
    assert abs(lb.snr_db(600.0) - 16.95) < 0.05
    # monotonically decreasing with range
    d = np.linspace(600, 1932, 50)
    assert np.all(np.diff(lb.snr_db(d)) < 0)
    assert abs(lb.snr_db(600.0, additional_loss_db=10.0) - (16.95 - 10.0)) < 0.05


def test_spectral_efficiency_cap():
    assert abs(spectral_efficiency_proxy(0.0) - 1.0) < 1e-9  # log2(1 + 1) = 1 bit/s/Hz at 0 dB
    assert spectral_efficiency_proxy(40.0) == 5.5
    assert spectral_efficiency_proxy(-np.inf) == 0.0


def test_tr38811_tables_interpolation():
    assert abs(los_probability("suburban", 10.0) - 0.782) < 1e-9
    assert abs(los_probability("dense_urban", 90.0) - 0.981) < 1e-9
    assert abs(los_probability("suburban", 15.0) - 0.5 * (0.782 + 0.869)) < 1e-9
    assert abs(los_probability("urban", 5.0) - 0.246) < 1e-9  # clamped below 10 deg
    assert abs(clutter_loss_db("suburban", 30.0) - 18.42) < 1e-9
    assert abs(shadow_fading_sigma_db("suburban", 30.0, True) - 1.14) < 1e-9
    assert abs(shadow_fading_sigma_db("suburban", 30.0, False) - 8.78) < 1e-9
    assert np.all(los_probability("dense_urban", np.arange(10, 91)) <= los_probability("suburban", np.arange(10, 91)))


def test_channel_realization_statistics_and_reproducibility():
    n, k = 400, 3000
    elev = np.full((n, k), 30.0)
    rng = np.random.default_rng(1)
    ch = generate_channel_realization(elev, 0.2, rng, "suburban", nlos_mean_duration_s=4.0)
    # stationary NLOS fraction ~ 1 - 0.919 = 8.1 %
    frac = ch.nlos.mean()
    assert 0.05 < frac < 0.12
    assert np.all(ch.clutter_db[ch.nlos] > 0) and np.all(ch.clutter_db[~ch.nlos] == 0)
    # LOS shadow fading std close to the tabulated 1.14 dB
    assert abs(ch.shadow_db[~ch.nlos].std() - 1.14) < 0.25
    ch2 = generate_channel_realization(elev, 0.2, np.random.default_rng(1), "suburban", nlos_mean_duration_s=4.0)
    np.testing.assert_array_equal(ch.nlos, ch2.nlos)
    np.testing.assert_allclose(ch.shadow_db, ch2.shadow_db)
    off = generate_channel_realization(elev, 0.2, rng, "suburban", enable_blockage=False, enable_shadowing=False)
    assert not off.nlos.any() and np.all(off.extra_loss_db == 0)
