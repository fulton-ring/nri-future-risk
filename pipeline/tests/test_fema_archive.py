import json

import pytest

pytest.importorskip("geopandas")

from fri_pipeline import fema_archive  # noqa: E402


class FakeBlob:
    def __init__(self, store, key):
        self.store, self.key, self.metadata = store, key, None

    @property
    def generation(self):
        return self.store[self.key]["generation"]

    def _write(self, data, if_generation_match):
        current = self.store.get(self.key)
        if (current["generation"] if current else 0) != if_generation_match:
            raise AssertionError(f"precondition failed for {self.key}")
        generation = (current["generation"] if current else 0) + 1
        self.store[self.key] = {"data": data, "metadata": self.metadata, "generation": generation}

    def upload_from_filename(self, path, if_generation_match):
        self._write(open(path, "rb").read(), if_generation_match)

    def upload_from_string(self, body, content_type, if_generation_match):
        self._write(body.encode(), if_generation_match)

    def download_as_bytes(self, if_generation_match):
        assert self.generation == if_generation_match
        return self.store[self.key]["data"]


class FakeBucket:
    def __init__(self):
        self.store = {}

    def blob(self, key):
        return FakeBlob(self.store, key)

    def get_blob(self, key):
        if key not in self.store:
            return None
        blob = FakeBlob(self.store, key)
        blob.metadata = self.store[key]["metadata"]
        return blob


class FakeClient:
    def __init__(self):
        self.bucket_ = FakeBucket()

    def bucket(self, name):
        assert name == "results"
        return self.bucket_


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    output = tmp_path_factory.mktemp("archive") / "build"
    return output, fema_archive.build(output)


def test_archive_version_matches_other_versions(built):
    import geopandas as gpd

    output, result = built
    folder = fema_archive.version_folder(output)
    collection = json.loads((folder / "collection.json").read_text())
    assert collection["id"] == "future-risk-index/fri/counties/v20241205T000000Z"
    assert collection["fri:publication_status"] == "archive"
    assert collection["providers"][0]["name"] == "FEMA"
    assert collection["hifld:feature_id_column"] == "area_id"
    names = [column["name"] for column in collection["table:columns"]]
    assert names[:2] == ["geoid", "area_id"] and "geometry" in names and "WFIR_EALR" in names
    assert {"geoparquet", "combined_nri_counties_borders.json", "counties.pmtiles"} <= set(
        collection["assets"]
    )
    frame = gpd.read_parquet(folder / "geoparquet/counties.parquet")
    assert len(frame) == result["counties"] == 3218
    assert frame["geoid"].str.fullmatch(r"\d{5}").all()


def test_archive_never_becomes_latest_version(built):
    from fri_pipeline.current_publish import merge_catalog

    output, _ = built
    incoming = json.loads((output / "future-risk-index/fri/counties/catalog.json").read_text())
    live = {
        **incoming,
        "links": [
            {
                "rel": "child",
                "href": "v20261111T211638Z/collection.json",
                "type": "application/json",
            }
        ],
    }
    merged = merge_catalog(live, incoming)
    children = {link["href"] for link in merged["links"] if link["rel"] == "child"}
    assert children == {"v20261111T211638Z/collection.json", "v20241205T000000Z/collection.json"}
    latest = [link["href"] for link in merged["links"] if link["rel"] == "latest-version"]
    assert latest == ["v20261111T211638Z/collection.json"]


def test_upload_is_create_only_and_rerunnable(built):
    output, _ = built
    client = FakeClient()
    key = "future-risk-index/fri/counties/catalog.json"
    client.bucket_.store[key] = {
        "data": json.dumps(
            {
                **json.loads((output / key).read_text()),
                "links": [
                    {
                        "rel": "child",
                        "href": "v20261111T211638Z/collection.json",
                        "type": "application/json",
                    }
                ],
            }
        ).encode(),
        "metadata": {},
        "generation": 7,
    }
    first = fema_archive.upload(output, "gs://results", client=client)
    assert first["created"] > 0 and first["catalogsMerged"] == 4
    again = fema_archive.upload(output, "gs://results", client=client)
    assert again["created"] == 0 and again["verified"] == first["created"]
    catalog = json.loads(client.bucket_.store[key]["data"])
    hrefs = {link["href"] for link in catalog["links"] if link["rel"] == "child"}
    assert "v20261111T211638Z/collection.json" in hrefs
