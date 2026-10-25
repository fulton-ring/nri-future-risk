"""Bounded GCS transfers. Outputs are create-only; compute cannot promote releases."""

import json
import re
from pathlib import Path

from google.cloud import storage

from .snapshot import sha256


def split_prefix(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([a-z0-9][a-z0-9._-]+)(?:/([^?#]*))?", uri)
    if not match or ".." in (match[2] or "").split("/"):
        raise ValueError("Expected gs://bucket/path without query, fragment, or traversal")
    return match[1], match[2] or ""


def split_uri(uri: str) -> tuple[str, str]:
    bucket, key = split_prefix(uri)
    if not key:
        raise ValueError("Expected gs://bucket/path for an object")
    return bucket, key


def download(uri: str, target: Path, expected_sha: str | None = None) -> None:
    bucket, key = split_uri(uri)
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = storage.Client().bucket(bucket).blob(key)
    blob.reload(timeout=60)
    blob.download_to_filename(str(target), if_generation_match=blob.generation, timeout=600)
    if expected_sha and sha256(target) != expected_sha:
        raise ValueError(f"Downloaded object hash mismatch: {uri}")


def upload(path: Path, uri: str) -> None:
    bucket, key = split_uri(uri)
    blob = storage.Client().bucket(bucket).blob(key)
    # A retry is allowed only when the existing object is byte-identical.
    if blob.exists(timeout=60):
        existing = blob.download_as_bytes(timeout=600)
        import hashlib

        if hashlib.sha256(existing).hexdigest() != sha256(path):
            raise ValueError(f"Refusing to overwrite immutable object: {uri}")
        return
    blob.upload_from_filename(str(path), if_generation_match=0, timeout=600)


def fetch_snapshot(uri: str, expected_sha: str, directory: Path) -> Path:
    manifest = directory / "snapshot.json"
    download(uri, manifest, expected_sha)
    payload = json.loads(manifest.read_text())
    bucket, key = split_uri(uri)
    prefix = key.rsplit("/", 1)[0] if "/" in key else ""
    for spec in payload["artifacts"].values():
        path = Path(spec["path"])
        resolved = (directory / path).resolve()
        if path.is_absolute() or not resolved.is_relative_to(directory.resolve()):
            raise ValueError("Invalid snapshot artifact path")
        object_key = "/".join(part for part in (prefix, path.as_posix()) if part)
        download(f"gs://{bucket}/{object_key}", resolved, spec["sha256"])
    return manifest


def fetch_candidate(uri: str, directory: Path) -> None:
    download(f"{uri.rstrip('/')}/candidate.json", directory / "candidate.json")
    payload = json.loads((directory / "candidate.json").read_text())
    allowed = {
        "counties.geojson",
        "counties.json",
        "multipliers.csv",
        "validation.json",
        "provenance.json",
        "changes.json",
        "report.md",
    }
    if set(payload["artifacts"]) != allowed:
        raise ValueError("Invalid candidate artifact inventory")
    for name, spec in payload["artifacts"].items():
        download(f"{uri.rstrip('/')}/{name}", directory / name, spec["sha256"])
