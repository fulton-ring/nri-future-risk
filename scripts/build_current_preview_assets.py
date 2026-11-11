"""Render verified v1.20 Batch results for review; never calculate hazard multipliers."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")
    return {"path": path.name, "sha256": digest(path)}


def display_columns(frame):
    baseline = re.compile(r"^(DRGT|WFIR|EXHT)_(EALT|EALR|RISKV|RISKR|RISKS)$")
    projected = re.compile(
        r"^(DRGT|WFIR|EXHT_L95|EXHT_L99)_(MID|LATE)_(LOWER|HIGHER)_(HM|PALT|PRISKV|PALR|PRISKR|PRISKS|DELTAR)$"
    )
    return [
        name for name in frame if baseline.fullmatch(name) or projected.fullmatch(name)
    ]


def write_attributes(frame, output, level):
    import numpy as np
    import pandas as pd
    import shapely

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    columns = display_columns(frame)
    values = (
        frame[columns]
        .astype(object)
        .where(pd.notna(frame[columns]), None)
        .values.tolist()
    )
    counties = []
    for row, (_, area) in enumerate(frame.iterrows()):
        shape = area.geometry
        if shape.bounds[2] - shape.bounds[0] > 180:
            shape = shapely.transform(
                shape,
                lambda xy: np.column_stack(
                    [
                        np.where(
                            xy[:, 0] < 0, xy[:, 0] + 360, xy[:, 0]
                        ),
                        xy[:, 1],
                    ]
                ),
            )
        counties.append(
            {
                "id": str(area.geoid),
                "name": area["name"],
                "state": area.state,
                "bounds": list(shape.bounds),
                "vintage": area.multiplier_vintage,
                "values": values[row],
            }
        )
    payload = {"columns": columns, "counties": counties}
    result = {}
    if level == "tracts":
        index = {
            "columns": [],
            "counties": [{**area, "values": []} for area in counties],
        }
        write_json(output / "counties.json", index)
        fields = {}
        for column in columns:
            if column.endswith(("_EALR", "_RISKR", "_PALR", "_PRISKR", "_HM")):
                spec = write_json(
                    output / "fields" / f"{column}.json",
                    [area["values"][columns.index(column)] for area in counties],
                )
                spec["path"] = f"fields/{column}.json"
                fields[column] = spec
        shards = {}
        for area in counties:
            shards.setdefault(area["id"][:5], []).append(area)
        hashes = {}
        for prefix, areas in shards.items():
            spec = write_json(
                output / "profiles" / f"{prefix}.json",
                {"columns": columns, "counties": areas},
            )
            hashes[prefix] = spec["sha256"]
        result = {
            "fieldAssets": fields,
            "profileAssets": {
                "template": "profiles/{prefix}.json",
                "prefixLength": 5,
                "hashes": hashes,
            },
        }
    else:
        write_json(output / "counties.json", payload)
    return {**result, "attributes": payload}


def main():
    import geopandas as gpd
    from fri_pipeline.publication import verify_tiles

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-prefix", required=True)
    args = parser.parse_args()
    if digest(args.manifest) != args.manifest_sha256:
        raise ValueError("Result manifest checksum mismatch")
    package = json.loads(args.manifest.read_text())
    if (
        package["baseline"] != "NRI v1.20"
        or package["collection"] != "future-risk-index"
    ):
        raise ValueError("Expected native v1.20 FRI results")
    releases = []
    for level in ("counties", "tracts"):
        folder = f"future-risk-index/fri/{level}/{package['version']}"
        relative = f"{folder}/geoparquet/{level}.parquet"
        parquet = args.source / relative
        if digest(parquet) != package["files"][relative]["sha256"]:
            raise ValueError("GeoParquet differs from completed Batch output")
        frame = gpd.read_parquet(parquet)
        output = args.output / level
        spec = write_attributes(frame, output, level)
        attributes = spec.pop("attributes")
        columns = attributes["columns"]
        tile_frame = frame[
            ["geoid", "area_id", "name", "state", *columns, "geometry"]
        ].copy()
        tile_frame["fips"] = tile_frame.geoid
        with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson") as handle:
            handle.write(tile_frame.to_json(na="null", drop_id=True))
            handle.flush()
            subprocess.run(
                [
                    "tippecanoe",
                    "-o",
                    str(output / "counties.pmtiles"),
                    "-l",
                    level,
                    "-Z5" if level == "tracts" else "-Z0",
                    "-z10" if level == "tracts" else "-z6",
                    "--use-attribute-for-id=area_id",
                    "--no-feature-limit",
                    "--no-tile-size-limit",
                    "--detect-shared-borders",
                    "--force",
                    handle.name,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        verify_tiles(output / "counties.pmtiles", attributes, source_layer=level)
        base = args.public_prefix.rstrip("/") + "/" + level
        for field in spec.get("fieldAssets", {}).values():
            field["path"] = base + "/" + field["path"]
        if "profileAssets" in spec:
            spec["profileAssets"]["template"] = (
                base + "/" + spec["profileAssets"]["template"]
            )

        def metadata(name, folder=folder):
            key = f"{folder}/metadata/{name}"
            path = args.source / key
            if digest(path) != package["files"][key]["sha256"]:
                raise ValueError(f"Version metadata checksum mismatch: {name}")
            return json.loads(path.read_text())

        provenance = metadata("provenance.json")
        validation = metadata("validation.json")
        release = {
            "id": provenance["runId"] + "-" + level,
            "title": "NRI v1.20 · "
            + ("census tracts" if level == "tracts" else "counties"),
            "date": package["version"][1:5]
            + "-"
            + package["version"][5:7]
            + "-"
            + package["version"][7:9],
            "baseline": "NRI v1.20",
            "status": "analysis",
            "geography": level,
            "rankingPopulation": "CONUS",
            "resultsVersion": package["version"],
            "countyCount": len(frame),
            "sourceSha256": digest(parquet),
            "sourceLayer": level,
            "parameters": provenance["parameters"],
            "bins": metadata("rating-bins.json"),
            "validation": validation,
            "resultManifestSha256": args.manifest_sha256,
            "sourceCatalog": f"https://storage.googleapis.com/future-risk-index-results/{folder}/collection.json",
            "sourceData": f"https://storage.googleapis.com/future-risk-index-results/{relative}",
            "methodology": "pipeline/CURRENT_METHODOLOGY.md",
            "codeRevision": provenance["codeRevision"],
            "assets": {
                name: {"path": base + "/" + name, "sha256": digest(output / name)}
                for name in ("counties.json", "counties.pmtiles")
            },
            **spec,
        }
        releases.append(release)
    write_json(ROOT / "src/data/current-releases.json", releases)
    print(
        json.dumps({"releases": [r["id"] for r in releases], "allTilesVerified": True})
    )


if __name__ == "__main__":
    main()
