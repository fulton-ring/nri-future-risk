import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import { join } from 'node:path';

const output = 'public/versions';
await mkdir(join(output, 'fonts'), {recursive:true});
await copyFile('node_modules/@fontsource-variable/figtree/files/figtree-latin-wght-normal.woff2', join(output, 'fonts/figtree.woff2'));
await writeFile(join(output, 'style.css'), `@font-face{font-family:Figtree;src:url(fonts/figtree.woff2) format('woff2');font-weight:300 900}*{box-sizing:border-box}body{margin:0;background:#f4f1eb;color:#34332e;font:16px/1.65 Figtree,system-ui,sans-serif}main{max-width:880px;margin:auto;padding:40px 24px 72px}nav{display:flex;flex-wrap:wrap;gap:20px;font-size:14px;border-bottom:1px solid #cbc7be;padding-bottom:20px}a{color:#285b56;text-underline-offset:3px}h1{font-size:34px;line-height:1.15;margin-top:40px}h2{font-size:22px;margin-top:32px}code{overflow-wrap:anywhere;font-size:12px}li{margin:10px 0}.meta{font-size:14px;color:#67645d}.downloads a{display:block;margin:10px 0}footer{border-top:1px solid #cbc7be;margin-top:40px;padding-top:20px;font-size:13px}`);
const escape = (value) => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const technical = 'https://eelp.law.harvard.edu/wp-content/uploads/2025/03/NRI_Future_Risk_Technical_Document.pdf';
for (const filename of ['release.json']) {
  const release = JSON.parse(await readFile(join('src/data', filename),'utf8'));
  const dir = join(output, release.id);
  await mkdir(dir, {recursive:true});
  const title = 'FEMA archive · December 2024';
  const page = (kind, body) => `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${kind} — ${escape(title)} — Future Risk Index</title><link rel="stylesheet" href="../style.css"></head><body><main><nav aria-label="Version navigation"><a href="../../?release=${encodeURIComponent(release.id)}">← Explorer</a><a href="methodology.html">Methodology</a><a href="data.html">Data</a></nav><h1>${kind}</h1><p class="meta">${escape(title)}<br><code>${escape(release.id)}</code></p>${body}<footer>Future Risk Index · Maintained by Public Environmental Data Partners and Fulton Ring.</footer></main></body></html>`;
  const methods = `
    <h2>Archived FEMA release</h2><p>This version preserves FEMA’s December 5, 2024 Future Risk Index master datasheet using the NRI v1.19 baseline. Its published county attributes are displayed without recalculating hazard projections or scientific values.</p><p>The archive includes drought, wildfire, extreme heat, coastal flooding and hurricane. Heat includes the archived LOCA and NEX 95th/99th-percentile variants. These are reference projections rather than present-day observations.</p>
    <h2>Original methodology</h2><p><a href="${technical}">Read FEMA’s Future Risk Index technical document</a> for the original models, historical reference periods, projection periods and equations. The archive’s scenario families are SSP2-4.5/SSP5-8.5 for drought, heat and wildfire; RCP 4.5/8.5 for hurricane; and intermediate/high sea-level-rise scenarios for coastal flooding.</p>
    <h2>Display conversion</h2><p>County attributes are preserved in JSON and score-bearing PMTiles. Geometry is generalized for map display; the scores are not. All 3,218 archived county geometries remain available. Source SHA-256: <code>${escape(release.sourceSha256)}</code>.</p>
    <h2>Interpretation</h2><p>The estimates keep baseline exposure and social conditions fixed. County categories are not event probabilities. Zooming into the map adds geographic context rather than scientific resolution.</p>`;
  const data = `<h2>County data</h2><p>Original FEMA county attributes for the five archived hazards.</p><p>${release.countyCount.toLocaleString('en-US')} county geometries · ${escape(release.baseline)}</p><div class="downloads"><a href="../../NRI_Future_Risk_Master_Datasheet_12052024.xlsx" download>FEMA master datasheet</a><a href="../../${release.assets['counties.json'].path}">County attributes — columnar JSON</a><a href="../../${release.assets['counties.pmtiles'].path}" download>Map tiles — PMTiles</a><a href="../../NRI_Data_Dictionary.xlsx" download>FEMA data dictionary</a></div><h2>Integrity</h2><p>Archived source GeoJSON SHA-256: <code>${escape(release.sourceSha256)}</code></p><p>PMTiles SHA-256: <code>${escape(release.assets['counties.pmtiles'].sha256)}</code></p><p><a href="methodology.html">Read this version’s methodology</a> before interpreting or reusing the data.</p>`;
  await writeFile(join(dir,'methodology.html'),page('Methodology',methods));
  await writeFile(join(dir,'data.html'),page('Data',data));
}
