# Future Risk Index pipelines

Hamilton computes county drought, wildfire and extreme heat from immutable climate snapshots.
Google Cloud Batch performs acquisition, computation, source archiving and results packaging.
GitHub Actions starts a run on demand and opens a review PR. Merging the PR approves the exact
candidate for copying into the existing publisher staging bucket.

There are exactly two project data buckets:

| Bucket | Contents |
|---|---|
| `future-risk-index-experiments` | Downloads/checkpoints, prepared snapshots, analysis runs, candidate review files, migration evidence and results pointers |
| `future-risk-index-results` | Portable Portolan catalog: versioned county GeoParquet, analysis-ready Zarr, exact prepared inputs, original source files and provenance |

Both are versioned. Experiments remain private; results allow anonymous reads and listings,
including versioned outputs, prepared arrays, original source files and provenance.
Public read access does not grant write access or approve an analysis for release. The existing Terraform state bucket is shared infrastructure,
not another project data bucket. State uses the isolated prefix
`gs://hifld-next-iac-prod-49775666365/nri-future-risk/prod`.

The four legacy `hifld-next-fri-*` buckets were retired after verifying all 5,043 object generations
(16,027,423,052 bytes) in experiments. The complete migration inventory is retained at
`gs://future-risk-index-experiments/_migrations/2026-10-25-four-to-two/manifest.json`.
Historical evidence retains its original URLs; replace the old inputs bucket with experiments,
and use `legacy-candidates/` in experiments for old candidate paths.

The available-year Batch analysis `fri-analysis-20261025140637` succeeded: 3,108 CONUS counties
were updated and scores calculated for the 3,231-county frozen baseline. All 310,176 archive
regression comparisons passed. This remains **non-publishable analysis**, because 19 required
wildfire years are absent from NASA's catalog. See the [analysis report](evidence/2026-10-25-available-year-analysis.md)
and [run evidence](evidence/2026-10-25-available-year-analysis.json). Nothing has been published.
The original source archiving job is separate from that completed numerical analysis.

## Verify locally

```bash
uv run --directory pipeline --frozen --extra results pytest -q
uv run --directory pipeline --frozen ruff check .
uv run --directory pipeline --frozen ruff format --check .
uv run --directory pipeline --frozen python -m fri_pipeline run \
  --replay --output /tmp/fri-replay --release-id archive-replay \
  --code-revision "$(git rev-parse HEAD)"
uv run --directory pipeline --frozen python -m fri_pipeline verify /tmp/fri-replay
```

Replays reproduce the archived classification/score fields and are never publishable. Synthetic
climate tests exercise the actual hazard implementations; they do not validate new observations.
GeoParquet and Zarr tests verify exact round trips, including zeros, missing values and histograms.
Portolan metadata is checked with Rashid. Output version directories must be new.

See [METHODOLOGY.md](METHODOLOGY.md) for the hazard calculations, reference periods,
scoring equations, coverage limitations and reproduction contract.

## Frozen scientific contract

`reference/contract.json` pins the workbook, geometry, method and verification commits. Every run:

- verifies the complete 3,231-row December 2024 workbook and reproduces its downstream fields;
- derives fixed loss/risk category thresholds from the **full** NRI v1.19 baseline;
- computes projected annual loss as hazard EAL × HM and risk value as **hazard RISKV × HM**;
- ranks projected risk separately within each scenario, including zero ties, to four significant digits;
- derives multiplier quintiles from all four scenarios pooled separately per variant;
- preserves exact upper boundaries in their lower band, tied quantiles and special statuses;
- requires all 3,108 CONUS counties and all four scenarios for each supported variant;
- rejects temporal gaps, changing source-domain masks, uncovered counties, non-finite outputs,
  and HMs below 1, including wildfire (no silent clipping).

Static all-time ocean/no-data masks remain NaN and retain the spike's original normalization over
valid cell area. They are never filled with zero. Source masks must remain identical across each
source family's variables/scenarios; every county must retain positive valid coverage. Snapshot
provenance records masked-cell counts and minimum/median county area coverage. A real 1950 NEX
probe found 17 structurally masked cells among 13,737 weighted cells, zero temporal gaps and valid
coverage for all 3,108 CONUS counties.

Non-CONUS multipliers remain archived, but **ranks are recomputed over the whole frozen population**.
This is an explicitly mixed-vintage reference population. A rank can change outside CONUS without
its multiplier changing. All scientific scoring precedes geometry filtering: 13 reference counties
lack matching archived geometry and are listed in `omittedGeometry`. Coastal flooding, hurricane
and NEX heat values remain archived. Baseline demographic/vulnerability values remain frozen.

County estimates retain the reviewed area-weighted method. No tracts, no v1.20 substitution, and no
national reconstruction claim. LOCA2 source centers retain 0.25° weighting boxes; no 6 km spatial
support claim. Changes to baseline, geometry, aggregation, source support, scenarios or coefficients'
fitting method require a new contract and comparison report. The fitted wildfire coefficient is
recorded for each candidate alongside its MME75/FWI_P95 settings and baseline/source fingerprints.

Published updated variants include `_HM`, `_PALR`, `_PRISKR`, `_PRISKS`, `_DELTAR`, plus `_PALT`
(projected annual loss, dollars/year) and `_PRISKV` (projected risk value, baseline hazard RISKV × HM).
Dollar outputs follow the validated equations; FEMA's archive has no direct published dollar answer key.

## Prepare an immutable climate snapshot

`fri_pipeline.prepare` provides the real acquisition worker (`Preparation.Dockerfile`). It uses
hash-checked copies of the pinned spike's data/weighting code in `vendor/fri_rebuild`, downloads
only NEX monthly tas/pr, MME75/FWI_P95 and LOCA2 tasmin, and records complete raw-file hashes.
LOCA2 files are downloaded and processed one at a time; the percentile calculation and 0.25°
county weighting are unchanged. The preparation and scoring accounts can read/create experiment and results objects.
They cannot write to the publisher staging bucket or publish hosted data. Shared catalog indexes
have narrowly scoped overwrite permission; versioned data remains create-only.

Completed caches and source ledgers are checkpointed under `real/acquisitions/RUN_ID`; successful
exports appear under `real/snapshots/RUN_ID`. A `result.json` marker is written only after the
snapshot passes all source/coverage checks. Retries can restore a checkpoint with `--resume-uri`
and its `--resume-sha256`; every restored object is hash verified. NEX file selection remains pinned
across retries. Acquisition can take hours; it does not call any LLM or agent loop.

For the user-approved available-year exploration, pass `--available-fwi-years` to preparation.
It omits only the 19 catalog gaps pinned in `reference/available-fwi-years.json`, retaining
26 historical years, 25 years per SSP2-4.5 period, and 28/27 SSP5-8.5 MID/LATE years.
All other source, coverage and temporal checks remain in force. Period means use equally
weighted available years; there is no interpolation or substitution. The snapshot explicitly
records the analysis policy and is rejected by the normal release worker. Hamilton calculates
the three hazards and writes a report, raw multipliers, hashes and provenance under
`real/analyses/RUN_ID` in the experiments bucket. Scores are included only if every raw
multiplier meets the unchanged release floor; otherwise the report records the violations
without clipping. These outputs are non-publishable and have no publication candidate manifest.

Source acquisition is deliberately separate from release calculation. The preparation worker pins
the original spike's newest-file selection, records complete raw-file hashes, and checkpoints its
cache. The scoring worker consumes only the immutable exported snapshot. As an alternative to the
preparation worker, prepare/review a climate cache using a clean checkout of `agent-content-demos`
at `390f7c072dc23b5c33a7d7a87b99cecd8ef8041c`, then export its cached inputs using that project's environment:

```bash
# FRI_CACHE selects the already prepared cache used by the spike.
uv run --directory /path/to/agent-content-demos/fri-agent-rebuild python \
  /path/to/nri-future-risk/pipeline/export_snapshot.py \
  --rebuild /path/to/agent-content-demos --sources /path/to/raw-sources.json \
  --output /tmp/fri-input-snapshot
```

`raw-sources.json` is a required list of acquisition records. Each has a unique `id`, `title`, permanent
HTTPS `url`, raw-content `sha256`, and `retrievedAt` date. Include the climate files, model/run,
LANDFIRE fuel source, boundary source and weighting preparation; optional `datasetUrl`/`license`
fields identify their parent datasets and reuse terms. These are acquisition fingerprints, not hashes
invented by the exporter. Keep the acquired raw files available at those URLs or in an immutable
source archive. The exporter associates its prepared artifacts with this inventory. It does not
independently re-download raw inputs to verify the acquisition records.

The exporter prohibits HTTP downloads, checks the upstream checkout, and hashes every exported
artifact. An incomplete cache fails. In particular, the old spike tolerates missing NASA FWI years;
this path requires every requested year and fails if any are absent. Missing FWI years, temporal
gaps, changing source-domain masks, or a wildfire HM below 1 must be investigated before a real release; do not bypass
these gates or interpret successful archive replay as evidence they have been resolved.

`snapshot.json` has `schemaVersion: 1`, `coverage: "CONUS"`, `methodology` equal to the frozen contract
ID, `rebuildCommit`, `sources`, and `artifacts`. Each artifact has a relative `path`, SHA-256 and
nonempty `sourceIds`. Absolute/traversing paths and unknown sources fail verification. Artifacts:

| Key | Format and contents |
|---|---|
| `county_ids` | JSON FIPS strings, all CONUS rows in master workbook order |
| `nex_weights`, `loca2_weights` | SciPy CSR NPZ, county rows × supported climate cells |
| `nex_coordinates` | CSV, `lat`, `lon`, matching NEX weight columns |
| `fuel_shares` | CSV, `STCOFIPS`, `nonburnable` and fuel groups, fractions summing to one |
| `monthly_{tas,pr}_{ssp245,ssp585}` | NumPy NPZ `values` (month × cell), `months` (datetime64), Jan 1950–Dec 2100; °C and mm/day |
| `fwi_{scenario}_{period}` | NPZ `values` (year × cell), `years`; MME75/FWI_P95 |
| `loca2_{scenario}_{period}` | NPZ `edges`, `counts`; original 0.1°C histogram including no-data row |

FWI and LOCA2 keys cover `historical_historical`, and each of `ssp245`/`ssp585` × `MID`/`LATE`.
Historical spans 1976–2005; MID 2036–2065; LATE 2070–2099. Histograms must account for every day.
Drought retains its distinct 1950–2010 calibration and 1985–2014 historical period.

Upload the complete directory under a unique prefix in the experiments bucket. Record the manifest's
SHA-256 printed by the exporter. The workflow requires both the GCS manifest URI and this digest;
each fetched object generation is pinned during transfer and every prepared file hash is checked.

## Infrastructure and cloud execution

Terraform is split into provider, variable, resource and output files in `infra/`.
`main.tf` provisions the two buckets, Artifact Registry, four service accounts, workload identity
and required APIs. The existing publisher staging bucket is an input, not a new resource.

```bash
export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"
terraform -chdir=pipeline/infra init -backend-config=prod.gcs.tfbackend
terraform -chdir=pipeline/infra plan -var-file=prod.tfvars
```

Apply the reviewed plan and copy `github_variables` outputs into repository variables. Set
`FRI_PR_TOKEN` to a repository token with contents and PR write permissions so candidate PRs can
trigger follow-on workflows. Never give the worker that token. No service-account keys are used.
Workload identity accepts only this repository, `main`, and the exact update/publication workflows.

Build `pipeline/Preparation.Dockerfile` for acquisition and `pipeline/Dockerfile` for scoring.
Use Linux AMD64 images pinned by digest. The Batch submission helper is
`python -m fri_pipeline.cloud --help`; preparation is `python -m fri_pipeline.prepare --help`.
Both run on the private `hifld-prod-vpc` / `hifld-prod-subnet`, with no external VM IPs.
Workers use 8 CPUs, 32 GiB RAM and a 100 GiB disk. They have no automatic task retries.
Acquisition and original archiving can take hours; completed hash-verified downloads are reusable.

A full source inventory should be archived before starting a release workflow. A first-time source
archive can exceed the release worker's four-hour limit. Run `python -m fri_pipeline.archive --help`
on a preparation Batch worker to populate it first. The archive stores content-addressed originals
in the experiments bucket’s shared `source-archives/originals/SHA256/` cache and writes its complete manifest only after
all recorded sources match their original SHA-256 and byte counts. Later runs reuse identical
objects. Changed or unavailable source bytes fail the archive instead of silently substituting data.

Run **Prepare Future Risk Index results** on `main` with the snapshot URI and SHA-256. Its Batch
worker verifies the snapshot, runs Hamilton, archives any missing original sources, then builds
Portolan results. The PR includes a deterministic numerical report, validation, provenance,
changes, candidate hashes and a hash-pinned results pointer. Large data stays in GCS. An LLM is
not required for numerical validation; optional narrative generation can be added separately.

## Portable results and staging

All data belongs to the explicit **`future-risk-index`** collection, separate from `hifld`:

```text
catalog.json
future-risk-index/
  catalog.json
  fri/counties/VERSION/
    collection.json
    geoparquet/counties.parquet
    metadata/                 # report, provenance, validation, original-source inventory
    prepared/                 # exact snapshot, weights, fuel shares, baseline and geometry
    originals/                # original FEMA workbook
  loca2/loca2/VERSION/
    collection.json
    zarr/                     # five exact prepared LOCA2 histogram stores
    netcdf/                   # original LOCA2 downloads
    metadata/
  nex-gddp-cmip6/nex-gddp-cmip6/VERSION/
    collection.json
    zarr/                     # four prepared temperature/precipitation stores
    netcdf/                   # original annual NEX downloads
    metadata/
  nex-gddp-fwi/nex-gddp-fwi/VERSION/
    collection.json
    zarr/                     # five prepared annual FWI stores
    netcdf/                   # original annual FWI downloads
    metadata/
  landfire/landfire/VERSION/
    collection.json
    geotiff/
    metadata/
  census-boundaries/counties/VERSION/
    collection.json
    originals/                # original Census boundary archive
    metadata/
_releases/VERSION.json        # immutable inventory and completion record
```

The hierarchy matches the existing HIFLD collection: collection → dataset → logical file → version → formats/assets. Each actual source dataset has its own catalog; `fri` is the derived dataset. The leaf `collection.json` lists the physical assets for that logical file version. Original files are copied from the verified acquisition cache into the same versioned dataset paths as their prepared arrays.

Zarr preserves the exact analysis arrays and time/year or histogram coordinates with lossless
compression. Original NetCDF preserves the bytes needed to repeat preprocessing. Both retain
source identities, retrieval metadata and recorded hashes. Older snapshots recover LOCA2 cell
coordinates only from a hash-pinned checkpoint whose weights must exactly match the snapshot.
The catalog also retains exact prepared NPZs so reproduction does not depend on a format conversion.
Relative links keep the collection portable when copied to a different bucket. Source licenses
must be reviewed individually; this is not an automatic public-domain collection.

The merge workflow checks that the approved candidate matches the result inventory, rejects
exploratory analyses, then performs checksum-verified GCS copies into
`gs://hifld-next-staging-prod/future-risk-index/`. It copies only the selected version and its
referenced originals, preserving previously staged versions and other collections. It does not
create another project staging bucket, publish live data, or switch the map.

The downstream HIFLD Next service owns format transforms, PMTiles hosting and catalog publication.
Its GeoParquet path already uses Portolan metadata; importing this prebuilt collection and
preserving its Zarr/original source assets still needs to be connected there before publication.
Do not assume its existing GeoParquet-only publishing command handles the entire source catalog.
The publisher must retain all county hazard properties, numeric `county_id` feature IDs, string
`fips`, provenance and immutable asset URLs. Hosted PMTiles and CORS/range behavior must pass the
existing `fri_pipeline.publication` verification checks before a separate map activation.
No custom request/receipt service is required by the staging workflow.

## Public review of results

Terraform grants `allUsers` the read-only `roles/storage.objectViewer` role on
`future-risk-index-results` and configures GET/HEAD CORS for browser clients. Experiments,
checkpoints and Terraform state remain private. Write permissions remain restricted to the
existing service accounts. The complete results bucket, including original source files,
is readable and listable without Google Cloud credentials; source terms continue to apply.

Start at the [public catalog](https://storage.googleapis.com/future-risk-index-results/catalog.json).
Relative dataset/file/version links identify the data and provenance for each version.
Public access to an analysis is for review; its analysis status and scientific limitations
remain in the catalog and reports, and the normal staging gates still reject it.
