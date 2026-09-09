import { useState } from "react";
import { flagUrl } from "../api/client";
import { RoleBadge } from "./RoleBadge";
import type { HintState, HintType } from "../types/api";

/**
 * Costruisce l'URL sicuro per la foto di una partita.
 * Il valore dell'indizio è "playerId:hmacSig" — viene passato come query param
 * all'endpoint /game/{token}/photo che verifica la firma lato server.
 * Così il player ID non è mai esposto direttamente al browser.
 */
function securePhotoUrl(gameToken: string, hintValue: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
  return `${base}/game/${gameToken}/photo?sig=${encodeURIComponent(hintValue)}`;
}

const HINT_CONFIG: { type: HintType; label: string }[] = [
  { type: "role",        label: "Ruolo"  },
  { type: "nationality", label: "Nazione" },
  { type: "photo",       label: "Volto"  },
];

interface Props {
  hints: Record<HintType, HintState>;
  gameToken: string;
  onUnlock: (type: HintType) => void;
  disabled?: boolean;
}

export function HintBar({ hints, gameToken, onUnlock, disabled = false }: Props) {
  const photoHint = hints.photo;
  const otherHints = HINT_CONFIG.filter((h) => h.type !== "photo");

  return (
    <div className="flex flex-col gap-2.5">
      <p className="text-[11px] font-bold uppercase tracking-widest text-grass">Indizi</p>

      {/* Foto — card grande quando sbloccata, altrimenti bottone inline */}
      {photoHint.unlocked && photoHint.value ? (
        <PhotoCard url={securePhotoUrl(gameToken, photoHint.value)} />
      ) : null}

      {/* Ruolo + Nazione + (se non ancora sbloccata, la foto come bottone) */}
      <div className="flex gap-2 flex-wrap">
        {otherHints.map(({ type, label }) => (
          <HintChip
            key={type}
            type={type}
            label={label}
            hint={hints[type]}
            onUnlock={() => onUnlock(type)}
            disabled={disabled}
          />
        ))}

        {!photoHint.unlocked && (
          <button
            onClick={() => onUnlock("photo")}
            disabled={disabled}
            className={[
              "flex items-center gap-1.5 px-4 py-1.5 rounded-2xl border text-sm font-semibold transition-all duration-200",
              disabled
                ? "border-bordo/40 text-grass/40 bg-stone/50 cursor-not-allowed"
                : "border-bordo text-grass bg-white/70 hover:border-verde hover:text-verde hover:shadow-soft hover:scale-[1.03] active:scale-95 cursor-pointer",
            ].join(" ")}
            title="Sblocca indizio: Volto"
          >
            <LockIcon />
            <span>Volto</span>
          </button>
        )}
      </div>
    </div>
  );
}

// ── Photo card grande ──────────────────────────────────────────────────────────

function PhotoCard({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);

  return (
    <div
      className="flex items-center gap-4 p-3 border border-bordo/60 bg-white shadow-soft"
      style={{ borderRadius: "1.25rem" }}
    >
      {failed ? (
        <div
          className="w-24 h-28 flex-shrink-0 bg-stone rounded-xl flex items-center justify-center
                     text-grass/40 text-xs font-bold border border-bordo/40"
        >
          ?
        </div>
      ) : (
        <img
          src={url}
          alt="Volto del giocatore"
          className="w-24 h-28 flex-shrink-0 object-cover object-top rounded-xl border border-bordo/40 shadow-sm"
          onError={() => setFailed(true)}
        />
      )}
      <div>
        <p className="text-[10px] font-bold uppercase tracking-widest text-grass mb-1">Indizio</p>
        <p className="text-sm font-bold text-loam leading-snug">Riconosci<br />questo volto?</p>
      </div>
    </div>
  );
}

// ── Singolo chip indizio (ruolo / nazione) ─────────────────────────────────────

function HintChip({
  type, label, hint, onUnlock, disabled,
}: {
  type: HintType; label: string;
  hint: HintState; onUnlock: () => void; disabled: boolean;
}) {
  /* Sbloccato */
  if (hint.unlocked && hint.value) {
    if (type === "role") {
      return (
        <div
          className="flex items-center gap-2 px-3 py-1.5 border border-bordo/60 bg-white shadow-soft"
          style={{ borderRadius: "0.875rem" }}
        >
          <RoleBadge position={hint.value} size="sm" />
          <span className="text-xs font-bold text-loam">{hint.value}</span>
        </div>
      );
    }

    if (type === "nationality") {
      return (
        <div
          className="flex items-center gap-2 px-3 py-1.5 border border-bordo/60 bg-white shadow-soft"
          style={{ borderRadius: "0.875rem" }}
        >
          <FlagImg tmId={hint.value} />
          <span className="text-[10px] font-bold uppercase tracking-widest text-grass">{label}</span>
        </div>
      );
    }
  }

  /* Bloccato / bottone */
  return (
    <button
      onClick={onUnlock}
      disabled={disabled}
      className={[
        "flex items-center gap-1.5 px-4 py-1.5 rounded-2xl border text-sm font-semibold transition-all duration-200",
        disabled
          ? "border-bordo/40 text-grass/40 bg-stone/50 cursor-not-allowed"
          : "border-bordo text-grass bg-white/70 hover:border-verde hover:text-verde hover:shadow-soft hover:scale-[1.03] active:scale-95 cursor-pointer",
      ].join(" ")}
      title={`Sblocca indizio: ${label}`}
    >
      <LockIcon />
      <span>{label}</span>
    </button>
  );
}

// ── Componenti ausiliari ───────────────────────────────────────────────────────

function FlagImg({ tmId }: { tmId: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <span className="text-xs">🌍</span>;
  return (
    <img
      src={flagUrl(tmId)}
      alt={tmId}
      className="w-6 h-4 object-cover rounded-sm flex-shrink-0"
      onError={() => setFailed(true)}
    />
  );
}

function LockIcon() {
  return (
    <svg
      className="w-3.5 h-3.5 text-grass/40 flex-shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}
