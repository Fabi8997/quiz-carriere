# Schema database (SQLite, fase di raccolta dati)

Vedi `CONTEXT.md` per il razionale delle decisioni. Questo file è il
riferimento rapido allo schema così com'è definito nel codice.

## players

| colonna | tipo | note |
|---|---|---|
| id | TEXT PK | ID Transfermarkt |
| name | TEXT | nome visualizzato |
| normalized_name | TEXT | minuscolo, senza accenti — per fuzzy search |
| nationality | TEXT | aggiunta da `scrape_player_profiles.py` |
| nationality_flag_url | TEXT | URL bandiera (CDN Transfermarkt, va scaricata) |
| birth_date | TEXT | formato "DD/MM/YYYY" |
| birth_place | TEXT | |
| height | TEXT | formato "1,86 m" (stringa, non numero — occhio se serve ordinare) |
| position_detailed | TEXT | valore grezzo TM, es. "Punta centrale" |
| photo_url | TEXT | URL CDN Transfermarkt, contiene un timestamp instabile — va scaricata, non hotlinkata |
| photo_source_ts | INTEGER | timestamp estratto da photo_url, per rilevare quando TM aggiorna la foto |
| photo_downloaded_at | TEXT | quando NOI abbiamo scaricato il file in locale (ISO datetime) |

**Manca ancora** (Step 2, non fatto): `position_general`, `slug`.

## clubs

| colonna | tipo | note |
|---|---|---|
| id | TEXT PK | ID Transfermarkt |
| name | TEXT | placeholder `"Club " + id` se non ancora risolto |
| crest_url | TEXT | URL CDN, costruito deterministicamente da club_id, no scraping extra |
| crest_downloaded_at | TEXT | quando scaricato in locale (ISO datetime) |

⚠️ Per trovare i placeholder non risolti: `WHERE name = 'Club ' || id`
(confronto ESATTO). MAI `LIKE 'Club %'` — vedi CONTEXT.md, ci sono club
veri il cui nome inizia legittimamente per "Club ".

## careers

| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| player_id | TEXT | FK logica verso players.id (non imposta da SQLite) |
| club_id | TEXT | FK logica verso clubs.id (non imposta da SQLite) |
| season | INTEGER | anno di inizio stagione, es. 2015 = stagione 2015/16 |
| appearances | INTEGER | presenze, aggregate da partite con participationState="played" |
| goals | INTEGER | |
| assists | INTEGER | |
| competitions | TEXT | competizioni coinvolte, separate da virgola (es. "IT1,CIT") |

Vincolo: `UNIQUE(player_id, club_id, season)` — una riga per ogni
combinazione giocatore+club+stagione (aggrega tutte le competizioni in
quella combinazione).

## Relazioni

```
players (1) ──< careers >── (1) clubs
```

`careers` è la tabella ponte many-to-many con attributi (stagione,
statistiche).

## File immagini scaricati (`download_all_assets.py`)

Nomi file **stabili**, non cambiano mai anche se il contenuto viene aggiornato:

```
data/assets/
├── photos/{player_id}.jpg     -- foto giocatore
├── crests/{club_id}.png       -- stemma club
└── flags/{country_id}.png     -- bandiera nazionalità (deduplicata)
```

Usare questi path locali nell'app finale, MAI l'URL Transfermarkt diretto
(rischio anti-hotlink + URL foto non stabili nel tempo — vedi CONTEXT.md).
