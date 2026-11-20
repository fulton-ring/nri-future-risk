"""Submit the v1.20 county/tract calculation to one bounded Cloud Batch task."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from .cloud import job_config as legacy_job_config
from .current_results import validate_version
from .current_run import CONTRACT
from .storage import split_uri


def job_config(
    *,
    image,
    service_account,
    network,
    subnetwork,
    run_id,
    version,
    revision,
    output,
    snapshot="",
    snapshot_sha="",
    results_uri="",
):
    validate_version(version)
    bucket, key = split_uri(output)
    if key != f"runs/{run_id}":
        raise ValueError("Output must be the run-specific experiments/runs/<run-id> prefix")
    if bool(snapshot) != bool(snapshot_sha):
        raise ValueError("Snapshot location and SHA-256 must be supplied together")
    config = legacy_job_config(
        image=image,
        service_account=service_account,
        network=network,
        subnetwork=subnetwork,
        release_id=run_id,
        code_revision=revision,
        output=output,
        snapshot="gs://unused/contract-pinned",
        snapshot_sha="a" * 64,
    )
    commands = [
        "-m",
        "fri_pipeline.current_run",
        "--run-id",
        run_id,
        "--version",
        version,
        "--code-revision",
        revision,
        "--output-gcs",
        f"gs://{bucket}/{key}",
    ]
    if snapshot:
        if not re.fullmatch("[a-f0-9]{64}", snapshot_sha):
            raise ValueError("Snapshot requires a complete SHA-256")
        if not snapshot.startswith(("https://", "gs://")):
            raise ValueError("Snapshot must use HTTPS or GCS")
        commands += ["--snapshot", snapshot, "--snapshot-sha256", snapshot_sha]
    if results_uri:
        from .storage import split_prefix

        split_prefix(results_uri)
        commands += ["--results-uri", results_uri]
    task = config["taskGroups"][0]["taskSpec"]
    task["runnables"][0]["container"].update(
        entrypoint="/app/pipeline/.venv/bin/python", commands=commands
    )
    task["computeResource"] = {"cpuMilli": 32000, "memoryMib": 131072}
    task["maxRunDuration"] = "21600s"
    policy = config["allocationPolicy"]["instances"][0]["policy"]
    policy["machineType"] = "e2-standard-32"
    policy["bootDisk"]["sizeGb"] = 200
    config["labels"] = {"application": "future-risk-index", "stage": "nri-v120-tracts"}
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "project",
        "region",
        "image",
        "service-account",
        "network",
        "subnetwork",
        "run-id",
        "version",
        "code-revision",
        "output",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--snapshot-sha256", default="")
    parser.add_argument("--config-output", type=Path)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--results-uri", default="")
    args = parser.parse_args()
    config = job_config(
        image=args.image,
        service_account=args.service_account,
        network=args.network,
        subnetwork=args.subnetwork,
        run_id=args.run_id,
        version=args.version,
        revision=args.code_revision,
        output=args.output,
        snapshot=args.snapshot,
        snapshot_sha=args.snapshot_sha256,
        results_uri=args.results_uri,
    )
    path = args.config_output or Path("/tmp/fri-current-batch-job.json")
    path.write_text(json.dumps(config, indent=2) + "\n")
    if args.submit:
        subprocess.run(
            [
                "gcloud",
                "batch",
                "jobs",
                "submit",
                args.run_id,
                "--project",
                args.project,
                "--location",
                args.region,
                "--config",
                str(path),
            ],
            check=True,
        )
    print(
        json.dumps(
            {
                "runId": args.run_id,
                "version": args.version,
                "config": str(path),
                "baseline": CONTRACT["baseline"],
                "submitted": args.submit,
            }
        )
    )


if __name__ == "__main__":
    main()
