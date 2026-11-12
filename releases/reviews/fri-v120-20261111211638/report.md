# NRI v1.20 county and tract review

Version: `v20261111T211638Z`. Scientific Batch job: `fri-v120-20261111211638`.

This review preserves the FEMA archive and applies recreated drought, MME50 annual-mean wildfire, and LOCA2 heat multipliers to native NRI v1.20 baselines. Connecticut uses nine planning regions. County-fitted wildfire gamma is 1.5711909155957975 and is shared with tracts.

The result contains 3,232 national county equivalents and 85,154 national tracts. Future climate projections cover all 3,109 CONUS county equivalents. Drought and wildfire cover 83,480 of 83,481 CONUS tracts; heat covers 83,461. Unsupported tracts are in Monroe County, Florida and retain native baselines with null future projections. Areas outside CONUS also retain baselines without future projections.

Climate weighting retains 0.25-degree boxes, including LOCA2: tract polygons provide separate exposure and vulnerability, not finer climate resolution. Future risk ranks compare supported CONUS areas within each geography and scenario; native baseline ranks and category thresholds retain their national geography-specific populations. Differences from the original archive combine baseline, geography and reconstruction differences and must not be described as observed changes in climate damage.

Exact inputs, native NRI ZIPs, Census geometries, sparse weights and ordered IDs are in the public results inventory. The pinned climate snapshot retains prepared arrays, analysis-ready Zarr and original NetCDF sources. The source manifest and public receipt committed here bind the exact data approved for staging when this review merges to main. No approved release has been activated.
