"""
Arricchisce TUTTI i giocatori del DB con nazionalità, posizione, data nascita,
foto, bandiera - leggendo la pagina profilo (slug derivato dal nome + retry
su 403, dato che i primi test mostrano un pattern di "riscaldamento" iniziale
seguito da run puliti).

Resumable: processa solo i giocatori che non hanno ancora questi dati (colonna
'nationality' NULL), quindi puoi interromperlo e rilanciarlo senza perdere lavoro.

USO:
    python scrape_player_profiles.py --db tm_data_test_40s_6w.db
"""

import sqlite3
import time
import random
import re
import argparse
import logging
import sys
import unicodedata

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.transfermarkt.it"

parser = argparse.ArgumentParser(description="Arricchimento profili giocatori")
parser.add_argument("--db", type=str, required=True)
parser.add_argument("--delay-min", type=float, default=1.0)
parser.add_argument("--delay-max", type=float, default=2.5)
parser.add_argument("--session-refresh-every", type=int, default=25)
parser.add_argument("--max-retries", type=int, default=3)
parser.add_argument("--progress-every", type=int, default=50)
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
        logging.FileHandler(args.db.replace(".db", "_profiles.log"), mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger("profiles")


def new_session():
    return cf_requests.Session(impersonate="chrome124")


def generate_slug(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = only_ascii.lower()
    slug = re.sub(r"[^a-z0-9\s\-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug or "player"


def parse_profile(html):
    soup = BeautifulSoup(html, "lxml")
    header = soup.find("header", class_="data-header")
    if not header:
        return None

    data = {}

    birth_date_el = soup.find(attrs={"itemprop": "birthDate"})
    data["birth_date"] = birth_date_el.get_text(strip=True).split(" (")[0].strip() if birth_date_el else None

    birth_place_el = soup.find(attrs={"itemprop": "birthPlace"})
    data["birth_place"] = birth_place_el.get_text(strip=True) if birth_place_el else None

    nationality_el = soup.find(attrs={"itemprop": "nationality"})
    data["nationality"] = nationality_el.get_text(strip=True) if nationality_el else None

    height_el = soup.find(attrs={"itemprop": "height"})
    data["height"] = height_el.get_text(strip=True) if height_el else None

    data["position_detailed"] = None
    for li in soup.find_all("li", class_="data-header__label"):
        if "Posizione" in li.get_text():
            content = li.find("span", class_="data-header__content")
            if content:
                data["position_detailed"] = content.get_text(strip=True)
            break

    photo_el = soup.find("img", class_="data-header__profile-image")
    data["photo_url"] = photo_el.get("src") if photo_el else None

    data["flag_url"] = None
    if nationality_el:
        flag_container = nationality_el.find_parent("span") or nationality_el
        flag_img = flag_container.find("img") if flag_container else None
        if not flag_img:
            parent_li = nationality_el.find_parent("li")
            if parent_li:
                flag_img = parent_li.find("img", src=re.compile("flagge"))
        if flag_img:
            data["flag_url"] = flag_img.get("src")

    return data


def fetch_profile(session, player_id, player_name):
    slug = generate_slug(player_name)
    url = f"{BASE_URL}/{slug}/profil/spieler/{player_id}"

    for attempt in range(1, args.max_retries + 1):
        try:
            resp = session.get(url, headers=WEB_HEADERS, timeout=20)
        except Exception as e:
            if attempt < args.max_retries:
                time.sleep(5 * attempt)
                continue
            return None, f"exception: {e}"

        if resp.status_code == 200:
            data = parse_profile(resp.text)
            if data is None:
                return None, "pagina non riconosciuta"
            return data, 200

        if resp.status_code == 403 and attempt < args.max_retries:
            backoff = 8 * attempt
            logger.debug(f"    403 per {player_name}, retry {attempt}/{args.max_retries} tra {backoff}s")
            time.sleep(backoff)
            continue

        return None, resp.status_code

    return None, "max_retries_exceeded"


def init_columns(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(players)")
    existing_cols = {row[1] for row in cur.fetchall()}
    new_cols = {
        "nationality": "TEXT", "nationality_flag_url": "TEXT",
        "birth_date": "TEXT", "birth_place": "TEXT", "height": "TEXT",
        "position_detailed": "TEXT", "photo_url": "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE players ADD COLUMN {col} {col_type}")
            logger.info(f"Aggiunta colonna players.{col}")
    conn.commit()


def format_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def main():
    conn = sqlite3.connect(args.db)
    init_columns(conn)
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM players WHERE nationality IS NULL")
    todo = cur.fetchall()
    logger.info(f"Giocatori da arricchire: {len(todo)} (quelli già fatti vengono saltati)")

    if not todo:
        logger.info("Niente da fare, tutti i giocatori hanno già i dati anagrafici.")
        return

    session = new_session()
    ok, failed = 0, 0
    fail_reasons = {}
    t_start = time.time()

    for i, (p_id, p_name) in enumerate(todo, 1):
        if i % args.session_refresh_every == 0:
            session = new_session()

        data, status = fetch_profile(session, p_id, p_name)

        if data:
            cur.execute("""
                UPDATE players SET nationality=?, nationality_flag_url=?, birth_date=?,
                birth_place=?, height=?, position_detailed=?, photo_url=?
                WHERE id=?
            """, (data["nationality"], data["flag_url"], data["birth_date"],
                  data["birth_place"], data["height"], data["position_detailed"],
                  data["photo_url"], p_id))
            conn.commit()
            ok += 1
        else:
            failed += 1
            fail_reasons[str(status)] = fail_reasons.get(str(status), 0) + 1
            logger.warning(f"[{i}/{len(todo)}] FALLITO {p_name} ({p_id}): {status}")

        if i % args.progress_every == 0 or i == len(todo):
            elapsed = time.time() - t_start
            rate = i / elapsed
            eta = (len(todo) - i) / rate if rate > 0 else 0
            logger.info(f"  >>> CHECKPOINT: {i}/{len(todo)} — {ok} ok, {failed} falliti — "
                        f"ETA {format_duration(eta)}")

        time.sleep(random.uniform(args.delay_min, args.delay_max))

    total_elapsed = time.time() - t_start
    logger.info("\n=== RIEPILOGO FINALE ===")
    logger.info(f"Riusciti: {ok}/{len(todo)}")
    logger.info(f"Falliti: {failed}/{len(todo)}")
    logger.info(f"Motivi fallimento: {fail_reasons}")
    logger.info(f"Tempo totale: {format_duration(total_elapsed)}")
    logger.info("Rilancia lo stesso comando per ritentare solo i falliti "
                "(vengono riconosciuti perché nationality resta NULL).")
    conn.close()


if __name__ == "__main__":
    main()
