"""Small gcloud wrapper for the single bounded Cloud Batch task."""

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .candidate import validate_id
from .storage import split_uri


def job_config(
    *,
    image: str,
    service_account: str,
    snapshot: str,
    snapshot_sha: str,
    output: str,
    release_id: str,
    code_revision: str,
    network: str,
    subnetwork: str,
    replay: bool = False,
) -> dict:
    validate_id(release_id)
    if not re.fullmatch(r"projects/[^/]+/global/networks/[^/]+", network) or not re.fullmatch(
        r"projects/[^/]+/regions/[^/]+/subnetworks/[^/]+", subnetwork
    ):
        raise ValueError("Explicit private network and regional subnetwork paths are required")
    if not re.fullmatch(r"[a-z0-9./_-]+@sha256:[a-f0-9]{64}", image):
        raise ValueError("Batch requires an immutable image digest")
    if replay and (snapshot or snapshot_sha):
        raise ValueError("Archive replay cannot accept update inputs")
    if not replay and not re.fullmatch(r"[a-f0-9]{64}", snapshot_sha):
        raise ValueError("Snapshot SHA-256 is required")
    if not re.fullmatch(r"[a-f0-9]{40}", code_revision):
        raise ValueError("Full code revision is required")
    if not replay:
        split_uri(snapshot)
    split_uri(output)
    commands = [
        "run",
        "--output",
        "/tmp/candidate",
        "--release-id",
        release_id,
        "--code-revision",
        code_revision,
        "--output-gcs",
        output,
    ]
    commands += (
        ["--replay"] if replay else ["--snapshot", snapshot, "--snapshot-sha256", snapshot_sha]
    )
    return {
        "taskGroups": [
            {
                "taskCount": 1,
                "parallelism": 1,
                "taskSpec": {
                    "runnables": [{"container": {"imageUri": image, "commands": commands}}],
                    "computeResource": {"cpuMilli": 8000, "memoryMib": 32768},
                    "maxRetryCount": 0,
                    "maxRunDuration": "14400s",
                    "environment": {"variables": {"FRI_WORKER_IMAGE": image}},
                },
            }
        ],
        "allocationPolicy": {
            "network": {
                "networkInterfaces": [
                    {"network": network, "subnetwork": subnetwork, "noExternalIpAddress": True}
                ]
            },
            "instances": [
                {
                    "policy": {
                        "machineType": "e2-standard-8",
                        "bootDisk": {"type": "pd-balanced", "sizeGb": 100},
                    }
                }
            ],
            "serviceAccount": {"email": service_account},
        },
        "logsPolicy": {"destination": "CLOUD_LOGGING"},
        "labels": {"application": "future-risk-index", "release": release_id},
    }


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "project",
        "region",
        "image",
        "service-account",
        "output",
        "release-id",
        "code-revision",
        "network",
        "subnetwork",
    ):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--snapshot-sha256", default="")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    config = job_config(
        image=args.image,
        service_account=args.service_account,
        snapshot=args.snapshot,
        snapshot_sha=args.snapshot_sha256,
        output=args.output,
        release_id=args.release_id,
        code_revision=args.code_revision,
        network=args.network,
        subnetwork=args.subnetwork,
        replay=args.replay,
    )
    base = ["gcloud", "batch", "jobs"]
    common = ["--project", args.project, "--location", args.region]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "job.json"
        path.write_text(json.dumps(config))
        subprocess.run(
            [*base, "submit", args.release_id, *common, "--config", str(path)], check=True
        )
    deadline = time.monotonic() + 18000
    while time.monotonic() < deadline:
        result = subprocess.run(
            [*base, "describe", args.release_id, *common, "--format=value(status.state)"],
            check=True,
            capture_output=True,
            text=True,
        )
        state = result.stdout.strip()
        print(f"Batch {args.release_id}: {state}", flush=True)
        if state == "SUCCEEDED":
            return
        if state in {"FAILED", "DELETION_IN_PROGRESS"}:
            raise RuntimeError(f"Batch job did not succeed: {state}")
        time.sleep(30)
    subprocess.run([*base, "delete", args.release_id, *common, "--quiet"], check=True)
    raise TimeoutError("Batch exceeded the five-hour wait limit; deletion requested")


if __name__ == "__main__":
    main()
