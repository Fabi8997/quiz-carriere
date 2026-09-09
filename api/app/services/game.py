"""Logica di business per la gestione delle partite."""

import hashlib
import hmac
import json
import random
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from ..models.player import Player, Career
from ..models.game import GameSession, GameGuess, GameHint
from ..schemas.game import (
    GameFilters,
    GameState,
    CareerEntry,
    HintState,
    HintType,
    HINT_ORDER,
    GuessEntry,
    PlayerReveal,
)
from ..core.exceptions import (
    GameNotFound,
    GameAlreadyOver,
    HintAlreadyUnlocked,
    NoPlayersFound,
)
from . import search as search_service

logger = logging.getLogger(__name__)


# ── Selezione giocatore ───────────────────────────────────────────────────────

def select_player(db: Session, filters: GameFilters) -> Player:
    """Seleziona casualmente un giocatore che soddisfa i filtri.

    Logica presenze e stagioni:
    - Con team_id: presenze e stagioni si riferiscono a quel club nel periodo indicato.
    - Senza team_id: presenze = totale carriera; stagioni = qualsiasi club nel periodo.

    Raises NoPlayersFound se la combinazione di filtri non dà risultati.
    """
    from sqlalchemy import func

    has_team = filters.team_id is not None
    has_season = filters.season_from is not None or filters.season_to is not None
    has_apps = filters.min_appearances is not None

    if has_team:
        # ── Con squadra: filtra le career rows di quel club ──────────────────
        cq = db.query(Career.player_id, func.sum(Career.appearances).label("club_apps"))
        cq = cq.filter(Career.club_id == filters.team_id)

        if filters.season_from is not None:
            cq = cq.filter(Career.season >= filters.season_from)
        if filters.season_to is not None:
            cq = cq.filter(Career.season <= filters.season_to)

        cq = cq.group_by(Career.player_id)

        if has_apps:
            cq = cq.having(func.sum(Career.appearances) >= filters.min_appearances)

        valid_ids = [r[0] for r in cq.all()]

        query = db.query(Player).filter(Player.id.in_(valid_ids))

    else:
        # ── Senza squadra: presenze sul totale carriera ───────────────────────
        apps_sq = (
            db.query(Career.player_id, func.sum(Career.appearances).label("total_apps"))
            .group_by(Career.player_id)
            .subquery()
        )
        query = db.query(Player).join(apps_sq, apps_sq.c.player_id == Player.id)

        if has_season:
            # Il giocatore deve aver giocato in almeno una stagione del range
            sq = db.query(Career.player_id).group_by(Career.player_id)
            if filters.season_from is not None:
                sq = sq.having(func.max(Career.season) >= filters.season_from)
            if filters.season_to is not None:
                sq = sq.having(func.min(Career.season) <= filters.season_to)
            season_ids = [r[0] for r in sq.all()]
            query = query.filter(Player.id.in_(season_ids))

        if has_apps:
            query = query.filter(apps_sq.c.total_apps >= filters.min_appearances)

    # Ruolo — sempre applicato indipendentemente dalla squadra
    if filters.position:
        query = query.filter(Player.position_general == filters.position)

    # Esclusione esplicita (es. evita ripescaggio dello stesso giocatore)
    if filters.exclude_player_id is not None:
        query = query.filter(Player.id != filters.exclude_player_id)

    # Conta e scegli offset casuale per efficienza (evita di caricare tutto in memoria)
    count = query.count()
    if count == 0:
        raise NoPlayersFound()

    offset = random.randint(0, count - 1)
    player = query.options(
        joinedload(Player.careers).joinedload(Career.club),
        joinedload(Player.country),
    ).offset(offset).first()

    if player is None:
        raise NoPlayersFound()

    return player


# ── Aggregazione carriera ─────────────────────────────────────────────────────

def aggregate_career(careers: list[Career]) -> list[CareerEntry]:
    """Raggruppa le stagioni consecutive nello stesso club in un'unica voce.

    Esempio: Juve 1994, 1995, 1996 → un entry Juve 1994–1996.
    Se il giocatore torna allo stesso club dopo un'interruzione, è un nuovo entry.
    """
    entries: list[CareerEntry] = []
    current: dict | None = None

    for c in sorted(careers, key=lambda x: x.season):
        if (
            current is not None
            and current["club_id"] == c.club_id
            and c.season == current["season_end"] + 1
        ):
            current["season_end"] = c.season
            current["appearances"] += c.appearances or 0
            current["goals"] += c.goals or 0
        else:
            if current is not None:
                entries.append(CareerEntry(**current))
            current = {
                "club_id": c.club.id,
                "club_name": c.club.name,
                "season_start": c.season,
                "season_end": c.season,
                "appearances": c.appearances or 0,
                "goals": c.goals or 0,
            }

    if current is not None:
        entries.append(CareerEntry(**current))

    return entries


# ── Costruzione stato partita ─────────────────────────────────────────────────

def _load_session(db: Session, token: str) -> GameSession:
    session = (
        db.query(GameSession)
        .options(
            joinedload(GameSession.player)
            .joinedload(Player.careers)
            .joinedload(Career.club),
            joinedload(GameSession.player).joinedload(Player.country),
            joinedload(GameSession.guesses),
            joinedload(GameSession.hints),
        )
        .filter(GameSession.token == token)
        .first()
    )
    if session is None:
        raise GameNotFound(token)
    return session


def build_state(session: GameSession) -> GameState:
    """Costruisce il DTO di risposta a partire dall'ORM session."""
    career = aggregate_career(session.player.careers)

    unlocked_types = {h.hint_type for h in session.hints}
    hints: dict[HintType, HintState] = {}
    for ht in HINT_ORDER:
        if ht in unlocked_types:
            value = _hint_value(session.player, ht, session.token)
            hints[ht] = HintState(unlocked=True, value=value)
        else:
            hints[ht] = HintState(unlocked=False)

    guesses = [GuessEntry(input=g.raw_input, correct=g.is_correct) for g in session.guesses]

    player_reveal = None
    if session.status != "playing":
        player_reveal = PlayerReveal(id=session.player.id, name=session.player.name)

    return GameState(
        token=session.token,
        status=session.status,
        career=career,
        hints=hints,
        guesses=guesses,
        attempt_count=len(session.guesses),
        hints_used=len(session.hints),
        player=player_reveal,
    )


def _hint_value(player: Player, hint_type: HintType, session_token: str) -> str | None:
    if hint_type == "role":
        return player.position_general
    if hint_type == "nationality":
        # Restituisce il tm_id del paese → il frontend costruisce l'URL del flag asset
        return player.country.tm_id if player.country else None
    if hint_type == "photo":
        # NON restituiamo il player_id diretto: firmiamo l'id con HMAC legato al
        # token di sessione. Il frontend lo passa a GET /game/{token}/photo che
        # verifica la firma e serve il redirect all'asset reale.
        # Così il valore dell'indizio è inutile fuori dal contesto della partita.
        from ..config import settings
        sig = hmac.new(
            settings.HINT_SIGN_KEY.encode(),
            f"{session_token}:{player.id}".encode(),
            hashlib.sha256,
        ).hexdigest()[:24]
        return f"{player.id}:{sig}"
    return None


# ── Azioni di gioco ───────────────────────────────────────────────────────────

def create_game(db: Session, player: Player, nickname: str | None, filters: GameFilters) -> GameState:
    session = GameSession(
        player_id=player.id,
        nickname=nickname,
        filters_json=filters.model_dump_json(),
    )
    db.add(session)
    db.flush()  # assegna l'id prima del commit

    # Ricarica con joinedload per costruire lo stato
    db.refresh(session)
    session = _load_session(db, session.token)
    db.commit()

    return build_state(session)


def get_game(db: Session, token: str) -> GameState:
    session = _load_session(db, token)
    return build_state(session)


def submit_guess(
    db: Session,
    token: str,
    raw_input: str,
    player_id: int | None = None,
) -> GameState:
    session = _load_session(db, token)

    if session.status != "playing":
        raise GameAlreadyOver()

    # Se il frontend ha passato l'ID diretto (selezionato dall'autocomplete) lo usiamo
    # senza passare per la fuzzy search — più preciso e più veloce.
    # SICUREZZA: il player_id viene usato SOLO per trovare il nome da mostrare nel log
    # e per il match. Non può essere usato per brute force perché:
    # 1. Il guess viene registrato nel DB con raw_input (audit trail visibile al giocatore)
    # 2. La risposta è solo "corretto/sbagliato" — non rivela il player_id target
    # 3. Rate limiting infrastrutturale (Fly.io/Cloudflare) limita le chiamate/secondo
    if player_id is not None:
        # Verifica che il player_id corrisponda effettivamente a un giocatore reale
        # (impedisce la sottomissione di ID arbitrari/inventati)
        from ..models.player import Player as PlayerModel
        exists = db.query(PlayerModel.id).filter(PlayerModel.id == player_id).scalar()
        if exists is None:
            player_id = None  # ID non valido → fallback a fuzzy search

    if player_id is not None:
        guessed_player_id = player_id
    else:
        search_results = search_service.search_players(raw_input, limit=1)
        guessed_player_id = search_results[0].id if search_results else None

    is_correct = guessed_player_id == session.player_id

    guess = GameGuess(
        session_id=session.id,
        guessed_player_id=guessed_player_id,
        raw_input=raw_input.strip(),
        is_correct=is_correct,
    )
    db.add(guess)

    if is_correct:
        session.status = "won"
        session.completed_at = datetime.now(timezone.utc).isoformat()

    db.commit()

    return build_state(_load_session(db, token))


def unlock_hint(db: Session, token: str, hint_type: HintType) -> GameState:
    session = _load_session(db, token)

    if session.status != "playing":
        raise GameAlreadyOver()

    already_unlocked = {h.hint_type for h in session.hints}
    if hint_type in already_unlocked:
        raise HintAlreadyUnlocked(hint_type)

    hint = GameHint(session_id=session.id, hint_type=hint_type)
    db.add(hint)
    db.commit()

    return build_state(_load_session(db, token))


def surrender(db: Session, token: str) -> GameState:
    session = _load_session(db, token)

    if session.status != "playing":
        raise GameAlreadyOver()

    session.status = "surrendered"
    session.completed_at = datetime.now(timezone.utc).isoformat()
    db.commit()

    return build_state(_load_session(db, token))
