"""Build lossless archived attributes and score-bearing PMTiles. Requires tippecanoe."""
import hashlib
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
source = ROOT / 'public/combined_nri_counties_borders.json'
output = ROOT / 'public/atlas'
output.mkdir(exist_ok=True)
features = json.loads(source.read_text())['features']
counties, geometries = [], []
for feature in features:
    props = feature['properties']
    fips = props['STCOFIPS']
    coordinates = []
    def collect(value):
        if isinstance(value[0], (int, float)):
            coordinates.append(value)
        else:
            for child in value:
                collect(child)
    collect(feature['geometry']['coordinates'])
    # Handle counties spanning the antimeridian without zooming to the entire world.
    xs = [p[0] for p in coordinates]
    ys = [p[1] for p in coordinates]
    bounds = [min(xs), min(ys), max(xs), max(ys)]
    if bounds[2] - bounds[0] > 180:
        xs = [x + 360 if x < 0 else x for x in xs]
        bounds = [min(xs), min(ys), max(xs), max(ys)]
    values = {k: v for k, v in props.items() if k.startswith(('WFIR_', 'DRGT_', 'EXHT_', 'CFLD_', 'HRCN_'))}
    counties.append(dict(id=fips, name=props['COUNTY'], state=props['STATEABBRV'], bounds=bounds, values=values))
    geometries.append(dict(type='Feature', properties=dict(county_id=int(fips), fips=fips, name=props['COUNTY'], state=props['STATEABBRV'], **values), geometry=feature['geometry']))
assert len({c['id'] for c in counties}) == len(counties)
counties.sort(key=lambda c: (c['state'], c['name']))
# Columnar encoding keeps repeated field names out of the network payload.
columns = list(counties[0]['values'])
assert all(set(c['values']) == set(columns) for c in counties)
payload = {'columns': columns, 'counties': [{**c, 'values': [c['values'][k] for k in columns]} for c in counties]}
(output / 'counties.json').write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))
with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson') as handle:
    json.dump(dict(type='FeatureCollection', features=geometries), handle)
    handle.flush()
    subprocess.run(['tippecanoe', '-o', str(output / 'counties.pmtiles'), '-l', 'counties', '-Z0', '-z8', '--use-attribute-for-id=county_id', '--no-feature-limit', '--no-tile-size-limit', '--detect-shared-borders', '--force', handle.name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
manifest = dict(id='fema-2024-12-05', title='FEMA archived release', date='2024-12-05', baseline='NRI v1.19', status='archive', sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(), countyCount=len(counties), assets={name: dict(path=f'atlas/{name}', sha256=hashlib.sha256((output/name).read_bytes()).hexdigest()) for name in ['counties.json', 'counties.pmtiles']}, sourceLayer='counties')
(ROOT / 'src/data/release.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(f"Built {len(counties)} counties; source SHA-256: {manifest['sourceSha256']}")
