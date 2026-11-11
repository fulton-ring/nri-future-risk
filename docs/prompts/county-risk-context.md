# County risk-context research and writing

User-approved brief: Research the county’s economy, demographics, and geography alongside its actual risk results. Write 1–2 sentences highlighting local characteristics most relevant to interpreting those results relative to other counties. Consider population, economic activity, exposed assets and landscape. Distinguish plausible context from demonstrable model inputs; don't invent causes of scores. Cite substantive claims.

You own assigned FIPS only. Read assignment-N.json, basis.json and dossiers/FIPS.json in this directory. Each dossier contains current Census population, primary BEA industry earnings, locality-specific economic research where available, pinned Wikipedia evidence, exact archived NRI v1.19 baseline results for all five hazards, and an optional same-state peer selected by similar population. Projected results are supplied for research orientation ONLY.

OUTPUT: descriptions-N.json mapping every assigned FIPS to:
{
 "description": "1–2 natural sentences, usually 35–65 words, max700 characters",
 "sources": [{"title":"...","url":"https://...","revisionId":123 if Wikipedia}],
 "evidence": [{"claim":"local substantive fact","basis":"wiki.geography|wiki.economy|population|BEA|localDescription|external","support":"exact source phrase or field/value","url":"source URL"}],
 "comparisons": [{"kind":"riskPercentile","hazard":"DRGT","value":97.5,"relation":"top10"}]
}

Comparison shapes allowed:
- riskPercentile: exact dossier baselineNRIv119[hazard].nationalRiskScore; relation top10 (>=90), top25 (>=75), aboveMedian (>=50), belowMedian (<50), bottom25 (<=25), bottom10 (<=10). Never classify null/NoRating as low risk.
- lossPercentile: exact lossPercentileAmongMapped3218; same relations, prose must say among mapped counties, not FEMA's national score.
- populationPercentile: exact population.percentileAmongMappedCounties with same relations. Use only when meaningful; it cannot replace a valid actual-risk comparison merely to save effort.
- riskContrast: hazards:["DRGT","WFIR"], values:[exact nationalRiskScore, exact nationalRiskScore]. Explain the actual baseline contrast, not fixed future ratings.
- lossPeer: hazard, peerId, countyValue, peerValue and relation above/below; exact annualLoss from matching baseline and peer. A same-population peer is NOT necessarily adjacent geographically.

Need at least one useful, defensible cross-county or cross-hazard risk comparison if baseline ratings exist. Prefer national risk percentile comparisons; don't add raw dollar values already shown in the panel. Qualitative phrases must match the comparison. A score of 80 means upper fifth for ranking, NOT 80% probability. Risk index value is adjusted loss, not literal dollars. The comparison proof must support prose, not be attached to unrelated boilerplate.

PUBLICATION: Narrative is shared across releases and map filters. Every risk comparison in text MUST explicitly say baseline/FEMA's baseline. Never present a fixed projected rank, category, multiplier or future-loss amount as applying to all scenarios. Baseline is identical across archive and new analysis (verified). Population estimates are contemporary context and do not replace model baseline exposure. Source baseline comparisons with basis.json riskSourceUrl. If no valid baseline score exists, use sourced exposure/scale context, not 'safe' or invented numbers; record that in evidence.

Source and model discipline:
- DRGT=drought; WFIR=wildfire; EXHT=extreme heat; CFLD=COASTAL flooding, NOT river flooding; HRCN=hurricanes. A river/lake location alone does NOT explain coastal-flood risk. Inland does not imply zero hurricane risk.
- Drought NRI losses quantify agriculture, not lost factory output or household water bills. General local economy is context, not proof of what loss is modeled. Do not say steel plants cause high drought scores. Other hazards can monetize fatalities/injuries as well as property/agriculture; don't describe all loss as building damage.
- No heat ratio inference or claim a 1x multiplier means no warming. No unsupported poverty, age, vulnerability, resilience, urban heat island, WUI, evacuation or adaptation claims.
- BEA measures local wages/benefits/proprietor earnings, not resident-worker/job counts or GDP. Other sectors may be suppressed. Use 'includes' or observed shares, not largest/leading without complete data. Farm earnings are not acreage. Do not infer farming from rural/state names.
- Wikipedia excerpts can be sparse or malformed by unit templates; skip missing quantities. Dates and sources matter. Census population takes precedence over older Wiki population. If quoting population count/year, use latest supplied year and at most3significantdigits. Size terms should match provided percentiles, not a guessed rural/urban label.
- Distinctive physical/economic facts must be in provided evidence or in an actually fetched public source. You can inspect full cached Wikipedia revisions under /tmp/fri-county-context/cache or fetch local government/USDA/extension/EDC material when necessary. Preserve pinned Wiki source revisions; no invented citations.
- Keep supporting exact source excerpts short, <=25words per source URL. Prefer factual field references for Census/BEA/risk evidence. Do not copy long source prose.

STYLE: These are researched context paragraphs, not a templated population sentence + three-industry list. Synthesize each place's meaningful traits and observed risk profile. Don't repeat 'this provides useful context', 'economic exposure matters', source/process limitations or county-seat/founding trivia. No generic risk-disclaimer boilerplate. No unsupported causal certainty; juxtapose/qualify plausible context clearly. Don't write lists of scenic features with no risk relevance. Don't force geography into every county. Every description should offer more insight than the old industry template.

Work incrementally: read 15–25 dossiers at a time, author actual prose, persist batches. Do not generate narrative templates in Python as substitute for individual writing. Author all assigned counties, not a sample. Then self-audit exact FIPS, comparison thresholds and named facts. Flag genuine evidence issues in issues-N.json rather than fabricate. Don't edit repo files/git/UI; root integrates and audits. Do not spawn more agents.
