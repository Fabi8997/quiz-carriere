export type HintType = "role" | "nationality" | "photo";
export type GameStatus = "playing" | "won" | "surrendered";
export type Position = "Portiere" | "Difensore" | "Centrocampista" | "Attaccante";

export interface CareerEntry {
  club_id: number;
  club_name: string;
  season_start: number;
  season_end: number;
  appearances: number;
  goals: number;
}

export interface HintState {
  unlocked: boolean;
  value: string | null;
}

export interface GuessEntry {
  input: string;
  correct: boolean;
}

export interface PlayerReveal {
  id: number;
  name: string;
}

export interface GameState {
  token: string;
  status: GameStatus;
  career: CareerEntry[];
  hints: Record<HintType, HintState>;
  guesses: GuessEntry[];
  attempt_count: number;
  hints_used: number;
  player: PlayerReveal | null;
}

export interface GameFilters {
  season_from?: number;
  season_to?: number;
  position?: Position;
  min_appearances?: number;
  team_id?: number;
  exclude_player_id?: number;
}

export interface SearchResult {
  id: number;
  name: string;
  position_general: string | null;
  country_name: string | null;
  score: number;
}

export interface TeamResult {
  id: number;
  name: string;
}

export interface PlayerPreview {
  id: number;
  name: string;
  position_general: string | null;
  career: CareerEntry[];
}

export interface ChallengeInfo {
  token: string;
  creator_nickname: string;
  career_preview: string;
  created_at: string;
}

export interface ChallengeCreated {
  token: string;
  share_url: string;
}
