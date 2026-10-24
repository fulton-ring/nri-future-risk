import json

import numpy as np
import pandas as pd
import pytest

from fri_pipeline.candidate import build_candidate, verify_candidate
from fri_pipeline.flow import merged_multipliers
from fri_pipeline.scoring import SCENARIOS, SUPPORTED
from fri_pipeline.snapshot import EXCLUDED, read_master


def test_hamilton_archive_replay_is_valid_but_cannot_publish(tmp_path):
    result = build_candidate(tmp_path, "replay-test", replay=True, code_revision="a" * 40)
    assert result["publishable"] is False
    assert result["population"] == 3231
    assert result["countyCount"] == 3218
    assert result["archiveRegression"]["comparisons"] == 310176
    assert verify_candidate(tmp_path)["id"] == "replay-test"
    with pytest.raises(ValueError, match="replay"):
        verify_candidate(tmp_path, publication=True)
    data = json.loads((tmp_path / "counties.geojson").read_text())
    la = next(f["properties"] for f in data["features"] if f["properties"]["fips"] == "06037")
    assert "CFLD_MID_LOWER_PRISKS" in la
    assert "HRCN_MID_LOWER_PRISKS" in la
    (tmp_path / "counties.geojson").write_text("tampered")
    with pytest.raises(ValueError, match="hash"):
        verify_candidate(tmp_path)
    from fri_pipeline.snapshot import sha256

    data["features"][0]["properties"]["WFIR_MID_LOWER_PRISKS"] = -999
    (tmp_path / "counties.geojson").write_text(json.dumps(data))
    meta_path = tmp_path / "candidate.json"
    meta = json.loads(meta_path.read_text())
    meta["artifacts"]["counties.geojson"] = {
        "sha256": sha256(tmp_path / "counties.geojson"),
        "bytes": (tmp_path / "counties.geojson").stat().st_size,
    }
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="scored data"):
        verify_candidate(tmp_path)


def test_reject_missing_counties_and_wildfire_below_floor():
    master = read_master()
    columns = [f"{v}_{s}_HM" for v in SUPPORTED for s in SCENARIOS]
    updates = master.loc[~master.STATEABBRV.isin(EXCLUDED), columns].copy()
    with pytest.raises(ValueError, match="CONUS"):
        merged_multipliers(master, updates.iloc[:-1])
    updates.iloc[0, 4] = 0.9
    with pytest.raises(ValueError, match=">= 1"):
        merged_multipliers(master, updates)
    updates.iloc[0, 4] = np.nan
    with pytest.raises(ValueError, match="finite"):
        merged_multipliers(master, updates)


def test_reject_changed_population_and_unsupported_variants():
    master = read_master()
    columns = [f"{v}_{s}_HM" for v in SUPPORTED for s in SCENARIOS]
    updates = master.loc[~master.STATEABBRV.isin(EXCLUDED), columns].copy()
    updates["EXHT_N99_MID_LOWER_HM"] = 1
    with pytest.raises(ValueError, match="supported"):
        merged_multipliers(master, updates)


def test_hazard_helpers_keep_snapshot_injection_explicit():
    from fri_pipeline.heat import days_above_pos, percentile_position

    counts = np.array([[1, 0], [3, 0], [0, 0]])
    position = percentile_position(counts, 50)
    np.testing.assert_allclose(days_above_pos(counts, position)[0], 2)
    assert pd.isna(days_above_pos(counts, position)[1])
