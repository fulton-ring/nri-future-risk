# Recreated projections using NRI v1.20

This version is separate from the December 2024 FEMA archive and the v1.19-based
reconstruction. It changes the economic/social baseline and the geographic units;
differences between releases are not observed changes in climate damage over time.

## Baseline and geography

The original FEMA December 2025 NRI v1.20 county and census-tract ZIPs are pinned
by SHA-256 in `reference/current-contract.json`. Their national inventories contain
3,232 county-equivalent areas and 85,154 census tracts. The heat-wave `HWAV` fields
are renamed `EXHT` for compatibility with the interface; values are not transformed.

Connecticut uses its nine planning regions (09110–09190), including 879 tracts.
Census 2024 cartographic boundary files supply the matching polygons. Native
baseline rows, missing values, and status labels are retained. Source ZIPs and
processed baseline tables accompany the results.

## Climate projections

The verified full-year MME50/annual-mean FWI snapshot supplies the same exact
analysis-ready climate arrays used in the previous reconstruction. It also contains
NEX monthly temperature/precipitation and LOCA2 tasmin histograms. Its source
fingerprints, original NetCDF archives and analysis-ready Zarr remain available in
the previous immutable public results version. This calculation records that exact
snapshot URL and hash rather than downloading a new climate ensemble.

Each county and tract gets its own sparse polygon/cell overlap weights in EPSG:5070.
Both grids retain the previous 0.25-degree weighting boxes, including around LOCA2
centers. This is a tract aggregation of existing climate information, not new
statistical or dynamical climate downscaling. Nearby small tracts may have nearly
identical multipliers; their exposure and vulnerability can nevertheless differ.

Drought retains SPEI-3, the −1.6 event threshold and the historical 15-day denominator
floor over the entire 1985–2014 period. Heat retains historical percentile event days,
the future 23.07°C minimum-temperature screen, and a minimum applied multiplier of
one. See `drought.py` and `heat.py` for the unchanged scientific calculations.

Wildfire retains the county-mean future/historical FWI ratio raised to fitted gamma.
Gamma is refitted using v1.20 **county** wildfire annual losses, historical county
FWI, and LF2022 fuel-share controls with burnable-share weighting. The same gamma
is applied to tract FWI ratios; there is no tract-level regression. LF2022's exact
archived 500m raster tiles are reused to calculate shares over the new county boundaries.
Wildfire multipliers below one are rejected, not silently clipped.

## Losses, values, scores and categories

For each supported area and scenario:

- Projected annual loss = native v1.20 hazard annual loss × hazard multiplier.
- Projected risk value = native v1.20 hazard risk value × hazard multiplier.
- Projected risk score = percentile rank of projected risk value among supported
  CONUS areas of the **same geography**, separately for each scenario. Zero ties
  participate; missing risk values do not.
- Category thresholds are recovered from the matching **national native v1.20**
  baseline ratings. Tract thresholds do not reuse county thresholds. Exact cutoff
  ties stay in the lower category, matching the existing scoring convention.

Baseline risk scores retain FEMA's national population. Future comparisons cover
3,109 CONUS county equivalents and 83,481 CONUS tracts, subject to native missing
baseline values. Outside CONUS, future multipliers, projections and scores remain
unavailable; native baseline values remain accessible. No multiplier of one is
invented to fill absent climate coverage. Coastal flooding, hurricane and NEX heat
future projections are not recalculated by this version.

Risk value is a vulnerability/resilience-adjusted loss index, not another estimate
of annual dollar damage. Risk score is the separate 0–100 percentile. Different
geographic populations and changing rank distributions prevent direct comparison
of a county percentile with a tract percentile.

## Reproduction and review

`python -m fri_pipeline.current_cloud` renders/submits a bounded Cloud Batch job.
`current_run` acquires hash-checked inputs, then executes `current_flow` through
Apache Hamilton. Exact baseline tables, original NRI ZIPs, new overlap matrices,
ordered area IDs, county fuel shares, thresholds, validation and provenance are
packaged with separate county and tract GeoParquet files.

The catalog layout is `future-risk-index/<dataset>/<file>/<version>/`:
`fri/counties/<version>/`, `fri/tracts/<version>/`, and native baseline datasets
`nri/counties/<version>/`, `nri/tracts/<version>/`. Existing releases are immutable.
A calculation writes only to its run-specific experiments prefix. Results require
review before promotion to the public results bucket, staging conversion, or an
approved map release. Running the workflow does not activate publication.
