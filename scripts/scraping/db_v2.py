"""
Helpers condivisi per lo schema DB v2.
Importato da tutti gli script di scraping — non eseguire direttamente.

Schema v2 rispetto a v1:
- id AUTOINCREMENT su players e clubs (non dipende da TM)
- tm_id come riferimento esterno (UNIQUE, ma non PK)
- countries come entità propria (non campo testo su players)
- height_cm INTEGER invece di "185 cm" testo
- position_general derivato da position_detailed
- slug per URL/export open dataset
- careers con FK reali e source_id per tracciare la provenienza
"""
import sqlite3
import unicodedata
import re

CREST_URL_PATTERN = (
    "https://img.a.transfermarkt.technology/wappen/homepageWappen150x150/{club_id}.png?lm=4711"
)
TM_SOURCE_NAME = "transfermarkt"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_sources (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS countries (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    tm_id    TEXT UNIQUE,
    flag_url TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tm_id               TEXT UNIQUE NOT NULL,
    slug                TEXT UNIQUE,
    name                TEXT NOT NULL,
    normalized_name     TEXT,
    birth_date          TEXT,
    birth_place         TEXT,
    height_cm           INTEGER,
    country_id          INTEGER REFERENCES countries(id),
    position_general    TEXT CHECK(position_general IN
                            ('Portiere','Difensore','Centrocampista','Attaccante')),
    position_detailed   TEXT,
    photo_url           TEXT,
    photo_source_ts     INTEGER,
    photo_downloaded_at TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clubs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tm_id               TEXT UNIQUE NOT NULL,
    slug                TEXT UNIQUE,
    name                TEXT NOT NULL,
    country_id          INTEGER REFERENCES countries(id),
    crest_url           TEXT,
    crest_downloaded_at TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS careers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id    INTEGER NOT NULL REFERENCES players(id),
    club_id      INTEGER NOT NULL REFERENCES clubs(id),
    season       INTEGER NOT NULL,
    appearances  INTEGER,
    goals        INTEGER,
    assists      INTEGER,
    competitions TEXT,
    source_id    INTEGER REFERENCES data_sources(id),
    UNIQUE(player_id, club_id, season)
);

CREATE TABLE IF NOT EXISTS player_aliases (
    alias     TEXT PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS leagues (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    tm_id      TEXT UNIQUE,
    country_id INTEGER REFERENCES countries(id)
);
"""


def normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", only_ascii.lower())


def _slug_base(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = only_ascii.lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return re.sub(r"-+", "-", s) or "unknown"


def _unique_slug(cur, table: str, base: str) -> str:
    cur.execute(f"SELECT 1 FROM {table} WHERE slug = ?", (base,))
    if not cur.fetchone():
        return base
    counter = 2
    while True:
        candidate = f"{base}-{counter}"
        cur.execute(f"SELECT 1 FROM {table} WHERE slug = ?", (candidate,))
        if not cur.fetchone():
            return candidate
        counter += 1


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    conn.execute("INSERT OR IGNORE INTO data_sources (name) VALUES (?)", (TM_SOURCE_NAME,))
    conn.commit()
    return conn


def get_tm_source_id(conn) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM data_sources WHERE name = ?", (TM_SOURCE_NAME,))
    return cur.fetchone()[0]


def get_or_create_player(conn, tm_id: str, name: str) -> int:
    """Ritorna l'id interno del giocatore, inserendo se non esiste.
    Chiamare dentro db_lock quando si usa threading."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM players WHERE tm_id = ?", (tm_id,))
    row = cur.fetchone()
    if row:
        return row[0]
    slug = _unique_slug(cur, "players", _slug_base(name))
    cur.execute(
        "INSERT INTO players (tm_id, slug, name, normalized_name) VALUES (?, ?, ?, ?)",
        (tm_id, slug, name, normalize_name(name)),
    )
    return cur.lastrowid


def get_or_create_club(conn, tm_id: str, name: str, crest_url: str = None) -> int:
    """Ritorna l'id interno del club, inserendo se non esiste.
    Se il club esiste con nome placeholder, lo aggiorna col nome reale.
    Chiamare dentro db_lock quando si usa threading."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM clubs WHERE tm_id = ?", (tm_id,))
    row = cur.fetchone()
    if row:
        if name and name != f"Club {tm_id}":
            cur.execute(
                "UPDATE clubs SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (name, row[0]),
            )
        return row[0]
    slug = _unique_slug(cur, "clubs", _slug_base(name))
    cur.execute(
        "INSERT INTO clubs (tm_id, slug, name, crest_url) VALUES (?, ?, ?, ?)",
        (tm_id, slug, name, crest_url),
    )
    return cur.lastrowid
