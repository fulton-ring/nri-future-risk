"""Re-acquire the exact original files recorded by a completed experiment, in Batch."""

import argparse
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from google.cloud import storage

from .candidate import write_json
from .prepare import download_loca2, download_raw
from .snapshot import sha256
from .storage import download, split_uri, upload


def archive_one(source: dict, destination: str, cache: Path, client) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", source["id"]):
        raise ValueError("Invalid source identity")
    if not source["url"].startswith("https://"):
        raise ValueError("Original sources must use HTTPS")
    filename = Path(source["title"]).name
    if filename != source["title"] or filename in {"", ".", ".."}:
        raise ValueError("Invalid original source filename")
    href = f"originals/{source['id']}/{filename}"
    bucket, prefix = split_uri(destination)
    blob = client.bucket(bucket).blob(f"{prefix}/{href}")
    item = {
        "href": href,
        "sha256": source["sha256"],
        "bytes": source["bytes"],
        "sourceId": source["id"],
        "sourceUrl": source["url"],
    }
    if blob.exists():
        blob.reload()
        if blob.size != source["bytes"] or (blob.metadata or {}).get("sha256") != source["sha256"]:
            raise ValueError(f"Existing source archive differs: {source['url']}")
        return item
    local = cache / source["id"] / filename
    local.parent.mkdir(parents=True, exist_ok=True)
    if urlparse(source["url"]).hostname == "cirrus.ucsd.edu":
        download_loca2(source["url"], local)
    else:
        download_raw(source["url"], local)
    if sha256(local) != source["sha256"] or local.stat().st_size != source["bytes"]:
        raise ValueError(f"Original source hash or size changed: {source['url']}")
    blob.metadata = {"sha256": source["sha256"], "source-id": source["id"]}
    blob.upload_from_filename(str(local), if_generation_match=0, timeout=1200)
    local.unlink()
    print(f"Archived {source['title']}: {source['bytes']} bytes", flush=True)
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provenance-uri", required=True)
    parser.add_argument("--provenance-sha256", required=True)
    parser.add_argument("--results-uri", required=True)
    parser.add_argument("--experiment-uri", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="source-archive-") as temp:
        cache = Path(temp)
        os.environ["FRI_CACHE"] = str(cache)
        provenance = cache / "provenance.json"
        download(args.provenance_uri, provenance, args.provenance_sha256)
        sources = json.loads(provenance.read_text())["inputSnapshot"]["sources"]
        if len({source["id"] for source in sources}) != len(sources):
            raise ValueError("Duplicate source identities")
        client = storage.Client()
        completed, errors = [], []

        def collect(source):
            try:
                return archive_one(source, args.results_uri, cache, client)
            except Exception as error:
                errors.append({"sourceId": source["id"], "url": source["url"], "error": str(error)})
                print(f"Source archive failed: {source['url']}: {error}", flush=True)
                return None

        # Large LOCA2 files are serial, with four ranges each. Other sources use a separate
        # bounded pool so their downloads overlap without retaining hundreds of GB on disk.
        large = [s for s in sources if urlparse(s["url"]).hostname == "cirrus.ucsd.edu"]
        others = [s for s in sources if s not in large]
        with ThreadPoolExecutor(4) as pool:
            futures = [pool.submit(collect, source) for source in others]
            for source in large:
                item = collect(source)
                if item:
                    completed.append(item)
            for future in as_completed(futures):
                item = future.result()
                if item:
                    completed.append(item)
        manifest = cache / "originals-manifest.json"
        value = {
            "complete": not errors,
            "expectedSources": len(sources),
            "sources": sorted(completed, key=lambda item: item["sourceId"]),
            "errors": errors,
            "provenanceSha256": args.provenance_sha256,
            "codeRevision": os.environ.get("FRI_CODE_REVISION"),
        }
        write_json(manifest, value)
        upload(manifest, f"{args.experiment_uri.rstrip('/')}/originals-manifest.json")
        if errors:
            raise RuntimeError(f"{len(errors)} original sources could not be archived exactly")
        upload(manifest, f"{args.results_uri.rstrip('/')}/metadata/originals-manifest.json")
        print(f"Archived all {len(completed)} original sources", flush=True)


if __name__ == "__main__":
    main()
