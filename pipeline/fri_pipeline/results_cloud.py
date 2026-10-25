"""Build portable results in Batch and copy an explicitly approved version to staging."""

import argparse
import hashlib
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import storage
from scipy import sparse

from .candidate import write_json
from .results import COLLECTION, build_results, render_catalog
from .snapshot import Snapshot, sha256
from .storage import download, fetch_candidate, fetch_snapshot, split_prefix, split_uri


def check_approval(package: dict, approved_candidate: Path) -> None:
    if package.get("collection") != COLLECTION or not package.get("publishable"):
        raise ValueError("Only reviewed publication candidates can be copied to staging")
    if package.get("sourceRunManifest") != "candidate.json" or package["sourceRunSha256"] != sha256(
        approved_candidate
    ):
        raise ValueError("Portolan results do not match the exact approved candidate")


def stage_cloud(
    results_uri: str, version: str, manifest_sha: str, approved_candidate: Path, staging_uri: str
) -> dict:
    """Copy one approved version and its referenced originals; preserve other collections."""
    client = storage.Client()
    with tempfile.TemporaryDirectory(prefix="future-risk-stage-") as temp:
        root = Path(temp)
        manifest = root / "result-manifest.json"
        download(f"{results_uri.rstrip('/')}/_releases/{version}.json", manifest, manifest_sha)
        package = json.loads(manifest.read_text())
        check_approval(package, approved_candidate)
        if package["version"] != version or not re.fullmatch(r"v[0-9A-Za-z-]{1,62}", version):
            raise ValueError("Version identity mismatch")
        source_bucket, source_root = split_prefix(results_uri)
        target_bucket, target_root = split_prefix(staging_uri)
        prefixes = [
            f"{COLLECTION}/{dataset}/{file}/{version}/"
            for dataset, file in (("county-risk", "counties"), ("reproducibility", "inputs"))
        ]
        copies = {
            name: spec
            for name, spec in package["files"].items()
            if any(name.startswith(p) for p in prefixes)
        }
        originals = root / "originals.json"
        original_key = f"{prefixes[1]}metadata/originals-manifest.json"
        download(
            f"{results_uri.rstrip('/')}/{original_key}",
            originals,
            package["originalSourceManifestSha256"],
        )
        for item in json.loads(originals.read_text())["sources"]:
            key = f"{COLLECTION}/sources/{item['href']}"
            if ".." in Path(key).parts or not key.startswith(f"{COLLECTION}/sources/originals/"):
                raise ValueError("Original source key escapes this collection")
            copies[key] = {"sha256": item["sha256"], "bytes": item["bytes"]}

        def copy(item):
            key, spec = item
            if ".." in Path(key).parts or not key.startswith(f"{COLLECTION}/"):
                raise ValueError("Result key escapes the Future Risk Index collection")
            source = client.bucket(source_bucket).get_blob(
                "/".join(p for p in (source_root, key) if p)
            )
            if (
                source is None
                or source.size != spec["bytes"]
                or (source.metadata or {}).get("sha256") != spec["sha256"]
            ):
                raise ValueError(f"Result asset does not match the approved inventory: {key}")
            destination_key = "/".join(p for p in (target_root, key) if p)
            current = client.bucket(target_bucket).get_blob(destination_key)
            if current:
                if current.size != source.size or current.crc32c != source.crc32c:
                    raise ValueError(f"Staging version already contains different bytes: {key}")
                return
            destination = client.bucket(target_bucket).blob(destination_key)
            token = None
            while True:
                token, _, _ = destination.rewrite(
                    source,
                    token=token,
                    if_generation_match=0,
                    if_source_generation_match=int(source.generation),
                )
                if token is None:
                    break
            destination.reload()
            if destination.size != source.size or destination.crc32c != source.crc32c:
                raise ValueError(f"Staging copy integrity failed: {key}")

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(copy, copies.items()))
        # Parent indexes contain only versions already staged plus this approved version.
        county_path = f"{prefixes[0]}collection.json"
        source_path = f"{prefixes[1]}collection.json"
        county_doc, source_doc = root / "county.json", root / "sources.json"
        download(
            f"{results_uri.rstrip('/')}/{county_path}",
            county_doc,
            package["files"][county_path]["sha256"],
        )
        download(
            f"{results_uri.rstrip('/')}/{source_path}",
            source_doc,
            package["files"][source_path]["sha256"],
        )
        county, sources = json.loads(county_doc.read_text()), json.loads(source_doc.read_text())
        tree = root / "catalog"
        render_catalog(
            tree,
            version,
            county["assets"],
            sources["assets"],
            county["extent"]["spatial"]["bbox"][0],
            county.get("table:columns", []),
            True,
        )
        for path in tree.rglob("*"):
            if not path.is_file():
                continue
            key = path.relative_to(tree).as_posix()
            if not key.startswith(f"{COLLECTION}/") or any(key.startswith(p) for p in prefixes):
                continue
            uri = f"{staging_uri.rstrip('/')}/{key}"
            if path.name == "catalog.json":
                bucket, object_key = split_uri(uri)
                prior = client.bucket(bucket).get_blob(object_key)
                if prior:
                    previous = json.loads(prior.download_as_bytes())
                    new = json.loads(path.read_text())
                    children = {
                        link["href"]: link
                        for link in previous.get("links", [])
                        if link.get("rel") == "child"
                    }
                    children.update(
                        {link["href"]: link for link in new["links"] if link.get("rel") == "child"}
                    )
                    new["links"] = [
                        link for link in new["links"] if link.get("rel") != "child"
                    ] + list(children.values())
                    write_json(path, new)
            put_file(client, path, uri, mutable=path.name == "catalog.json")
        return {
            "collection": COLLECTION,
            "version": version,
            "objectsVerified": len(copies),
            "stagingUri": f"{staging_uri.rstrip('/')}/{COLLECTION}/",
            "manifestSha256": manifest_sha,
        }


def put_file(client, path: Path, uri: str, *, mutable: bool = False):
    bucket, key = split_uri(uri)
    blob = client.bucket(bucket).blob(key)
    current = client.bucket(bucket).get_blob(key)
    digest = sha256(path)
    if current:
        current_digest = (current.metadata or {}).get("sha256")
        if current_digest is None:
            current_digest = hashlib.sha256(current.download_as_bytes()).hexdigest()
        if current_digest == digest and current.size == path.stat().st_size:
            return
        if not mutable:
            raise ValueError(f"Refusing to change immutable result: {uri}")
    blob.metadata = {"sha256": digest}
    blob.upload_from_filename(
        str(path), if_generation_match=int(current.generation) if current else 0, timeout=1200
    )


def loca_coordinates(snapshot: Snapshot, checkpoint_uri: str, checkpoint_sha: str, root: Path):
    if "loca2_coordinates" in snapshot.files:
        frame = pd.read_csv(snapshot.file("loca2_coordinates"))
        return {key: frame[key].to_numpy() for key in ("lat", "lon")}
    if not checkpoint_uri:
        raise ValueError(
            "This older snapshot needs its pinned checkpoint to recover LOCA2 coordinates"
        )
    manifest = root / "checkpoint.json"
    download(checkpoint_uri, manifest, checkpoint_sha)
    inventory = json.loads(manifest.read_text())["files"]
    prefix = checkpoint_uri.rsplit("/", 1)[0]
    paths = {}
    for name in ("loca2/grid.npz", "geo/weights_counties_loca2.npz"):
        target = root / Path(name).name
        download(f"{prefix}/cache/{name}", target, inventory[name])
        paths[name] = target
    full = sparse.load_npz(paths["geo/weights_counties_loca2.npz"])
    selected = np.flatnonzero(np.asarray(full.sum(axis=0)).ravel() > 0)
    expected, _ = snapshot.loca2_county_weights()
    if full[:, selected].shape != expected.shape or (full[:, selected] != expected).nnz:
        raise ValueError("Recovered coordinate columns do not match the snapshot weights")
    with np.load(paths["loca2/grid.npz"], allow_pickle=False) as grid:
        lat, lon = np.meshgrid(
            grid["lat"], np.where(grid["lon"] > 180, grid["lon"] - 360, grid["lon"]), indexing="ij"
        )
    return {"lat": lat.ravel()[selected], "lon": lon.ravel()[selected]}


def build_cloud(
    run_uri: str,
    run_sha: str,
    snapshot_uri: str,
    snapshot_sha: str,
    results_uri: str,
    version: str,
    experiment_uri: str,
    *,
    kind="analysis",
    checkpoint_uri="",
    checkpoint_sha="",
) -> dict:
    from rashid import validate

    if not re.fullmatch(r"v[0-9A-Za-z-]{1,62}", version):
        raise ValueError("Invalid result version")
    client = storage.Client()
    with tempfile.TemporaryDirectory(prefix="future-risk-results-") as temp:
        work = Path(temp)
        run = work / "run"
        if kind == "candidate":
            fetch_candidate(run_uri, run)
            manifest = run / "candidate.json"
            if sha256(manifest) != run_sha:
                raise ValueError("Candidate run manifest hash mismatch")
        else:
            manifest = run / "analysis.json"
            download(f"{run_uri.rstrip('/')}/analysis.json", manifest, run_sha)
            meta = json.loads(manifest.read_text())
            for name, spec in meta["artifacts"].items():
                target = (run / name).resolve()
                if not target.is_relative_to(run.resolve()):
                    raise ValueError("Invalid analysis artifact path")
                download(f"{run_uri.rstrip('/')}/{name}", target, spec["sha256"])
        provenance_sha = sha256(run / "provenance.json")
        originals = work / "originals-manifest.json"
        download(
            f"{results_uri.rstrip('/')}/{COLLECTION}/sources/manifests/{provenance_sha}.json",
            originals,
        )
        source_inventory = json.loads(originals.read_text())
        if source_inventory["provenanceSha256"] != provenance_sha:
            raise ValueError("Original archive was not produced for this exact run")
        snapshot_path = fetch_snapshot(snapshot_uri, snapshot_sha, work / "snapshot")
        source_snapshot = Snapshot(snapshot_path, analysis=kind == "analysis")
        coordinates = loca_coordinates(source_snapshot, checkpoint_uri, checkpoint_sha, work)
        output = work / "results"
        bucket, prefix = split_prefix(results_uri)
        for blob in client.list_blobs(
            bucket, prefix=(prefix.rstrip("/") + "/" if prefix else "") + COLLECTION + "/"
        ):
            key = blob.name[len(prefix.rstrip("/") + "/") :] if prefix else blob.name
            if key.startswith(f"{COLLECTION}/sources/") or f"/{version}/" in key:
                continue
            if Path(key).name in {
                "catalog.json",
                "collection.json",
                "README.md",
                "AGENTS.md",
                "LICENSE.md",
            }:
                download(f"gs://{bucket}/{blob.name}", output / key)
        package = build_results(run, snapshot_path, originals, output, version, coordinates)
        report = validate(output, data=False, schema=True)
        validation = report.to_dict()
        if not report.passed:
            raise ValueError(f"Portolan validation failed: {[f.message for f in report.errors]}")
        print(
            f"Validated Portolan tree; {package['featureCount']} counties, "
            f"{package['sourceCount']} original sources",
            flush=True,
        )

        def verify_original(item):
            bucket, prefix = split_uri(f"{results_uri.rstrip('/')}/{COLLECTION}/sources")
            blob = client.bucket(bucket).get_blob(f"{prefix}/{item['href']}")
            if (
                blob is None
                or blob.size != item["bytes"]
                or (blob.metadata or {}).get("sha256") != item["sha256"]
            ):
                raise ValueError(f"Original archived asset is missing or differs: {item['href']}")

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(verify_original, source_inventory["sources"]))
        package["portolanValidation"] = validation
        package["packagingCodeRevision"] = os.environ.get("FRI_CODE_REVISION")
        package["workerImage"] = os.environ.get("FRI_WORKER_IMAGE")
        package["supplementaryCheckpointSha256"] = checkpoint_sha or None
        write_json(output / "result-manifest.json", package)

        def send(name):
            path = output / name
            put_file(
                client,
                path,
                f"{results_uri.rstrip('/')}/{name}",
                mutable=path.name == "catalog.json",
            )

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(send, (key for key in package["files"] if key != "catalog.json")))
        put_file(
            client,
            output / "result-manifest.json",
            f"{results_uri.rstrip('/')}/_releases/{version}.json",
        )
        put_file(
            client, output / "catalog.json", f"{results_uri.rstrip('/')}/catalog.json", mutable=True
        )
        receipt = work / "results.json"
        write_json(
            receipt,
            {
                "collection": COLLECTION,
                "version": version,
                "publishable": package["publishable"],
                "resultsUri": results_uri,
                "manifestUri": f"{results_uri.rstrip('/')}/_releases/{version}.json",
                "manifestSha256": sha256(output / "result-manifest.json"),
                "sourceRunSha256": run_sha,
            },
        )
        put_file(client, receipt, f"{experiment_uri.rstrip('/')}/results.json")
        print(receipt.read_text(), flush=True)
        return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--run-uri", required=True)
    build.add_argument("--run-sha256", required=True)
    build.add_argument("--snapshot-uri", required=True)
    build.add_argument("--snapshot-sha256", required=True)
    build.add_argument("--results-uri", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--experiment-uri", required=True)
    build.add_argument("--kind", choices=("analysis", "candidate"), default="analysis")
    build.add_argument("--checkpoint-uri", default="")
    build.add_argument("--checkpoint-sha256", default="")
    stage = commands.add_parser("stage")
    stage.add_argument("--results-uri", required=True)
    stage.add_argument("--version", required=True)
    stage.add_argument("--manifest-sha256", required=True)
    stage.add_argument("--approved-candidate", type=Path, required=True)
    stage.add_argument("--staging-uri", required=True)
    args = parser.parse_args()
    if args.command == "stage":
        print(
            json.dumps(
                stage_cloud(
                    args.results_uri,
                    args.version,
                    args.manifest_sha256,
                    args.approved_candidate,
                    args.staging_uri,
                )
            )
        )
        return
    build_cloud(
        args.run_uri,
        args.run_sha256,
        args.snapshot_uri,
        args.snapshot_sha256,
        args.results_uri,
        args.version,
        args.experiment_uri,
        kind=args.kind,
        checkpoint_uri=args.checkpoint_uri,
        checkpoint_sha=args.checkpoint_sha256,
    )


if __name__ == "__main__":
    main()
