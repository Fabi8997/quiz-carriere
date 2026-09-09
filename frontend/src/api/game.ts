import { client } from "./client";
import type { GameFilters, GameState, HintType, PlayerPreview } from "../types/api";

export async function previewPlayer(
  filters: GameFilters = {},
  playerId?: number
): Promise<PlayerPreview> {
  const { data } = await client.post<PlayerPreview>("/game/preview", {
    filters,
    ...(playerId !== undefined ? { player_id: playerId } : {}),
  });
  return data;
}

export async function createGame(
  filters: GameFilters = {},
  nickname?: string,
  playerId?: number
): Promise<GameState> {
  const { data } = await client.post<GameState>("/game", {
    filters,
    nickname,
    ...(playerId !== undefined ? { player_id: playerId } : {}),
  });
  return data;
}

export async function getGame(token: string): Promise<GameState> {
  const { data } = await client.get<GameState>(`/game/${token}`);
  return data;
}

export async function submitGuess(
  token: string,
  input: string,
  playerId?: number
): Promise<GameState> {
  const { data } = await client.post<GameState>(`/game/${token}/guess`, {
    input,
    ...(playerId !== undefined ? { player_id: playerId } : {}),
  });
  return data;
}

export async function unlockHint(token: string, hintType: HintType): Promise<GameState> {
  const { data } = await client.post<GameState>(`/game/${token}/hint/${hintType}`);
  return data;
}

export async function surrender(token: string): Promise<GameState> {
  const { data } = await client.post<GameState>(`/game/${token}/surrender`);
  return data;
}
