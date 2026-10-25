import json

import numpy as np
import pytest


def test_zarr_round_trip_preserves_zero_counts_masks_and_years(tmp_path):
    import xarray as xr

    from fri_pipeline.results import write_array_store

    path = tmp_path / "values.npz"
    values = np.array([[0.0, np.nan], [2.5, np.nan]], dtype=np.float32)
    np.savez(path, values=values, years=np.array([1976, 1977]))
    write_array_store(path, "fwi_historical_historical", tmp_path / "inputs.zarr")
    with xr.open_zarr(tmp_path / "inputs.zarr", consolidated=True) as data:
        np.testing.assert_array_equal(data["values"].values, values)
        np.testing.assert_array_equal(data["years"].values, [1976, 1977])
    counts = np.array([[0, 1], [5, 0]], dtype=np.uint16)
    np.savez(path, counts=counts, edges=np.array([-np.inf, np.inf]))
    write_array_store(path, "loca2_historical_historical", tmp_path / "histogram.zarr")
    with xr.open_zarr(tmp_path / "histogram.zarr", consolidated=True) as data:
        np.testing.assert_array_equal(data["counts"].values, counts)
        assert data["counts"].dtype == np.uint16


def test_portolan_collection_is_separate_and_links_survive_copy(tmp_path):
    from rashid import validate

    from fri_pipeline.results import render_catalog

    assets = {
        "report": {
            "href": "metadata/report.md",
            "type": "text/markdown",
            "roles": ["metadata"],
            "title": "Analysis report",
        }
    }
    for dataset, file in [("county-risk", "counties"), ("reproducibility", "inputs")]:
        path = tmp_path / "future-risk-index" / dataset / file / "v1" / "metadata"
        path.mkdir(parents=True)
        (path / "report.md").write_text("Synthetic fixture report")
    render_catalog(tmp_path, "v1", assets, assets, [-125, 24, -66, 50], [], False)
    report = validate(tmp_path, data=False, schema=True)
    assert report.passed, [
        (f.rule_id, f.message) for f in report.findings if f.severity.value == "error"
    ]
    collection = json.loads((tmp_path / "future-risk-index/catalog.json").read_text())
    assert collection["id"] == "future-risk-index"
    for path in tmp_path.rglob("*.json"):
        data = json.loads(path.read_text())
        for item in [*data.get("links", []), *data.get("assets", {}).values()]:
            href = item["href"]
            if "://" not in href:
                assert (path.parent / href).resolve().exists(), (path, href)
    for dataset, file in [("county-risk", "counties"), ("reproducibility", "inputs")]:
        folder = tmp_path / "future-risk-index" / dataset / file / "v2/metadata"
        folder.mkdir(parents=True)
        (folder / "report.md").write_text("Second synthetic report")
    render_catalog(tmp_path, "v2", assets, assets, [-125, 24, -66, 50], [], False)
    file_catalog = json.loads(
        (tmp_path / "future-risk-index/county-risk/counties/catalog.json").read_text()
    )
    assert {link["href"] for link in file_catalog["links"] if link["rel"] == "child"} == {
        "v1/collection.json",
        "v2/collection.json",
    }
    assert validate(tmp_path, data=False, schema=True).passed


def test_staging_requires_exact_reviewed_candidate_and_separate_collection(tmp_path):
    from fri_pipeline.results_cloud import check_approval
    from fri_pipeline.snapshot import sha256

    approved = tmp_path / "candidate.json"
    approved.write_text('{"id":"approved-candidate"}')
    package = {
        "collection": "future-risk-index",
        "publishable": True,
        "sourceRunManifest": "candidate.json",
        "sourceRunSha256": sha256(approved),
    }
    check_approval(package, approved)
    with pytest.raises(ValueError, match="reviewed"):
        check_approval({**package, "publishable": False}, approved)
    with pytest.raises(ValueError, match="reviewed"):
        check_approval({**package, "collection": "hifld"}, approved)
    with pytest.raises(ValueError, match="exact"):
        check_approval({**package, "sourceRunSha256": "a" * 64}, approved)


def test_candidate_packages_real_county_geometry_and_lossless_input_stores(tmp_path):
    import geopandas as gpd
    from rashid import validate
    from test_climate_run import prepared_snapshot

    from fri_pipeline.candidate import build_candidate
    from fri_pipeline.results import build_results

    snapshot = prepared_snapshot(tmp_path / "inputs")
    candidate = tmp_path / "candidate"
    build_candidate(candidate, "results-test", snapshot=str(snapshot), code_revision="a" * 40)
    originals = tmp_path / "originals.json"
    originals.write_text(
        json.dumps(
            {
                "complete": True,
                "sources": [
                    {
                        "sourceId": "synthetic",
                        "sha256": "a" * 64,
                        "bytes": 1,
                        "href": "originals/fixture/synthetic.nc",
                        "sourceUrl": "https://example.org/fixture",
                    }
                ],
            }
        )
    )
    root = tmp_path / "results"
    package = build_results(
        candidate,
        snapshot,
        originals,
        root,
        "v20261025T120000Z",
        {"lat": np.array([35.0]), "lon": np.array([-100.0])},
    )
    parquet = (
        root
        / "future-risk-index/county-risk/counties/v20261025T120000Z/geoparquet/counties.parquet"
    )
    counties = gpd.read_parquet(parquet)
    assert len(counties) == package["featureCount"] == 3218
    assert counties.county_id.is_unique
    assert package["sourceRunManifest"] == "candidate.json"
    assert len(list(root.rglob("*.zarr"))) == 14
    validation = validate(root, data=False, schema=True)
    assert validation.passed, [(f.rule_id, f.message) for f in validation.errors]
