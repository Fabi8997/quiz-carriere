"""Servizio di ricerca giocatori con fuzzy matching in memoria.

Strategia:
1. All'avvio carica tutti i giocatori + alias in RAM (~8.000 voci, pochi MB).
2. Pipeline di ricerca in ordine di priorità:
   a. Alias esatti (score = 100) — "cr7", "el fenomeno", ecc.
   b. Sottostringa esatta nel nome normalizzato (score = 95) — "totti", "del piero"
   c. Fuzzy WRatio (rapidfuzz) — gestisce trasposizioni, accenti, nomi parziali.
      Usa WRatio invece di token_sort_ratio perché combina internamente
      partial_ratio, token_set_ratio e ratio, scegliendo il punteggio migliore.
3. L'indice si può rigenerare con `refresh_index()` senza riavviare il server.
"""

import unicodedata
import re
import logging
from dataclasses import dataclass

from rapidfuzz import process, fuzz
from sqlalchemy.orm import Session

from ..config import settings
from ..schemas.search import SearchResult

logger = logging.getLogger(__name__)


# ── Normalizzazione ───────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Minuscolo, rimuove accenti, punteggiatura e spazi multipli."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ── Indice in memoria ─────────────────────────────────────────────────────────

@dataclass
class _PlayerEntry:
    id: int
    name: str
    normalized_name: str
    position_general: str | None
    country_name: str | None


_index: list[_PlayerEntry] = []
_alias_map: dict[str, int] = {}  # normalized_alias → player_id
_names_list: list[str] = []      # parallelo a _index, per rapidfuzz
_ready = False


def build_index(db: Session) -> None:
    """Carica l'indice di ricerca in memoria. Da chiamare all'avvio."""
    global _index, _alias_map, _names_list, _ready

    from ..models.player import Player, PlayerAlias, Country
    from sqlalchemy.orm import joinedload

    logger.info("Costruzione indice di ricerca...")

    players = (
        db.query(Player)
        .options(joinedload(Player.country))
        .all()
    )

    _index = [
        _PlayerEntry(
            id=p.id,
            name=p.name,
            normalized_name=p.normalized_name or normalize(p.name),
            position_general=p.position_general,
            country_name=p.country.name if p.country else None,
        )
        for p in players
    ]
    _names_list = [e.normalized_name for e in _index]

    aliases = db.query(PlayerAlias).all()
    _alias_map = {normalize(a.alias): a.player_id for a in aliases}

    _ready = True
    logger.info(f"Indice pronto: {len(_index)} giocatori, {len(_alias_map)} alias")


def refresh_index(db: Session) -> None:
    """Ricostruisce l'indice — utile dopo aggiornamenti del DB senza riavvio."""
    build_index(db)


# ── Ricerca ───────────────────────────────────────────────────────────────────

def search_players(query: str, limit: int = 10) -> list[SearchResult]:
    """Restituisce i giocatori più simili alla query, in ordine di rilevanza."""
    if not _ready:
        logger.warning("Indice non ancora pronto, restituisco lista vuota.")
        return []

    query = query.strip()
    if not query:
        return []

    nq = normalize(query)
    seen_ids: set[int] = set()
    results: list[SearchResult] = []

    # 1. Alias esatti (score = 100)
    if nq in _alias_map:
        pid = _alias_map[nq]
        entry = next((e for e in _index if e.id == pid), None)
        if entry:
            results.append(_to_result(entry, 100))
            seen_ids.add(pid)

    # 2. Sottostringa esatta nel nome normalizzato (score = 95)
    #    Cattura casi come "totti", "del piero", "van basten" anche senza fuzzy.
    if len(nq) >= 3:
        for entry in _index:
            if entry.id not in seen_ids and nq in entry.normalized_name:
                results.append(_to_result(entry, 95))
                seen_ids.add(entry.id)

    # 3. Fuzzy WRatio — migliore per nomi propri, gestisce ordine parole e abbreviazioni
    matches = process.extract(
        nq,
        _names_list,
        scorer=fuzz.WRatio,
        limit=limit * 5,
        score_cutoff=max(settings.FUZZY_SCORE_THRESHOLD - 10, 40),
    )

    for _matched_text, score, idx in matches:
        entry = _index[idx]
        if entry.id not in seen_ids:
            results.append(_to_result(entry, int(score)))
            seen_ids.add(entry.id)

    # Ordina: alias (100) → sottostringa (95) → fuzzy (decrescente)
    results.sort(key=lambda r: -r.score)

    return results[:limit]


def _to_result(entry: _PlayerEntry, score: int) -> SearchResult:
    return SearchResult(
        id=entry.id,
        name=entry.name,
        position_general=entry.position_general,
        country_name=entry.country_name,
        score=score,
    )
