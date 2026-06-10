"""Quick read-only inspector for the canonical source tables (called from v3 build).
Outputs:
  1. all tables in global_aesthetics.db
  2. row counts
  3. for the tables most likely to feed a globe (company / location / track),
     dump the column list + 2 sample rows
"""
import sqlite3
import json
from pathlib import Path

DB = Path(r"E:\shared\Documents\data\global_aesthetics_dashboard\data\global_aesthetics.db")

INTERESTING = {
    # name suffix patterns we want to dump column + 2 rows for
    "compan", "country", "geo", "city", "location", "headquarter",
    "track", "segment", "ownership", "stock", "listed", "valuation",
    "product_master",
}

def is_interesting(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in INTERESTING)

def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]

    print(f"=== {len(tables)} tables in {DB.name} ===\n")
    for t in tables:
        try:
            n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.OperationalError as exc:
            print(f"  {t:<60} ! {exc}")
            continue
        marker = " *" if is_interesting(t) else "  "
        print(f"{marker} {t:<60} {n:>10,}")

    print("\n=== column lists + 2-row samples for company/geo/track-related tables ===\n")
    for t in tables:
        if not is_interesting(t):
            continue
        try:
            cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{t}")').fetchall()]
            sample = [dict(r) for r in cur.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchall()]
        except sqlite3.OperationalError as exc:
            print(f"  {t}: {exc}")
            continue
        print(f"\n--- {t} ({len(cols)} cols) ---")
        print("  cols:", ", ".join(cols))
        if sample:
            print("  sample[0]:", json.dumps(sample[0], ensure_ascii=False, default=str)[:600])
            if len(sample) > 1:
                print("  sample[1]:", json.dumps(sample[1], ensure_ascii=False, default=str)[:600])
    conn.close()

if __name__ == "__main__":
    main()
