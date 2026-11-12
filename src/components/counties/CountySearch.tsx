import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { release } from "../../data/releases";
import type { County } from "../../lib/risk";
import { localPlaces, type LocalPlace } from "../../lib/location-search";
import {
  searchPlaces,
  resolvePlaceArea,
  type PlaceResult,
} from "../../clients/geocoding";
export default function CountySearch({
  counties,
  onLocate,
}: {
  counties: County[];
  onLocate: (place: PlaceResult, areaId?: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [remote, setRemote] = useState<PlaceResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const request = useRef<AbortController | null>(null);
  const autocompleteTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  useEffect(
    () => () => {
      clearTimeout(autocompleteTimer.current);
      request.current?.abort();
    },
    [],
  );
  const id = useId();
  const local = useMemo(() => localPlaces(counties, query), [counties, query]);
  const results: (PlaceResult | LocalPlace)[] = [...local, ...remote];
  const begin = () => {
    clearTimeout(autocompleteTimer.current);
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setMessage("");
    return controller;
  };
  const search = async (searchQuery = query) => {
    if (searchQuery.trim().length < 3) return;
    const controller = begin();
    setOpen(true);
    setActive(-1);
    try {
      const places = await searchPlaces(searchQuery.trim(), controller.signal);
      if (controller.signal.aborted) return;
      setRemote(places);
      if (!places.length)
        setMessage("No places found. Try a full address with city and state.");
    } catch {
      if (!controller.signal.aborted)
        setMessage(
          "Location search is unavailable. Try a county name or select the map.",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const select = async (place: PlaceResult | LocalPlace) => {
    const controller = begin();
    try {
      let areaId = "areaId" in place ? place.areaId : undefined;
      if (place.kind === "address") {
        const found = await resolvePlaceArea(
          place,
          release.baseline,
          release.geography ?? "counties",
          controller.signal,
        );
        if (controller.signal.aborted) return;
        areaId =
          found && counties.some((c) => c.id === found) ? found : undefined;
      }
      if (controller.signal.aborted) return;
      onLocate(place, areaId);
      setQuery(place.label);
      setOpen(false);
      setMessage(
        place.kind === "address" && !areaId
          ? "No matching risk area in this version. Choose an area on the map."
          : "",
      );
    } catch {
      if (!controller.signal.aborted)
        setMessage(
          "Couldn’t locate the risk area. Try again or select the map.",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return (
    <div
      className="county-search"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          clearTimeout(autocompleteTimer.current);
          setOpen(false);
        }
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (active >= 0 && results[active]) void select(results[active]);
          else void search();
        }}
      >
        <label className="sr-only" htmlFor={id}>
          Address, city, or county
        </label>
        <input
          id={id}
          type="search"
          role="combobox"
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={open && !!query}
          aria-controls={`${id}-results`}
          aria-activedescendant={
            open && results[active] ? `${id}-${active}` : undefined
          }
          placeholder="Address, city, or county"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            const value = e.target.value;
            clearTimeout(autocompleteTimer.current);
            request.current?.abort();
            setBusy(false);
            setQuery(value);
            setRemote([]);
            setMessage("");
            setOpen(true);
            setActive(-1);
            if (value.trim().length >= 3) {
              autocompleteTimer.current = setTimeout(
                () => void search(value),
                350,
              );
            }
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              clearTimeout(autocompleteTimer.current);
              request.current?.abort();
              setBusy(false);
              setOpen(false);
            }
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              setOpen(true);
              setActive((n) =>
                Math.max(
                  -1,
                  Math.min(
                    results.length - 1,
                    n + (e.key === "ArrowDown" ? 1 : -1),
                  ),
                ),
              );
            }
          }}
        />
        <button
          className="location-submit"
          type="submit"
          aria-label="Search location"
          disabled={busy}
        >
          <Search size={17} aria-hidden="true" />
        </button>
      </form>
      {open && query && (
        <div className="search-results">
          <ul id={`${id}-results`} role="listbox" aria-label="Matching places">
            {results.map((place, i) => (
              <li
                key={place.id}
                id={`${id}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => e.preventDefault()}
              >
                <button type="button" onClick={() => void select(place)}>
                  <span>
                    {place.label}
                    <small>{place.detail}</small>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {remote.length > 0 && (
            <small className="search-attribution">
              Places:{" "}
              <a
                href="https://www.openstreetmap.org/copyright"
                target="_blank"
                rel="noreferrer"
              >
                © OpenStreetMap
              </a>{" "}
              · Addresses: US Census Bureau
            </small>
          )}
        </div>
      )}
      <p className="search-status" role="status">
        {busy ? "Finding location…" : message}
      </p>
    </div>
  );
}
