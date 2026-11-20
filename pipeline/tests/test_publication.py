import pytest

from fri_pipeline.publication import validate_receipt


def receipt():
    meta = {
        "id": "fri-test",
        "countyCount": 3218,
        "collection": "future-risk-index",
        "artifacts": {
            "counties.geojson": {"sha256": "a" * 64},
            "counties.json": {"sha256": "b" * 64},
            "provenance.json": {"sha256": "c" * 64},
        },
    }
    value = {
        "schemaVersion": 1,
        "releaseId": "fri-test",
        "candidateSha256": "d" * 64,
        "sourceSha256": "a" * 64,
        "collection": "future-risk-index",
        "countyCount": 3218,
        "sourceLayer": "counties",
        "featureIdProperty": "county_id",
        "assets": {
            name: {"url": f"https://storage.googleapis.com/published/{name}", "sha256": sha}
            for name, sha in [
                ("counties.pmtiles", "e" * 64),
                ("counties.json", "b" * 64),
                ("provenance.json", "c" * 64),
            ]
        },
    }
    return value, meta


def test_receipt_binds_publication_to_exact_approved_candidate():
    value, meta = receipt()
    validate_receipt(value, meta, "d" * 64, "published")
    value["sourceSha256"] = "f" * 64
    with pytest.raises(ValueError, match="approved"):
        validate_receipt(value, meta, "d" * 64, "published")


@pytest.mark.parametrize(
    "url",
    [
        "http://storage.googleapis.com/published/a",
        "https://evil.test/a",
        "https://storage.googleapis.com/other/a",
        "https://storage.googleapis.com/published/a?token=secret",
    ],
)
def test_receipt_rejects_untrusted_or_expiring_asset_urls(url):
    value, meta = receipt()
    value["assets"]["counties.pmtiles"]["url"] = url
    with pytest.raises(ValueError, match="URL"):
        validate_receipt(value, meta, "d" * 64, "published")


def test_receipt_rejects_changed_attribute_table():
    value, meta = receipt()
    value["assets"]["counties.json"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="attribute"):
        validate_receipt(value, meta, "d" * 64, "published")


def test_receipt_rejects_unexpected_layer_or_feature_ids():
    value, meta = receipt()
    value["featureIdProperty"] = "row_number"
    with pytest.raises(ValueError, match="approved"):
        validate_receipt(value, meta, "d" * 64, "published")


def test_pmtiles_actual_properties_match_candidate(tmp_path):
    import mapbox_vector_tile
    from pmtiles.tile import Compression, TileType
    from pmtiles.writer import Writer

    from fri_pipeline.publication import verify_tiles

    properties = {"fips": "01001", "WFIR_MID_LOWER_HM": 1.25, "DRGT_MID_LOWER_PALR": "Very Low"}
    tile = mapbox_vector_tile.encode(
        {
            "name": "counties",
            "features": [
                {
                    "id": 1001,
                    "geometry": {"type": "Point", "coordinates": [10, 10]},
                    "properties": properties,
                }
            ],
        }
    )
    path = tmp_path / "counties.pmtiles"
    with path.open("wb") as handle:
        writer = Writer(handle)
        writer.write_tile(0, tile)
        writer.finalize(
            {"tile_compression": Compression.NONE, "tile_type": TileType.MVT},
            {"vector_layers": [{"id": "counties"}]},
        )
    attributes = {
        "columns": ["WFIR_MID_LOWER_HM", "DRGT_MID_LOWER_PALR"],
        "counties": [{"id": "01001", "values": [1.25, "Very Low"]}],
    }
    verify_tiles(path, attributes)
    attributes["counties"][0]["values"][0] = 99
    with pytest.raises(ValueError, match="properties"):
        verify_tiles(path, attributes)
