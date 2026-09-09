import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..models.player import Player, Career
from ..schemas.game import (
    GameCreateRequest,
    GameState,
    GuessRequest,
    HintType,
    PreviewRequest,
    PreviewResponse,
)
from ..services import game as game_service

router = APIRouter(prefix="/game", tags=["game"])


@router.post("", response_model=GameState, status_code=201)
def create_game(body: GameCreateRequest, db: Session = Depends(get_db)):
    """Crea una nuova partita.

    Se `player_id` è specificato usa quel giocatore specifico; altrimenti
    seleziona casualmente in base ai filtri.
    Restituisce lo stato iniziale: carriera visibile, tutti gli indizi bloccati.
    """
    if body.player_id is not None:
        player = (
            db.query(Player)
            .options(
                joinedload(Player.careers).joinedload(Career.club),
                joinedload(Player.country),
            )
            .filter(Player.id == body.player_id)
            .first()
        )
        if player is None:
            raise HTTPException(status_code=404, detail="Giocatore non trovato")
    else:
        player = game_service.select_player(db, body.filters)
    return game_service.create_game(db, player, body.nickname, body.filters)


@router.post("/preview", response_model=PreviewResponse)
def preview_player(body: PreviewRequest, db: Session = Depends(get_db)):
    """Seleziona un giocatore (casuale o specifico) e ne restituisce i dati
    senza creare alcuna partita. Usato dalla schermata 'Crea Sfida' per mostrare
    la preview prima di confermare il link."""
    if body.player_id is not None:
        player = (
            db.query(Player)
            .options(
                joinedload(Player.careers).joinedload(Career.club),
            )
            .filter(Player.id == body.player_id)
            .first()
        )
        if player is None:
            raise HTTPException(status_code=404, detail="Giocatore non trovato")
    else:
        player = game_service.select_player(db, body.filters)

    # Ricostruisce la carriera aggregata nello stesso modo del servizio di gioco
    career = game_service.aggregate_career(player.careers)

    return PreviewResponse(
        id=player.id,
        name=player.name,
        position_general=player.position_general,
        career=career,
    )


@router.get("/{token}", response_model=GameState)
def get_game(token: str, db: Session = Depends(get_db)):
    """Restituisce lo stato corrente di una partita tramite il suo token."""
    return game_service.get_game(db, token)


@router.post("/{token}/guess", response_model=GameState)
def submit_guess(token: str, body: GuessRequest, db: Session = Depends(get_db)):
    """Invia un tentativo di risposta.

    La ricerca del giocatore è fuzzy: "cr7", "Ronaldo il Fenomeno", "totti"
    funzionano senza digitare il nome esatto.
    """
    return game_service.submit_guess(db, token, body.input, body.player_id)


@router.post("/{token}/hint/{hint_type}", response_model=GameState)
def unlock_hint(token: str, hint_type: HintType, db: Session = Depends(get_db)):
    """Sblocca un indizio. Ordine suggerito: role → nationality → photo.

    Un indizio già sbloccato restituisce 409.
    """
    return game_service.unlock_hint(db, token, hint_type)


@router.post("/{token}/surrender", response_model=GameState)
def surrender(token: str, db: Session = Depends(get_db)):
    """Termina la partita con resa. Rivela l'identità del giocatore."""
    return game_service.surrender(db, token)


@router.get("/{token}/photo")
def get_photo(token: str, sig: str, db: Session = Depends(get_db)):
    """Serve il redirect alla foto del giocatore solo se l'indizio photo è stato
    sbloccato e la firma HMAC è valida. Impedisce di ricavare il player_id dall'indizio.

    Query param: ?sig=<player_id>:<hmac> (valore restituito dall'hint photo)
    """
    # Verifica che il token di partita esista e la foto sia sbloccata
    from ..models.game import GameSession, GameHint
    session = db.query(GameSession).filter(GameSession.token == token).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Partita non trovata.")

    hint_unlocked = db.query(GameHint).filter(
        GameHint.session_id == session.id,
        GameHint.hint_type == "photo",
    ).first()
    if hint_unlocked is None:
        raise HTTPException(status_code=403, detail="Indizio foto non ancora sbloccato.")

    # Verifica firma HMAC
    try:
        player_id_str, provided_sig = sig.split(":", 1)
        player_id = int(player_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Parametro sig non valido.")

    expected_sig = hmac.new(
        settings.HINT_SIGN_KEY.encode(),
        f"{token}:{player_id}".encode(),
        hashlib.sha256,
    ).hexdigest()[:24]

    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(status_code=403, detail="Firma non valida.")

    # Serve redirect alla risorsa asset (CDN o locale)
    photo_url = f"{settings.ASSETS_BASE_URL}/photos/{player_id}.webp"
    return RedirectResponse(url=photo_url, status_code=302)
