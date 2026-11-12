"""One-time backfill: publish FEMA's December 2024 archive as a results version.

The archive never changes, so it is not part of the recurring workflow. Run once by
someone with write access to the results bucket:

    cd pipeline
    uv run --extra results python -m fri_pipeline.fema_archive build --output /tmp/fema
    uv run --extra results python -m fri_pipeline.fema_archive upload --output /tmp/fema \\
        --results-uri gs://future-risk-index-results

``build`` packages files already in the repository; nothing is recalculated. ``upload`` creates
version files only if they are absent (re-runs verify them instead) and merges catalogs, so
existing versions stay listed and the newest recomputed version remains ``latest-version``.
"""

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

from .candidate import write_json
from .results import asset
from .snapshot import CONTRACT, ROOT, sha256

VERSION = "v20241205T000000Z"
DATASET, LEVEL = "fri", "counties"
ORIGINALS = [
    (
        "NRI_Future_Risk_Master_Datasheet_12052024.xlsx",
        "FEMA Future Risk Index master datasheet (December 5, 2024)",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (
        "NRI_Data_Dictionary.xlsx",
        "FEMA National Risk Index data dictionary",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (
        "combined_nri_counties_borders.json",
        "Archived county GeoJSON with FEMA attributes",
        "application/geo+json",
    ),
]
PREVIEW = [
    ("atlas/counties.pmtiles", "Score-bearing PMTiles for the explorer", "application/vnd.pmtiles"),
    ("atlas/counties.json", "Columnar attributes for the explorer", "application/json"),
]


def version_folder(output: Path) -> Path:
    return output / "future-risk-index" / DATASET / LEVEL / VERSION


def build(output: Path) -> dict:
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import shape

    from .current_results import write_catalog

    output = Path(output).resolve()
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    folder = version_folder(output)
    public = ROOT / "public"
    if sha256(public / ORIGINALS[0][0]) != CONTRACT["workbookSha256"]:
        raise ValueError("Archived workbook differs from the frozen contract")

    assets, sources = {}, []
    for directory, items, role in (
        ("originals", ORIGINALS, "source"),
        ("preview", PREVIEW, "visual"),
    ):
        for name, title, media in items:
            source = public / name
            target = folder / directory / PurePosixPath(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            assets[target.name] = asset(target, folder, title, media, (role,))
            sources.append({"path": f"public/{name}", "sha256": sha256(source)})

    # GeoParquet from FEMA's archived GeoJSON, values unchanged, plus the usual ID columns.
    features = json.loads((public / "combined_nri_counties_borders.json").read_text())["features"]
    rows = [
        {
            "geoid": f["properties"]["STCOFIPS"],
            "area_id": int(f["properties"]["STCOFIPS"]),
            **f["properties"],
        }
        for f in features
    ]
    frame = gpd.GeoDataFrame(
        rows, geometry=[shape(f["geometry"]) for f in features], crs="EPSG:4326"
    )
    if not frame["geoid"].is_unique:
        raise ValueError("Archived GeoJSON repeats county identifiers")
    parquet = folder / "geoparquet" / "counties.parquet"
    parquet.parent.mkdir(parents=True)
    frame.to_parquet(parquet, index=False)
    check = gpd.read_parquet(parquet)
    for row, feature in zip(check.to_dict("records"), features, strict=True):
        for key, value in feature["properties"].items():
            stored = row[key]
            if value is None:
                if not pd.isna(stored):
                    raise ValueError(f"{row['geoid']} {key}: null became {stored!r}")
            elif stored != value:
                raise ValueError(f"{row['geoid']} {key}: {value!r} became {stored!r}")
    assets["geoparquet"] = asset(
        parquet,
        folder,
        "FEMA archived county attributes and geometry",
        "application/vnd.apache.parquet",
    )

    (folder / "metadata").mkdir()
    shutil.copyfile(
        ROOT / "pipeline/reference/rating-bins.json", folder / "metadata/rating-bins.json"
    )
    assets["rating-bins.json"] = asset(
        folder / "metadata/rating-bins.json",
        folder,
        "FEMA published rating thresholds",
        "application/json",
        ("metadata",),
    )
    write_json(
        folder / "metadata/provenance.json",
        {
            "version": VERSION,
            "baseline": "NRI v1.19",
            "description": "FEMA's Future Risk Index as published on December 5, 2024 "
            "and archived before removal. "
            "Values are FEMA's; nothing is recalculated.",
            "workbookSha256": CONTRACT["workbookSha256"],
            "countiesWithGeometry": len(features),
            "countiesInWorkbook": CONTRACT["population"],
            "repositorySources": sources,
        },
    )
    assets["provenance"] = asset(
        folder / "metadata/provenance.json",
        folder,
        "Source files and hashes",
        "application/json",
        ("metadata",),
    )

    columns = [
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
    ]
    write_catalog(
        output,
        VERSION,
        {
            (DATASET, LEVEL): {
                "title": "Future Risk Index — counties",
                "summary": (
                    "FEMA's December 2024 Future Risk Index archive (NRI v1.19 baseline), "
                    "published without recalculation."
                ),
                "status": "archive",
                "producer": {"name": "FEMA", "url": "https://www.fema.gov"},
                "bbox": frame.total_bounds.tolist(),
                "assets": assets,
                "columns": columns,
            }
        },
    )
    return {
        "version": VERSION,
        "folder": str(folder),
        "counties": len(features),
        "assets": sorted(assets),
    }


def upload(output: Path, results_uri: str, client=None) -> dict:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    from .current_publish import merge_catalog
    from .storage import split_prefix

    output = Path(output).resolve()
    folder = version_folder(output)
    client = client or storage.Client()
    bucket_name, prefix = split_prefix(results_uri)
    prefix = f"{prefix.strip('/')}/" if prefix.strip("/") else ""
    bucket = client.bucket(bucket_name)
    created = verified = merged = 0
    files = sorted(p for p in output.rglob("*") if p.is_file())
    for path in files:
        if path.name == "catalog.json":
            continue
        key = prefix + path.relative_to(output).as_posix()
        digest = sha256(path)
        existing = bucket.get_blob(key)
        if existing is not None:
            # Shared guidance outside this version is retained; version files must match exactly.
            if path.is_relative_to(folder) and (existing.metadata or {}).get("sha256") != digest:
                raise ValueError(f"Existing object differs from the archive build: {key}")
            verified += 1
            continue
        blob = bucket.blob(key)
        blob.metadata = {"sha256": digest}
        blob.upload_from_filename(str(path), if_generation_match=0)
        created += 1
    # Merge catalogs deepest first, only after every version file is present.
    for path in sorted((p for p in files if p.name == "catalog.json"), key=lambda p: -len(p.parts)):
        key = prefix + path.relative_to(output).as_posix()
        incoming = json.loads(path.read_text())
        for attempt in range(3):
            prior = bucket.get_blob(key)
            previous = (
                json.loads(prior.download_as_bytes(if_generation_match=prior.generation))
                if prior
                else None
            )
            body = json.dumps(merge_catalog(previous, incoming), separators=(",", ":")) + "\n"
            blob = bucket.blob(key)
            blob.metadata = {"sha256": hashlib.sha256(body.encode()).hexdigest()}
            try:
                blob.upload_from_string(
                    body,
                    content_type="application/json",
                    if_generation_match=prior.generation if prior else 0,
                )
                merged += 1
                break
            except PreconditionFailed:
                if attempt == 2:
                    raise
    return {"version": VERSION, "created": created, "verified": verified, "catalogsMerged": merged}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build").add_argument("--output", type=Path, required=True)
    up = sub.add_parser("upload")
    up.add_argument("--output", type=Path, required=True)
    up.add_argument("--results-uri", required=True)
    args = parser.parse_args()
    result = (
        build(args.output) if args.command == "build" else upload(args.output, args.results_uri)
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
