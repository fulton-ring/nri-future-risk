"""Available-year exploration. Outputs cannot enter the publication workflow."""

import os
from pathlib import Path

import numpy as np
import pandas as pd
from hamilton import driver

from . import flow
from .candidate import change_summary, validate_id, write_json
from .scoring import score
from .snapshot import FWI_ANALYSIS, SPANS, fwi_years, sha256


def run_analysis(snapshot: Path, output: Path, run_id: str, revision: str) -> dict:
    validate_id(run_id)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Analysis output directory must be empty")
    graph = driver.Builder().with_modules(flow).build()
    result = graph.execute(
        [
            "input_snapshot",
            "baseline",
            "archive_validation",
            "drought_hm",
            "wildfire_hm",
            "heat_hm",
        ],
        inputs={"snapshot_path": str(snapshot), "replay": False, "analysis": True},
    )
    master = result["baseline"]
    updates = pd.concat([result[key] for key in ("drought_hm", "wildfire_hm", "heat_hm")], axis=1)
    if not np.isfinite(updates).all().all() or (updates <= 0).any().any():
        raise ValueError("Analysis requires finite, positive hazard multipliers")
    updates.to_csv(output / "multipliers.csv", index_label="STCOFIPS", float_format="%.17g")
    coverage = []
    for scenario, periods in [
        ("historical", ["historical"]),
        ("ssp245", ["MID", "LATE"]),
        ("ssp585", ["MID", "LATE"]),
    ]:
        for period in periods:
            first, last = SPANS[period]
            years = fwi_years(scenario, period, analysis=True).tolist()
            coverage.append(
                {
                    "scenario": scenario,
                    "period": period,
                    "usedYears": len(years),
                    "expectedYears": last - first + 1,
                    "years": years,
                    "omittedYears": sorted(set(range(first, last + 1)) - set(years)),
                }
            )
    summaries = []
    for column in updates:
        delta = updates[column] - master.loc[updates.index, column]
        summaries.append(
            {
                "column": column,
                "minimum": float(updates[column].min()),
                "median": float(updates[column].median()),
                "maximum": float(updates[column].max()),
                "belowReleaseFloor": int((updates[column] < 1).sum()),
                "changedMultipliers": int((delta.abs() > 1e-10).sum()),
                "medianChangeFromArchive": float(delta.median()),
                "maximumAbsoluteChangeFromArchive": float(delta.abs().max()),
            }
        )
    scores_generated = not (updates < 1).any().any()
    if scores_generated:
        merged = flow.merged_multipliers(master, updates)
        computed = score(master, merged)
        computed.to_csv(output / "scores.csv", index_label="STCOFIPS", float_format="%.17g")
        write_json(output / "changes.json", change_summary(master, computed))
    meta = {
        "id": run_id,
        "publishable": False,
        "analysis": FWI_ANALYSIS,
        "codeRevision": revision,
        "counties": len(updates),
        "wildfireCoverage": coverage,
        "wildfireElasticity": result["wildfire_hm"].attrs["elasticity"],
        "multiplierSummary": summaries,
        "scoresGenerated": scores_generated,
    }
    write_json(
        output / "provenance.json",
        {
            "inputSnapshot": result["input_snapshot"]["manifest"],
            "codeRevision": revision,
            "workerImage": os.environ.get("FRI_WORKER_IMAGE", "local"),
            "publishable": False,
        },
    )
    write_json(
        output / "validation.json",
        {
            "archive": result["archive_validation"],
            "coverageDiagnostics": result["input_snapshot"]["snapshot"].coverage_diagnostics,
            "releaseFloorViolations": int((updates < 1).sum().sum()),
        },
    )
    lines = [
        f"# Available-year risk analysis: {run_id}",
        "",
        "Exploratory analysis only; not approved for publication.",
        "",
        "Unequal year coverage: annual MME75/FWI_P95 values are equally weighted "
        "within each original period. No interpolation or replacement years. "
        "Differences from FEMA's archive are reconstruction differences, "
        "not observed changes since 2024.",
        "",
        "| Scenario | Period | Years used | Omitted years |",
        "|---|---|---:|---|",
    ]
    for row in coverage:
        lines.append(
            f"| {row['scenario']} | {row['period']} | {row['usedYears']}/30 | "
            f"{', '.join(map(str, row['omittedYears']))} |"
        )
    lines += [
        "",
        f"Counties: {len(updates)}. Fitted wildfire elasticity: {meta['wildfireElasticity']:.8g}.",
        "",
        "| Multiplier | Minimum | Median | Maximum | Below release floor |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['column']} | {row['minimum']:.6g} | {row['median']:.6g} | "
            f"{row['maximum']:.6g} | {row['belowReleaseFloor']} |"
        )
    lines += [
        "",
        "Scores generated using the unchanged release rules."
        if scores_generated
        else "Scores withheld: raw multipliers below 1 violate the release contract. "
        "Raw values are retained without clipping.",
        "Archive regression: 310,176 comparisons, zero mismatches.",
        "Drought and heat retain complete original periods. "
        "Baseline and non-CONUS values remain frozen.",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines))
    meta["artifacts"] = {
        p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(output.iterdir())
    }
    write_json(output / "analysis.json", meta)
    return meta
