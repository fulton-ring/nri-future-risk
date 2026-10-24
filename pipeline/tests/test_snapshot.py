import hashlib
import json

import numpy as np
import pytest
from scipy import sparse

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


def test_static_source_mask_is_preserved_but_temporal_gaps_fail():
    from fri_pipeline.snapshot import source_domain

    values = np.array([[1.0, np.nan], [2.0, np.nan]])
    np.testing.assert_array_equal(source_domain(values), [True, False])
    assert np.isnan(values[:, 1]).all()  # No fill values are invented.
    with pytest.raises(ValueError, match="Temporal"):
        source_domain(np.array([[1.0, np.nan], [np.nan, np.nan]]))
    with pytest.raises(ValueError, match="Temporal"):
        source_domain(np.array([[1.0, np.inf], [2.0, np.inf]]))


def test_domain_must_be_stable_and_cover_every_county(tmp_path):
    snapshot = Snapshot(manifest(tmp_path))
    weights = sparse.csr_matrix([[1.0, 1.0], [2.0, 0.0]])
    snapshot.record_domain("nex", np.array([True, False]), weights)
    assert snapshot.coverage_diagnostics["nex"]["structuralNoDataCells"] == 1
    assert snapshot.coverage_diagnostics["nex"]["minimumCountyCoverage"] == 0.5
    with pytest.raises(ValueError, match="changes"):
        snapshot.record_domain("nex", np.array([True, True]), weights)
    with pytest.raises(ValueError, match="coverage"):
        snapshot.record_domain("other", np.array([False, True]), weights)


def test_static_masks_keep_original_area_weighted_numbers():
    from fri_pipeline.drought import area_mean as drought_mean
    from fri_pipeline.wildfire import area_mean as wildfire_mean

    values = np.array([2.0, np.nan, 4.0])
    weights = sparse.csr_matrix([[1.0, 10.0, 3.0], [2.0, 2.0, 0.0]])
    for mean in (drought_mean, wildfire_mean):
        np.testing.assert_allclose(mean(values, weights), [3.5, 2.0])
        np.testing.assert_array_equal(
            mean(values, weights), mean(values[[0, 2]], weights[:, [0, 2]])
        )
