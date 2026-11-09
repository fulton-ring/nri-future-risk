# County risk candidate: fri-mme50-20261109195422-score

Candidate for review. Merging approves this exact source for publication.

Changes below are relative to FEMA’s December 2024 archive, not the previous update.

| Variant | Scenario | Changed multipliers | Changed loss ratings | Max HM Δ |
|---|---|---:|---:|---:|
| DRGT | MID_LOWER | 2530 | 24 | 0.364402 |
| DRGT | MID_HIGHER | 2966 | 17 | 0.413416 |
| DRGT | LATE_LOWER | 2866 | 18 | 0.445227 |
| DRGT | LATE_HIGHER | 3104 | 9 | 0.814561 |
| WFIR | MID_LOWER | 3108 | 14 | 0.0958227 |
| WFIR | MID_HIGHER | 3108 | 19 | 0.150578 |
| WFIR | LATE_LOWER | 3108 | 24 | 0.148168 |
| WFIR | LATE_HIGHER | 3108 | 87 | 0.630757 |
| EXHT_L95 | MID_LOWER | 1081 | 6 | 0.477262 |
| EXHT_L95 | MID_HIGHER | 1267 | 10 | 1.00865 |
| EXHT_L95 | LATE_LOWER | 1357 | 15 | 1.13181 |
| EXHT_L95 | LATE_HIGHER | 2399 | 14 | 3.59988 |
| EXHT_L99 | MID_LOWER | 2230 | 13 | 4.32699 |
| EXHT_L99 | MID_HIGHER | 2328 | 15 | 6.60397 |
| EXHT_L99 | LATE_LOWER | 2442 | 16 | 7.16325 |
| EXHT_L99 | LATE_HIGHER | 2830 | 24 | 19.7074 |

Archive regression: **310,176 comparisons, zero mismatches**.

Scoring population: 3231; mapped counties: 3218; missing geometries: 13.

## Scope and interpretation

- Rebuilt multipliers: CONUS drought, wildfire, LOCA2 heat (95th/99th).
- Other areas retain archived multipliers. National ranks use all 3,231 counties and can change outside CONUS as CONUS risk changes.
- Coastal flooding, hurricanes, and NEX heat remain archived.
- County projections use area weighting; no tract product is published.
- LOCA2 weights use 0.25° boxes around source centers; no 6 km support claim.
- SSP2-4.5 and SSP5-8.5; one model/run, no uncertainty ensemble.
- Frozen NRI v1.19; no future demographics or baseline replacement.
- Missing/non-finite inputs and multipliers below one block publication.

See provenance.json, validation.json and changes.json for machine-readable evidence.
Map activation waits for verified hosted assets from the publisher.
