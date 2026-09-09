import { client } from "./client";
import type { SearchResult, TeamResult } from "../types/api";

interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export async function searchPlayers(
  q: string,
  limit = 8
): Promise<SearchResult[]> {
  if (!q.trim()) return [];
  const { data } = await client.get<SearchResponse>("/search", {
    params: { q, limit },
  });
  return data.results;
}

export async function searchTeams(
  q: string,
  limit = 8
): Promise<TeamResult[]> {
  if (!q.trim()) return [];
  const { data } = await client.get<TeamResult[]>("/search/teams", {
    params: { q, limit },
  });
  return data;
}
