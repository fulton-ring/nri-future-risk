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

The atlas uses React, TypeScript, MapLibre GL JS and PMTiles, bundled with Vite.
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

## County update pipeline

See [pipeline/README.md](pipeline/README.md) for the independent Hamilton/Cloud Batch pipeline, Terraform configuration and publication contract.

### Combined analysis preview

`feat/future-risk-preview` combines the atlas interface and county risk infrastructure branches.
The normal build continues to show the FEMA archive. `npm run build:cloudflare` selects the
available-year analysis explicitly and builds at `/` for the dedicated Cloudflare preview project.

The Data version dropdown switches between the FEMA archive and the Batch analysis. Shared URLs carry the selected release ID and override the deployment default. The selector sits in the version disclaimer header on desktop and mobile, alongside the selected version’s status.

The preview contains the completed Batch analysis, with 3,218 county geometries and all five
hazards. Drought, wildfire and LOCA2 heat are recalculated; coastal flooding, hurricane and NEX heat
remain archived. The page identifies the analysis and its 19 missing wildfire years. It is not a
publication candidate. The preview has no connection to the publisher staging workflow.

Preview assets are checked in under `public/preview/`. Rebuild them from the immutable results
manifest and county GeoParquet using `scripts/build_preview_assets.py --help` in the pipeline's
`results` environment. The builder verifies the source hashes and every decoded PMTiles feature's
hazard values. Preview tiles stop at zoom 6 and overzoom for closer views, retaining every county
and numeric attribute while fitting Cloudflare's 25 MiB asset limit. Full source geometry remains
in the original GeoParquet. Map assets, reports and provenance are served with the preview site;
large legacy geometry files are excluded from the deployment. A Pages worker routes only PMTiles requests through Cloudflare’s Cache API because Pages static hosting does not supply HTTP 206 range responses. Cache keys include the asset SHA-256; the cache streams the file and serves partial responses without loading it into JavaScript memory.

```bash
npm ci
npm test
npm run build:cloudflare
npx wrangler@4.152.0 pages deploy dist --project-name future-risk-index-preview \
  --branch review-feat-fut-0dc4eaf5 --force
```

`.github/workflows/preview.yml` builds feature branches and same-repository PRs. Set the repository
variable `CLOUDFLARE_ACCOUNT_ID` and a repository secret `CLOUDFLARE_API_TOKEN` with **Account →
Cloudflare Pages → Edit** for the preview account to enable automatic deployment. Without the token,
the workflow still tests/builds and uploads a review artifact. It does not reuse a personal OAuth
session in CI. Preview branch names always start with `review-`, so they never target the Pages
project's `main` production branch. Cloudflare's `--force` flag selects its existing Pages upload
path rather than the newer Workers migration wrapper.

Combined branch preview: https://review-feat-fut-0dc4eaf5.future-risk-index-preview.pages.dev
