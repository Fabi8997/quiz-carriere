"""Rinomina i file asset da TM IDs a ID interni v2.

Il primo download degli asset girava contro il DB v1 in cui i PK erano i TM IDs,
quindi i file sono nominati {tm_id}.png / {tm_id}.jpg.
Ora le API usano gli ID interni v2 → i file vanno rinominati.

Usa un approccio in due passi (old → _tmp_{new} → {new}) per evitare
collisioni quando un TM ID coincide numericamente con un ID interno di un
altro elemento.

USO (dalla root del progetto):
    python scripts/scraping/rename_assets.py --db data/tm_data_v2.db --assets data/assets
"""

import sqlite3
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("rename_assets")

parser = argparse.ArgumentParser()
parser.add_argument("--db", required=True, help="Percorso DB v2")
parser.add_argument("--assets", required=True, help="Cartella radice degli asset")
args = parser.parse_args()


def _rename_dir(directory: Path, mapping: dict[str, int], ext: str, label: str) -> None:
    """Rinomina i file in `directory` da {tm_id}.ext a {internal_id}.ext."""
    if not directory.exists():
        logger.warning(f"  Cartella non trovata: {directory}")
        return

    files = {f.stem: f for f in directory.glob(f"*{ext}")}
    renamed = skipped = already_ok = not_in_map = 0

    # ── Passo 1: vecchio nome → nome temporaneo ───────────────────────────────
    for tm_id, old_file in list(files.items()):
        if tm_id.startswith("_tmp_"):
            continue  # già temporaneo da un run precedente interrotto

        internal_id = mapping.get(tm_id)
        if internal_id is None:
            not_in_map += 1
            continue

        new_name = str(internal_id)
        if tm_id == new_name:
            already_ok += 1
            continue

        tmp_path = directory / f"_tmp_{internal_id}{ext}"
        old_file.rename(tmp_path)
        renamed += 1

    # ── Passo 2: nome temporaneo → nome definitivo ────────────────────────────
    for tmp_file in sorted(directory.glob(f"_tmp_*{ext}")):
        final_name = tmp_file.name.replace("_tmp_", "", 1)
        final_path = directory / final_name
        if final_path.exists():
            logger.warning(f"  Conflitto: {final_path.name} già esiste, salto {tmp_file.name}")
            skipped += 1
            continue
        tmp_file.rename(final_path)

    logger.info(
        f"  {label}: {renamed} rinominati, {already_ok} già corretti, "
        f"{not_in_map} TM ID sconosciuto, {skipped} conflitti"
    )


def main() -> None:
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    assets = Path(args.assets)

    # ── Stemmi ────────────────────────────────────────────────────────────────
    logger.info("--- Stemmi (crests) ---")
    cur.execute("SELECT tm_id, id FROM clubs WHERE tm_id IS NOT NULL")
    club_map = {str(row[0]): row[1] for row in cur.fetchall()}
    _rename_dir(assets / "crests", club_map, ".png", "Stemmi")

    # ── Foto giocatori ────────────────────────────────────────────────────────
    logger.info("--- Foto giocatori (photos) ---")
    cur.execute("SELECT tm_id, id FROM players WHERE tm_id IS NOT NULL")
    player_map = {str(row[0]): row[1] for row in cur.fetchall()}
    _rename_dir(assets / "photos", player_map, ".jpg", "Foto")

    # ── Bandiere — già nominate con tm_id nazione, non vanno cambiate ─────────
    logger.info("--- Bandiere: nessuna modifica necessaria (usano tm_id paese) ---")

    conn.close()
    logger.info("Completato.")


if __name__ == "__main__":
    main()
