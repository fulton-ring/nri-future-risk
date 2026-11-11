#!/usr/bin/env python3
"""Collect Census population estimates without an API key or boundary remapping."""
import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://www2.census.gov/programs-surveys/popest/datasets/'
FILES = [
    ('2020-2025/counties/totals/co-est2025-alldata.csv', 2025, 'county'),
    ('2020-2025/puerto-rico/asrh/cc-est2025-agesex-72.csv', 2025, 'municipio'),
    ('2010-2020/counties/totals/co-est2020-alldata.csv', 2020, 'legacy'),
]


def main():
    expected = {c['id'] for c in json.loads((ROOT/'public/atlas/counties.json').read_text())['counties']}
    result = {}
    for path, year, kind in FILES:
        url = BASE + path
        request = urllib.request.Request(url, headers={'User-Agent': 'FutureRiskIndex/1.0 (county population context)'})
        with urllib.request.urlopen(request, timeout=60) as response:
            rows = csv.DictReader(io.StringIO(response.read().decode('latin1')))
            for row in rows:
                if row['SUMLEV'] != '050':
                    continue
                if kind == 'municipio':
                    if row['YEAR'] != '7':  # July 1, 2025, per the Vintage 2025 file layout.
                        continue
                    fips, number = '72' + row['MUNICIPIO'], int(row['POPESTIMATE'])
                else:
                    fips, number = row['STATE'] + row['COUNTY'], int(row[f'POPESTIMATE{year}'])
                    if kind == 'legacy' and not fips.startswith('09'):
                        continue
                if fips not in expected or fips in result:
                    continue
                if number <= 0:
                    raise ValueError(f'Invalid population for {fips}')
                result[fips] = {'population': number, 'year': year, 'kind': 'estimate',
                                'date': f'July 1, {year}', 'source': {
                                    'title': f'U.S. Census Bureau population estimate ({year})', 'url': url}}
    if set(result) != expected:
        raise ValueError(f'Missing population estimates: {sorted(expected-result.keys())}')
    output = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/fri-county-economy/population.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {len(result)} population estimates to {output}')


if __name__ == '__main__':
    main()
