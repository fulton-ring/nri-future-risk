"""Download every public input once into a cache outside the repo, and read it back.

The cache lives in $FRI_CACHE (default ~/.cache/fri-agent-rebuild). Every function here checks
the cache first, so rerunning after an interruption only fetches what is missing.
Run `uv run python -m fri_rebuild.data` to fetch everything up front.
"""

import io
import os
import re
import time
import zipfile
from collections.abc import Generator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

import aiohttp
import fsspec
import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
import rasterio
import requests
import shapely
from rasterio import features
from rasterio.transform import from_origin
from requests.adapters import HTTPAdapter
from scipy import sparse
from urllib3.util.retry import Retry

PROJECT_DIR = Path(__file__).resolve().parents[2]
EQUAL_AREA = "EPSG:5070"
CONUS_EXCLUDED = {"AK", "HI", "AS", "GU", "MP", "PR", "VI"}


def cache(*parts: str) -> Path:
    """A path inside the cache, creating its parent folder."""
    root = Path(os.environ.get("FRI_CACHE", Path.home() / ".cache" / "fri-agent-rebuild"))
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def http() -> requests.Session:
    """A session that retries dropped connections and 502-504s, with backoff."""
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(502, 503, 504), allowed_methods=None)
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def download(url: str, target: Path, timeout: int = 600) -> Path:
    """Stream `url` to `target` unless it is already there."""
    if not target.exists():
        partial = target.with_name(target.name + ".partial")
        with http().get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for block in response.iter_content(chunk_size=8 << 20):
                    handle.write(block)
        partial.rename(target)
    return target


# FEMA's published values: the Future Risk master datasheet, saved before FEMA took the tool down
# in February 2025 and published in fulton-ring/nri-future-risk.
ANSWER_KEY_URL = (
    "https://raw.githubusercontent.com/fulton-ring/nri-future-risk/"
    "c5cc0d6686832f809446fc6061a689eff71d09df/public/NRI_Future_Risk_Master_Datasheet_12052024.xlsx"
)


def answer_key() -> pd.DataFrame:
    """FEMA's master datasheet (HMs, ratings, NRI v1.19 EAL) indexed by 5-digit county FIPS."""
    parquet = cache("answer_key", "master_datasheet.parquet")
    if not parquet.exists():
        xlsx = download(ANSWER_KEY_URL, cache("answer_key", "master_datasheet.xlsx"))
        table = pd.read_excel(xlsx)
        table["STCOFIPS"] = table["STCOFIPS"].astype(int).map("{:05d}".format)
        table.to_parquet(parquet)
    return pd.read_parquet(parquet).set_index("STCOFIPS")


def conus(table: pd.DataFrame) -> pd.DataFrame:
    return table[~table["STATEABBRV"].isin(CONUS_EXCLUDED)]


def nri_tracts() -> pd.DataFrame:
    """NRI v1.19.0 tract table (the FRI's baseline), from the Harvard Dataverse snapshot."""
    parquet = cache("nri", "tracts_v1_19.parquet")
    if not parquet.exists():
        csv = download(
            "https://dataverse.harvard.edu/api/access/datafile/10775728", cache("nri", "tracts.csv")
        )
        eal = [f"{hazard}_EALT" for hazard in ("CFLD", "DRGT", "HWAV", "WFIR", "HRCN")]
        fips = {"TRACTFIPS": str, "STCOFIPS": str}
        table = pd.read_csv(csv, usecols=[*fips, *eal], dtype=fips)
        table["TRACTFIPS"] = table["TRACTFIPS"].str.zfill(11)
        table["STCOFIPS"] = table["STCOFIPS"].str.zfill(5)
        table.to_parquet(parquet)
        csv.unlink()
    return pd.read_parquet(parquet).set_index("TRACTFIPS")


def census_shapes(url: str, name: str) -> gpd.GeoDataFrame:
    target = cache("geo", f"{name}.parquet")
    if not target.exists():
        archive = zipfile.ZipFile(download(url, cache("geo", f"{name}.zip")))
        folder = cache("geo", name, "x").parent
        archive.extractall(folder)
        shp = next(n for n in archive.namelist() if n.endswith(".shp"))
        gpd.read_file(folder / shp).to_parquet(target)
    return gpd.read_parquet(target)


def counties() -> gpd.GeoDataFrame:
    """2020 Census counties, the geography of NRI v1.19 and the FRI."""
    url = "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_county_500k.zip"
    shapes = census_shapes(url, "counties_2020").rename(columns={"GEOID": "fips"})
    return shapes.set_index("fips")[["STATEFP", "NAME", "geometry"]]


def tracts(state_fips: str) -> gpd.GeoDataFrame:
    url = f"https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_{state_fips}_tract_500k.zip"
    shapes = census_shapes(url, f"tracts_2020_{state_fips}").rename(columns={"GEOID": "tract"})
    return shapes.set_index("tract")[["COUNTYFP", "geometry"]]


def area_weights(
    areas: gpd.GeoDataFrame, lat: np.ndarray, lon: np.ndarray, name: str
) -> tuple[sparse.csr_matrix, pd.Index]:
    """Intersection areas (km^2) of polygons (rows) with grid cells (columns, row-major).

    Every grid is drawn as 0.25-degree boxes around its cell centres, the NEX cell size. LOCA2's
    1/16-degree centres get the same boxes, so its county values are smoothed over about 25 km.
    That is how the published numbers were made; see the rebuild notebook.
    """
    target, ids_path = (
        cache("geo", f"weights_{name}.npz"),
        cache("geo", f"weights_{name}_ids.parquet"),
    )
    if not target.exists():
        grid_lat, grid_lon = np.meshgrid(lat, np.where(lon > 180, lon - 360, lon), indexing="ij")
        x, y = grid_lon.ravel(), grid_lat.ravel()
        boxes = shapely.box(x - 0.125, y - 0.125, x + 0.125, y + 0.125)
        cells = gpd.GeoDataFrame({"cell": np.arange(len(boxes))}, geometry=boxes, crs="EPSG:4326")  # ty: ignore[no-matching-overload] - geopandas has no stubs that agree with pandas-stubs
        shapes = areas.to_crs(EQUAL_AREA).reset_index(names="area_id")
        pieces = gpd.overlay(shapes[["area_id", "geometry"]], cells.to_crs(EQUAL_AREA))
        rows = pd.Index(shapes["area_id"])
        where = (rows.get_indexer(pieces["area_id"]), pieces["cell"].to_numpy())
        matrix = sparse.csr_matrix(
            (pieces.geometry.area.to_numpy() / 1e6, where), shape=(len(rows), len(boxes))
        )
        sparse.save_npz(target, matrix)
        pd.DataFrame({"area_id": rows}).to_parquet(ids_path)
    ids = pd.Index(pd.read_parquet(ids_path)["area_id"])
    return sparse.csr_matrix(sparse.load_npz(target)), ids


# NASA NEX-GDDP-CMIP6, one climate model. Each source file is one global year of one variable
# (about 250 MB), so we read it whole and keep the CONUS box as int16 hundredths.
NEX = "https://nex-gddp-cmip6.s3.us-west-2.amazonaws.com"
NEX_PREFIX = "NEX-GDDP-CMIP6/MPI-ESM1-2-HR/{scenario}/r1i1p1f1/{variable}/"
BOX = ((24.0, 50.0), (235.0, 294.0))
NEX_SCALE, NEX_MISSING = 100.0, np.iinfo(np.int16).min
HEAT_YEARS = {
    "historical": range(1976, 2006),
    "ssp245": [*range(2036, 2066), *range(2070, 2100)],
    "ssp585": [*range(2036, 2066), *range(2070, 2100)],
}
MONTHLY_YEARS = {"historical": range(1950, 2015), "ssp245": range(2015, 2101)}
MONTHLY_YEARS["ssp585"] = MONTHLY_YEARS["ssp245"]


def nex_path(kind: str, variable: str, scenario: str, year: int) -> Path:
    return cache("nex", kind, variable, scenario, f"{year}.npy")


def nex_newest_files(variable: str, scenario: str) -> dict[int, str]:
    """Year -> key of the newest file version (S3 lists 1,000 keys a page; we need under 200)."""
    prefix = NEX_PREFIX.format(scenario=scenario, variable=variable)
    response = http().get(NEX, params={"list-type": "2", "prefix": prefix}, timeout=60)
    response.raise_for_status()
    assert "<IsTruncated>false" in response.text, f"{prefix} lists more than one page"
    newest: dict[int, tuple[float, str]] = {}
    for key in re.findall(r"<Key>([^<]+)</Key>", response.text):
        found = re.search(r"_(\d{4})(?:_v(\d+\.\d+))?\.nc$", key)
        if found:
            year, version = int(found.group(1)), float(found.group(2) or 0)
            if version >= newest.get(year, (-1.0, ""))[0]:
                newest[year] = (version, key)
    return {year: key for year, (_, key) in newest.items()}


def box_slices(lat: np.ndarray, lon: np.ndarray) -> tuple[slice, slice]:
    rows = np.flatnonzero((lat >= BOX[0][0]) & (lat <= BOX[0][1]))
    cols = np.flatnonzero((lon >= BOX[1][0]) & (lon <= BOX[1][1]))
    return slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1)


def save(path: Path, array: np.ndarray) -> None:
    """Write through a temporary name, so an interrupted run never leaves a half-written file."""
    partial = path.with_name(path.stem + ".partial.npy")
    np.save(partial, array)
    partial.rename(path)


def nex_year(variable: str, scenario: str, year: int, key: str, keep: tuple[bool, bool]) -> str:
    """Download one NEX file and save its CONUS box: daily values and/or monthly means."""
    raw = download(f"{NEX}/{key}", cache("nex", "tmp", f"{variable}_{scenario}_{year}.nc"), 300)
    with h5py.File(raw) as nc:
        rows, cols = box_slices(nc["lat"][:], nc["lon"][:])
        data = nc[variable][:, rows, cols].astype(np.float32)
        if not cache("nex", "grid.npz").exists():
            np.savez(cache("nex", "grid.npz"), lat=nc["lat"][rows], lon=nc["lon"][cols])
    raw.unlink()
    data[np.abs(data) > 1e10] = np.nan
    data = data - 273.15 if variable.startswith("tas") else data
    data = data * 86400.0 if variable == "pr" else data
    if keep[1]:
        days = np.arange(f"{year}-01-01", f"{year + 1}-01-01", dtype="datetime64[D]")
        month = days[: len(data)].astype("datetime64[M]").astype(int) % 12
        monthly = np.stack([data[month == m].mean(axis=0) for m in range(12)])
        save(nex_path("monthly", variable, scenario, year), monthly)
    if keep[0]:
        scaled = np.where(np.isnan(data), NEX_MISSING, np.round(data * NEX_SCALE))
        save(nex_path("daily", variable, scenario, year), scaled.astype(np.int16))
    return f"{variable} {scenario} {year}"


def nex_all(workers: int = 8) -> None:
    jobs: dict[tuple[str, str, int], tuple[bool, bool]] = {}
    for variable in ("tasmin", "tas", "pr", "hurs", "tasmax"):
        for scenario in ("historical", "ssp245", "ssp585"):
            daily = variable != "pr" and HEAT_YEARS[scenario]
            monthly = variable in ("tas", "pr") and MONTHLY_YEARS[scenario]
            for year in sorted({*(daily or []), *(monthly or [])}):
                keep = (bool(daily) and year in daily, bool(monthly) and year in monthly)
                done = all(
                    not wanted or nex_path(kind, variable, scenario, year).exists()
                    for wanted, kind in zip(keep, ("daily", "monthly"), strict=True)
                )
                if not done:
                    jobs[(variable, scenario, year)] = keep
    print(f"NEX-GDDP-CMIP6: {len(jobs)} files to fetch", flush=True)
    keys = {(v, s): nex_newest_files(v, s) for v, s in {(v, s) for v, s, _ in jobs}}
    with ProcessPoolExecutor(workers) as pool:
        futures = [
            pool.submit(nex_year, v, s, y, keys[(v, s)][y], k) for (v, s, y), k in jobs.items()
        ]
        for count, future in enumerate(as_completed(futures), 1):
            print(f"[{count}/{len(jobs)}] {future.result()}", flush=True)


# NASA's NEX-GDDP-CMIP6 Fire Weather Index: yearly multi-model-ensemble files. Some years are
# missing on the portal; those are recorded and skipped.
FWI = "https://data.nas.nasa.gov/gddpimpact/FWI/Yearly/MME/{ensemble}_{scenario}_fwi_metrics_yearly_{year}.nc"


def fwi_path(ensemble: str, scenario: str, year: int) -> Path:
    return cache("fwi", ensemble, scenario, f"{year}.npz")


def fwi_year(ensemble: str, scenario: str, year: int) -> bool:
    """Save one year's CONUS box; False if the portal doesn't have that year."""
    target, missing = (
        fwi_path(ensemble, scenario, year),
        cache("fwi", ensemble, scenario, f"{year}.missing"),
    )
    if target.exists() or missing.exists():
        return target.exists()
    response = http().get(FWI.format(ensemble=ensemble, scenario=scenario, year=year), timeout=300)
    if response.status_code != 200:
        missing.write_text(str(response.status_code))
        return False
    with h5py.File(io.BytesIO(response.content)) as nc:
        rows, cols = box_slices(nc["lat"][:], nc["lon"][:])
        grids = {k: nc[k][rows, cols].astype(np.float32) for k in nc if nc[k].ndim == 2}
    for values in grids.values():
        values[np.abs(values) > 1e10] = np.nan
    np.savez(target, **grids)
    return True


def fwi_all() -> None:
    jobs = [
        (ensemble, scenario, year)
        for ensemble in ("MME25", "MME50", "MME75")
        for scenario, years in HEAT_YEARS.items()
        for year in years
    ]
    with ThreadPoolExecutor(3) as pool:
        found = list(pool.map(lambda job: fwi_year(*job), jobs))
    print(f"FWI: {len(jobs)} files, {found.count(False)} missing on the portal", flush=True)


# LANDFIRE LF2022 fuel models (FBFM40). The 30 m national file is 3.4 GB, so we ask the
# ImageServer for a nearest-neighbour 500 m export in four tiles.
LANDFIRE = (
    "https://lfps.usgs.gov/arcgis/rest/services/Landfire_LF2022/LF2022_FBFM40_CONUS/ImageServer"
)
LANDFIRE_BOUNDS, PIXEL = (-2362395.0, 221265.0, 2327655.0, 3267405.0), 500.0
FUEL_GROUPS = {  # Scott and Burgan (2005) code ranges
    "nonburnable": range(91, 100),
    "grass": range(101, 110),
    "grass_shrub": range(121, 125),
    "shrub": range(141, 150),
    "timber_understory": range(161, 166),
    "timber_litter": range(181, 190),
    "slash_blowdown": range(201, 205),
}


def landfire_tile(x0: float, y0: float, width: int, height: int) -> np.ndarray:
    params = {
        "bbox": f"{x0},{y0},{x0 + width * PIXEL},{y0 + height * PIXEL}",
        "bboxSR": "5070",
        "imageSR": "5070",
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "U8",
        "interpolation": "RSP_NearestNeighbor",
        "f": "image",
    }
    response = requests.get(f"{LANDFIRE}/exportImage", params=params, timeout=600)
    response.raise_for_status()
    with rasterio.open(io.BytesIO(response.content)) as tile:
        data = tile.read(1)
    assert data.shape == (height, width), f"tile came back {data.shape}"
    return data


def fuel_shares(areas: gpd.GeoDataFrame, name: str) -> pd.DataFrame:
    """Share of each fuel group's 500 m pixels in every polygon."""
    target = cache("landfire", f"shares_{name}.parquet")
    if target.exists():
        return pd.read_parquet(target)
    left, bottom, right, top = LANDFIRE_BOUNDS
    width, height = int(np.ceil((right - left) / PIXEL)), int(np.ceil((top - bottom) / PIXEL))
    grid_path = cache("landfire", "fbfm40_lf2022_500m.npy")
    if not grid_path.exists():
        grid = np.zeros((height, width), dtype=np.uint8)
        cols, rows = np.linspace(0, width, 3).astype(int), np.linspace(0, height, 3).astype(int)
        for r0, r1 in zip(rows[:-1], rows[1:], strict=True):
            for c0, c1 in zip(cols[:-1], cols[1:], strict=True):
                grid[r0:r1, c0:c1] = landfire_tile(
                    left + c0 * PIXEL, top - r1 * PIXEL, c1 - c0, r1 - r0
                )
        np.save(grid_path, grid)
    grid = np.load(grid_path)
    shapes = areas.to_crs(EQUAL_AREA).geometry
    labels = features.rasterize(
        zip(shapes, range(1, len(shapes) + 1), strict=True),
        out_shape=grid.shape,
        transform=from_origin(left, top, PIXEL, PIXEL),
        dtype=np.int32,
    )
    group_of_code = np.full(256, -1, dtype=np.int8)
    for index, codes in enumerate(FUEL_GROUPS.values()):
        group_of_code[list(codes)] = index
    groups = group_of_code[grid]
    keep = (labels > 0) & (groups >= 0)
    counts = np.zeros((len(shapes) + 1, len(FUEL_GROUPS)))
    np.add.at(counts, (labels[keep], groups[keep]), 1)
    with np.errstate(invalid="ignore"):
        shares = counts[1:] / counts[1:].sum(axis=1, keepdims=True)
    pd.DataFrame(shares, index=areas.index, columns=list(FUEL_GROUPS)).to_parquet(target)
    return pd.read_parquet(target)


# LOCA2 daily tasmin, same climate model, 1/16 degree. Its files are 9-22 GB, so we read only the
# FRI periods' days over HTTP and keep, per cell, a histogram of tasmin in 0.1 C bins: percentiles
# and day counts above any threshold come straight from it.
LOCA2 = (
    "https://cirrus.ucsd.edu/~pierce/LOCA2/NAmer/MPI-ESM1-2-HR/0p0625deg/r1i1p1f1/{run}/tasmin/"
    "tasmin.MPI-ESM1-2-HR.{run}.r1i1p1f1.{span}.LOCA_16thdeg_v20220413.nc"
)
LOCA2_SPANS = {"historical": ["1950-2014"], "ssp245": ["2015-2044", "2045-2074", "2075-2100"]}
LOCA2_SPANS["ssp585"] = LOCA2_SPANS["ssp245"]
PERIODS = {"historical": (1976, 2005), "MID": (2036, 2065), "LATE": (2070, 2099)}
# Bin 0 holds everything below -10 C, the last value bin everything from 40 C, and one more row
# counts days with no data (ocean cells).
EDGES = np.concatenate([[-np.inf], np.arange(-10.0, 40.05, 0.1), [np.inf]])
NO_DATA_ROW = len(EDGES) - 1
PIECE_DAYS = 3 * 365  # each finished piece is saved, so an interruption loses only pieces in flight


@contextmanager
def loca2_open(run: str, span: str) -> Generator[h5py.File]:
    """One LOCA2 file over HTTP. Closing the remote file too frees its read-ahead buffer;
    h5py alone leaves it open, and a worker then grows past 4 GB over a three-year piece."""
    url = LOCA2.format(run=run, span=span)
    # trust_env makes fsspec's aiohttp session use HTTPS_PROXY when one is set.
    remote = fsspec.open(
        url, block_size=64 << 20, cache_type="readahead", client_kwargs={"trust_env": True}
    )
    with remote as handle, h5py.File(handle) as nc:
        yield nc


def loca2_cells() -> tuple[np.ndarray, sparse.csr_matrix, pd.Index]:
    """LOCA2 cells that overlap a CONUS county (flat indices) and county x cell areas."""
    grid = cache("loca2", "grid.npz")
    if not grid.exists():
        with loca2_open("historical", "1950-2014") as nc:
            np.savez(grid, lat=nc["lat"][:], lon=nc["lon"][:])
    lat, lon = np.load(grid)["lat"], np.load(grid)["lon"]
    fips = conus(answer_key()).index
    weights, ids = area_weights(counties().loc[fips], lat, lon, "counties_loca2")
    cells = np.flatnonzero(np.asarray(weights.sum(axis=0)).ravel() > 0)
    return cells, sparse.csr_matrix(weights[:, cells]), ids


def loca2_piece(run: str, span: str, days: tuple[int, int], cells: np.ndarray, name: str) -> Path:
    """Histogram of one run of days, read 60 days at a time (5 tries per read, with backoff)."""
    target = cache("loca2", "partial", name)
    if target.exists():
        return target
    counts = np.zeros((len(EDGES), len(cells)), dtype=np.uint16)
    for start in range(days[0], days[1], 60):
        for attempt in range(5):
            try:
                with loca2_open(run, span) as nc:
                    block = nc["tasmin"][start : min(start + 60, days[1])]
                break
            except (OSError, aiohttp.ClientError):
                if attempt == 4:
                    raise
                time.sleep(30 * 2**attempt)  # the server drops reads now and then
        for day in block.reshape(block.shape[0], -1)[:, cells] - 273.15:
            bins = np.searchsorted(EDGES, day, side="right") - 1
            bins = np.where(np.isfinite(day) & (np.abs(day) < 1e10), bins, NO_DATA_ROW)
            counts[bins, np.arange(len(cells))] += 1
    np.save(target.with_name(target.stem + ".tmp.npy"), counts)
    target.with_name(target.stem + ".tmp.npy").rename(target)
    return target


def loca2_histogram_path(scenario: str, period: str) -> Path:
    return cache("loca2", "hist", f"{scenario}_{period}.npy")


def loca2_period(scenario: str, period: str, cells: np.ndarray) -> None:
    """Build one period's histograms from pieces of about three years, read in parallel by
    $FRI_LOCA2_WORKERS processes (default 4; each uses about 1 GB of memory)."""
    if loca2_histogram_path(scenario, period).exists():
        return
    first, last = PERIODS[period]
    pieces = []
    for span in LOCA2_SPANS[scenario]:
        start, end = (int(year) for year in span.split("-"))
        lo, hi = max(first, start), min(last, end)
        if lo <= hi:
            origin = np.datetime64(f"{start}-01-01")
            begin = int((np.datetime64(f"{lo}-01-01") - origin).astype(int))
            stop = int((np.datetime64(f"{hi + 1}-01-01") - origin).astype(int))
            bounds = np.linspace(
                begin, stop, max(1, round((stop - begin) / PIECE_DAYS)) + 1
            ).astype(int)
            pieces += [
                (span, (int(a), int(b))) for a, b in zip(bounds[:-1], bounds[1:], strict=True)
            ]
    names = [f"{scenario}_{period}_{i}.npy" for i in range(len(pieces))]
    with ProcessPoolExecutor(int(os.environ.get("FRI_LOCA2_WORKERS", "4"))) as pool:
        futures = [
            pool.submit(loca2_piece, scenario, span, days, cells, name)
            for (span, days), name in zip(pieces, names, strict=True)
        ]
        partials = [future.result() for future in futures]
    total = sum(np.load(path).astype(np.uint32) for path in partials)
    np.save(loca2_histogram_path(scenario, period), np.asarray(total, dtype=np.uint16))
    for path in partials:
        path.unlink()
    print(f"LOCA2 {scenario} {period}: done", flush=True)


def loca2_all() -> None:
    cells, _, _ = loca2_cells()
    loca2_period("historical", "historical", cells)
    for scenario in ("ssp245", "ssp585"):
        for period in ("MID", "LATE"):
            loca2_period(scenario, period, cells)


# NOAA tide-gauge data for coastal flooding.
HTF = "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/htf"
STATIONS = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station}/{resource}.json?units=metric"
SLR_REPORT = "https://cdn.oceanservice.noaa.gov/oceanserviceprod/hazards/sealevelrise/Sea_Level_Rise_Datasets_2022.zip"
SEVERITIES = ("minor", "moderate", "major")


def station(station_id: str, resource: str) -> dict:
    """One CO-OPS metadata resource for a station; empty if the station doesn't publish it."""
    response = http().get(STATIONS.format(station=station_id, resource=resource), timeout=120)
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    return response.json()


def report_table(name: str) -> pd.DataFrame:
    """One CSV from the 2022 Sea Level Rise Technical Report zip, its preamble skipped."""
    with zipfile.ZipFile(
        download(SLR_REPORT, cache("coastal", "Sea_Level_Rise_Datasets_2022.zip"))
    ) as zf:
        lines = (
            zf.read(next(n for n in zf.namelist() if n.endswith(name)))
            .decode("latin-1")
            .splitlines()
        )
    header = next(
        i for i, line in enumerate(lines) if line.startswith(("EWL_GridNum", "PSMSL Site"))
    )
    return pd.read_csv(io.StringIO("\n".join(lines[header:])), low_memory=False)


def htf_projections() -> pd.DataFrame:
    """CO-OPS decadal high-tide-flooding projections: flood days a year by gauge, decade,
    severity and 2022 scenario."""
    response = http().get(f"{HTF}/htf_projection_decadal.json", timeout=120)
    response.raise_for_status()
    return pd.DataFrame(
        {
            "station": str(entry["stnId"]),
            "lat": entry["lat"],
            "lon": entry["lon"],
            "decade": int(entry["decade"]),
            "severity": severity,
            "scenario": scenario,
            "days": entry[scenario],
        }
        for record in response.json()["DecadalProjection"]
        for severity in SEVERITIES
        for entry in record[severity]
        for scenario in ("low", "intLow", "intermediate", "intHigh", "high")
    )


def htf_observed() -> pd.DataFrame:
    response = http().get(f"{HTF}/htf_annual.json", timeout=120)
    response.raise_for_status()
    names = {"stnId": "station", "minCount": "minor", "modCount": "moderate", "majCount": "major"}
    table = pd.DataFrame(response.json()["AnnualFloodCount"]).rename(columns=names)
    table["station"] = table["station"].astype(str)
    return table.rename(columns={"nanCount": "missing_days"})[
        ["station", "lat", "lon", "year", *SEVERITIES, "missing_days"]
    ]


def gauge_metadata(stations: list[str]) -> pd.DataFrame:
    """NOAA flood thresholds (m above MHHW), tide range GT and MHHW for each gauge."""
    rows = []
    for station_id in stations:
        levels = station(station_id, "floodlevels")
        datums = {d["name"]: d["value"] for d in station(station_id, "datums").get("datums", [])}
        row: dict[str, object] = {
            "station": station_id,
            "gt_m": datums.get("GT"),
            "mhhw_m": datums.get("MHHW"),
        }
        for severity in SEVERITIES:
            value, mhhw = levels.get(f"nos_{severity}"), datums.get("MHHW")
            row[f"{severity}_m_above_mhhw"] = (
                None if value is None or mhhw is None else float(value) - float(mhhw)
            )
        rows.append(row)
    return pd.DataFrame(rows)


def tide_tables() -> dict[str, pd.DataFrame]:
    """The coastal tables, cached as parquet. See `inputs.coastal_tables` for what each holds."""
    builders = {
        "extreme_water_levels": lambda: report_table(
            "SLR_TF U.S. Extreme Water Levels_Final-tide-gauges.csv"
        ),
        "sea_level_projections": lambda: report_table("SLR_TF U.S. Sea Level Projections.csv"),
        "htf_decadal": htf_projections,
        "htf_observed": htf_observed,
    }
    tables = {}
    for name, build in builders.items():
        path = cache("coastal", f"{name}.parquet")
        if not path.exists():
            table = build()
            table.columns = [str(c) for c in table.columns]
            table.to_parquet(path)
        tables[name] = pd.read_parquet(path)
    path = cache("coastal", "gauge_metadata.parquet")
    if not path.exists():
        gauges = {str(s) for s in tables["extreme_water_levels"]["St"].dropna()}
        gauge_metadata(sorted(gauges | set(tables["htf_decadal"]["station"]))).to_parquet(path)
    metadata = pd.read_parquet(path)
    tables["flood_thresholds"] = metadata[["station", *(f"{s}_m_above_mhhw" for s in SEVERITIES)]]
    tables["tidal_datums"] = metadata[["station", "gt_m", "mhhw_m"]]
    return tables


def prepare() -> None:
    """Fetch every input the notebooks need. The slow parts are NEX (about 230 GB transferred)
    and LOCA2 (about 55 GB of range reads); both resume where they stopped."""
    fips = conus(answer_key()).index
    print(f"answer key: {len(fips)} CONUS counties", flush=True)
    nri_tracts()
    nex_all()
    fwi_all()
    grid = np.load(cache("nex", "grid.npz"))
    area_weights(counties().loc[fips], grid["lat"], grid["lon"], "counties")
    fuel_shares(counties().loc[fips], "counties")
    tide_tables()
    loca2_all()
    print("inputs ready", flush=True)


if __name__ == "__main__":
    prepare()
