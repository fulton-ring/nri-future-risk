"""Attach verified derived heat details without changing completed scientific attributes."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def augment(diagnostics_root, display_root, releases_path):
    releases = json.loads(releases_path.read_text())
    pending = []
    for release in releases:
        if release.get("status") == "archive":
            continue
        level = release["geography"]
        folder = diagnostics_root / level
        path = folder / "heat-calculations.json"
        manifest_path = folder / "heat-diagnostics-manifest.json"
        diagnostics = json.loads(path.read_text())
        manifest = json.loads(manifest_path.read_text())
        for doc in (diagnostics, manifest):
            if doc["version"] != release["resultsVersion"] or doc["geography"] != level:
                raise ValueError("Diagnostic release identity mismatch")
        if manifest["assets"]["heat-calculations.json"]["sha256"] != digest(path):
            raise ValueError("Diagnostic calculation hash mismatch")
        if diagnostics["publishedMultipliersSha256"] != release["sourceSha256"]:
            raise ValueError(
                "Diagnostic source differs from displayed scientific source"
            )
        if diagnostics["verifiedAreaScenarios"] != len(diagnostics["counties"]) * 8:
            raise ValueError("Diagnostic verified scenario count mismatch")
        version_base = release["sourceData"].rsplit("/geoparquet/", 1)[0]
        asset = {
            "path": f"{version_base}/metadata/heat-calculations.json",
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }
        release["heatDiagnostics"] = {
            **asset,
            "manifest": {
                "path": f"{version_base}/metadata/heat-diagnostics-manifest.json",
                "sha256": digest(manifest_path),
                "bytes": manifest_path.stat().st_size,
            },
        }
        if level == "counties":
            release["assets"]["heatCalculations"] = asset
            release["heatCalculations"] = {
                **asset,
                "snapshotSha256": diagnostics["snapshotSha256"],
            }
            continue
        details = diagnostics["counties"]
        seen = set()
        for prefix, expected in release["profileAssets"]["hashes"].items():
            shard = display_root / level / "profiles" / f"{prefix}.json"
            if digest(shard) != expected:
                raise ValueError(f"Profile hash mismatch before augmentation: {prefix}")
            payload = json.loads(shard.read_text())
            for row in payload["counties"]:
                if row["id"] in details:
                    row["heatCalculations"] = details[row["id"]]
                    seen.add(row["id"])
            pending.append((shard, payload, release["profileAssets"]["hashes"], prefix))
        if seen != set(details):
            raise ValueError("Heat diagnostics contain IDs absent from profile shards")
    # Validate every input before changing a shard or its release hash.
    for shard, payload, hashes, prefix in pending:
        write_json(shard, payload)
        hashes[prefix] = digest(shard)
    releases_path.write_text(json.dumps(releases, indent=2, allow_nan=False) + "\n")
    return {
        "releases": [r["id"] for r in releases if "id" in r],
        "profileShards": len(pending),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics-root", type=Path, required=True)
    parser.add_argument("--display-root", type=Path, required=True)
    parser.add_argument(
        "--releases", type=Path, default=ROOT / "src/data/releases.json"
    )
    args = parser.parse_args()
    print(json.dumps(augment(args.diagnostics_root, args.display_root, args.releases)))


if __name__ == "__main__":
    main()
