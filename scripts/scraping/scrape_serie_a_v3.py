"""
Scraping Transfermarkt v3 - Serie A, ultime N stagioni.
Con logging dettagliato (console + file) e parametri da linea di comando.

USO:
    python scrape_serie_a_v3.py --seasons 2 --workers 6
    python scrape_serie_a_v3.py --seasons 10 --workers 6   (run completo)
"""

import sqlite3
import time
import random
import re
import threading
import sys
import argparse
import logging
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.transfermarkt.it"
API_BASE = "https://tmapi.transfermarkt.technology"

LEAGUES = {
    "serie-a": {"slug": "serie-a", "id": "IT1", "label": "Serie A"},
    "premier-league": {"slug": "premier-league", "id": "GB1", "label": "Premier League"},
    "la-liga": {"slug": "laliga", "id": "ES1", "label": "La Liga"},
    "bundesliga": {"slug": "bundesliga", "id": "L1", "label": "Bundesliga"},
    "ligue-1": {"slug": "ligue-1", "id": "FR1", "label": "Ligue 1"},
}

ALL_SEASONS = list(range(1986, 2026))  # 40 stagioni: 1986/87 -> 2025/26
CREST_URL_PATTERN = "https://img.a.transfermarkt.technology/wappen/homepageWappen150x150/{club_id}.png?lm=4711"

# --- Parametri da linea di comando ---
parser = argparse.ArgumentParser(description="Scraping Transfermarkt")
parser.add_argument("--league", type=str, default="serie-a", choices=list(LEAGUES.keys()),
                     help="Quale campionato scrapare (default: serie-a)")
parser.add_argument("--seasons", type=int, default=10,
                     help="Quante stagioni testare, dalla più recente (default: 10 = tutte)")
parser.add_argument("--workers", type=int, default=6,
                     help="Richieste API parallele (default: 6)")
parser.add_argument("--db", type=str, default=None,
                     help="Nome file database (default: automatico). USA LO STESSO FILE tra leghe "
                          "diverse per riusare club/giocatori già trovati!")
parser.add_argument("--verbose", action="store_true",
                     help="Log dettagliatissimo: ogni singola richiesta HTTP/API")
parser.add_argument("--progress-every", type=int, default=20,
                     help="Ogni quanti giocatori completati stampare un checkpoint in fase 3 (default: 20)")
args = parser.parse_args()

LEAGUE_SLUG = LEAGUES[args.league]["slug"]
COMPETITION_ID = LEAGUES[args.league]["id"]
LEAGUE_LABEL = LEAGUES[args.league]["label"]
SEASONS = ALL_SEASONS[-args.seasons:]
MAX_WORKERS = args.workers
DB_PATH = args.db or f"tm_data_{args.league}_{args.seasons}s_{args.workers}w.db"
LOG_PATH = DB_PATH.replace(".db", ".log")

# --- Setup logging: console + file, con timestamp ---
logger = logging.getLogger("tm_scraper")
logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

fmt = logging.Formatter("[%(asctime)s] [%(levelname)-5s] %(message)s", datefmt="%H:%M:%S")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(fmt)
console_handler.setLevel(logging.DEBUG if args.verbose else logging.INFO)
logger.addHandler(console_handler)

file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
file_handler.setFormatter(fmt)
file_handler.setLevel(logging.DEBUG)  # nel file salviamo sempre tutto, anche col verbose spento
logger.addHandler(file_handler)

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

club_name_cache = {}
cache_lock = threading.Lock()
db_lock = threading.Lock()

# Contatori globali per il riepilogo finale (thread-safe con lock)
stats_lock = threading.Lock()
status_code_counter = Counter()
request_count = {"api": 0, "club_resolve": 0}


def safe_get(session, url, headers=None, timeout=20, max_retries=3, retry_delay=5, context="", retry_status_codes=(502, 503, 504)):
    """Wrapper robusto per le richieste HTTP: ritenta su timeout/errori di rete
    E su status HTTP transitori (502/503/504) invece di far crashare o skippare subito.
    Ritorna None se fallisce dopo tutti i tentativi."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            if resp.status_code in retry_status_codes and attempt < max_retries:
                logger.warning(f"  [RETRY {attempt}/{max_retries}] {context or url}: "
                                f"status {resp.status_code} (errore server transitorio)")
                time.sleep(retry_delay * attempt)
                continue
            return resp
        except Exception as e:
            last_error = e
            logger.warning(f"  [RETRY {attempt}/{max_retries}] {context or url}: {type(e).__name__}: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)  # backoff crescente: 5s, 10s, 15s...
    logger.error(f"  [FALLITO dopo {max_retries} tentativi] {context or url}: {last_error}")
    return None


def new_session():
    return cf_requests.Session(impersonate="chrome124")


def polite_sleep(a=0.3, b=1.0):
    time.sleep(random.uniform(a, b))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY, name TEXT, normalized_name TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS clubs (
        id TEXT PRIMARY KEY, name TEXT, crest_url TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS careers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT, club_id TEXT, season INTEGER,
        appearances INTEGER, goals INTEGER, assists INTEGER, competitions TEXT,
        UNIQUE(player_id, club_id, season))""")
    conn.commit()
    return conn


def normalize_name(name: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", name)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", only_ascii.lower())


def get_league_teams(session, season: int):
    url = f"{BASE_URL}/{LEAGUE_SLUG}/startseite/wettbewerb/{COMPETITION_ID}/plus/?saison_id={season}"
    t0 = time.time()
    resp = safe_get(session, url, headers=WEB_HEADERS, context=f"squadre {LEAGUE_LABEL} stagione {season}")
    if resp is None:
        with stats_lock:
            status_code_counter["teams_network_error"] += 1
        return []
    logger.debug(f"GET squadre stagione {season} -> status {resp.status_code} ({time.time()-t0:.2f}s)")
    with stats_lock:
        status_code_counter[f"teams_{resp.status_code}"] += 1
    if resp.status_code != 200:
        logger.warning(f"Status {resp.status_code} per stagione {season}, salto")
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    teams, seen = [], set()
    for a in soup.select("a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"/([a-z0-9\-]+)/startseite/verein/(\d+)", href)
        if m:
            slug, team_id = m.groups()
            name = a.get_text(strip=True)
            if name and team_id not in seen:
                seen.add(team_id)
                teams.append((team_id, name, slug))
    return teams


def get_team_squad(session, team_id: str, slug: str, season: int):
    url = f"{BASE_URL}/{slug}/kader/verein/{team_id}/saison_id/{season}"
    t0 = time.time()
    resp = safe_get(session, url, headers=WEB_HEADERS, context=f"rosa {slug} {season}")
    if resp is None:
        with stats_lock:
            status_code_counter["squad_network_error"] += 1
        return []
    elapsed = time.time() - t0
    logger.debug(f"GET rosa {slug} {season} -> status {resp.status_code} ({elapsed:.2f}s)")
    with stats_lock:
        status_code_counter[f"squad_{resp.status_code}"] += 1
    if resp.status_code != 200:
        logger.warning(f"Status {resp.status_code} per rosa {slug} {season}, salto")
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


def get_player_performance(session, player_id: str):
    url = f"{API_BASE}/player/{player_id}/performance-game"
    t0 = time.time()
    resp = safe_get(session, url, headers=API_HEADERS, context=f"api player {player_id}")
    if resp is None:
        with stats_lock:
            request_count["api"] += 1
            status_code_counter["api_network_error"] += 1
        return None, "network_error"
    elapsed = time.time() - t0
    with stats_lock:
        request_count["api"] += 1
        status_code_counter[f"api_{resp.status_code}"] += 1
    logger.debug(f"GET api player {player_id} -> status {resp.status_code} ({elapsed:.2f}s)")
    if resp.status_code != 200:
        return None, resp.status_code
    try:
        data = resp.json()
    except Exception as e:
        logger.warning(f"Errore parsing JSON per player {player_id}: {e}")
        return None, "json_error"
    return data.get("data"), resp.status_code


def aggregate_career(perf_data: dict):
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


def resolve_club_name(session, club_id: str):
    with cache_lock:
        if club_id in club_name_cache:
            return club_name_cache[club_id]
    url = f"{BASE_URL}/-/startseite/verein/{club_id}"
    t0 = time.time()
    resp = safe_get(session, url, headers=WEB_HEADERS, max_retries=1, context=f"nome club {club_id}")
    if resp is None:
        with stats_lock:
            request_count["club_resolve"] += 1
            status_code_counter["club_network_error"] += 1
        name = f"Club {club_id}"
        with cache_lock:
            club_name_cache[club_id] = name
        return name
    elapsed = time.time() - t0
    with stats_lock:
        request_count["club_resolve"] += 1
        status_code_counter[f"club_{resp.status_code}"] += 1
    logger.debug(f"GET nome club {club_id} -> status {resp.status_code} ({elapsed:.2f}s) [cache miss]")
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.find("title")
        name = title.get_text(strip=True).split(" - ")[0] if title else f"Club {club_id}"
    else:
        name = f"Club {club_id}"
    with cache_lock:
        club_name_cache[club_id] = name
    return name


def process_player(p_id, p_name):
    session = new_session()
    perf_data, status = get_player_performance(session, p_id)
    if not perf_data:
        return p_id, p_name, None, status
    agg = aggregate_career(perf_data)
    resolved_rows = []
    for (club_id, season), stats in agg.items():
        name = resolve_club_name(session, club_id)
        resolved_rows.append((club_id, name, season, stats))
    return p_id, p_name, resolved_rows, status


def save_player_data(conn, p_id, p_name, rows):
    with db_lock:
        conn.execute("INSERT OR IGNORE INTO players VALUES (?, ?, ?)",
                      (p_id, p_name, normalize_name(p_name)))
        for club_id, club_name, season, stats in rows:
            crest_url = CREST_URL_PATTERN.format(club_id=club_id)
            conn.execute("INSERT OR IGNORE INTO clubs VALUES (?, ?, ?)",
                          (club_id, club_name, crest_url))
            conn.execute(
                """INSERT OR REPLACE INTO careers
                   (player_id, club_id, season, appearances, goals, assists, competitions)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (p_id, club_id, season, stats["appearances"], stats["goals"],
                 stats["assists"], ",".join(sorted(stats["competitions"]))))
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
    logger.info(f"=== SCRAPING v3 — {LEAGUE_LABEL}: {len(SEASONS)} stagioni "
                f"({SEASONS[0]}/{SEASONS[0]+1} -> {SEASONS[-1]}/{SEASONS[-1]+1}) ===")
    logger.info(f"Worker paralleli: {MAX_WORKERS} | DB: {DB_PATH} | Log: {LOG_PATH}")
    logger.info(f"Verbose: {'ON (log dettagliato per ogni richiesta)' if args.verbose else 'OFF (usa --verbose per il dettaglio completo)'}")
    t_start = time.time()
    conn = init_db()
    session = new_session()

    # Pre-carica cache nomi club dal DB esistente (se stai riusando lo stesso file
    # tra leghe diverse, molti club esteri sono probabilmente già risolti)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM clubs WHERE name != 'Club ' || id")
    preloaded_clubs = cur.fetchall()
    for club_id, name in preloaded_clubs:
        with cache_lock:
            club_name_cache[club_id] = name
    logger.info(f"Club già noti (riusati dal DB esistente): {len(preloaded_clubs)}")

    # Pre-carica giocatori già presenti: se li re-incontriamo in questa lega,
    # saltiamo la chiamata API (la loro carriera completa è già salvata)
    cur.execute("SELECT id FROM players")
    already_known_players = {row[0] for row in cur.fetchall()}
    logger.info(f"Giocatori già noti (riusati dal DB esistente): {len(already_known_players)}")

    # TEST connessione
    logger.info("--- TEST connessione ---")
    resp = safe_get(session, BASE_URL, headers=WEB_HEADERS, context="test connessione web")
    if resp is None:
        logger.error("Impossibile connettersi al sito. Controlla la connessione e riprova.")
        return
    logger.info(f"Web status: {resp.status_code}")
    test_data, status = get_player_performance(session, "96828")
    n_test_matches = len(test_data.get("performance", [])) if test_data else 0
    logger.info(f"API status: {status}, partite trovate (player di test): {n_test_matches}")
    if resp.status_code != 200 or not test_data:
        logger.error("Connessione fallita, mi fermo.")
        return

    # FASE 1
    logger.info(f"--- FASE 1: squadre per {len(SEASONS)} stagioni ---")
    t1 = time.time()
    all_teams_by_season = {}
    for i, season in enumerate(SEASONS, 1):
        t_season = time.time()
        teams = get_league_teams(session, season)
        all_teams_by_season[season] = teams
        for team_id, name, slug in teams:
            with cache_lock:
                club_name_cache[team_id] = name
        logger.info(f"  [{i}/{len(SEASONS)}] Stagione {season}/{season+1}: "
                    f"{len(teams)} squadre ({time.time()-t_season:.1f}s)")
        polite_sleep(1.0, 2.0)
    t1_elapsed = time.time() - t1
    logger.info(f"FASE 1 completata in {format_duration(t1_elapsed)}, "
                f"{len(club_name_cache)} club pre-caricati in cache")

    # FASE 2
    logger.info("--- FASE 2: rose di tutte le squadre/stagioni ---")
    t2 = time.time()
    all_players = {}
    n_team_seasons = sum(len(v) for v in all_teams_by_season.values())
    done = 0
    for season, teams in all_teams_by_season.items():
        for team_id, name, slug in teams:
            t_team = time.time()
            players = get_team_squad(session, team_id, slug, season)
            new_players = sum(1 for p in players if p[0] not in all_players)
            for p in players:
                all_players[p[0]] = p[1]
            done += 1
            logger.info(f"  [{done}/{n_team_seasons}] {name} {season}/{season+1}: "
                        f"{len(players)} giocatori ({new_players} nuovi) — "
                        f"totale unici finora: {len(all_players)} ({time.time()-t_team:.1f}s)")
            polite_sleep(1.0, 2.0)
    t2_elapsed = time.time() - t2
    logger.info(f"FASE 2 completata in {format_duration(t2_elapsed)}, "
                f"{len(all_players)} giocatori unici totali")

    # FASE 3
    logger.info(f"--- FASE 3: carriere via API, {MAX_WORKERS} worker paralleli ---")
    t3 = time.time()
    all_player_items = list(all_players.items())
    already_covered = [(p_id, p_name) for p_id, p_name in all_player_items if p_id in already_known_players]
    player_items = [(p_id, p_name) for p_id, p_name in all_player_items if p_id not in already_known_players]
    logger.info(f"  {len(already_covered)} giocatori già completamente nel DB (nessuna chiamata API necessaria)")
    logger.info(f"  {len(player_items)} giocatori nuovi da recuperare")

    completed = 0
    errors = 0
    total_rows_saved = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_player, p_id, p_name): (p_id, p_name)
                   for p_id, p_name in player_items}
        for future in as_completed(futures):
            p_id, p_name = futures[future]
            _, _, rows, status = future.result()
            completed += 1
            if rows is None:
                errors += 1
                logger.warning(f"  [{completed}/{len(player_items)}] ERRORE {p_name} ({p_id}): status {status}")
            else:
                save_player_data(conn, p_id, p_name, rows)
                total_rows_saved += len(rows)
                if args.verbose:
                    logger.debug(f"  [{completed}/{len(player_items)}] OK {p_name}: {len(rows)} righe carriera")

            if completed % args.progress_every == 0 or completed == len(player_items):
                elapsed = time.time() - t3
                rate = completed / elapsed
                remaining = len(player_items) - completed
                eta = remaining / rate if rate > 0 else 0
                error_rate = errors / completed * 100
                logger.info(f"  >>> CHECKPOINT: {completed}/{len(player_items)} "
                            f"({errors} errori, {error_rate:.1f}%) — "
                            f"{rate:.2f} player/s — {total_rows_saved} righe salvate — "
                            f"ETA {format_duration(eta)}")
    t3_elapsed = time.time() - t3

    total_elapsed = time.time() - t_start

    logger.info("=== RIEPILOGO FINALE ===")
    logger.info(f"Lega: {LEAGUE_LABEL}")
    logger.info(f"Fase 1 (squadre):  {format_duration(t1_elapsed)}")
    logger.info(f"Fase 2 (rose):     {format_duration(t2_elapsed)}")
    logger.info(f"Fase 3 (carriere): {format_duration(t3_elapsed)} — "
                f"{completed} giocatori nuovi, {errors} errori ({errors/max(completed,1)*100:.1f}%), "
                f"{len(already_covered)} riusati dal DB (zero chiamate API)")
    logger.info(f"TEMPO TOTALE: {format_duration(total_elapsed)}")
    logger.info(f"Righe carriera salvate: {total_rows_saved}")
    logger.info(f"Chiamate API totali: {request_count['api']}, "
                f"risoluzioni nome club: {request_count['club_resolve']} "
                f"(su {len(club_name_cache)} club totali in cache)")
    logger.info("Breakdown status code:")
    for code, count in sorted(status_code_counter.items()):
        logger.info(f"    {code}: {count}")
    logger.info(f"Log completo salvato in: {LOG_PATH}")

    conn.close()


if __name__ == "__main__":
    main()
