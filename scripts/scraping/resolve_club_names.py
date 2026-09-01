"""
Risolve i nomi dei club mancanti nel DB (quelli salvati come placeholder "Club {id}").
Da lanciare DOPO lo scraping principale, come processo separato.

Strategia anti-blocco:
- Sequenziale, un thread solo (niente parallelismo che triggera Cloudflare)
- Delay alto e variabile tra le richieste (3-6s)
- Retry con backoff se riceve 403 (aspetta di più e riprova, max 2 tentativi)
- Sessione nuova ogni tot richieste (a volte aiuta a "resettare" il fingerprint)

USO:
    python resolve_club_names.py --db tm_data_test_2s_6w.db
    python resolve_club_names.py --db tm_data_v3.db --delay-min 4 --delay-max 8
"""

import sqlite3
import time
import random
import re
import argparse
import logging
import sys
from datetime import datetime

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.transfermarkt.it"

parser = argparse.ArgumentParser(description="Risoluzione nomi club mancanti")
parser.add_argument("--db", type=str, required=True, help="File database su cui lavorare")
parser.add_argument("--delay-min", type=float, default=3.0, help="Delay minimo tra richieste (s)")
parser.add_argument("--delay-max", type=float, default=6.0, help="Delay massimo tra richieste (s)")
parser.add_argument("--session-refresh-every", type=int, default=20,
                     help="Ogni quante richieste creare una nuova sessione (default: 20)")
parser.add_argument("--max-retries", type=int, default=2, help="Tentativi extra se riceve 403")
args = parser.parse_args()

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(args.db.replace(".db", "_clubnames.log"), mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("resolve_clubs")


def new_session():
    return cf_requests.Session(impersonate="chrome124")


def resolve_one(session, club_id, attempt=0):
    url = f"{BASE_URL}/-/startseite/verein/{club_id}"
    try:
        resp = session.get(url, headers=WEB_HEADERS, timeout=15)
    except Exception as e:
        logger.warning(f"  Eccezione per club {club_id}: {e}")
        return None, "exception"

    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.find("title")
        name = title.get_text(strip=True).split(" - ")[0] if title else None
        return name, 200

    if resp.status_code == 403 and attempt < args.max_retries:
        backoff = 15 * (attempt + 1)
        logger.warning(f"  403 per club {club_id}, aspetto {backoff}s e riprovo "
                        f"(tentativo {attempt+1}/{args.max_retries})...")
        time.sleep(backoff)
        return resolve_one(session, club_id, attempt + 1)

    return None, resp.status_code


def main():
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # Trova i club con nome placeholder (quelli non risolti dal run principale)
    # NOTA: usiamo un confronto ESATTO (name = 'Club ' || id), non LIKE 'Club %',
    # perché molti club veri (sudamericani/messicani) si chiamano legittimamente
    # "Club Nacional", "Club Atlético X", ecc. — LIKE 'Club %' li ributta dentro
    # come falsi positivi ad ogni run successivo.
    cur.execute("SELECT id, name FROM clubs WHERE name = 'Club ' || id")
    missing = cur.fetchall()
    logger.info(f"Club da risolvere: {len(missing)}")

    if not missing:
        logger.info("Niente da fare, tutti i club hanno già un nome.")
        return

    session = new_session()
    resolved = 0
    still_failed = 0
    t_start = time.time()

    for i, (club_id, old_name) in enumerate(missing, 1):
        if i % args.session_refresh_every == 0:
            session = new_session()
            logger.info(f"  [sessione rinnovata dopo {i} richieste]")

        name, status = resolve_one(session, club_id)

        if name:
            cur.execute("UPDATE clubs SET name = ? WHERE id = ?", (name, club_id))
            conn.commit()
            resolved += 1
            logger.info(f"[{i}/{len(missing)}] OK club {club_id} -> '{name}'")
        else:
            still_failed += 1
            logger.warning(f"[{i}/{len(missing)}] FALLITO club {club_id} (status {status}), resta placeholder")

        if i % 10 == 0:
            elapsed = time.time() - t_start
            rate = i / elapsed
            eta = (len(missing) - i) / rate if rate > 0 else 0
            logger.info(f"  >>> Checkpoint: {i}/{len(missing)} — "
                        f"{resolved} risolti, {still_failed} falliti — ETA {eta/60:.1f} min")

        time.sleep(random.uniform(args.delay_min, args.delay_max))

    total_elapsed = time.time() - t_start
    logger.info("=== RIEPILOGO ===")
    logger.info(f"Risolti: {resolved}/{len(missing)}")
    logger.info(f"Ancora falliti: {still_failed}/{len(missing)}")
    logger.info(f"Tempo totale: {total_elapsed/60:.1f} minuti")
    conn.close()


if __name__ == "__main__":
    main()
