import { useState, useEffect, useRef } from "react";
import { searchTeams } from "../api/search";
import type { TeamResult } from "../types/api";

const DEBOUNCE_MS = 280;

interface UseTeamSearchReturn {
  query: string;
  setQuery: (q: string) => void;
  suggestions: TeamResult[];
  loading: boolean;
  clear: () => void;
}

export function useTeamSearch(): UseTeamSearchReturn {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<TeamResult[]>([]);
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
      searchTeams(query)
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
