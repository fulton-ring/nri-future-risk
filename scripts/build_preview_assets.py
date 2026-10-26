"""Render a hash-pinned analysis GeoParquet into review-only map assets; no hazard computation."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


def main():
    import geopandas as gpd
    from fri_pipeline.publication import verify_tiles

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--geoparquet", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if digest(args.manifest) != args.manifest_sha256:
        raise ValueError("Results manifest hash mismatch")
    manifest = json.loads(args.manifest.read_text())
    if manifest["collection"] != "future-risk-index" or manifest["publishable"]:
        raise ValueError(
            "This builder is only for the explicitly selected analysis preview"
        )
    key = f"future-risk-index/fri/counties/{manifest['version']}/geoparquet/counties.parquet"
    source_sha = digest(args.geoparquet)
    if source_sha != manifest["files"][key]["sha256"]:
        raise ValueError("County GeoParquet differs from the completed Batch result")
    frame = gpd.read_parquet(args.geoparquet)
    columns = [
        k
        for k in frame.columns
        if k.startswith(("WFIR_", "DRGT_", "EXHT_", "CFLD_", "HRCN_"))
    ]
    fields = [
        "county_id",
        "fips",
        "name",
        "state",
        "multiplier_vintage",
        *columns,
        "geometry",
    ]
    features = json.loads(frame[fields].to_json(na="null", drop_id=True))["features"]
    indexed = {f["properties"]["fips"]: f for f in features}
    baseline = json.loads((ROOT / "public/atlas/counties.json").read_text())
    if (
        set(indexed) != {c["id"] for c in baseline["counties"]}
        or len(features) != manifest["featureCount"]
    ):
        raise ValueError("Preview county identity differs from the validated geometry")
    counties = []
    for c in baseline["counties"]:
        props = indexed[c["id"]]["properties"]
        counties.append(
            {
                **c,
                "vintage": props["multiplier_vintage"],
                "values": [props[k] for k in columns],
            }
        )
    payload = {"columns": columns, "counties": counties}
    output = ROOT / "public/preview"
    output.mkdir(exist_ok=True)
    (output / "counties.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False)
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson") as handle:
        json.dump(
            {"type": "FeatureCollection", "features": features}, handle, allow_nan=False
        )
        handle.flush()
        subprocess.run(
            [
                "tippecanoe",
                "-o",
                str(output / "counties.pmtiles"),
                "-l",
                "counties",
                "-Z0",
                "-z6",
                "--use-attribute-for-id=county_id",
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
    # Zoom 6 plus overzoom keeps the review archive within Pages' 25 MiB per-file limit.
    # All county attributes remain present and are checked in every decoded tile.
    verify_tiles(output / "counties.pmtiles", payload)
    for name in ["report.md", "provenance.json", "validation.json"]:
        spec = manifest["files"][
            f"future-risk-index/fri/counties/{manifest['version']}/metadata/{name}"
        ]
        source = args.report_dir / name
        if digest(source) != spec["sha256"]:
            raise ValueError(f"Analysis metadata hash mismatch: {name}")
        shutil.copyfile(source, output / name)
    release = {
        "id": manifest["analysisId"],
        "title": "Available-year analysis preview",
        "date": "2026-10-25",
        "baseline": "NRI v1.19",
        "status": "analysis",
        "sourceSha256": source_sha,
        "resultManifestSha256": args.manifest_sha256,
        "countyCount": len(counties),
        "assets": {
            name: {"path": f"preview/{name}", "sha256": digest(output / name)}
            for name in ["counties.json", "counties.pmtiles"]
        },
        "sourceLayer": "counties",
    }
    (ROOT / "src/data/analysis-preview.json").write_text(
        json.dumps(release, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "counties": len(counties),
                "attributes": len(columns),
                "pmtilesBytes": (output / "counties.pmtiles").stat().st_size,
                "release": release["id"],
                "allTilesVerified": True,
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
