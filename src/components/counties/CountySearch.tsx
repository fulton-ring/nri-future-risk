import { useId, useState } from "react";
import { Search } from "lucide-react";
import type { County } from "../../lib/risk";
export default function CountySearch({
  counties,
  onSelect,
}: {
  counties: County[];
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const id = useId();
  const results = query.trim()
    ? counties
        .filter((c) =>
          `${c.name}, ${c.state} ${c.id}`
            .toLowerCase()
            .includes(query.toLowerCase()),
        )
        .slice(0, 8)
    : [];
  const select = (county: County) => {
    onSelect(county.id);
    setQuery("");
    setOpen(false);
  };
  return (
    <div
      className="county-search"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false);
      }}
    >
      <label className="sr-only" htmlFor={id}>
        Search counties by name, state abbreviation or FIPS
      </label>
      <Search size={18} aria-hidden="true" />
      <input
        id={id}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open && !!query}
        aria-controls={`${id}-results`}
        aria-activedescendant={
          open && results[active] ? `${id}-${active}` : undefined
        }
        placeholder="Find a county…"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            setActive((n) =>
              Math.max(
                0,
                Math.min(
                  results.length - 1,
                  n + (e.key === "ArrowDown" ? 1 : -1),
                ),
              ),
            );
          }
          if (e.key === "Enter" && open && results[active]) {
            e.preventDefault();
            select(results[active]);
          }
        }}
      />
      {open && query && (
        <ul
          className="search-results"
          id={`${id}-results`}
          role="listbox"
          aria-label="Matching counties"
        >
          {results.length ? (
            results.map((county, i) => (
              <li
                key={county.id}
                id={`${id}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => e.preventDefault()}
              >
                <button tabIndex={-1} onClick={() => select(county)}>
                  <span>{county.name}</span>
                  <small>
                    {county.state} · {county.id}
                  </small>
                </button>
              </li>
            ))
          ) : (
            <li role="option" aria-disabled="true" aria-selected="false">
              No counties found. Try a name or state abbreviation.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
