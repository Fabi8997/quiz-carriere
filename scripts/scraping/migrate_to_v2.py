"""
Migra il DB v1 (TM IDs come PK) al nuovo schema v2 (ID interni stabili).

Cosa fa:
  - Costruisce la tabella countries dalle nazionalità presenti in players
  - Assegna AUTOINCREMENT id a players e clubs, conservando tm_id come riferimento
  - Converte height TEXT -> height_cm INTEGER
  - Mappa position_detailed -> position_general (logga i valori non mappati)
  - Genera slug univoci per players e clubs
  - Migra careers usando i nuovi id interni
  - Il DB v1 non viene toccato: output è un nuovo file

USO:
    python migrate_to_v2.py --src data/tm_data_test_40s_6w.db --dst data/tm_data_v2.db
"""

import sqlite3
import re
import argparse
import logging
import sys
from collections import defaultdict

from db_v2 import init_db, normalize_name, _slug_base, _unique_slug, get_tm_source_id

parser = argparse.ArgumentParser(description="Migrazione schema v1 → v2")
parser.add_argument("--src", required=True, help="DB sorgente (v1, non viene modificato)")
parser.add_argument("--dst", required=True, help="DB destinazione (v2, verrà creato)")
args = parser.parse_args()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("migrate")

# Mappa position_detailed (valori TM in italiano) → position_general
# Costruita sui valori più comuni; quelli non presenti vengono loggati a fine migrazione.
POSITION_MAP = {
    # Portieri
    "Portiere": "Portiere",
    # Difensori
    "Difensore centrale": "Difensore",
    "Terzino destro": "Difensore",
    "Terzino sinistro": "Difensore",
    "Libero": "Difensore",
    "Difesa": "Difensore",           # categoria generica TM
    # Centrocampisti
    "Centrocampista": "Centrocampista",
    "Centrocampo": "Centrocampista", # categoria generica TM
    "Mediano": "Centrocampista",
    "Trequartista": "Centrocampista",
    "Ala destra": "Centrocampista",
    "Ala sinistra": "Centrocampista",
    "Esterno di destra": "Centrocampista",
    "Esterno di sinistra": "Centrocampista",
    # Attaccanti
    "Punta centrale": "Attaccante",
    "Seconda punta": "Attaccante",
    "Attacco": "Attaccante",         # categoria generica TM
}


def parse_height_cm(s: str):
    if not s:
        return None
    m = re.search(r"(\d{2,3})\s*cm", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d)[,.](\d{2})\s*m", s, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    return None


def extract_flag_tm_id(flag_url: str):
    if not flag_url:
        return None
    m = re.search(r"/flagge/tiny/(\d+)\.png", flag_url)
    return m.group(1) if m else None


def migrate_countries(v1_cur, v2_conn):
    logger.info("--- Migrazione countries ---")
    v1_cur.execute("""
        SELECT DISTINCT nationality, nationality_flag_url
        FROM players
        WHERE nationality IS NOT NULL
        ORDER BY nationality
    """)
    rows = v1_cur.fetchall()

    v2_cur = v2_conn.cursor()
    name_to_id = {}
    inserted = 0

    for nationality, flag_url in rows:
        if nationality in name_to_id:
            continue
        tm_id = extract_flag_tm_id(flag_url)
        v2_cur.execute(
            "INSERT OR IGNORE INTO countries (name, tm_id, flag_url) VALUES (?, ?, ?)",
            (nationality, tm_id, flag_url),
        )
        v2_cur.execute("SELECT id FROM countries WHERE name = ?", (nationality,))
        name_to_id[nationality] = v2_cur.fetchone()[0]
        inserted += 1

    v2_conn.commit()
    logger.info(f"  {inserted} paesi inseriti")
    return name_to_id


CORRUPT_CLUB_IDS = {
    "0",    # "Le rose più preziose | Transfermarkt" — pagina generica TM, non un club
    "75",   # "Calcio e Mercato | Transfermarkt" — idem
    "123",  # "Calcio e Mercato | Transfermarkt" — idem
    "2077", # "Calcio e Mercato | Transfermarkt" — idem
    "2113", # "Calcio e Mercato | Transfermarkt" — idem
}


def migrate_clubs(v1_cur, v2_conn):
    logger.info("--- Migrazione clubs ---")
    v1_cur.execute("SELECT id, name, crest_url, crest_downloaded_at FROM clubs")
    rows = v1_cur.fetchall()

    v2_cur = v2_conn.cursor()
    tm_to_internal = {}
    skipped = 0

    for tm_id, name, crest_url, crest_downloaded_at in rows:
        if tm_id in CORRUPT_CLUB_IDS:
            logger.warning(f"  Scartato club corrotto: id={tm_id!r}, name={name!r}")
            skipped += 1
            continue
        slug = _unique_slug(v2_cur, "clubs", _slug_base(name))
        v2_cur.execute(
            """INSERT INTO clubs (tm_id, slug, name, crest_url, crest_downloaded_at)
               VALUES (?, ?, ?, ?, ?)""",
            (tm_id, slug, name, crest_url, crest_downloaded_at),
        )
        internal_id = v2_cur.lastrowid
        tm_to_internal[tm_id] = internal_id

    v2_conn.commit()
    logger.info(f"  {len(rows) - skipped} club migrati, {skipped} scartati (corrotti)")
    return tm_to_internal


def migrate_players(v1_cur, v2_conn, country_name_to_id):
    logger.info("--- Migrazione players ---")

    # Controlla quali colonne esistono nel v1 (potrebbero non esserci tutte
    # se lo script scrape_player_profiles non è mai stato eseguito)
    v1_cur.execute("PRAGMA table_info(players)")
    v1_cols = {row[1] for row in v1_cur.fetchall()}

    select_cols = ["id", "name", "normalized_name"]
    optional = [
        "nationality", "nationality_flag_url", "birth_date", "birth_place",
        "height", "position_detailed", "photo_url", "photo_source_ts", "photo_downloaded_at",
    ]
    for col in optional:
        if col in v1_cols:
            select_cols.append(col)

    v1_cur.execute(f"SELECT {', '.join(select_cols)} FROM players")
    rows = v1_cur.fetchall()
    col_idx = {name: i for i, name in enumerate(select_cols)}

    v2_cur = v2_conn.cursor()
    tm_to_internal = {}
    unmapped_positions = defaultdict(int)
    inserted = 0

    for row in rows:
        tm_id = row[col_idx["id"]]
        name = row[col_idx["name"]]

        nationality = row[col_idx["nationality"]] if "nationality" in col_idx else None
        birth_date = row[col_idx["birth_date"]] if "birth_date" in col_idx else None
        birth_place = row[col_idx["birth_place"]] if "birth_place" in col_idx else None
        height_raw = row[col_idx["height"]] if "height" in col_idx else None
        position_detailed = row[col_idx["position_detailed"]] if "position_detailed" in col_idx else None
        photo_url = row[col_idx["photo_url"]] if "photo_url" in col_idx else None
        photo_source_ts = row[col_idx["photo_source_ts"]] if "photo_source_ts" in col_idx else None
        photo_downloaded_at = row[col_idx["photo_downloaded_at"]] if "photo_downloaded_at" in col_idx else None

        height_cm = parse_height_cm(height_raw)
        country_id = country_name_to_id.get(nationality) if nationality else None
        position_general = POSITION_MAP.get(position_detailed) if position_detailed else None
        if position_detailed and not position_general:
            unmapped_positions[position_detailed] += 1

        slug = _unique_slug(v2_cur, "players", _slug_base(name))

        v2_cur.execute(
            """INSERT INTO players
               (tm_id, slug, name, normalized_name, birth_date, birth_place,
                height_cm, country_id, position_general, position_detailed,
                photo_url, photo_source_ts, photo_downloaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tm_id, slug, name, normalize_name(name), birth_date, birth_place,
             height_cm, country_id, position_general, position_detailed,
             photo_url, photo_source_ts, photo_downloaded_at),
        )
        tm_to_internal[tm_id] = v2_cur.lastrowid
        inserted += 1

        if inserted % 1000 == 0:
            v2_conn.commit()
            logger.info(f"  ...{inserted} giocatori migrati")

    v2_conn.commit()
    logger.info(f"  {inserted} giocatori migrati totali")

    if unmapped_positions:
        logger.warning(f"\n  ⚠️  POSIZIONI NON MAPPATE (aggiungerle a POSITION_MAP in migrate_to_v2.py):")
        for pos, count in sorted(unmapped_positions.items(), key=lambda x: -x[1]):
            logger.warning(f"    '{pos}': {count} giocatori → da mappare manualmente")

    return tm_to_internal


# Alias giocatori: chiave = alias ricercabile, valore = tm_id del giocatore.
# Aggiungi qui nuovi alias man mano che servono.
# Due Ronaldo nel DB (id=3140 il brasiliano, id=146660 altro): "ronaldo" punta al Fenomeno.
PLAYER_ALIASES = {
    # Cristiano Ronaldo
    "cr7":              "8198",
    "cristiano":        "8198",
    # Zlatan Ibrahimović
    "ibra":             "3455",
    "zlatan":           "3455",
    # Ronaldo Il Fenomeno
    "il fenomeno":      "3140",
    "o fenomeno":       "3140",
    "ronaldo il fenomeno": "3140",
    # Ronaldinho
    "ronaldinho":       "3373",
    "dinho":            "3373",
    # Adriano L'Imperatore
    "adriano":          "5876",
    "l imperatore":     "5876",
    "imperatore":       "5876",
    # Italiani
    "totti":            "5958",
    "del piero":        "4289",
    "pinturicchio":     "4289",
    "pirlo":            "5817",
    "buffon":           "5023",
    "gigi":             "5023",
    "baggio":           "4153",
    "il divin codino":  "4153",
    "maldini":          "5803",
    "inzaghi":          "5821",
    "pippo":            "5821",
    "nesta":            "4171",
    "cannavaro":        "5775",
    "luca toni":        "5980",
    # Olandesi
    "van basten":       "74471",
    "gullit":           "101045",
    # Eto'o
    "etoo":             "4257",
}


def migrate_aliases(v2_conn, player_tm_to_id):
    logger.info("--- Migrazione aliases ---")
    v2_cur = v2_conn.cursor()
    inserted = 0
    skipped = 0
    for alias, tm_id in PLAYER_ALIASES.items():
        player_id = player_tm_to_id.get(tm_id)
        if not player_id:
            logger.warning(f"  Alias '{alias}' → tm_id={tm_id} non trovato nel DB, saltato")
            skipped += 1
            continue
        v2_cur.execute(
            "INSERT OR IGNORE INTO player_aliases (alias, player_id) VALUES (?, ?)",
            (alias, player_id),
        )
        inserted += 1
    v2_conn.commit()
    logger.info(f"  {inserted} alias inseriti, {skipped} saltati")


def migrate_careers(v1_cur, v2_conn, player_tm_to_id, club_tm_to_id):
    logger.info("--- Migrazione careers ---")
    v1_cur.execute("""
        SELECT player_id, club_id, season, appearances, goals, assists, competitions
        FROM careers
    """)
    rows = v1_cur.fetchall()

    v2_cur = v2_conn.cursor()
    source_id = get_tm_source_id(v2_conn)

    inserted = 0
    skipped = 0

    for tm_player_id, tm_club_id, season, apps, goals, assists, comps in rows:
        player_id = player_tm_to_id.get(tm_player_id)
        club_id = club_tm_to_id.get(tm_club_id)

        if not player_id or not club_id:
            skipped += 1
            continue

        v2_cur.execute(
            """INSERT OR IGNORE INTO careers
               (player_id, club_id, season, appearances, goals, assists, competitions, source_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (player_id, club_id, season, apps, goals, assists, comps, source_id),
        )
        inserted += 1

        if inserted % 5000 == 0:
            v2_conn.commit()
            logger.info(f"  ...{inserted} carriere migrate")

    v2_conn.commit()
    logger.info(f"  {inserted} righe carriera migrate, {skipped} saltate (player/club non trovati)")


def main():
    logger.info(f"Migrazione: {args.src} -> {args.dst}")

    v1_conn = sqlite3.connect(args.src)
    v1_cur = v1_conn.cursor()

    v2_conn = init_db(args.dst)

    country_name_to_id = migrate_countries(v1_cur, v2_conn)
    club_tm_to_id = migrate_clubs(v1_cur, v2_conn)
    player_tm_to_id = migrate_players(v1_cur, v2_conn, country_name_to_id)
    migrate_careers(v1_cur, v2_conn, player_tm_to_id, club_tm_to_id)
    migrate_aliases(v2_conn, player_tm_to_id)

    # Riepilogo finale
    v2_cur = v2_conn.cursor()
    logger.info("\n=== RIEPILOGO MIGRAZIONE ===")
    for table in ("countries", "players", "clubs", "careers", "player_aliases"):
        v2_cur.execute(f"SELECT COUNT(*) FROM {table}")
        logger.info(f"  {table}: {v2_cur.fetchone()[0]} righe")

    v1_conn.close()
    v2_conn.close()
    logger.info(f"\nDB v2 scritto in: {args.dst}")
    logger.info("Il DB v1 originale non è stato modificato.")


if __name__ == "__main__":
    main()
