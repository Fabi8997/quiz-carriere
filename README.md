# Campionissimo

> Indovina il calciatore dalla sua carriera — il Wordle del calcio.

La carriera del giocatore è visibile da subito (squadre, anni, presenze, gol).
Puoi sbloccare tre indizi in ordine: ruolo → nazionalità → foto.
Non ci sono limiti di tentativi. Puoi condividere la tua sfida via link.

---

## Struttura del progetto

```
quiz-carriere/
├── api/                  Backend FastAPI (Python)
├── scripts/scraping/     Pipeline dati Transfermarkt
├── data/                 Database SQLite + asset (non versionati)
└── docs/                 Documentazione tecnica
```

→ `docs/architecture.md` — architettura completa, scelte tecniche, deploy  
→ `docs/schema_v2.md` — schema del database v2 (player, club, career, sessioni)  
→ `CONTEXT.md` — contesto storico del progetto, decisioni prese, lezioni apprese

---

## Avvio in locale

### Prerequisiti

- Python 3.11+
- Il database `data/tm_data_v2.db` popolato dagli script di scraping
- La cartella `data/assets/` con foto, stemmi e bandiere

### 1 — Crea e attiva il virtualenv

```bash
# dalla root del progetto
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# Mac / Linux
source venv/bin/activate
```

### 2 — Installa le dipendenze API

```bash
cd api
pip install -r requirements.txt
```

### 3 — Configura le variabili d'ambiente

```bash
cp .env.example .env
# .env è già pronto per lo sviluppo locale — non serve modificarlo
```

### 4 — Avvia il server

```bash
# dalla directory api/
uvicorn app.main:app --reload
```

Il server parte su **http://localhost:8000**.

| URL | Descrizione |
|---|---|
| http://localhost:8000/docs | Swagger UI interattivo |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/health | Health check |
| http://localhost:8000/assets/photos/42.jpg | Foto giocatore (ID interno) |

### 5 — Lancia i test

```bash
# dalla directory api/
pytest
```

---

## Endpoint principali

### Gioco

| Metodo | Path | Descrizione |
|---|---|---|
| `POST` | `/game` | Crea una nuova partita (con filtri opzionali) |
| `GET` | `/game/{token}` | Stato corrente della partita |
| `POST` | `/game/{token}/guess` | Invia un tentativo |
| `POST` | `/game/{token}/hint/{type}` | Sblocca un indizio (`role`, `nationality`, `photo`) |
| `POST` | `/game/{token}/surrender` | Resa — rivela il giocatore |

### Sfida

| Metodo | Path | Descrizione |
|---|---|---|
| `POST` | `/challenge` | Crea una sfida condivisibile |
| `GET` | `/challenge/{token}` | Info sfida (per il destinatario) |
| `POST` | `/challenge/{token}/accept` | Accetta e avvia la partita |

### Ricerca fuzzy

| Metodo | Path | Descrizione |
|---|---|---|
| `GET` | `/search?q=cr7` | Ricerca giocatori (gestisce alias, accenti, nomi parziali) |

---

## Frontend (React + Vite)

```bash
cd frontend
cp .env.example .env       # già configurato per dev, non serve modificare
npm install
npm run dev
# → http://localhost:5173
```

Il proxy Vite reindirizza `/api/*` → `http://localhost:8000` e `/assets/*` → `http://localhost:8000`.
**Avvia il backend prima del frontend.**

```bash
# In un terminale: backend
cd api && ..\venv\Scripts\python.exe -m uvicorn app.main:app --reload

# In un altro terminale: frontend
cd frontend && npm run dev
```

| URL | Descrizione |
|---|---|
| http://localhost:5173 | App |
| http://localhost:5173/gioca/{token} | Partita diretta |
| http://localhost:5173/sfida/{token} | Sfida ricevuta via link |

---

## Pipeline dati

```bash
cd scripts

# installa dipendenze scraping
pip install -r requirements.txt

# 1. Scarica dati Serie A da Transfermarkt
python scraping/scrape_serie_a_v3.py --db ../data/tm_data_v2.db

# 2. Arricchisci con profili giocatori
python scraping/scrape_player_profiles.py --db ../data/tm_data_v2.db

# 3. Risolvi nomi club mancanti
python scraping/resolve_club_names.py --db ../data/tm_data_v2.db

# 4. Scarica tutti gli asset (foto, stemmi, bandiere)
python scraping/download_all_assets.py --db ../data/tm_data_v2.db --out ../data/assets

# 5. Analizza qualità dati
python scraping/analyze_db.py --db ../data/tm_data_v2.db
```

---

## Deploy in produzione

1. Copia `.env.example` → `.env` e imposta le variabili Supabase
2. Cambia `DATABASE_URL` con la stringa Postgres di Supabase
3. Cambia `ASSETS_BASE_URL` con l'URL del bucket Supabase Storage
4. Imposta `APP_ENV=production` e `DEBUG=false`
5. Deploy su Railway / Fly.io / Render puntando alla directory `api/`

Il codice non cambia tra dev e prod — cambia solo `.env`.
