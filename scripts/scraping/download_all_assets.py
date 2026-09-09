"""
Scarica in locale TUTTE le immagini (stemmi club, foto giocatori, bandiere),
con nomi file stabili (non cambiano mai, anche se il contenuto viene
aggiornato) e gestione intelligente degli aggiornamenti per le foto giocatori
(basata sul timestamp incluso nell'URL Transfermarkt).

Pensato per essere rilanciato periodicamente: al secondo run e successivi,
scarica solo cosa è nuovo o cambiato, non ripete tutto da capo.

USO:
    python download_all_assets.py --db ../../data/tm_data_test_40s_6w.db --out ../../data/assets
"""

import sqlite3
import time
import random
import re
import os
import argparse
import logging
import sys
from datetime import datetime, timezone

from curl_cffi import requests as cf_requests

from db_v2 import init_db

parser = argparse.ArgumentParser(description="Download unificato assets (stemmi/foto/bandiere)")
parser.add_argument("--db", type=str, required=True)
parser.add_argument("--out", type=str, default="assets", help="Cartella di output")
parser.add_argument("--delay-min", type=float, default=0.2)
parser.add_argument("--delay-max", type=float, default=0.6)
args = parser.parse_args()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("download_assets.log", mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("download_assets")


def new_session():
    return cf_requests.Session(impersonate="chrome124")


def extract_photo_timestamp(photo_url: str):
    """Estrae il timestamp dall'URL foto TM: .../96828-1596184084.jpg -> 1596184084"""
    if not photo_url:
        return None
    m = re.search(r"-(\d+)\.jpg", photo_url)
    return int(m.group(1)) if m else None


def extract_country_id(flag_url: str):
    """Estrae l'id paese dall'URL bandiera: .../flagge/tiny/75.png -> 75"""
    if not flag_url:
        return None
    m = re.search(r"/(\d+)\.png", flag_url)
    return m.group(1) if m else None



def download_file(session, url, out_path):
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return True
        return False
    except Exception as e:
        logger.warning(f"    Errore download {url}: {e}")
        return False


def main():
    photos_dir = os.path.join(args.out, "photos")
    crests_dir = os.path.join(args.out, "crests")
    flags_dir = os.path.join(args.out, "flags")
    for d in (photos_dir, crests_dir, flags_dir):
        os.makedirs(d, exist_ok=True)

    conn = init_db(args.db)
    cur = conn.cursor()
    session = new_session()
    now_iso = datetime.now(timezone.utc).isoformat()

    # --- STEMMI: scarica solo se il file locale non esiste già ---
    logger.info("--- Stemmi club ---")
    cur.execute("SELECT id, crest_url, crest_downloaded_at FROM clubs WHERE crest_url IS NOT NULL")
    clubs = cur.fetchall()
    crest_ok, crest_skip, crest_fail = 0, 0, 0
    for internal_id, crest_url, downloaded_at in clubs:
        out_path = os.path.join(crests_dir, f"{internal_id}.png")  # usa id interno, non tm_id
        if os.path.exists(out_path) and downloaded_at:
            crest_skip += 1
            continue
        if download_file(session, crest_url, out_path):
            cur.execute("UPDATE clubs SET crest_downloaded_at = ? WHERE id = ?", (now_iso, internal_id))
            crest_ok += 1
        else:
            crest_fail += 1
        if (crest_ok + crest_fail) % 200 == 0:
            conn.commit()
            logger.info(f"  ...{crest_ok} scaricati, {crest_skip} saltati, {crest_fail} falliti")
        time.sleep(random.uniform(args.delay_min, args.delay_max))
    conn.commit()
    logger.info(f"Stemmi: {crest_ok} scaricati, {crest_skip} già presenti, {crest_fail} falliti")

    # --- BANDIERE: dedup per country_id (tante nazionalità condividono la stessa) ---
    logger.info("--- Bandiere ---")
    cur.execute("SELECT DISTINCT nationality_flag_url FROM players WHERE nationality_flag_url IS NOT NULL")
    flag_urls = [row[0] for row in cur.fetchall()]
    flag_ok, flag_skip, flag_fail = 0, 0, 0
    for flag_url in flag_urls:
        country_id = extract_country_id(flag_url)
        if not country_id:
            continue
        out_path = os.path.join(flags_dir, f"{country_id}.png")  # nome file STABILE
        if os.path.exists(out_path):
            flag_skip += 1
            continue
        if download_file(session, flag_url, out_path):
            flag_ok += 1
        else:
            flag_fail += 1
        time.sleep(random.uniform(args.delay_min, args.delay_max))
    logger.info(f"Bandiere: {flag_ok} scaricate, {flag_skip} già presenti, {flag_fail} fallite "
                f"({len(flag_urls)} nazionalità uniche totali)")

    # --- FOTO GIOCATORI: scarica solo se nuove o il timestamp è cambiato ---
    logger.info("--- Foto giocatori ---")
    cur.execute("SELECT id, photo_url, photo_source_ts FROM players WHERE photo_url IS NOT NULL")
    players = cur.fetchall()
    photo_ok, photo_skip, photo_fail = 0, 0, 0
    for i, (internal_id, photo_url, saved_ts) in enumerate(players, 1):
        current_ts = extract_photo_timestamp(photo_url)
        out_path = os.path.join(photos_dir, f"{internal_id}.jpg")  # usa id interno, non tm_id

        needs_download = (
            not os.path.exists(out_path)
            or saved_ts is None
            or current_ts != saved_ts
        )
        if not needs_download:
            photo_skip += 1
            continue

        if download_file(session, photo_url, out_path):
            cur.execute(
                "UPDATE players SET photo_source_ts = ?, photo_downloaded_at = ? WHERE id = ?",
                (current_ts, now_iso, internal_id)
            )
            photo_ok += 1
        else:
            photo_fail += 1

        if i % 300 == 0:
            conn.commit()
            logger.info(f"  [{i}/{len(players)}] {photo_ok} scaricate, {photo_skip} saltate, {photo_fail} fallite")

        time.sleep(random.uniform(args.delay_min, args.delay_max))
    conn.commit()
    logger.info(f"Foto: {photo_ok} scaricate, {photo_skip} già aggiornate, {photo_fail} fallite")

    logger.info("\n=== RIEPILOGO FINALE ===")
    logger.info(f"Stemmi:   {crest_ok} nuovi, {crest_skip} saltati, {crest_fail} falliti")
    logger.info(f"Bandiere: {flag_ok} nuove, {flag_skip} saltate, {flag_fail} fallite")
    logger.info(f"Foto:     {photo_ok} nuove/aggiornate, {photo_skip} saltate, {photo_fail} fallite")
    logger.info(f"File salvati in: {os.path.abspath(args.out)}")
    logger.info("Rilancia periodicamente questo script: la seconda volta in poi")
    logger.info("scaricherà solo cosa è nuovo o cambiato, non ripete tutto.")

    conn.close()


if __name__ == "__main__":
    main()
