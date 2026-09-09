import { client } from "./client";
import type { ChallengeCreated, ChallengeInfo, GameFilters, GameState } from "../types/api";

export async function createChallenge(
  creatorNickname: string,
  playerId?: number,
  filters: GameFilters = {}
): Promise<ChallengeCreated> {
  const { data } = await client.post<ChallengeCreated>("/challenge", {
    creator_nickname: creatorNickname,
    ...(playerId !== undefined ? { player_id: playerId } : {}),
    filters,
  });
  return data;
}

export async function getChallengeInfo(token: string): Promise<ChallengeInfo> {
  const { data } = await client.get<ChallengeInfo>(`/challenge/${token}`);
  return data;
}

export async function acceptChallenge(
  token: string,
  nickname?: string
): Promise<GameState> {
  const { data } = await client.post<GameState>(`/challenge/${token}/accept`, {
    nickname,
  });
  return data;
}
