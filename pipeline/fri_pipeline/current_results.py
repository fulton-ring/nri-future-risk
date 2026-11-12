"""Immutable review files for NRI v1.20 projections, with one version per file."""

import json
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
        "columns": [
            {
                "name": name,
                "type": "binary"
                if name == "geometry"
                else "integer"
                if pd.api.types.is_integer_dtype(frame[name])
                else "number"
                if pd.api.types.is_numeric_dtype(frame[name])
                else "string",
                "nullable": bool(frame[name].isna().any()),
                "is_geometry": name == "geometry",
            }
            for name in frame.columns
        ],
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
    """Create schema-conformant dataset / file / version catalogs."""
    import os

    from .results import FILE_EXTENSION, PORTOLAN, TABLE_EXTENSION, VERSION_EXTENSION

    validate_version(version)
    root = Path(root).resolve()
    collection = root / "future-risk-index"
    description = (
        "Future Risk Index results and reproducibility assets. "
        "Each version documents its baseline and methodology."
    )

    def links(path, title):
        path.parent.mkdir(parents=True, exist_ok=True)
        for name in ("README.md", "AGENTS.md"):
            (path.parent / name).write_text(
                f"# {title}\n\n{description}\n\n"
                "Read catalog.json or collection.json for versioned assets and provenance. "
                "Review status is distinct from an approved map release.\n"
            )
        result = [
            {"rel": "self", "href": path.name, "type": "application/json"},
            {
                "rel": "root",
                "href": os.path.relpath(root / "catalog.json", path.parent),
                "type": "application/json",
            },
            {"rel": "agents", "href": "AGENTS.md", "type": "text/markdown"},
            {"rel": "describedby", "href": "README.md", "type": "text/markdown"},
        ]
        if path.parent != root:
            result.append({"rel": "parent", "href": "../catalog.json", "type": "application/json"})
        return result

    def catalog(path, identity, title, children):
        navigation = links(path, title)
        navigation += [
            {"rel": "child", "href": href, "title": label, "type": "application/json"}
            for href, label in children
        ]
        if identity.count("/") == 2:
            navigation.append(
                {
                    "rel": "latest-version",
                    "href": f"{version}/collection.json",
                    "type": "application/json",
                }
            )
        write_json(
            path,
            {
                "stac_version": "1.1.0",
                "stac_extensions": [PORTOLAN],
                "type": "Catalog",
                "id": identity,
                "title": title,
                "description": description,
                "links": navigation,
            },
        )

    datasets = {}
    for (dataset, file), record in records.items():
        datasets.setdefault(dataset, []).append((file, record))
        folder = collection / dataset / file / version
        path = folder / "collection.json"
        navigation = links(path, record["title"])
        (folder / "LICENSE.md").write_text(
            "# Source data rights\n\nOriginal source files retain their upstream terms. "
            "Original ZIPs, source URLs and hashes accompany these results. "
            "Derived results credit FEMA, Public Environmental Data Partners and Fulton Ring.\n"
        )
        navigation.append({"rel": "license", "href": "LICENSE.md", "type": "text/markdown"})
        producer = record.get("producer") or (
            {"name": "FEMA", "url": "https://www.fema.gov"}
            if dataset == "nri"
            else {"name": "US Census Bureau", "url": "https://www.census.gov"}
            if dataset == "census-boundaries"
            else {
                "name": "Public Environmental Data Partners",
                "url": "https://publicenvirodata.org",
            }
        )
        value = {
            "stac_version": "1.1.0",
            "stac_extensions": [PORTOLAN, FILE_EXTENSION, VERSION_EXTENSION],
            "type": "Collection",
            "id": f"future-risk-index/{dataset}/{file}/{version}",
            "title": record["title"],
            "description": record.get("summary", "NRI v1.20 review results.") + " " + description,
            "license": "other",
            "version": version,
            "fri:publication_status": record.get("status", "analysis"),
            "extent": {
                "spatial": {"bbox": [record["bbox"]]},
                "temporal": {"interval": [[None, None]]},
            },
            "providers": [
                {**producer, "roles": ["producer"]},
                {
                    "name": "Fulton Ring",
                    "url": "https://fultonring.com",
                    "roles": ["processor", "host"],
                },
            ],
            "assets": record["assets"],
            "links": navigation,
        }
        if dataset == "fri" and record.get("columns"):
            value["stac_extensions"].append(TABLE_EXTENSION)
            value.update(
                {
                    "table:columns": record["columns"],
                    "hifld:feature_id_column": "area_id",
                    "hifld:geometry_column": "geometry",
                    "hifld:spatial_status": "spatial",
                }
            )
        write_json(path, value)
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
    validate_catalog_tree(root)


def validate_catalog_tree(root: Path):
    """Validate the pinned official schema and every local navigation/asset target."""
    import jsonschema

    from .snapshot import ROOT

    root = Path(root).resolve()
    schema_path = ROOT / "pipeline/reference/portolan-v0.2.0.schema.json"
    contract = json.loads((ROOT / "pipeline/reference/current-contract.json").read_text())
    if sha256(schema_path) != contract["portolanSchemaSha256"]:
        raise ValueError("Portolan schema checksum mismatch")
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.validators.validator_for(schema)(schema)
    paths = [*root.rglob("catalog.json"), *root.rglob("collection.json")]
    for path in paths:
        value = json.loads(path.read_text())
        validator.validate(value)
        for reference in [*value["links"], *value.get("assets", {}).values()]:
            href = reference["href"]
            if "://" not in href:
                target = (path.parent / href).resolve()
                if not target.is_relative_to(root) or not target.is_file():
                    raise ValueError(f"Catalog target does not resolve: {path}: {href}")
    return len(paths)


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
