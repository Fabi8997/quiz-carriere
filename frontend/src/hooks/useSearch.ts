import { useState, useEffect, useRef } from "react";
import { searchPlayers } from "../api/search";
import type { SearchResult } from "../types/api";

const DEBOUNCE_MS = 280;

interface UseSearchReturn {
  query: string;
  setQuery: (q: string) => void;
  suggestions: SearchResult[];
  loading: boolean;
  clear: () => void;
}

export function useSearch(): UseSearchReturn {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }

    setLoading(true);
    timerRef.current = setTimeout(() => {
      searchPlayers(query)
        .then(setSuggestions)
        .catch(() => setSuggestions([]))
        .finally(() => setLoading(false));
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query]);

  function clear() {
    setQuery("");
    setSuggestions([]);
  }

  return { query, setQuery, suggestions, loading, clear };
}
