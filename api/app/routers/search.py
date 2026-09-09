from fastapi import APIRouter, Query, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.player import Club
from ..schemas.search import SearchResponse, TeamResult
from ..services import search as search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=100, description="Nome del giocatore da cercare"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Ricerca fuzzy su tutti i giocatori nel database.

    Gestisce automaticamente:
    - Alias (cr7 → Cristiano Ronaldo, totti → Francesco Totti, …)
    - Trasposizioni di parole (Ronaldo Cristiano → Cristiano Ronaldo)
    - Nomi parziali e abbreviazioni
    - Accenti e caratteri speciali
    """
    results = search_service.search_players(q, limit=limit)
    return SearchResponse(query=q, results=results, total=len(results))


@router.get("/teams", response_model=list[TeamResult])
def search_teams(
    q: str = Query(..., min_length=1, max_length=100, description="Nome della squadra"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Ricerca squadre per nome (ILIKE). Usata per il filtro team nella home."""
    results = (
        db.query(Club.id, Club.name)
        .filter(Club.name.ilike(f"%{q}%"))
        .order_by(Club.name)
        .limit(limit)
        .all()
    )
    return [TeamResult(id=r[0], name=r[1]) for r in results]


@router.post("/refresh-index", tags=["admin"])
def refresh_search_index(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
    db: Session = Depends(get_db),
):
    """Ricostruisce l'indice di ricerca in memoria. Richiede header X-Admin-Secret."""
    if not settings.ADMIN_SECRET or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Non autorizzato.")
    search_service.refresh_index(db)
    return {"ok": True, "message": "Indice aggiornato."}
