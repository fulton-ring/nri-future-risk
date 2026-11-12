# Available-year Future Risk Index analysis

Google Cloud Batch job `fri-analysis-20261025140637` succeeded on 2026-10-25. It calculated drought, wildfire and LOCA2 extreme heat for **3,108 CONUS counties**, then scored the full **3,231-county** frozen baseline. All 16 updated multiplier columns are finite and at least 1. The generated analysis is non-publishable; no live datasets or map release were changed.

The Batch worker acquired and processed the climate inputs, ran the Hamilton hazard graph, and generated scores, changes, validation and provenance artifacts. Independent local checks used copies of prepared drought/wildfire inputs; the authoritative outputs below came from Batch.

The verified snapshot records **618 source fingerprints**. The final Batch task ran for 2 hours, 7 minutes and 42 seconds. Its temporary VM was cleaned up.

## Wildfire year coverage

The user approved analysis without the 19 MME75 files absent from [NASA’s catalog](https://data.nas.nasa.gov/gddpimpact/FWI/Yearly/MME/). Available annual FWI_P95 observations receive equal weight within each original period. No years were interpolated or replaced. The historical calibration and future means therefore have different year coverage; resulting sampling bias has not been quantified. Drought and heat retain their complete original periods.

| Pathway | Period | Years used | Omitted years |
|---|---|---:|---|
| Historical | 1976–2005 | 26/30 | 1982, 1983, 1986, 2002 |
| SSP2-4.5 | 2036–2065 | 25/30 | 2045, 2051, 2053, 2057, 2060 |
| SSP2-4.5 | 2070–2099 | 25/30 | 2070, 2075, 2082, 2096, 2098 |
| SSP5-8.5 | 2036–2065 | 28/30 | 2050, 2060 |
| SSP5-8.5 | 2070–2099 | 27/30 | 2070, 2081, 2098 |

The fitted wildfire elasticity is **1.5180275773**. The available-year snapshot is explicitly marked and rejected by the normal release worker.

## Median hazard multipliers

| Hazard | SSP2-4.5 mid-century | SSP2-4.5 late-century | SSP5-8.5 mid-century | SSP5-8.5 late-century |
|---|---:|---:|---:|---:|
| Drought | 1.581 | 2.044 | 1.711 | 5.144 |
| Wildfire | 1.482 | 1.739 | 1.663 | 2.457 |
| Heat, 95th percentile | 1 | 1 | 1 | 2.45 |
| Heat, 99th percentile | 2.69 | 3.487 | 3.404 | 11.65 |

These are multipliers relative to each hazard’s historical calculation. The heat method requires minimum temperature to exceed both the historical percentile and **23.07°C**, and floors its multiplier at 1. An HM of 1 can reflect those method thresholds.

## Changes relative to FEMA’s December 2024 archive

These comparisons describe reconstruction differences using the acquired inputs and available wildfire years. The baseline loss/vulnerability data remain frozen. Counts in each row are scenario-specific, rather than unique counties across scenarios.

| Hazard | Scenario | Changed HMs | Changed loss ratings | Changed risk ratings | Largest absolute HM change |
|---|---|---:|---:|---:|---:|
| DRGT | MID_LOWER | 2,530 | 24 | 18 | 0.364402 |
| DRGT | MID_HIGHER | 2,966 | 17 | 21 | 0.413416 |
| DRGT | LATE_LOWER | 2,866 | 18 | 17 | 0.445227 |
| DRGT | LATE_HIGHER | 3,104 | 9 | 19 | 0.814561 |
| WFIR | MID_LOWER | 3,108 | 56 | 36 | 0.672024 |
| WFIR | MID_HIGHER | 3,108 | 72 | 50 | 0.859359 |
| WFIR | LATE_LOWER | 3,108 | 68 | 51 | 0.753799 |
| WFIR | LATE_HIGHER | 3,108 | 105 | 110 | 2.41183 |
| EXHT_L95 | MID_LOWER | 1,081 | 6 | 3 | 0.477262 |
| EXHT_L95 | MID_HIGHER | 1,267 | 10 | 6 | 1.00865 |
| EXHT_L95 | LATE_LOWER | 1,357 | 15 | 8 | 1.13181 |
| EXHT_L95 | LATE_HIGHER | 2,399 | 14 | 14 | 3.59988 |
| EXHT_L99 | MID_LOWER | 2,230 | 13 | 18 | 4.32699 |
| EXHT_L99 | MID_HIGHER | 2,328 | 15 | 13 | 6.60397 |
| EXHT_L99 | LATE_LOWER | 2,442 | 16 | 15 | 7.16325 |
| EXHT_L99 | LATE_HIGHER | 2,830 | 24 | 17 | 19.7074 |

## Validation and spatial support

- Frozen archive regression: **310,176 comparisons; zero mismatches**.
- All updated multipliers are finite and meet the unchanged release floor; scores were generated.
- Independent drought and wildfire checks each compared 12,432 values. Maximum absolute differences were 3.6e-15 and 1.6e-14 respectively.
- Every downloaded analysis artifact matched its recorded SHA-256 and byte count.
- Source-domain masks remain stable across years and scenarios; every CONUS county has positive valid weighting support.

| Source family | Weighted cells | Structurally masked cells | Counties with partial support | Minimum valid support fraction |
|---|---:|---:|---:|---:|
| nex-monthly | 13,737 | 17 | 15 | 99.296% |
| nex-fwi | 13,737 | 17 | 15 | 99.296% |
| loca2 | 220,047 | 4,568 | 287 | 51.298% |

Support fractions refer to the reviewed weighting scheme. LOCA2 retains 0.25° weighting boxes around its 1/16° source centers; the support fractions are not county land-area measurements. Static no-data cells remain masked and means normalize over valid support. The 51.3% minimum LOCA2 support is a material spatial limitation to review alongside the wildfire year omissions.

Non-CONUS multipliers and unsupported variants retain archived values. Scenario ranks are recalculated over the full frozen population, so ranks can also change for counties whose multipliers remain archived.

## Artifacts and provenance

- Analysis output: `gs://hifld-next-fri-inputs/real/analyses/fri-analysis-20261025140637`
- Analysis manifest SHA-256: `19040e4f1c8a0f19c0d9fe112bac1e19744864ed471cac31f10405a287fc5be9`
- Input snapshot: `gs://hifld-next-fri-inputs/real/snapshots/fri-analysis-20261025140637/snapshot.json`
- Snapshot SHA-256: `6e083b1795215e66a0ba5c709b2b02d41523800ecefcfc3c8413901ea82eddf4`
- Source commit: `f93e4a9a135f200b5d0c036e6fb08cdc2dbab555`
- Worker image: `us-central1-docker.pkg.dev/hifld-next/fri/preparation@sha256:14c884711f4d7ead4dc8177550cdf57ca2aec79af9ae07a6e92d6f05b8744a4b`
- Machine-readable run evidence: [2026-10-25-available-year-analysis.json](2026-10-25-available-year-analysis.json).

The cloud output includes `multipliers.csv` (3,108 counties), `scores.csv` (3,231 counties, 168 fields), `changes.json`, `report.md`, `validation.json`, `provenance.json` and the hashed `analysis.json` inventory. The original acquired-file URLs, complete source hashes, preparation hashes and analysis policy are retained in provenance.
