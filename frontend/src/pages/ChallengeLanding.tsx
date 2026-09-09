import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getChallengeInfo, acceptChallenge } from "../api/challenge";
import type { ChallengeInfo } from "../types/api";

export function ChallengeLanding() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [info, setInfo] = useState<ChallengeInfo | null>(null);
  const [nickname, setNickname] = useState(
    () => localStorage.getItem("nickname") ?? ""
  );
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    getChallengeInfo(token)
      .then(setInfo)
      .catch(() => setError("Sfida non trovata o scaduta."))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleAccept() {
    if (!token) return;
    setAccepting(true);
    try {
      const nick = nickname.trim() || undefined;
      if (nick) localStorage.setItem("nickname", nick);
      const game = await acceptChallenge(token, nick);
      navigate(`/gioca/${game.token}`);
    } catch {
      setError("Errore nell'avvio della partita.");
    } finally {
      setAccepting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-crema flex items-center justify-center">
        <p className="text-[#888]">Caricamento sfida…</p>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="min-h-screen bg-crema flex flex-col items-center justify-center gap-4 px-6">
        <p className="text-xl">😕</p>
        <p className="text-[#555] text-center">{error ?? "Sfida non disponibile."}</p>
        <button
          onClick={() => navigate("/")}
          className="px-4 py-2 rounded border border-verde text-verde text-sm hover:bg-verde/5"
        >
          Gioca una partita normale
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-crema flex flex-col">
      <header className="bg-verde text-white text-center py-8 px-4">
        <h1 className="text-2xl font-black tracking-tight">CAMPIONISSIMO</h1>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 py-10 gap-6 max-w-sm mx-auto w-full">
        {/* Card sfida */}
        <div className="w-full p-6 bg-white border-2 border-oro rounded-xl text-center shadow">
          <p className="text-3xl mb-3">⚡</p>
          <h2 className="text-xl font-black text-verde mb-1">
            {info.creator_nickname} ti ha sfidato!
          </h2>
          <p className="text-sm text-[#666] mt-3">
            {info.career_preview}
          </p>
        </div>

        {/* Nickname */}
        <div className="w-full">
          <label className="block text-xs font-semibold text-[#666] uppercase tracking-wide mb-1.5">
            Come ti chiami?
          </label>
          <input
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder="Il tuo soprannome"
            maxLength={32}
            className="w-full px-3 py-2.5 border border-bordo rounded bg-white text-sm outline-none focus:border-verde focus:ring-1 focus:ring-verde/30"
          />
        </div>

        <button
          onClick={handleAccept}
          disabled={accepting}
          className="w-full py-4 bg-verde text-white rounded font-black text-base tracking-wide hover:bg-verde-dark transition-all active:scale-[0.98] disabled:opacity-70 shadow-md"
        >
          {accepting ? "…" : "ACCETTA ▶"}
        </button>
      </main>
    </div>
  );
}
