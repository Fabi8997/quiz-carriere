"""
Pulizia dati sul DB v2. Da lanciare dopo migrate_to_v2.py.

Operazioni:
  - Normalizza birth_date da DD/MM/YYYY a YYYY-MM-DD (ISO 8601)

USO:
    python clean_v2.py --db data/tm_data_v2.db
"""

import sqlite3
import re
import argparse
import logging
import sys

parser = argparse.ArgumentParser(description="Pulizia dati DB v2")
parser.add_argument("--db", required=True)
args = parser.parse_args()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("clean_v2")


def normalize_birth_dates(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, birth_date FROM players WHERE birth_date IS NOT NULL")
    rows = cur.fetchall()

    converted, skipped, errors = 0, 0, 0

    for player_id, raw in rows:
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", raw.strip())
        if not m:
            # Già in altro formato o non riconosciuto
            skipped += 1
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw.strip()):
                logger.warning(f"  Formato non riconosciuto per id={player_id}: {raw!r}")
                errors += 1
            continue

        day, month, year = m.groups()
        iso = f"{year}-{month}-{day}"
        cur.execute(
            "UPDATE players SET birth_date = ? WHERE id = ?",
            (iso, player_id),
        )
        converted += 1

    conn.commit()
    logger.info(f"  birth_date: {converted} convertite a ISO, {skipped} gia' nel formato corretto, {errors} non riconosciute")


def nullify_invalid_dates(conn):
    """TM usa 'd.n.d.(NN)' per date sconosciute con eta' stimata — non e' una data."""
    cur = conn.cursor()
    cur.execute("UPDATE players SET birth_date = NULL WHERE birth_date LIKE 'd.n.d.%'")
    n = cur.rowcount
    conn.commit()
    if n:
        logger.info(f"  {n} birth_date 'd.n.d.' -> NULL")


def main():
    conn = sqlite3.connect(args.db)

    logger.info("--- Pulizia birth_date non valide (d.n.d.) ---")
    nullify_invalid_dates(conn)

    logger.info("--- Normalizzazione birth_date (DD/MM/YYYY -> YYYY-MM-DD) ---")
    normalize_birth_dates(conn)

    # Verifica finale
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM players WHERE birth_date IS NOT NULL AND birth_date NOT LIKE '____-__-__%'")
    remaining = cur.fetchone()[0]
    if remaining:
        logger.warning(f"  {remaining} date ancora in formato non ISO - controllare manualmente")
    else:
        logger.info("  Verifica OK: tutte le date sono in formato ISO 8601")

    conn.close()


if __name__ == "__main__":
    main()
