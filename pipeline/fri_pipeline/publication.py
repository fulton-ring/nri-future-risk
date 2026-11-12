"""Publisher handoff and verified activation. This does not mutate the shared catalog."""

import argparse
import gzip
import json
import math
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import Compression

from .candidate import verify_candidate, write_json
from .snapshot import CONTRACT, sha256
from .storage import upload


def validate_receipt(receipt: dict, candidate: dict, candidate_sha: str, bucket: str) -> None:
    if (
        receipt.get("schemaVersion") != 1
        or receipt.get("releaseId") != candidate["id"]
        or receipt.get("candidateSha256") != candidate_sha
        or receipt.get("sourceSha256") != candidate["artifacts"]["counties.geojson"]["sha256"]
        or receipt.get("countyCount") != candidate["countyCount"]
        or receipt.get("collection") != "future-risk-index"
        or receipt.get("sourceLayer") != "counties"
        or receipt.get("featureIdProperty") != "county_id"
    ):
        raise ValueError("Receipt does not match the approved candidate")
    if set(receipt.get("assets", {})) != {"counties.json", "counties.pmtiles", "provenance.json"}:
        raise ValueError("Receipt requires tiles, attribute table, and provenance")
    for spec in receipt["assets"].values():
        parsed = urlparse(spec["url"])
        if (
            parsed.scheme != "https"
            or parsed.netloc != "storage.googleapis.com"
            or not parsed.path.startswith(f"/{bucket}/")
            or parsed.query
            or parsed.fragment
            or "/../" in parsed.path
            or not re.fullmatch(r"[a-f0-9]{64}", spec["sha256"])
        ):
            raise ValueError("Asset URL must be a permanent HTTPS URL in the published bucket")
    for name in ("counties.json", "provenance.json"):
        if receipt["assets"][name]["sha256"] != candidate["artifacts"][name]["sha256"]:
            raise ValueError("Publisher changed the approved attribute table or provenance")


def verify_tiles(path: Path, attributes: dict) -> None:
    expected = {
        c["id"]: {
            key: value
            for key, value in zip(attributes["columns"], c["values"], strict=True)
            if value is not None
        }
        for c in attributes["counties"]
    }
    seen = set()
    with path.open("rb") as handle:
        source = MmapSource(handle)
        reader = Reader(source)
        header, metadata = reader.header(), reader.metadata()
        if metadata.get("vector_layers", [{}])[0].get("id") != "counties":
            raise ValueError("PMTiles source layer must be counties")
        for _, data in all_tiles(source):
            if header["tile_compression"] == Compression.GZIP:
                data = gzip.decompress(data)
            elif header["tile_compression"] != Compression.NONE:
                raise ValueError("Unsupported PMTiles tile compression")
            layers = mapbox_vector_tile.decode(data)
            if set(layers) != {"counties"}:
                raise ValueError("Unexpected PMTiles layers")
            for feature in layers["counties"]["features"]:
                props = feature["properties"]
                fips = props.get("fips")
                if fips not in expected or feature["id"] != int(fips):
                    raise ValueError("PMTiles county IDs do not match approved data")
                actual = {
                    k: v
                    for k, v in props.items()
                    if k.startswith(("WFIR_", "DRGT_", "EXHT_", "CFLD_", "HRCN_"))
                }
                if actual.keys() != expected[fips].keys():
                    raise ValueError(f"PMTiles properties schema mismatch: {fips}")
                for key, value in actual.items():
                    target = expected[fips][key]
                    same = (
                        math.isclose(value, target, rel_tol=1e-12, abs_tol=1e-12)
                        if isinstance(value, (int, float)) and isinstance(target, (int, float))
                        else value == target
                    )
                    if not same:
                        raise ValueError(f"PMTiles properties mismatch: {fips}/{key}")
                seen.add(fips)
    if seen != expected.keys():
        raise ValueError(f"PMTiles omits {len(expected.keys() - seen)} approved counties")


def stage(directory: Path, staging_uri: str, version: str, receipt_uri: str) -> dict:
    candidate = verify_candidate(directory, publication=True)
    provenance = json.loads((directory / "provenance.json").read_text())
    if not re.fullmatch(r"v\d{8}T\d{6}Z", version):
        raise ValueError("Publisher version must use vYYYYMMDDTHHMMSSZ")
    prefix = f"{staging_uri.rstrip('/')}/future-risk-index/county-risk/counties/{version}"
    request = {
        "schemaVersion": 1,
        "collection_slug": "future-risk-index",
        "dataset_slug": "county-risk",
        "file_slug": "counties",
        "collection_title": "Future Risk Index",
        "title": "County Future Risk Index",
        "description": "Archive-compatible county drought, wildfire and LOCA2 heat update; "
        "CONUS multipliers rebuilt, other areas and hazards carried forward. "
        "Frozen NRI v1.19 baseline, county area weighting, SSP2-4.5 and SSP5-8.5.",
        "provider": "Public Environmental Data Partners and Fulton Ring; FEMA archive",
        "archive_public_domain": False,
        "collection": "future-risk-index",
        "dataset": "county-risk",
        "file": "counties",
        "version": version,
        "releaseId": candidate["id"],
        "candidateSha256": sha256(directory / "candidate.json"),
        "sourceSha256": candidate["artifacts"]["counties.geojson"]["sha256"],
        "sourceUri": f"{prefix}/geojson/counties.geojson",
        "receiptUri": receipt_uri,
        "sourceLayer": "counties",
        "featureIdProperty": "county_id",
        "countyCount": candidate["countyCount"],
        "requiredAssets": ["counties.pmtiles", "counties.json", "provenance.json"],
        "license": "other",
        "attribution": "FEMA; maintained by Public Environmental Data Partners and Fulton Ring",
        "provenanceUri": f"{prefix}/metadata/provenance.json",
        "sourceDatasets": [
            {
                "id": "fema-2024-master",
                "title": "FEMA Future Risk Index December 2024 master",
                "url": "https://raw.githubusercontent.com/fulton-ring/nri-future-risk/"
                "c5cc0d6686832f809446fc6061a689eff71d09df/public/"
                "NRI_Future_Risk_Master_Datasheet_12052024.xlsx",
                "sha256": CONTRACT["workbookSha256"],
            },
            {
                "id": "fema-methodology",
                "title": "FEMA Future Risk Technical Documentation",
                "url": CONTRACT["methodologyUrl"],
                "sha256": CONTRACT["methodologySha256"],
            },
            *provenance["inputSnapshot"]["sources"],
        ],
    }
    upload(directory / "counties.geojson", request["sourceUri"])
    for name in ("counties.json", "provenance.json", "candidate.json", "validation.json"):
        upload(directory / name, f"{prefix}/metadata/{name}")
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "request.json"
        write_json(path, request)
        # Last object marks completion; ordinary discovery must not publish before this request.
        upload(path, f"{prefix}/metadata/fri-publication-request.json")
    return request


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    publish = sub.add_parser("stage")
    publish.add_argument("directory", type=Path)
    publish.add_argument("--staging-uri", required=True)
    publish.add_argument("--version", required=True)
    publish.add_argument("--receipt-uri", required=True)
    args = parser.parse_args()
    value = stage(args.directory, args.staging_uri, args.version, args.receipt_uri)
    print(json.dumps(value))


if __name__ == "__main__":
    main()
