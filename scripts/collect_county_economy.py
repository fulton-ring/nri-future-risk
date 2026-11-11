#!/usr/bin/env python3
"""Collect BEA county earnings-by-industry bulk data.

Downloads BEA's public county archives and writes a compact JSON keyed by the
project's selectable FIPS codes. No API key is required. Suppressed/unavailable
values remain null; no boundary remapping is attempted.
"""
from __future__ import annotations
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path('/tmp/fri-county-economy/bea-facts.json')
INCOME_URL = "https://apps.bea.gov/regional/zip/CAINC5N.zip"
# CAINC5N top-level place-of-work earnings categories. Codes are distinct
# table line codes; more detailed subindustries are excluded to avoid double count.
EARNINGS_LINES = {"81", *(str(n) for n in range(100, 2001, 100))}
YEAR_RE = re.compile(r"^\d{4}$")


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "county-economy-data-collector/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def rows_by_fips(archive: bytes, prefix: str, fips: set[str]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for name in zf.namelist():
            if not (name.startswith(prefix + "_") and name.endswith(".csv") and "__" not in name):
                continue
            with zf.open(name) as stream:
                text = io.TextIOWrapper(stream, encoding="latin-1", newline="")
                for row in csv.DictReader(text):
                    f = row["GeoFIPS"].strip().strip('"')
                    if f in fips:
                        result.setdefault(f, []).append(row)
    return result


def value(row: dict[str, str], year: str) -> int | None:
    raw = row.get(year, "").strip()
    if not raw or raw in {"(D)", "(NA)", "(L)", "(NM)", "--"}:
        return None
    raw = raw.replace(",", "")
    try:
        return int(raw)
    except ValueError:
        try:
            return int(float(raw))
        except ValueError:
            return None


def latest_year(rows: list[dict[str, str]]) -> str | None:
    years = sorted({k for row in rows for k in row if YEAR_RE.fullmatch(k)})
    for year in reversed(years):
        if any(value(r, year) is not None for r in rows):
            return year
    return None


def select_row(rows: list[dict[str, str]], predicate) -> dict[str, str] | None:
    return next((r for r in rows if predicate(r)), None)


def main() -> None:
    outpath = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    context = json.loads((ROOT / "public/context/counties.json").read_text())
    fips = set(context["counties"])
    print("Downloading BEA CAINC5N archive…", file=sys.stderr)
    inc_rows = rows_by_fips(download(INCOME_URL), "CAINC5N", fips)
    result: dict[str, dict] = {}
    for f in sorted(fips):
        inc = inc_rows.get(f, [])
        record: dict = {}
        if inc:
            year = latest_year(inc)
            earnings = select_row(inc, lambda r: r["LineCode"] == "35")
            industry_rows = []
            if year:
                for r in inc:
                    if r["LineCode"] in EARNINGS_LINES:
                        amount = value(r, year)
                        industry_rows.append({"lineCode": r["LineCode"], "naics": r["IndustryClassification"].strip().strip('"'), "name": r["Description"].strip(), "thousandDollars": amount})
            if len(industry_rows) != len(EARNINGS_LINES):
                raise ValueError(f'Incomplete earnings sector definitions for {f}')
            record["income"] = {"year": int(year) if year else None,
                                "earningsByPlaceOfWorkThousandDollars": value(earnings, year) if earnings and year else None,
                                "industryEarnings": industry_rows}
        if record:
            result[f] = record
    payload = {"source": {
        "provider": "U.S. Bureau of Economic Analysis, Regional Data",
        "incomeTable": {"title": "Personal Income by County, Metro, and Other Areas (CAINC5N)", "url": INCOME_URL, "definitionUrl": "https://apps.bea.gov/regional/zip/CAINC5N__definition.xml", "semantics": "industry earnings are measured by place of work, not job or resident-worker counts; population and personal income refer to residence"},
        "downloaded": __import__("datetime").date.today().isoformat(),
        "unmatchedFips": sorted(fips - result.keys())
    }, "counties": result}
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(result)}/{len(fips)} FIPS rows to {outpath}", file=sys.stderr)

if __name__ == "__main__":
    main()
