import hashlib
import json

import numpy as np
from test_climate_run import prepared_snapshot

from fri_pipeline.explain import explain_heat
from fri_pipeline.snapshot import Snapshot


def test_heat_details_preserve_raw_ratio_below_the_published_floor(tmp_path):
    path = prepared_snapshot(tmp_path / "inputs")
    manifest = json.loads(path.read_text())
    spec = manifest["artifacts"]["loca2_ssp245_MID"]
    target = path.parent / spec["path"]
    with np.load(target) as data:
        edges, counts = data["edges"], data["counts"].copy()
    counts[300] += 900
    counts[400] -= 900
    np.savez(target, edges=edges, counts=counts)
    spec["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))
    result = explain_heat(Snapshot(path))
    first = next(iter(result["counties"].values()))
    details = first["EXHT_L95_MID_LOWER"]
    assert np.isclose(details["rawMultiplier"], 0.1)
    assert details["appliedMultiplier"] == 1
    assert np.isclose(details["futureDaysPerYear"] / details["historicalDaysPerYear"], 0.1)
    assert result["snapshotSha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["temperatureFloorC"] == 23.07
