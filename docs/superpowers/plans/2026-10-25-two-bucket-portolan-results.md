# Two-bucket Future Risk Index results

The user approved two project buckets and a separate `future-risk-index` collection. They also requested analysis-ready Zarr and original NetCDF source archives. Publication remains a later approved copy to the existing HIFLD Next staging bucket.

- [x] Replace four project buckets with `future-risk-index-experiments` and `future-risk-index-results`. Keep the shared Terraform state backend. Preserve existing data and generations before retiring legacy buckets.
- [x] Put runs, checkpoints, source acquisition records, raw review artifacts, and receipts/history in experiments. Results contains only a portable Portolan collection tree with versioned county GeoParquet, reproducibility metadata, Zarr stores, and original source assets.
- [x] Read the existing prepared snapshot and completed analysis without rerunning hazard calculations. Package all available inputs, frozen baseline/geometry, sparse weights, fuel shares, and exact configuration. Distinguish masked source support and the approved 19-year wildfire omission policy.
- [ ] Re-acquire original source files in Batch with bounded downloads and exact recorded SHA-256 checks. Preserve original NetCDF bytes; never replace a changed source silently. Store verified objects in the results collection and preserve source acquisition metadata in experiments.
- [x] Use relative Portolan links throughout. Set collection identity explicitly to `future-risk-index`, including any downstream publish manifest. Do not inherit the publisher's `hifld` default.
- [x] Update workers, Terraform outputs, workflows, and docs for the two buckets. Promotion copies only approved collection data to the existing staging service, without an extra project staging or receipt bucket. No publication during this task.
- [ ] Test catalog/link/data integrity and default publication rejection of exploratory data; validate real results against the HIFLD Next Portolan tooling. Verify cloud copies before retiring old storage and record migration locations without rewriting historical run evidence.

Runtime verification: 45 pipeline tests pass; Terraform reports no drift after the two-bucket migration and scoped catalog IAM changes. Original-source archiving runs in Batch (`future-risk-archive-20261025174607`). Real Portolan packaging awaits its complete, hash-verified inventory; synthetic full-geometry and lossless Zarr packaging has passed.
