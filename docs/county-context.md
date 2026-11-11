# County context

The county panel describes population and local economic activity for all 3,218
selectable counties and county equivalents. It sits immediately below the score
overview. These figures provide context; they do not change the selected risk
version's population, exposure or scientific inputs.

Census population estimates cover every selectable FIPS. Most use July 1, 2025;
the eight legacy Connecticut counties use explicitly dated 2020 estimates because
Census now publishes planning regions. Boundaries are never silently remapped.

For 3,087 exact-matching BEA geographies, the economic evidence is CAINC5N earnings
by place of work: wages, supplements and proprietor income. The prose selects up
to three positive, disclosed industry categories and says they were *included* in
local earnings. It does not claim a complete industry ranking, count jobs or
resident workers, or substitute GDP for earnings. All 21 nonoverlapping categories
are parsed, including farming, forestry/fishing, manufacturing, retail and
transportation. Suppressed values stay unavailable.

The 131 gaps—including Puerto Rico, some Virginia county/city combinations and
two Hawaii counties—use reviewed locality-specific descriptions and quotations
in `scripts/county-economy-overrides.json`. Four additional example counties have
more specific economic descriptions there. Combined economic regions are never
assigned to an individual city. Geography appears only in selected hazard notes
where it adds relevant context, such as irrigation dependence for Yakima drought.

`public/context/counties.json` stores the prose, supporting facts, dates and source
links. It is loaded once on county selection and cached; visitors make no model
or external-source requests. **Sources** explains the measures and attributes
Wikipedia-derived text under CC BY-SA 4.0 where applicable. The code's license is
unchanged.

## Refresh

1. Run `python scripts/collect_county_population.py` and
   `python scripts/collect_county_economy.py`. These download public bulk files
   without API keys and write working data under `/tmp/fri-county-economy`.
2. Review boundary gaps and refresh the locality-specific prose, source links and
   supporting quotations in `scripts/county-economy-overrides.json`. Add no facts
   from geographic stereotypes or historical industries without current evidence.
3. Run `python scripts/update_county_economy_context.py`. It requires complete
   FIPS coverage, preserves dates and suppression, and adds no model calls.
4. Run `npm test`, `npm run lint`, and `VITE_BASE_PATH=/ npm run build`.
   Check short and long descriptions and hazard notes in the panel. Cloudflare
   packaging retains `context`; the preview HTTP check compares hosted data with
   the build.

The earlier Wikipedia collector/assembler remain available for new editorial
research, but normal refreshes use the population/economy path above. Never
silently replace descriptions by refreshing source evidence alone.
