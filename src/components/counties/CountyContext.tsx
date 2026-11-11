import useSWR from "swr";
import { assetUrl } from "../../clients/api";
import type { County, Hazard } from "../../lib/risk";

type CountyContextData = {
  description: string;
  sources: { title: string; url: string }[];
  attribution?: string;
  sourceNote?: string;
  riskContext?: Partial<Record<Hazard, {text: string; sources: {title: string; url: string}[]}>>;
};

type ContextAsset = {
  schemaVersion: 1;
  generatedAt: string;
  counties: Record<string, CountyContextData>;
  license: {name: string; url: string; attribution: string};
};

const contextAssetUrl = assetUrl("context/counties.json");

async function fetchCountyContext(): Promise<ContextAsset> {
  const response = await fetch(contextAssetUrl);
  if (!response.ok) throw new Error("County context could not be loaded.");

  const data: ContextAsset = await response.json();
  if (data.schemaVersion !== 1 || !data.counties || typeof data.counties !== "object") {
    throw new Error("County context data is invalid.");
  }
  return data;
}

export default function CountyContext({ county, hazard }: { county: County; hazard: Hazard }) {
  const { data } = useSWR<ContextAsset>(contextAssetUrl, fetchCountyContext, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: false,
  });
  const context = data?.counties[county.id];

  if (!context || typeof context.description !== "string" || !context.description.trim())
    return null;

  const riskContext = context.riskContext?.[hazard];
  const sources = Array.isArray(context.sources)
    ? [...new Map([...context.sources, ...(riskContext?.sources ?? [])].map(source=>[source.url,source])).values()].filter(
        (source) =>
          typeof source?.title === "string" &&
          typeof source.url === "string" &&
          /^https?:\/\//i.test(source.url),
      )
    : [];

  return (
    <section className="county-context" aria-label={`${county.name} context`}>
      <p>{context.description}</p>
      {riskContext && <p>{riskContext.text}</p>}
      {sources.length > 0 && (
        <details>
          <summary>Sources</summary>
          <ul>
            {sources.map((source, index) => (
              <li key={`${source.url}-${index}`}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                </a>
              </li>
            ))}
          </ul>
          {context.sourceNote && <p>{context.sourceNote}</p>}
          <p>Context figures do not change the risk version’s baseline exposure.</p>
          <p className="county-context-attribution">{context.attribution ?? 'Adapted from Wikipedia by AI; wording changed.'} {sources.some(source=>source.url.includes('en.wikipedia.org/')) && <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a>}</p>
        </details>
      )}
    </section>
  );
}
