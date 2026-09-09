from typing import Literal
from pydantic import BaseModel, Field


# ── Filtri di creazione partita ──────────────────────────────────────────────

class GameFilters(BaseModel):
    season_from: int | None = Field(None, ge=1950, le=2100, description="Anno di inizio stagione minimo (es. 1990 = stagione 90/91)")
    season_to: int | None = Field(None, ge=1950, le=2100, description="Anno di inizio stagione massimo")
    position: Literal["Portiere", "Difensore", "Centrocampista", "Attaccante"] | None = None
    min_appearances: int | None = Field(None, ge=1, description="Minimo presenze totali in carriera")
    team_id: int | None = Field(None, description="ID interno del club — il giocatore deve aver giocato almeno una stagione lì")
    exclude_player_id: int | None = Field(None, description="Esclude un giocatore specifico dalla selezione casuale (usato per evitare ripescaggi)")


class GameCreateRequest(BaseModel):
    nickname: str | None = Field(None, max_length=32)
    filters: GameFilters = Field(default_factory=GameFilters)
    player_id: int | None = Field(None, description="Forza un giocatore specifico invece della selezione casuale")


# ── Career ───────────────────────────────────────────────────────────────────

class CareerEntry(BaseModel):
    """Stint aggregato in un club (una o più stagioni consecutive)."""

    club_id: int
    club_name: str
    season_start: int
    season_end: int
    appearances: int
    goals: int

    @property
    def seasons_label(self) -> str:
        if self.season_start == self.season_end:
            return f"{self.season_start}/{str(self.season_start + 1)[-2:]}"
        return f"{self.season_start}–{self.season_end + 1}"


# ── Hints ────────────────────────────────────────────────────────────────────

class HintState(BaseModel):
    unlocked: bool
    value: str | None = None


HintType = Literal["role", "nationality", "photo"]

HINT_ORDER: list[HintType] = ["role", "nationality", "photo"]


# ── Guess ────────────────────────────────────────────────────────────────────

class GuessRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=100)
    # ID selezionato dall'autocomplete: bypassa la fuzzy search → guess sempre preciso
    player_id: int | None = Field(None, description="ID interno del giocatore selezionato dall'autocomplete")


class GuessEntry(BaseModel):
    input: str
    correct: bool


# ── Player reveal ────────────────────────────────────────────────────────────

class PlayerReveal(BaseModel):
    id: int
    name: str


# ── Game state (risposta principale) ─────────────────────────────────────────

class GameState(BaseModel):
    token: str
    status: Literal["playing", "won", "surrendered"]
    career: list[CareerEntry]
    hints: dict[HintType, HintState]
    guesses: list[GuessEntry]
    attempt_count: int
    hints_used: int
    player: PlayerReveal | None = None  # rivelato solo a fine partita


# ── Preview (selezione giocatore senza creare partita) ───────────────────────

class PreviewRequest(BaseModel):
    filters: GameFilters = Field(default_factory=GameFilters)
    player_id: int | None = Field(None, description="Forza un giocatore specifico")


class PreviewResponse(BaseModel):
    id: int
    name: str
    position_general: str | None = None
    career: list[CareerEntry]


# ── Challenge ────────────────────────────────────────────────────────────────

class ChallengeCreateRequest(BaseModel):
    creator_nickname: str = Field(..., min_length=1, max_length=32)
    player_id: int | None = None
    filters: GameFilters = Field(default_factory=GameFilters)


class ChallengeCreated(BaseModel):
    token: str
    share_url: str


class ChallengeInfo(BaseModel):
    """Informazioni visibili al destinatario prima di accettare la sfida."""

    token: str
    creator_nickname: str
    career_preview: str
    created_at: str


class ChallengeAcceptRequest(BaseModel):
    nickname: str | None = Field(None, max_length=32)
