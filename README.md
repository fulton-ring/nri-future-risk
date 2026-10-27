# Climate Informed Risk Index

[Visit Tool](https://fulton-ring.github.io/nri-future-risk/)

Public Environmental Data Partners and Fulton Ring maintain this atlas of FEMA’s
discontinued National Risk Index (NRI) Future Risk tool, which
was removed from the public by the US Government in February, 2025. It
references the following datasets which were downloaded before the tool was
taken down:

- [NRI Future Risk Master Datasheet](https://github.com/fulton-ring/nri-future-risk/blob/main/public/NRI_Future_Risk_Master_Datasheet_12052024.xlsx)
- [NRI Data Dictionary](https://github.com/fulton-ring/nri-future-risk/blob/main/public/NRI_Data_Dictionary.xlsx)

[Donate To The Developers](https://buymeacoffee.com/herzo175)

## Architecture

The atlas uses TanStack Start and Router with React, TypeScript, MapLibre GL JS and PMTiles.
Vite builds a prerendered static site for GitHub Pages and Cloudflare Pages.
Fonts are provided by Fontsource, and dropdowns/dialogs use shadcn components.
The map reads archived scores and ratings directly from PMTiles properties.
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

## Archived display assets

`public/atlas/counties.pmtiles` contains geometry and all five hazards’ archived
scores, ratings and multipliers. `public/atlas/counties.json` stores the same
attributes in columnar JSON for county profiles and the national table.
`src/data/release.json` records asset paths, SHA-256 hashes, the source hash and
release identity. The archived source GeoJSON and workbooks remain available.

To regenerate these checked-in assets, install [tippecanoe](https://github.com/felt/tippecanoe), then run:

```bash
npm run assets:archive
```

This command changes display formats only; it does not recompute the science.
New reconstructed products must be validated before replacing the release
manifest. All currently displayed values are labeled as the December 2024 archive.

Shared URLs retain the release, county, hazard, measure, time period, emissions,
heat model and map camera. Unrecognized releases produce a visible warning.
The optional OpenFreeMap Bright basemap supplies roads and place labels,
with Mapzen/USGS terrain shading. Map layers controls adjust county opacity and
terrain visibility, which are retained in shared URLs; the county overlay
and data table remain independent of that provider.

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
Methodology and Data pages. This UI branch includes only the FEMA archive; the
new analysis data and its pipeline remain on the combined preview branch.
Shared links retain the selected release. The main header links to GitHub, and
the help button reopens the welcome guide. The guide opens once per tab session,
so changing versions does not show it again.

Every build generates the version pages with `scripts/build_version_pages.mjs`.
They include the original technical document, download links and source checksums.

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
