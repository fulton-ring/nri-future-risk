"""The read-only data API that hazard pipelines (and so the agents) may use.

Climate arrays cover only grid cells that overlap a CONUS county, as float32 (time, cell) arrays
whose cell order matches the columns of `county_weights()`. Nothing here exposes FEMA's
published multipliers: `baseline()` returns only the NRI EAL and ratings they were applied to.
"""

from functools import cache

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse

from fri_rebuild import data

SSP = {"LOWER": "ssp245", "HIGHER": "ssp585"}
# Intersection areas (km^2) of areas (rows) with the cells pipelines see (columns), and area ids.
AreaWeights = tuple[sparse.csr_matrix, pd.Index]


@cache
def grid() -> tuple[np.ndarray, np.ndarray]:
    """Latitude and longitude (degrees east, 0-360) of the NEX CONUS box."""
    saved = np.load(data.cache("nex", "grid.npz"))
    return saved["lat"], saved["lon"]


@cache
def box_weights() -> AreaWeights:
    fips = data.conus(data.answer_key()).index
    return data.area_weights(data.counties().loc[fips], *grid(), "counties")


@cache
def cell_index() -> np.ndarray:
    """Indices into the flattened NEX box of the cells that overlap a county."""
    return np.flatnonzero(np.asarray(box_weights()[0].sum(axis=0)).ravel() > 0)


@cache
def county_weights() -> AreaWeights:
    """Intersection area (km^2) of each CONUS county (rows) with each cell (columns)."""
    weights, fips = box_weights()
    return weights[:, cell_index()].tocsr(), fips


def tract_weights(state_fips: str) -> AreaWeights:
    """Like `county_weights`, for the 2020 census tracts of one state."""
    weights, ids = data.area_weights(data.tracts(state_fips), *grid(), f"tracts_{state_fips}")
    return weights[:, cell_index()].tocsr(), ids


@cache
def cell_coordinates() -> pd.DataFrame:
    """Latitude and longitude (-180..180) of each cell pipelines see."""
    lat, lon = grid()
    grid_lat, grid_lon = np.meshgrid(lat, np.where(lon > 180, lon - 360, lon), indexing="ij")
    return pd.DataFrame(
        {"lat": grid_lat.ravel()[cell_index()], "lon": grid_lon.ravel()[cell_index()]}
    )


def period_years(scenario: str, period: str) -> range:
    if (scenario == "historical") != (period == "historical"):
        raise ValueError(f"{period} is not a {scenario} period")
    first, last = data.PERIODS[period]
    return range(first, last + 1)


def daily(variable: str, scenario: str, period: str) -> np.ndarray:
    """Daily NEX values (tasmin/tasmax/tas in deg C, hurs in %) for one 30-year period, shape
    (days, cells). scenario: historical, ssp245 or ssp585; period: historical, MID or LATE."""
    target = data.cache("inputs", "daily", f"{variable}_{scenario}_{period}.npy")
    if not target.exists():
        years = [
            np.load(data.nex_path("daily", variable, scenario, year))
            for year in period_years(scenario, period)
        ]
        np.save(target, np.concatenate([y.reshape(len(y), -1)[:, cell_index()] for y in years]))
    values = np.load(target).astype(np.float32)
    values[values == data.NEX_MISSING] = np.nan
    return values / data.NEX_SCALE


def monthly(variable: str, scenario: str) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """Monthly means (tas deg C, pr mm/day), 1950-2100, shape (months, cells). Scenario runs
    are joined to the historical run (1950-2014)."""
    years = [*data.MONTHLY_YEARS["historical"]]
    years += [*data.MONTHLY_YEARS[scenario]] if scenario != "historical" else []
    target = data.cache("inputs", "monthly", f"{variable}_{scenario}.npy")
    if not target.exists():
        stacks = [
            np.load(data.nex_path("monthly", variable, "historical" if y <= 2014 else scenario, y))
            for y in years
        ]
        np.save(target, np.concatenate([s.reshape(12, -1)[:, cell_index()] for s in stacks]))
    months = pd.date_range(f"{years[0]}-01-01", periods=12 * len(years), freq="MS")
    return np.load(target).astype(np.float32), months


def fwi(scenario: str, period: str, variable: str = "FWI", ensemble: str = "MME50") -> np.ndarray:
    """Yearly Fire Weather Index statistics, shape (years on NASA's portal, cells).

    variable: FWI (annual mean), FWI_P25/P50/P75/P95, FWI_N15/N30/N45 (days above 15/30/45),
    FWI_NP95, FWI_Nmid, FFMC, DMC, DC, ISI, BUI. ensemble: MME25, MME50 or MME75.
    """
    paths = [data.fwi_path(ensemble, scenario, y) for y in period_years(scenario, period)]
    return np.stack([np.load(p)[variable].reshape(-1)[cell_index()] for p in paths if p.exists()])


def baseline() -> pd.DataFrame:
    """NRI v1.19 EAL and EAL ratings per CONUS county, as given in FEMA's datasheet."""
    key = data.conus(data.answer_key())
    return key[["STATEABBRV", "COUNTY", *key.columns[key.columns.str.endswith(("_EALT", "_EALR"))]]]


def county_fuel_shares() -> pd.DataFrame:
    """Share of LANDFIRE LF2022 fuel-model groups in each county (500 m sampling)."""
    return data.fuel_shares(data.counties().loc[county_weights()[1]], "counties")


def loca2_histogram(scenario: str, period: str) -> tuple[np.ndarray, np.ndarray]:
    """LOCA2 daily tasmin histograms for one 30-year period: (edges, counts).

    edges are bin edges in deg C (first and last are -inf/inf, 0.1 deg C bins from -10 to 40).
    counts has one row per bin plus a last row counting days with no data, and one column per
    cell of `loca2_county_weights`.
    """
    return data.EDGES, np.load(data.loca2_histogram_path(scenario, period))


def loca2_county_weights() -> AreaWeights:
    """County x cell overlap areas (km^2) for the cells in `loca2_histogram`.

    Each cell is drawn as a 0.25-degree box around its centre, not its exact 1/16-degree footprint.
    """
    _, weights, fips = data.loca2_cells()
    return weights, fips


def coastal_tables() -> dict[str, pd.DataFrame]:
    """NOAA tide-gauge tables for coastal flooding.

    htf_decadal: projected flood days a year by station, decade 2020-2100, severity and 2022
    scenario (low, intLow, intermediate, intHigh, high). htf_observed: observed flood days per
    meteorological year and severity. extreme_water_levels: the 187 gauges' return levels (m
    above MHHW) for 0.1-100 year return periods. sea_level_projections: relative sea level rise
    (cm) by scenario and decade, per gauge and 1-degree grid. flood_thresholds: NOAA minor,
    moderate and major thresholds (m above MHHW).
    """
    return data.tide_tables()


def county_shapes() -> gpd.GeoDataFrame:
    """CONUS county polygons (EPSG:4269) indexed by FIPS."""
    return data.counties().loc[county_weights()[1]]


def points(table: pd.DataFrame, lon: str = "lon", lat: str = "lat") -> gpd.GeoDataFrame:
    """A table with lon/lat columns as points (EPSG:4326)."""
    geometry = gpd.points_from_xy(table[lon].astype(float), table[lat].astype(float))
    return gpd.GeoDataFrame(table, geometry=geometry, crs="EPSG:4326")  # ty: ignore[no-matching-overload] - geopandas has no stubs that agree with pandas-stubs
