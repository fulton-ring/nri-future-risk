"""Immutable review artifacts and deterministic verification; no publication side effects."""

import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from hamilton import driver

from .scoring import FIELDS, SCENARIOS, SUPPORTED, reproduce_archive, score
from .snapshot import CONTRACT, EXCLUDED, ROOT, read_master, sha256


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def validate_id(release_id: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", release_id):
        raise ValueError("Release ID must be a lowercase slug, 3–63 characters")


def build_candidate(
    output: Path, release_id: str, *, replay: bool = False, snapshot: str = "", code_revision: str
) -> dict:
    from . import flow

    validate_id(release_id)
    if not re.fullmatch(r"[a-f0-9]{40}", code_revision):
        raise ValueError("A full source commit SHA is required")
    graph = driver.Builder().with_modules(flow).build()
    return graph.execute(
        ["candidate"],
        inputs={
            "snapshot_path": snapshot,
            "replay": replay,
            "output_dir": str(output),
            "release_id": release_id,
            "code_revision": code_revision,
        },
    )["candidate"]


def display_assets(scored: pd.DataFrame, master: pd.DataFrame) -> tuple[dict, dict, list]:
    path = ROOT / "public/combined_nri_counties_borders.json"
    if sha256(path) != CONTRACT["geometrySha256"]:
        raise ValueError("Frozen geometry hash mismatch")
    source = json.loads(path.read_text())
    features, counties = [], []
    for feature in source["features"]:
        original = feature["properties"]
        fips = original["STCOFIPS"]
        if fips not in scored.index:
            raise ValueError(f"Unknown geometry county {fips}")
        values = {
            key: value
            for key, value in original.items()
            if key.startswith(("DRGT_", "WFIR_", "EXHT_", "CFLD_", "HRCN_"))
        }
        for variant in SUPPORTED:
            for scenario in SCENARIOS:
                for field in ("HM", "PALT", "PRISKV", *FIELDS):
                    key = f"{variant}_{scenario}_{field}"
                    value = scored.at[fips, key]
                    values[key] = None if pd.isna(value) else value
        points = []

        def collect(coordinates, points=points):
            if isinstance(coordinates[0], (int, float)):
                points.append(coordinates)
            else:
                for child in coordinates:
                    collect(child)

        collect(feature["geometry"]["coordinates"])
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if max(xs) - min(xs) > 180:
            xs = [x + 360 if x < 0 else x for x in xs]
        bounds = [min(xs), min(ys), max(xs), max(ys)]
        props = {
            "county_id": int(fips),
            "fips": fips,
            "name": original["COUNTY"],
            "state": original["STATEABBRV"],
            **values,
        }
        props["multiplier_vintage"] = (
            "FEMA archive" if master.at[fips, "STATEABBRV"] in EXCLUDED else "rebuilt"
        )
        features.append({"type": "Feature", "properties": props, "geometry": feature["geometry"]})
        counties.append(
            {
                "id": fips,
                "name": props["name"],
                "state": props["state"],
                "bounds": bounds,
                "values": values,
            }
        )
    if len(features) != CONTRACT["geometryCount"]:
        raise ValueError("Geometry count mismatch")
    counties.sort(key=lambda c: (c["state"], c["name"]))
    columns = list(counties[0]["values"])
    if any(set(c["values"]) != set(columns) for c in counties):
        raise ValueError("Inconsistent county attribute schema")
    payload = {
        "columns": columns,
        "counties": [
            {**county, "values": [county["values"][key] for key in columns]} for county in counties
        ],
    }
    omitted = sorted(set(master.index) - {c["id"] for c in counties})
    return {"type": "FeatureCollection", "features": features}, payload, omitted


def change_summary(master: pd.DataFrame, computed: pd.DataFrame) -> list:
    rows = []
    for variant in SUPPORTED:
        for scenario in SCENARIOS:
            prefix = f"{variant}_{scenario}"
            delta = computed[f"{prefix}_HM"] - master[f"{prefix}_HM"]
            from .scoring import names

            changed = computed[f"{prefix}_PALR"].ne(names(master[f"{prefix}_PALR"]))
            risk_changed = computed[f"{prefix}_PRISKR"].ne(names(master[f"{prefix}_PRISKR"]))
            rows.append(
                {
                    "variant": variant,
                    "scenario": scenario,
                    "changedMultipliers": int((delta.abs() > 1e-10).sum()),
                    "changedLossRatings": int(changed.fillna(False).sum()),
                    "changedRiskRatings": int(risk_changed.fillna(False).sum()),
                    "maxAbsoluteMultiplierChange": float(delta.abs().max()),
                    "medianMultiplierChange": float(delta.median()),
                }
            )
    return rows


def report(candidate: dict, changes: list) -> str:
    lines = [
        f"# County risk candidate: {candidate['id']}",
        "",
        "ARCHIVE REPLAY — cannot publish."
        if not candidate["publishable"]
        else "Candidate for review. Merging approves this exact source for publication.",
        "",
        "Changes below are relative to FEMA’s December 2024 archive, not the previous update.",
        "",
        "| Variant | Scenario | Changed multipliers | Changed loss ratings | Max HM Δ |",
        "|---|---|---:|---:|---:|",
    ]
    for row in changes:
        lines.append(
            f"| {row['variant']} | {row['scenario']} | {row['changedMultipliers']} | "
            f"{row['changedLossRatings']} | {row['maxAbsoluteMultiplierChange']:.6g} |"
        )
    lines += [
        "",
        "Archive regression: **310,176 comparisons, zero mismatches**.",
        "",
        f"Scoring population: {candidate['population']}; mapped counties: "
        f"{candidate['countyCount']}; missing geometries: {len(candidate['omittedGeometry'])}.",
        "",
        "## Scope and interpretation",
        "",
        "- Rebuilt multipliers: CONUS drought, wildfire, LOCA2 heat (95th/99th).",
        "- Other areas retain archived multipliers. National ranks use all 3,231 counties "
        "and can change outside CONUS as CONUS risk changes.",
        "- Coastal flooding, hurricanes, and NEX heat remain archived.",
        "- County projections use area weighting; no tract product is published.",
        "- LOCA2 weights use 0.25° boxes around source centers; no 6 km support claim.",
        "- SSP2-4.5 and SSP5-8.5; one model/run, no uncertainty ensemble.",
        "- Frozen NRI v1.19; no future demographics or baseline replacement.",
        "- Missing/non-finite inputs and multipliers below one block publication.",
        "",
        "See provenance.json, validation.json and changes.json for machine-readable evidence.",
        "Map activation waits for verified hosted assets from the publisher.",
        "",
    ]
    return "\n".join(lines)


def write_candidate(
    output: Path,
    release_id: str,
    code_revision: str,
    replay: bool,
    master: pd.DataFrame,
    multipliers: pd.DataFrame,
    computed: pd.DataFrame,
    archive_validation: dict,
    snapshot_manifest: dict | None,
    parameters: dict,
) -> dict:
    validate_id(release_id)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Candidate output directory must be empty")
    geojson, attributes, omitted = display_assets(computed, master)
    changes = change_summary(master, computed)
    meta = {
        "schemaVersion": 1,
        "id": release_id,
        "publishable": not replay,
        "codeRevision": code_revision,
        "methodology": CONTRACT["id"],
        "collection": "future-risk-index",
        "dataset": "county-risk",
        "file": "counties",
        "population": len(master),
        "countyCount": len(attributes["counties"]),
        "omittedGeometry": omitted,
        "archiveRegression": {"comparisons": archive_validation["comparisons"], "mismatches": 0},
        "sourceLayer": "counties",
        "featureIdProperty": "county_id",
    }
    write_json(output / "counties.geojson", geojson)
    write_json(output / "counties.json", attributes)
    multipliers.to_csv(output / "multipliers.csv", index_label="STCOFIPS", float_format="%.17g")
    write_json(
        output / "validation.json",
        {"archive": archive_validation, "contract": CONTRACT, "omittedGeometry": omitted},
    )
    write_json(
        output / "provenance.json",
        {
            "contract": CONTRACT,
            "codeRevision": code_revision,
            "inputSnapshot": snapshot_manifest,
            "parameters": parameters,
            "workerImage": os.environ.get("FRI_WORKER_IMAGE", "local"),
            "replay": replay,
        },
    )
    write_json(output / "changes.json", changes)
    (output / "report.md").write_text(report(meta, changes))
    meta["artifacts"] = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(output.iterdir())
    }
    write_json(output / "candidate.json", meta)
    return meta


def verify_candidate(directory: Path, *, publication: bool = False) -> dict:
    meta = json.loads((directory / "candidate.json").read_text())
    validate_id(meta["id"])
    if not re.fullmatch(r"[a-f0-9]{40}", meta["codeRevision"]):
        raise ValueError("Candidate source revision must be a full commit SHA")
    if publication and not meta["publishable"]:
        raise ValueError("Archive replay is not publishable")
    if (
        meta["schemaVersion"] != 1
        or meta["methodology"] != CONTRACT["id"]
        or meta["collection"] != "future-risk-index"
        or meta["dataset"] != "county-risk"
        or meta["file"] != "counties"
        or meta["sourceLayer"] != "counties"
        or meta["featureIdProperty"] != "county_id"
    ):
        raise ValueError("Candidate contract mismatch")
    expected = {
        "counties.geojson",
        "counties.json",
        "multipliers.csv",
        "validation.json",
        "provenance.json",
        "changes.json",
        "report.md",
    }
    if set(meta["artifacts"]) != expected:
        raise ValueError("Candidate artifact inventory mismatch")
    for name, spec in meta["artifacts"].items():
        path = directory / name
        if (
            not path.is_file()
            or sha256(path) != spec["sha256"]
            or path.stat().st_size != spec["bytes"]
        ):
            raise ValueError(f"Candidate artifact hash mismatch: {name}")
    master = read_master()
    archived = reproduce_archive(master)
    values = pd.read_csv(
        directory / "multipliers.csv", dtype={"STCOFIPS": str}, float_precision="round_trip"
    ).set_index("STCOFIPS")
    if not values.index.equals(master.index):
        raise ValueError("Candidate population mismatch")
    from .flow import merged_multipliers

    columns = [f"{v}_{s}_HM" for v in SUPPORTED for s in SCENARIOS]
    expected_values = merged_multipliers(
        master, values.loc[~master.STATEABBRV.isin(EXCLUDED), columns]
    )
    if not values.columns.equals(expected_values.columns) or not np.array_equal(
        values.to_numpy(dtype=float), expected_values.to_numpy(dtype=float)
    ):
        raise ValueError("Candidate changed archived multipliers outside supported coverage")
    computed = score(master, values)
    geojson, attributes, omitted = display_assets(computed, master)
    if (
        meta["population"] != len(master)
        or meta["countyCount"] != len(attributes["counties"])
        or meta["omittedGeometry"] != omitted
        or meta["archiveRegression"] != {"comparisons": archived["comparisons"], "mismatches": 0}
    ):
        raise ValueError("Candidate validation metadata mismatch")
    for name, expected_data in [
        ("counties.geojson", geojson),
        ("counties.json", attributes),
        ("changes.json", change_summary(master, computed)),
    ]:
        if json.loads((directory / name).read_text()) != expected_data:
            raise ValueError(f"Candidate scored data mismatch: {name}")
    provenance = json.loads((directory / "provenance.json").read_text())
    validation = json.loads((directory / "validation.json").read_text())
    if validation != {"archive": archived, "contract": CONTRACT, "omittedGeometry": omitted}:
        raise ValueError("Candidate validation artifact mismatch")
    if (
        provenance["contract"] != CONTRACT
        or provenance["codeRevision"] != meta["codeRevision"]
        or provenance["replay"] == meta["publishable"]
    ):
        raise ValueError("Candidate provenance mismatch")
    if publication and not provenance.get("inputSnapshot"):
        raise ValueError("Publication requires input snapshot provenance")
    if publication:
        parameters = provenance["parameters"]
        elasticity = parameters.get("wildfireElasticity")
        if (
            not isinstance(elasticity, (int, float))
            or not math.isfinite(elasticity)
            or parameters.get("wildfireEnsemble") != "MME75"
            or parameters.get("wildfireVariable") != "FWI_P95"
        ):
            raise ValueError("Publication requires the fitted wildfire coefficient and method")
        snapshot = provenance["inputSnapshot"]
        if (
            snapshot.get("methodology") != CONTRACT["id"]
            or snapshot.get("rebuildCommit") != CONTRACT["rebuildCommit"]
            or not re.fullmatch(r"[a-f0-9]{64}", snapshot.get("manifestSha256", ""))
        ):
            raise ValueError("Publication snapshot does not match the frozen methodology")
    if (directory / "report.md").read_text() != report(meta, change_summary(master, computed)):
        raise ValueError("Candidate report mismatch")
    return meta
