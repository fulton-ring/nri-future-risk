import archive from './release.json';

export const releases = [archive];

export function selectRelease(mode?: string, requestedId?: string | null) {
  const requested = releases.find((item) => item.id === requestedId);
  if (requested) return requested;
  if (!mode || mode === 'archive') return archive;
  throw new Error(`Unknown data release: ${mode}`);
}

const requestedId = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("release");
export const release = selectRelease(import.meta.env?.VITE_DATA_RELEASE, requestedId);
export const isAnalysis = release.status === 'analysis';
