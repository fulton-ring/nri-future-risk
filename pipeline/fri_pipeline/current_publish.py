"""Copy verified review artifacts to the public results bucket; never activate a release."""

import argparse
import hashlib
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from .candidate import write_json
from .current_results import validate_version
from .results_cloud import put_file
from .snapshot import sha256
from .storage import download, split_prefix, split_uri


def validate_inventory(package):
    version = validate_version(package["version"])
    if package.get("collection") != "future-risk-index" or package.get("baseline") != "NRI v1.20":
        raise ValueError("Expected a native v1.20 FRI review package")
    for name, spec in package["files"].items():
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not re.fullmatch("[a-f0-9]{64}", spec["sha256"])
            or spec["bytes"] < 0
        ):
            raise ValueError("Invalid result inventory path or digest")
        if name in ("catalog.json", "report.md", "README.md", "AGENTS.md"):
            continue
        if (
            path.name in ("README.md", "AGENTS.md")
            and len(path.parts) <= 4
            and path.parts[0] == "future-risk-index"
        ):
            continue
        if not name.startswith("future-risk-index/"):
            raise ValueError("Unexpected collection path")
        if path.name == "catalog.json" and len(path.parts) <= 4:
            continue
        if len(path.parts) < 5 or path.parts[3] != version:
            raise ValueError("Review results cannot replace a different version or active pointer")


def merge_catalog(prior, current):
    if prior and prior.get("id") != current.get("id"):
        raise ValueError("Catalog identity differs from existing results")
    children = {
        link["href"]: link for link in (prior or {}).get("links", []) if link["rel"] == "child"
    }
    children.update(
        {link["href"]: link for link in current.get("links", []) if link["rel"] == "child"}
    )
    merged = {
        **current,
        "links": [link for link in current.get("links", []) if link["rel"] != "child"]
        + [children[key] for key in sorted(children)],
    }
    versions = [href for href in children if re.fullmatch(r"v[0-9A-Za-z-]+/collection\.json", href)]
    if versions:
        merged["links"] = [link for link in merged["links"] if link["rel"] != "latest-version"]
        merged["links"].append(
            {
                "rel": "latest-version",
                "href": max(versions),
                "type": "application/json",
                "title": "Latest version",
            }
        )
    merged["description"] = (
        "Future Risk Index results and reproducibility assets. "
        "Each version documents its own baseline and methodology."
    )
    return merged


def publish(source_manifest, source_sha, results_uri):
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    source_bucket, manifest_key = split_uri(source_manifest)
    target_bucket, target_prefix = split_prefix(results_uri)
    if source_bucket == target_bucket:
        raise ValueError("Experiments and public results must use separate buckets")
    client = storage.Client()
    with tempfile.TemporaryDirectory(prefix="fri-review-publish-") as temporary:
        local = Path(temporary) / "result-manifest.json"
        download(source_manifest, local, source_sha)
        package = json.loads(local.read_text())
        validate_inventory(package)
        prefix = manifest_key.rsplit("/", 1)[0]
        if prefix != f"runs/{package['provenance']['runId']}":
            raise ValueError("Review manifest must belong to its exact experiment run")
        version = package["version"]

        def target_uri(name):
            return f"gs://{target_bucket}/" + "/".join(p for p in (target_prefix, name) if p)

        def source_object(name, spec):
            blob = client.bucket(source_bucket).get_blob(f"{prefix}/{name}")
            if blob is None or blob.size != spec["bytes"]:
                raise ValueError(f"Source inventory size mismatch: {name}")
            if (blob.metadata or {}).get("sha256") != spec["sha256"]:
                # Older experiment uploaders did not record SHA metadata. Verify bytes once.
                digest = hashlib.sha256()
                with blob.open("rb", if_generation_match=int(blob.generation)) as stream:
                    for chunk in iter(lambda: stream.read(8 << 20), b""):
                        digest.update(chunk)
                if digest.hexdigest() != spec["sha256"]:
                    raise ValueError(f"Source inventory hash mismatch: {name}")
            return blob

        mutable = [name for name in package["files"] if name.endswith("catalog.json")]
        support = [
            name
            for name in package["files"]
            if PurePosixPath(name).name in ("README.md", "AGENTS.md")
            and len(PurePosixPath(name).parts) <= 4
        ]
        immutable = [
            (name, spec)
            for name, spec in package["files"].items()
            if name not in mutable and name not in support
        ]

        def copy(item):
            name, spec = item
            source = source_object(name, spec)
            destination = f"_releases/{version}-report.md" if name == "report.md" else name
            bucket, key = split_uri(target_uri(destination))
            target = client.bucket(bucket).get_blob(key)
            if target is None:
                target = client.bucket(bucket).blob(key)
                target.metadata = {"sha256": spec["sha256"]}
                token = None
                while True:
                    token, _, _ = target.rewrite(
                        source,
                        token=token,
                        if_generation_match=0,
                        if_source_generation_match=int(source.generation),
                    )
                    if token is None:
                        break
                target.reload()
            if (
                target.size != source.size
                or target.crc32c != source.crc32c
                or (target.metadata or {}).get("sha256") != spec["sha256"]
            ):
                raise ValueError(f"Immutable public copy differs: {destination}")
            return destination, spec

        with ThreadPoolExecutor(6) as pool:
            public_files = dict(pool.map(copy, immutable))
        # Existing shared guidance is retained; create-only compute credentials cannot replace it.
        for name in support:
            bucket, key = split_uri(target_uri(name))
            if client.bucket(bucket).get_blob(key) is None:
                copy((name, package["files"][name]))
        # Catalogs are merged only after every immutable asset is verified and present.
        for name in sorted(mutable, key=lambda value: -len(PurePosixPath(value).parts)):
            spec = package["files"][name]
            source = source_object(name, spec)
            incoming = json.loads(
                source.download_as_bytes(if_generation_match=int(source.generation))
            )
            bucket, key = split_uri(target_uri(name))
            blob = client.bucket(bucket).blob(key)
            for attempt in range(3):
                prior = client.bucket(bucket).get_blob(key)
                previous = (
                    json.loads(prior.download_as_bytes(if_generation_match=int(prior.generation)))
                    if prior
                    else None
                )
                body = json.dumps(merge_catalog(previous, incoming), separators=(",", ":")) + "\n"
                blob.metadata = {"sha256": hashlib.sha256(body.encode()).hexdigest()}
                try:
                    blob.upload_from_string(
                        body,
                        content_type="application/json",
                        if_generation_match=int(prior.generation) if prior else 0,
                    )
                    break
                except PreconditionFailed:
                    if attempt == 2:
                        raise
        receipt = {
            **package,
            "publishable": False,
            "files": public_files,
            "sourceManifestUri": source_manifest,
            "sourceManifestSha256": source_sha,
            "resultsUri": results_uri,
            "status": "review",
        }
        path = Path(temporary) / "public-review.json"
        write_json(path, receipt)
        put_file(client, path, target_uri(f"_releases/{version}.json"))
        return {
            "version": version,
            "resultsUri": results_uri,
            "files": len(public_files),
            "manifestUri": target_uri(f"_releases/{version}.json"),
            "manifestSha256": sha256(path),
            "liveReleaseActivated": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--results-uri", required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.source_manifest, args.source_sha256, args.results_uri)))


if __name__ == "__main__":
    main()
