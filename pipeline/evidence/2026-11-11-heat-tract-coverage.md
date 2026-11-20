# LOCA2 tract coverage in the Florida Keys

Version `v20261111T211638Z` has 20 CONUS tracts without heat projection coverage, all in Monroe County, Florida. They cover the Middle and Lower Keys, including Marathon and Key West, plus an offshore tract. Upper Keys tracts near Key Largo and mainland Monroe have valid inputs and computed multipliers. This is not a county-wide absence.

The chosen LOCA2 MPI-ESM1-2-HR minimum-temperature input is on a 1/16-degree native grid. The calculation retains its documented 0.25-degree weighting boxes; it does not invent higher spatial climate resolution. Every affected tract has zero overlap with valid cells in the prepared snapshot. The input mask is consistent across all historical/future periods and scenarios. Baseline NRI values are retained; affected future heat multipliers, losses and scores remain null.

A read-only HTTP Range inspection of the archived original historical NetCDF checked its stored SHA-256 identity and sampled native grid points in the analysis reference period, on January 1, 1976 and January 1, 2005. The variable declares `missing_value = 1e30`. Cells near Marathon and Key West contain that marker on both dates. Cells near Key Largo and mainland Monroe contain valid temperatures. The file's bounding extent includes the Keys, so being inside the bounding box alone does not guarantee temperature data.

These point samples corroborate the already completed full-snapshot coverage checks; they do not assert that every LOCA2 model/version has the same mask. No original files, prepared arrays or scientific scores were changed. No nearby mainland temperature was substituted. See the accompanying JSON for source hashes, exact coordinates, dates, raw values and all unsupported tract IDs.
