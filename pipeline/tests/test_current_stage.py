import copy
import hashlib
import json

import pytest

from fri_pipeline.current_publish import merge_catalog
from fri_pipeline.current_stage import approved_collection, parent_catalogs, validate_approval


def approval(tmp_path):
    key = "future-risk-index/fri/tracts/v20261111/collection.json"
    source = {
        "collection": "future-risk-index",
        "baseline": "NRI v1.20",
        "version": "v20261111",
        "publishable": False,
        "provenance": {"runId": "review-run"},
        "files": {key: {"sha256": "a" * 64, "bytes": 10}},
    }
    path = tmp_path / "result-manifest.json"
    path.write_text(json.dumps(source))
    receipt = {
        **source,
        "status": "review",
        "resultsUri": "gs://results",
        "sourceManifestUri": "gs://experiments/runs/review-run/result-manifest.json",
        "sourceManifestSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    review = tmp_path / "public-review.json"
    review.write_text(json.dumps(receipt))
    return path, review, receipt


def test_exact_merged_source_approves_review_without_changing_science(tmp_path):
    source, review, receipt = approval(tmp_path)
    assert validate_approval(source, review, "gs://results") == receipt
    source.write_text(source.read_text() + "\n")
    with pytest.raises(ValueError, match="source manifest"):
        validate_approval(source, review, "gs://results")


@pytest.mark.parametrize(
    "change", ["version", "baseline", "results", "source", "path", "missing", "mixed"]
)
def test_rejects_unapproved_or_mixed_receipts(tmp_path, change):
    source, review, receipt = approval(tmp_path)
    if change == "version":
        receipt["version"] = "vOTHER"
    elif change == "baseline":
        receipt["baseline"] = "NRI v1.19"
    elif change == "results":
        receipt["resultsUri"] = "gs://elsewhere"
    elif change == "source":
        receipt["sourceManifestUri"] = "gs://experiments/runs/another/result-manifest.json"
    elif change == "missing":
        receipt["files"] = {}
    else:
        name = (
            "future-risk-index/fri/tracts/../secret"
            if change == "path"
            else "future-risk-index/fri/counties/v20261111/extra"
        )
        receipt["files"][name] = {"sha256": "b" * 64, "bytes": 3}
    review.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        validate_approval(source, review, "gs://results")


def test_parent_navigation_and_preservation_and_approval_metadata():
    doc = {
        "id": "future-risk-index/fri/tracts/v20261111",
        "version": "v20261111",
        "title": "Tracts",
        "assets": {"data": {"href": "geoparquet/tracts.parquet", "file:checksum": "abc"}},
        "links": [{"rel": "root", "href": "../../../../catalog.json"}],
    }
    original = copy.deepcopy(doc)
    approved = approved_collection(doc, "1" * 40, "a" * 64)
    assert doc == original
    assert approved["assets"] == doc["assets"]
    assert approved["fri:publication_status"] == "candidate"
    assert approved["fri:approved_revision"] == "1" * 40
    assert approved["links"][0]["href"] == "../../../catalog.json"
    parents = parent_catalogs([approved])
    assert set(parents) == {
        "future-risk-index/catalog.json",
        "future-risk-index/fri/catalog.json",
        "future-risk-index/fri/tracts/catalog.json",
    }
    prior = {
        "id": "future-risk-index/fri/tracts",
        "links": [{"rel": "child", "href": "v20260101/collection.json"}],
    }
    merged = merge_catalog(prior, parents["future-risk-index/fri/tracts/catalog.json"])
    assert {x["href"] for x in merged["links"] if x["rel"] == "child"} == {
        "v20260101/collection.json",
        "v20261111/collection.json",
    }


def test_staging_pins_receipt_and_copies_only_approved_version(tmp_path, monkeypatch):
    from fri_pipeline import current_stage

    source, review, receipt = approval(tmp_path)
    name = next(iter(receipt["files"]))
    document = {
        "id": name.removesuffix("/collection.json"),
        "version": receipt["version"],
        "title": "Tracts",
        "assets": {"numeric": {"href": "data.parquet"}},
        "links": [],
    }
    body = json.dumps(document).encode()
    spec = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    source_doc = json.loads(source.read_bytes())
    source_doc["files"][name] = spec
    data_name = name.removesuffix("collection.json") + "data.parquet"
    source_doc["files"][data_name] = {"sha256": "b" * 64, "bytes": 1000000000}
    source.write_text(json.dumps(source_doc))
    receipt.update(source_doc)
    receipt["sourceManifestSha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    review.write_text(json.dumps(receipt))
    downloads, copies, puts, catalogs = [], [], {}, {}

    def download(uri, path, expected_sha):
        downloads.append((uri, expected_sha))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = review.read_bytes() if uri.endswith("/_releases/v20261111.json") else body
        assert hashlib.sha256(payload).hexdigest() == expected_sha
        path.write_bytes(payload)

    class Blob:
        def __init__(self, key):
            self.key = key

        def upload_from_string(self, body, **kwargs):
            assert kwargs["if_generation_match"] == 0
            catalogs[self.key] = json.loads(body)

    class Bucket:
        def get_blob(self, key):
            return None

        def blob(self, key):
            return Blob(key)

    class Client:
        def bucket(self, bucket):
            assert bucket == "staging"
            return Bucket()

    monkeypatch.setattr(current_stage, "download", download)
    monkeypatch.setattr("google.cloud.storage.Client", Client)
    monkeypatch.setattr(current_stage, "copy_verified", lambda *args: copies.append(args[1:]))
    monkeypatch.setattr(
        current_stage, "put_file", lambda client, path, uri: puts.update({uri: path.read_bytes()})
    )
    result = current_stage.stage_cloud("gs://results", source, review, "gs://staging", "1" * 40)
    assert downloads[0] == (
        "gs://results/_releases/v20261111.json",
        hashlib.sha256(review.read_bytes()).hexdigest(),
    )
    assert len(downloads) == 2  # The billion-byte asset is never downloaded.
    assert copies == [
        ("gs://results/" + data_name, "gs://staging/" + data_name, source_doc["files"][data_name])
    ]
    approved = json.loads(puts["gs://staging/" + name])
    assert approved["assets"] == document["assets"]
    assert approved["fri:approved_source_sha256"] == receipt["sourceManifestSha256"]
    assert set(catalogs) == {
        "future-risk-index/catalog.json",
        "future-risk-index/fri/catalog.json",
        "future-risk-index/fri/tracts/catalog.json",
    }
    assert all(uri.startswith("gs://staging/future-risk-index/") for uri in puts)
    assert result["publicReviewSha256"] == hashlib.sha256(review.read_bytes()).hexdigest()
    assert result["liveReleaseActivated"] is False


def test_parent_catalogs_match_pinned_portolan_schema():
    import jsonschema

    from fri_pipeline.snapshot import ROOT

    schema = json.loads((ROOT / "pipeline/reference/portolan-v0.2.0.schema.json").read_bytes())
    catalogs = parent_catalogs([{"id": "future-risk-index/fri/tracts/v20261111"}])
    for catalog in catalogs.values():
        jsonschema.validate(catalog, schema)
