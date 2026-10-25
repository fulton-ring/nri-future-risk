import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .candidate import build_candidate, verify_candidate
from .storage import fetch_candidate, fetch_snapshot, upload


def main():
    parser = argparse.ArgumentParser(description="Frozen county risk release pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--release-id", required=True)
    run.add_argument("--code-revision", required=True)
    run.add_argument("--replay", action="store_true")
    run.add_argument("--snapshot", default="")
    run.add_argument("--snapshot-sha256", default="")
    run.add_argument("--output-gcs")
    run.add_argument("--results-uri", default="")
    run.add_argument("--results-version", default="")
    verify = sub.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--publication", action="store_true")
    fetch = sub.add_parser("fetch")
    fetch.add_argument("uri")
    fetch.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "verify":
        meta = verify_candidate(args.directory, publication=args.publication)
    elif args.command == "fetch":
        fetch_candidate(args.uri, args.directory)
        meta = verify_candidate(args.directory)
    else:
        if args.results_uri and (
            args.replay
            or not args.output_gcs
            or not args.results_version
            or not args.snapshot.startswith("gs://")
        ):
            parser.error("Portolan results require a GCS snapshot, experiments output and version")
        with tempfile.TemporaryDirectory(prefix="fri-inputs-") as temporary:
            snapshot = args.snapshot
            if not args.replay:
                import re

                from .snapshot import sha256

                if not re.fullmatch("[a-f0-9]{64}", args.snapshot_sha256):
                    parser.error("updates require --snapshot-sha256")
                if snapshot.startswith("gs://"):
                    snapshot = str(fetch_snapshot(snapshot, args.snapshot_sha256, Path(temporary)))
                elif not snapshot or sha256(Path(snapshot)) != args.snapshot_sha256:
                    parser.error("local snapshot manifest hash mismatch")
            meta = build_candidate(
                args.output,
                args.release_id,
                replay=args.replay,
                snapshot=snapshot,
                code_revision=args.code_revision,
            )
            verify_candidate(args.output)
            if args.output_gcs:
                for path in sorted(args.output.iterdir(), key=lambda p: p.name == "candidate.json"):
                    upload(path, f"{args.output_gcs.rstrip('/')}/{path.name}")
            if args.results_uri:
                provenance_sha = sha256(args.output / "provenance.json")
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "fri_pipeline.archive",
                        "--provenance-uri",
                        f"{args.output_gcs.rstrip('/')}/provenance.json",
                        "--provenance-sha256",
                        provenance_sha,
                        "--results-uri",
                        f"{args.results_uri.rstrip('/')}/future-risk-index/sources",
                        "--experiment-uri",
                        f"{args.output_gcs.rstrip('/')}/source-archive",
                    ],
                    check=True,
                )
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "fri_pipeline.results_cloud",
                        "build",
                        "--kind",
                        "candidate",
                        "--run-uri",
                        args.output_gcs,
                        "--run-sha256",
                        sha256(args.output / "candidate.json"),
                        "--snapshot-uri",
                        args.snapshot,
                        "--snapshot-sha256",
                        args.snapshot_sha256,
                        "--results-uri",
                        args.results_uri,
                        "--version",
                        args.results_version,
                        "--experiment-uri",
                        args.output_gcs,
                    ],
                    check=True,
                )
    print(
        json.dumps(
            {
                "id": meta["id"],
                "publishable": meta["publishable"],
                "archiveRegression": meta["archiveRegression"],
            }
        )
    )


if __name__ == "__main__":
    main()
