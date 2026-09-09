# Architettura Campionissimo

## Visione d'insieme

```
┌─────────────────────────────────────────────────────┐
│                   FRONTEND (PWA)                    │
│          Browser desktop / mobile                   │
└───────────────���────┬────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────────┐
│                  BACKEND (FastAPI)                  │
│  /game   /search   /challenge   /assets (dev only)  │
└──────────┬─────────────────────┬────────────────────┘
           │ SQLAlchemy ORM      │ URL diretti (prod)
┌──────────▼──────────┐  ┌───────▼──────────────────┐
│   DATABASE          │  │  ASSET STORAGE            │
│   Dev:  SQLite v2   │  │  Dev:  data/assets/       │
│   Prod: Supabase    │  │  Prod: Supabase Storage   │
│         Postgres    │  └──────────────────────────┘
└─────────────────────┘
           ▲
           │ pipeline scraping (separata dall'API)
┌──────────┴──────────┐
│  scripts/scraping/  │
│  (Transfermarkt)    │
└─────────────────────┘
```

## Struttura del progetto

```
quiz-carriere/
├── api/                        ← Backend FastAPI
│   ├── app/
│   │   ├── main.py             entrypoint, lifespan, mount static
│   │   ├── config.py           settings via pydantic-settings + .env
│   │   ├── database.py         engine SQLAlchemy, sessione, init tabelle
│   │   ├── models/
│   │   │   ├── player.py       ORM read-only (schema gestito dagli script)
│   │   │   └── game.py         ORM game sessions, guesses, hints, challenges
│   │   ├── schemas/
│   │   │   ├── game.py         Pydantic request/response per gioco e sfide
│   │   │   └── search.py       Pydantic request/response per ricerca
│   │   ├── routers/
│   │   │   ├── game.py         POST /game, GET /game/{token}, …
│   │   │   ├── search.py       GET /search
│   │   │   └── challenge.py    POST /challenge, GET /challenge/{token}, …
│   │   ├── services/
│   │   │   ├── game.py         logica selezione giocatore, guess, hint, resa
│   │   │   ├── search.py       indice fuzzy in-memory (rapidfuzz)
│   │   │   └── challenge.py    creazione e accettazione sfide
│   │   └── core/
│   │       └── exceptions.py   HTTPException tipizzate
│   ├── tests/
│   │   ├── conftest.py         fixtures: engine in-memory, client, sample_player
│   │   ├── test_game.py        test partite
│   │   └── test_search.py      test fuzzy search
│   ├── .env.example
│   ├── requirements.txt
│   └── pyproject.toml
│
├── scripts/scraping/           ← Pipeline dati (indipendente dall'API)
│   ├── db_v2.py                schema SQLite v2 e helpers
│   ├── scrape_serie_a_v3.py
│   ├── scrape_player_profiles.py
│   ├── migrate_to_v2.py
│   ├── clean_v2.py
│   ├── download_all_assets.py
│   ├── resolve_club_names.py
│   └── analyze_db.py
│
├── data/                       ← Dati (non versionati)
│   ├── tm_data_v2.db
│   └── assets/
│       ├── photos/
│       ├── crests/
│       └── flags/
│
├── docs/
│   ├── architecture.md         ← questo file
│   └── schema_v2.md            schema DB completo
│
└── README.md
```

## Fuzzy Search

L'indice di ricerca viene caricato in RAM all'avvio del server:

1. Tutti i giocatori (`id`, `name`, `normalized_name`, `position_general`, `country_name`)
   vengono letti una volta e tenuti in una lista Python.
2. Gli alias (cr7, totti, il fenomeno, …) vengono caricati in un dizionario
   `normalized_alias → player_id`.
3. Ogni query viene:
   - Normalizzata (minuscolo, rimozione accenti, punteggiatura)
   - Confrontata esattamente con gli alias (match istantaneo)
   - Confrontata con `rapidfuzz.token_sort_ratio` sull'intera lista nomi
4. I risultati sono ordinati per score decrescente; gli alias scalano sempre in cima.

**Performance**: con ~8.000 giocatori l'indice occupa ~2 MB in RAM e una ricerca
richiede < 5ms. Scala tranquillamente fino a ~100.000 giocatori senza modifiche.

**Postgres in produzione**: il codice non usa `pg_trgm` — la stessa logica Python
funziona identicamente su entrambi i DB. `pg_trgm` è disponibile come ottimizzazione
futura se il dataset cresce molto.

## Sessioni di gioco

- Ogni partita è identificata da un **UUID v4 opaco** nel campo `token`.
- Il `player_id` (la risposta) non è mai esposto nelle risposte API finché
  la partita non termina.
- Gli asset (foto, stemmi) sono referenziati tramite **ID interni** (non TM IDs)
  proprio per non esporre la fonte dei dati.
- Il nickname del giocatore viene memorizzato nella sessione ma NON è richiesto:
  l'autenticazione è zero-friction (localStorage lato client).

## Deploy in produzione

1. **Database**: eseguire `sync_to_postgres.py` (da scrivere) per popolare Supabase.
2. **Asset**: eseguire `upload_assets.py` (da scrivere) per caricare su Supabase Storage.
3. **Backend**: deploy su Railway / Fly.io / Render con variabile `DATABASE_URL`
   puntata a Supabase e `APP_ENV=production`.
4. **Frontend**: deploy su Vercel / Netlify.

L'unica differenza tra dev e prod è la stringa di connessione DB e la base URL degli asset.
