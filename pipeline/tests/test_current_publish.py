import pytest

from fri_pipeline.current_publish import merge_catalog, validate_inventory


def test_review_catalog_keeps_prior_datasets_versions_and_updates_latest():
    prior = {
        "id": "future-risk-index/fri/counties",
        "links": [
            {"rel": "child", "href": "v20261025/collection.json"},
            {"rel": "latest-version", "href": "v20261025/collection.json"},
        ],
    }
    current = {
        "id": prior["id"],
        "links": [
            {"rel": "self", "href": "catalog.json"},
            {"rel": "child", "href": "v20261111/collection.json"},
            {"rel": "latest-version", "href": "v20261111/collection.json"},
        ],
    }
    merged = merge_catalog(prior, current)
    assert {x["href"] for x in merged["links"] if x["rel"] == "child"} == {
        "v20261025/collection.json",
        "v20261111/collection.json",
    }
    assert [x["href"] for x in merged["links"] if x["rel"] == "latest-version"] == [
        "v20261111/collection.json"
    ]
    reverse = merge_catalog(current, prior)
    assert [link["href"] for link in reverse["links"] if link["rel"] == "latest-version"] == [
        "v20261111/collection.json"
    ]
    with pytest.raises(ValueError):
        merge_catalog({"id": "different"}, current)


def test_review_manifest_cannot_copy_outside_its_version():
    manifest = {
        "version": "v20261111",
        "collection": "future-risk-index",
        "baseline": "NRI v1.20",
        "files": {
            "future-risk-index/fri/tracts/v20261111/collection.json": {
                "sha256": "a" * 64,
                "bytes": 10,
            }
        },
    }
    validate_inventory(manifest)
    for path in [
        "../secret",
        "future-risk-index/fri/tracts/v20261025/collection.json",
        "future-risk-index/fri/counties/current.json",
    ]:
        manifest["files"] = {path: {"sha256": "a" * 64, "bytes": 10}}
        with pytest.raises(ValueError):
            validate_inventory(manifest)
