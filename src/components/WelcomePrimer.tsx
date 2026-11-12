import { areaLabel, areasLabel, release } from '../data/releases';

const image = (name: string) => `${import.meta.env.BASE_URL}guide/${name}.jpg`;

function Example({ src, alt, caption, children }: { src: string; alt: string; caption: string; children: React.ReactNode }) {
  return (
    <figure className="primer-example">
      <img src={image(src)} alt={alt} width={1100} height={687} loading="lazy" decoding="async" />
      <figcaption>{caption}</figcaption>
      {children}
    </figure>
  );
}

export default function WelcomePrimer() {
  return (
    <div className="prose">
      <h3>What is it?</h3>
      <p>
        FEMA released the Future Risk Index in December 2024 and removed it from
        public view in early 2025. This is a rebuilt version, and the first free
        tool to show how much climate change could cost American communities.
      </p>
      <p>
        It adds a climate multiplier to FEMA’s National Risk Index, which
        estimates the economic impact of natural hazards.{' '}
        <a href="https://www.publicenvirodata.org/">Public Environmental Data Partners</a>
        {' and '}<a href="https://www.fultonring.com/">Fulton Ring</a> maintain it.
      </p>

      <h3>How to read the map</h3>
      <p>
        The map shows one hazard, measure, time period and emissions scenario at a
        time. Change them with the controls; select a {areaLabel} for its details.
      </p>
      <p>
        <strong>Annual loss rating</strong> is projected average yearly loss,
        grouped into FEMA’s five categories. FEMA set the category edges by
        clustering baseline losses, so the ranges are uneven. They are thresholds,
        not uncertainty ranges.
      </p>
      <p>
        <strong>Risk rating</strong> adjusts annual loss for social vulnerability
        and community resilience. It compares {areasLabel}; it is not the chance
        of an event.
      </p>
      <p>
        <strong>Change in annual loss</strong> is future loss divided by baseline
        loss: 4× means four times the baseline. A large multiplier on a small loss
        can still be a small dollar amount.
      </p>

      <h3>Three places, three different stories</h3>
      <p>
        These examples use the FEMA archive release. The legend chart marks where
        the selected county falls in each category.
      </p>

      <Example
        src="kings-coastal-flooding"
        alt="Coastal flooding annual loss map of New York City with Brooklyn outlined; most coastal counties are in the darkest category, and the legend chart marks Brooklyn in Very high."
        caption="Brooklyn: coastal flooding annual loss, mid-century, intermediate sea-level rise."
      >
        <p>
          <strong>Brooklyn (Kings County, NY)</strong> already has large heat
          and hurricane losses: about $26 million and $78 million a year at
          baseline. Coastal flooding is what moves. About $19
          million a year becomes about $76 million by mid-century under the lower
          sea-level scenario (4.1×), moving Brooklyn from Relatively High to Very
          High. Under the high scenario late in the century, the multiplier reaches
          42×, about $780 million a year. With this much property beside the water,
          a moderate change in the hazard means very large losses.
        </p>
      </Example>

      <Example
        src="napa-drought"
        alt="Drought annual loss map of the San Francisco Bay Area with Napa County outlined in the darkest category; the legend chart marks Napa near the top of Very high."
        caption="Napa County: drought annual loss, mid-century, lower emissions."
      >
        <p>
          <strong>Napa County, CA</strong> is known for wildfire, but wildfire is
          not where its projections change most: about $4 million a year, rising
          8–22%. Drought already costs about $85 million a year in crop
          losses. It rises 2.8× by mid-century under lower emissions (about
          $240 million) and 6.9× by late century under higher emissions. The
          rating stays Very High the whole time because it is already the top
          category, so check the dollar figures and multiplier, not just the color.
        </p>
      </Example>

      <Example
        src="sedgwick-drought-change"
        alt="Map of drought change in annual loss across the Great Plains, nearly all in the darkest category, with Sedgwick County, Kansas outlined; the legend chart marks it above 4 times baseline."
        caption="Sedgwick County: drought change in annual loss, late century, higher emissions."
      >
        <p>
          <strong>Sedgwick County, KS</strong> (Wichita) sits in a sea of the
          darkest color on the drought multiplier map: 9.6× by late century under
          higher emissions. But its baseline drought loss is about $170,000 a
          year, so 9.6× is about $1.6 million. Extreme heat grows less, 2.2× by
          mid-century and 5× by late century, yet adds far more: from $2.8
          million to $6.3 million and $14 million a year. Use change in annual
          loss to see where risk is growing, and annual loss to see how much is at
          stake.
        </p>
      </Example>

      <h3>Scenarios and time periods</h3>
      <p>
        Lower and higher emissions are alternative climate futures from IPCC
        scenario families; they are not assigned probabilities.
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
        late-century (2070–2099). Baseline means the selected {release.baseline}{' '}
        National Risk Index release, not conditions today.
      </p>

      <h3>What’s not included</h3>
      <p>
        Population growth, demographic change, land use and adaptation. The
        projections hold today’s exposure and social conditions fixed.
      </p>
      <p>
        Results describe entire {areasLabel}; zooming in adds geographic context,
        not scientific resolution. Gray means unavailable, white means no rating
        and pale gray means not applicable. None of these mean zero losses. Use
        local information alongside these projections for decisions about a
        specific property.
      </p>

      <h3>What can I do with this information?</h3>
      <ul className="primer-actions">
        <li><strong>Check risk before you move.</strong> A home that’s safe now might not be in 20 years.</li>
        <li><strong>Be ready for your area’s hazards.</strong> Make a plan and know where you’ll go. See <a href="https://www.ready.gov/">ready.gov</a>.</li>
        <li><strong>Homeowners, prepare your house.</strong> Stronger hurricanes? Reinforce the roof. Rising wildfire risk? Clear vegetation.</li>
        <li><strong>Renters, ask your landlord.</strong> Show them the map and ask how the building is prepared.</li>
        <li><strong>Use it in your work.</strong> Planning, emergency management, insurance, finance, engineering and research all depend on how these risks change.</li>
      </ul>
    </div>
  );
}
