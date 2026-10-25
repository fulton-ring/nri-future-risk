import pytest

from fri_pipeline.cloud import job_config


def test_batch_uses_digest_pin_and_finite_resources():
    config = job_config(
        image="us-docker.pkg.dev/project/fri/worker@sha256:" + "a" * 64,
        service_account="worker@project.iam.gserviceaccount.com",
        snapshot="gs://inputs/snapshot.json",
        snapshot_sha="b" * 64,
        output="gs://candidates/runs/fri-test",
        release_id="fri-test",
        code_revision="c" * 40,
        network="projects/project/global/networks/private",
        subnetwork="projects/project/regions/us-central1/subnetworks/private",
    )
    task = config["taskGroups"][0]["taskSpec"]
    assert task["maxRetryCount"] == 0
    assert task["maxRunDuration"] == "14400s"
    assert task["computeResource"]["memoryMib"] == 32768
    command = task["runnables"][0]["container"]["commands"]
    assert "--snapshot-sha256" in command
    assert config["allocationPolicy"]["serviceAccount"]["email"].startswith("worker@")
    interface = config["allocationPolicy"]["network"]["networkInterfaces"][0]
    assert interface["noExternalIpAddress"] is True
    assert interface["subnetwork"].endswith("/subnetworks/private")


def test_batch_rejects_mutable_images():
    with pytest.raises(ValueError, match="digest"):
        job_config(
            image="image:latest",
            service_account="worker@example.com",
            snapshot="gs://inputs/snapshot.json",
            snapshot_sha="b" * 64,
            output="gs://candidates/runs/fri-test",
            release_id="fri-test",
            code_revision="c" * 40,
            network="projects/project/global/networks/private",
            subnetwork="projects/project/regions/us-central1/subnetworks/private",
        )


def test_batch_replay_needs_no_snapshot_and_remains_an_explicit_mode():
    config = job_config(
        image="us-docker.pkg.dev/project/fri/worker@sha256:" + "a" * 64,
        service_account="worker@project.iam.gserviceaccount.com",
        snapshot="",
        snapshot_sha="",
        output="gs://candidates/runs/replay-test",
        release_id="replay-test",
        code_revision="c" * 40,
        replay=True,
        network="projects/project/global/networks/private",
        subnetwork="projects/project/regions/us-central1/subnetworks/private",
    )
    command = config["taskGroups"][0]["taskSpec"]["runnables"][0]["container"]["commands"]
    assert "--replay" in command
    assert "--snapshot" not in command


def test_batch_passes_two_bucket_results_and_version():
    config = job_config(
        image="us-docker.pkg.dev/project/fri/worker@sha256:" + "a" * 64,
        service_account="worker@example.com",
        snapshot="gs://experiments/snapshot.json",
        snapshot_sha="b" * 64,
        output="gs://experiments/runs/fri-test",
        release_id="fri-test",
        code_revision="c" * 40,
        network="projects/project/global/networks/private",
        subnetwork="projects/project/regions/us-central1/subnetworks/private",
        results_uri="gs://future-risk-index-results",
        results_version="v20261025T120000Z",
    )
    command = config["taskGroups"][0]["taskSpec"]["runnables"][0]["container"]["commands"]
    assert command[command.index("--results-uri") + 1] == "gs://future-risk-index-results"
    assert command[command.index("--results-version") + 1] == "v20261025T120000Z"
