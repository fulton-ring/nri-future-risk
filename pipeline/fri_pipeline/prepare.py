"""Acquire real inputs using the pinned spike; publish only immutable input snapshots."""

import argparse
import hashlib
import json
import multiprocessing
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import requests

from .candidate import validate_id, write_json
from .snapshot import CONTRACT, ROOT, Snapshot, sha256
from .storage import download, split_uri, upload

REFERENCE_HASHES = {
    "__init__.py": "79095cc940ab22eb21bafa08f956c05c3c5e0b7166d3feaea6178268183d9a5f",
    "data.py": "c1a02289c05db164ca52ad33145a90d944dd945c0c4c86ad3ab934964b48cede",
    "inputs.py": "c7f77c65a0d9eeb9802623ded6c82806e7f604e0fc5115dd631a61b59b43bb5a",
}
PERIODS = {"historical": (1976, 2005), "MID": (2036, 2065), "LATE": (2070, 2099)}


def verify_reference(directory: Path) -> None:
    for name, expected in REFERENCE_HASHES.items():
        if sha256(directory / name) != expected:
            raise ValueError(f"Pinned acquisition reference changed: {name}")


def record_source(directory: Path, url: str, path: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    identifier = hashlib.sha256(url.encode()).hexdigest()
    target = directory / f"{identifier}.json"
    value = {
        "id": identifier,
        "title": path.name,
        "url": url,
        "sha256": sha256(path),
        "retrievedAt": datetime.now(UTC).isoformat(),
        "bytes": path.stat().st_size,
    }
    if target.exists():
        previous = json.loads(target.read_text())
        if previous["sha256"] != value["sha256"]:
            raise ValueError(f"Source changed within acquisition: {url}")
        return previous
    temporary = target.with_suffix(f".{os.getpid()}.tmp")
    write_json(temporary, value)
    temporary.replace(target)
    return value


def download_raw(url: str, target: Path, timeout: int = 300) -> Path:
    """Hash the complete source object before upstream code discards its scratch file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    source_directory = Path(os.environ["FRI_CACHE"]) / "sources"
    if target.exists():
        record_source(source_directory, url, target)
        return target
    temporary = target.with_name(target.name + ".partial")
    for attempt in range(4):
        try:
            with requests.get(
                url, stream=True, timeout=(20, timeout), headers={"Cache-Control": "no-cache"}
            ) as response:
                if response.status_code != 200:
                    raise ValueError(
                        f"Expected complete source object: {response.status_code}: {url}"
                    )
                transferred, last_progress = 0, time.monotonic()
                with temporary.open("wb") as handle:
                    for block in response.iter_content(8 << 20):
                        handle.write(block)
                        transferred += len(block)
                        if time.monotonic() - last_progress >= 30:
                            print(f"Downloading {target.name}: {transferred} bytes", flush=True)
                            last_progress = time.monotonic()
            temporary.replace(target)
            record = record_source(source_directory, url, target)
            print(
                f"Downloaded {target.name}: {record['bytes']} bytes sha256={record['sha256']}",
                flush=True,
            )
            return target
        except (requests.RequestException, OSError):
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Unreachable download retry state")


def loca_pieces(scenario: str, span: str) -> list[dict]:
    start, end = map(int, span.split("-"))
    periods = ["historical"] if scenario == "historical" else ["MID", "LATE"]
    pieces = []
    for period in periods:
        first, last = PERIODS[period]
        lo, hi = max(first, start), min(last, end)
        if lo > hi:
            continue
        origin = np.datetime64(f"{start}-01-01")
        begin = int((np.datetime64(f"{lo}-01-01") - origin).astype(int))
        stop = int((np.datetime64(f"{hi + 1}-01-01") - origin).astype(int))
        bounds = np.linspace(begin, stop, max(1, round((stop - begin) / (3 * 365))) + 1).astype(int)
        for a, b in zip(bounds[:-1], bounds[1:], strict=True):
            pieces.append(
                {
                    "scenario": scenario,
                    "period": period,
                    "span": span,
                    "days": (int(a), int(b)),
                    "name": f"{scenario}_{period}_{span}_{int(a)}_{int(b)}.npy",
                }
            )
    return pieces


@contextmanager
def local_loca2_open(run: str, span: str):
    import h5py

    path = Path(os.environ["FRI_CACHE"]) / "loca2/raw" / f"{run}_{span}.nc"
    if not path.is_file():
        raise ValueError(f"LOCA2 source must be fully downloaded before calculation: {path}")
    with h5py.File(path) as handle:
        yield handle


def landfire_tile(x0: float, y0: float, width: int, height: int) -> np.ndarray:
    import rasterio
    from fri_rebuild import data

    params = {
        "bbox": f"{x0},{y0},{x0 + width * data.PIXEL},{y0 + height * data.PIXEL}",
        "bboxSR": "5070",
        "imageSR": "5070",
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "U8",
        "interpolation": "RSP_NearestNeighbor",
        "f": "image",
    }
    url = requests.Request("GET", f"{data.LANDFIRE}/exportImage", params=params).prepare().url
    if url is None:
        raise ValueError("LANDFIRE request URL missing")
    path = download_raw(url, data.cache("landfire", f"raw_{x0}_{y0}.tiff"), 600)
    with rasterio.open(path) as handle:
        values = handle.read(1)
    if values.shape != (height, width):
        raise ValueError("LANDFIRE export dimensions do not match requested support")
    return values


def prepare_nex(data, workers: int) -> dict:
    jobs = []
    selection_path = data.cache("sources", "nex-file-selection.json")
    pinned = json.loads(selection_path.read_text())["selection"] if selection_path.exists() else {}
    for variable in ("tas", "pr"):
        for scenario in ("historical", "ssp245", "ssp585"):
            key = f"{variable}/{scenario}"
            keys = (
                {int(year): value for year, value in pinned[key].items()}
                if key in pinned
                else data.nex_newest_files(variable, scenario)
            )
            pinned[f"{variable}/{scenario}"] = keys
            for year in data.MONTHLY_YEARS[scenario]:
                if year not in keys:
                    raise ValueError(f"Missing NEX source year: {variable}/{scenario}/{year}")
                if not data.nex_path("monthly", variable, scenario, year).exists():
                    jobs.append((variable, scenario, year, keys[year], (False, True)))
    write_json(selection_path, {"selection": pinned})
    if jobs and not data.cache("nex", "grid.npz").exists():
        print(f"NEX grid seed: {data.nex_year(*jobs.pop(0))}", flush=True)
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(data.nex_year, *job) for job in jobs]
        for count, future in enumerate(as_completed(futures), 1):
            print(f"NEX monthly [{count}/{len(jobs)}] {future.result()}", flush=True)
    return {"sourceFiles": len(jobs), "variables": ["tas", "pr"]}


def prepare_fwi(data, inputs, workers: int) -> None:
    import h5py

    grid = np.load(data.cache("nex", "grid.npz"))

    def one(scenario, year):
        target = data.fwi_path("MME75", scenario, year)
        if target.exists():
            return
        url = data.FWI.format(ensemble="MME75", scenario=scenario, year=year)
        raw = download_raw(url, data.cache("fwi", "raw", f"{scenario}_{year}.nc"))
        with h5py.File(raw) as handle:
            rows, cols = data.box_slices(handle["lat"][:], handle["lon"][:])
            if not np.array_equal(handle["lat"][rows], grid["lat"]) or not np.array_equal(
                handle["lon"][cols], grid["lon"]
            ):
                raise ValueError("FWI and NEX coordinates differ; cannot reuse county weights")
            values = handle["FWI_P95"][rows, cols].astype(np.float32)
        values[np.abs(values) > 1e10] = np.nan
        np.savez(target, FWI_P95=values)
        raw.unlink()

    jobs = [(scenario, year) for scenario, years in data.HEAT_YEARS.items() for year in years]
    with ThreadPoolExecutor(min(workers, 3)) as pool:
        futures = [pool.submit(one, *job) for job in jobs]
        for count, future in enumerate(as_completed(futures), 1):
            future.result()
            print(f"FWI complete years [{count}/{len(jobs)}]", flush=True)
    inputs.county_fuel_shares()


def prepare_loca2(data, workers: int) -> None:
    spans = [(scenario, span) for scenario, values in data.LOCA2_SPANS.items() for span in values]
    partials = {}
    cells = None
    for scenario, span in spans:
        url = data.LOCA2.format(run=scenario, span=span)
        raw = data.cache("loca2", "raw", f"{scenario}_{span}.nc")
        print(f"LOCA2 full source {scenario}/{span}", flush=True)
        download_raw(url, raw, 600)
        if cells is None:
            cells, _, _ = data.loca2_cells()
        pieces = loca_pieces(scenario, span)
        with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork")) as pool:
            futures = {
                pool.submit(
                    data.loca2_piece, scenario, span, piece["days"], cells, piece["name"]
                ): piece
                for piece in pieces
            }
            for count, future in enumerate(as_completed(futures), 1):
                piece = futures[future]
                partials.setdefault((scenario, piece["period"]), []).append(future.result())
                print(f"LOCA2 pieces {scenario}/{span} [{count}/{len(pieces)}]", flush=True)
        raw.unlink()
    for (scenario, period), paths in partials.items():
        total = None
        for path in paths:
            counts = np.load(path).astype(np.uint32)
            total = counts if total is None else total + counts
        if total is None or total.max() > np.iinfo(np.uint16).max:
            raise ValueError("LOCA2 histogram count overflow or empty period")
        np.save(data.loca2_histogram_path(scenario, period), total.astype(np.uint16))


def checkpoint(cache: Path, uri: str, phase: str) -> None:
    inventory = {}
    files = [
        path
        for path in cache.rglob("*")
        if path.is_file()
        and not path.name.endswith((".partial", ".partial.npy", ".tmp.npy"))
        and "raw" not in path.relative_to(cache).parts
        and path.relative_to(cache).parts[:2] != ("nex", "tmp")
    ]
    with ThreadPoolExecutor(8) as pool:
        futures = []
        for path in files:
            name = path.relative_to(cache).as_posix()
            inventory[name] = sha256(path)
            futures.append(pool.submit(upload, path, f"{uri.rstrip('/')}/cache/{name}"))
        for future in futures:
            future.result()
    manifest = cache.parent / f"checkpoint-{phase}.json"
    write_json(manifest, {"phase": phase, "files": inventory})
    upload(manifest, f"{uri.rstrip('/')}/{manifest.name}")
    print(f"Checkpoint {phase}: {len(files)} immutable objects", flush=True)


def restore_checkpoint(uri: str, expected_sha: str, cache: Path) -> None:
    manifest = cache.parent / "resume.json"
    download(uri, manifest, expected_sha)
    prefix = uri.rsplit("/", 1)[0]
    files = json.loads(manifest.read_text())["files"]
    with ThreadPoolExecutor(8) as pool:
        futures = []
        for name, digest in files.items():
            target = (cache / name).resolve()
            if Path(name).is_absolute() or not target.is_relative_to(cache.resolve()):
                raise ValueError("Checkpoint path escapes cache directory")
            futures.append(pool.submit(download, f"{prefix}/cache/{name}", target, digest))
        for future in futures:
            future.result()
    print(f"Restored {len(files)} hash-verified cache objects", flush=True)


def run(
    run_id: str, input_uri: str, workers: int, resume_uri: str = "", resume_sha: str = ""
) -> None:
    validate_id(run_id)
    split_uri(f"{input_uri.rstrip('/')}/_validate")
    reference = ROOT / "pipeline/vendor/fri_rebuild"
    verify_reference(reference)
    cache = Path(os.environ.get("FRI_CACHE", "/tmp/fri-cache"))
    os.environ["FRI_CACHE"] = str(cache)
    sys.path.insert(0, str(reference.parent))
    from fri_rebuild import data, inputs

    data.download = download_raw
    data.loca2_open = local_loca2_open
    data.landfire_tile = landfire_tile
    acquisition_uri = f"{input_uri.rstrip('/')}/acquisitions/{run_id}"
    phase = "initial"
    try:
        if resume_uri:
            restore_checkpoint(resume_uri, resume_sha, cache)
        master_path = data.cache("answer_key", "master_datasheet.xlsx")
        # The pinned baseline is already baked into the worker image.
        baseline = ROOT / "public/NRI_Future_Risk_Master_Datasheet_12052024.xlsx"
        if sha256(baseline) != CONTRACT["workbookSha256"]:
            raise ValueError("Frozen workbook hash mismatch")
        shutil.copyfile(baseline, master_path)
        prepare_nex(data, workers)
        phase = "nex"
        inputs.county_weights()
        checkpoint(cache, acquisition_uri, phase)
        prepare_fwi(data, inputs, workers)
        phase = "wildfire"
        checkpoint(cache, acquisition_uri, phase)
        prepare_loca2(data, workers)
        phase = "loca2"
        checkpoint(cache, acquisition_uri, phase)
        sources = [
            json.loads(path.read_text())
            for path in sorted((cache / "sources").glob("*.json"))
            if path.name != "nex-file-selection.json"
        ]
        sys.path.insert(0, str(ROOT / "pipeline"))
        from export_snapshot import export_inputs

        snapshot = export_inputs(inputs, cache.parent / "snapshot", sources)
        verified = Snapshot(snapshot)
        # Force input coverage and schema checks before writing the completion marker.
        for scenario in inputs.SSP.values():
            for variable in ("tas", "pr"):
                verified.monthly(variable, scenario)
        for scenario, period in [
            ("historical", "historical"),
            *[(s, p) for s in inputs.SSP.values() for p in ("MID", "LATE")],
        ]:
            verified.fwi(scenario, period, "FWI_P95", "MME75")
            verified.loca2_histogram(scenario, period)
        verified.county_fuel_shares()
        snapshot_uri = f"{input_uri.rstrip('/')}/snapshots/{run_id}"
        for path in sorted(snapshot.parent.iterdir(), key=lambda p: p.name == "snapshot.json"):
            upload(path, f"{snapshot_uri}/{path.name}")
        result = cache.parent / "result.json"
        write_json(
            result,
            {
                "runId": run_id,
                "snapshotUri": f"{snapshot_uri}/snapshot.json",
                "snapshotSha256": sha256(snapshot),
                "sourceCount": len(sources),
                "methodology": CONTRACT["id"],
            },
        )
        upload(result, f"{acquisition_uri}/result.json")
        print(result.read_text(), flush=True)
    finally:
        checkpoint(cache, acquisition_uri, f"exit-{phase}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--input-uri", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--resume-uri", default="")
    parser.add_argument("--resume-sha256", default="")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between one and eight")
    if bool(args.resume_uri) != bool(args.resume_sha256):
        parser.error("resume requires both --resume-uri and --resume-sha256")
    run(args.run_id, args.input_uri, args.workers, args.resume_uri, args.resume_sha256)


if __name__ == "__main__":
    main()
