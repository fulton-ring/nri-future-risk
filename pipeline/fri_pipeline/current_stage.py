"""Stage the exact v1.20 data approved by a merged review; never activate a release."""

import argparse
import copy
import hashlib
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from .candidate import write_json
from .current_publish import merge_catalog, validate_inventory
from .results import PORTOLAN
from .results_cloud import copy_verified, put_file
from .snapshot import sha256
from .storage import download, split_prefix, split_uri


def version_asset(name, version):
    path = PurePosixPath(name)
    return (
        len(path.parts) >= 5
        and path.parts[0] == "future-risk-index"
        and path.parts[3] == version
        and all(re.fullmatch(r"[a-z0-9][a-z0-9-]*", part) for part in path.parts[1:3])
        and ".." not in path.parts
        and not path.is_absolute()
        and str(path) == name
    )


def version_collection(name):
    return len(PurePosixPath(name).parts) == 5 and name.endswith("/collection.json")


def validate_approval(source_manifest, approved_receipt, results_uri):
    """A merged receipt authorizes only the exact inventory of its merged source."""
    split_prefix(results_uri)
    source = json.loads(source_manifest.read_bytes())
    receipt = json.loads(approved_receipt.read_bytes())
    validate_inventory(source)
    version = source["version"]
    if receipt.get("sourceManifestSha256") != sha256(source_manifest):
        raise ValueError("Receipt does not match the approved source manifest bytes")
    if any(receipt.get(key) != value for key, value in source.items() if key != "files"):
        raise ValueError("Public review identity differs from approved source manifest")
    if receipt.get("status") != "review" or receipt.get("resultsUri") != results_uri:
        raise ValueError("Expected the configured public review results URI")
    bucket, key = split_uri(receipt["sourceManifestUri"])
    if key != f"runs/{source['provenance']['runId']}/result-manifest.json":
        raise ValueError("Source manifest must belong to the exact approved run")
    if bucket == split_prefix(results_uri)[0]:
        raise ValueError("Experiment and public review buckets must differ")
    expected = {}
    for name, spec in source["files"].items():
        if version_asset(name, version):
            expected[name] = spec
        elif name == "report.md":
            expected[f"_releases/{version}-report.md"] = spec
    if not expected or receipt.get("files") != expected:
        raise ValueError("Public inventory differs from the approved version assets")
    if not any(version_collection(name) for name in expected):
        raise ValueError("Review must include version collections")
    return receipt


def approved_collection(document, revision, source_sha):
    value = copy.deepcopy(document)
    value.update(
        {
            "fri:publication_status": "candidate",
            "fri:approved_revision": revision,
            "fri:approved_source_sha256": source_sha,
        }
    )
    for link in value["links"]:
        if link["rel"] == "root":
            link["href"] = "../../../catalog.json"
    return value


def parent_catalogs(collections):
    """Build only collection-local typed navigation; preserve prior children at upload."""
    catalogs = {}
    for collection in collections:
        parts = collection["id"].split("/")
        for depth in (1, 2, 3):
            identity = "/".join(parts[:depth])
            name = f"{identity}/catalog.json"
            if name not in catalogs:
                links = [
                    {"rel": "self", "href": "catalog.json", "type": "application/json"},
                    {
                        "rel": "root",
                        "href": "../" * (depth - 1) + "catalog.json",
                        "type": "application/json",
                    },
                    {"rel": "agents", "href": "AGENTS.md", "type": "text/markdown"},
                    {"rel": "describedby", "href": "README.md", "type": "text/markdown"},
                ]
                if depth > 1:
                    links.append(
                        {"rel": "parent", "href": "../catalog.json", "type": "application/json"}
                    )
                catalogs[name] = {
                    "stac_version": "1.1.0",
                    "stac_extensions": [PORTOLAN],
                    "type": "Catalog",
                    "id": identity,
                    "title": "Future Risk Index" if depth == 1 else parts[depth - 1],
                    "description": "Approved Future Risk Index data and reproducibility assets.",
                    "links": links,
                }
            href = f"{parts[depth]}/" + ("collection.json" if depth == 3 else "catalog.json")
            child = {
                "rel": "child",
                "href": href,
                "type": "application/json",
                "title": collection.get("title", parts[depth]) if depth == 3 else parts[depth],
            }
            if child not in catalogs[name]["links"]:
                catalogs[name]["links"].append(child)
    return catalogs


def stage_cloud(
    results_uri, approved_source_manifest, approved_receipt, staging_uri, approved_revision
):
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    receipt = validate_approval(approved_source_manifest, approved_receipt, results_uri)
    if split_prefix(results_uri)[0] == split_prefix(staging_uri)[0]:
        raise ValueError("Public review and staging buckets must differ")
    if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", approved_revision):
        raise ValueError("Expected the exact approved Git revision")
    client = storage.Client()
    version = receipt["version"]
    inventory = {
        name: spec for name, spec in receipt["files"].items() if version_asset(name, version)
    }
    with tempfile.TemporaryDirectory(prefix="fri-approved-stage-") as temporary:
        root = Path(temporary)
        fetched = root / "public-review.json"
        download(f"{results_uri}/_releases/{version}.json", fetched, sha256(approved_receipt))
        if fetched.read_bytes() != approved_receipt.read_bytes():
            raise ValueError("Public receipt differs from the merged approval")
        # Download only tiny version collections; all numeric/source assets are server-side copies.
        collections = []
        for name, spec in inventory.items():
            if not version_collection(name):
                continue
            path = root / name
            download(f"{results_uri}/{name}", path, spec["sha256"])
            if path.stat().st_size != spec["bytes"]:
                raise ValueError("Version collection size differs from approved inventory")
            document = json.loads(path.read_bytes())
            if (
                document.get("id") != name.removesuffix("/collection.json")
                or document.get("version") != version
            ):
                raise ValueError("Version collection identity differs from approved inventory")
            approved = approved_collection(
                document, approved_revision, receipt["sourceManifestSha256"]
            )
            collections.append(approved)
            write_json(path, approved)

        def copy_asset(item):
            name, spec = item
            copy_verified(client, f"{results_uri}/{name}", f"{staging_uri}/{name}", spec)

        with ThreadPoolExecutor(8) as pool:
            list(
                pool.map(
                    copy_asset,
                    [
                        (name, spec)
                        for name, spec in inventory.items()
                        if not version_collection(name)
                    ],
                )
            )
        for document in collections:
            name = document["id"] + "/collection.json"
            put_file(client, root / name, f"{staging_uri}/{name}")
        for name, incoming in sorted(parent_catalogs(collections).items(), reverse=True):
            bucket, key = split_uri(f"{staging_uri}/{name}")
            target = client.bucket(bucket)
            # Shared guidance is generic and create-only, and confined to this collection.
            for support in ("README.md", "AGENTS.md"):
                support_key = str(PurePosixPath(key).parent / support)
                if target.get_blob(support_key) is None:
                    path = root / support_key
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        "# Future Risk Index\n\nRead catalog.json for approved "
                        "versioned data, source assets and provenance.\n"
                    )
                    put_file(client, path, f"gs://{bucket}/{support_key}")
            for attempt in range(3):
                prior = target.get_blob(key)
                previous = (
                    json.loads(prior.download_as_bytes(if_generation_match=int(prior.generation)))
                    if prior
                    else None
                )
                body = json.dumps(merge_catalog(previous, incoming), separators=(",", ":")) + "\n"
                blob = target.blob(key)
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
    return {
        "collection": "future-risk-index",
        "version": version,
        "approvedRevision": approved_revision,
        "approvedSourceSha256": receipt["sourceManifestSha256"],
        "publicReviewSha256": sha256(approved_receipt),
        "objectsVerified": len(inventory),
        "copiedFiles": sorted(inventory),
        "nextOwner": "Downstream publication: transforms, hosting and activation",
        "stagingUri": f"{staging_uri}/future-risk-index/",
        "liveReleaseActivated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-uri", required=True)
    parser.add_argument("--staging-uri", required=True)
    parser.add_argument("--approved-source-manifest", type=Path, required=True)
    parser.add_argument("--approved-public-review", type=Path, required=True)
    parser.add_argument("--approved-revision", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            stage_cloud(
                args.results_uri,
                args.approved_source_manifest,
                args.approved_public_review,
                args.staging_uri,
                args.approved_revision,
            )
        )
    )


if __name__ == "__main__":
    main()
