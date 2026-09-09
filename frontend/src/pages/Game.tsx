import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGame } from "../hooks/useGame";
import { CareerTable } from "../components/CareerTable";
import { HintBar } from "../components/HintBar";
import { SearchInput } from "../components/SearchInput";
import { GuessList } from "../components/GuessList";
import { ResultOverlay } from "../components/ResultOverlay";
import { createGame } from "../api/game";
import type { GameFilters, HintType } from "../types/api";

export function Game() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { state, loading, error, submitting, submitGuess, unlockHint, surrender } =
    useGame(token ?? "");

  const [showSurrenderModal, setShowSurrenderModal] = useState(false);
  const [replayLoading, setReplayLoading] = useState(false);
  const nickname = localStorage.getItem("nickname") ?? undefined;

  // Filtri usati per avviare questa partita, salvati da Home.tsx in sessionStorage
  const lastFilters: GameFilters = (() => {
    try { return JSON.parse(sessionStorage.getItem("lastFilters") ?? "{}"); }
    catch { return {}; }
  })();

  const [noMorePlayers, setNoMorePlayers] = useState(false);

  async function handlePlayAgainSame(excludePlayerId: number) {
    setReplayLoading(true);
    setNoMorePlayers(false);
    try {
      const filters = { ...lastFilters, exclude_player_id: excludePlayerId };
      const game = await createGame(filters, nickname);
      sessionStorage.setItem("lastFilters", JSON.stringify(lastFilters));
      navigate(`/gioca/${game.token}`);
    } catch {
      setNoMorePlayers(true);
      setReplayLoading(false);
    } finally { setReplayLoading(false); }
  }

  /* ── Loading ── */
  if (loading) {
    return (
      <div className="min-h-screen bg-crema flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="text-3xl animate-bounce">⚽</span>
          <p className="text-grass text-sm animate-pulse font-medium">Caricamento partita…</p>
        </div>
      </div>
    );
  }

  /* ── Errore ── */
  if (error || !state) {
    return (
      <div className="min-h-screen bg-crema flex flex-col items-center justify-center gap-4 px-6">
        <p className="text-4xl">😕</p>
        <p className="text-grass text-center text-sm max-w-xs">
          {error ?? "Partita non disponibile."}
        </p>
        <button
          onClick={() => navigate("/")}
          className="px-6 py-2.5 rounded-full border-2 border-verde text-verde text-sm font-bold
                     hover:bg-verde hover:text-white transition-all duration-200"
        >
          ← Home
        </button>
      </div>
    );
  }

  const isOver = state.status !== "playing";

  async function handleHint(type: HintType) {
    if (isOver) return;
    await unlockHint(type);
  }

  async function confirmSurrender() {
    setShowSurrenderModal(false);
    await surrender();
  }

  return (
    <div className="min-h-screen bg-crema font-sans flex flex-col">

      {/* ── Header sticky con glassmorphism ── */}
      <header
        className="sticky top-0 z-20 px-4 py-2.5 flex items-center justify-between gap-3"
        style={{
          background: "rgba(45, 90, 39, 0.92)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 4px 20px -2px rgba(45, 90, 39, 0.25)",
        }}
      >
        <button
          onClick={() => navigate("/")}
          className="text-white/60 hover:text-white text-sm transition-colors font-medium"
        >
          ← Home
        </button>

        <h1 className="font-display font-bold text-white text-lg tracking-tight">
          Campionissimo
        </h1>

        <div className="flex items-center gap-1.5">
          <span
            className="px-2.5 py-0.5 rounded-full text-xs font-bold text-verde bg-oro"
            title="Tentativi effettuati"
          >
            {state.attempt_count}
          </span>
        </div>
      </header>

      {/* ── Layout desktop: 2 colonne / mobile: colonna ── */}
      <main className="flex-1 flex flex-col lg:flex-row max-w-5xl mx-auto w-full">

        {/* Sinistra — carriera + tentativi errati (mobile) */}
        <div className="flex-1 flex flex-col p-4 gap-4 lg:overflow-y-auto lg:max-h-[calc(100vh-52px)]">
          <section>
            <p className="text-[11px] font-bold uppercase tracking-widest text-grass mb-2">
              Carriera
            </p>
            <div className="shadow-soft overflow-hidden" style={{ borderRadius: "1.25rem" }}>
              <CareerTable career={state.career} />
            </div>
          </section>

          <div className="lg:hidden">
            <GuessList guesses={state.guesses} />
          </div>
        </div>

        {/* Destra — indizi + tentativi (desktop) + search */}
        <div
          className="lg:w-80 lg:flex-shrink-0 flex flex-col gap-4 p-4
                     lg:border-l lg:border-bordo/40
                     lg:overflow-y-auto lg:max-h-[calc(100vh-52px)]"
        >
          <HintBar hints={state.hints} gameToken={state.token} onUnlock={handleHint} disabled={isOver} />

          <div className="hidden lg:block">
            <GuessList guesses={state.guesses} />
          </div>

          <div
            className="lg:mt-auto sticky bottom-0 bg-crema/95 pt-3 pb-5 lg:static lg:bg-transparent lg:pt-0 lg:pb-0"
            style={{ backdropFilter: "blur(8px)" }}
          >
            {!isOver && (
              <SearchInput
                onConfirm={submitGuess}
                onSurrender={() => setShowSurrenderModal(true)}
                disabled={submitting}
              />
            )}
          </div>
        </div>
      </main>

      {/* Overlay risultato */}
      {isOver && state.player && (
        <ResultOverlay
          game={state}
          nickname={nickname}
          onPlayAgain={() => navigate("/")}
          onPlayAgainSame={handlePlayAgainSame}
          replayLoading={replayLoading}
          noMorePlayers={noMorePlayers}
          onResetNoMore={() => setNoMorePlayers(false)}
        />
      )}

      {/* ── Modale resa ── */}
      {showSurrenderModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-5"
          style={{ background: "rgba(26, 46, 24, 0.65)", backdropFilter: "blur(6px)" }}
          onClick={() => setShowSurrenderModal(false)}
        >
          <div
            className="bg-crema w-full max-w-xs p-6 shadow-float-lg text-center animate-in zoom-in-95"
            style={{ borderRadius: "2rem" }}
            onClick={e => e.stopPropagation()}
          >
            {/* Decorazione */}
            <div
              className="mx-auto mb-4 w-16 h-16 flex items-center justify-center bg-bordo/30"
              style={{ borderRadius: "60% 40% 50% 50% / 50% 60% 40% 50%" }}
            >
              <span className="text-3xl">🏳️</span>
            </div>

            <h3 className="font-display font-bold text-xl text-loam mb-1.5">
              Ti arrendi?
            </h3>
            <p className="text-sm text-grass mb-6 leading-relaxed max-w-[220px] mx-auto">
              Il giocatore verrà rivelato e la partita terminerà.
            </p>

            <div className="flex gap-3">
              <button
                onClick={() => setShowSurrenderModal(false)}
                className="flex-1 h-12 rounded-full border-2 border-bordo text-grass text-sm font-bold
                           hover:border-verde hover:text-verde transition-all duration-200"
              >
                Continua
              </button>
              <button
                onClick={confirmSurrender}
                className="flex-1 h-12 rounded-full bg-verde text-white text-sm font-bold
                           shadow-soft hover:bg-verde-dark hover:shadow-float
                           active:scale-95 transition-all duration-200"
              >
                Mi arrendo
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
