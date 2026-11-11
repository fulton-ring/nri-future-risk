import useSWR from "swr";
import { release } from "../../data/releases";
import { assetUrl } from "../../clients/api";
import type { County } from "../../lib/risk";

type CountyContextData = {
  description: string;
  sources: { title: string; url: string }[];
  attribution?: string;
  sourceNote?: string;
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

export default function CountyContext({ county }: { county: County }) {
  const { data } = useSWR<ContextAsset>(contextAssetUrl, fetchCountyContext, {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    shouldRetryOnError: false,
  });
  const context = data?.counties[county.id];

  if (!context || typeof context.description !== "string" || !context.description.trim())
    return null;

  const sources = Array.isArray(context.sources)
    ? [...new Map(context.sources.map(source=>[source.url,source])).values()].filter(
        (source) =>
          typeof source?.title === "string" &&
          typeof source.url === "string" &&
          /^https?:\/\//i.test(source.url),
      )
    : [];

  return (
    <section className="county-context" aria-label={`${county.name} context`}>
      {release.baseline === 'NRI v1.20' && <p className="caption">County context compares archived NRI v1.19 values.</p>}
      <p>{context.description}</p>
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
          <p className="county-context-attribution">{context.attribution ?? 'Adapted from Wikipedia by AI; wording changed.'} {sources.some(source=>source.url.includes('en.wikipedia.org/')) && <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a>}</p>
        </details>
      )}
    </section>
  );
}
