"""Hamilton DAG for native v1.20 counties and census tracts with CONUS projection ranks."""

import numpy as np
import pandas as pd

from . import drought, heat, wildfire
from .current_geography import GeographySnapshot
from .scoring import (
    SCENARIOS,
    SUPPORTED,
    classify,
    display_score,
    projected_rating,
    risk_score,
    thresholds,
)
from .snapshot import EXCLUDED

HM_COLUMNS = [f"{variant}_{scenario}_HM" for variant in SUPPORTED for scenario in SCENARIOS]


def complete_multipliers(baseline: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    """Keep all native national rows; unsupported non-CONUS projections remain null."""
    expected = baseline.loc[~baseline.STATEABBRV.isin(EXCLUDED)].index
    if not updates.index.equals(expected):
        raise ValueError("Updates must match the entire native CONUS geography in order")
    if not updates.columns.is_unique or set(updates.columns) != set(HM_COLUMNS):
        raise ValueError("Expected exactly 16 supported hazard/scenario multiplier columns")
    if not np.isfinite(updates).all().all() or (updates < 1).any().any():
        raise ValueError("Every supported multiplier must be finite and >= 1; no silent clipping")
    result = pd.DataFrame(np.nan, index=baseline.index, columns=HM_COLUMNS)
    result.loc[expected, HM_COLUMNS] = updates[HM_COLUMNS]
    return result


def score_geography(baseline: pd.DataFrame, multipliers: pd.DataFrame) -> tuple:
    """Use national native rating bins and rank supported CONUS projections independently."""
    if not baseline.index.equals(multipliers.index):
        raise ValueError("Scoring requires complete national baseline order")
    if set(multipliers) != set(HM_COLUMNS) or not multipliers.columns.is_unique:
        raise ValueError("Expected exactly supported multipliers")
    supported = ~baseline.STATEABBRV.isin(EXCLUDED)
    if (
        not np.isfinite(multipliers.loc[supported]).all().all()
        or (multipliers.loc[supported] < 1).any().any()
    ):
        raise ValueError("Supported multipliers must be finite and >= 1")
    if not multipliers.loc[~supported].isna().all().all():
        raise ValueError("Unsupported areas must have null future multipliers")
    bins, result, nulls = {}, {}, {}
    for variant in SUPPORTED:
        hazard = variant.split("_")[0]
        eal, risk = baseline[f"{hazard}_EALT"], baseline[f"{hazard}_RISKV"]
        eal_labels, risk_labels = baseline[f"{hazard}_EALR"], baseline[f"{hazard}_RISKR"]
        eal_edges, risk_edges = thresholds(eal, eal_labels), thresholds(risk, risk_labels)
        pooled = pd.concat([multipliers[f"{variant}_{s}_HM"] for s in SCENARIOS])
        hm_edges = pooled.quantile([0.2, 0.4, 0.6, 0.8]).to_numpy()
        bins[variant] = {
            "eal": eal_edges.tolist(),
            "risk": risk_edges.tolist(),
            "hm": hm_edges.tolist(),
        }
        for scenario in SCENARIOS:
            prefix = f"{variant}_{scenario}"
            hm = multipliers[f"{prefix}_HM"]
            projected_eal, projected_risk = eal * hm, risk * hm
            if not projected_eal.isna().equals(eal.isna() | ~supported) or not (
                projected_risk.isna().equals(risk.isna() | ~supported)
            ):
                raise ValueError("Projected baseline null mask changed")
            if (
                not np.isfinite(projected_eal.dropna()).all()
                or not np.isfinite(projected_risk.dropna()).all()
            ):
                raise ValueError("Projected baseline values overflowed or are invalid")
            result[f"{prefix}_HM"] = hm
            result[f"{prefix}_PALT"] = projected_eal
            result[f"{prefix}_PRISKV"] = projected_risk
            result[f"{prefix}_PALR"] = projected_rating(projected_eal, eal_labels, eal_edges).where(
                supported
            )
            result[f"{prefix}_PRISKR"] = projected_rating(
                projected_risk, risk_labels, risk_edges
            ).where(supported)
            result[f"{prefix}_PRISKS"] = display_score(risk_score(projected_risk))
            result[f"{prefix}_DELTAR"] = classify(hm, hm_edges)
        nulls[variant] = {"eal": int(eal.isna().sum()), "risk": int(risk.isna().sum())}
    validation = {
        "population": len(baseline),
        "conusPopulation": int((~baseline.STATEABBRV.isin(EXCLUDED)).sum()),
        "nationalRanking": False,
        "rankingPopulation": "CONUS",
        "nativeNationalRatingBins": True,
        "baselineNullMasksPreserved": True,
        "unsupportedFutureValuesNull": True,
        "nullCounts": nulls,
        "nonConusAssumption": "Native baseline retained; future fields null",
        "minimumMultiplier": float(multipliers.min().min()),
        "maximumMultiplier": float(multipliers.max().max()),
    }
    return pd.DataFrame(result, index=baseline.index), bins, validation


def county_gamma(county_snapshot: GeographySnapshot) -> float:
    if county_snapshot.full_baseline.attrs.get("geography") != "county":
        raise ValueError("Wildfire gamma requires the updated county baseline")
    weights, ids = county_snapshot.county_weights()
    historic = pd.Series(
        wildfire.period_fwi("historical", "historical", weights, county_snapshot), index=ids
    )
    gamma = wildfire.elasticity(historic, county_snapshot)
    if not np.isfinite(gamma):
        raise ValueError("County-fitted wildfire gamma must be finite")
    return gamma


def project_geography(snapshot: GeographySnapshot, gamma: float) -> dict:
    updates = pd.concat(
        [
            drought.hazard_multipliers(snapshot),
            wildfire.hazard_multipliers(snapshot, gamma=gamma),
            heat.hazard_multipliers(snapshot),
        ],
        axis=1,
    )
    baseline = snapshot.full_baseline
    multipliers = complete_multipliers(baseline, updates)
    scored, bins, validation = score_geography(baseline, multipliers)
    validation["climateCoverage"] = snapshot.coverage_diagnostics.copy()
    return {
        "baseline": baseline,
        "multipliers": multipliers,
        "scored": scored,
        "bins": bins,
        "validation": validation,
    }


def counties(county_snapshot: GeographySnapshot, county_gamma: float) -> dict:
    return project_geography(county_snapshot, county_gamma)


def tracts(tract_snapshot: GeographySnapshot, county_gamma: float) -> dict:
    return project_geography(tract_snapshot, county_gamma)


def current_results(counties: dict, tracts: dict, county_gamma: float) -> dict:
    return {
        "counties": counties,
        "tracts": tracts,
        "parameters": {
            "wildfireElasticity": county_gamma,
            "wildfireElasticityFitGeography": "county",
            "wildfireEnsemble": wildfire.ENSEMBLE,
            "wildfireVariable": wildfire.VARIABLE,
            "climateCellHalfWidthDegrees": 0.125,
            "tractClimateResolution": "Saved climate support retained; no downscaling",
            "rankingPopulation": "CONUS",
            "nonConusAssumption": "Native baseline retained; future fields null",
        },
    }


def run(county_snapshot: GeographySnapshot, tract_snapshot: GeographySnapshot) -> dict:
    """Execute current_results via Hamilton; returns frames, bins and validation only."""
    import sys

    from hamilton import driver

    dag = driver.Builder().with_modules(sys.modules[__name__]).build()
    return dag.execute(
        ["current_results"],
        inputs={"county_snapshot": county_snapshot, "tract_snapshot": tract_snapshot},
    )["current_results"]
