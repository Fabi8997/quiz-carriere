import axios from "axios";

// In dev: proxy Vite → /api → localhost:8000
// In prod: URL assoluto del backend (es. https://campionissimo.fly.dev)
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const client = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 10_000,
});

// In dev: /assets → serviti dal backend locale via proxy Vite
// In prod: URL Supabase Storage (es. https://xxx.supabase.co/storage/v1/object/public)
const ASSETS_URL = import.meta.env.VITE_ASSETS_BASE_URL ?? "";

// In Supabase Storage, i file sono stati caricati con la struttura:
//   bucket=photos → path photos/1.webp  → URL .../photos/photos/1.webp
//   bucket=crests → path crests/1.webp  → URL .../crests/crests/1.webp
// In dev, il backend locale serve direttamente /assets/photos/1.webp
function assetUrl(type: string, file: string): string {
  if (ASSETS_URL) {
    // Produzione: Supabase Storage con doppio path per via dell'upload
    return `${ASSETS_URL}/${type}/${type}/${file}`;
  }
  // Dev: proxy Vite → FastAPI StaticFiles
  return `/assets/${type}/${file}`;
}

export function crestUrl(clubId: number): string {
  return assetUrl("crests", `${clubId}.webp`);
}

export function photoUrl(playerId: number): string {
  return assetUrl("photos", `${playerId}.webp`);
}

export function flagUrl(countryTmId: string): string {
  return assetUrl("flags", `${countryTmId}.webp`);
}
