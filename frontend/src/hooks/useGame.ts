import { useState, useEffect, useCallback } from "react";
import * as gameApi from "../api/game";
import type { GameState, HintType } from "../types/api";

interface UseGameReturn {
  state: GameState | null;
  loading: boolean;
  error: string | null;
  submitting: boolean;
  submitGuess: (input: string, playerId?: number) => Promise<GameState>;
  unlockHint: (type: HintType) => Promise<GameState>;
  surrender: () => Promise<GameState>;
}

export function useGame(token: string): UseGameReturn {
  const [state, setState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    gameApi
      .getGame(token)
      .then((data) => {
        if (!cancelled) setState(data);
      })
      .catch(() => {
        if (!cancelled) setError("Partita non trovata o scaduta.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const submitGuess = useCallback(
    async (input: string, playerId?: number): Promise<GameState> => {
      setSubmitting(true);
      try {
        const next = await gameApi.submitGuess(token, input, playerId);
        setState(next);
        return next;
      } finally {
        setSubmitting(false);
      }
    },
    [token]
  );

  const unlockHint = useCallback(
    async (type: HintType): Promise<GameState> => {
      const next = await gameApi.unlockHint(token, type);
      setState(next);
      return next;
    },
    [token]
  );

  const surrender = useCallback(async (): Promise<GameState> => {
    const next = await gameApi.surrender(token);
    setState(next);
    return next;
  }, [token]);

  return { state, loading, error, submitting, submitGuess, unlockHint, surrender };
}
