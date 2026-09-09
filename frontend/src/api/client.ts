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
// In prod: URL Supabase Storage (es. https://xxx.supabase.co/storage/v1/object/public/assets)
const ASSETS_URL = import.meta.env.VITE_ASSETS_BASE_URL ?? "/assets";

export function crestUrl(clubId: number): string {
  return `${ASSETS_URL}/crests/${clubId}.webp`;
}

export function photoUrl(playerId: number): string {
  return `${ASSETS_URL}/photos/${playerId}.webp`;
}

export function flagUrl(countryTmId: string): string {
  return `${ASSETS_URL}/flags/${countryTmId}.webp`;
}
