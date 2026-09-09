from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.game import (
    ChallengeCreateRequest,
    ChallengeCreated,
    ChallengeInfo,
    ChallengeAcceptRequest,
    GameState,
)
from ..services import challenge as challenge_service

router = APIRouter(prefix="/challenge", tags=["challenge"])


@router.post("", response_model=ChallengeCreated, status_code=201)
def create_challenge(body: ChallengeCreateRequest, db: Session = Depends(get_db)):
    """Crea una sfida condivisibile.

    Il creatore può specificare un `player_id` preciso o lasciare che il sistema
    scelga casualmente in base ai filtri. Restituisce il token e l'URL da condividere.
    """
    return challenge_service.create_challenge(
        db=db,
        creator_nickname=body.creator_nickname,
        player_id=body.player_id,
        filters=body.filters,
    )


@router.get("/{token}", response_model=ChallengeInfo)
def get_challenge_info(token: str, db: Session = Depends(get_db)):
    """Restituisce le informazioni della sfida visibili prima di accettare.

    Non rivela il giocatore — solo l'anteprima della carriera (es. "4 squadre · 14 stagioni")
    e il nome di chi ha creato la sfida.
    """
    return challenge_service.get_challenge_info(db, token)


@router.post("/{token}/accept", response_model=GameState, status_code=201)
def accept_challenge(token: str, body: ChallengeAcceptRequest, db: Session = Depends(get_db)):
    """Accetta la sfida: crea una nuova sessione di gioco per il destinatario.

    Restituisce direttamente lo stato iniziale della partita, pronto per giocare.
    """
    return challenge_service.accept_challenge(db, token, body.nickname)
