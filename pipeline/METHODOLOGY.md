# County Future Risk Index methodology

This document describes the implemented county pipeline, its frozen scientific contract,
and the separate available-year analysis. Operational commands and the storage layout are
in [README.md](README.md). The website's version-specific Methodology and Data pages are
part of the UI branch, not this pipeline PR.

## Reference and scope

The reference is FEMA's December 2024 Future Risk Index workbook and National Risk Index
v1.19. [contract.json](reference/contract.json) pins their hashes, the county geometry,
the original technical document, and the reconstruction and verification commits from
[the verification spike](https://github.com/fulton-ring/agent-content-demos/pull/120).
The [original FEMA technical document](https://eelp.law.harvard.edu/wp-content/uploads/2025/03/NRI_Future_Risk_Technical_Document.pdf)
remains the source methodology; this implementation does not claim a new national model.

The pipeline updates drought, wildfire and LOCA2 extreme heat for 3,108 CONUS counties.
The full frozen scoring population has 3,231 counties; 3,218 have archived geometry.
Coastal flooding, hurricane and NEX heat retain archived values. Non-CONUS multipliers
also remain archived, while supported risk ranks are recomputed nationally. Consequently,
a non-CONUS rank can change without its multiplier changing.

Future scenarios are SSP2-4.5 and SSP5-8.5, each for mid-century (2036–2065) and late-century
(2070–2099). Historical reference periods differ by hazard. Baseline exposure, population,
social vulnerability and community resilience remain fixed. The outputs do not model future
population growth, development, land use or adaptation, and are county estimates rather than
property-level predictions.

## Drought

[drought.py](fri_pipeline/drought.py) uses NEX-GDDP-CMIP6 MPI-ESM1-2-HR monthly temperature
and precipitation. It calculates Thornthwaite potential evapotranspiration with latitude/daylight
and calendar-month corrections, then accumulates the precipitation-minus-PET balance over
three months. The SPEI transformation fits each calendar month separately over 1950–2010,
using the implementation's generalized-logistic probability-weighted-moment fit and a normal
quantile transform.

A month with SPEI ≤ −1.6 counts all its calendar days as drought days. The historical period
is 1985–2014. The grid-cell multiplier is the future drought-day rate divided by the historical
rate, with a denominator floor of 15 historical drought days. Cell multipliers are averaged
using county area weights over valid support; the resulting county multiplier is floored at one.

## Extreme heat

[heat.py](fri_pipeline/heat.py) uses LOCA2 MPI-ESM1-2-HR daily minimum-temperature histograms.
Historical 95th- and 99th-percentile thresholds use 1976–2005. Percentile positions and the
296.22 K (23.07°C) temperature floor are interpolated within the original 0.1°C histogram bins.

Future event days exceed both the historical percentile and the temperature floor. The
historical denominator counts days above the historical percentile alone. Event-day totals
are area-weighted to counties; the multiplier is the future county mean divided by its
historical counterpart, floored at one. Both periods retain the original 30-year spans.

LOCA2 source centers are on a 1/16-degree grid, but the frozen county weighting uses
0.25-degree boxes. That weighting is retained for comparability; the results do not establish
6 km county-level spatial support. Valid weighting support varies by county, down to 51.3%
in the completed analysis.

## Wildfire

[wildfire.py](fri_pipeline/wildfire.py) uses NASA annual MME75 `FWI_P95` and LANDFIRE fuel shares.
Historical FWI is averaged over 1976–2005 and future FWI over each projection period, then
area-weighted to counties. The county multiplier is:

```text
HM = (future county FWI / historical county FWI) ** gamma
```

`gamma` is the coefficient on log historical FWI in a county regression of log wildfire
expected annual loss, controlling for fuel shares and log burnable share. The least-squares
implementation weights observations by burnable share (multiplying the design and response
by its square root). The fitted coefficient and input fingerprints are recorded per run.
Wildfire multipliers below one fail the downstream gate; they are not silently clipped.

## Frozen scoring and ratings

[scoring.py](fri_pipeline/scoring.py) applies each hazard multiplier to the full reference
population before filtering to mapped geometry:

```text
projected annual loss (PALT) = baseline hazard EALT × HM
projected risk value (PRISKV) = baseline hazard RISKV × HM
```

Annual loss and risk categories use thresholds recovered from the full NRI v1.19 baseline.
Exact upper boundaries remain in the lower band. Special statuses and ties retain the frozen
rules. Risk percentile scores are recomputed within each scenario across all 3,231 counties,
including average ranks for zero ties, and displayed to four significant digits. Multiplier
rating thresholds use quintiles pooled across all four scenarios for each hazard variant.

Rating colors compare the resulting category, not percentage change. A county with a larger
multiplier can have smaller projected dollar losses and a lower annual loss category than
another county. Dollar category ranges are thresholds, not uncertainty intervals.

Every run first reproduces the archived rating/score fields. The completed analysis passed
all 310,176 archive comparisons. This validates the scoring reconstruction, not the scientific
accuracy of newly calculated hazard multipliers. The archive has no direct published dollar
answer key for the derived `PALT` and `PRISKV` fields.

## Missing data and available-year analysis

Normal release preparation rejects missing years, temporal gaps, changing source-domain masks,
uncovered counties and non-finite outputs. Static all-time ocean/no-data cells remain masked;
county means normalize over supported area rather than filling missing cells with zero.
The merged supported multipliers must all be finite and at least one.

The separate October 2026 analysis explicitly omits the 19 annual wildfire files absent from
NASA's catalog, as pinned in [available-fwi-years.json](reference/available-fwi-years.json).
It equally weights the available years in each original period, without interpolation or
substitution. Historical FWI uses 26 years; SSP2-4.5 uses 25 per future period; SSP5-8.5 uses
28 mid-century and 27 late-century years. Unequal coverage can introduce sampling bias that
has not been quantified. Drought and heat retain complete periods.

That run is marked non-publishable and cannot pass the normal candidate/staging workflow.
Its [analysis report](evidence/2026-10-25-available-year-analysis.md) lists omitted years,
measured outputs, comparison findings and limitations. Successful archive replay or Batch
execution does not approve this analysis for publication.

## Reproduction and review

Each immutable input snapshot records source identities, retrieval metadata, hashes, prepared
arrays, coordinates, county weights and fuel shares. Hash-pinned worker images and code revisions
identify the implementation. Hamilton expresses the hazard/scoring dependencies in
[flow.py](fri_pipeline/flow.py); Cloud Batch runs acquisition, computation and packaging.

The results catalog separates the derived FRI dataset from LOCA2, NEX-GDDP-CMIP6, NEX-GDDP-FWI,
LANDFIRE and Census boundaries. Each logical file is versioned under
`future-risk-index/DATASET/FILE/VERSION/`. Results retain county GeoParquet, exact prepared inputs,
analysis-ready Zarr, original NetCDF and other source files, source lineage and hashes.
Reports distinguish computed outputs from carried-forward archived values.

Candidate review PRs include a deterministic numerical report, validation, provenance, changes
and a hash-pinned results pointer. Merging an eligible candidate authorizes checksum-verified
copying to the existing staging bucket. Downstream transforms, catalog publication and map
activation remain separate. The current analysis is not eligible for that approval path.
