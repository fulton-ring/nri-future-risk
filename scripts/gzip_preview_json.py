"""Re-store every explorer JSON object for the releases in src/data/releases.json gzip-encoded.

The bytes a browser decodes are unchanged, so the published SHA-256 values stay valid. Objects
already gzip-encoded are skipped, so the script is safe to rerun after each upload.
"""

import argparse
import hashlib
import json
import posixpath
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


def preview_prefixes(releases):
    """(bucket, prefix) of each release's preview folder, from its index asset URL."""
    for release in releases:
        url = urlparse(release["assets"]["counties.json"]["path"])
        if url.netloc != "storage.googleapis.com":
            raise ValueError(f"Expected a storage.googleapis.com asset URL: {url.geturl()}")
        bucket, _, key = url.path.lstrip("/").partition("/")
        yield bucket, posixpath.dirname(key) + "/"


def main():
    from google.cloud import storage

    from fri_pipeline.storage import upload_gzip_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    client = storage.Client()
    releases = json.loads((ROOT / "src/data/releases.json").read_text())
    for bucket_name, prefix in preview_prefixes(releases):
        for blob in client.list_blobs(bucket_name, prefix=prefix):
            if not blob.name.endswith(".json") or blob.content_encoding == "gzip":
                continue
            data = blob.download_as_bytes(if_generation_match=blob.generation, timeout=600)
            digest = hashlib.sha256(data).hexdigest()
            expected = (blob.metadata or {}).get("sha256")
            if expected and expected != digest:
                raise ValueError(f"Stored bytes differ from their recorded SHA-256: {blob.name}")
            action = "would gzip" if args.dry_run else "gzip"
            print(f"{action} gs://{bucket_name}/{blob.name} ({len(data):,} bytes)")
            if args.dry_run:
                continue
            target = client.bucket(bucket_name).blob(blob.name)
            target.metadata = {**(blob.metadata or {}), "sha256": digest}
            target.cache_control = blob.cache_control
            upload_gzip_json(target, data, if_generation_match=blob.generation, timeout=600)


if __name__ == "__main__":
    main()
