# County context

The county panel adds short, AI-authored descriptions of the 3,218 selectable
counties and county equivalents, including independent cities, Alaska boroughs
and census areas, and Puerto Rico municipalities. Descriptions describe the
place; they do not explain the numerical score or change any scientific inputs.
They are shared across data versions.

`public/context/counties.json` contains the text and revision-pinned Wikipedia
links. The panel fetches this static asset when a county is selected and reuses
it across selections. Visitors make no Wikipedia or model requests. Source
links and the CC BY-SA 4.0 attribution appear under **Sources**. Descriptions
are adapted text under that license; this does not change the code's license.

## Refresh

1. Run `python scripts/collect_county_context.py`. Evidence and cached API
   responses are written to `/tmp/fri-county-context`; inspect `missing.json`
   and resolve all missing or ambiguous county matches before drafting.
   Cached responses are keyed by requested titles. To collect fresh revisions,
   set `FRI_COUNTY_CONTEXT_WORKDIR` to a new working directory; pass that
   directory to the assembler with `--workdir` as well.
2. Divide the FIPS inventory among small writing agents. Each writes a JSON
   object mapping its assigned FIPS to original prose, saved as
   `descriptions-N.json` in the working directory. Keep each description to
   roughly two sentences. Prefer sourced landscape, settlement, land-use and
   economic facts. Include the date with population figures. Avoid historical
   trivia, generic risk boilerplate, and claims about what caused a score.
   Do not infer agriculture, vulnerability or hazard exposure from a place name.
   Additional curated public-source facts for the example counties are in
   `scripts/county-context-enrichment.json`; use and cite them where relevant.
3. Review drafts against the collected evidence. Resolve gaps using public
   sources rather than inventing descriptions. Run
   `python scripts/assemble_county_context.py` to require complete coverage and
   attach article revision IDs and attribution. This step makes no model calls.
4. Run `npm test`, `npm run lint`, and `VITE_BASE_PATH=/ npm run build`.
   Check short and long descriptions in the county panel, including independent
   cities and Puerto Rico. Cloudflare packaging retains the `context` directory;
   the preview HTTP check compares the deployed descriptions with the build.

Keep source collection and prose generation explicit review steps. Refreshing
Wikipedia evidence alone must not silently replace the deployed descriptions.
