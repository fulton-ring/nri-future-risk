"""Hamilton DAG: verified inputs → county hazard multipliers → frozen national scoring."""

import numpy as np
import pandas as pd

from . import drought, heat, wildfire
from .scoring import SCENARIOS, SUPPORTED, VARIANTS, reproduce_archive, score
from .snapshot import EXCLUDED, Snapshot, read_master


def baseline() -> pd.DataFrame:
    return read_master()


def archive_validation(baseline: pd.DataFrame) -> dict:
    return reproduce_archive(baseline)


def input_snapshot(snapshot_path: str, replay: bool, analysis: bool = False) -> dict:
    if replay:
        if snapshot_path:
            raise ValueError("Archive replay cannot accept update inputs")
        return {"snapshot": None, "manifest": None}
    from pathlib import Path

    snapshot = Snapshot(Path(snapshot_path), analysis=analysis)
    from .snapshot import sha256

    return {
        "snapshot": snapshot,
        "manifest": {**snapshot.manifest, "manifestSha256": sha256(snapshot.path)},
    }


def drought_hm(input_snapshot: dict, baseline: pd.DataFrame, replay: bool) -> pd.DataFrame:
    if replay:
        return baseline.loc[
            ~baseline.STATEABBRV.isin(EXCLUDED), [f"DRGT_{s}_HM" for s in SCENARIOS]
        ]
    return drought.hazard_multipliers(input_snapshot["snapshot"])


def wildfire_hm(input_snapshot: dict, baseline: pd.DataFrame, replay: bool) -> pd.DataFrame:
    if replay:
        return baseline.loc[
            ~baseline.STATEABBRV.isin(EXCLUDED), [f"WFIR_{s}_HM" for s in SCENARIOS]
        ]
    return wildfire.hazard_multipliers(input_snapshot["snapshot"])


def heat_hm(input_snapshot: dict, baseline: pd.DataFrame, replay: bool) -> pd.DataFrame:
    if replay:
        return baseline.loc[
            ~baseline.STATEABBRV.isin(EXCLUDED),
            [f"{v}_{s}_HM" for v in SUPPORTED[2:] for s in SCENARIOS],
        ]
    return heat.hazard_multipliers(input_snapshot["snapshot"])


def merged_multipliers(master: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    expected = master.loc[~master.STATEABBRV.isin(EXCLUDED)].index
    if not updates.index.equals(expected):
        raise ValueError("Updates require all CONUS counties in frozen baseline order")
    supported = [f"{v}_{s}_HM" for v in SUPPORTED for s in SCENARIOS]
    if set(updates.columns) != set(supported) or not updates.columns.is_unique:
        raise ValueError("Updates require exactly the supported hazard/scenario columns")
    if not np.isfinite(updates).all().all():
        raise ValueError("Every supported county multiplier must be finite")
    if (updates < 1).any().any():
        raise ValueError("Every supported county multiplier must be >= 1; no silent clipping")
    result = master[[f"{v}_{s}_HM" for v in VARIANTS for s in SCENARIOS]].copy()
    result.loc[expected, supported] = updates[supported]
    return result


def multipliers(
    baseline: pd.DataFrame,
    drought_hm: pd.DataFrame,
    wildfire_hm: pd.DataFrame,
    heat_hm: pd.DataFrame,
) -> pd.DataFrame:
    return merged_multipliers(baseline, pd.concat([drought_hm, wildfire_hm, heat_hm], axis=1))


def scored_counties(baseline: pd.DataFrame, multipliers: pd.DataFrame) -> pd.DataFrame:
    return score(baseline, multipliers)


def candidate(
    scored_counties: pd.DataFrame,
    baseline: pd.DataFrame,
    multipliers: pd.DataFrame,
    archive_validation: dict,
    input_snapshot: dict,
    output_dir: str,
    release_id: str,
    replay: bool,
    code_revision: str,
    wildfire_hm: pd.DataFrame,
) -> dict:
    from pathlib import Path

    from .candidate import write_candidate

    return write_candidate(
        Path(output_dir),
        release_id,
        code_revision,
        replay,
        baseline,
        multipliers,
        scored_counties,
        archive_validation,
        input_snapshot["manifest"],
        {
            "wildfireElasticity": wildfire_hm.attrs.get("elasticity"),
            "wildfireEnsemble": wildfire.ENSEMBLE,
            "wildfireVariable": wildfire.VARIABLE,
        },
    )
