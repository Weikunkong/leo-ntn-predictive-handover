"""Loading real orbital elements: two/three-line element sets (TLE) and OMM (CSV/JSON).

CelesTrak distributes general-perturbation (GP) data for groups such as
``starlink`` or ``oneweb`` in several formats, e.g.
``https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=csv``
(OMM CSV) or ``FORMAT=json``. Note that CelesTrak limits downloads of the
same data set to once per update cycle; download once and store the file
under ``data/`` (see ``data/README.md``).

Only the loaders live here; propagation is done by :class:`Constellation`.
"""

from __future__ import annotations

import json
from pathlib import Path

from sgp4 import omm
from sgp4.api import WGS72, Satrec


def load_tle_file(path: str | Path) -> tuple[list[Satrec], list[str]]:
    """Parse a 2-line or 3-line element file (comment lines starting with ``#`` are ignored).

    Returns ``(satrecs, names)``. For 2-line files the name is the NORAD catalogue number.
    """
    lines = [ln.rstrip("\n") for ln in Path(path).read_text().splitlines()]
    lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    satrecs: list[Satrec] = []
    names: list[str] = []
    i = 0
    pending_name: str | None = None
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            rec = Satrec.twoline2rv(ln[:69], lines[i + 1][:69], WGS72)
            satrecs.append(rec)
            names.append(pending_name or f"NORAD-{rec.satnum}")
            pending_name = None
            i += 2
        else:
            pending_name = ln.strip().lstrip("0 ").strip() or None
            i += 1
    if not satrecs:
        raise ValueError(f"no TLE records found in {path}")
    return satrecs, names


def _omm_fields_to_satrec(fields: dict) -> Satrec:
    rec = Satrec()
    omm.initialize(rec, {k: str(v) for k, v in fields.items()})
    return rec


def load_omm_csv(path: str | Path) -> tuple[list[Satrec], list[str]]:
    """Load an OMM CSV file as served by CelesTrak (``FORMAT=csv``)."""
    satrecs: list[Satrec] = []
    names: list[str] = []
    with open(path, newline="") as fh:
        for fields in omm.parse_csv(fh):
            satrecs.append(_omm_fields_to_satrec(fields))
            names.append(str(fields.get("OBJECT_NAME", fields.get("NORAD_CAT_ID", "?"))).strip())
    if not satrecs:
        raise ValueError(f"no OMM records found in {path}")
    return satrecs, names


def load_omm_json(path: str | Path) -> tuple[list[Satrec], list[str]]:
    """Load an OMM JSON array as served by CelesTrak (``FORMAT=json``)."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        data = [data]
    satrecs = [_omm_fields_to_satrec(d) for d in data]
    names = [str(d.get("OBJECT_NAME", d.get("NORAD_CAT_ID", "?"))).strip() for d in data]
    if not satrecs:
        raise ValueError(f"no OMM records found in {path}")
    return satrecs, names


def load_satellites(path: str | Path, name_filter: str | None = None,
                    max_sats: int | None = None) -> tuple[list[Satrec], list[str]]:
    """Dispatch on file extension (.tle/.txt/.3le -> TLE, .csv -> OMM CSV, .json -> OMM JSON).

    ``name_filter`` keeps only satellites whose name contains the given substring
    (case-insensitive); ``max_sats`` truncates the list (useful for quick tests).
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in {".tle", ".txt", ".3le", ".2le"}:
        satrecs, names = load_tle_file(p)
    elif suffix == ".csv":
        satrecs, names = load_omm_csv(p)
    elif suffix == ".json":
        satrecs, names = load_omm_json(p)
    else:
        raise ValueError(f"unsupported orbital element file type: {suffix}")
    if name_filter:
        keep = [i for i, n in enumerate(names) if name_filter.lower() in n.lower()]
        satrecs = [satrecs[i] for i in keep]
        names = [names[i] for i in keep]
    if max_sats is not None:
        satrecs, names = satrecs[:max_sats], names[:max_sats]
    return satrecs, names


def write_tle_file(path: str | Path, satrecs: list[Satrec], names: list[str]) -> None:
    """Export satellite records as a 3-line element file (helper for tests/demos)."""
    from sgp4.exporter import export_tle

    with open(path, "w") as fh:
        for rec, name in zip(satrecs, names):
            l1, l2 = export_tle(rec)
            fh.write(f"{name}\n{l1}\n{l2}\n")
