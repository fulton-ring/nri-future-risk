# Climate Informed Risk Index

[Visit Tool](https://fulton-ring.github.io/nri-future-risk/)

Public Environmental Data Partners and Fulton Ring maintain this atlas of FEMA’s
discontinued National Risk Index (NRI) Future Risk tool, which
was removed from the public by the US Government in February, 2025. It
references the following datasets which were downloaded before the tool was
taken down:

- [NRI Future Risk Master Datasheet](https://storage.googleapis.com/future-risk-index-results/future-risk-index/fri/counties/v20241205T000000Z/originals/NRI_Future_Risk_Master_Datasheet_12052024.xlsx)
- [NRI Data Dictionary](https://storage.googleapis.com/future-risk-index-results/future-risk-index/fri/counties/v20241205T000000Z/originals/NRI_Data_Dictionary.xlsx)

[Donate To The Developers](https://buymeacoffee.com/herzo175)

## Architecture

The atlas uses TanStack Start and Router with React, TypeScript, MapLibre GL JS and PMTiles.
Vite builds a prerendered static site for GitHub Pages and Cloudflare Pages.
Fonts are provided by Fontsource, and dropdowns/dialogs use shadcn components.
The map reads version-specific ratings and multipliers directly from PMTiles properties.
A separate lossless attribute table supports county search, comparisons and
the accessible national table independently of the visible tiles.

- [Vite](https://vitejs.dev/)
- [React](https://reactjs.org/)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/)
- [PMTiles](https://docs.protomaps.com/pmtiles/)
- [Shadcn](https://ui.shadcn.com/)

## Running Locally

To get started, clone the repository and run the following commands:

```bash
npm install
npm run dev
```

This will start the development server and open the tool in your default browser.

## Release data

All release data is served from the public results bucket
(`gs://future-risk-index-results`), not from this repository. Each entry in
`src/data/releases.json` records its asset URLs and SHA-256 hashes; the explorer
verifies JSON assets against those hashes before using them.

- FEMA archive (December 2024): `future-risk-index/fri/counties/v20241205T000000Z/`,
  with FEMA's values unchanged as GeoParquet, the original workbook, data dictionary
  and GeoJSON, and the explorer's PMTiles and JSON. See
  [`pipeline/README.md`](pipeline/README.md#fema-archive-version-one-time-backfill).
- Recreated NRI v1.20 county and tract releases: `future-risk-index/fri/{counties,tracts}/<version>/`.

The workbook and archived GeoJSON also stay in `public/` because the pipeline's frozen
baseline uses them. The original archive remains selectable alongside recreated
analyses; each release identifies its own baseline and methodology.

Shared URLs retain the release, county, hazard, measure, time period, emissions,
heat model and map camera. Unrecognized releases produce a visible warning.
The optional OpenFreeMap Bright basemap supplies roads and place labels,
with Mapzen/USGS terrain shading. Map layers controls adjust county opacity and
terrain visibility, which are retained in shared URLs; the county overlay
and data table remain independent of that provider.

## Analytics

Umami and PEDP's PostHog project both run on the site. PostHog autocaptures
pageviews and clicks; `src/analytics/track.ts` adds these named events, each
with the selected `release`:

| Event | Properties |
| --- | --- |
| `map_setting_changed` | `setting` (hazard, metric, period, emissions, model), `value` |
| `map_layer_changed` | `setting` (terrain), `value` |
| `data_version_changed` | `from`, `to` |
| `area_selected` | `area_id` (FIPS/GEOID), `source` (map, table, search) |
| `location_searched` | `result_kind`, `result_source`, `matched_area` — never the search text |
| `result_view_changed` | `view` (map, table) |
| `share_link_copied` | `success` |
| `area_data_downloaded` | `area_id` |
| `welcome_guide_opened` | `trigger` (first_visit, help_button) |
| `panel_toggled` | `panel` (map_settings, area_profile), `open` |
| `legend_toggled` | `open` |
| `map_reset` | — |

## Verification

```bash
npm test
npm run lint
npm run build
```

Tests cover URL round-trips, invalid combinations, missing and zero values,
lossless archive conversion, and actual scores decoded from PMTiles.

## Hosting

To reduce the risk of this tool being taken down again, we recommend forking
this repository and hosting it with GitHub Pages. It currently has all the code
needed to deploy to GitHub Pages, you'll just need to enable GitHub Pages in
your fork's repository settings.

More deployment guides to come as needed.

## Cloudflare PR previews

The Cloudflare preview workflow builds same-repository PRs and `feat/**` branches.
Set the repository secret `CLOUDFLARE_API_TOKEN` (Cloudflare Pages Edit) and
variable `CLOUDFLARE_ACCOUNT_ID` for the `future-risk-index-preview` Pages project.
After deployment and hosted PMTiles checks pass, the workflow posts a preview
link on the PR and updates that comment on subsequent builds.

Run `npm run build:cloudflare` to prepare a root-hosted preview locally.
The Pages worker provides byte-range responses required by PMTiles.

## Version information and welcome guide

The Data version header identifies the displayed dataset and links to its separate
Methodology and Data pages. The selector includes the FEMA archive, earlier
analyses, and the verified NRI v1.20 county and census-tract results. Cloudflare
previews open the current county release by default. Scientific calculations and
infrastructure are reviewed separately in the pipeline PRs.
Shared links retain the selected release. The main header links to GitHub, and
the help button reopens the welcome guide. The guide opens once per tab session,
so changing versions does not show it again.

Every build generates the version pages with `scripts/build_version_pages.mjs`.
They include version-specific methods, download links and source checksums.
Tract PMTiles cover zooms 0–10 with generalized overview geometry, retaining exact
map ratings and multipliers. Tract profiles show their own scores followed by
the containing county or planning region’s sourced description.

## Rendering and static builds

Use Node 22.12 or newer. TanStack Start owns the HTML document, route metadata and
hydration. The introduction is prerendered as readable HTML; the interactive explorer
loads in the browser so WebGL, shared URL state and session storage remain client-only.
Version-specific Methodology and Data pages are generated during the build.

`npm run build` targets `/nri-future-risk/` for GitHub Pages. `npm run build:cloudflare`
targets `/` and prepares the existing PMTiles range worker. The build strips the temporary
SSR output and checks the static HTML, asset URLs and version documents. Both deployments
continue to serve static files; no application server is required.

`npm run preview -- --port 4173 --strictPort` serves the built static site. Set
`VITE_BASE_PATH=/` when previewing a Cloudflare build. `npm run dev` runs Start's development
server. This migration preserves the current version selector and datasets; it does not
add county landing pages or change any scientific values.

## County update pipeline

See [pipeline/README.md](pipeline/README.md) for the independent Hamilton/Cloud Batch
pipeline, Terraform configuration and merge-approved publication contract.

The combined branch preview is available at
https://review-feat-fut-0dc4eaf5.future-risk-index-preview.pages.dev/.
