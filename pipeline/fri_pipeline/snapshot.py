"""Hash-checked prepared inputs. Hazard calculation has no network access or latest lookup."""

import hashlib
import json
import re
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "pipeline/reference/contract.json").read_text())
EXCLUDED = {"AK", "HI", "AS", "GU", "MP", "PR", "VI"}
SSP = {"LOWER": "ssp245", "HIGHER": "ssp585"}
SPANS = {"historical": (1976, 2005), "MID": (2036, 2065), "LATE": (2070, 2099)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_master() -> pd.DataFrame:
    path = ROOT / "public/NRI_Future_Risk_Master_Datasheet_12052024.xlsx"
    if sha256(path) != CONTRACT["workbookSha256"]:
        raise ValueError("Frozen baseline workbook hash mismatch")
    master = pd.read_excel(path, dtype={"STCOFIPS": str}).set_index("STCOFIPS")
    master.index = master.index.str.zfill(5)
    if len(master) != CONTRACT["population"] or not master.index.is_unique:
        raise ValueError("Frozen baseline population mismatch")
    return master


def source_domain(values: np.ndarray) -> np.ndarray:
    """Only all-time NaN cells are structural masks; mixed gaps and infinities fail."""
    if values.ndim != 2 or not len(values):
        raise ValueError("Expected a nonempty time-by-cell array")
    valid = np.isfinite(values).all(axis=0)
    masked = np.isnan(values).all(axis=0)
    if not (valid | masked).all():
        raise ValueError("Temporal gaps or invalid values in supported climate cells")
    return valid


class Snapshot:
    """A manifest plus local files, all verified before any computation."""

    SSP = SSP

    def __init__(self, manifest: Path):
        self.path = manifest.resolve()
        self.root = self.path.parent
        self.manifest = json.loads(self.path.read_text())
        if (
            self.manifest.get("methodology") != CONTRACT["id"]
            or self.manifest.get("rebuildCommit") != CONTRACT["rebuildCommit"]
        ):
            raise ValueError(
                "Snapshot methodology and rebuild commit must match the frozen contract"
            )
        if self.manifest.get("schemaVersion") != 1 or self.manifest.get("coverage") != "CONUS":
            raise ValueError("Expected schemaVersion 1 and CONUS coverage")
        sources = self.manifest.get("sources", [])
        ids = [source.get("id") for source in sources]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("Unique source provenance is required")
        for source in sources:
            if (
                not source.get("title")
                or not source.get("retrievedAt")
                or not str(source.get("url", "")).startswith("https://")
                or not re.fullmatch(r"[a-f0-9]{64}", source.get("sha256", ""))
            ):
                raise ValueError("Each source needs title, HTTPS URL, retrieval date and SHA-256")
        if not self.manifest.get("artifacts"):
            raise ValueError("Snapshot has no artifacts")
        self.files = {}
        self._domain_masks = {}
        self.coverage_diagnostics = {}
        for name, spec in self.manifest["artifacts"].items():
            path = Path(spec["path"])
            resolved = (self.root / path).resolve()
            if path.is_absolute() or not resolved.is_relative_to(self.root):
                raise ValueError(f"Invalid artifact path: {path}")
            if not spec.get("sourceIds") or not set(spec["sourceIds"]).issubset(ids):
                raise ValueError(f"Unknown or missing source for {name}")
            if not resolved.is_file() or sha256(resolved) != spec["sha256"]:
                raise ValueError(f"Artifact hash mismatch: {name}")
            self.files[name] = resolved

    def record_domain(self, family: str, valid: np.ndarray, weights) -> None:
        previous = self._domain_masks.get(family)
        if previous is not None and not np.array_equal(previous, valid):
            raise ValueError(f"Source domain mask changes across variables/scenarios: {family}")
        covered = np.asarray(weights @ valid.astype(float)).ravel()
        if (covered <= 0).any():
            raise ValueError(f"Missing valid climate coverage for {(covered <= 0).sum()} counties")
        fraction = covered / np.asarray(weights.sum(axis=1)).ravel()
        self._domain_masks[family] = valid.copy()
        self.coverage_diagnostics[family] = {
            "weightedCells": len(valid),
            "structuralNoDataCells": int((~valid).sum()),
            "counties": weights.shape[0],
            "minimumCountyCoverage": float(fraction.min()),
            "medianCountyCoverage": float(np.median(fraction)),
            "countiesWithPartialCoverage": int((fraction < 1 - 1e-10).sum()),
        }

    def file(self, key: str) -> Path:
        if key not in self.files:
            raise ValueError(f"Missing snapshot artifact: {key}")
        return self.files[key]

    def ids(self) -> pd.Index:
        return self.county_ids

    @cached_property
    def county_ids(self) -> pd.Index:
        ids = pd.Index(json.loads(self.file("county_ids").read_text()), name="STCOFIPS")
        expected = self.baseline().index
        if not ids.equals(expected):
            raise ValueError("Snapshot county IDs must match all CONUS baseline counties in order")
        return ids

    def baseline(self) -> pd.DataFrame:
        return self.frozen_baseline

    @cached_property
    def frozen_baseline(self) -> pd.DataFrame:
        master = read_master()
        return master.loc[~master.STATEABBRV.isin(EXCLUDED)]

    def weights(self, key: str):
        weights = sparse.load_npz(self.file(key)).tocsr()
        ids = self.ids()
        if (
            weights.shape[0] != len(ids)
            or not np.isfinite(weights.data).all()
            or (weights.data < 0).any()
            or (np.asarray(weights.sum(axis=1)) <= 0).any()
        ):
            raise ValueError(f"Invalid county weights: {key}")
        return weights, ids

    def county_weights(self):
        return self.weights("nex_weights")

    def loca2_county_weights(self):
        return self.weights("loca2_weights")

    def cell_coordinates(self) -> pd.DataFrame:
        frame = pd.read_csv(self.file("nex_coordinates"))
        if (
            len(frame) != self.county_weights()[0].shape[1]
            or not np.isfinite(frame[["lat", "lon"]]).all().all()
            or not frame.lat.between(-90, 90).all()
        ):
            raise ValueError("Invalid NEX cell coordinates")
        return frame

    def monthly(self, variable: str, scenario: str):
        with np.load(self.file(f"monthly_{variable}_{scenario}"), allow_pickle=False) as data:
            values, months = data["values"], pd.DatetimeIndex(data["months"])
        expected = pd.date_range("1950-01-01", "2100-12-01", freq="MS")
        if not months.equals(expected) or values.shape != (
            len(expected),
            self.county_weights()[0].shape[1],
        ):
            raise ValueError("Monthly inputs must cover 1950–2100 and match NEX weights")
        self.record_domain("nex-monthly", source_domain(values), self.county_weights()[0])
        return values, months

    def fwi(self, scenario: str, period: str, variable: str, ensemble: str):
        if variable != "FWI_P95" or ensemble != "MME75":
            raise ValueError("Frozen wildfire method requires FWI_P95 / MME75")
        with np.load(self.file(f"fwi_{scenario}_{period}"), allow_pickle=False) as data:
            values, years = data["values"], data["years"]
        first, last = SPANS[period]
        if not np.array_equal(years, np.arange(first, last + 1)) or values.shape != (
            len(years),
            self.county_weights()[0].shape[1],
        ):
            raise ValueError("FWI snapshot has missing years or mismatched cell support")
        self.record_domain("nex-fwi", source_domain(values), self.county_weights()[0])
        return values

    def county_fuel_shares(self) -> pd.DataFrame:
        frame = pd.read_csv(self.file("fuel_shares"), dtype={"STCOFIPS": str})
        frame = frame.set_index("STCOFIPS")
        if (
            not frame.index.equals(self.ids())
            or "nonburnable" not in frame
            or not np.isfinite(frame).all().all()
            or (frame < 0).any().any()
            or (frame > 1).any().any()
            or not np.allclose(frame.sum(axis=1), 1, atol=1e-5)
        ):
            raise ValueError("Fuel shares must be complete, sum to one, and match county IDs")
        return frame

    def loca2_histogram(self, scenario: str, period: str):
        with np.load(self.file(f"loca2_{scenario}_{period}"), allow_pickle=False) as data:
            edges, counts = data["edges"], data["counts"]
        expected = np.concatenate([[-np.inf], np.arange(-10.0, 40.05, 0.1), [np.inf]])
        if (
            not np.array_equal(edges, expected)
            or counts.shape != (len(edges), self.loca2_county_weights()[0].shape[1])
            or not np.isfinite(counts).all()
            or (counts < 0).any()
            or (counts != np.floor(counts)).any()
        ):
            raise ValueError("Invalid LOCA2 histogram support/counts")
        first, last = SPANS[period]
        days = len(pd.date_range(f"{first}-01-01", f"{last}-12-31"))
        if not np.all(counts.sum(axis=0) == days):
            raise ValueError("LOCA2 histogram must account for every day including no-data")
        if not ((counts[-1] == 0) | (counts[-1] == days)).all():
            raise ValueError("Missing LOCA2 days within supported cells")
        self.record_domain("loca2", counts[-1] == 0, self.loca2_county_weights()[0])
        return edges, counts
