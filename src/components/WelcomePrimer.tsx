export default function WelcomePrimer() {
  return (
    <div className="prose">
      <h3>What is it?</h3>
      <p>
        This is a rebuilt version of FEMA’s Future Risk Index, which was released
        on Dec. 12, 2024 and taken down on Jan. 19, 2025 when the Trump
        administration decided to suppress climate data. It is the first free
        tool to show how much climate change will cost American communities.
      </p>
      <p>
        The Future Risk Index adds a climate change multiplier to FEMA’s National
        Risk Index, which measures the economic impact of natural hazards. The
        Future Risk Index shows how those impacts change when you take climate
        change into account.
      </p>
      <p>
        <a href="https://www.publicenvirodata.org/">Public Environmental Data Partners</a>
        {" and "}<a href="https://www.fultonring.com/">Fulton Ring</a> preserve the
        data and rebuild the tool so it remains available to everyone.
      </p>
      <h3>What does the map show?</h3>
      <p>
        The map shows one hazard, one output type and one emissions scenario at a
        time. Change these using the filters. The available hazards and climate
        models depend on the dataset being shown.
      </p>
      <p>
        <strong>Annual loss rating</strong> shows a county’s projected average
        yearly economic losses as a dollar range and a comparative rating.
        Why the unusual ranges? FEMA used a clustering algorithm to group
        counties into risk tiers in the National Risk Index. The Future Risk
        Index uses those same bins so you can compare baseline and future losses.
        The ranges are category thresholds, not uncertainty intervals.
      </p>
      <p>
        <strong>Risk rating</strong> also includes social vulnerability and
        community resilience, which adjust projected economic losses up or down.
        It is presented as a comparative rating rather than a dollar amount
        because future social conditions are unpredictable. A rating compares
        counties; it is not the probability of an event.
      </p>
      <p>
        <strong>Change in annual loss</strong> is the hazard multiplier. A
        multiplier of 4× means projected future losses are four times baseline
        losses. Some high-risk areas have low multipliers because their baseline
        losses are already high. That is why California’s wildfire multipliers
        can be lower than the Midwest’s. A bigger percentage increase can still
        mean smaller dollar losses and a lighter annual loss rating on the map.
      </p>
      <h3>Where’s the data from?</h3>
      <p>
        FEMA’s input data come from NASA, NOAA, USDA, EPA, USGS, Applied Research
        Associates and others. FEMA spent years selecting data sources and
        refining its methodology. Methodology and Data describe the dataset being
        shown and provide its sources and downloads.
      </p>
      <p>
        The Future Risk Index uses IPCC emissions scenarios: Representative
        Concentration Pathways (RCPs) or Shared Socioeconomic Pathways (SSPs),
        depending on the hazard. Lower and higher emissions describe alternative
        climate futures; they are not assigned probabilities.
      </p>
      <table className="pathway-table">
        <caption>Scenario families by hazard</caption>
        <thead>
          <tr><th scope="col">Hazard</th><th scope="col">Lower</th><th scope="col">Higher</th></tr>
        </thead>
        <tbody>
          <tr><th scope="row">Drought, heat, wildfire</th><td>SSP2-4.5</td><td>SSP5-8.5</td></tr>
          <tr><th scope="row">Hurricane</th><td>RCP 4.5</td><td>RCP 8.5</td></tr>
          <tr><th scope="row">Coastal flooding</th><td>Intermediate SLR</td><td>High SLR</td></tr>
        </tbody>
      </table>
      <p>
        Drought, wildfire and extreme heat use mid-century (2036–2065) and
        late-century (2070–2099) projection periods. Historical reference periods
        vary by hazard and source. Baseline refers to the archived National Risk
        Index, not conditions today.
      </p>
      <h3>What’s not included?</h3>
      <p>
        Future population growth, changing demographics, land use changes and
        adaptation. This tool shows how climate change could affect communities
        if baseline exposure and social conditions stay the same.
      </p>
      <p>
        Results describe entire counties. Zooming in adds geographic context,
        not scientific resolution. Gray means unavailable, white means no rating
        and pale gray means not applicable. These are different from zero losses.
        Use local information alongside these projections when making decisions
        about a specific property.
      </p>
      <h3>What can I do with this information?</h3>
      <p>
        Mitigation, urban and community planning, emergency response, education,
        insurance, finance, research—you tell us. We’re excited to see where you
        go with this. For everyone else, here are some options:
      </p>
      <ul className="primer-actions">
        <li><strong>Check risk before you move.</strong> A home that’s safe now might not be in 20 years.</li>
        <li><strong>Be ready for high-risk hazards.</strong> Make a plan. Know where you’ll go. Don’t forget pets and vulnerable friends and neighbors. See <a href="https://www.ready.gov/">ready.gov</a>.</li>
        <li><strong>Homeowners, prep your house.</strong> Stronger hurricanes? Reinforce the roof. Rising wildfire risk? Clear vegetation.</li>
        <li><strong>Renters, talk to your landlord.</strong> Show them the map. Ask what they’re doing about future risk.</li>
        <li><strong>Vote local.</strong> State and local governments control building codes, disaster funding and infrastructure. Vote for people with climate plans.</li>
        <li><strong>Call out big polluters.</strong> Social media, conversations, protests, wherever. Show people the map. Emissions drive these numbers.</li>
        <li><strong>Join forces.</strong> Find a group working on climate solutions. Go to a meeting. Volunteer. Share your knowledge about future risk.</li>
        <li><strong>Cut emissions where you can.</strong> Climate change is not an individual responsibility, but individual interventions can help: fly less, eat less beef and dairy, and buy less stuff.</li>
        <li><strong>Most importantly—do what you’re good at.</strong> Writers, write about climate. Data scientists and engineers, rebuild a government tool. Tradespeople, talk about how buildings and infrastructure will hold up in more extreme weather. Whatever your skillset, use it.</li>
      </ul>
      <p><strong>The risks on this map aren’t theoretical. They’re coming. Do something, even if it’s a small thing. Protect what you love.</strong></p>
    </div>
  );
}
