import hashlib
import json

import pytest

from fri_pipeline.snapshot import Snapshot, read_master


def manifest(tmp_path, path="data.csv"):
    content = b"id,value\n01001,1\n"
    (tmp_path / "data.csv").write_bytes(content)
    from fri_pipeline.snapshot import CONTRACT

    payload = {
        "methodology": CONTRACT["id"],
        "rebuildCommit": CONTRACT["rebuildCommit"],
        "schemaVersion": 1,
        "coverage": "CONUS",
        "sources": [
            {
                "id": "test",
                "url": "https://example.org/source",
                "title": "fixture",
                "sha256": hashlib.sha256(content).hexdigest(),
                "retrievedAt": "2026-10-24",
            }
        ],
        "artifacts": {
            "values": {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "sourceIds": ["test"],
            }
        },
    }
    target = tmp_path / "snapshot.json"
    target.write_text(json.dumps(payload))
    return target


def test_snapshot_rejects_tampering(tmp_path):
    target = manifest(tmp_path)
    Snapshot(target)
    (tmp_path / "data.csv").write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        Snapshot(target)


@pytest.mark.parametrize("path", ["../outside.csv", "/tmp/outside.csv"])
def test_snapshot_rejects_paths_outside_its_root(tmp_path, path):
    with pytest.raises(ValueError, match="path"):
        Snapshot(manifest(tmp_path, path))


def test_snapshot_rejects_missing_provenance(tmp_path):
    target = manifest(tmp_path)
    payload = json.loads(target.read_text())
    payload["artifacts"]["values"]["sourceIds"] = ["unknown"]
    target.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="source"):
        Snapshot(target)


def test_pinned_archive_regression():
    from fri_pipeline.scoring import reproduce_archive

    master = read_master()
    assert reproduce_archive(master)["comparisons"] == 310176
