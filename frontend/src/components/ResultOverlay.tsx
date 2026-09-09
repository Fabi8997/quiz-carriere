import { useState } from "react";
import { photoUrl } from "../api/client";
import { createChallenge } from "../api/challenge";
import { formatShareText, shareOrCopy } from "../utils/format";
import type { GameState } from "../types/api";

interface Props {
  game: GameState;
  nickname?: string;
  onPlayAgain: () => void;
  onPlayAgainSame?: (excludePlayerId: number) => void;
  replayLoading?: boolean;
  noMorePlayers?: boolean;
  onResetNoMore?: () => void;
}

export function ResultOverlay({ game, nickname, onPlayAgain, onPlayAgainSame, replayLoading, noMorePlayers, onResetNoMore }: Props) {
  const [shared, setShared] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [photoFailed, setPhotoFailed] = useState(false);

  const won = game.status === "won";
  const player = game.player!;

  async function handleShare() {
    setSharing(true);
    try {
      const creator = nickname || "Anonimo";
      const challenge = await createChallenge(creator, player.id);
      const text = `${formatShareText(game.attempt_count, game.hints_used, won, nickname)}\n\n${challenge.share_url}`;
      await shareOrCopy(text);
      setShared(true);
      setTimeout(() => setShared(false), 2500);
    } catch { /* silenzioso */ }
    finally { setSharing(false); }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-5 overflow-y-auto animate-in fade-in"
      style={{ background: "rgba(26, 46, 24, 0.72)", backdropFilter: "blur(6px)" }}
    >
      {/* min-h-screen sul centering div garantisce che il backdrop copra sempre tutto */}
      <div className="flex items-center justify-center min-h-screen w-full py-8">
        <div
          className="w-full max-w-sm bg-crema shadow-float-lg animate-in zoom-in-95"
          style={{ borderRadius: "2rem" }}
        >
          <div className="px-6 pt-7 pb-8 flex flex-col gap-5">

            {/* ── Esito ── */}
            <div className="text-center">
              <div
                className="mx-auto mb-3 w-16 h-16 flex items-center justify-center text-3xl"
                style={{
                  background: won
                    ? "linear-gradient(135deg, #f5c518 0%, #fad54a 100%)"
                    : "rgba(212,200,154,0.45)",
                  borderRadius: "60% 40% 55% 45% / 45% 55% 45% 55%",
                }}
              >
                {won ? "🏆" : "🏳️"}
              </div>

              <h2 className="font-display font-bold text-2xl text-verde leading-tight">
                {won ? "Indovinato!" : "Ti sei arreso"}
              </h2>
              <p className="text-sm text-grass mt-1">
                {won
                  ? `${game.attempt_count} ${game.attempt_count === 1 ? "tentativo" : "tentativi"} · ${game.hints_used} ${game.hints_used === 1 ? "indizio" : "indizi"}`
                  : `${game.attempt_count} ${game.attempt_count === 1 ? "tentativo" : "tentativi"} effettuati`}
              </p>
            </div>

            {/* ── Reveal giocatore ── */}
            <div
              className="flex items-center gap-4 p-4 border border-bordo/60 bg-white/80 shadow-soft"
              style={{ borderRadius: "1.5rem" }}
            >
              {!photoFailed ? (
                <img
                  src={photoUrl(player.id)}
                  alt={player.name}
                  className="w-20 h-24 rounded-2xl object-cover object-top border border-bordo/60 flex-shrink-0 shadow-soft"
                  onError={() => setPhotoFailed(true)}
                />
              ) : (
                <div
                  className="w-20 h-24 rounded-2xl bg-bordo/30 flex items-center justify-center
                             font-display font-bold text-3xl text-verde flex-shrink-0 border border-bordo/60"
                >
                  {player.name[0]?.toUpperCase()}
                </div>
              )}
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-widest text-grass mb-1">
                  Il campionissimo era
                </p>
                <p className="font-display font-bold text-xl text-loam leading-tight break-words">
                  {player.name}
                </p>
              </div>
            </div>

            {/* ── Statistiche ── */}
            <div className="grid grid-cols-2 gap-3">
              <StatCard label="Tentativi" value={String(game.attempt_count)} icon="🎯" />
              <StatCard label="Indizi usati" value={String(game.hints_used)} icon="💡" />
            </div>

            {/* ── Azioni ── */}
            <div className="flex flex-col gap-2.5">
              <button
                onClick={handleShare}
                disabled={sharing}
                className="w-full h-12 rounded-full font-display font-bold text-sm
                           bg-verde text-white shadow-float
                           hover:bg-verde-dark hover:shadow-float-lg hover:scale-[1.02]
                           active:scale-95 disabled:opacity-60
                           transition-all duration-200"
              >
                {shared ? "✓ Copiato!" : sharing ? "…" : "🔗 Sfida un amico"}
              </button>

              {/* Ricerca con stessi filtri, escluso il giocatore appena indovinato */}
              {onPlayAgainSame && player && (
                <button
                  onClick={() => onPlayAgainSame(player.id)}
                  disabled={replayLoading}
                  className="w-full h-12 rounded-full font-bold text-sm
                             bg-oro text-verde shadow-oro
                             hover:brightness-95 hover:scale-[1.02]
                             active:scale-95 disabled:opacity-60
                             transition-all duration-200"
                >
                  {replayLoading ? "Preparando…" : "🔄 Ricerca con stessi filtri"}
                </button>
              )}

              <button
                onClick={onPlayAgain}
                className="w-full h-11 rounded-full text-sm border-2 border-bordo text-grass
                           hover:border-verde hover:text-verde active:scale-95 transition-all duration-200"
              >
                Cambia filtri
              </button>
            </div>

          </div>
        </div>
      </div>

      {/* Modale: nessun altro giocatore con questi filtri */}
      {noMorePlayers && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center px-5"
          style={{ background: "rgba(26,46,24,0.70)", backdropFilter: "blur(6px)" }}
          onClick={onResetNoMore}
        >
          <div
            className="bg-crema w-full max-w-xs p-6 shadow-float-lg text-center animate-in zoom-in-95"
            style={{ borderRadius: "2rem" }}
            onClick={e => e.stopPropagation()}
          >
            <div
              className="mx-auto mb-4 w-16 h-16 flex items-center justify-center text-3xl"
              style={{ background: "rgba(212,200,154,0.45)", borderRadius: "55% 45% 60% 40% / 45% 55% 45% 55%" }}
            >
              🔍
            </div>
            <h3 className="font-display font-bold text-xl text-loam mb-2">
              Nessun altro giocatore
            </h3>
            <p className="text-sm text-grass leading-relaxed mb-6 max-w-[220px] mx-auto">
              Con i filtri attuali non ci sono altri giocatori disponibili. Torna alla home e allarga i criteri di ricerca.
            </p>
            <button
              onClick={onPlayAgain}
              className="w-full h-12 rounded-full bg-verde text-white text-sm font-bold
                         shadow-soft hover:bg-verde-dark active:scale-95 transition-all duration-200"
            >
              Cambia filtri
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div
      className="text-center p-3.5 border border-bordo/60 bg-white/80 shadow-soft"
      style={{ borderRadius: "1.25rem" }}
    >
      <p className="text-base mb-0.5">{icon}</p>
      <p className="text-2xl font-display font-bold text-verde">{value}</p>
      <p className="text-[11px] text-grass mt-0.5">{label}</p>
    </div>
  );
}
