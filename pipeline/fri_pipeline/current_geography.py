"""Current native boundaries and sparse overlaps retaining the saved climate support."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from .current_baseline import validate_ids
from .snapshot import EXCLUDED, Snapshot, sha256, source_domain


def load_geography(paths: list[Path], baseline: pd.DataFrame, *, conus_only: bool = True):
    """Read Census 2024 cb_*_500k county or per-state tract ZIPs in baseline order."""
    import geopandas as gpd
    import shapely

    geography = baseline.attrs["geography"]
    pieces = []
    for path in paths:
        path = Path(path)
        if not path.name.startswith("cb_2024_") or "_500k" not in path.name:
            raise ValueError("Expected Census 2024 500k boundary source")
        piece = gpd.read_file(path)
        if piece.crs is None or "GEOID" not in piece:
            raise ValueError("Boundary source needs CRS and native GEOID")
        pieces.append(piece[["GEOID", "geometry"]].to_crs(4326))
    frame = gpd.GeoDataFrame(pd.concat(pieces), crs=4326).set_index("GEOID")
    validate_ids(frame.index, geography)
    expected = (
        baseline.loc[~baseline.STATEABBRV.isin(EXCLUDED)].index if conus_only else baseline.index
    )
    if set(expected) - set(frame.index):
        raise ValueError("Boundary source is missing native NRI IDs")
    extras = sorted(set(frame.index) - set(baseline.index))
    frame = frame.loc[expected].copy()
    frame.index.name = baseline.index.name
    frame.geometry = shapely.make_valid(frame.geometry.to_numpy())
    if frame.geometry.is_empty.any() or frame.geometry.isna().any():
        raise ValueError("Empty native geometry")
    frame.attrs["excludedBoundaryIds"] = extras
    frame.attrs["sources"] = {str(Path(p).name): sha256(Path(p)) for p in paths}
    return frame


def overlap_weights(
    areas,
    coordinates: pd.DataFrame,
    cache_dir: Path,
    source_fingerprints: dict,
    *,
    batch_size: int = 256,
):
    """Sparse projected intersection areas; coordinate row order is never changed.

    Both climate grids deliberately retain the archived boxes of halfwidth 0.125°.
    Tract boundaries supply aggregation, not additional climate resolution.
    """
    import geopandas as gpd
    import shapely

    if batch_size < 1 or areas.crs is None or not areas.index.is_unique or len(areas) == 0:
        raise ValueError("Expected nonempty unique areas, CRS, and positive batch size")
    xy = coordinates[["lon", "lat"]].to_numpy(dtype=float)
    if len(xy) == 0 or not np.isfinite(xy).all() or (np.abs(xy[:, 1]) > 90).any():
        raise ValueError("Invalid saved climate coordinates")
    # Match existing acquisition longitude normalization without changing the saved order.
    xy[:, 0] = (xy[:, 0] + 180) % 360 - 180
    native = areas.to_crs(4326)
    digest = hashlib.sha256()
    digest.update(json.dumps(list(native.index)).encode())
    for geom in native.geometry:
        digest.update(geom.wkb)
    metadata = {
        "schemaVersion": 1,
        "geometrySha256": digest.hexdigest(),
        "coordinateSha256": hashlib.sha256(xy.tobytes()).hexdigest(),
        "sources": source_fingerprints,
        "halfWidthDegrees": 0.125,
        "areaCRS": "EPSG:5070",
        "areaUnits": "squareMetres",
        "rows": len(areas),
        "columns": len(xy),
    }
    key = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output, meta = directory / f"{key}.npz", directory / f"{key}.json"
    if output.exists() and meta.exists():
        saved = json.loads(meta.read_text())
        if saved != metadata:
            raise ValueError("Weight cache provenance mismatch")
        result = sparse.load_npz(output).tocsr()
        if result.shape != (len(areas), len(xy)):
            raise ValueError("Weight cache shape mismatch")
    else:
        cells = gpd.GeoSeries(
            shapely.box(xy[:, 0] - 0.125, xy[:, 1] - 0.125, xy[:, 0] + 0.125, xy[:, 1] + 0.125),
            crs=4326,
        )
        cells = cells.to_crs(5070)
        # Only candidate pairs for one area batch are materialized, never the cross product.
        tree = cells.sindex
        projected = native.to_crs(5070).geometry.to_numpy()
        rows, columns, values = [], [], []
        for start in range(0, len(native), batch_size):
            pairs = tree.query(projected[start : start + batch_size], predicate="intersects")
            if pairs.shape[1] == 0:
                continue
            row, col = pairs[0] + start, pairs[1]
            projected_cells = cells.to_numpy()[col]
            area = shapely.area(shapely.intersection(projected[row], projected_cells))
            positive = np.isfinite(area) & (area > 0)
            rows.extend(row[positive])
            columns.extend(col[positive])
            values.extend(area[positive])
        result = sparse.csr_matrix((values, (rows, columns)), shape=(len(areas), len(xy)))
    if (
        not np.isfinite(result.data).all()
        or (result.data <= 0).any()
        or (np.asarray(result.sum(axis=1)).ravel() <= 0).any()
    ):
        raise ValueError("Every area needs positive finite climate support")
    if not output.exists() or not meta.exists():
        temporary = output.with_suffix(".partial.npz")
        sparse.save_npz(temporary, result)
        temporary.replace(output)
        meta.write_text(json.dumps(metadata, indent=2))
    return result, metadata


class GeographySnapshot:
    """Target geography adapter around an already verified legacy climate Snapshot.

    County fuel shares must match the updated county baseline exactly. Tracts never
    need fuels: callers must supply the separately county-fitted gamma to wildfire.
    """

    def __init__(
        self,
        verified: Snapshot,
        baseline: pd.DataFrame,
        nex_weights,
        loca_weights,
        fuel_shares: pd.DataFrame | None = None,
    ):
        self.verified = verified
        self.full_baseline = baseline
        self._baseline = baseline.loc[~baseline.STATEABBRV.isin(EXCLUDED)]
        self._ids = self._baseline.index
        self.SSP = verified.SSP
        self._weights = {"nex": nex_weights.tocsr(), "loca2": loca_weights.tocsr()}
        self._fuels = fuel_shares
        self._domain_masks = {}
        self.coverage_diagnostics = {}
        for family, weights in self._weights.items():
            if (
                weights.shape[0] != len(self._ids)
                or not np.isfinite(weights.data).all()
                or (weights.data < 0).any()
                or (np.asarray(weights.sum(axis=1)) <= 0).any()
            ):
                raise ValueError(f"Invalid target weights: {family}")

    def ids(self):
        return self._ids

    def baseline(self):
        return self._baseline

    def county_weights(self):
        return self._weights["nex"], self._ids

    def loca2_county_weights(self):
        return self._weights["loca2"], self._ids

    def cell_coordinates(self):
        return self.verified.cell_coordinates()

    def _record(self, family, valid, weights):
        if len(valid) != weights.shape[1]:
            raise ValueError("Climate coordinate/target weight support mismatch")
        Snapshot.record_domain(self, family, valid, weights)

    def monthly(self, variable, scenario):
        values, months = self.verified.monthly(variable, scenario)
        self._record("nex-monthly", source_domain(values), self._weights["nex"])
        return values, months

    def fwi(self, scenario, period, variable, ensemble):
        values = self.verified.fwi(scenario, period, variable, ensemble)
        self._record("nex-fwi", source_domain(values), self._weights["nex"])
        return values

    def loca2_histogram(self, scenario, period):
        edges, counts = self.verified.loca2_histogram(scenario, period)
        self._record("loca2", counts[-1] == 0, self._weights["loca2"])
        return edges, counts

    def county_fuel_shares(self):
        frame = self._fuels
        if self.full_baseline.attrs.get("geography") == "tract":
            raise ValueError("Wildfire elasticity must be fitted at county level")
        if frame is None or not frame.index.equals(self._ids) or "nonburnable" not in frame:
            raise ValueError("Updated county fuel shares must match native county IDs exactly")
        if (
            not np.isfinite(frame).all().all()
            or (frame < 0).any().any()
            or (frame > 1).any().any()
            or not np.allclose(frame.sum(axis=1), 1, atol=1e-5)
        ):
            raise ValueError("Invalid updated county fuel shares")
        return frame
