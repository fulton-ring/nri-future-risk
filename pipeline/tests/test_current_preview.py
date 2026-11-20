import importlib.util
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

spec = importlib.util.spec_from_file_location(
    "current_preview", Path(__file__).parents[2] / "scripts/build_current_preview_assets.py"
)
preview = importlib.util.module_from_spec(spec)


def test_tract_index_does_not_embed_all_scenarios_and_profile_roundtrips(tmp_path):
    spec.loader.exec_module(preview)
    frame = gpd.GeoDataFrame(
        {
            "geoid": ["09110000100", "09110000200", "09120000100"],
            "name": ["Tract 1", "Tract 2", "Tract 1"],
            "state": ["CT"] * 3,
            "multiplier_vintage": ["rebuilt"] * 3,
            "DRGT_EALT": [100.0, None, 200.0],
            "DRGT_EALR": ["Very Low", None, "Relatively Low"],
            "DRGT_MID_LOWER_HM": [2.0, 3.0, 4.0],
        },
        geometry=[box(-73, 41, -72, 42)] * 3,
        crs=4326,
    )
    result = preview.write_attributes(frame, tmp_path, "tracts")
    index = json.loads((tmp_path / "counties.json").read_text())
    assert index["columns"] == []
    assert all(area["values"] == [] for area in index["counties"])
    assert len(result["profileAssets"]["hashes"]) == 2
    shard = json.loads((tmp_path / "profiles/09110.json").read_text())
    assert [area["id"] for area in shard["counties"]] == ["09110000100", "09110000200"]
    assert shard["counties"][1]["values"][shard["columns"].index("DRGT_EALT")] is None
    column = json.loads((tmp_path / "fields/DRGT_EALR.json").read_text())
    assert column == ["Very Low", None, "Relatively Low"]


def test_tract_pmtiles_retains_exact_geoid_and_scores(tmp_path):
    import mapbox_vector_tile
    import pytest
    from pmtiles.tile import Compression, TileType
    from pmtiles.writer import Writer

    from fri_pipeline.publication import verify_tiles

    path = tmp_path / "tracts.pmtiles"
    data = mapbox_vector_tile.encode(
        {
            "name": "tracts",
            "features": [
                {
                    "id": 9110000100,
                    "geometry": {"type": "Point", "coordinates": [10, 10]},
                    "properties": {"fips": "09110000100", "WFIR_MID_LOWER_HM": 1.23456789},
                }
            ],
        }
    )
    with path.open("wb") as stream:
        writer = Writer(stream)
        writer.write_tile(0, data)
        writer.finalize(
            {"tile_compression": Compression.NONE, "tile_type": TileType.MVT},
            {"vector_layers": [{"id": "tracts"}]},
        )
    attributes = {
        "columns": ["WFIR_MID_LOWER_HM"],
        "counties": [{"id": "09110000100", "values": [1.23456789]}],
    }
    verify_tiles(path, attributes, source_layer="tracts")
    with pytest.raises(ValueError, match="layer"):
        verify_tiles(path, attributes)
