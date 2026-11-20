"""Read-only county heat diagnostics; published multipliers and scores are unchanged."""

import argparse
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import heat
from .candidate import write_json
from .snapshot import Snapshot, sha256
from .storage import download, fetch_snapshot, upload


def explain_heat(snapshot: Snapshot) -> dict:
    _, ids = snapshot.loca2_county_weights()
    edges, history = snapshot.loca2_histogram("historical", "historical")
    floor_bin = int(np.searchsorted(edges, heat.FLOOR_C, side="right") - 1)
    floor_pos = floor_bin + (heat.FLOOR_C - edges[floor_bin]) / (
        edges[floor_bin + 1] - edges[floor_bin]
    )
    positions = {name: heat.percentile_position(history, p) for name, p in heat.PERCENTILES.items()}
    past = {
        name: heat.county_mean(heat.days_above_pos(history, position), snapshot)
        for name, position in positions.items()
    }
    counties = {fips: {} for fips in ids}
    for warming, ssp in snapshot.SSP.items():
        for period in ("MID", "LATE"):
            _, counts = snapshot.loca2_histogram(ssp, period)
            for name, position in positions.items():
                future = heat.county_mean(
                    heat.days_above_pos(counts, np.maximum(position, floor_pos)), snapshot
                )
                ratio = future / past[name]
                if not np.isfinite(ratio).all() or (ratio < 0).any():
                    raise ValueError("Heat explanation requires complete finite county ratios")
                key = f"EXHT_{name}_{period}_{warming}"
                for i, fips in enumerate(ids):
                    counties[fips][key] = {
                        "historicalDaysPerYear": float(past[name][i] / 30),
                        "futureDaysPerYear": float(future[i] / 30),
                        "rawMultiplier": float(ratio[i]),
                        "appliedMultiplier": float(max(1.0, ratio[i])),
                    }
    return {
        "schemaVersion": 1,
        "methodology": snapshot.manifest["methodology"],
        "snapshotSha256": sha256(snapshot.path),
        "temperatureFloorC": round(heat.FLOOR_C, 2),
        "historicalPeriod": "1976–2005",
        "futurePeriods": {"MID": "2036–2065", "LATE": "2070–2099"},
        "historicalDefinition": "Days above the historical percentile alone.",
        "futureDefinition": (
            "Days above both the historical percentile and 23.07 C minimum temperature."
        ),
        "aggregation": "County area-weighted event days; each 30-year total divided by 30.",
        "formula": "applied multiplier = max(1, future days / historical days)",
        "counties": counties,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-uri", required=True)
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--multipliers-uri", required=True)
    parser.add_argument("--multipliers-sha256", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="fri-explanation-") as directory:
        root = Path(directory)
        path = fetch_snapshot(args.snapshot_uri, args.snapshot_sha256, root / "snapshot")
        snapshot = Snapshot(path)
        result = explain_heat(snapshot)
        expected_path = root / "multipliers.csv"
        download(args.multipliers_uri, expected_path, args.multipliers_sha256)
        expected = pd.read_csv(expected_path, dtype={"STCOFIPS": str}).set_index("STCOFIPS")
        actual = pd.DataFrame.from_dict(
            {
                fips: {f"{key}_HM": item["appliedMultiplier"] for key, item in details.items()}
                for fips, details in result["counties"].items()
            },
            orient="index",
        )
        np.testing.assert_allclose(
            actual, expected.loc[actual.index, actual.columns], rtol=1e-12, atol=1e-12
        )
        result.update(
            publishedMultipliersSha256=args.multipliers_sha256,
            codeRevision=os.environ.get("FRI_CODE_REVISION", "local"),
            workerImage=os.environ.get("FRI_WORKER_IMAGE", "local"),
            verifiedCountyScenarios=int(actual.size),
        )
        output = root / "calculations.json"
        write_json(output, result)
        upload(output, args.output_uri)
        print(
            json.dumps({"uri": args.output_uri, "sha256": sha256(output), "verified": actual.size})
        )


if __name__ == "__main__":
    main()
