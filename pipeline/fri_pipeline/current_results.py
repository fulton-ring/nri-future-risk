"""Immutable review files for NRI v1.20 projections, with one version per file."""

import re
from pathlib import Path

from .candidate import write_json
from .results import asset
from .snapshot import sha256


def validate_version(value: str) -> str:
    if not re.fullmatch(r"v[0-9A-Za-z-]{1,62}", value):
        raise ValueError("Expected a version ID without path separators")
    return value


def package_geography(root, version, level, geometry, baseline, scores, bins, validation):
    """Write exact values and shapes; review packaging never activates a release."""
    import geopandas as gpd
    import pandas as pd

    validate_version(version)
    if level not in ("counties", "tracts"):
        raise ValueError("Expected counties or tracts")
    folder = Path(root) / "future-risk-index/fri" / level / version
    if folder.exists():
        raise ValueError("Result versions are immutable; choose an empty version")
    if not geometry.index.equals(baseline.index) or not scores.index.equals(baseline.index):
        raise ValueError("Geometry, baseline and projections must have identical native IDs")
    if set(baseline.columns) & set(scores.columns):
        raise ValueError("Baseline fields must not overwrite projections")
    frame = gpd.GeoDataFrame(
        pd.concat([baseline, scores], axis=1), geometry=geometry.geometry, crs=geometry.crs
    ).to_crs(4326)
    if not frame.geometry.is_valid.all() or frame.geometry.is_empty.any():
        raise ValueError("Invalid result geometry")
    frame.insert(0, "geoid", frame.index.astype(str))
    frame.insert(1, "area_id", frame.index.astype("int64"))
    frame["name"] = (
        baseline.get("COUNTY", geometry.get("name"))
        if level == "counties"
        else "Tract " + baseline.index.str[-6:-2] + "." + baseline.index.str[-2:]
    )
    frame["state"] = baseline.get("STATEABBRV", geometry.get("state"))
    from .snapshot import EXCLUDED

    frame["multiplier_vintage"] = frame["state"].map(
        lambda state: "unavailable" if state in EXCLUDED else "rebuilt"
    )
    (folder / "geoparquet").mkdir(parents=True)
    (folder / "metadata").mkdir()
    path = folder / "geoparquet" / f"{level}.parquet"
    frame.reset_index(drop=True).to_parquet(
        path, index=False, compression="zstd", schema_version="1.1.0", write_covering_bbox=True
    )
    restored = gpd.read_parquet(path)
    if not restored.equals(frame.reset_index(drop=True)):
        raise ValueError("Result GeoParquet round trip changed data")
    write_json(folder / "metadata/rating-bins.json", bins)
    write_json(folder / "metadata/validation.json", validation)
    record = {
        "file": level,
        "title": f"Future Risk Index — {level}",
        "assets": {
            "geoparquet": asset(
                path, folder, f"{level.title()} projections", "application/vnd.apache.parquet"
            )
        },
        "bbox": frame.total_bounds.tolist(),
    }
    for name, title in [
        ("rating-bins.json", "Version-specific rating thresholds"),
        ("validation.json", "Calculation validation"),
    ]:
        record["assets"][name] = asset(
            folder / "metadata" / name, folder, title, "application/json", ("metadata",)
        )
    return record


def write_catalog(root: Path, version: str, records: dict):
    """Create a review catalog with dataset / file / version navigation."""
    from .results import FILE_EXTENSION, PORTOLAN, VERSION_EXTENSION

    validate_version(version)
    collection = root / "future-risk-index"
    description = (
        "Recreated Future Risk Index using NRI v1.20. Review results; "
        "no approved release is activated by this catalog. "
        "Produced by Public Environmental Data Partners and Fulton Ring."
    )

    def catalog(path, identity, title, children):
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            path,
            {
                "stac_version": "1.1.0",
                "stac_extensions": [PORTOLAN],
                "type": "Catalog",
                "id": identity,
                "title": title,
                "description": description,
                "links": [
                    {"rel": "self", "href": "catalog.json"},
                    *[{"rel": "child", "href": href, "title": label} for href, label in children],
                ],
            },
        )

    datasets = {}
    for (dataset, file), record in records.items():
        datasets.setdefault(dataset, []).append((file, record))
        folder = collection / dataset / file / version
        folder.mkdir(parents=True, exist_ok=True)
        write_json(
            folder / "collection.json",
            {
                "stac_version": "1.1.0",
                "stac_extensions": [PORTOLAN, FILE_EXTENSION, VERSION_EXTENSION],
                "type": "Collection",
                "id": f"future-risk-index/{dataset}/{file}/{version}",
                "title": record["title"],
                "description": description,
                "license": "other",
                "version": version,
                "fri:publication_status": "analysis",
                "extent": {
                    "spatial": {"bbox": [record["bbox"]]},
                    "temporal": {"interval": [[None, None]]},
                },
                "assets": record["assets"],
                "links": [
                    {"rel": "self", "href": "collection.json"},
                    {"rel": "parent", "href": "../catalog.json"},
                    {"rel": "root", "href": "../../../../catalog.json"},
                ],
            },
        )
        catalog(
            folder.parent / "catalog.json",
            f"future-risk-index/{dataset}/{file}",
            record["title"],
            [(f"{version}/collection.json", version)],
        )
    for dataset, files in datasets.items():
        catalog(
            collection / dataset / "catalog.json",
            f"future-risk-index/{dataset}",
            dataset,
            [(f"{file}/catalog.json", record["title"]) for file, record in files],
        )
    catalog(
        collection / "catalog.json",
        "future-risk-index",
        "Future Risk Index",
        [(f"{dataset}/catalog.json", dataset) for dataset in datasets],
    )
    catalog(
        root / "catalog.json",
        "future-risk-index-results",
        "Future Risk Index results",
        [("future-risk-index/catalog.json", "Future Risk Index")],
    )


def manifest(root: Path, version: str, provenance: dict) -> dict:
    return {
        "schemaVersion": 1,
        "collection": "future-risk-index",
        "version": validate_version(version),
        "baseline": "NRI v1.20",
        "publishable": False,
        "provenance": provenance,
        "files": {
            p.relative_to(root).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size}
            for p in sorted(root.rglob("*"))
            if p.is_file()
        },
    }
