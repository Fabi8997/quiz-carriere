#!/usr/bin/env python3
"""
Migra i dati da SQLite (dev) a PostgreSQL (Supabase produzione).

USO:
    pip install psycopg2-binary python-dotenv
    python scripts/migrate_sqlite_to_postgres.py

Variabili d'ambiente richieste:
    SQLITE_PATH    — percorso al file .db locale (default: data/tm_data_v2.db)
    DATABASE_URL   — PostgreSQL connection string Supabase
                     (es: postgresql://postgres:[PASSWORD]@db.[PROGETTO].supabase.co:5432/postgres)
"""
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit("❌  psycopg2-binary non installato. Esegui: pip install psycopg2-binary")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / "api" / ".env.production")
except ImportError:
    pass  # python-dotenv opzionale, le env var possono essere già settate

# ── Configurazione ────────────────────────────────────────────────────────────
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", "data/tm_data_v2.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    sys.exit(
        "❌  DATABASE_URL non impostata.\n"
        "    Esportala prima di eseguire lo script:\n"
        "    $env:DATABASE_URL = 'postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres'"
    )

if not SQLITE_PATH.exists():
    sys.exit(f"❌  Database SQLite non trovato: {SQLITE_PATH}")


# ── DDL PostgreSQL ─────────────────────────────────────────────────────────────
DDL = """
CREATE TABLE IF NOT EXISTS countries (
    id      SERIAL PRIMARY KEY,
    tm_id   TEXT,
    name    TEXT NOT NULL,
    flag_url TEXT
);

CREATE TABLE IF NOT EXISTS clubs (
    id                    SERIAL PRIMARY KEY,
    tm_id                 TEXT UNIQUE,
    slug                  TEXT UNIQUE,
    name                  TEXT NOT NULL,
    crest_url             TEXT,
    crest_downloaded_at   TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id                  SERIAL PRIMARY KEY,
    tm_id               TEXT UNIQUE,
    slug                TEXT UNIQUE,
    name                TEXT NOT NULL,
    normalized_name     TEXT,
    birth_date          TEXT,
    birth_place         TEXT,
    height_cm           INTEGER,
    country_id          INTEGER REFERENCES countries(id),
    position_general    TEXT,
    position_detailed   TEXT,
    photo_url           TEXT,
    photo_downloaded_at TEXT
);

CREATE TABLE IF NOT EXISTS careers (
    id           SERIAL PRIMARY KEY,
    player_id    INTEGER NOT NULL REFERENCES players(id),
    club_id      INTEGER NOT NULL REFERENCES clubs(id),
    season       INTEGER NOT NULL,
    appearances  INTEGER DEFAULT 0,
    goals        INTEGER DEFAULT 0,
    assists      INTEGER DEFAULT 0,
    competitions TEXT,
    source_id    INTEGER
);

CREATE TABLE IF NOT EXISTS player_aliases (
    alias     TEXT PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id)
);

-- Tabelle runtime (sessioni di gioco) — schema allineato ai modelli ORM
CREATE TABLE IF NOT EXISTS game_sessions (
    id           SERIAL PRIMARY KEY,
    token        TEXT UNIQUE NOT NULL,
    player_id    INTEGER NOT NULL REFERENCES players(id),
    nickname     TEXT,
    status       TEXT NOT NULL DEFAULT 'playing',
    filters_json TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS game_guesses (
    id                SERIAL PRIMARY KEY,
    session_id        INTEGER NOT NULL REFERENCES game_sessions(id),
    guessed_player_id INTEGER REFERENCES players(id),
    raw_input         TEXT NOT NULL,
    is_correct        BOOLEAN NOT NULL DEFAULT FALSE,
    guessed_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_hints (
    id           SERIAL PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES game_sessions(id),
    hint_type    TEXT NOT NULL,
    unlocked_at  TEXT NOT NULL,
    UNIQUE (session_id, hint_type)
);

CREATE TABLE IF NOT EXISTS challenge_links (
    id               SERIAL PRIMARY KEY,
    token            TEXT UNIQUE NOT NULL,
    creator_nickname TEXT NOT NULL,
    player_id        INTEGER NOT NULL REFERENCES players(id),
    created_at       TEXT NOT NULL
);

-- Indici per query frequenti
CREATE INDEX IF NOT EXISTS idx_careers_player    ON careers(player_id);
CREATE INDEX IF NOT EXISTS idx_careers_club      ON careers(club_id);
CREATE INDEX IF NOT EXISTS idx_careers_season    ON careers(season);
CREATE INDEX IF NOT EXISTS idx_players_position  ON players(position_general);
CREATE INDEX IF NOT EXISTS idx_players_country   ON players(country_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token    ON game_sessions(token);
CREATE INDEX IF NOT EXISTS idx_challenges_token  ON challenges(token);
"""


def connect_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate():
    print(f"📂  SQLite: {SQLITE_PATH}")
    print(f"🐘  PostgreSQL: {DATABASE_URL[:40]}…\n")

    src = connect_sqlite()
    dst = psycopg2.connect(DATABASE_URL)
    dst.autocommit = False
    cur = dst.cursor()

    # ── 1. Crea schema ─────────────────────────────────────────────────────────
    print("🏗   Creo lo schema PostgreSQL…")
    cur.execute(DDL)
    dst.commit()
    print("    ✓ Schema pronto\n")

    # ── 2. Paesi ───────────────────────────────────────────────────────────────
    rows = src.execute("SELECT id, tm_id, name, flag_url FROM countries").fetchall()
    print(f"🌍  Migro {len(rows)} paesi…")
    if rows:
        execute_values(
            cur,
            "INSERT INTO countries (id, tm_id, name, flag_url) VALUES %s ON CONFLICT (id) DO NOTHING",
            [tuple(r) for r in rows],
        )
        # Risincronizza la sequenza SERIAL dopo INSERT con id esplicito
        cur.execute("SELECT setval('countries_id_seq', (SELECT MAX(id) FROM countries))")
    dst.commit()
    print(f"    ✓ {len(rows)} paesi\n")

    # ── 3. Club ────────────────────────────────────────────────────────────────
    rows = src.execute(
        "SELECT id, tm_id, slug, name, crest_url, crest_downloaded_at FROM clubs"
    ).fetchall()
    print(f"🏟   Migro {len(rows)} club…")
    if rows:
        execute_values(
            cur,
            """INSERT INTO clubs (id, tm_id, slug, name, crest_url, crest_downloaded_at)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            [tuple(r) for r in rows],
        )
        cur.execute("SELECT setval('clubs_id_seq', (SELECT MAX(id) FROM clubs))")
    dst.commit()
    print(f"    ✓ {len(rows)} club\n")

    # ── 4. Giocatori ──────────────────────────────────────────────────────────
    rows = src.execute(
        """SELECT id, tm_id, slug, name, normalized_name, birth_date, birth_place,
                  height_cm, country_id, position_general, position_detailed,
                  photo_url, photo_downloaded_at
           FROM players"""
    ).fetchall()
    print(f"⚽  Migro {len(rows)} giocatori…")
    if rows:
        execute_values(
            cur,
            """INSERT INTO players
               (id, tm_id, slug, name, normalized_name, birth_date, birth_place,
                height_cm, country_id, position_general, position_detailed,
                photo_url, photo_downloaded_at)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            [tuple(r) for r in rows],
        )
        cur.execute("SELECT setval('players_id_seq', (SELECT MAX(id) FROM players))")
    dst.commit()
    print(f"    ✓ {len(rows)} giocatori\n")

    # ── 5. Carriere ───────────────────────────────────────────────────────────
    rows = src.execute(
        """SELECT id, player_id, club_id, season, appearances, goals, assists,
                  competitions, source_id
           FROM careers"""
    ).fetchall()
    print(f"📅  Migro {len(rows)} record di carriera…")
    if rows:
        # Batch da 2000 per non saturare la memoria
        batch = 2000
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            execute_values(
                cur,
                """INSERT INTO careers
                   (id, player_id, club_id, season, appearances, goals, assists,
                    competitions, source_id)
                   VALUES %s ON CONFLICT (id) DO NOTHING""",
                [tuple(r) for r in chunk],
            )
            dst.commit()
            print(f"    … {min(i + batch, len(rows))}/{len(rows)}", end="\r")
        cur.execute("SELECT setval('careers_id_seq', (SELECT MAX(id) FROM careers))")
        dst.commit()
    print(f"\n    ✓ {len(rows)} record di carriera\n")

    # ── 6. Alias ──────────────────────────────────────────────────────────────
    rows = src.execute("SELECT alias, player_id FROM player_aliases").fetchall()
    print(f"🏷   Migro {len(rows)} alias…")
    if rows:
        execute_values(
            cur,
            "INSERT INTO player_aliases (alias, player_id) VALUES %s ON CONFLICT (alias) DO NOTHING",
            [tuple(r) for r in rows],
        )
    dst.commit()
    print(f"    ✓ {len(rows)} alias\n")

    src.close()
    cur.close()
    dst.close()

    print("🎉  Migrazione completata!")


if __name__ == "__main__":
    migrate()
