"""Export an already prepared, pinned rebuild cache; never download climate data here.

Run using the rebuild project's environment, which supplies its geospatial dependencies.
Raw source fingerprints are a required JSON list, prepared during source acquisition.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import requests
from scipy import sparse

from fri_pipeline.snapshot import FWI_ANALYSIS, fwi_years

REBUILD_COMMIT = "390f7c072dc23b5c33a7d7a87b99cecd8ef8041c"


def export_inputs(inputs, output: Path, sources: list[dict], *, analysis: bool = False) -> Path:
    """Export verified prepared arrays; acquisition and network access remain caller-owned."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Snapshot directory must be empty")
    ids = [source["id"] for source in sources]
    if not ids:
        raise ValueError("Raw source fingerprints are required")
    artifacts = {}

    def register(name, path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts[name] = {"path": path.name, "sha256": digest, "sourceIds": ids}

    nex, fips = inputs.county_weights()
    loca, loca_fips = inputs.loca2_county_weights()
    if not fips.equals(loca_fips):
        raise ValueError("NEX and LOCA2 county populations disagree")
    path = output / "county_ids.json"
    path.write_text(json.dumps(fips.tolist()) + "\n")
    register("county_ids", path)
    for name, weights in [("nex_weights", nex), ("loca2_weights", loca)]:
        path = output / f"{name}.npz"
        sparse.save_npz(path, weights)
        register(name, path)
    path = output / "nex_coordinates.csv"
    inputs.cell_coordinates().to_csv(path, index=False)
    register("nex_coordinates", path)
    path = output / "fuel_shares.csv"
    inputs.county_fuel_shares().to_csv(path, index_label="STCOFIPS", float_format="%.17g")
    register("fuel_shares", path)
    for ssp in ("ssp245", "ssp585"):
        for variable in ("tas", "pr"):
            values, months = inputs.monthly(variable, ssp)
            name = f"monthly_{variable}_{ssp}"
            path = output / f"{name}.npz"
            np.savez_compressed(path, values=values, months=months.to_numpy())
            register(name, path)
    for ssp, period in [
        ("historical", "historical"),
        *[(s, p) for s in ("ssp245", "ssp585") for p in ("MID", "LATE")],
    ]:
        years = fwi_years(ssp, period, analysis=analysis)
        if analysis:
            actual = [
                year
                for year in inputs.period_years(ssp, period)
                if inputs.data.fwi_path("MME75", ssp, year).exists()
            ]
            if not np.array_equal(actual, years):
                raise ValueError(
                    f"FWI cache years disagree with the approved analysis: {ssp}/{period}"
                )
        values = inputs.fwi(ssp, period, variable="FWI_P95", ensemble="MME75")
        if len(values) != len(years):
            raise ValueError(
                f"FWI missing years for {ssp}/{period}; resolve before snapshot export"
            )
        name, path = f"fwi_{ssp}_{period}", output / f"fwi_{ssp}_{period}.npz"
        np.savez_compressed(path, values=values, years=years)
        register(name, path)
        edges, counts = inputs.loca2_histogram(ssp, period)
        name, path = f"loca2_{ssp}_{period}", output / f"loca2_{ssp}_{period}.npz"
        np.savez_compressed(path, edges=edges, counts=counts)
        register(name, path)
    manifest = {
        "schemaVersion": 1,
        "coverage": "CONUS",
        "sources": sources,
        "rebuildCommit": REBUILD_COMMIT,
        "methodology": "fema-2024-county-area-weighted-v1",
        "artifacts": artifacts,
    }
    if analysis:
        manifest["analysis"] = FWI_ANALYSIS
    path = output / "snapshot.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Snapshot manifest SHA-256: {hashlib.sha256(path.read_bytes()).hexdigest()}")

    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = REBUILD_COMMIT
    sha = subprocess.check_output(
        ["git", "-C", str(args.rebuild), "rev-parse", "HEAD"], text=True
    ).strip()
    changes = subprocess.check_output(
        ["git", "-C", str(args.rebuild), "status", "--porcelain"], text=True
    ).strip()
    if sha != expected or changes:
        raise ValueError("Export requires a clean checkout of the pinned rebuild commit")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Snapshot directory must be empty")
    sources = json.loads(args.sources.read_text())
    ids = [source["id"] for source in sources]
    if not ids:
        raise ValueError("Raw climate, weights, and fuel source fingerprints are required")
    sys.path.insert(0, str(args.rebuild / "fri-agent-rebuild/src"))
    from fri_rebuild import inputs

    def no_download(*_args, **_kwargs):
        raise RuntimeError("Snapshot export attempted a network request; prepare the cache first")

    requests.sessions.Session.request = no_download
    export_inputs(inputs, output, sources)


if __name__ == "__main__":
    main()
