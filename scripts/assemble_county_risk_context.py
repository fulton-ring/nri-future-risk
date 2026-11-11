#!/usr/bin/env python3
"""Validate agent-authored county context against actual baseline comparisons."""
import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
RELATIONS = {
    'top10': lambda n: n >= 90, 'top25': lambda n: n >= 75,
    'aboveMedian': lambda n: n >= 50, 'belowMedian': lambda n: n < 50,
    'bottom25': lambda n: n <= 25, 'bottom10': lambda n: n <= 10,
}


def format_percentages(text):
    return re.sub(r'(\d+(?:\.\d+)?)(\s*)(%|percent\b)',
                  lambda match: format(float(match[1]), '.3g') + match[2] + match[3], text)


def validate(record, dossier):
    text = record['description']
    assert isinstance(text, str) and 80 <= len(text) <= 750, 'description length'
    assert not re.search(r'\[\[|\]\]|\{\{|\}\}|<ref|\|', text), 'source markup leaked into prose'
    assert record.get('sources') and record.get('evidence'), 'sources and supporting evidence required'
    assert 'Census estimated about' not in text, 'old template was retained'
    for source in record['sources']:
        url = urlparse(source['url'])
        assert url.scheme == 'https' and url.hostname, 'source must use HTTPS'
        if url.hostname == 'en.wikipedia.org':
            assert parse_qs(url.query).get('oldid', [''])[0].isdigit(), 'Wikipedia revision must be pinned'
    comparisons = record.get('comparisons', [])
    for comparison in comparisons:
        kind = comparison['kind']
        if kind in {'riskPercentile', 'lossPercentile', 'populationPercentile'}:
            if kind == 'populationPercentile':
                expected = dossier['population']['percentileAmongMappedCounties']
            else:
                field = 'nationalRiskScore' if kind == 'riskPercentile' else 'lossPercentileAmongMapped3218'
                expected = dossier['baselineNRIv119'][comparison['hazard']][field]
            assert expected is not None and abs(expected-comparison['value']) < 1e-7, 'comparison does not match source'
            assert RELATIONS[comparison['relation']](expected), 'percentile language contradicts source'
        elif kind == 'riskContrast':
            expected = [dossier['baselineNRIv119'][h]['nationalRiskScore'] for h in comparison['hazards']]
            assert len(expected) == 2 and all(v is not None for v in expected), 'unrated hazard in contrast'
            assert expected == comparison['values'], 'contrast values do not match source'
        elif kind == 'lossPeer':
            peer = dossier['similarPopulationPeerSameState']
            hazard = comparison['hazard']
            assert peer and comparison['peerId'] == peer['id'], 'wrong peer'
            county_value = dossier['baselineNRIv119'][hazard]['annualLoss']
            peer_value = peer['baseline'][hazard]['annualLoss']
            assert comparison['countyValue'] == county_value and comparison['peerValue'] == peer_value, 'peer values do not match source'
            assert (county_value > peer_value if comparison['relation'] == 'above' else county_value < peer_value), 'peer comparison direction'
        else:
            raise AssertionError(f'Unsupported comparison: {kind}')
        if kind != 'populationPercentile':
            assert 'baseline' in text.lower(), 'baseline comparison must be explicit in prose'
    if any(v['nationalRiskScore'] is not None for v in dossier['baselineNRIv119'].values()):
        assert any(c['kind'] != 'populationPercentile' for c in comparisons), 'actual-risk comparison missing'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, default=Path('/tmp/fri-county-research'))
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    expected = {c['id'] for c in json.loads((ROOT/'public/atlas/counties.json').read_text())['counties']}
    records, errors = {}, []
    for path in sorted(args.workdir.glob('descriptions-*.json')):
        if not path.stem.removeprefix('descriptions-').isdigit():
            continue
        for fips, record in json.loads(path.read_text()).items():
            assert fips not in records, f'Duplicate FIPS {fips}'
            record['description'] = format_percentages(record['description'])
            records[fips] = record
            try:
                dossier = json.loads((args.workdir/'dossiers'/f'{fips}.json').read_text())
                validate(record, dossier)
            except (AssertionError, KeyError, TypeError, ValueError) as error:
                errors.append({'id': fips, 'file': path.name, 'error': str(error)})
    (args.workdir/'validation-errors.json').write_text(json.dumps(errors, indent=2)+'\n')
    print(f'Validated {len(records)}/{len(expected)} narratives; {len(errors)} errors')
    if errors:
        raise ValueError(f'See {args.workdir / "validation-errors.json"}')
    if args.check_only:
        assert args.allow_partial or set(records) == expected, 'Incomplete FIPS coverage'
        return
    assert not args.allow_partial and set(records) == expected, 'Publishing requires complete FIPS coverage'
    basis = json.loads((args.workdir/'basis.json').read_text())
    assert hashlib.sha256((ROOT/basis['baselineFile']).read_bytes()).hexdigest() == basis['baselineSha256'], 'Baseline data changed; regenerate comparisons'
    research = {'schemaVersion': 1, 'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'prompt': 'docs/prompts/county-risk-context.md', 'baseline': basis, 'counties': dict(sorted(records.items()))}
    destination = ROOT/'scripts/county-context-research.json'
    destination.write_text(json.dumps(research, ensure_ascii=False, indent=2)+'\n')
    asset_path = ROOT/'public/context/counties.json'
    asset = json.loads(asset_path.read_text())
    for fips, record in records.items():
        entry = asset['counties'][fips]
        entry['description'] = record['description']
        sources = list(record['sources'])
        if any(c['kind'] != 'populationPercentile' for c in record.get('comparisons', [])):
            sources.append({'title': 'Archived FEMA baseline results used for these comparisons', 'url': basis['riskSourceUrl']})
        entry['sources'] = list({s['url']: s for s in sources}.values())
        entry.pop('riskContext', None)
        entry['researchComparisons'] = record.get('comparisons', [])
        entry['sourceNote'] = 'Risk comparisons refer to the archived FEMA NRI v1.19 baseline, not a fixed future scenario. Population, economic and geographic facts provide context; they do not establish what caused a score or replace the model’s baseline inputs.'
        entry['attribution'] = 'Researched and written by AI from the cited public sources; Wikipedia-derived wording has been changed.'
    asset['generatedAt'] = research['generatedAt']
    asset['authoringMethod'] = 'researched-risk-context'
    asset['researchBaseline'] = basis
    asset['contextMethod'] = 'Individually researched county narratives with source-checked baseline comparisons; shared across versions and filters.'
    asset_path.write_text(json.dumps(asset, ensure_ascii=False, indent=2)+'\n')
    print(f'Published {len(records)} researched county narratives')


if __name__ == '__main__':
    main()
