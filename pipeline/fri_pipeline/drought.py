# Adapted from fulton-ring/agent-content-demos@390f7c0:
# fri-agent-rebuild/hazards/drought/pipeline.py
# Changes: inject verified snapshot inputs; no network fetches or tract mode.
"""Drought hazard multipliers from NEX-GDDP-CMIP6 (MPI-ESM1-2-HR) through SPEI-3.

FRI Technical Documentation, Section 5: monthly SPEI at a 3-month scale from precipitation and
Thornthwaite PET, log-logistic distribution, calibrated on 1950-2010. A month with SPEI <= -1.6
makes every day in it a drought event-day. HM = future event-day rate / historical (1985-2014)
rate, per 0.25-degree cell, then area-weighted to counties.
"""

import numpy as np
import pandas as pd
from scipy import sparse, stats

from .snapshot import Snapshot

SCALE_MONTHS = 3
DROUGHT_SPEI = -1.6
MIN_HIST_DAYS = 15.0  # detection floor on historical drought days (denominator only)
CALIBRATION = (pd.Timestamp("1950-01-01"), pd.Timestamp("2010-12-31"))
HISTORICAL = (pd.Timestamp("1985-01-01"), pd.Timestamp("2014-12-31"))
FUTURE = {
    "MID": (pd.Timestamp("2036-01-01"), pd.Timestamp("2065-12-31")),
    "LATE": (pd.Timestamp("2070-01-01"), pd.Timestamp("2099-12-31")),
}


def daylight_hours(lat_deg: np.ndarray, months: pd.DatetimeIndex) -> np.ndarray:
    """Mean daylight hours on the 15th of each month (FAO-56 sunset hour angle)."""
    # Verified snapshots contain month starts; +14 gives the 15th without timedelta coercion.
    day = months.dayofyear.to_numpy()[:, None] + 14
    lat = np.radians(lat_deg)[None, :]
    declination = 0.409 * np.sin(2 * np.pi * day / 365 - 1.39)
    hour_angle = np.arccos(np.clip(-np.tan(lat) * np.tan(declination), -1, 1))
    return 24 / np.pi * hour_angle


def thornthwaite_pet(
    temp_c: np.ndarray, lat_deg: np.ndarray, months: pd.DatetimeIndex
) -> np.ndarray:
    """Monthly PET (mm/month) by Thornthwaite, heat index computed per calendar year."""
    terms = (np.maximum(temp_c, 0) / 5) ** 1.514
    heat_index = pd.DataFrame(terms).groupby(np.asarray(months.year)).transform("sum").to_numpy()
    del terms
    exponent = 6.75e-7 * heat_index**3 - 7.71e-5 * heat_index**2 + 1.792e-2 * heat_index + 0.49239
    correction = (
        daylight_hours(lat_deg, months) / 12 * (months.days_in_month.to_numpy()[:, None] / 30)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        pet = 16 * correction * (10 * np.maximum(temp_c, 0) / heat_index) ** exponent
    return np.where(temp_c > 0, np.nan_to_num(pet), 0.0)


def glo_cdf(sample: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Fit a generalized logistic ("log-logistic" in the SPEI package) by unbiased PWMs per
    column of `sample` and return its CDF at `values`."""
    ordered = np.sort(sample, axis=0)
    n = np.isfinite(ordered).sum(axis=0)
    rank = np.arange(sample.shape[0])[:, None]
    b0 = np.nanmean(ordered, axis=0)
    b1 = np.nansum(rank / (n - 1) * ordered, axis=0) / n
    b2 = np.nansum(rank * (rank - 1) / ((n - 1) * (n - 2)) * ordered, axis=0) / n
    l1, l2, l3 = b0, 2 * b1 - b0, 6 * b2 - 6 * b1 + b0
    k = -(l3 / l2)
    k = np.where(np.abs(k) < 1e-6, 1e-6, k)
    alpha = l2 * np.sin(k * np.pi) / (k * np.pi)
    xi = l1 - alpha * (1 / k - np.pi / np.sin(k * np.pi))
    inner = np.clip(1 - k * (values - xi) / alpha, 1e-12, None)
    y = -np.log(inner) / k
    return 1 / (1 + np.exp(-y))


def spei(balance: np.ndarray, months: pd.DatetimeIndex) -> np.ndarray:
    """SPEI at SCALE_MONTHS, fitted separately for each calendar month on the calibration span."""
    rolled = pd.DataFrame(balance).rolling(SCALE_MONTHS).sum().to_numpy()
    calibrate = (months >= CALIBRATION[0]) & (months <= CALIBRATION[1])
    result = np.full_like(rolled, np.nan)
    for month in range(1, 13):
        rows = months.month == month
        cdf = glo_cdf(rolled[rows & calibrate], rolled[rows])
        result[rows] = stats.norm.ppf(np.clip(cdf, 1e-6, 1 - 1e-6))
    return result


def drought_days(
    index: np.ndarray, months: pd.DatetimeIndex, span: tuple[pd.Timestamp, pd.Timestamp]
) -> tuple[np.ndarray, float, np.ndarray]:
    rows = (months >= span[0]) & (months <= span[1])
    days = months.days_in_month.to_numpy()[rows, None]
    count = ((index[rows] <= DROUGHT_SPEI) * days).sum(axis=0).astype(float)
    valid = np.asarray(np.isfinite(index[rows]).any(axis=0))
    return count, float(days.sum()), valid


def area_mean(values: np.ndarray, weights: sparse.csr_matrix) -> np.ndarray:
    valid = np.isfinite(values)
    totals = weights @ np.where(valid, values, 0.0)
    covered = weights @ valid.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return totals / covered


def hazard_multipliers(inputs: Snapshot) -> pd.DataFrame:
    """Columns DRGT_<period>_<warming>_HM indexed by county FIPS (or `areas` ids)."""
    weights, fips = inputs.county_weights()
    lat = inputs.cell_coordinates()["lat"].to_numpy()
    result = {}
    for warming, ssp in inputs.SSP.items():
        temp, months = inputs.monthly("tas", ssp)
        precip, _ = inputs.monthly("pr", ssp)
        precip_mm = precip * months.days_in_month.to_numpy()[:, None]
        index = spei(precip_mm - thornthwaite_pet(temp, lat, months), months)
        past_days, past_total, past_valid = drought_days(index, months, HISTORICAL)
        past_rate = np.where(past_valid, np.maximum(past_days, MIN_HIST_DAYS) / past_total, np.nan)
        for period, span in FUTURE.items():
            fut_days, fut_total, fut_valid = drought_days(index, months, span)
            fut_rate = np.where(fut_valid, fut_days / fut_total, np.nan)
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = fut_rate / past_rate
            cell_hm = np.where(np.isfinite(ratio), ratio, np.nan)
            result[f"DRGT_{period}_{warming}_HM"] = np.maximum(1.0, area_mean(cell_hm, weights))
    return pd.DataFrame(result, index=fips)
