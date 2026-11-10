# County calculation transparency

Goal: show numeric county losses, risk scores, applied/raw multipliers, exact category thresholds,
hazard-specific formulas and a FEMA NRI county report link across the three active branches.

Use existing frozen county data and rating rules. Add an optional, source-hash-pinned heat
explanation sidecar computed in Batch and checked against the published multipliers. Do not
change published scores, baseline inputs, or fabricate missing archive diagnostics.

- [ ] Add exact baseline loss/risk thresholds, a pure heat explanation exporter, and numerical tests.
- [ ] Run the explanation exporter in Batch against the November immutable snapshot; verify outputs.
- [ ] Add numeric calculation details and exact legend bins to both interface branches, using shared code.
- [ ] Add county NRI links and version-specific methodology/data links, preserving archive scope.
- [ ] Verify tests, static builds, hosted previews and pipeline CI; update the pipeline PR docs.

Risk scores are percentile ranks, not the thresholds used for risk categories. Annual-loss
categories use fixed hazard-specific dollar thresholds; risk categories use fixed risk-value
thresholds. Exact upper boundaries stay in the lower category. Raw ratios are available only
when the source arrays and calculation are verified for the selected version.
