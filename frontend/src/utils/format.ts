/** "1994, 1998" → "94–99" (la stagione 98 finisce nel 99) */
export function formatSeasonRange(start: number, end: number): string {
  const s = String(start).slice(-2);
  const e = String(end + 1).slice(-2);
  if (start === end) return `${s}/${e}`;
  return `${s}–${e}`;
}

/** Intero → stringa con eventuale zero (es. 7 → "07") */
export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Copia testo negli appunti. Restituisce true se riuscito. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Condivide tramite Web Share API (mobile) o copia negli appunti come fallback. */
export async function shareOrCopy(text: string, title = "Campionissimo"): Promise<void> {
  if (navigator.share) {
    await navigator.share({ title, text });
  } else {
    await copyToClipboard(text);
  }
}

/**
 * Testo condivisibile per una partita completata (stile Wordle).
 * NON include il nome del giocatore — chi riceve il link deve scoprirlo da solo.
 */
export function formatShareText(
  attempts: number,
  hintsUsed: number,
  won: boolean,
  creatorName?: string
): string {
  const who = creatorName ? `${creatorName} ha` : "Ho";
  const outcome = won
    ? `${who} indovinato in ${attempts} ${attempts === 1 ? "tentativo" : "tentativi"}${hintsUsed > 0 ? ` e ${hintsUsed} ${hintsUsed === 1 ? "indizio" : "indizi"}` : ""}! 🏆`
    : `${who} capitolato dopo ${attempts} ${attempts === 1 ? "tentativo" : "tentativi"}. 🏳️`;
  return `🏆 Campionissimo\n${outcome}\nRiesci a indovinare chi è il campionissimo?`;
}
