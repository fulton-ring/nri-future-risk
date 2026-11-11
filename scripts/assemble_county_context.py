#!/usr/bin/env python3
"""Assemble agent-authored county prose and pinned Wikipedia attribution.

Run collect_county_context.py first. Have writing agents produce descriptions-N.json
objects mapping FIPS to prose in the same working directory, then run this script.
No model calls or external requests are made by this assembly step.
"""
import argparse
import datetime
import json
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, default=Path('/tmp/fri-county-context'))
    parser.add_argument('--output', type=Path, default=ROOT / 'public/context/counties.json')
    args = parser.parse_args()
    sources = json.loads((args.workdir / 'sources.json').read_text())
    enrichment_file = args.workdir / 'enrichment.json'
    if not enrichment_file.exists():
        enrichment_file = ROOT / 'scripts/county-context-enrichment.json'
    enrichment = json.loads(enrichment_file.read_text())
    inventory = json.loads((ROOT / 'public/atlas/counties.json').read_text())['counties']
    drafts = {}
    for file in sorted(args.workdir.glob('descriptions-*.json')):
        if not file.stem.removeprefix('descriptions-').isdigit():
            continue
        entries = json.loads(file.read_text())
        overlap = drafts.keys() & entries.keys()
        if overlap:
            raise ValueError(f'Duplicate drafts in {file}: {sorted(overlap)}')
        drafts.update(entries)
    expected = {county['id'] for county in inventory}
    if set(drafts) != expected:
        raise ValueError(f'Draft coverage: missing {sorted(expected-set(drafts))}; extra {sorted(set(drafts)-expected)}')
    counties = {}
    for fips in sorted(expected):
        evidence = sources[fips]
        if evidence.get('missing') or not evidence.get('revisionId') or not evidence.get('url'):
            raise ValueError(f'No verified source for {fips}')
        description = drafts[fips].strip()
        if not 80 <= len(description) <= 800:
            raise ValueError(f'Description length for {fips}: {len(description)}')
        counties[fips] = {
            'description': description,
            'sources': [{
                'title': f"Wikipedia: {evidence['title']}",
                'url': 'https://en.wikipedia.org/w/index.php?' + urlencode({
                    'title': evidence['title'], 'oldid': evidence['revisionId']}),
                'revisionId': evidence['revisionId'],
            }],
        }
        counties[fips]['sources'].extend(enrichment.get(fips, {}).get('sources', []))
    asset = {
        'schemaVersion': 1,
        'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'license': {
            'name': 'CC BY-SA 4.0',
            'url': 'https://creativecommons.org/licenses/by-sa/4.0/',
            'attribution': 'Adapted from Wikipedia by AI writing agents; wording has been changed. Article history credits the contributors.',
        },
        'counties': counties,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {len(counties)} sourced county descriptions to {args.output}')


if __name__ == '__main__':
    main()
