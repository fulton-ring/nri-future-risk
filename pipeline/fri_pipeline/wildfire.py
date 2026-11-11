# Adapted from fulton-ring/agent-content-demos@390f7c0:
# fri-agent-rebuild/hazards/wildfire/pipeline.py
# Changes: inject verified snapshot inputs; no network fetches or tract mode.
"""Wildfire hazard multipliers from NEX-GDDP-CMIP6 Fire Weather Index and LANDFIRE fuels.

FRI Technical Documentation, Section 8: HM = (FWI_scenario / FWI_historic) ** gamma, where gamma
is the coefficient on log historic FWI in a log-log regression of NRI county EAL on FWI with
fuel-type shares as controls. MME50 / annual mean follows the controlled FWI-choice spike;
the fuel-controlled regression and county aggregation remain unchanged.
"""

import numpy as np
import pandas as pd
from scipy import sparse

from .snapshot import Snapshot

PERIODS = ("MID", "LATE")
ENSEMBLE = "MME50"
VARIABLE = "FWI"


def area_mean(values: np.ndarray, weights: sparse.csr_matrix) -> np.ndarray:
    valid = np.isfinite(values)
    totals = weights @ np.where(valid, values, 0.0)
    covered = weights @ valid.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return totals / covered


def period_fwi(
    scenario: str, period: str, weights: sparse.csr_matrix, inputs: Snapshot
) -> np.ndarray:
    return area_mean(
        np.nanmean(inputs.fwi(scenario, period, variable=VARIABLE, ensemble=ENSEMBLE), axis=0),
        weights,
    )


def elasticity(historic_fwi: pd.Series, inputs: Snapshot) -> float:
    """gamma: WLS of ln(wildfire EAL) on ln(FWI), fuel shares and ln(burnable share)."""
    baseline = inputs.baseline()
    all_fuels = inputs.county_fuel_shares()
    fuels = all_fuels.drop(columns="nonburnable")
    burnable = (1.0 - all_fuels["nonburnable"]).clip(lower=1e-3)
    eal = baseline["WFIR_EALT"]
    usable = (eal > 0) & (historic_fwi > 0) & fuels.notna().all(axis=1) & burnable.notna()
    design = pd.concat(
        [
            historic_fwi[usable].map(np.log).rename("log_fwi"),
            fuels[usable],
            burnable[usable].map(np.log).rename("log_burnable"),
        ],
        axis=1,
    ).assign(const=1.0)
    w = np.sqrt(burnable[usable].to_numpy())
    X = design.to_numpy() * w[:, None]
    y = np.log(eal[usable].to_numpy()) * w
    coefficients, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(coefficients[0])


def hazard_multipliers(inputs: Snapshot, *, gamma: float | None = None) -> pd.DataFrame:
    """Columns WFIR_<period>_<warming>_HM indexed by county FIPS (or `areas` ids).

    Without an explicit gamma, fit across counties using NRI EAL and fuels.
    Tract callers supply the separately county-fitted gamma.
    """
    county_weights, counties = inputs.county_weights()
    if gamma is None:
        gamma = elasticity(
            pd.Series(period_fwi("historical", "historical", county_weights, inputs), counties),
            inputs,
        )
    if not np.isfinite(gamma):
        raise ValueError("Wildfire elasticity must be finite")
    weights, ids = county_weights, counties
    historic = pd.Series(period_fwi("historical", "historical", weights, inputs), index=ids)
    result = {}
    for warming, ssp in inputs.SSP.items():
        for period in PERIODS:
            future = pd.Series(period_fwi(ssp, period, weights, inputs), index=ids)
            result[f"WFIR_{period}_{warming}_HM"] = (future / historic) ** gamma
    frame = pd.DataFrame(result, index=ids)
    frame.attrs["elasticity"] = gamma
    return frame
