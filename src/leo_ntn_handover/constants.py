"""Physical and geodetic constants used throughout the package."""

# Speed of light [m/s]
C_LIGHT = 299_792_458.0

# Boltzmann constant [J/K] and its value in dBW/(K Hz)
K_BOLTZMANN = 1.380649e-23
K_BOLTZMANN_DBW = -228.5991671  # 10*log10(1.380649e-23)

# WGS84 ellipsoid
WGS84_A = 6_378_137.0            # semi-major axis [m]
WGS84_F = 1.0 / 298.257223563    # flattening
WGS84_B = WGS84_A * (1.0 - WGS84_F)
WGS84_E2 = 1.0 - (WGS84_B / WGS84_A) ** 2

# Mean Earth radius [km] (used only for the Walker-delta altitude -> mean-motion conversion)
EARTH_RADIUS_KM = 6_371.0

# Standard gravitational parameter of the Earth [km^3/s^2] (WGS72 value used by SGP4)
MU_EARTH_KM3_S2 = 398_600.8

# Earth rotation rate [rad/s]
OMEGA_EARTH = 7.2921159e-5

# Julian date of 1949-12-31 00:00 UT (SGP4 "epoch" reference) and of J2000.0
JD_1949_12_31 = 2_433_281.5
JD_J2000 = 2_451_545.0
