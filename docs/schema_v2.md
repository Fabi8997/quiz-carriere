# Schema database v2

> Questo è lo schema in produzione. Lo schema v1 (TM IDs come PK) era quello
> intermedio degli script di scraping — la migrazione a v2 è già avvenuta tramite
> `migrate_to_v2.py`.

## Tabelle gestite dagli script di scraping

### `countries`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | ID interno stabile |
| tm_id | TEXT | ID Transfermarkt (es. "100") |
| name | TEXT | nome per esteso (es. "Italia") |
| flag_url | TEXT | URL CDN TM — il file è scaricato in `data/assets/flags/{tm_id}.png` |

### `players`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | ID interno stabile (usato nei nomi file asset) |
| tm_id | TEXT UNIQUE | ID Transfermarkt — non esposto nelle API |
| slug | TEXT UNIQUE | URL-friendly, es. "cristiano-ronaldo" |
| name | TEXT | nome visualizzato |
| normalized_name | TEXT | minuscolo, senza accenti — per fuzzy search |
| birth_date | TEXT | ISO 8601 YYYY-MM-DD (normalizzato da `clean_v2.py`) |
| birth_place | TEXT | |
| height_cm | INTEGER | in cm (convertito da `migrate_to_v2.py`) |
| country_id | INTEGER FK | → countries.id |
| position_general | TEXT | Portiere / Difensore / Centrocampista / Attaccante |
| position_detailed | TEXT | valore grezzo TM, es. "Punta centrale" |
| photo_url | TEXT | URL CDN TM (instabile nel tempo — usare il file locale) |
| photo_downloaded_at | TEXT | ISO datetime dell'ultimo download |

### `clubs`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | ID interno stabile |
| tm_id | TEXT UNIQUE | ID Transfermarkt |
| slug | TEXT UNIQUE | URL-friendly |
| name | TEXT | placeholder `'Club ' \|\| tm_id` se non ancora risolto |
| crest_url | TEXT | URL CDN TM |
| crest_downloaded_at | TEXT | ISO datetime dell'ultimo download |

⚠️ Placeholder non risolti: `WHERE name = 'Club ' || tm_id` (confronto esatto, mai LIKE).

### `careers`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| player_id | INTEGER FK | → players.id |
| club_id | INTEGER FK | → clubs.id |
| season | INTEGER | anno di inizio stagione (es. 2015 = stagione 2015/16) |
| appearances | INTEGER | presenze aggregate per tutte le competizioni |
| goals | INTEGER | |
| assists | INTEGER | |
| competitions | TEXT | es. "IT1,CIT" |
| source_id | INTEGER FK | → data_sources.id (Transfermarkt = 1) |

Vincolo: `UNIQUE(player_id, club_id, season)`

### `player_aliases`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| alias | TEXT UNIQUE | stringa normalizzata (es. "cr7", "il fenomeno") |
| player_id | INTEGER FK | → players.id |

### `data_sources`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | es. "transfermarkt" |
| base_url | TEXT | |

---

## Tabelle gestite dall'API di gioco

### `game_sessions`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| token | TEXT UNIQUE | UUID v4 — usato negli URL, non espone ID interni |
| player_id | INTEGER FK | → players.id (la risposta del gioco) |
| nickname | TEXT | soprannome del giocatore (da localStorage) |
| status | TEXT | `playing` / `won` / `surrendered` |
| filters_json | TEXT | JSON dei filtri usati per selezionare il giocatore |
| created_at | TEXT | ISO datetime |
| completed_at | TEXT | ISO datetime, NULL se ancora in corso |

### `game_guesses`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| session_id | INTEGER FK | → game_sessions.id |
| guessed_player_id | INTEGER FK | → players.id, NULL se nome non riconosciuto |
| raw_input | TEXT | testo digitato dall'utente così com'è |
| is_correct | BOOLEAN | |
| guessed_at | TEXT | ISO datetime |

### `game_hints`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| session_id | INTEGER FK | → game_sessions.id |
| hint_type | TEXT | `role` / `nationality` / `photo` |
| unlocked_at | TEXT | ISO datetime |

Vincolo: `UNIQUE(session_id, hint_type)` — ogni indizio si sblocca una sola volta.

### `challenge_links`
| colonna | tipo | note |
|---|---|---|
| id | INTEGER PK | |
| token | TEXT UNIQUE | UUID v4 — usato negli URL condivisibili |
| creator_nickname | TEXT | chi ha creato la sfida |
| player_id | INTEGER FK | → players.id |
| created_at | TEXT | ISO datetime |

---

## Asset

```
data/assets/
├── photos/{player.id}.jpg      foto giocatore (nominata con ID interno, non TM)
├── crests/{club.id}.png        stemma club
└── flags/{country.tm_id}.png   bandiera nazione (deduplicata per nazione)
```

In sviluppo gli asset sono serviti da FastAPI su `/assets/`.
In produzione sono su Supabase Storage allo stesso path relativo.
