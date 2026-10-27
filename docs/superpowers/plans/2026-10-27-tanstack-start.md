# TanStack Start migration implementation plan

> **For agentic workers:** Execute inline using executing-plans; keep the same migration commit in both branch histories.

**Goal:** Prerender useful HTML through TanStack Start while preserving the archive UI, combined analysis preview, version documents and existing static hosts.

**Architecture:** TanStack Start owns the HTML document, routing and hydration. Prerender the index with the existing welcome primer; isolate the interactive explorer behind a client-only lazy boundary because it reads URL/storage state and uses WebGL. Continue generating standalone version pages and serving score-bearing PMTiles through the existing Pages worker. No server runtime or new climate calculations are required.

**Tech Stack:** React, TanStack Start/Router, Vite 8, Fontsource, MapLibre, PMTiles, static GitHub Pages and Cloudflare Pages.

## Tasks

- [x] Add a failing artifact check in `scripts/check_static.mjs`: require meaningful prerendered introduction, metadata, module entry and working local assets/documents at `/` and `/nri-future-risk/`. Run it against an existing build to confirm the empty SPA root fails.
- [x] Install compatible Start/Router and Vite/React plugin versions; update the lockfile and Node requirement. Add `src/router.tsx`, `src/routes/__root.tsx` and `src/routes/index.tsx`. Move document metadata and analytics from `index.html` to the root route; remove `src/main.tsx` and the obsolete HTML entry.
- [x] Configure `vite.config.ts` with Start before React, static prerendering, the existing base path and no crawling of binary download links. Keep the explorer client-only and lazy, with `WelcomePrimer` as useful static fallback content.
- [x] Add `scripts/prepare_static.mjs` to retain only the static client output in `dist/`, preserving version pages and downloads. Run the artifact check at the end of `npm run build`. Keep Cloudflare's preparation and PMTiles worker after this step.
- [x] Raise the GitHub Pages build to Node 22 and exclude generated route/build state from lint/git. Document the new build and static-host model in README.
- [x] Verify tests, lint, both base-path builds, actual no-JavaScript HTML and hosted PMTiles/documents. Commit the migration on the UI branch.
- [ ] Merge the UI branch into the combined branch so that migration commit is shared literally. Resolve only release registry, analysis-specific documentation/build default and pipeline-only files by retaining the combined versions. Re-run tests and both production builds there.
- [ ] Push both branches, watch Cloudflare CI, verify the branch preview comment and browser hydration, version switching and guide behavior. Confirm `git merge-base --is-ancestor MIGRATION_COMMIT` succeeds on both branches. Keep the pipeline PR independent.
