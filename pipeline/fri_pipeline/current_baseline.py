"""Native December 2025 NRI v1.20 tables; no archive crosswalk or null filling."""

import zipfile
from pathlib import Path

import pandas as pd

from .snapshot import EXCLUDED, sha256

RELEASE = "December 2025"
GEOGRAPHIES = {
    "county": ("STCOFIPS", 5, "NRI_Table_Counties.csv"),
    "tract": ("TRACTFIPS", 11, "NRI_Table_CensusTracts.csv"),
}
CT_COUNTIES = {f"09{code:03}" for code in range(110, 191, 10)}


def validate_ids(ids: pd.Index, geography: str) -> None:
    _, width, _ = GEOGRAPHIES[geography]
    if (
        not ids.is_unique
        or not ids.to_series().astype("string").str.fullmatch(rf"\d{{{width}}}", na=False).all()
    ):
        raise ValueError(f"{geography} IDs must be unique native {width}-digit strings")


def normalize_baseline(
    raw: pd.DataFrame, geography: str, *, validate_population: bool = True
) -> pd.DataFrame:
    id_column, _, _ = GEOGRAPHIES[geography]
    if "NRI_VER" not in raw or set(raw.NRI_VER.dropna()) != {RELEASE} or raw.NRI_VER.isna().any():
        raise ValueError(f"Expected strictly {RELEASE} NRI v1.20 release")
    if id_column not in raw:
        raise ValueError(f"Missing native IDs: {id_column}")
    frame = raw.copy().set_index(id_column)
    validate_ids(frame.index, geography)
    if "STATEABBRV" not in frame or frame.STATEABBRV.isna().any():
        raise ValueError("Every native area needs STATEABBRV")
    if geography == "tract":
        if "STCOFIPS" not in frame or not (frame.index.str[:5] == frame.STCOFIPS.to_numpy()).all():
            raise ValueError("Native tract and county IDs disagree")
    rename = {c: c.replace("HWAV_", "EXHT_", 1) for c in frame if c.startswith("HWAV_")}
    if set(rename.values()).intersection(frame.columns):
        raise ValueError("Conflicting HWAV/EXHT fields")
    frame = frame.rename(columns=rename)
    required = [
        f"{h}_{f}" for h in ("DRGT", "WFIR", "EXHT") for f in ("EALT", "RISKV", "EALR", "RISKR")
    ]
    if set(required) - set(frame):
        raise ValueError(f"Missing baseline fields: {sorted(set(required) - set(frame))}")
    for h in ("DRGT", "WFIR", "EXHT"):
        for f in ("EALT", "RISKV"):
            frame[f"{h}_{f}"] = pd.to_numeric(frame[f"{h}_{f}"], errors="raise")
    if validate_population:
        county_ids = set(frame.index if geography == "county" else frame.STCOFIPS)
        if {x for x in county_ids if x.startswith("09")} != CT_COUNTIES:
            raise ValueError("Expected nine native Connecticut planning region county IDs")
        if geography == "county" and (
            len(frame) != 3232 or (~frame.STATEABBRV.isin(EXCLUDED)).sum() != 3109
        ):
            raise ValueError("NRI v1.20 county population must be 3232 national / 3109 CONUS")
        if geography == "tract" and (
            len(frame) != 85154 or (~frame.STATEABBRV.isin(EXCLUDED)).sum() != 83481
        ):
            raise ValueError("NRI v1.20 tract population must be 85154 national / 83481 CONUS")
    frame.attrs.update({"nriVersion": "1.20", "release": RELEASE, "geography": geography})
    return frame


def load_baseline(
    path: Path,
    geography: str,
    *,
    expected_sha256: str | None = None,
    validate_population: bool = True,
) -> pd.DataFrame:
    path = Path(path)
    digest = sha256(path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("NRI source SHA-256 mismatch")
    id_column, _, filename = GEOGRAPHIES[geography]
    with zipfile.ZipFile(path) as archive:
        matches = [n for n in archive.namelist() if Path(n).name == filename]
        if len(matches) != 1:
            raise ValueError(f"Expected one official {filename}")
        with archive.open(matches[0]) as handle:
            raw = pd.read_csv(
                handle, dtype={id_column: str, "STCOFIPS": str, "STATEFIPS": str, "COUNTYFIPS": str}
            )
    frame = normalize_baseline(raw, geography, validate_population=validate_population)
    frame.attrs["sourceSha256"] = digest
    return frame
