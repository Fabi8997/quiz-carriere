"""Logica per la gestione delle sfide condivisibili."""

import logging

from sqlalchemy.orm import Session

from ..models.game import ChallengeLink
from ..models.player import Player, Career
from ..schemas.game import (
    GameFilters,
    ChallengeCreated,
    ChallengeInfo,
    GameState,
)
from ..core.exceptions import ChallengeNotFound, NoPlayersFound
from ..config import settings
from . import game as game_service

logger = logging.getLogger(__name__)


def _load_challenge(db: Session, token: str) -> ChallengeLink:
    challenge = db.query(ChallengeLink).filter(ChallengeLink.token == token).first()
    if challenge is None:
        raise ChallengeNotFound(token)
    return challenge


def create_challenge(
    db: Session,
    creator_nickname: str,
    player_id: int | None,
    filters: GameFilters,
) -> ChallengeCreated:
    """Crea un link di sfida.

    Se `player_id` è specificato usa quel giocatore, altrimenti ne seleziona
    uno casuale secondo i filtri forniti.
    """
    if player_id is not None:
        player = db.query(Player).filter(Player.id == player_id).first()
        if player is None:
            raise NoPlayersFound()
    else:
        player = game_service.select_player(db, filters)

    challenge = ChallengeLink(
        creator_nickname=creator_nickname,
        player_id=player.id,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    share_url = f"{settings.FRONTEND_URL}/sfida/{challenge.token}"

    return ChallengeCreated(token=challenge.token, share_url=share_url)


def get_challenge_info(db: Session, token: str) -> ChallengeInfo:
    """Restituisce le info visibili al destinatario prima di accettare."""
    challenge = _load_challenge(db, token)

    # Anteprima carriera senza rivelare il giocatore
    careers = db.query(Career).filter(Career.player_id == challenge.player_id).all()
    aggregated = game_service.aggregate_career(careers)
    num_clubs = len(aggregated)
    num_seasons = sum(e.season_end - e.season_start + 1 for e in aggregated)
    preview = f"{num_clubs} squadr{'a' if num_clubs == 1 else 'e'} · {num_seasons} stagion{'e' if num_seasons == 1 else 'i'}"

    return ChallengeInfo(
        token=challenge.token,
        creator_nickname=challenge.creator_nickname,
        career_preview=preview,
        created_at=challenge.created_at,
    )


def accept_challenge(db: Session, token: str, nickname: str | None) -> GameState:
    """Accetta la sfida creando una nuova sessione di gioco per il destinatario."""
    challenge = _load_challenge(db, token)

    from sqlalchemy.orm import joinedload
    player = (
        db.query(Player)
        .options(
            joinedload(Player.careers).joinedload(Career.club),
            joinedload(Player.country),
        )
        .filter(Player.id == challenge.player_id)
        .first()
    )

    return game_service.create_game(
        db=db,
        player=player,
        nickname=nickname,
        filters=GameFilters(),
    )
