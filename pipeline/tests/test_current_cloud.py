import pytest

from fri_pipeline.current_cloud import job_config


def test_current_batch_job_pins_worker_and_runs_in_private_network():
    config = job_config(
        image="us-central1-docker.pkg.dev/hifld-next/fri/preparation@sha256:" + "a" * 64,
        service_account="worker@example.iam.gserviceaccount.com",
        network="projects/hifld-next/global/networks/private",
        subnetwork="projects/hifld-next/regions/us-central1/subnetworks/private",
        run_id="fri-nri-v120-test",
        version="v20261111T120000Z",
        revision="b" * 40,
        output="gs://future-risk-index-experiments/runs/fri-nri-v120-test",
    )
    task = config["taskGroups"][0]["taskSpec"]
    container = task["runnables"][0]["container"]
    assert container["commands"][:2] == ["-m", "fri_pipeline.current_run"]
    assert config["allocationPolicy"]["network"]["networkInterfaces"][0]["noExternalIpAddress"]
    assert task["maxRetryCount"] == 0
    assert "--output-gcs" in container["commands"]
    for change in [
        {"image": "image:latest"},
        {"revision": "main"},
        {"output": "gs://future-risk-index-experiments/runs/someone-else"},
    ]:
        with pytest.raises(ValueError):
            job_config(
                image=change.get("image", container["imageUri"]),
                service_account="worker@example.iam.gserviceaccount.com",
                network="projects/hifld-next/global/networks/private",
                subnetwork="projects/hifld-next/regions/us-central1/subnetworks/private",
                run_id="fri-nri-v120-test",
                version="v20261111T120000Z",
                revision=change.get("revision", "b" * 40),
                output=change.get(
                    "output", "gs://future-risk-index-experiments/runs/fri-nri-v120-test"
                ),
            )
