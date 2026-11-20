"""Batch-only acquisition and Hamilton calculation for native NRI v1.20 geographies."""

import argparse
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from .candidate import validate_id, write_json
from .current_results import manifest, package_geography, validate_version, write_catalog
from .snapshot import ROOT, Snapshot, sha256

CONTRACT = json.loads((ROOT / "pipeline/reference/current-contract.json").read_text())


def fetch(url: str, destination: Path, expected: str | None = None) -> dict:
    import requests

    if url.startswith("gs://"):
        from .storage import download

        download(url, destination, expected)
    elif not url.startswith("https://"):
        raise ValueError("Source downloads require HTTPS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + ".partial")
        for attempt in range(3):
            try:
                with requests.get(url, stream=True, timeout=(30, 600)) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as stream:
                        for chunk in response.iter_content(8 << 20):
                            stream.write(chunk)
                temporary.replace(destination)
                break
            except (requests.RequestException, OSError):
                temporary.unlink(missing_ok=True)
                if attempt == 2:
                    raise
    digest = sha256(destination)
    if expected is not None and digest != expected:
        raise ValueError(f"Source hash mismatch: {url}")
    print(f"Verified {destination.name}: {digest}", flush=True)
    return {
        "url": url,
        "sha256": digest,
        "bytes": destination.stat().st_size,
        "retrievedAt": datetime.now(UTC).isoformat(),
        "path": destination.name,
    }


def climate_inputs(directory: Path, spec: dict) -> tuple[Snapshot, dict]:
    path = directory / "snapshot.json"
    fetch(spec["url"], path, spec["sha256"])
    payload = json.loads(path.read_text())
    prefix = spec["url"].rsplit("/", 1)[0]

    def transfer(item):
        name = Path(item["path"])
        if name.is_absolute() or not (directory / name).resolve().is_relative_to(
            directory.resolve()
        ):
            raise ValueError("Invalid climate artifact path")
        return fetch(f"{prefix}/{name.as_posix()}", directory / name, item["sha256"])

    with ThreadPoolExecutor(6) as pool:
        list(pool.map(transfer, payload["artifacts"].values()))
    return Snapshot(path), spec


def fuels(areas, directory: Path):
    """Resample native current counties against the exact archived LF2022 500m grid."""
    import numpy as np
    import rasterio

    sys.path.insert(0, str(ROOT / "pipeline/vendor"))
    from fri_rebuild import data

    os.environ["FRI_CACHE"] = str(directory)
    left, bottom, right, top = data.LANDFIRE_BOUNDS
    width = int(np.ceil((right - left) / data.PIXEL))
    height = int(np.ceil((top - bottom) / data.PIXEL))
    grid = np.zeros((height, width), dtype=np.uint8)
    covered = np.zeros((height, width), dtype=bool)
    records = []
    for spec in CONTRACT["landfireTiles"]:
        path = directory / "landfire" / Path(urlparse(spec["url"]).path).name
        records.append(fetch(spec["url"], path, spec["sha256"]))
        with rasterio.open(path) as tile:
            if tile.crs.to_epsg() != 5070 or tile.res != (500.0, 500.0):
                raise ValueError("Archived LF2022 tile support differs from the 500m contract")
            row = round((top - tile.transform.f) / data.PIXEL)
            column = round((tile.transform.c - left) / data.PIXEL)
            block = tile.read(1)
            if row < 0 or column < 0 or row + tile.height > height or column + tile.width > width:
                raise ValueError("LF2022 tile lies outside the fixed grid")
            target = (slice(row, row + tile.height), slice(column, column + tile.width))
            if covered[target].any():
                raise ValueError("Overlapping archived LF2022 tiles")
            grid[target] = block
            covered[target] = True
    if not covered.all():
        raise ValueError("Incomplete archived LF2022 grid")
    np.save(data.cache("landfire", "fbfm40_lf2022_500m.npy"), grid)
    return data.fuel_shares(areas, "nri_v120_counties"), records


def execute(
    work: Path,
    output: Path,
    version: str,
    run_id: str,
    revision: str,
    snapshot_spec: dict | None = None,
):
    import pandas as pd
    from scipy import sparse

    from .current_baseline import load_baseline
    from .current_flow import run
    from .current_geography import GeographySnapshot, load_geography, overlap_weights
    from .results import asset
    from .snapshot import EXCLUDED

    validate_id(run_id)
    validate_version(version)
    if not __import__("re").fullmatch("[a-f0-9]{40}", revision):
        raise ValueError("A complete source revision is required")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be empty")
    sources, tables = {}, {}
    for level, key in [("counties", "countyTable"), ("tracts", "tractTable")]:
        spec = CONTRACT[key]
        path = work / "sources" / Path(urlparse(spec["url"]).path).name
        sources[key] = fetch(spec["url"], path, spec["sha256"])
        tables[level] = load_baseline(
            path, "county" if level == "counties" else "tract", expected_sha256=spec["sha256"]
        )
    spec = CONTRACT["countyGeometry"]
    path = work / "sources" / Path(urlparse(spec["url"]).path).name
    sources["countyGeometry"] = fetch(spec["url"], path, spec["sha256"])
    geometries = {"counties": load_geography([path], tables["counties"], conus_only=False)}
    states = sorted(set(tables["tracts"].index.str[:2]))

    def tract_shape(state):
        override = CONTRACT.get("tractGeometryOverrides", {}).get(state, {})
        url = override.get("url", CONTRACT["tractGeometryTemplate"].format(state=state))
        target = work / "sources" / Path(urlparse(url).path).name
        return target, fetch(url, target, override.get("sha256"))

    with ThreadPoolExecutor(6) as pool:
        shape_records = list(pool.map(tract_shape, states))
    sources["tractGeometries"] = [record for _, record in shape_records]
    geometries["tracts"] = load_geography(
        [path for path, _ in shape_records], tables["tracts"], conus_only=False
    )
    verified, climate = climate_inputs(
        work / "climate", snapshot_spec or CONTRACT["climateSnapshot"]
    )
    coordinates = {
        "nex": pd.read_csv(verified.file("nex_coordinates")),
        "loca2": pd.read_csv(verified.file("loca2_coordinates")),
    }
    adapters, weights, overlap_provenance = {}, {}, {}
    for level in ("counties", "tracts"):
        target = tables[level].loc[~tables[level].STATEABBRV.isin(EXCLUDED)].index
        shapes = geometries[level].loc[target]
        weights[level], overlap_provenance[level] = {}, {}
        for grid, coords in coordinates.items():
            print(f"Building {level} {grid} weights: {len(shapes)} areas", flush=True)
            matrix, metadata = overlap_weights(
                shapes, coords, work / "weights", geometries[level].attrs.get("sources", {})
            )
            weights[level][grid] = matrix
            overlap_provenance[level][grid] = metadata
        if level == "counties":
            shares, records = fuels(shapes, work / "fuels")
            sources["landfireTiles"] = records
        else:
            shares = None
        adapters[level] = GeographySnapshot(
            verified, tables[level], weights[level]["nex"], weights[level]["loca2"], shares
        )
    print("Running Hamilton county and tract projections", flush=True)
    results = run(adapters["counties"], adapters["tracts"])
    provenance = {
        "contract": CONTRACT,
        "codeRevision": revision,
        "runId": run_id,
        "workerImage": os.environ.get("FRI_WORKER_IMAGE", "local"),
        "climateSnapshot": climate,
        "sources": sources,
        "overlapWeights": overlap_provenance,
        "parameters": results["parameters"],
    }
    catalog_records = {}
    for level in ("counties", "tracts"):
        result = results[level]
        bins = {
            "baseline": "NRI v1.20",
            "geography": level,
            "population": len(tables[level]),
            "variants": result["bins"],
            "hazards": {
                hazard: {
                    "annualLoss": result["bins"][variant]["eal"],
                    "riskValue": result["bins"][variant]["risk"],
                }
                for hazard, variant in [("DRGT", "DRGT"), ("WFIR", "WFIR"), ("EXHT", "EXHT_L95")]
            },
        }
        record = package_geography(
            output,
            version,
            level,
            geometries[level],
            tables[level],
            result["scored"],
            bins,
            result["validation"],
        )
        folder = output / "future-risk-index/fri" / level / version
        prepared = folder / "prepared"
        prepared.mkdir()
        for grid, matrix in weights[level].items():
            sparse.save_npz(prepared / f"{grid}_weights.npz", matrix)
        (prepared / "area_ids.json").write_text(json.dumps(adapters[level].ids().tolist()))
        if level == "counties":
            shares = adapters[level].county_fuel_shares()
            shares.to_csv(
                prepared / "fuel_shares.csv", index_label="STCOFIPS", float_format="%.17g"
            )
        write_json(folder / "metadata/provenance.json", provenance)
        for source in prepared.iterdir():
            record["assets"][source.name] = asset(
                source, folder, source.name, "application/octet-stream", ("metadata",)
            )
        record["assets"]["provenance"] = asset(
            folder / "metadata/provenance.json",
            folder,
            "Source and calculation provenance",
            "application/json",
            ("metadata",),
        )
        catalog_records[("fri", level)] = record
        # NRI is its own dataset; county and tract are files, each behind a version.
        native = output / "future-risk-index/nri" / level / version
        native.mkdir(parents=True)
        raw = (
            work
            / "sources"
            / Path(
                urlparse(
                    CONTRACT["countyTable" if level == "counties" else "tractTable"]["url"]
                ).path
            ).name
        )
        shutil.copyfile(raw, native / raw.name)
        tables[level].to_parquet(native / "baseline.parquet", compression="zstd")
        catalog_records[("nri", level)] = {
            "file": level,
            "title": f"FEMA NRI v1.20 — {level}",
            "bbox": geometries[level].total_bounds.tolist(),
            "assets": {
                "original": asset(
                    native / raw.name, native, "Original FEMA NRI v1.20 ZIP", "application/zip"
                ),
                "baseline": asset(
                    native / "baseline.parquet",
                    native,
                    "Normalized baseline; HWAV mapped to EXHT",
                    "application/vnd.apache.parquet",
                ),
            },
        }
    for level in ("counties", "tracts"):
        native = output / "future-risk-index/census-boundaries" / level / version
        native.mkdir(parents=True)
        specs = [sources["countyGeometry"]] if level == "counties" else sources["tractGeometries"]
        assets = {}
        for source in specs:
            original = work / "sources" / source["path"]
            shutil.copyfile(original, native / original.name)
            assets[original.name] = asset(
                native / original.name, native, original.name, "application/zip"
            )
        geometries[level].to_parquet(native / "geometry.parquet", compression="zstd")
        assets["geometry"] = asset(
            native / "geometry.parquet",
            native,
            "Exact normalized input boundaries",
            "application/vnd.apache.parquet",
        )
        catalog_records[("census-boundaries", level)] = {
            "file": level,
            "title": f"Census 2024 {level} boundaries",
            "bbox": geometries[level].total_bounds.tolist(),
            "assets": assets,
        }
    write_catalog(output, version, catalog_records)
    report = [
        "# NRI v1.20 county and tract reconstruction",
        "",
        f"Run: {run_id}. Baseline: December 2025, NRI v1.20.",
        "",
        "Review artifacts only; no staging publication or approved map release activated.",
        "Connecticut uses its nine planning regions; the FEMA archive remains unchanged.",
        "Climate inputs are the exact verified MME50 snapshot. County and tract weights "
        "retain 0.25-degree boxes, including LOCA2; tract polygons do not add climate detail.",
        "Wildfire elasticity is fitted using county NRI losses and fuel shares, then shared "
        "with tracts. No tract-level regression is fitted.",
        "Future values are unavailable outside CONUS. Projected percentiles rank supported "
        "CONUS areas with valid coverage, separately for counties and tracts. "
        "Unsupported tract hazards remain null; baseline ratings remain native NRI.",
        "",
        "## Validation",
        "",
    ]
    for level in ("counties", "tracts"):
        report += [
            f"### {level.title()}",
            "",
            "```json",
            json.dumps(results[level]["validation"], indent=2),
            "```",
            "",
        ]
    (output / "report.md").write_text("\n".join(report))
    package = manifest(output, version, provenance)
    write_json(output / "result-manifest.json", package)
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/nri-v120"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/nri-v120-results"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output-gcs", default="")
    parser.add_argument("--results-uri", default="")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--snapshot-sha256", default="")
    args = parser.parse_args()
    if bool(args.snapshot) != bool(args.snapshot_sha256):
        parser.error("Snapshot and SHA-256 must be supplied together")
    spec = {"url": args.snapshot, "sha256": args.snapshot_sha256} if args.snapshot else None
    package = execute(args.work, args.output, args.version, args.run_id, args.code_revision, spec)
    if args.output_gcs:
        from google.cloud import storage

        from .results_cloud import put_file
        from .storage import split_uri

        split_uri(args.output_gcs)
        client = storage.Client()
        # Upload only to an immutable experiment prefix. Promotion is a separate review step.
        for path in sorted(args.output.rglob("*")):
            if path.is_file():
                put_file(
                    client,
                    path,
                    f"{args.output_gcs.rstrip('/')}/{path.relative_to(args.output).as_posix()}",
                )
    if args.results_uri:
        if not args.output_gcs:
            parser.error("Public review results require experiment outputs")
        from .current_publish import publish

        receipt = publish(
            f"{args.output_gcs.rstrip('/')}/result-manifest.json",
            sha256(args.output / "result-manifest.json"),
            args.results_uri,
        )
        print(json.dumps(receipt), flush=True)
        from .current_explain import execute as explain_current_results

        diagnostics = explain_current_results(
            args.results_uri, args.version, receipt["manifestSha256"], args.work
        )
        print(json.dumps(diagnostics), flush=True)
    print(
        json.dumps(
            {"version": package["version"], "files": len(package["files"]), "publishable": False}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
