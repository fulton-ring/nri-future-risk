# County risk context

The county panel contains individually researched 1–2 sentence narratives for all
3,218 selectable counties and county equivalents. They sit below the score
overview and synthesize local economy, demographics and relevant geography with
actual FEMA baseline results. They are not population-and-industry templates.

The exact writing brief is in `docs/prompts/county-risk-context.md`. Source links,
short supporting evidence and structured comparisons are retained in
`scripts/county-context-research.json`. The public `context/counties.json` asset
contains the reviewed prose and comparison proofs. It is fetched once and cached;
visitors make no LLM or external-source requests.

## What the comparisons mean

Legacy county comparisons explicitly refer to the archived NRI v1.19 baseline,
which is identical across the archive and v1.19 analysis releases. The v1.20 view
labels those older comparisons; the nine new planning regions use native v1.20
comparisons instead. The narrative does
not assert that a fixed projected rank applies to every hazard/filter/scenario.
FEMA risk percentiles are distinct from dollar loss, published rating categories,
and probabilities. Computed loss percentiles compare the 3,218 mapped counties;
FEMA's published national risk percentiles retain their original universe.

A valid score is required before making a low/high-risk comparison. Unrated
Puerto Rico cases use sourced local exposure context and do not imply safety.
Drought comparisons concern agricultural losses; a manufacturing earnings share
is not a modeled drought loss. Coastal flooding is not river flooding. Context
is not a causal attribution or a change to the model's baseline inputs.

## Sources and refresh

1. Collect public evidence with `collect_county_context.py`,
   `collect_county_population.py`, and `collect_county_economy.py` in `scripts/`.
   Current Census population estimates cover every mapped FIPS, with dated legacy
   Connecticut estimates rather than remapping planning regions. BEA workplace
   earnings are not worker counts or GDP; suppression is preserved. Locality
   research covers combined-region gaps without assigning region totals to cities.
2. Supplement farm/crop context with USDA's 2022 Ag Census Web Maps workbook:
   `https://www.nass.usda.gov/sites/default/files/publications/agcensus/2022/Online_Resources/Ag_Census_Web_Maps/Data_download/NASSAgCensusDownload2022_175maps_Links.xlsx`.
   Save it as `/tmp/fri-county-research/agriculture.xlsx`, then run
   `python scripts/collect_county_agriculture_context.py`. Preserve metric dates
   and denominators; harvested cropland and orchard percentages are not county
   land shares. Suppressed/missing values are not zero. This extraction excludes
   Alaska, Virginia and Puerto Rico to avoid ambiguous agricultural geographies.
3. Run `python scripts/prepare_county_context_research.py` from the repository
   root. It uses cached Wikipedia/BEA/Census evidence under `/tmp`, verifies
   baseline loss equality across archive/analysis, and prepares bounded per-county
   dossiers plus eight assignments under `/tmp/fri-county-research`.
4. Give research agents the full brief, dossiers, full pinned articles and USDA
   facts. Require original prose, citations, claim evidence and structured
   comparison proofs. Inspect thin profiles and factual/causal language. Do not
   generate sector-list templates or infer local characteristics from state names.
5. Run `python scripts/assemble_county_risk_context.py --check-only` and then
   `python scripts/assemble_county_risk_context.py`. Publication requires all
   FIPS, source links, exact comparison values, valid percentile thresholds and
   explicit baseline language. The asset is bound to its baseline file hash.
6. Run tests, lint and the static build; check the browser and preview HTTP checks.

The old economy-template updater refuses to overwrite reviewed research. Refreshing
source evidence alone must not silently replace the prose. Sources in the panel
attribute Wikipedia-derived text under CC BY-SA 4.0; the code license is unchanged.

## Connecticut planning regions

The nine native NRI v1.20 planning-region IDs have separate researched context in
`public/context/planning-regions.json`. The panel loads it for 09110–09190 rather
than assigning retired county narratives to new boundaries. Descriptions use
Census July 2025 region population estimates, cited regional economic-development
sources, and exact native v1.20 baseline comparisons; evidence and source hashes
are in `scripts/planning-region-context-research.json`. They appear below the
headline values, just like county descriptions. Tract profiles show their containing county or planning region’s description,
clearly labeled as county/region context below the tract’s own headline scores.
The parent ID is the tract GEOID’s first five digits; no county-level narrative
is presented as tract-specific research. The archived county asset and its v1.19 comparisons stay
unchanged.

Tract boundaries are generalized in the PMTiles overview at low zoom; detailed
boundaries remain available as the map zooms in. Map tiles retain every rating and
multiplier used by the controls; full exact numeric values remain in the verified
profile assets and source GeoParquet.
