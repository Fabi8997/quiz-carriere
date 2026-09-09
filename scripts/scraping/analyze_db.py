"""
Analizza il DB scrapato e stampa un report di qualità dati:
conteggi generali, buchi, duplicati, valori sospetti, campione di verifica.

USO:
    python analyze_db.py --db tm_data_test_40s_6w.db
"""

import sqlite3
import argparse

parser = argparse.ArgumentParser(description="Analisi qualità dataset")
parser.add_argument("--db", type=str, required=True)
args = parser.parse_args()


def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")


def main():
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    section("CONTEGGI GENERALI")
    cur.execute("SELECT COUNT(*) FROM players")
    print(f"Giocatori totali:  {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM clubs")
    print(f"Club totali:       {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM careers")
    print(f"Righe carriera:    {cur.fetchone()[0]}")

    section("CLUB CON NOME NON RISOLTO (placeholder)")
    cur.execute("SELECT id, tm_id, name FROM clubs WHERE name = 'Club ' || tm_id")
    unresolved = cur.fetchall()
    print(f"Totale: {len(unresolved)}")
    for internal_id, tm_id, name in unresolved[:20]:
        cur.execute("SELECT COUNT(*) FROM careers WHERE club_id = ?", (internal_id,))
        n = cur.fetchone()[0]
        print(f"  {name} (tm_id={tm_id}) -> coinvolto in {n} righe carriera")
    if len(unresolved) > 20:
        print(f"  ... e altri {len(unresolved) - 20}")

    section("GIOCATORI SENZA NESSUNA RIGA DI CARRIERA (orfani)")
    cur.execute("""
        SELECT p.id, p.name FROM players p
        LEFT JOIN careers c ON p.id = c.player_id
        WHERE c.id IS NULL
    """)
    orphans = cur.fetchall()
    print(f"Totale: {len(orphans)}")
    for pid, name in orphans[:15]:
        print(f"  {name} ({pid})")

    section("POSSIBILI DUPLICATI NOME CLUB (stesso nome, tm_id diversi)")
    cur.execute("""
        SELECT name, COUNT(*) as n, GROUP_CONCAT(tm_id) as tm_ids
        FROM clubs
        WHERE name != 'Club ' || tm_id
        GROUP BY name
        HAVING n > 1
        ORDER BY n DESC
        LIMIT 20
    """)
    dupes = cur.fetchall()
    print(f"Nomi duplicati trovati: {len(dupes)}")
    for name, n, tm_ids in dupes:
        print(f"  '{name}' -> {n} tm_id diversi: {tm_ids}")

    section("VALORI SOSPETTI: presenze/gol anomali in una singola stagione")
    # Una stagione ha max ~38 partite di campionato + coppe; oltre 60 è sospetto
    cur.execute("""
        SELECT p.name, c.club_id, cl.name, c.season, c.appearances, c.goals
        FROM careers c
        JOIN players p ON c.player_id = p.id
        LEFT JOIN clubs cl ON c.club_id = cl.id
        WHERE c.appearances > 60 OR c.goals > 50
        ORDER BY c.appearances DESC
        LIMIT 15
    """)
    suspicious = cur.fetchall()
    print(f"Righe con valori insolitamente alti: {len(suspicious)}")
    for name, club_id, club_name, season, apps, goals in suspicious:
        print(f"  {name} @ {club_name} ({season}): {apps} presenze, {goals} gol")

    section("COPERTURA PER STAGIONE (righe carriera per anno)")
    cur.execute("""
        SELECT season, COUNT(*) as n
        FROM careers
        GROUP BY season
        ORDER BY season
    """)
    for season, n in cur.fetchall():
        bar = "#" * min(n // 50, 60)
        print(f"  {season}/{season+1}: {n:>5} righe {bar}")

    section("CAMPIONE DI VERIFICA (5 giocatori a caso)")
    cur.execute("SELECT id, name FROM players ORDER BY RANDOM() LIMIT 5")
    sample_players = cur.fetchall()
    for pid, name in sample_players:
        print(f"\n{name} ({pid}):")
        cur.execute("""
            SELECT cl.name, c.season, c.appearances, c.goals
            FROM careers c
            LEFT JOIN clubs cl ON c.club_id = cl.id
            WHERE c.player_id = ?
            ORDER BY c.season
        """, (pid,))
        for club_name, season, apps, goals in cur.fetchall():
            print(f"    {season}/{season+1}  {club_name:<30} {apps:>3} presenze, {goals:>2} gol")

    conn.close()
    print("\n" + "="*60)
    print("Report completato.")


if __name__ == "__main__":
    main()
