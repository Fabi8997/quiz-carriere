# Gioco Carriere

Webapp tipo "Wordle del calcio": indovina il calciatore a partire dalla sua
carriera (squadre, anni, presenze, gol), da giocare e condividere tra amici.

## Per iniziare (anche per Claude Code)

**Leggi prima [`CONTEXT.md`](./CONTEXT.md)** — contiene tutto il contesto di
design, le decisioni prese, i problemi già risolti (in particolare le
lezioni su come Transfermarkt gestisce l'anti-bot) e la roadmap dettagliata.
Non saltarlo: evita di ripetere debugging già fatto o di riproporre
soluzioni già scartate.

## Struttura del progetto

```
gioco-carriere/
├── CONTEXT.md              ← leggi questo per primo
├── README.md                ← questo file
├── docs/
│   └── schema.md             schema DB attuale, documentato
├── scripts/
│   ├── requirements.txt
│   └── scraping/             pipeline di raccolta dati (Transfermarkt)
│       ├── scrape_serie_a_v3.py
│       ├── resolve_club_names.py
│       ├── patch_missing_squads.py
│       ├── download_crests.py
│       ├── scrape_player_profiles.py
│       └── analyze_db.py
└── data/                     qui va il file .db (non versionato, vedi .gitignore)
```

## Stato attuale

Raccolta dati Serie A (40 stagioni) quasi completa. Vedi la checklist
dettagliata in `CONTEXT.md` → sezione "Roadmap completa" per sapere
esattamente cosa è fatto e cosa manca.

## Setup rapido

```bash
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate

pip install -r scripts/requirements.txt
```

Il database SQLite (`.db`) generato dagli script di scraping va tenuto in
`data/` — non è incluso in questo pacchetto perché è un file dati pesante
generato in locale, non codice.
