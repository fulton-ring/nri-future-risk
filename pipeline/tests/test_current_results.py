import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from fri_pipeline.current_results import package_geography, validate_version


def test_version_paths_cannot_escape_collection():
    assert validate_version("v20261111T120000Z") == "v20261111T120000Z"
    for value in ["../outside", "new/version", "", "v space"]:
        with pytest.raises(ValueError):
            validate_version(value)


def test_county_and_tract_files_share_dataset_but_have_own_version(tmp_path):
    version = "v20261111T120000Z"
    for level, fips in [("counties", "09110"), ("tracts", "09110000100")]:
        index = pd.Index([fips], name="geoid")
        geometry = gpd.GeoDataFrame(
            {"name": ["Capitol"], "state": ["CT"]},
            geometry=[box(-73, 41, -72, 42)],
            index=index,
            crs=4326,
        )
        baseline = pd.DataFrame({"DRGT_EALT": [100.0], "DRGT_RISKV": [120.0]}, index=index)
        scores = pd.DataFrame(
            {"DRGT_MID_LOWER_HM": [2.0], "DRGT_MID_LOWER_PALT": [200.0]}, index=index
        )
        record = package_geography(
            tmp_path,
            version,
            level,
            geometry,
            baseline,
            scores,
            {"baseline": "NRI v1.20"},
            {"checks": 1},
        )
        folder = tmp_path / "future-risk-index" / "fri" / level / version
        restored = gpd.read_parquet(folder / "geoparquet" / f"{level}.parquet")
        assert restored.geoid.tolist() == [fips]
        assert restored.DRGT_EALT.tolist() == [100.0]
        assert restored.DRGT_MID_LOWER_PALT.tolist() == [200.0]
        assert (
            json.loads((folder / "metadata" / "rating-bins.json").read_text())["baseline"]
            == "NRI v1.20"
        )
        assert record["file"] == level
        with pytest.raises(ValueError, match="immutable"):
            package_geography(tmp_path, version, level, geometry, baseline, scores, {}, {})
