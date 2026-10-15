"""leo_ntn_handover: ephemeris-aided predictive satellite handover for LEO 5G-NTN.

The package is organised along the four model layers of the study:

* ``orbit``      – constellation generation (Walker-delta) and TLE/OMM loading,
                   SGP4 propagation and coordinate frames (TEME -> ECEF -> ENU).
* ``mobility``   – ground-user trajectory model.
* ``channel``    – link budget (3GPP TR 38.821 Set-1 style) and the simplified,
                   TR 38.811-inspired LOS/NLOS blockage + shadow-fading model.
* ``handover``   – handover decision rules (baselines and the proposed method).
* ``simulation`` – geometry traces, measurement model and the discrete-time
                   handover simulation engine.
* ``evaluation`` – KPIs, statistics (confidence intervals) and plotting.
"""

__version__ = "0.1.0"
