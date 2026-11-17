"""Membangun database SQLite dari data/processed dan menjalankan kueri di sql/analysis.sql."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd

TABLES = ["proyek", "aktivitas", "periode_proyek", "aktivitas_periode"]


def build_database(root: Path, db_path: Path | None = None) -> Path:
    root = Path(root)
    db_path = db_path or root / "sql" / "project_controls.db"
    con = sqlite3.connect(db_path)
    con.executescript((root / "sql" / "schema.sql").read_text(encoding="utf-8"))
    for t in TABLES:
        f = root / "data" / "processed" / (f"{t}.csv.gz" if t == "aktivitas_periode" else f"{t}.csv")
        df = pd.read_csv(f, keep_default_na=True)
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        df[cols].to_sql(t, con, if_exists="append", index=False)
    con.commit()
    con.close()
    return db_path


def queries(root: Path) -> dict[str, str]:
    text = (Path(root) / "sql" / "analysis.sql").read_text(encoding="utf-8")
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run(db_path: Path, sql: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as con:
        return pd.read_sql_query(sql, con)
