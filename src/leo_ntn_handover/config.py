"""Experiment configuration (YAML -> typed dataclasses).

All simulation parameters live in YAML files under ``configs/``; experiment
scripts never hard-code physical parameters. Sweeps are expressed as dotted
paths into the configuration (e.g. ``measurement.noise_std_db``) plus a list
of values, see :func:`SimConfig.with_override`.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import types
import typing
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml


def _build(cls: type, data: dict | None, where: str) -> Any:
    """Instantiate dataclass ``cls`` from ``data``, raising on unknown keys."""
    data = dict(data or {})
    names = {f.name for f in fields(cls)}
    unknown = set(data) - names
    if unknown:
        raise ValueError(f"unknown key(s) {sorted(unknown)} in section '{where}'")
    hints = typing.get_type_hints(cls)  # resolves the string annotations of ``from __future__ import annotations``
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        ftype = hints.get(f.name, f.type)
        if is_dataclass(ftype) and isinstance(value, dict):
            value = _build(ftype, value, f"{where}.{f.name}")
        else:
            value = _coerce(ftype, value, f"{where}.{f.name}")
        kwargs[f.name] = value
    return cls(**kwargs)


def _coerce(ftype: Any, value: Any, where: str) -> Any:
    """Coerce scalars to the annotated type (YAML 1.1 reads e.g. ``2.0e9`` as a string)."""
    if value is None:
        return None
    base = ftype
    if isinstance(ftype, types.UnionType) or typing.get_origin(ftype) is typing.Union:
        non_none = [a for a in typing.get_args(ftype) if a is not type(None)]
        base = non_none[0] if len(non_none) == 1 else ftype
    try:
        if base is float and not isinstance(value, float):
            return float(value)
        if base is int and not isinstance(value, bool) and not isinstance(value, int):
            return int(value)
        if base is bool and isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        if base is str and not isinstance(value, str):
            return str(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot convert {value!r} at '{where}' to {base}") from exc
    return value


@dataclass
class ConstellationConfig:
    type: str = "walker_delta"           # "walker_delta" or "file"
    altitude_km: float = 550.0
    inclination_deg: float = 53.0
    n_planes: int = 72
    sats_per_plane: int = 22
    phasing: int = 1
    epoch_utc: str = "2026-01-01T00:00:00"
    file: str | None = None              # TLE/3LE/OMM-CSV/OMM-JSON file for type == "file"
    name_filter: str | None = None
    max_sats: int | None = None

    @property
    def n_sats(self) -> int:
        return self.n_planes * self.sats_per_plane


@dataclass
class UEConfig:
    lat_deg: float = 49.57               # Erlangen
    lon_deg: float = 11.03
    alt_m: float = 300.0
    speed_mps: float = 0.0
    heading_deg: float = 90.0
    randomize_longitude: bool = True     # per seed: uniform longitude (random constellation phase)
    randomize_start_time: bool = True    # per seed: uniform offset within one orbital period


@dataclass
class TimeConfig:
    duration_s: float = 600.0
    step_s: float = 0.2                  # simulation / measurement / decision period
    geometry_step_s: float = 1.0         # SGP4 propagation grid; geometry is linearly interpolated to step_s
    tail_s: float = 900.0                # extra propagated time so predictions near the end are valid


@dataclass
class LinkConfig:
    carrier_hz: float = 2.0e9
    eirp_density_dbw_per_mhz: float = 34.0
    ue_antenna_gain_dbi: float = 0.0
    ue_noise_figure_db: float = 7.0
    ue_antenna_temp_k: float = 290.0
    extra_losses_db: float = 0.3
    min_elevation_deg: float = 25.0


@dataclass
class ChannelConfig:
    environment: str = "suburban"
    enable_blockage: bool = True
    enable_shadowing: bool = True
    nlos_mean_duration_s: float = 4.0
    shadow_decorr_time_s: float = 2.0


@dataclass
class MeasurementConfig:
    noise_std_db: float = 1.0
    l3_filter_k: int = 4                 # TS 38.331 filterCoefficient k; a = 1/2^(k/4)


@dataclass
class HandoverConfig:
    snr_min_db: float = 0.0
    execution_delay_s: float = 0.15
    link_loss_timeout_s: float = 2.0
    recovery_delay_s: float = 0.5
    pingpong_window_s: float = 10.0
    algorithms: list[str] = field(default_factory=lambda: ["greedy", "a3", "maxvis", "predictive"])
    params: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class EphemerisConfig:
    timing_error_s: float = 0.0          # along-track timing (stale-ephemeris) error seen by the UE
    max_lookahead_s: float = 900.0


@dataclass
class EvaluationConfig:
    seeds: list[int] = field(default_factory=lambda: [0, 1, 2])
    se_cap_bits_per_hz: float = 5.5
    confidence: float = 0.95


@dataclass
class SimConfig:
    name: str = "default"
    constellation: ConstellationConfig = field(default_factory=ConstellationConfig)
    ue: UEConfig = field(default_factory=UEConfig)
    time: TimeConfig = field(default_factory=TimeConfig)
    link: LinkConfig = field(default_factory=LinkConfig)
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    measurement: MeasurementConfig = field(default_factory=MeasurementConfig)
    handover: HandoverConfig = field(default_factory=HandoverConfig)
    ephemeris: EphemerisConfig = field(default_factory=EphemerisConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    sweeps: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ I/O
    @classmethod
    def from_dict(cls, data: dict) -> "SimConfig":
        return _build(cls, data, "root")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SimConfig":
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def to_yaml(self, path: str | Path) -> None:
        with open(path, "w") as fh:
            yaml.safe_dump(self.to_dict(), fh, sort_keys=False)

    # ------------------------------------------------------------ overrides
    def with_override(self, dotted_path: str, value: Any) -> "SimConfig":
        """Return a deep copy with ``dotted_path`` (e.g. ``measurement.noise_std_db``) set to ``value``.

        If the target is a dataclass and ``value`` is a dict, the dict is merged into it
        (used for constellation sweeps).
        """
        new = copy.deepcopy(self)
        parts = dotted_path.split(".")
        obj: Any = new
        for p in parts[:-1]:
            obj = obj[p] if isinstance(obj, dict) else getattr(obj, p)
        last = parts[-1]
        if isinstance(obj, dict):
            obj[last] = value
            return new
        current = getattr(obj, last)
        if is_dataclass(current) and isinstance(value, dict):
            for k, v in value.items():
                if not hasattr(current, k):
                    raise ValueError(f"unknown key {k!r} in {dotted_path}")
                setattr(current, k, v)
        else:
            if not hasattr(obj, last):
                raise ValueError(f"unknown config path {dotted_path!r}")
            setattr(obj, last, value)
        return new

    def with_overrides(self, overrides: dict[str, Any]) -> "SimConfig":
        cfg = self
        for k, v in overrides.items():
            cfg = cfg.with_override(k, v)
        return cfg

    # ------------------------------------------------------------- hashing
    def geometry_key(self, seed: int) -> str:
        """Hash of everything that determines the deterministic geometry trace."""
        payload = {
            "constellation": dataclasses.asdict(self.constellation),
            "ue": dataclasses.asdict(self.ue),
            "time": dataclasses.asdict(self.time),
            "min_elevation_deg": self.link.min_elevation_deg,
            "seed": seed,
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha1(blob).hexdigest()[:16]


def load_config(path: str | Path) -> SimConfig:
    """Load a YAML configuration file."""
    return SimConfig.from_yaml(path)
