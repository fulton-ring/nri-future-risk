"""Portable Portolan results and reproducibility inputs for a separate collection."""

import json
import os
import shutil
from pathlib import Path

import numpy as np

from .candidate import write_json
from .snapshot import sha256

COLLECTION = "future-risk-index"
PORTOLAN = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"
FILE_EXTENSION = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
VERSION_EXTENSION = "https://stac-extensions.github.io/version/v1.2.0/schema.json"
TABLE_EXTENSION = "https://stac-extensions.github.io/table/v1.2.0/schema.json"
DESCRIPTION = (
    "County Future Risk Index reconstructed from FEMA's discontinued December 2024 archive. "
    "Maintained by Public Environmental Data Partners and Fulton Ring. "
    "Includes drought, wildfire and extreme heat under SSP2-4.5 and SSP5-8.5."
)


def asset(path: Path, relative_to: Path, title: str, media_type: str, roles=("data",)) -> dict:
    return {
        "href": os.path.relpath(path, relative_to),
        "type": media_type,
        "title": title,
        "roles": list(roles),
        "file:size": path.stat().st_size,
        "file:checksum": "1220" + sha256(path),
    }


def build_results(
    analysis_dir: Path,
    snapshot_path: Path,
    originals_path: Path,
    output: Path,
    version: str,
    loca_coordinates=None,
) -> dict:
    """Package completed results; this does not recalculate hazards or publish data."""
    import geopandas as gpd
    import pandas as pd

    from .candidate import display_assets, verify_candidate
    from .scoring import score
    from .snapshot import CONTRACT, ROOT, Snapshot, read_master

    source_manifest = analysis_dir / "analysis.json"
    analysis = source_manifest.exists()
    if not analysis:
        source_manifest = analysis_dir / "candidate.json"
        verify_candidate(analysis_dir, publication=True)
    meta = json.loads(source_manifest.read_text())
    for name, spec in meta["artifacts"].items():
        path = (analysis_dir / name).resolve()
        if not path.is_relative_to(analysis_dir.resolve()) or sha256(path) != spec["sha256"]:
            raise ValueError(f"Analysis artifact mismatch: {name}")
    if analysis and not meta["scoresGenerated"]:
        raise ValueError("Only completed analyses with scores can be packaged")
    snapshot = Snapshot(snapshot_path, analysis=bool(meta.get("analysis")))
    originals = json.loads(originals_path.read_text())
    recorded = {source["id"]: source for source in snapshot.manifest["sources"]}
    if (
        not originals.get("complete")
        or len(originals["sources"]) != len(recorded)
        or {item["sourceId"] for item in originals["sources"]} != set(recorded)
    ):
        raise ValueError("The original-source archive must be complete before cataloging results")
    for item in originals["sources"]:
        if (
            item["sourceId"] not in recorded
            or item["sha256"] != recorded[item["sourceId"]]["sha256"]
        ):
            raise ValueError("Original source inventory differs from the input snapshot")
    county_dir = output / COLLECTION / "county-risk/counties" / version
    inputs_dir = output / COLLECTION / "reproducibility/inputs" / version
    if county_dir.exists() or inputs_dir.exists():
        raise ValueError("Result versions are immutable; choose an empty version")
    for folder in (
        county_dir / "metadata",
        county_dir / "geoparquet",
        inputs_dir / "metadata",
        inputs_dir / "prepared",
        inputs_dir / "zarr",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    master = read_master()
    if analysis:
        scores = pd.read_csv(
            analysis_dir / "scores.csv", dtype={"STCOFIPS": str}, float_precision="round_trip"
        ).set_index("STCOFIPS")
    else:
        multipliers = pd.read_csv(
            analysis_dir / "multipliers.csv", dtype={"STCOFIPS": str}, float_precision="round_trip"
        ).set_index("STCOFIPS")
        scores = score(master, multipliers)
    if not scores.index.equals(master.index):
        raise ValueError("Scored county population does not match the frozen baseline")
    geojson, _, omitted = display_assets(scores, master)
    frame = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
    if len(frame) != CONTRACT["geometryCount"] or not frame.county_id.is_unique:
        raise ValueError("County geometry identity differs from the frozen contract")
    frame = frame.sort_values("county_id").reset_index(drop=True)
    parquet = county_dir / "geoparquet/counties.parquet"
    frame.to_parquet(
        parquet,
        index=False,
        compression="zstd",
        schema_version="1.1.0",
        write_covering_bbox=True,
        row_group_size=512,
    )
    restored = gpd.read_parquet(parquet)
    if not frame.equals(restored[frame.columns]):
        raise ValueError("County GeoParquet round trip changed data or geometry")
    columns = [
        {
            "name": key,
            "type": "binary"
            if key == "geometry"
            else "integer"
            if pd.api.types.is_integer_dtype(frame[key])
            else "number"
            if pd.api.types.is_numeric_dtype(frame[key])
            else "string",
            "nullable": bool(frame[key].isna().any()),
            "is_geometry": key == "geometry",
        }
        for key in frame.columns
    ]
    county_assets = {
        "geoparquet": asset(
            parquet, county_dir, "County risk GeoParquet", "application/vnd.apache.parquet"
        )
    }
    from PIL import Image, ImageDraw

    preview = frame.loc[frame.multiplier_vintage.eq("rebuilt")].geometry.simplify(0.04)
    left, bottom, right, top = preview.total_bounds
    thumbnail = county_dir / "metadata/counties.png"
    image = Image.new("RGB", (960, 600), "#f8faf9")
    draw = ImageDraw.Draw(image)
    colors = ["#2a6865", "#3d7d77", "#539185", "#6da395"]
    for index, geometry in enumerate(preview):
        polygons = [geometry] if geometry.geom_type == "Polygon" else geometry.geoms
        for polygon in polygons:
            if polygon.geom_type != "Polygon" or polygon.is_empty:
                continue

            def points(ring):
                return [
                    ((x - left) / (right - left) * 959, (top - y) / (top - bottom) * 599)
                    for x, y in ring.coords
                ]

            draw.polygon(
                points(polygon.exterior), fill=colors[index % len(colors)], outline="#f8faf9"
            )
            for ring in polygon.interiors:
                draw.polygon(points(ring), fill="#f8faf9")
    image.save(thumbnail, format="PNG", optimize=True)
    county_assets["thumbnail"] = asset(
        thumbnail, county_dir, "CONUS county coverage", "image/png", ("thumbnail",)
    )
    for path in sorted(analysis_dir.iterdir()):
        if path.is_file():
            target = county_dir / "metadata" / path.name
            shutil.copyfile(path, target)
            media = (
                "text/csv"
                if path.suffix == ".csv"
                else "text/markdown"
                if path.suffix == ".md"
                else "application/json"
            )
            county_assets[path.name.replace(".", "-")] = asset(
                target, county_dir, path.name, media, ("metadata",)
            )
    if not analysis:
        path = county_dir / "metadata/scores.csv"
        scores.to_csv(path, index_label="STCOFIPS", float_format="%.17g")
        county_assets["scores-csv"] = asset(path, county_dir, "County scores", "text/csv")
    publishable = bool(meta["publishable"]) and bool(frame.geometry.is_valid.all())
    quality = {
        "passed": bool(frame.geometry.is_valid.all()) and not bool(frame.geometry.isna().any()),
        "quality_check_passed": bool(frame.geometry.is_valid.all())
        and not bool(frame.geometry.isna().any()),
        "feature_count": len(frame),
        "invalid_geometry_count": int((~frame.geometry.is_valid).sum()),
        "null_geometry_count": int(frame.geometry.isna().sum()),
        "omittedGeometry": omitted,
        "computationValidation": json.loads((analysis_dir / "validation.json").read_text()),
        "publicationStatus": "candidate" if publishable else "analysis",
        "publishable": publishable,
    }
    write_json(county_dir / "metadata/quality_manifest.json", quality)
    write_json(
        county_dir / "metadata/data_dictionary.json",
        {
            "title": "County Future Risk Index",
            "description": DESCRIPTION,
            "publisher": "Public Environmental Data Partners and Fulton Ring",
            "columns": columns,
        },
    )
    source_assets = {}
    prepared = inputs_dir / "prepared"
    shutil.copyfile(snapshot.path, prepared / "snapshot.json")
    source_assets["prepared-snapshot"] = asset(
        prepared / "snapshot.json",
        inputs_dir,
        "Exact prepared input snapshot",
        "application/json",
        ("metadata",),
    )
    nex_coordinates = pd.read_csv(snapshot.file("nex_coordinates"))
    for name, original in snapshot.files.items():
        target = prepared / snapshot.manifest["artifacts"][name]["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        media = (
            "text/csv"
            if target.suffix == ".csv"
            else "application/json"
            if target.suffix == ".json"
            else "application/octet-stream"
        )
        source_assets[f"prepared-{name}"] = asset(
            target, inputs_dir, name.replace("_", " "), media, ("data", "source")
        )
        if name.startswith(("monthly_", "fwi_", "loca2_")) and name not in {
            "loca2_weights",
            "loca2_coordinates",
        }:
            store = inputs_dir / "zarr" / f"{name}.zarr"
            coordinates = (
                loca_coordinates
                if name.startswith("loca2_")
                else {key: nex_coordinates[key].to_numpy() for key in ("lat", "lon")}
            )
            write_array_store(original, name, store, coordinates)
            source_assets[f"zarr-{name}"] = {
                "href": os.path.relpath(store, inputs_dir) + "/",
                "title": name.replace("_", " ") + " (Zarr)",
                "type": "application/vnd.zarr",
                "roles": ["data", "source"],
                "file:size": sum(p.stat().st_size for p in store.rglob("*") if p.is_file()),
            }
    for name in (
        "NRI_Future_Risk_Master_Datasheet_12052024.xlsx",
        "combined_nri_counties_borders.json",
    ):
        target = prepared / name
        shutil.copyfile(ROOT / "public" / name, target)
        source_assets[name.split(".")[0]] = asset(
            target,
            inputs_dir,
            name,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if name.endswith("xlsx")
            else "application/geo+json",
            ("data", "source"),
        )
    if loca_coordinates is not None:
        coordinate_path = prepared / "loca2_coordinates.csv"
        if not coordinate_path.exists():
            pd.DataFrame(loca_coordinates).to_csv(coordinate_path, index=False)
        source_assets["loca2-cell-centers"] = asset(
            coordinate_path,
            inputs_dir,
            "LOCA2 source cell centers in weight-column order",
            "text/csv",
        )
    source_assets["provenance"] = asset(
        county_dir / "metadata/provenance.json",
        inputs_dir,
        "Acquisition and computation provenance",
        "application/json",
        ("metadata",),
    )
    original_sources = output / COLLECTION / "sources"
    for item in originals["sources"]:
        original = (original_sources / item["href"]).resolve()
        if not original.is_relative_to(original_sources.resolve()):
            raise ValueError("Original source path escapes this collection")
        source_assets[f"original-{item['sourceId']}"] = {
            "href": os.path.relpath(original, inputs_dir),
            "title": Path(item["href"]).name,
            "type": "application/netcdf"
            if original.suffix == ".nc"
            else "image/tiff"
            if original.suffix in {".tif", ".tiff"}
            else "application/octet-stream",
            "roles": ["data", "source"],
            "file:size": item["bytes"],
            "file:checksum": "1220" + item["sha256"],
            "fri:original_url": item["sourceUrl"],
        }
    shutil.copyfile(originals_path, inputs_dir / "metadata/originals-manifest.json")
    source_assets["originals-manifest"] = asset(
        inputs_dir / "metadata/originals-manifest.json",
        inputs_dir,
        "Original source inventory",
        "application/json",
        ("metadata",),
    )
    render_catalog(
        output,
        version,
        county_assets,
        source_assets,
        frame.total_bounds.tolist(),
        columns,
        publishable,
    )
    collection_path = county_dir / "collection.json"
    collection = json.loads(collection_path.read_text())
    collection["links"].append(
        {
            "rel": "derived_from",
            "href": f"../../../reproducibility/inputs/{version}/collection.json",
            "type": "application/json",
            "title": "Exact analysis inputs and original source datasets",
        }
    )
    collection.update(
        {
            "hifld:feature_count": len(frame),
            "hifld:native_crs": "EPSG:4326",
            "hifld:native_bbox": frame.total_bounds.tolist(),
            "hifld:quality": {
                "passed": quality["passed"],
                "manifest_href": "metadata/quality_manifest.json",
            },
        }
    )
    write_json(collection_path, collection)
    for dataset, file in (("county-risk", "counties"), ("reproducibility", "inputs")):
        write_json(
            output / COLLECTION / dataset / file / version / "metadata/source_manifest.json",
            {
                "collection_slug": COLLECTION,
                "dataset_slug": dataset,
                "file_slug": file,
                "version": version,
                "title": "County Future Risk Index"
                if dataset == "county-risk"
                else "Future Risk Index reproducibility inputs",
                "description": DESCRIPTION,
                "provider": "Public Environmental Data Partners and Fulton Ring",
                "analysisPolicy": meta.get("analysis"),
                "originalRunSha256": sha256(source_manifest),
                "snapshotSha256": sha256(snapshot.path),
                "publishable": publishable,
            },
        )
    files = {
        p.relative_to(output).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size}
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    package = {
        "collection": COLLECTION,
        "version": version,
        "analysisId": meta["id"],
        "publishable": publishable,
        "sourceRunSha256": sha256(source_manifest),
        "sourceRunManifest": source_manifest.name,
        "snapshotSha256": sha256(snapshot.path),
        "sourceCount": len(originals["sources"]),
        "featureCount": len(frame),
        "scoringPopulation": len(scores),
        "files": files,
        "originalSourceManifestSha256": sha256(originals_path),
        "geometryQuality": quality,
    }
    write_json(output / "result-manifest.json", package)
    return package


def write_array_store(source: Path, name: str, destination: Path, coordinates=None) -> None:
    import xarray as xr
    from numcodecs import Blosc

    with np.load(source, allow_pickle=False) as data:
        if "counts" in data:
            variables = {
                "counts": (("histogram_row", "cell"), data["counts"]),
                "edges": (("edge",), data["edges"]),
            }
            coords = {"cell": np.arange(data["counts"].shape[1])}
        else:
            time = "months" if "months" in data else "years"
            variables = {"values": ((time, "cell"), data["values"])}
            coords = {time: data[time], "cell": np.arange(data["values"].shape[1])}
        if coordinates:
            coords.update({key: (("cell",), value) for key, value in coordinates.items()})
        dataset = xr.Dataset(
            variables,
            coords=coords,
            attrs={
                "prepared_artifact": name,
                "source_sha256": sha256(source),
                "mask_policy": "Static all-time no-data cells remain masked; no interpolation.",
                "spatial_support": "Same cell order as the accompanying sparse county weights.",
            },
        )
        if "values" in dataset:
            dataset["values"].attrs["units"] = (
                "degC" if "_tas_" in name else "mm day-1" if "_pr_" in name else "1"
            )
            if name.startswith("fwi_"):
                dataset.attrs.update(variable="FWI_P95", ensemble="MME75", aggregation="annual")
            else:
                dataset.attrs.update(aggregation="monthly mean", source_grid_spacing_degrees=0.25)
        else:
            dataset["counts"].attrs.update(
                units="days", missing_row=dataset.sizes["histogram_row"] - 1
            )
            dataset["edges"].attrs["units"] = "degC"
            dataset.attrs.update(
                variable="tasmin",
                aggregation="histogram",
                source_grid_spacing_degrees=0.0625,
                weighting_box_width_degrees=0.25,
            )
        for key, units in (("lat", "degrees_north"), ("lon", "degrees_east")):
            if key in dataset:
                dataset[key].attrs["units"] = units
        encoding = {}
        for key, array in dataset.variables.items():
            chunks = tuple(
                min(size, 4096 if dim == "cell" else 120)
                for dim, size in zip(array.dims, array.shape, strict=True)
            )
            encoding[key] = {
                "chunks": chunks,
                "_FillValue": None,
                "compressors": Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE),
            }
        dataset.to_zarr(destination, mode="w-", zarr_format=2, consolidated=True, encoding=encoding)
        with xr.open_zarr(destination, consolidated=True) as restored:
            for key in data.files:
                np.testing.assert_array_equal(restored[key].values, data[key])


def render_catalog(
    root: Path,
    version: str,
    county_assets: dict,
    source_assets: dict,
    bbox: list,
    columns: list,
    publishable: bool,
) -> None:
    """Use relative navigation and asset links; copying the collection needs no URL rewriting."""
    root = root.resolve()

    def node(path: Path, identity: str, title: str, children: list, collection=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        links = [
            {
                "rel": "root",
                "href": os.path.relpath(root / "catalog.json", path.parent),
                "type": "application/json",
            },
            {"rel": "self", "href": path.name, "type": "application/json"},
            {"rel": "agents", "href": "AGENTS.md", "type": "text/markdown"},
            {"rel": "describedby", "href": "README.md", "type": "text/markdown"},
        ]
        if path.parent != root:
            links.append({"rel": "parent", "href": "../catalog.json", "type": "application/json"})
        links += [
            {"rel": "child", "href": href, "type": "application/json", "title": label}
            for href, label in children
        ]
        if collection is None and path.exists():
            prior = json.loads(path.read_text())
            prior_children = {
                link["href"]: link for link in prior.get("links", []) if link.get("rel") == "child"
            }
            prior_children.update(
                {link["href"]: link for link in links if link.get("rel") == "child"}
            )
            links = [link for link in links if link.get("rel") != "child"] + [
                prior_children[key] for key in sorted(prior_children)
            ]
        if collection is None and identity.endswith(
            ("/county-risk/counties", "/reproducibility/inputs")
        ):
            latest = max(link["href"] for link in links if link.get("rel") == "child")
            links.append(
                {
                    "rel": "latest-version",
                    "href": latest,
                    "type": "application/json",
                    "title": "Latest version",
                }
            )
        value = {
            "stac_version": "1.1.0",
            "stac_extensions": [PORTOLAN],
            "type": "Catalog",
            "id": identity,
            "title": title,
            "description": DESCRIPTION,
            "links": links,
        }
        if collection:
            assets, spatial = collection
            value.update(
                type="Collection",
                assets=assets,
                license="other",
                version=version,
                extent={"spatial": {"bbox": [spatial]}, "temporal": {"interval": [[None, None]]}},
                providers=[
                    {
                        "name": "Public Environmental Data Partners",
                        "url": "https://publicenvirodata.org",
                        "roles": ["producer"],
                    },
                    {
                        "name": "Fulton Ring",
                        "url": "https://fultonring.com",
                        "roles": ["producer", "processor", "host"],
                    },
                ],
            )
            value["stac_extensions"].extend([FILE_EXTENSION, VERSION_EXTENSION])
            links.append({"rel": "license", "href": "LICENSE.md", "type": "text/markdown"})
            (path.parent / "LICENSE.md").write_text(
                "# Source data rights\n\nOriginal source files retain their respective "
                "source terms. "
                "Their original URLs and attribution are recorded in provenance. "
                "Packaging does not relicense upstream material. "
                "Derived results credit FEMA, Public Environmental Data Partners, "
                "and Fulton Ring.\n"
            )
            value["fri:publication_status"] = "candidate" if publishable else "analysis"
            if identity.startswith(f"{COLLECTION}/county-risk/"):
                value["stac_extensions"].append(TABLE_EXTENSION)
                value["table:columns"] = columns
                value["hifld:feature_id_column"] = "county_id"
                value["hifld:geometry_column"] = "geometry"
                value["hifld:spatial_status"] = "spatial"
        write_json(path, value)
        for name in ("README.md", "AGENTS.md"):
            (path.parent / name).write_text(
                f"# {title}\n\n{DESCRIPTION}\n\n"
                f"Read {path.name} for versioned assets and provenance.\n"
            )

    node(
        root / "catalog.json",
        "future-risk-index-results",
        "Future Risk Index results",
        [(f"{COLLECTION}/catalog.json", "Future Risk Index")],
    )
    node(
        root / COLLECTION / "catalog.json",
        COLLECTION,
        "Future Risk Index",
        [
            ("county-risk/catalog.json", "County risk"),
            ("reproducibility/catalog.json", "Reproducibility inputs"),
        ],
    )
    for dataset, file, title, assets, spatial in [
        ("county-risk", "counties", "County Future Risk Index", county_assets, bbox),
        (
            "reproducibility",
            "inputs",
            "Inputs for reproducing the Future Risk Index",
            source_assets,
            [-180, -90, 180, 90],
        ),
    ]:
        base = root / COLLECTION / dataset
        node(
            base / "catalog.json",
            f"{COLLECTION}/{dataset}",
            title,
            [(f"{file}/catalog.json", title)],
        )
        node(
            base / file / "catalog.json",
            f"{COLLECTION}/{dataset}/{file}",
            title,
            [(f"{version}/collection.json", f"{title} — {version}")],
        )
        node(
            base / file / version / "collection.json",
            f"{COLLECTION}/{dataset}/{file}/{version}",
            title,
            [],
            (assets, spatial),
        )
