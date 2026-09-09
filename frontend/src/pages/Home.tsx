import { useRef, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { createGame, previewPlayer } from "../api/game";
import { createChallenge } from "../api/challenge";
import { searchPlayers, searchTeams } from "../api/search";
import { crestUrl, photoUrl } from "../api/client";
import { RoleBadge } from "../components/RoleBadge";
import type { GameFilters, PlayerPreview, Position, SearchResult, TeamResult } from "../types/api";

// ── Costanti ──────────────────────────────────────────────────────────────────

const POSITIONS: Position[] = ["Portiere", "Difensore", "Centrocampista", "Attaccante"];

const PRESENZE_OPTIONS = [
  { label: "Qualsiasi",     min: undefined, hint: "Nessun limite di presenze. Include anche giocatori che hanno collezionato poche partite." },
  { label: "50+ presenze",  min: 50,        hint: "Giocatori con almeno 50 presenze. Esclude le comparse." },
  { label: "200+ presenze", min: 200,       hint: "Solo titolari affermati con carriera lunga e importante." },
] as const;

const SEASONS: number[] = Array.from({ length: 76 }, (_, i) => 2025 - i); // 2025 → 1950

function formatSeason(y: number) { return `${y}/${String(y + 1).slice(-2)}`; }

// ── Helpers ───────────────────────────────────────────────────────────────────

function getNickname() { return localStorage.getItem("nickname") ?? ""; }
function saveNickname(n: string) { localStorage.setItem("nickname", n); }

interface Sel {
  position: Position | undefined;
  seasonFrom: number | undefined;
  seasonTo: number | undefined;
  diffIdx: number;
  teamId: number | undefined;
  teamName: string;
  playerId: number | undefined;
  playerName: string;
}

const DEFAULT_SEL: Sel = {
  position: undefined,
  seasonFrom: undefined, seasonTo: undefined,
  diffIdx: 0,
  teamId: undefined, teamName: "",
  playerId: undefined, playerName: "",
};

function toFilters(s: Sel): GameFilters {
  return {
    season_from: s.seasonFrom,
    season_to:   s.seasonTo,
    position:    s.position,
    min_appearances: PRESENZE_OPTIONS[s.diffIdx].min,
    team_id:     s.teamId,
  };
}

function countActive(s: Sel) {
  return [s.position, s.seasonFrom ?? s.seasonTo, s.teamId, s.diffIdx !== 0 ? 1 : 0, s.playerId]
    .filter(Boolean).length;
}

function seasonPillLabel(from?: number, to?: number) {
  if (!from && !to)                    return "Stagione";
  if (from && to && from === to)       return formatSeason(from);
  if (from && to)                      return `${from}/${String(from+1).slice(-2)} – ${to}/${String(to+1).slice(-2)}`;
  if (from)                            return `Dal ${formatSeason(from)}`;
  return `Fino ${formatSeason(to!)}`;
}

type Mode = "solo" | "sfida";
type ActiveFilter = "role" | "season" | "team" | "presenze" | null;

// ── Componente principale ─────────────────────────────────────────────────────

export function Home() {
  const navigate  = useNavigate();
  const [nickname, setNicknameState] = useState(getNickname);
  const [mode, setMode]          = useState<Mode>("solo");
  const [sel, setSel]            = useState<Sel>(DEFAULT_SEL);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>(null);

  const [loadingSolo,    setLoadingSolo]    = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingLink,    setLoadingLink]    = useState(false);
  const [preview,        setPreview]        = useState<PlayerPreview | null>(null);
  const [challengeUrl,   setChallengeUrl]   = useState<string | null>(null);
  const [copied,         setCopied]         = useState(false);
  const [errorModal,     setErrorModal]     = useState<{ title: string; body: string } | null>(null);

  const nick        = nickname.trim();
  const activeCount = countActive(sel);
  const hasPlayer   = sel.playerId !== undefined;

  function toggleFilter(f: ActiveFilter) {
    setActiveFilter(o => o === f ? null : f);
  }

  async function handlePlay() {
    setLoadingSolo(true);
    try {
      if (nick) saveNickname(nick);
      const game = await createGame(toFilters(sel), nick || undefined, sel.playerId);
      sessionStorage.setItem("lastFilters", JSON.stringify(toFilters(sel)));
      navigate(`/gioca/${game.token}`);
    } catch {
      setErrorModal({
        title: "Nessun giocatore trovato",
        body: "La combinazione di filtri selezionata non corrisponde a nessun giocatore nel database. Prova ad allargare i criteri di ricerca.",
      });
    } finally { setLoadingSolo(false); }
  }

  /** Passo 1 — mostra la preview del giocatore prima di creare il link */
  async function handleRequestPreview() {
    if (!nick) {
      setErrorModal({
        title: "Nome mancante",
        body: "Inserisci il tuo nome prima di creare una sfida, così i tuoi amici sapranno da chi proviene il link!",
      });
      return;
    }
    setLoadingPreview(true);
    setPreview(null); setChallengeUrl(null); setCopied(false);
    try {
      const p = await previewPlayer(toFilters(sel), sel.playerId);
      setPreview(p);
    } catch {
      setErrorModal({
        title: "Nessun giocatore trovato",
        body: "La combinazione di filtri selezionata non corrisponde a nessun giocatore. Prova ad allargare i criteri.",
      });
    } finally { setLoadingPreview(false); }
  }

  /** Passo 2 — conferma e crea il link di sfida con il giocatore già scelto */
  async function handleConfirmChallenge() {
    if (!preview || !nick) return;
    setLoadingLink(true);
    try {
      saveNickname(nick);
      const result = await createChallenge(nick, preview.id, toFilters(sel));
      setChallengeUrl(result.share_url);
    } catch {
      setErrorModal({
        title: "Errore nella sfida",
        body: "Non è stato possibile creare la sfida. Controlla la connessione e riprova.",
      });
    } finally { setLoadingLink(false); }
  }

  /** Ri-pesca un altro giocatore casuale con gli stessi filtri */
  async function handleReroll() {
    if (sel.playerId !== undefined) return; // con giocatore fisso non ha senso
    setLoadingPreview(true);
    setPreview(null);
    try {
      const p = await previewPlayer(toFilters(sel));
      setPreview(p);
    } catch {
      setErrorModal({
        title: "Nessun giocatore trovato",
        body: "Nessun altro giocatore corrisponde ai filtri impostati.",
      });
    } finally { setLoadingPreview(false); }
  }

  async function handleCopy() {
    if (!challengeUrl) return;
    try { await navigator.clipboard.writeText(challengeUrl); }
    catch { prompt("Copia il link:", challengeUrl); return; }
    setCopied(true);
    setTimeout(() => setCopied(false), 2200);
  }

  function handleWhatsApp() {
    if (!challengeUrl) return;
    window.open(`https://wa.me/?text=${encodeURIComponent(
      `${nick || "Qualcuno"} ti ha sfidato su Campionissimo! 🏆\nIndovina il calciatore dalla sua carriera:\n${challengeUrl}`
    )}`, "_blank");
  }

  // ── Dati pills ──────────────────────────────────────────────────────────────
  const isRoleActive    = !!sel.position;
  const isSeasonActive  = !!(sel.seasonFrom || sel.seasonTo);
  const isTeamActive    = !!sel.teamId;
  const isPresenzeActive = sel.diffIdx !== 0;

  return (
    <div className="min-h-screen bg-crema font-sans overflow-x-hidden">

      {/* ── Hero compatto ── */}
      <header className="relative overflow-hidden bg-verde text-white pt-8 pb-8 px-6 text-center">
        <div className="absolute -top-6 -right-6 w-40 h-40 bg-white/10 blur-3xl pointer-events-none blob-drift"
             style={{ borderRadius: "60% 40% 30% 70% / 60% 30% 70% 40%" }} />
        <div className="absolute bottom-0 -left-8 w-32 h-32 bg-oro/20 blur-2xl pointer-events-none blob-drift-slow"
             style={{ borderRadius: "30% 70% 70% 30% / 30% 30% 70% 70%" }} />
        <div className="relative z-10">
          <p className="text-white/50 text-[11px] font-semibold tracking-[0.25em] uppercase mb-2">
            Il gioco del calcio
          </p>
          <h1 className="font-display font-bold text-4xl sm:text-5xl leading-none tracking-tight"
              style={{ textShadow: "0 2px 16px rgba(0,0,0,0.15)" }}>
            Campionissimo
          </h1>
          <p className="mt-2 text-white/65 text-sm max-w-xs mx-auto leading-snug">
            Indovina il calciatore dalla sua carriera
          </p>
        </div>
      </header>

      <main className="max-w-sm mx-auto px-4 py-6 flex flex-col gap-4">

        {/* Nome */}
        <div className="flex flex-col gap-1.5">
          <label className="text-[11px] font-bold uppercase tracking-widest text-grass">
            Il tuo nome{mode === "sfida" && <span className="text-[#ee1d41]"> *</span>}
          </label>
          <input
            type="text" value={nickname}
            onChange={e => setNicknameState(e.target.value)}
            placeholder="Es. Marco" maxLength={32}
            className="w-full h-12 px-5 rounded-full border border-bordo bg-white/70
                       text-sm text-loam placeholder:text-grass/50
                       focus:outline-none focus:border-verde focus:ring-2 focus:ring-verde/20
                       transition-all shadow-soft"
          />
        </div>

        {/* Modalità */}
        <div className="grid grid-cols-2 gap-3">
          {([
            { m: "solo" as Mode, icon: "🎮", title: "Gioca Solo", desc: "Partita casuale",
              r: "70% 30% 60% 40% / 40% 60% 40% 60%",
              act: "bg-verde text-white shadow-float",
              inact: "bg-white/80 text-loam border border-bordo hover:border-verde/60 hover:shadow-soft" },
            { m: "sfida" as Mode, icon: "⚡", title: "Sfida", desc: "Crea un link",
              r: "40% 60% 30% 70% / 60% 40% 60% 40%",
              act: "bg-oro text-verde shadow-oro",
              inact: "bg-white/80 text-loam border border-bordo hover:border-oro/60 hover:shadow-oro" },
          ]).map(({ m, icon, title, desc, r, act, inact }) => (
            <button key={m} onClick={() => { setMode(m); setChallengeUrl(null); }}
              style={{ borderRadius: mode === m ? "1.5rem" : r }}
              className={["flex flex-col items-center gap-1.5 py-4 px-3 text-center transition-all duration-300",
                mode === m ? act : inact].join(" ")}>
              <span className="text-xl">{icon}</span>
              <span className="font-display font-bold text-sm">{title}</span>
              <span className={`text-[11px] leading-tight ${mode === m ? "opacity-80" : "text-grass"}`}>{desc}</span>
            </button>
          ))}
        </div>

        {/* ── Personalizza partita ── */}
        <div className="bg-white/80 border border-bordo/60 shadow-soft rounded-3xl overflow-hidden">

          {/* Header toggle */}
          <button
            onClick={() => { setFiltersOpen(o => !o); setActiveFilter(null); }}
            className="w-full flex items-center justify-between px-5 py-3.5 text-left
                       hover:bg-stone/30 transition-colors duration-150"
          >
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-widest text-grass">
                Personalizza partita
              </span>
              {activeCount > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-verde text-white text-[10px] font-bold leading-none">
                  {activeCount}
                </span>
              )}
            </div>
            <ChevronIcon open={filtersOpen} />
          </button>

          {/* Corpo espanso */}
          {filtersOpen && (
            <div className="border-t border-bordo/40 px-4 pb-4 flex flex-col gap-3">

              {/* Giocatore specifico — solo in modalità sfida */}
              {mode === "sfida" && (
                <div className="pt-3 flex flex-col gap-2">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-grass/80">
                    Giocatore da indovinare
                  </p>

                  {hasPlayer ? (
                    /* Preview del giocatore selezionato */
                    <PlayerPreviewCard
                      playerId={sel.playerId!}
                      playerName={sel.playerName}
                      onClear={() => setSel(s => ({ ...s, playerId: undefined, playerName: "" }))}
                    />
                  ) : (
                    <>
                      <PlayerSearchInput
                        selectedId={sel.playerId}
                        selectedName={sel.playerName}
                        onSelect={(id, name) => { setSel(s => ({ ...s, playerId: id, playerName: name })); setActiveFilter(null); }}
                        onClear={() => setSel(s => ({ ...s, playerId: undefined, playerName: "" }))}
                      />
                      <p className="text-[10px] text-grass/60 leading-snug">
                        Scegli un giocatore preciso oppure lascia scegliere al caso con i filtri sotto.
                      </p>
                    </>
                  )}
                </div>
              )}

              {/* Pills filtri — 2×2 grid, visibili solo se nessun giocatore specifico */}
              {!hasPlayer && (
                <>
                  <div className="grid grid-cols-2 gap-2">

                    {/* Ruolo */}
                    <FilterPill
                      active={isRoleActive}
                      open={activeFilter === "role"}
                      onClick={() => toggleFilter("role")}
                    >
                      {isRoleActive
                        ? <span className="flex items-center gap-1.5 min-w-0">
                            <RoleBadge position={sel.position} size="xs" />
                            <span className="truncate">{sel.position}</span>
                          </span>
                        : "Ruolo"}
                    </FilterPill>

                    {/* Stagione */}
                    <FilterPill
                      active={isSeasonActive}
                      open={activeFilter === "season"}
                      onClick={() => toggleFilter("season")}
                    >
                      <span className="truncate">{seasonPillLabel(sel.seasonFrom, sel.seasonTo)}</span>
                    </FilterPill>

                    {/* Squadra */}
                    <FilterPill
                      active={isTeamActive}
                      open={activeFilter === "team"}
                      onClick={() => toggleFilter("team")}
                    >
                      <span className="truncate">{isTeamActive ? sel.teamName : "Squadra"}</span>
                    </FilterPill>

                    {/* Presenze */}
                    <FilterPill
                      active={isPresenzeActive}
                      open={activeFilter === "presenze"}
                      onClick={() => toggleFilter("presenze")}
                    >
                      <span className="truncate">{isPresenzeActive ? PRESENZE_OPTIONS[sel.diffIdx].label : "Presenze"}</span>
                    </FilterPill>

                  </div>

                  {/* Pannello inline del filtro attivo */}
                  {activeFilter && (
                    <div className="bg-stone/50 border border-bordo/50 rounded-2xl p-3 flex flex-col gap-3">

                      {/* ── Ruolo ── */}
                      {activeFilter === "role" && (
                        <>
                          <FilterPanelInfo
                            text="Filtra per la posizione del giocatore in campo."
                          />
                          <div className="grid grid-cols-2 gap-2">
                            <RolePillBtn
                              active={sel.position === undefined}
                              onClick={() => { setSel(s => ({ ...s, position: undefined })); setActiveFilter(null); }}
                              bg={undefined}
                            >
                              Tutti i ruoli
                            </RolePillBtn>
                            {POSITIONS.map(p => (
                              <RolePillBtn
                                key={p}
                                active={sel.position === p}
                                onClick={() => { setSel(s => ({ ...s, position: s.position === p ? undefined : p })); setActiveFilter(null); }}
                                bg={ROLE_BG[p]}
                              >
                                <RoleBadge position={p} size="xs" />
                                {p}
                              </RolePillBtn>
                            ))}
                          </div>
                        </>
                      )}

                      {/* ── Stagione ── */}
                      {activeFilter === "season" && (
                        <>
                          <FilterPanelInfo
                            text={sel.teamId
                              ? "Stagione in cui il giocatore ha militato nella squadra selezionata."
                              : "Periodo di attività del giocatore. Seleziona solo 'Dal' per una stagione singola."}
                          />
                          <div className="flex flex-col gap-2.5">
                            <div className="flex items-center gap-3">
                              <span className="text-[11px] font-bold text-grass w-8 shrink-0">Dal</span>
                              <SeasonSelect
                                value={sel.seasonFrom}
                                onChange={v => setSel(s => ({ ...s, seasonFrom: v }))}
                                filterMax={sel.seasonTo}
                              />
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-[11px] font-bold text-grass w-8 shrink-0">Al</span>
                              <SeasonSelect
                                value={sel.seasonTo}
                                onChange={v => setSel(s => ({ ...s, seasonTo: v }))}
                                filterMin={sel.seasonFrom}
                              />
                            </div>
                          </div>
                          <button
                            onClick={() => setActiveFilter(null)}
                            className="w-full h-9 rounded-xl bg-verde text-white text-xs font-bold
                                       hover:bg-verde-dark transition-all"
                          >
                            Conferma stagione
                          </button>
                          {isSeasonActive && (
                            <button
                              onClick={() => { setSel(s => ({ ...s, seasonFrom: undefined, seasonTo: undefined })); setActiveFilter(null); }}
                              className="text-[11px] text-grass/60 hover:text-grass text-center"
                            >
                              Azzera stagione
                            </button>
                          )}
                        </>
                      )}

                      {/* ── Squadra ── */}
                      {activeFilter === "team" && (
                        <>
                          <FilterPanelInfo
                            text="Cerca una squadra. Presenze e stagione si riferiscono a quel club se attivo."
                          />
                          <TeamSearchInput
                            selectedId={sel.teamId}
                            selectedName={sel.teamName}
                            onSelect={(id, name) => { setSel(s => ({ ...s, teamId: id, teamName: name })); setActiveFilter(null); }}
                            onClear={() => setSel(s => ({ ...s, teamId: undefined, teamName: "" }))}
                          />
                        </>
                      )}

                      {/* ── Presenze ── */}
                      {activeFilter === "presenze" && (
                        <>
                          <FilterPanelInfo
                            text={sel.teamId
                              ? "Presenze minime nella squadra selezionata (nel range di stagioni se impostato)."
                              : "Presenze minime sull'intera carriera del giocatore."}
                          />
                          <div className="flex flex-col gap-1.5">
                            {PRESENZE_OPTIONS.map((opt, i) => (
                              <button
                                key={opt.label}
                                onClick={() => { setSel(s => ({ ...s, diffIdx: i })); setActiveFilter(null); }}
                                className={[
                                  "w-full text-left px-4 py-3 rounded-xl text-sm font-medium transition-all duration-150",
                                  sel.diffIdx === i
                                    ? "bg-verde text-white font-bold shadow-soft"
                                    : "bg-white border border-bordo/60 text-loam hover:border-verde/50 hover:bg-stone/30",
                                ].join(" ")}
                              >
                                <span className="block font-bold">{opt.label}</span>
                                <span className={`text-[11px] ${sel.diffIdx === i ? "text-white/70" : "text-grass/70"}`}>
                                  {opt.hint}
                                </span>
                              </button>
                            ))}
                          </div>
                        </>
                      )}

                    </div>
                  )}

                  {/* Azzera filtri */}
                  {activeCount > 0 && (
                    <button
                      onClick={() => { setSel(DEFAULT_SEL); setActiveFilter(null); }}
                      className="w-full h-9 rounded-full border-2 border-bordo text-loam text-xs font-bold
                                 hover:border-[#ee1d41]/60 hover:text-[#ee1d41] hover:bg-[#ee1d41]/5
                                 transition-all duration-200"
                    >
                      Azzera tutti i filtri
                    </button>
                  )}
                </>
              )}

            </div>
          )}
        </div>

        {/* CTA */}
        {mode === "solo" ? (
          <button
            onClick={handlePlay} disabled={loadingSolo}
            className="w-full h-14 rounded-full font-display font-bold text-base tracking-wide
                       bg-verde text-white shadow-float
                       hover:bg-verde-dark hover:shadow-float-lg hover:scale-[1.02]
                       active:scale-[0.97] disabled:opacity-60 disabled:cursor-not-allowed
                       transition-all duration-300"
          >
            {loadingSolo ? "Preparando…" : "Gioca ▶"}
          </button>
        ) : (
          <div className="flex flex-col gap-3">

            {/* Passo 1 — bottone "Anteprima" (non ancora scelto) */}
            {!preview && !challengeUrl && (
              <button
                onClick={handleRequestPreview} disabled={loadingPreview}
                className="w-full h-14 rounded-full font-display font-bold text-base tracking-wide
                           bg-oro text-verde shadow-oro
                           hover:brightness-95 hover:shadow-oro-lg hover:scale-[1.02]
                           active:scale-[0.97] disabled:opacity-60 disabled:cursor-not-allowed
                           transition-all duration-300"
              >
                {loadingPreview ? "Cercando giocatore…" : "Anteprima sfida →"}
              </button>
            )}

            {/* Passo 2 — preview del giocatore scelto */}
            {preview && !challengeUrl && (
              <ChallengePreviewCard
                preview={preview}
                canReroll={sel.playerId === undefined}
                loadingLink={loadingLink}
                loadingReroll={loadingPreview}
                onConfirm={handleConfirmChallenge}
                onReroll={handleReroll}
                onReset={() => setPreview(null)}
              />
            )}

            {/* Passo 3 — link pronto */}
            {challengeUrl && (
              <div className="flex flex-col gap-3 p-5 border-2 border-oro/60 bg-white shadow-oro rounded-3xl">
                <p className="text-sm font-bold text-verde text-center">🎉 Sfida pronta!</p>
                <div className="flex gap-2">
                  <input readOnly value={challengeUrl}
                    className="flex-1 px-4 py-2.5 rounded-full border border-bordo bg-stone text-xs text-grass outline-none"
                    onClick={e => (e.target as HTMLInputElement).select()} />
                  <button onClick={handleCopy}
                    className="px-4 py-2 rounded-full border-2 border-verde text-verde text-xs font-bold
                               hover:bg-verde hover:text-white transition-all duration-200 whitespace-nowrap">
                    {copied ? "✓" : "Copia"}
                  </button>
                </div>
                <button onClick={handleWhatsApp}
                  className="w-full py-3 rounded-full bg-[#25D366] text-white text-sm font-bold
                             hover:brightness-95 transition-all">
                  📲 Invia su WhatsApp
                </button>
                <button onClick={() => { setChallengeUrl(null); setPreview(null); setCopied(false); }}
                  className="text-xs text-grass hover:text-loam text-center transition-colors">
                  Crea una nuova sfida
                </button>
              </div>
            )}

          </div>
        )}

      </main>

      <footer className="text-center text-xs text-grass/50 pb-6 mt-2">
        Serie A · 8.000+ calciatori
      </footer>

      {/* ── Modale errore ── */}
      {errorModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-5"
          style={{ background: "rgba(26, 46, 24, 0.65)", backdropFilter: "blur(6px)" }}
          onClick={() => setErrorModal(null)}
        >
          <div
            className="bg-crema w-full max-w-xs p-6 shadow-float-lg text-center animate-in zoom-in-95"
            style={{ borderRadius: "2rem" }}
            onClick={e => e.stopPropagation()}
          >
            {/* Decorazione */}
            <div
              className="mx-auto mb-4 w-16 h-16 flex items-center justify-center"
              style={{
                background: "rgba(238,29,65,0.12)",
                borderRadius: "55% 45% 60% 40% / 45% 55% 45% 55%",
              }}
            >
              <span className="text-3xl">🔍</span>
            </div>

            <h3 className="font-display font-bold text-xl text-loam mb-2">
              {errorModal.title}
            </h3>
            <p className="text-sm text-grass leading-relaxed mb-6 max-w-[220px] mx-auto">
              {errorModal.body}
            </p>

            <button
              onClick={() => setErrorModal(null)}
              className="w-full h-12 rounded-full bg-verde text-white text-sm font-bold
                         shadow-soft hover:bg-verde-dark hover:shadow-float
                         active:scale-95 transition-all duration-200"
            >
              Capito, riprovo
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

// ── Palette ruoli ─────────────────────────────────────────────────────────────

const ROLE_BG: Record<string, string> = {
  "Portiere":       "#f9ab0f",
  "Difensore":      "#66c723",
  "Centrocampista": "#136dfa",
  "Attaccante":     "#ee1d41",
};

// ── Componenti UI ─────────────────────────────────────────────────────────────

/** Pill usata nel 2×2 grid dei filtri */
function FilterPill({
  active, open, onClick, children,
}: {
  active: boolean; open: boolean;
  onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={[
        "w-full flex items-center justify-between gap-1.5 px-3 py-2.5 rounded-2xl border text-xs font-semibold transition-all duration-150",
        open
          ? "border-verde bg-verde/10 text-verde"
          : active
            ? "bg-verde text-white border-verde shadow-soft"
            : "border-bordo text-grass bg-white/70 hover:border-verde/50",
      ].join(" ")}
    >
      <span className="flex items-center gap-1.5 min-w-0 truncate">{children}</span>
      <svg className={`w-3 h-3 flex-shrink-0 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
           viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}
           strokeLinecap="round" strokeLinejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
  );
}

/** Bottone opzione nel pannello Ruolo */
function RolePillBtn({
  active, onClick, bg, children,
}: {
  active: boolean; onClick: () => void; bg?: string; children: React.ReactNode;
}) {
  const style: React.CSSProperties = active && bg
    ? { backgroundColor: `${bg}18`, borderColor: bg, color: bg }
    : {};

  return (
    <button
      onClick={onClick}
      style={style}
      className={[
        "w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border text-xs font-semibold transition-all duration-150",
        active
          ? "shadow-sm font-bold"
          : "border-bordo/60 text-grass bg-white hover:border-verde/40",
        active && !bg ? "bg-verde text-white border-verde" : "",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

/** Info box in cima a ogni pannello filtro */
function FilterPanelInfo({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 p-2.5 bg-white/70 rounded-xl border border-bordo/40">
      <span className="text-verde text-sm flex-shrink-0 mt-0.5">ℹ</span>
      <p className="text-[11px] text-grass/80 leading-snug">{text}</p>
    </div>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg className={`w-4 h-4 text-grass/60 transition-transform duration-300 flex-shrink-0 ${open ? "rotate-180" : ""}`}
         viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}
         strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

// ── Season Select ─────────────────────────────────────────────────────────────

function SeasonSelect({
  value, onChange, filterMin, filterMax,
}: {
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  filterMin?: number;
  filterMax?: number;
}) {
  const options = SEASONS.filter(s => {
    if (filterMin !== undefined && s < filterMin) return false;
    if (filterMax !== undefined && s > filterMax) return false;
    return true;
  });

  return (
    <select
      value={value ?? ""}
      onChange={e => onChange(e.target.value ? Number(e.target.value) : undefined)}
      className="flex-1 h-10 px-3 rounded-xl border border-bordo bg-white text-sm text-loam
                 focus:outline-none focus:border-verde focus:ring-2 focus:ring-verde/20 transition-all"
    >
      <option value="">Qualsiasi</option>
      {options.map(s => (
        <option key={s} value={s}>{formatSeason(s)}</option>
      ))}
    </select>
  );
}

// ── Challenge Preview Card ────────────────────────────────────────────────────

function ChallengePreviewCard({
  preview, canReroll, loadingLink, loadingReroll,
  onConfirm, onReroll, onReset,
}: {
  preview: PlayerPreview;
  canReroll: boolean;
  loadingLink: boolean;
  loadingReroll: boolean;
  onConfirm: () => void;
  onReroll: () => void;
  onReset: () => void;
}) {
  const [photoFailed, setPhotoFailed] = useState(false);

  return (
    <div
      className="flex flex-col gap-4 p-4 bg-white border-2 border-oro/60 shadow-oro"
      style={{ borderRadius: "1.5rem" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold uppercase tracking-widest text-grass">
          Giocatore scelto
        </p>
        <button
          onClick={onReset}
          className="text-[11px] text-grass/50 hover:text-grass transition-colors"
        >
          ← Cambia filtri
        </button>
      </div>

      {/* Identità giocatore */}
      <div className="flex items-center gap-3">
        {!photoFailed ? (
          <img
            src={photoUrl(preview.id)}
            alt={preview.name}
            className="w-16 h-20 rounded-2xl object-cover object-top border border-bordo/50 flex-shrink-0"
            onError={() => setPhotoFailed(true)}
          />
        ) : (
          <div className="w-16 h-20 rounded-2xl bg-bordo/25 flex items-center justify-center
                          font-display font-bold text-2xl text-verde flex-shrink-0 border border-bordo/40">
            {preview.name[0]?.toUpperCase()}
          </div>
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {preview.position_general && (
              <RoleBadge position={preview.position_general} size="xs" />
            )}
            <span className="text-[11px] text-grass">{preview.position_general}</span>
          </div>
          <p className="font-display font-bold text-lg text-loam leading-tight">
            {preview.name}
          </p>
        </div>
      </div>

      {/* Carriera preview */}
      {preview.career.length > 0 && (
        <div className="overflow-hidden" style={{ borderRadius: "0.875rem" }}>
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-verde text-white">
                <th className="text-left px-3 py-1.5 font-semibold">Stagione</th>
                <th className="text-left px-3 py-1.5 font-semibold">Club</th>
                <th className="text-right px-3 py-1.5 font-semibold">Pres.</th>
                <th className="text-right px-3 py-1.5 font-semibold">Gol</th>
              </tr>
            </thead>
            <tbody>
              {preview.career.map((c, i) => {
                const label = c.season_start === c.season_end
                  ? `${c.season_start}/${String(c.season_start + 1).slice(-2)}`
                  : `${c.season_start}–${c.season_end + 1}`;
                return (
                  <tr key={i} className={i % 2 === 0 ? "bg-stone/40" : "bg-white/60"}>
                    <td className="px-3 py-1.5 text-grass/80">{label}</td>
                    <td className="px-3 py-1.5 font-medium text-loam">{c.club_name}</td>
                    <td className="px-3 py-1.5 text-right text-grass">{c.appearances}</td>
                    <td className="px-3 py-1.5 text-right text-grass">{c.goals}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Azioni */}
      <div className="flex gap-2">
        {canReroll && (
          <button
            onClick={onReroll} disabled={loadingReroll || loadingLink}
            className="flex-1 h-11 rounded-full border-2 border-bordo text-grass text-xs font-bold
                       hover:border-verde hover:text-verde active:scale-95
                       disabled:opacity-50 transition-all duration-200"
          >
            {loadingReroll ? "…" : "🔄 Altro"}
          </button>
        )}
        <button
          onClick={onConfirm} disabled={loadingLink || loadingReroll}
          className="flex-[2] h-11 rounded-full bg-oro text-verde text-sm font-display font-bold
                     shadow-oro hover:brightness-95 active:scale-95
                     disabled:opacity-50 transition-all duration-200"
        >
          {loadingLink ? "Creando…" : "✓ Crea il link ⚡"}
        </button>
      </div>
    </div>
  );
}

// ── Player Preview Card (sfida) ───────────────────────────────────────────────

function PlayerPreviewCard({
  playerId, playerName, onClear,
}: {
  playerId: number; playerName: string; onClear: () => void;
}) {
  const [photoFailed, setPhotoFailed] = useState(false);

  return (
    <div
      className="flex items-center gap-3 p-3 bg-white border border-bordo/60 shadow-soft"
      style={{ borderRadius: "1.25rem" }}
    >
      {/* Foto */}
      {!photoFailed ? (
        <img
          src={photoUrl(playerId)}
          alt={playerName}
          className="w-14 h-16 rounded-xl object-cover object-top border border-bordo/40 flex-shrink-0"
          onError={() => setPhotoFailed(true)}
        />
      ) : (
        <div
          className="w-14 h-16 rounded-xl bg-bordo/25 flex items-center justify-center
                     font-display font-bold text-2xl text-verde flex-shrink-0 border border-bordo/40"
        >
          {playerName[0]?.toUpperCase()}
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-widest text-grass mb-0.5">
          Giocatore scelto
        </p>
        <p className="font-display font-bold text-base text-loam leading-tight truncate">
          {playerName}
        </p>
      </div>

      {/* Cambio */}
      <button
        onClick={onClear}
        className="flex-shrink-0 flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl
                   border border-bordo/50 text-grass text-[10px] font-bold
                   hover:border-verde/60 hover:text-verde hover:bg-verde/5
                   transition-all duration-150"
      >
        <span className="text-sm">🔄</span>
        <span>Cambia</span>
      </button>
    </div>
  );
}

// ── Player Search ─────────────────────────────────────────────────────────────

function PlayerSearchInput({
  selectedId, selectedName, onSelect, onClear,
}: {
  selectedId: number | undefined; selectedName: string;
  onSelect: (id: number, name: string) => void; onClear: () => void;
}) {
  const [query, setQuery] = useState(selectedName);
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setQuery(selectedName); }, [selectedName]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 2 || selectedId !== undefined) { setSuggestions([]); return; }
    timer.current = setTimeout(() => {
      searchPlayers(query, 6).then(r => { setSuggestions(r); setOpen(true); }).catch(() => {});
    }, 280);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [query, selectedId]);

  useEffect(() => {
    function onOut(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOut);
    return () => document.removeEventListener("mousedown", onOut);
  }, []);

  if (selectedId !== undefined) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-full border border-verde/40 bg-verde/8"
           style={{ background: "rgba(45,90,39,0.07)" }}>
        <span className="flex-1 text-sm font-semibold text-verde truncate">{selectedName}</span>
        <button onClick={() => { onClear(); setQuery(""); setSuggestions([]); }}
          className="text-xs text-grass/60 hover:text-grass px-2 py-0.5 rounded-full
                     border border-bordo/40 hover:border-bordo transition-colors flex-shrink-0 leading-tight">
          ✕ Rimuovi
        </button>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <input type="text" value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Es. Totti, Del Piero, CR7…"
        className="w-full h-10 px-4 rounded-full border border-bordo bg-white/80 text-sm text-loam
                   placeholder:text-grass/40 focus:outline-none focus:border-verde
                   focus:ring-2 focus:ring-verde/20 transition-all"
        autoComplete="off" spellCheck={false}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
      />
      {open && suggestions.length > 0 && (
        <ul className="absolute top-full mt-1.5 left-0 right-0 z-40 bg-white border border-bordo/60
                       shadow-float max-h-48 overflow-y-auto rounded-2xl">
          {suggestions.map(s => (
            <li key={s.id}>
              <button
                className="w-full text-left px-4 py-2.5 flex items-center gap-3 text-sm
                           hover:bg-oro/15 transition-colors first:rounded-t-2xl last:rounded-b-2xl"
                onMouseDown={e => { e.preventDefault(); onSelect(s.id, s.name); setOpen(false); setSuggestions([]); }}
              >
                <span className="font-semibold text-loam truncate flex-1">{s.name}</span>
                <span className="text-xs text-grass flex-shrink-0 flex items-center gap-1">
                  {s.position_general && <RoleBadge position={s.position_general} size="xs" />}
                  <span className="hidden sm:inline">{s.country_name}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Team Search ───────────────────────────────────────────────────────────────

function TeamSearchInput({
  selectedId, selectedName, onSelect, onClear,
}: {
  selectedId: number | undefined; selectedName: string;
  onSelect: (id: number, name: string) => void; onClear: () => void;
}) {
  const [query, setQuery]           = useState("");
  const [suggestions, setSuggestions] = useState<TeamResult[]>([]);
  const [loading, setLoading]       = useState(false);
  const timer  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const doSearch = useCallback((q: string) => {
    if (timer.current) clearTimeout(timer.current);
    if (q.trim().length < 1) { setSuggestions([]); return; }
    setLoading(true);
    timer.current = setTimeout(() => {
      searchTeams(q, 10)
        .then(r => { setSuggestions(r); setLoading(false); })
        .catch(() => { setSuggestions([]); setLoading(false); });
    }, 220);
  }, []);

  if (selectedId !== undefined) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-2xl bg-white border border-bordo/60">
        <TeamCrest clubId={selectedId} name={selectedName} size={22} />
        <span className="flex-1 text-sm font-semibold text-loam truncate">{selectedName}</span>
        <button onClick={onClear}
          className="text-xs text-grass/60 hover:text-[#ee1d41] px-2 py-0.5 rounded-full
                     border border-bordo/40 hover:border-[#ee1d41]/40 transition-colors flex-shrink-0">
          ✕
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={inputRef}
        type="text" value={query}
        onChange={e => { setQuery(e.target.value); doSearch(e.target.value); }}
        placeholder="Es. Juventus, Milan, Inter…"
        className="w-full h-10 px-4 rounded-xl border border-bordo bg-white text-sm text-loam
                   placeholder:text-grass/40 focus:outline-none focus:border-verde
                   focus:ring-2 focus:ring-verde/20 transition-all"
        autoComplete="off" spellCheck={false}
      />
      {loading && <p className="text-[11px] text-grass/60 px-1">Cercando…</p>}
      {suggestions.length > 0 && (
        <ul className="max-h-44 overflow-y-auto flex flex-col gap-0.5 rounded-xl border border-bordo/40 bg-white/80 p-1">
          {suggestions.map(t => (
            <li key={t.id}>
              <button
                className="w-full text-left px-3 py-2 rounded-lg flex items-center gap-2.5
                           hover:bg-oro/20 transition-colors"
                onMouseDown={e => { e.preventDefault(); onSelect(t.id, t.name); }}
              >
                <TeamCrest clubId={t.id} name={t.name} size={22} />
                <span className="text-sm font-medium text-loam truncate">{t.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!loading && query.length >= 1 && suggestions.length === 0 && (
        <p className="text-[11px] text-grass/60 px-1">Nessuna squadra trovata per "{query}"</p>
      )}
    </div>
  );
}

function TeamCrest({ clubId, name, size }: { clubId: number; name: string; size: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="flex-shrink-0 rounded-full bg-bordo/40 flex items-center justify-center
                       font-bold text-verde border border-bordo/60"
            style={{ width: size, height: size, fontSize: size * 0.4 }}>
        {name[0]?.toUpperCase() ?? "?"}
      </span>
    );
  }
  return (
    <img src={crestUrl(clubId)} alt={name}
         style={{ width: size, height: size }}
         className="flex-shrink-0 object-contain"
         onError={() => setFailed(true)} />
  );
}

