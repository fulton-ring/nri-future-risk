import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from fri_pipeline import heat


def synthetic(tmp_path):
    class Inputs:
        SSP = {"LOWER": "ssp245", "HIGHER": "ssp585"}
        manifest = {"methodology": "synthetic"}
        path = tmp_path / "snapshot.json"

        def loca2_histogram(self, scenario, period):
            counts = np.zeros((4, 2), dtype=int)
            counts[1, 0] = 10000 if scenario == "historical" else 1000
            counts[2, 0] = 1000 if scenario == "historical" else 10000
            counts[-1, 1] = 11000
            return np.array([0.0, 20.0, 30.0, 40.0]), counts

    Inputs.path.write_text("{}")
    return Inputs()


def test_supported_rows_preserve_raw_heat_and_validate_all_source_multipliers(tmp_path):
    from fri_pipeline.current_explain import HeatInputs, explain_current

    source = synthetic(tmp_path)
    weights = sparse.eye(2, format="csr")
    ids = ["01001000100", "01001000200"]
    expected = heat.hazard_multipliers(HeatInputs(source, weights, ids, supported_only=False))
    expected.loc["02001000100"] = np.nan
    result = explain_current(source, weights, ids, expected, ids[1:], "contract", "tracts")
    assert result["unsupportedAreaIds"] == ids[1:]
    assert set(result["counties"]) == {ids[0]}
    assert len(result["counties"][ids[0]]) == 8
    item = result["counties"][ids[0]]["EXHT_L95_MID_LOWER"]
    assert item["futureDaysPerYear"] / item["historicalDaysPerYear"] == pytest.approx(
        item["rawMultiplier"]
    )
    assert result["verifiedAreaScenarios"] == 8
    assert result["methodology"] == "contract"
    assert result["sourceSnapshotMethodology"] == "synthetic"
    expected.iloc[0, 0] += 0.1
    with pytest.raises(ValueError, match="multiplier"):
        explain_current(source, weights, ids, expected, ids[1:], "contract", "tracts")


def test_unsupported_ids_and_nulls_are_enforced(tmp_path):
    from fri_pipeline.current_explain import HeatInputs, explain_current

    source = synthetic(tmp_path)
    weights = sparse.eye(2, format="csr")
    ids = ["01001", "01003"]
    expected = heat.hazard_multipliers(HeatInputs(source, weights, ids, supported_only=False))
    with pytest.raises(ValueError, match="coverage"):
        explain_current(source, weights, ids, expected, [], "contract", "counties")
    expected.iloc[1, 0] = 1.0
    with pytest.raises(ValueError, match="null"):
        explain_current(source, weights, ids, expected, ids[1:], "contract", "tracts")


@pytest.mark.parametrize("verified_count", [8, 7])
def test_augmentation_changes_only_optional_details_and_shard_hash(tmp_path, verified_count):
    spec = importlib.util.spec_from_file_location(
        "augment", Path(__file__).parents[2] / "scripts/augment_current_heat_details.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from fri_pipeline.snapshot import sha256

    display, diagnostics = tmp_path / "display", tmp_path / "diagnostics"
    releases = []
    for level in ("counties", "tracts"):
        folder = diagnostics / level
        folder.mkdir(parents=True)
        doc = {
            "snapshotSha256": "a" * 64,
            "publishedMultipliersSha256": "b" * 64,
            "verifiedAreaScenarios": verified_count,
            "schemaVersion": 1,
            "geography": level,
            "version": "v1",
            "counties": {"01001000100": {"EXHT_L95_MID_LOWER": {"appliedMultiplier": 1}}},
        }
        (folder / "heat-calculations.json").write_text(json.dumps(doc))
        (folder / "heat-diagnostics-manifest.json").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "geography": level,
                    "assets": {
                        "heat-calculations.json": {
                            "sha256": sha256(folder / "heat-calculations.json")
                        }
                    },
                }
            )
        )
        releases.append(
            {
                "geography": level,
                "resultsVersion": "v1",
                "sourceSha256": "b" * 64,
                "assets": {},
                "sourceData": f"https://example.org/fri/{level}/v1/geoparquet/{level}.parquet",
            }
        )
    profiles = display / "tracts/profiles"
    profiles.mkdir(parents=True)
    row = {"id": "01001000100", "name": "a", "values": [1, None]}
    original = {
        "columns": ["x", "y"],
        "counties": [row, {"id": "02001000100", "values": [None, None]}],
    }
    shard = profiles / "01001.json"
    shard.write_text(json.dumps(original))
    releases[1]["profileAssets"] = {"hashes": {"01001": sha256(shard)}}
    path = tmp_path / "releases.json"
    path.write_text(json.dumps(releases))
    if verified_count != 8:
        with pytest.raises(ValueError, match="count"):
            module.augment(diagnostics, display, path)
        assert json.loads(shard.read_text()) == original
        return
    module.augment(diagnostics, display, path)
    after = json.loads(shard.read_text())
    assert after["columns"] == original["columns"]
    assert {k: v for k, v in after["counties"][0].items() if k != "heatCalculations"} == row
    assert after["counties"][1] == original["counties"][1]
    updated = json.loads(path.read_text())
    assert updated[1]["profileAssets"]["hashes"]["01001"] == sha256(shard)
    assert "heatCalculations" not in updated[1]["assets"]
    assert updated[0]["assets"]["heatCalculations"]["sha256"] == sha256(
        diagnostics / "counties/heat-calculations.json"
    )


def test_augmentation_rejects_diagnostics_for_a_different_source(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "augment", Path(__file__).parents[2] / "scripts/augment_current_heat_details.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    folder = tmp_path / "diagnostics/counties"
    folder.mkdir(parents=True)
    doc = {
        "version": "v1",
        "geography": "counties",
        "publishedMultipliersSha256": "wrong",
        "snapshotSha256": "a" * 64,
    }
    calculation = folder / "heat-calculations.json"
    calculation.write_text(json.dumps(doc))
    manifest = {**doc, "assets": {"heat-calculations.json": {"sha256": module.digest(calculation)}}}
    (folder / "heat-diagnostics-manifest.json").write_text(json.dumps(manifest))
    releases = tmp_path / "releases.json"
    release = {
        "geography": "counties",
        "resultsVersion": "v1",
        "sourceSha256": "correct",
        "sourceData": "https://example.org/fri/counties/v1/geoparquet/counties.parquet",
        "assets": {},
    }
    releases.write_text(json.dumps([release]))
    before = releases.read_bytes()
    with pytest.raises(ValueError, match="source"):
        module.augment(tmp_path / "diagnostics", tmp_path / "display", releases)
    assert releases.read_bytes() == before
