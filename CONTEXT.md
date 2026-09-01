# Contesto progetto — Gioco "Indovina il giocatore"

Questo file esiste per dare a Claude Code tutto il contesto accumulato in una
lunga sessione di progettazione su claude.ai, senza doverlo rispiegare da zero.
Leggilo per intero prima di iniziare a lavorare sul progetto.

## Cos'è il progetto

Una webapp (poi eventualmente app mobile) tra amici, tipo "Wordle ma per il
calcio": un giocatore sceglie un calciatore e lo manda a un altro giocatore
(o gruppo, condivisibile su WhatsApp). Chi riceve la sfida vede la carriera
del calciatore (squadre, anni, presenze, gol) SENZA il nome, e deve indovinarlo
scrivendolo in un campo di ricerca con autocomplete fuzzy.

**Modalità di gioco decisa per l'MVP**: tentativi progressivi (alla Wordle) —
ogni tentativo sbagliato rivela un indizio in più (prima solo squadre/anni,
poi presenze, poi gol, ecc.). Altre modalità (daily challenge, torneo,
indizi su nazionalità/ruolo) sono previste ma NON prioritarie per l'MVP.

## Stack deciso

- Dataset: scraping Transfermarkt (vedi sotto, è la parte quasi completata)
- DB raccolta dati: SQLite locale (fase attuale)
- DB produzione: Postgres via Supabase (fuzzy search con `pg_trgm`) — DA FARE
- Backend: da decidere in dettaglio, ma endpoint previsti:
  - `POST /sfida` → genera sfida, ritorna game_id
  - `GET /sfida/{id}` → carriera senza nome, per la UI
  - `POST /sfida/{id}/tentativo` → valida un nome (fuzzy match)
  - `GET /search-giocatori?q=...` → autocomplete
- Frontend: webapp condivisibile via link, pensata anche come PWA
  (installabile su home screen senza passare dagli store)
- Deploy: Vercel/Netlify (frontend) + Supabase (backend/DB), tutto free tier

## Stato attuale della raccolta dati (la parte fatta finora)

### Fonte dati: Transfermarkt, NON API ufficiale

Importante: Transfermarkt vieta lo scraping massivo nei suoi ToS. Per un
progetto personale/tra amici il rischio pratico è basso, ma se il progetto
diventasse pubblico/commerciale bisognerebbe rivalutare (API ufficiali a
pagamento, o Wikidata come fonte legalmente più pulita ma meno granulare).

### Endpoint scoperti (fondamentali, non ovvi)

1. **Carriera partita-per-partita**: `https://tmapi.transfermarkt.technology/player/{player_id}/performance-game`
   - Ritorna JSON con OGNI partita giocata in carriera (club, stagione,
     competizione, gol, assist, minuti, participationState)
   - Aggregare per `(club_id, seasonId)` filtrando `participationState == "played"`
     dà squadra+anno+presenze+gol — esattamente il dato che serve al gioco
   - Questo endpoint è MOLTO affidabile: su 8748 chiamate nel run principale,
     **zero errori**. È il pezzo più solido di tutta la pipeline.

2. **Rose squadra per stagione** (HTML scraping classico):
   `https://www.transfermarkt.it/{slug}/kader/verein/{team_id}/saison_id/{season}`
   - Anche questo affidabile, pochi errori (quasi tutti timeout transitori,
     risolti con retry)

3. **Stemmi club** (CDN immagini diretto, deterministico):
   `https://img.a.transfermarkt.technology/wappen/homepageWappen150x150/{club_id}.png?lm=4711`
   - Nessuna richiesta HTML necessaria, si costruisce l'URL dal solo club_id

4. **Foto profilo giocatore** (stesso CDN):
   `https://img.a.transfermarkt.technology/portrait/header/{player_id}-{timestamp}.jpg`
   - ATTENZIONE: il timestamp nell'URL cambia se TM aggiorna la foto — non è
     stabile nel tempo, va scaricata e ri-hostata, non hotlinkata

5. **Bandiera nazionalità** (stesso CDN):
   `https://img.a.transfermarkt.technology/flagge/tiny/{country_id}.png`

### Anti-bot: lezioni imparate (IMPORTANTI, leggere prima di scrivere nuovo scraping)

Transfermarkt usa Cloudflare. Pattern osservati sperimentalmente:

- **L'endpoint JSON `performance-game` non ha mai dato problemi**, nemmeno
  con 6 richieste parallele.
- **Le pagine HTML (rose, profili) sono più delicate.** Il problema principale
  non è la velocità pura, è il **pattern dell'URL**: usare uno slug
  placeholder sintetico (es. `/-/startseite/verein/{id}` o `/-/profil/spieler/{id}`)
  fa scattare il rilevamento anti-bot molto più facilmente di uno slug
  "umano" (es. `/simone-zaza/profil/spieler/96828`), perché nessun utente
  reale visita mai URL con `-` come slug.
- **Uno slug derivato dal nome** (minuscolo, accenti rimossi, spazi→trattini
  — vedi funzione `generate_slug()` in `scrape_player_profiles.py`) non deve
  essere perfetto: Transfermarkt fa match sull'ID numerico finale, lo slug
  testuale è quasi decorativo. Usare lo slug derivato ha portato il tasso di
  successo dal 20% all'80% nei test.
- **Pattern di "riscaldamento"**: nei test si è osservato che i primi ~15-20
  request hanno un tasso di fallimento (403) più alto, poi la sessione
  sembra "guadagnare fiducia" e i request successivi passano quasi sempre
  puliti. Soluzione: retry con backoff breve (8s/16s/24s) sui 403, NON
  rallentare drasticamente tutto.
- **Le pagine club specificamente** (`/-/startseite/verein/{id}`) sono le
  più sensibili incontrate finora: durante lo scraping massivo parallelo
  sono arrivati ~99% di 403. La soluzione che ha funzionato: risoluzione
  POST-processing, sequenziale, delay 3-6s, retry con backoff lungo
  (15s/30s), refresh sessione ogni 20 richieste → tasso di successo ~96-98%
  su due passate.
- **Bug da NON reintrodurre**: il placeholder per i nomi club non risolti è
  la stringa `"Club " + id` (es. "Club 4941"). NON usare mai
  `WHERE name LIKE 'Club %'` per trovarli — moltissimi club veri
  (sudamericani/messicani) si chiamano legittimamente "Club Nacional",
  "Club Atlético X", ecc. e verrebbero ri-processati inutilmente ad ogni
  run. Usare invece il confronto ESATTO: `WHERE name = 'Club ' || id`.

### Pipeline di scraping — script disponibili in `scripts/scraping/`

Esegui in quest'ordine (già tutti testati e funzionanti):

1. **`scrape_serie_a_v3.py`** — script principale. Parametrico per lega
   (`--league serie-a|premier-league|la-liga|bundesliga|ligue-1`) e stagioni
   (`--seasons N`, prende le N più recenti su 40 disponibili, 1986-2025).
   Se punti allo stesso file `--db` tra leghe diverse, RIUSA club e
   giocatori già trovati (molti club esteri sono già noti dai trasferimenti
   dei giocatori italiani, molte "stelle" già scoperte non vengono
   ri-processate). Fa scraping di: squadre per stagione → rose → carriere
   via API → nomi club (con qualche 403 fisiologico, si risolve dopo) →
   crest_url (costruito, non scaricato).
   Ha retry automatico su timeout di rete E su 502/503/504.

2. **`resolve_club_names.py`** — risolve i placeholder `"Club {id}"` rimasti
   dal run principale (di solito 1-4% del totale). Sequenziale, lento
   apposta (delay 3-6s), con retry/backoff. Lanciare più volte se restano
   pochi falliti dopo il primo giro (tasso di successo cresce).

3. **`patch_missing_squads.py`** — recupera rose fallite per errori 502
   specifici incontrati nel run principale (attualmente hardcoded per
   Siena/Messina 2004/05, ma il pattern è riusabile per altri buchi
   analoghi — basta aggiungere alla lista `MISSING_SQUADS`).

4. **`download_crests.py`** — scarica le immagini stemmi in locale
   (`crests/{club_id}.png`), NON va hotlinkato l'URL Transfermarkt nell'app
   finale (rischio protezione anti-hotlink + URL non stabili).
   ⚠️ NOTA: era stato deciso di ACCORPARE questo con lo scaricamento di
   foto giocatori e bandiere in un unico script `download_all_assets.py`
   MAI SCRITTO — se non esiste ancora, è uno dei prossimi task.

5. **`scrape_player_profiles.py`** — arricchisce ogni giocatore con
   nazionalità, posizione dettagliata, data/luogo nascita, altezza, URL
   foto, URL bandiera. Aggiunge le colonne alla tabella `players`
   automaticamente al primo avvio. Resumable (processa solo
   `WHERE nationality IS NULL`). Usa `generate_slug()` + retry su 403.
   ✅ COMPLETATO su tutti gli 8764 giocatori Serie A, 100% di successo
   (0 falliti), ~5 ore di esecuzione.

6. **`download_all_assets.py`** — script unificato (era stato deciso di
   accorpare qui il vecchio `download_crests.py` standalone, che è stato
   rimosso). Scarica in locale stemmi club, foto giocatori e bandiere.
   Punti chiave:
   - **Nomi file stabili**: `{player_id}.jpg`, `{club_id}.png`,
     `{country_id}.png` — non cambiano mai anche se il contenuto viene
     aggiornato, così i riferimenti nell'app non si rompono mai
   - **Foto giocatori**: gestione aggiornamenti intelligente. L'URL
     Transfermarkt della foto contiene già un timestamp
     (`.../96828-1596184084.jpg`) — lo confrontiamo con quello salvato
     l'ultima volta (`players.photo_source_ts`) e riscarichiamo SOLO se è
     cambiato. Pensato per essere rilanciato periodicamente.
   - **Stemmi**: scaricati una sola volta (cambiano raramente), skip se il
     file esiste già
   - **Bandiere**: deduplicate per country_id (tante nazionalità
     condividono la stessa immagine, non ha senso scaricarla N volte)
   - Nuove colonne aggiunte: `players.photo_source_ts`,
     `players.photo_downloaded_at`, `clubs.crest_downloaded_at`
   - ⚠️ NON ANCORA ESEGUITO alla chiusura di questa sessione — prossimo
     step pratico da fare

7. **`analyze_db.py`** — report di qualità dati: conteggi, club non
   risolti, giocatori orfani, duplicati, valori sospetti (presenze/gol
   anomali), copertura per stagione, campione casuale di verifica.
   Utile da rilanciare dopo ogni fase per controllare che sia tutto pulito.

### Schema DB attuale (SQLite, `scripts/scraping/*.py` → `init_db()`)

```sql
players (
  id TEXT PRIMARY KEY,              -- ID Transfermarkt
  name TEXT,
  normalized_name TEXT,             -- minuscolo, senza accenti, per fuzzy search
  -- colonne aggiunte da scrape_player_profiles.py:
  nationality TEXT,
  nationality_flag_url TEXT,
  birth_date TEXT,
  birth_place TEXT,
  height TEXT,
  position_detailed TEXT,           -- es. "Punta centrale", valore grezzo TM
  photo_url TEXT
)

clubs (
  id TEXT PRIMARY KEY,
  name TEXT,
  crest_url TEXT
)

careers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id TEXT,                   -- FK logica, NON dichiarata nel DB
  club_id TEXT,                     -- FK logica, NON dichiarata nel DB
  season INTEGER,                   -- anno di inizio stagione (2015 = 2015/16)
  appearances INTEGER,
  goals INTEGER,
  assists INTEGER,
  competitions TEXT,                -- lista competizioni separate da virgola
  UNIQUE(player_id, club_id, season)
)
```

**Da fare esplicitamente sullo schema (Step 2, ancora non iniziato)**:
- `position_general` (Attaccante/Centrocampista/Difensore/Portiere), derivato
  da `position_detailed` con una mappa scritta a mano — la mappa va costruita
  guardando i valori DISTINCT reali presenti nel DB, non indovinata a priori
  (decisione esplicita presa in sessione precedente)
- Tabella `aliases` (nickname → player_id): CR7, Ibra, ecc. — lista scritta
  a mano per i giocatori più noti
- Foreign key vere (per ora solo logiche, non imposte da SQLite)
- Pulizia duplicati nomi club (stesso club, ID diversi in stagioni diverse
  — capita con Transfermarkt)
- Colonna `slug` in `players` — attualmente NON salvata (lo slug reale
  veniva scartato durante lo scraping rose), utile da aggiungere per
  costruire link diretti alla pagina Transfermarkt del giocatore nell'app

## Roadmap completa (dove siamo, cosa manca)

- [x] Scraping Serie A 40 stagioni (1986-2025)
- [x] Patch buchi (errori 502 Siena/Messina 2004/05)
- [x] Nomi club risolti (bug query LIKE corretto, ~96-100% risolti)
- [x] Arricchimento profili (nazionalità/posizione/foto/bandiera) —
      8764/8764 giocatori, 100% successo
- [ ] Download effettivo stemmi+foto+bandiere in locale (script
      `download_all_assets.py` pronto, MAI ANCORA ESEGUITO — primo task
      pratico da fare)
- [ ] **Step 2 — Consolidamento schema**: position_general, aliases, pulizia
      duplicati, FK vere
- [ ] **Step 3 — Migrazione Postgres/Supabase**: con estensione `pg_trgm`
      per fuzzy search
- [ ] **Step 4 — Backend**: endpoint sfida/tentativo/ricerca
- [ ] **Step 5 — Frontend**: crea sfida, gioca, PWA
- [ ] **Step 6 — Deploy**: Vercel/Netlify + Supabase
- [ ] **Validazione con gli amici** (primo vero checkpoint)
- [ ] Solo dopo, se piace: altre 4 leghe (Premier, Liga, Bundesliga, Ligue 1)
      — riusando lo stesso `--db` per sfruttare cache club/giocatori già
      trovati, sarà più rapido del run Serie A
- [ ] Modalità di gioco aggiuntive (daily challenge, indizi su
      nazionalità/ruolo, classifiche, torneo)

## Decisioni prese e PERCHÉ (per non tornarci sopra senza motivo)

- **MVP solo Serie A, non le 5 leghe insieme**: prima verificare che tutto
  il resto (schema, gioco, UI) funzioni su un dataset gestibile, poi
  espandere. "Finito piccolo" batte "grande a metà".
- **No hotlink diretto a immagini Transfermarkt nell'app finale**: rischio
  protezione anti-hotlink (referer check) + URL foto non stabili nel tempo
  (contengono un timestamp che cambia se la foto viene aggiornata). Va
  tutto scaricato e ri-hostato (Supabase Storage o simile).
- **Wikipedia scartata come fonte primaria** (era stata valutata): dati meno
  granulari (spesso solo campionato nazionale, non le coppe), template
  wikitext più complesso da parsare in modo affidabile rispetto all'API
  JSON di Transfermarkt che si è rivelata solidissima. Rimane un'opzione di
  backup/arricchimento futuro, specialmente se il rischio ToS di
  Transfermarkt diventasse un problema reale (progetto pubblico/commerciale).
- **SQLite per la raccolta, Postgres per la produzione**: SQLite ottimo per
  scraping locale (scritture veloci anche da thread paralleli), ma non
  pensato per essere il backend di una webapp multi-utente.

## Nota su questa sessione

Questo progetto è stato sviluppato in una lunga conversazione su claude.ai
(non Claude Code) perché serviva iterare rapidamente su decisioni di design
e debug empirico (perché un endpoint dà 403, che dati sono disponibili,
ecc.) con feedback conversazionale. Da qui in avanti (schema finale,
migrazione DB, backend, frontend) il lavoro è più adatto a un ambiente con
accesso diretto a file/rete/esecuzione — da qui la scelta di passare a
Claude Code.

Se hai dubbi su una decisione presa e documentata qui, chiedi conferma
all'utente prima di cambiarla — molte di queste scelte derivano da test
empirici reali (log di scraping analizzati insieme), non da assunzioni.
