Rewrite county descriptions in plain, human language. The user explicitly rejected the academic tone and economy-first checklist. Their brief: "Just explain why a county's risk scores are high based on what you know about the county." Explain the place and what makes its hazards matter. Economy, population, geography, climate, housing and land use are relevant ONLY when they help tell that story. Do not force any one of them into every county.

Target: 1–2 sentences, usually 25–55 words, <=500 characters. Example: "Cook County includes Chicago and about 5.2 million people. Hot Midwest summers, dense neighborhoods and a huge concentration of homes and businesses make extreme heat a major concern here."

Lead with recognizable places and concrete characteristics: cities, farms, forests, mountains, coastlines, dry weather or flood-prone settlements. Connect those to the relevant hazard in everyday terms. Use the supplied local facts, reviewed evidence and risk results. Familiar, reliable regional knowledge is welcome; do not invent named facilities, precise statistics, slopes, housing patterns or cities. Approximate population to 2–3 significant digits when it helps. Do not mechanically add population, industry lists, dates or numbers to every entry.

Explain what makes a hazard consequential, not the percentile calculation. Avoid academic ranking language and statistical contrasts: no "earnings base," "national upper quarter," "percentile," "baseline," "frames its exposure," "provides context," "aggregate exposure," or "vulnerability-adjusted." No repetitive disclaimers, "FEMA says" boilerplate, or long sector lists. Avoid semicolons and parenthetical qualifications. A natural "because" or "makes X a concern" is fine when the connection is sound; do not invent what caused an exact model score. Never claim regional location alone proves a high score.

Choose hazards using both actual results and physical common sense. Do not describe low/unrated risk as high, or inland flooding as coastal flooding. Do not invent hurricane exposure for an inland Midwest county merely because a rank looks high. Drought is primarily agricultural in this model: connect it to farms where relevant, not automatically to office employment. Consider meaningful current exposure, not only the single highest percentile. If the scores are unavailable, explain plausible hazards without asserting a rating.

Read your assignment in manageable batches. Author descriptions individually, not using a prose template or regex substitutions. Output a JSON object mapping each assigned five-digit ID to its description in /tmp/fri-plain-context/descriptions-N.json. Save incremental batches in that directory, merge them into your final output, verify every ID exactly once, and check length. Do not edit repo files, git, source evidence, cloud data, or other agents' output. Do not spawn agents. Report the final count and a few examples. Root will integrate, review and validate.

For publication, root merges the revised wording into the existing research record,
retaining its source URLs, pinned Wikipedia revisions, evidence, dates and checked
reference baseline values. Each revised record sets `languageStyle` to
`plain-place-context`. Those reference values are research inputs, not a requirement
to recite rankings in the public paragraph. Numerical or fixed future-scenario
claims must still be verified against their exact data; the plain explanation
must not invent why a model produced a particular number.
