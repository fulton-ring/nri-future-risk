import hashlib
from unittest.mock import Mock

import pytest


def test_archive_checks_original_bytes_before_upload(tmp_path, monkeypatch):
    from fri_pipeline import archive

    payload = b"original netcdf content"
    source = {
        "id": "source-a",
        "title": "climate.nc",
        "url": "https://example.org/climate.nc",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    client = Mock()
    blob = client.bucket.return_value.blob.return_value
    blob.exists.return_value = False

    def download(url, path):
        path.write_bytes(payload)
        return path

    monkeypatch.setattr(archive, "download_raw", download)
    item = archive.archive_one(
        source, "gs://results/future-risk-index/reproducibility/inputs/v1", tmp_path, client
    )
    assert item["sha256"] == source["sha256"]
    assert item["href"] == f"originals/{source['sha256']}/climate.nc"
    assert blob.upload_from_filename.call_args.kwargs["if_generation_match"] == 0
    assert blob.metadata["sha256"] == source["sha256"]
    source["sha256"] = "f" * 64
    blob.upload_from_filename.reset_mock()
    with pytest.raises(ValueError, match="source hash"):
        archive.archive_one(
            source, "gs://results/future-risk-index/reproducibility/inputs/v1", tmp_path, client
        )
    blob.upload_from_filename.assert_not_called()
