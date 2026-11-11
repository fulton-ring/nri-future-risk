#!/usr/bin/env python3
"""Build economy-first prose from Census/BEA facts and reviewed local descriptions."""
import argparse
import datetime
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    '81': 'farming', '100': 'forestry, fishing and related services',
    '200': 'mining and energy extraction', '300': 'utilities', '400': 'construction',
    '500': 'manufacturing', '600': 'wholesale trade', '700': 'retail',
    '800': 'transportation and warehousing', '900': 'information services',
    '1000': 'finance and insurance', '1100': 'real estate and rental services',
    '1200': 'professional and technical services', '1300': 'corporate management',
    '1400': 'business support and waste services', '1500': 'private education',
    '1600': 'healthcare and social services', '1700': 'arts, entertainment and recreation',
    '1800': 'lodging and food services', '1900': 'other private services',
    '2000': 'government work',
}


def compact_population(number):
    step = 10 ** max(0, math.floor(math.log10(number)) - 2)
    return f'{int(math.floor(number/step+0.5)*step):,}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, default=Path('/tmp/fri-county-economy'))
    args = parser.parse_args()
    if (ROOT/'scripts/county-context-research.json').exists():
        raise SystemExit('County context now uses researched narratives. Refresh research inputs and run assemble_county_risk_context.py; economy templates must not overwrite the reviewed prose.')
    target = ROOT/'public/context/counties.json'
    asset = json.loads(target.read_text())
    population = json.loads((args.workdir/'population.json').read_text())
    bea = json.loads((args.workdir/'bea-facts.json').read_text())
    overrides = json.loads((ROOT/'scripts/county-economy-overrides.json').read_text())
    for fips, entry in asset['counties'].items():
        entry.pop('riskContext', None)
        pop = population[fips]
        intro = f"Census estimated about {compact_population(pop['population'])} residents in {pop['year']}."
        sources = [{'title': f"U.S. Census Bureau population estimate ({pop['year']})", 'url': pop['source']['url']}]
        income = bea['counties'].get(fips, {}).get('income')
        entry['population'] = {'value': pop['population'], 'year': pop['year'], 'date': pop['date'],
                               'kind': pop['kind'], 'sourceUrl': pop['source']['url']}
        if income:
            rows = income['industryEarnings']
            if {r['lineCode'] for r in rows} != set(LABELS):
                raise ValueError(f'Incomplete industry definitions for {fips}')
            sectors = sorted((r for r in rows if r['thousandDollars'] is not None and r['thousandDollars'] > 0),
                             key=lambda r: r['thousandDollars'], reverse=True)[:3]
            if not sectors:
                raise ValueError(f'No published positive industry earnings for {fips}')
            names = [LABELS[r['lineCode']] for r in sectors]
            joined = names[0] if len(names) == 1 else ' and '.join(names) if len(names) == 2 else ', '.join(names[:-1]) + ' and ' + names[-1]
            prose = f"Local sources of earnings in {income['year']} included {joined}."
            entry['economy'] = {'year': income['year'], 'measure': 'earningsByPlaceOfWork',
                                'hasSuppressedSectors': any(r['thousandDollars'] is None for r in rows),
                                'sectors': [{'lineCode': r['lineCode'], 'label': LABELS[r['lineCode']],
                                             'thousandDollars': r['thousandDollars']} for r in sectors]}
            sources.append({'title': f"BEA local earnings by industry ({income['year']})",
                            'url': bea['source']['incomeTable']['url']})
            entry['sourceNote'] = 'Industries shown have published earnings by place of work, including wages, benefits and proprietor income. Suppressed values are omitted; this is not a complete ranking or a count of resident workers.'
        else:
            if fips not in overrides:
                raise ValueError(f'No locality-specific economic description for {fips}')
            prose = overrides[fips]['description']
            entry['economy'] = {'measure': 'localSourceDescription'}
            entry['sourceNote'] = 'The economic description uses locality-specific public sources; combined county/city BEA figures are not assigned to individual places.'
        if fips in overrides:
            prose = overrides[fips]['description']
            sources.extend(overrides[fips]['sources'])
            if 'riskContext' in overrides[fips]:
                entry['riskContext'] = overrides[fips]['riskContext']
        entry['description'] = intro + ' ' + prose
        if pop['year'] < 2025:
            entry['sourceNote'] += ' Population uses a 2020 estimate for this legacy Connecticut county; current Census estimates use planning regions instead.'
        entry['sources'] = list({source['url']: source for source in sources}.values())
        entry['attribution'] = ('Adapted from Wikipedia and public data; wording changed.'
                                if any('en.wikipedia.org/' in s['url'] for s in entry['sources'])
                                else 'Summarized from public population and economic sources.')
    asset['generatedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    asset['license']['attribution'] = 'Population and earnings summaries use U.S. Census Bureau and BEA data. Some local descriptions adapt cited Wikipedia text; wording has been changed.'
    asset['contextMethod'] = 'Population and economic context are separate from version-specific risk-model inputs.'
    target.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + '\n')
    print(f"Updated {len(asset['counties'])} economy-first county descriptions")


if __name__ == '__main__':
    main()
