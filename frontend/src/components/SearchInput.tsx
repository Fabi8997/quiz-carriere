import { useRef, useState, useEffect } from "react";
import { useSearch } from "../hooks/useSearch";
import type { SearchResult } from "../types/api";

interface Props {
  onConfirm: (playerName: string, playerId?: number) => void;
  onSurrender: () => void;
  disabled?: boolean;
}

export function SearchInput({ onConfirm, onSurrender, disabled = false }: Props) {
  const { query, setQuery, suggestions, loading, clear } = useSearch();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  useEffect(() => {
    // Riapre solo se non è già selezionato un giocatore — evita che la ricerca
    // successiva a setQuery(result.name) riapra il dropdown dopo la selezione.
    if (suggestions.length > 0 && !selectedId) setOpen(true);
  }, [suggestions, selectedId]);

  function handleSelect(result: SearchResult) {
    setSelectedName(result.name);
    setSelectedId(result.id);
    setQuery(result.name);
    setOpen(false);
    inputRef.current?.focus();
  }

  function handleSubmit() {
    const value = selectedName ?? query.trim();
    if (!value) return;
    onConfirm(value, selectedId ?? undefined);
    clear();
    setSelectedName(null);
    setSelectedId(null);
    setOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSubmit();
    if (e.key === "Escape") setOpen(false);
  }

  return (
    <div className="flex flex-col gap-2.5">

      {/* Input + dropdown */}
      <div ref={containerRef} className="relative">

        {/* Dropdown — sopra su mobile, sotto su desktop */}
        {open && suggestions.length > 0 && (
          <ul
            className="absolute bottom-full mb-2 left-0 right-0 z-30 bg-white
                       border border-bordo/60 shadow-float max-h-52 overflow-y-auto
                       lg:bottom-auto lg:top-full lg:mt-2 lg:mb-0"
            style={{ borderRadius: "1.25rem" }}
          >
            {suggestions.map((s) => (
              <SuggestionItem key={s.id} result={s} onSelect={handleSelect} />
            ))}
          </ul>
        )}

        {/* Campo di testo pill */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelectedName(null);
            setSelectedId(null);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={loading ? "Cercando…" : "Chi è questo campionissimo?"}
          disabled={disabled}
          className={[
            "w-full h-12 px-5 rounded-full border text-sm bg-white/80 outline-none transition-all duration-200",
            "placeholder:text-grass/50 text-loam",
            disabled
              ? "border-bordo/40 text-grass/40 cursor-not-allowed"
              : "border-bordo focus:border-verde focus:ring-2 focus:ring-verde/20 focus:shadow-soft",
          ].join(" ")}
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      {/* Bottone INDOVINA */}
      <button
        onClick={handleSubmit}
        disabled={disabled || !query.trim()}
        className={[
          "w-full h-12 rounded-full font-display font-bold text-sm tracking-wide transition-all duration-200",
          disabled || !query.trim()
            ? "bg-bordo/60 text-white/60 cursor-not-allowed"
            : "bg-verde text-white shadow-soft hover:bg-verde-dark hover:shadow-float hover:scale-[1.02] active:scale-95",
        ].join(" ")}
      >
        Indovina ▶
      </button>

      {/* Mi arrendo */}
      <button
        onClick={onSurrender}
        disabled={disabled}
        className={[
          "w-full h-10 rounded-full border text-xs font-semibold transition-all duration-200",
          disabled
            ? "border-bordo/30 text-grass/30 cursor-not-allowed"
            : "border-bordo/60 text-grass hover:border-[#ee1d41]/50 hover:text-[#ee1d41] hover:bg-[#ee1d41]/5 active:scale-95",
        ].join(" ")}
      >
        Mi arrendo
      </button>
    </div>
  );
}

function SuggestionItem({
  result, onSelect,
}: {
  result: SearchResult;
  onSelect: (r: SearchResult) => void;
}) {
  return (
    <li>
      <button
        className="w-full text-left px-4 py-3 flex items-center justify-between gap-3 text-sm
                   hover:bg-oro/15 transition-colors duration-150
                   first:rounded-t-[1.25rem] last:rounded-b-[1.25rem]"
        onMouseDown={(e) => { e.preventDefault(); onSelect(result); }}
      >
        <span className="font-semibold text-loam truncate">{result.name}</span>
        <span className="text-xs text-grass whitespace-nowrap flex-shrink-0">
          {result.position_general}
          {result.country_name ? ` · ${result.country_name}` : ""}
        </span>
      </button>
    </li>
  );
}
