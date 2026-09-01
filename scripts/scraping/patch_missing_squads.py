"""
Recupera le rose mancanti a causa di errori 502 durante lo scraping principale,
e aggiunge alla carriera i giocatori nuovi (mai visti in nessun'altra stagione/squadra).

USO:
    python patch_missing_squads.py --db tm_data_test_40s_6w.db
"""

import sqlite3
import time
import random
import re
import argparse
import logging
import sys
from collections import defaultdict

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.transfermarkt.it"
API_BASE = "https://tmapi.transfermarkt.technology"
CREST_URL_PATTERN = "https://img.a.transfermarkt.technology/wappen/homepageWappen150x150/{club_id}.png?lm=4711"

# Le squadre/stagioni note per essere fallite con 502 nel run principale.
# Se ne trovi altre nel tuo log, aggiungile qui come (slug, nome_visualizzato, stagione).
MISSING_SQUADS = [
    ("acn-siena-1904", "AC Siena", 2004),
    ("acr-messina", "FC Messina Peloro", 2004),
]

parser = argparse.ArgumentParser(description="Patch rose mancanti")
parser.add_argument("--db", type=str, required=True, help="Database su cui lavorare")
args = parser.parse_args()

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}
API_HEADERS = {
    "accept": "application/json",
    "accept-language": "it-IT,it;q=0.9,en;q=0.8",
    "origin": "https://www.transfermarkt.it",
    "referer": "https://www.transfermarkt.it/",
    "user-agent": WEB_HEADERS["User-Agent"],
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("patch")


def new_session():
    return cf_requests.Session(impersonate="chrome124")


def retry_get(session, url, headers, max_retries=5, base_delay=5):
    """Più paziente dello script principale: qui parliamo di poche richieste mirate,
    possiamo permetterci di insistere di più."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, headers=headers, timeout=25)
            if resp.status_code == 200:
                return resp
            logger.warning(f"  Tentativo {attempt}/{max_retries}: status {resp.status_code}, riprovo tra {base_delay*attempt}s...")
        except Exception as e:
            logger.warning(f"  Tentativo {attempt}/{max_retries}: {type(e).__name__}: {e}, riprovo tra {base_delay*attempt}s...")
        time.sleep(base_delay * attempt)
    return None


def normalize_name(name: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", name)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", only_ascii.lower())


def find_team_id(session, season, target_slug):
    """Ricava il team_id numerico cercando nella pagina Serie A di quella stagione."""
    url = f"{BASE_URL}/serie-a/startseite/wettbewerb/IT1/plus/?saison_id={season}"
    resp = retry_get(session, url, WEB_HEADERS)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "lxml")
    for a in soup.select("a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"/([a-z0-9\-]+)/startseite/verein/(\d+)", href)
        if m and m.group(1) == target_slug:
            return m.group(2)
    return None


def get_team_squad(session, team_id, slug, season):
    url = f"{BASE_URL}/{slug}/kader/verein/{team_id}/saison_id/{season}"
    resp = retry_get(session, url, WEB_HEADERS)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    players, seen = [], set()
    for a in soup.select("a[href*='/profil/spieler/']"):
        href = a.get("href", "")
        m = re.search(r"/([a-z0-9\-]+)/profil/spieler/(\d+)", href)
        if m:
            p_slug, p_id = m.groups()
            name = a.get_text(strip=True)
            if name and p_id not in seen:
                seen.add(p_id)
                players.append((p_id, name, p_slug))
    return players


def get_player_performance(session, player_id):
    url = f"{API_BASE}/player/{player_id}/performance-game"
    resp = retry_get(session, url, API_HEADERS)
    if not resp:
        return None
    try:
        return resp.json().get("data")
    except Exception:
        return None


def aggregate_career(perf_data):
    agg = defaultdict(lambda: {"appearances": 0, "goals": 0, "assists": 0, "competitions": set()})
    for p in perf_data.get("performance", []):
        gs = p["statistics"]["generalStatistics"]
        if gs["participationState"] != "played":
            continue
        club_id = str(gs["primaryClubId"])
        season = p["gameInformation"]["seasonId"]
        comp = p["gameInformation"]["competitionId"]
        key = (club_id, season)
        goals = p["statistics"]["goalStatistics"]["goalsScoredTotal"] or 0
        assists = p["statistics"]["goalStatistics"]["assists"] or 0
        agg[key]["appearances"] += 1
        agg[key]["goals"] += goals
        agg[key]["assists"] += assists
        agg[key]["competitions"].add(comp)
    return agg


def resolve_club_name(session, club_id, cache):
    if club_id in cache:
        return cache[club_id]
    url = f"{BASE_URL}/-/startseite/verein/{club_id}"
    try:
        resp = session.get(url, headers=WEB_HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            title = soup.find("title")
            name = title.get_text(strip=True).split(" - ")[0] if title else f"Club {club_id}"
        else:
            name = f"Club {club_id}"
    except Exception:
        name = f"Club {club_id}"
    cache[club_id] = name
    return name


def main():
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # Pre-carica cache nomi club esistenti (evita richieste inutili)
    cur.execute("SELECT id, name FROM clubs")
    club_name_cache = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("SELECT id FROM players")
    existing_player_ids = {row[0] for row in cur.fetchall()}
    logger.info(f"Giocatori già presenti nel DB: {len(existing_player_ids)}")
    logger.info(f"Club già noti in cache: {len(club_name_cache)}")

    session = new_session()

    for slug, display_name, season in MISSING_SQUADS:
        logger.info(f"\n--- Recupero {display_name} {season}/{season+1} (slug: {slug}) ---")

        team_id = find_team_id(session, season, slug)
        if not team_id:
            logger.error(f"  Non sono riuscito a trovare il team_id per {slug} stagione {season}. Salto.")
            continue
        logger.info(f"  team_id trovato: {team_id}")

        players = get_team_squad(session, team_id, slug, season)
        if not players:
            logger.error(f"  Rosa vuota anche al secondo tentativo per {display_name}. "
                          f"Il sito potrebbe avere ancora problemi, riprova più tardi.")
            continue
        logger.info(f"  Rosa recuperata: {len(players)} giocatori")

        new_players = [(p_id, p_name) for p_id, p_name, _ in players if p_id not in existing_player_ids]
        logger.info(f"  Di cui NUOVI (mai visti in altre stagioni): {len(new_players)}")

        if not new_players:
            logger.info("  Nessun giocatore nuovo da aggiungere, la rosa era già coperta da altre stagioni.")
            continue

        for i, (p_id, p_name) in enumerate(new_players, 1):
            logger.info(f"  [{i}/{len(new_players)}] Recupero carriera di {p_name} ({p_id})...")
            perf_data = get_player_performance(session, p_id)
            if not perf_data:
                logger.warning(f"    Fallito recupero carriera per {p_name}, salto.")
                continue

            agg = aggregate_career(perf_data)
            cur.execute("INSERT OR IGNORE INTO players VALUES (?, ?, ?)",
                        (p_id, p_name, normalize_name(p_name)))
            existing_player_ids.add(p_id)

            for (club_id, c_season), stats in agg.items():
                c_name = resolve_club_name(session, club_id, club_name_cache)
                crest_url = CREST_URL_PATTERN.format(club_id=club_id)
                cur.execute("INSERT OR IGNORE INTO clubs VALUES (?, ?, ?)", (club_id, c_name, crest_url))
                cur.execute(
                    """INSERT OR REPLACE INTO careers
                       (player_id, club_id, season, appearances, goals, assists, competitions)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (p_id, club_id, c_season, stats["appearances"], stats["goals"],
                     stats["assists"], ",".join(sorted(stats["competitions"]))))
            conn.commit()
            time.sleep(random.uniform(1.0, 2.0))

    logger.info("\n=== COMPLETATO ===")
    cur.execute("SELECT COUNT(*) FROM players")
    logger.info(f"Totale giocatori nel DB ora: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM careers")
    logger.info(f"Totale righe carriera nel DB ora: {cur.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
