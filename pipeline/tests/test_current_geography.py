import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from fri_pipeline import wildfire
from fri_pipeline.current_geography import GeographySnapshot, overlap_weights


def test_sparse_overlaps_order_cache_and_unsupported(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    areas = gpd.GeoDataFrame(
        geometry=[box(-100.1, 39.9, -99.9, 40.1)],
        crs=4326,
        index=pd.Index(["01001000100"], name="TRACTFIPS"),
    )
    coords = pd.DataFrame({"lon": [-99.0, -100.0], "lat": [40.0, 40.0]})
    weights, metadata = overlap_weights(areas, coords, tmp_path, {"boundary": "abc"}, batch_size=1)
    assert weights.shape == (1, 2)
    assert weights[0, 0] == 0 and weights[0, 1] > 0
    assert metadata["halfWidthDegrees"] == 0.125
    again, meta2 = overlap_weights(areas, coords, tmp_path, {"boundary": "abc"})
    assert (again != weights).nnz == 0 and metadata == meta2
    with pytest.raises(ValueError, match="support"):
        overlap_weights(areas, coords.iloc[:1], tmp_path, {"boundary": "abc"})


def test_explicit_county_gamma_never_fits_tract_losses():
    class Inputs:
        SSP = {"LOWER": "ssp245", "HIGHER": "ssp585"}

        def county_weights(self):
            return sparse.eye(2).tocsr(), pd.Index(["01001000100", "01001000200"])

        def fwi(self, scenario, period, **kwargs):
            return np.array([[2.0, 4.0]]) if period == "historical" else np.array([[4.0, 8.0]])

        def baseline(self):
            raise AssertionError("must not fit gamma on tract baseline")

    result = wildfire.hazard_multipliers(Inputs(), gamma=2.0)
    assert (result == 4).all().all()
    assert result.attrs["elasticity"] == 2


def test_adapter_delegates_validation_but_checks_target_coverage():
    class Verified:
        SSP = {"LOWER": "ssp245"}

        def monthly(self, variable, scenario):
            return np.array([[1.0, np.nan]]), pd.date_range("2000-01-01", periods=1)

    master = pd.DataFrame({"STATEABBRV": ["AL"]}, index=pd.Index(["01001"]))
    target = GeographySnapshot(
        Verified(), master, sparse.csr_matrix([[0.0, 1.0]]), sparse.csr_matrix([[1.0, 0.0]])
    )
    with pytest.raises(ValueError, match="coverage"):
        target.monthly("tas", "ssp245")


def test_census_extras_are_recorded_without_changing_nri_population(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    from fri_pipeline.current_geography import load_geography

    path = tmp_path / "cb_2024_us_county_500k.geojson"
    gpd.GeoDataFrame(
        {"GEOID": ["01001", "60030"]}, geometry=[box(0, 0, 1, 1), box(1, 1, 2, 2)], crs=4326
    ).to_file(path)
    baseline = pd.DataFrame({"STATEABBRV": ["AL"]}, index=pd.Index(["01001"], name="STCOFIPS"))
    baseline.attrs["geography"] = "county"
    frame = load_geography([path], baseline, conus_only=False)
    assert frame.index.tolist() == ["01001"]
    assert frame.attrs["excludedBoundaryIds"] == ["60030"]


def test_overlaps_equal_explicit_equal_area_intersections(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    areas = gpd.GeoDataFrame(
        geometry=[box(-100.3, 39.8, -99.9, 40.2), box(-100.05, 39.9, -99.8, 40.1)],
        crs=4326,
        index=pd.Index(["01001", "01003"]),
    )
    coords = pd.DataFrame({"lon": [-100.0, -100.25], "lat": [40.0, 40.0]})
    result, _ = overlap_weights(areas, coords, tmp_path, {}, batch_size=1)
    expected = np.zeros((2, 2))
    projected = areas.to_crs(5070)
    cells = gpd.GeoSeries(
        [
            box(x - 0.125, y - 0.125, x + 0.125, y + 0.125)
            for x, y in coords[["lon", "lat"]].to_numpy()
        ],
        crs=4326,
    ).to_crs(5070)
    for i in range(2):
        for j in range(2):
            expected[i, j] = projected.geometry.iloc[i].intersection(cells.iloc[j]).area
    assert np.allclose(result.toarray(), expected)


def test_full_resolution_2024_tiger_tracts_restore_cartographic_omission(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    from fri_pipeline.current_geography import load_geography

    path = tmp_path / "tl_2024_12_tract.geojson"
    gpd.GeoDataFrame(
        {"GEOID": ["12057980100"]}, geometry=[box(-82.8, 27.6, -82.7, 27.7)], crs=4326
    ).to_file(path)
    baseline = pd.DataFrame(
        {"STATEABBRV": ["FL"]}, index=pd.Index(["12057980100"], name="TRACTFIPS")
    )
    baseline.attrs["geography"] = "tract"
    result = load_geography([path], baseline, conus_only=False)
    assert result.index.equals(baseline.index)
    assert result.attrs["sources"][path.name]
    assert result.attrs["boundaryVintage"] == 2024
    assert result.attrs["fullResolutionSources"] == [path.name]

    old = tmp_path / "tl_2023_12_tract.geojson"
    old.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="2024"):
        load_geography([old], baseline)


def test_missing_boundary_error_reports_count_and_native_id_sample(tmp_path):
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import box

    from fri_pipeline.current_geography import load_geography

    path = tmp_path / "cb_2024_12_tract_500k.geojson"
    gpd.GeoDataFrame(
        {"GEOID": ["12057000100"]}, geometry=[box(-82.8, 27.6, -82.7, 27.7)], crs=4326
    ).to_file(path)
    baseline = pd.DataFrame(
        {"STATEABBRV": ["FL", "FL"]},
        index=pd.Index(["12057000100", "12057980100"], name="TRACTFIPS"),
    )
    baseline.attrs["geography"] = "tract"
    with pytest.raises(ValueError, match="1 native NRI IDs.*12057980100"):
        load_geography([path], baseline)
