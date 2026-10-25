# County risk releases

This implements the county-first path established by [verification PR #120](https://github.com/fulton-ring/agent-content-demos/pull/120).
Hamilton calculates drought, wildfire and LOCA2 95th/99th heat from a hash-verified prepared input
snapshot. Cloud Batch runs that graph on demand. GitHub Actions opens a candidate PR containing
measured changes and provenance; merge approves the exact hashed candidate for publication.
The map switches only after the HIFLD Next publisher returns verified hosted assets.

**Deployment status:** the FRI infrastructure is provisioned in `hifld-next` (2026-10-24).
Its isolated remote state is `gs://hifld-next-iac-prod-49775666365/nri-future-risk/prod`.
The real Batch archive replay `fri-replay-20261024205347` succeeded on a private worker in
27.9 seconds of execution; all downloaded artifacts passed local verification (310,176 comparisons,
zero mismatches). [Run evidence](evidence/2026-10-24-cloud-batch-replay.json) records the pinned
image, source revision, candidate hashes and infrastructure state location.
No production data has been published. The external
publisher must register the new collection and consume the handoff/produce the receipt described
below; this repository does not install code into or mutate that service's catalog.
The first real acquisition completed all 474 NEX annual inputs and 131/150 wildfire years, then
stopped because NASA returned HTTP 500 for the remaining 19 required MME75 files. Catalog
verification confirmed that all 19 paths are absent from NASA's published listing; these are
catalog gaps, not demonstrated intermittent transfer failures. No LOCA2 heat acquisition or real scoring ran, and no candidate was
generated. [Acquisition evidence](evidence/2026-10-24-real-input-acquisition.json) lists every missing
source and the hash-pinned checkpoint for resuming without repeating completed downloads.
The subsequent user-approved available-year analysis `fri-analysis-20261025140637` succeeded
on 2026-10-25: all three hazards were calculated for 3,108 CONUS counties and scores generated
over the 3,231-county baseline. All 310,176 archive checks passed, all updated multipliers met
the release floor, and the output hashes were verified. This exploratory output is non-publishable;
the normal release path still requires complete wildfire periods. See the
[analysis report](evidence/2026-10-25-available-year-analysis.md) and
[run evidence](evidence/2026-10-25-available-year-analysis.json), including year omissions and
the lower valid spatial support in some LOCA2 weighting areas.
This branch is based directly on `main`, independent of the atlas UI branch. Hosted assets are
verified even before that UI is merged; map activation waits until its release-manifest support exists.

## Local verification and replay

Requires Python 3.12+ and uv. From the repository root:

```bash
uv run --directory pipeline --frozen pytest -q
uv run --directory pipeline --frozen ruff check .
uv run --directory pipeline --frozen ruff format --check .
uv run --directory pipeline --frozen python -m fri_pipeline run \
  --replay --output /tmp/fri-replay --release-id archive-replay \
  --code-revision "$(git rev-parse HEAD)"
uv run --directory pipeline --frozen python -m fri_pipeline verify /tmp/fri-replay
```

Output directories must be empty. Replays reproduce **310,176** archived classification/score fields,
package 3,218 county geometries, and are **never publishable**. Tests also run the actual three hazard
implementations against a small synthetic climate grid; that is an integration check, not scientific
validation of new climate observations. A real climate update still needs the prepared source inputs
and review. Tests encode/decode a small PMTiles fixture and check county IDs and hazard properties
without depending on the atlas branch's display assets.

The container can run replay without network access:

```bash
docker build --platform linux/amd64 -f pipeline/Dockerfile -t fri-worker .
docker run --rm --network none fri-worker run --replay --output /tmp/replay \
  --release-id archive-replay --code-revision "$(git rev-parse HEAD)"
```

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
county weighting are unchanged. A dedicated `fri-preparation` account can create/read input
objects but cannot publish datasets or modify candidates. The scoring worker retains read-only
input access.

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
`real/analyses/RUN_ID` in the private input bucket. Scores are included only if every raw
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

Upload the complete directory under a unique prefix in the private input bucket. Record the manifest's
SHA-256 printed by the exporter. The workflow requires both the GCS manifest URI and this digest;
each fetched object generation is pinned during transfer and every prepared file hash is checked.

## Cloud setup

`infra/main.tf` provisions private versioned input/candidate/staging/receipt buckets, an Artifact
Registry repository, four separate service accounts, workload identity and the required APIs.
Production backend and variables are recorded in `infra/prod.gcs.tfbackend` and `infra/prod.tfvars`.
The backend reuses the existing infrastructure state bucket with an independent FRI prefix.
Credentials and state contents are never committed.

```bash
export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"
terraform -chdir=pipeline/infra init -backend-config=prod.gcs.tfbackend
terraform -chdir=pipeline/infra plan -var-file=prod.tfvars
```

Apply the reviewed plan through your normal infrastructure process. Copy `github_variables` outputs
to GitHub repository variables. Also set `FRI_PUBLISHED_BUCKET` to the existing published asset bucket
and `FRI_ATLAS_ORIGIN` to the atlas's HTTPS origin, e.g. `https://fulton-ring.github.io`.
The publisher's existing identity must retain its catalog/transform permissions; this module grants
only read access to the dedicated staged source and create/read access to its receipts.

Set secret `FRI_PR_TOKEN` to a fine-grained repository token with contents and
pull-request write permission. It creates candidate PRs and writes the approved activation commit.
Repository rules must permit that identity's narrow activation path. A normal `GITHUB_TOKEN` does
not trigger follow-on PR/Pages workflows when it writes a commit. Do not grant the Batch worker
this token. If rules reject activation, publication stops without changing the map.

Workload identity accepts only this repository's numeric identity, `main`, and the two exact workflow
paths. Compute can read inputs and create/read candidate objects, but cannot stage/publish or overwrite
outputs. The Actions runner can submit Batch and push worker images. The separate publication identity
can read candidates, stage approved sources and read receipts. No service-account JSON keys are used.

The Batch task uses 8 CPUs, 32 GiB RAM, a 100 GiB boot disk, no automatic retries, a digest-pinned
image and a four-hour task limit. Submission waits at most five hours. Candidate IDs contain the
Actions run ID and attempt; output writes are create-only (a retry accepts identical existing bytes).
Canceling an Actions run may leave its already-submitted Batch task running until its time limit;
cancel it explicitly with `gcloud batch jobs delete RELEASE_ID --location REGION --project PROJECT`.
Jobs require an explicit VPC/subnet and always disable external VM IPs. Production uses
`hifld-prod-vpc` / `hifld-prod-subnet`, with Private Google Access already enabled. The project's
no-public-VM-IP policy remains in force; no firewall or organization policy exceptions are needed.

## Submit Batch from your local CLI

Use `gcloud auth login`; the submission helper invokes gcloud rather than requiring separate ADC.
Build the same AMD64 image the workflow will use, push it, then use its **digest**, never its tag:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
docker buildx build --platform linux/amd64 -f pipeline/Dockerfile \
  -t "us-central1-docker.pkg.dev/hifld-next/fri/worker:$(git rev-parse HEAD)" \
  --push --metadata-file /tmp/fri-worker-image.json .
FRI_IMAGE_DIGEST=$(python3 -c 'import json; print(json.load(open("/tmp/fri-worker-image.json"))["containerimage.digest"])')
FRI_REPLAY_ID="archive-replay-$(date -u +%Y%m%d%H%M%S)"
uv run --directory pipeline --frozen python -m fri_pipeline.cloud \
  --project hifld-next --region us-central1 \
  --network projects/hifld-next/global/networks/hifld-prod-vpc \
  --subnetwork projects/hifld-next/regions/us-central1/subnetworks/hifld-prod-subnet \
  --image "us-central1-docker.pkg.dev/hifld-next/fri/worker@$FRI_IMAGE_DIGEST" \
  --service-account fri-worker@hifld-next.iam.gserviceaccount.com \
  --output "gs://hifld-next-fri-candidates/runs/$FRI_REPLAY_ID" \
  --release-id "$FRI_REPLAY_ID" --code-revision "$(git rev-parse HEAD)" --replay
gcloud storage cp --recursive "gs://hifld-next-fri-candidates/runs/$FRI_REPLAY_ID" /tmp/
uv run --directory pipeline --frozen python -m fri_pipeline verify "/tmp/$FRI_REPLAY_ID"
```

Replays use the frozen baseline baked into the image and are non-publishable. For a real update,
replace `--replay` with `--snapshot gs://.../snapshot.json --snapshot-sha256 THE_MANIFEST_DIGEST`.
The worker obtains its credentials from the Batch VM's bound service account.

Run **Prepare county risk update** on `main` with the snapshot URI/digest. The result is a PR under
`releases/candidates/RELEASE_ID`, containing candidate hashes, deterministic measured report,
validation, source lineage and changes. Large artifacts stay in private GCS. Reports compare against
the FEMA archive, explicitly not the previous update. No LLM is needed for this numerical report;
an optional narrative can be added later without becoming a validation or publication authority.

## HIFLD Next publisher registration and receipt

Register a new **`future-risk-index` collection**, dataset **`county-risk`**, file **`counties`**, backed
by the dedicated staging bucket. Keep this separate from the archived HIFLD collection and its
automatic public-domain license default; source reuse terms must be reviewed independently.
The current publisher's documented staged layout is preserved:

```text
future-risk-index/county-risk/counties/vYYYYMMDDTHHMMSSZ/geojson/counties.geojson
future-risk-index/county-risk/counties/vYYYYMMDDTHHMMSSZ/metadata/{counties.json,provenance.json,candidate.json,validation.json}
future-risk-index/county-risk/counties/vYYYYMMDDTHHMMSSZ/metadata/fri-publication-request.json
```

The first segment is the collection prefix used by the current Portolan publisher. The request
also includes its authored-record keys (`collection_slug`, `dataset_slug`, `file_slug`, `version`,
`title`, `description`, `provider`) alongside the FRI receipt contract. The request is uploaded
**last**, after approval and source validation. Configure this registered
dataset to wait for that marker; don't let generic discovery publish partially staged uploads.
The publisher must:

1. Check request/candidate/source hashes and collection identity; retain all 3,218 source features.
2. Use its normal GeoParquet/quality/PMTiles transforms and immutable catalog promotion. The PMTiles
   layer must be `counties`, feature IDs must be numeric FIPS from `county_id`, and string `fips`
   plus **all** hazard attributes must survive. No low-zoom aggregation of scores or labels.
3. Host the approved `counties.json` and `provenance.json` byte-for-byte. Expose source datasets through
   STAC `derived_from` links and dataset descriptions using the supplied source inventory/baseline
   references. Include model/run, pathways, geographic support, mixed vintages and scientific limits.
4. Serve permanent HTTPS GCS asset URLs with CORS for the atlas origin and HTTP Range support for
   PMTiles. Do not replace bytes at an existing published URL.
5. Write the following receipt, create-only, to the request's `receiptUri` after promotion:

```json
{
  "schemaVersion": 1,
  "releaseId": "THE_APPROVED_RELEASE_ID",
  "candidateSha256": "SHA256_OF_APPROVED_CANDIDATE_JSON",
  "sourceSha256": "SHA256_OF_APPROVED_COUNTIES_GEOJSON",
  "collection": "future-risk-index",
  "countyCount": 3218,
  "sourceLayer": "counties",
  "featureIdProperty": "county_id",
  "assets": {
    "counties.pmtiles": {"url": "https://storage.googleapis.com/PUBLISHED_BUCKET/IMMUTABLE_PATH/counties.pmtiles", "sha256": "ACTUAL_PM_TILES_HASH"},
    "counties.json": {"url": "https://storage.googleapis.com/PUBLISHED_BUCKET/IMMUTABLE_PATH/counties.json", "sha256": "APPROVED_ATTRIBUTES_HASH"},
    "provenance.json": {"url": "https://storage.googleapis.com/PUBLISHED_BUCKET/IMMUTABLE_PATH/provenance.json", "sha256": "APPROVED_PROVENANCE_HASH"}
  }
}
```

This is an explicit integration contract, **not an existing HIFLD Next HTTP endpoint**. Registration,
request consumption and receipt emission are required changes/configuration in the publisher repo.
They must be deployed before enabling real update PR merges here. No shared catalog pointer is
written by this repository. Existing publisher implementation: [hifld-next-datasets](https://github.com/Public-Environmental-Data-Partners/hifld-next-datasets).

The merge workflow downloads the exact candidate, compares its manifest with the merged PR,
recalculates its scores and checks the report. It stages approved bytes, waits up to four hours for
the receipt, then checks asset hashes, CORS/ranges and **every decoded PMTiles feature's hazard
attributes against the approved table**, including full county coverage. Only then does it write
`src/data/release.json`, run frontend checks and commit activation. Pages deploys that commit.
Missing/mismatched receipts fail closed. A newer candidate approval prevents stale activation.
Keep candidate PRs one release each. GitHub concurrency can replace a pending run when several
merges arrive together; avoid bulk merges and rerun an omitted/failed publication run explicitly.

Rollback: revert the activation commit to select the previously verified immutable manifest.
Do not delete or rewrite published source/assets. Archive assets remain checked in. Shared links
identify their release; if an older release is no longer selected, the UI visibly identifies the
current release rather than silently presenting it as the requested one.
