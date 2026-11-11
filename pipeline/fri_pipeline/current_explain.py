"""Batch-only, read-only heat-floor diagnostics for completed native NRI results."""

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from .candidate import write_json
from .explain import explain_heat
from .snapshot import sha256


class HeatInputs:
    """Use verified climate with the completed run's exact geography weights."""

    def __init__(self, verified, weights, ids, *, supported_only=True):
        self.verified = verified
        self.SSP, self.manifest, self.path = verified.SSP, verified.manifest, verified.path
        ids = np.asarray(ids, dtype=str)
        _, counts = verified.loca2_histogram("historical", "historical")
        self.valid = counts[-1] == 0
        if weights.shape != (len(ids), len(self.valid)) or len(set(ids)) != len(ids):
            raise ValueError("Heat weights/IDs support mismatch")
        if not np.isfinite(weights.data).all() or (weights.data < 0).any():
            raise ValueError("Invalid heat weights")
        supported = np.asarray(weights @ self.valid.astype(float)).ravel() > 0
        self.unsupported_ids = ids[~supported].tolist()
        self.weights = weights[supported] if supported_only else weights
        self.ids = ids[supported] if supported_only else ids

    def loca2_county_weights(self):
        return self.weights, self.ids

    def loca2_histogram(self, scenario, period):
        edges, counts = self.verified.loca2_histogram(scenario, period)
        if not np.array_equal(counts[-1] == 0, self.valid):
            raise ValueError("LOCA2 domain mask changes across scenarios")
        return edges, counts


def explain_current(verified, weights, ids, expected, unsupported_ids, contract_id, level):
    adapter = HeatInputs(verified, weights, ids)
    if set(adapter.unsupported_ids) != set(unsupported_ids):
        raise ValueError("Heat coverage differs from completed validation")
    result = explain_heat(adapter)
    keys = {
        f"EXHT_{percentile}_{period}_{warming}"
        for percentile in ("L95", "L99")
        for period in ("MID", "LATE")
        for warming in ("LOWER", "HIGHER")
    }
    columns = sorted(f"{key}_HM" for key in keys)
    if not expected.index.is_unique or set(columns) - set(expected.columns):
        raise ValueError("Invalid source heat multiplier table")
    if set(map(str, ids)) - set(expected.index):
        raise ValueError("Source lacks prepared area IDs")
    supported = set(result["counties"])
    # This also checks every national row outside CONUS remains unavailable.
    if not expected.loc[~expected.index.isin(supported), columns].isna().all().all():
        raise ValueError("Unsupported source heat multipliers must be null")
    for geoid, details in result["counties"].items():
        if set(details) != keys:
            raise ValueError("Expected all eight heat scenarios")
        for key, item in details.items():
            source = float(expected.loc[geoid, f"{key}_HM"])
            if not math.isfinite(source) or not math.isclose(
                source, item["appliedMultiplier"], rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError(f"Source heat multiplier mismatch: {geoid} {key}")
    result.update(
        contractId=contract_id,
        methodology=contract_id,
        sourceSnapshotMethodology=verified.manifest["methodology"],
        geography=level,
        unsupportedAreaIds=adapter.unsupported_ids,
        verifiedAreaScenarios=len(supported) * 8,
        aggregation="Area-weighted event days; each 30-year total divided by 30.",
        diagnosticOnly=True,
    )
    return result


def execute(results_uri, version, manifest_sha256, work):
    from google.cloud import storage

    from .current_stage import validate_approval
    from .current_results import validate_version
    from .current_run import CONTRACT, climate_inputs
    from .results_cloud import put_file
    from .storage import download, split_prefix

    validate_version(version)
    split_prefix(results_uri)
    origin = results_uri.rstrip("/")
    receipt_uri = f"{origin}/_releases/{version}.json"
    receipt_path = work / "public-review.json"
    download(receipt_uri, receipt_path, manifest_sha256)
    package = json.loads(receipt_path.read_text())
    source_path = work / "result-manifest.json"
    download(package["sourceManifestUri"], source_path, package["sourceManifestSha256"])
    validate_approval(source_path, receipt_path, origin)
    if package["version"] != version or package["resultsUri"].rstrip("/") != origin:
        raise ValueError("Public receipt identity mismatch")
    if package["provenance"]["contract"] != CONTRACT:
        raise ValueError("Completed run uses a different scientific contract")
    snapshot, spec = climate_inputs(work / "climate", package["provenance"]["climateSnapshot"])
    client = storage.Client()
    receipt = {"version": version, "diagnosticOnly": True, "geographies": {}}
    for level in ("counties", "tracts"):
        folder = f"future-risk-index/fri/{level}/{version}"
        fingerprints = {}

        def fetch(relative, folder=folder, level=level, fingerprints=fingerprints):
            key = f"{folder}/{relative}"
            pinned = package["files"][key]
            path = work / level / relative
            download(f"{origin}/{key}", path, pinned["sha256"])
            if path.stat().st_size != pinned["bytes"]:
                raise ValueError(f"Completed result size mismatch: {key}")
            fingerprints[relative] = {"uri": f"{origin}/{key}", **pinned}
            return path

        weights = sparse.load_npz(fetch("prepared/loca2_weights.npz")).tocsr()
        ids = json.loads(fetch("prepared/area_ids.json").read_text())
        validation = json.loads(fetch("metadata/validation.json").read_text())
        source_path = fetch(f"geoparquet/{level}.parquet")
        # Geometry is unnecessary for diagnostics; read only identifiers and published HMs.
        columns = [
            f"EXHT_{p}_{t}_{s}_HM"
            for p in ("L95", "L99")
            for t in ("MID", "LATE")
            for s in ("LOWER", "HIGHER")
        ]
        source = pd.read_parquet(source_path, columns=["geoid", *columns]).set_index("geoid")
        source.index = source.index.astype(str)
        unsupported = validation["climateCoverage"]["loca2"]["unsupportedAreaIds"]
        result = explain_current(snapshot, weights, ids, source, unsupported, CONTRACT["id"], level)
        result.update(
            version=version,
            publishedMultipliersSha256=fingerprints[f"geoparquet/{level}.parquet"]["sha256"],
            sourceManifestSha256=manifest_sha256,
            codeRevision=os.environ.get("FRI_CODE_REVISION", "unknown"),
            workerImage=os.environ.get("FRI_WORKER_IMAGE", "unknown"),
        )
        target = work / level / "heat-calculations.json"
        write_json(target, result)
        key = f"{folder}/metadata/heat-calculations.json"
        asset = {
            "path": key,
            "uri": f"{origin}/{key}",
            "sha256": sha256(target),
            "bytes": target.stat().st_size,
        }
        manifest = {
            "schemaVersion": 1,
            "diagnosticOnly": True,
            "version": version,
            "geography": level,
            "contractId": CONTRACT["id"],
            "sourceManifest": {"uri": receipt_uri, "sha256": manifest_sha256},
            "climateSnapshot": spec,
            "inputs": fingerprints,
            "codeRevision": result["codeRevision"],
            "workerImage": result["workerImage"],
            "verifiedAreaScenarios": result["verifiedAreaScenarios"],
            "unsupportedAreaIds": result["unsupportedAreaIds"],
            "assets": {"heat-calculations.json": asset},
        }
        manifest_path = work / level / "heat-diagnostics-manifest.json"
        write_json(manifest_path, manifest)
        manifest_key = f"{folder}/metadata/heat-diagnostics-manifest.json"
        manifest_asset = {
            "path": manifest_key,
            "uri": f"{origin}/{manifest_key}",
            "sha256": sha256(manifest_path),
            "bytes": manifest_path.stat().st_size,
        }
        put_file(client, target, asset["uri"])
        put_file(client, manifest_path, manifest_asset["uri"])
        receipt["geographies"][level] = {
            "heatCalculations": asset,
            "manifest": manifest_asset,
            "verifiedAreaScenarios": result["verifiedAreaScenarios"],
        }
        print(
            f"Verified {level}: {result['verifiedAreaScenarios']} heat area-scenarios", flush=True
        )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-uri", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(execute(args.results_uri, args.version, args.manifest_sha256, args.work)),
        flush=True,
    )


if __name__ == "__main__":
    main()
