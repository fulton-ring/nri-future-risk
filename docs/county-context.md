# County descriptions

The panel gives a short, plain-language explanation of the place and the hazards
that matter there. Lead with recognizable cities, landscape, climate, homes or
farms. Include population or economic activity when it helps explain the risk,
rather than making each paragraph a checklist. Avoid percentile recitations,
industry lists and academic framing. The writing brief is
`docs/prompts/county-risk-context.md`.

All 3,218 archived county equivalents have individually written descriptions in
`public/context/counties.json`. Sources, evidence, dates and checked reference
risk values are retained in `scripts/county-context-research.json`. The prose is
shared across versions and filters; it explains the place rather than claiming
that one future category or multiplier applies to every scenario.

Population, geography and economic details come from the cited public sources.
The original research used the archived NRI v1.19 data to identify relevant
hazards. Those reference values remain checked against the original data, but
the public paragraph does not have to repeat them. Exact scores, formulas and
thresholds remain in the calculation panel and each version’s documentation.

## Refreshing descriptions

Collect or update evidence with the county context, population, economy and
agriculture scripts in `scripts/`. Keep source dates and pinned Wikipedia
revisions. Give writers the brief and per-county dossiers, retaining source
links and evidence alongside the new wording. Use `languageStyle: plain-place-context`
for these descriptions. Read them for plausible local connections without
inventing a cause for an exact model value.

`assemble_county_risk_context.py --check-only` validates complete county coverage,
source links, reference values, prose length and the plain-language guard.
The normal command publishes the checked research and public asset. Tests,
lint, builds and hosted checks also verify the output. The source baseline hash
must continue to match; rewriting prose never changes scientific data.
Wikipedia-derived text retains its source attribution and CC BY-SA 4.0 license.

## Planning regions and tracts

Connecticut’s nine native v1.20 planning regions have their own descriptions in
`public/context/planning-regions.json` and evidence in
`scripts/planning-region-context-research.json`. They do not inherit descriptions
of the retired counties.

Selecting a tract shows its own scores, followed by its containing county or
planning region’s description. The heading clearly labels that context as being
about the larger area. The parent ID is the tract GEOID’s first five digits.

Tract PMTiles include generalized overview geometry at low zoom and more detail
as the map zooms in. They retain exact map ratings and multipliers. Full numeric
values remain in verified profiles and source GeoParquet; zooming does not add
climate resolution.
