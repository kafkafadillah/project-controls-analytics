"""Pipeline lengkap: DSLIB.zip -> tabel olahan -> database SQLite -> tabel ringkasan untuk Power BI.

Jalankan dari folder repo:  python -m project_controls.pipeline
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from . import analysis as an
from . import dataset as ds
from . import db


def build_data(root: Path) -> pd.DataFrame:
    root = Path(root)
    with tempfile.TemporaryDirectory() as tmp:
        files = ds.extract_archive(root / "data" / "raw" / "DSLIB.zip", Path(tmp))
        summary = ds.read_summary(Path(tmp) / "DSLIB_Analysis_Sheet.xlsx")
        proyek, aktivitas, periode, paket, akt_per = ds.build(files, summary)
    proyek = ds.add_quality_flags(proyek)
    ds.write_outputs(root, proyek, aktivitas, periode, paket, akt_per)
    return proyek


def build_summaries(root: Path, p: an.Params = an.Params()) -> dict[str, pd.DataFrame]:
    """Tabel ringkasan (dipakai Power BI dan README), dihitung dari data/processed."""
    root = Path(root)
    proyek = pd.read_csv(root / "data" / "processed" / "proyek.csv")
    periode = pd.read_csv(root / "data" / "processed" / "periode_proyek.csv", parse_dates=["tanggal_status"])
    a = an.portfolio(proyek)
    snap = an.milestone_snapshots(an.project_periods(periode, a), p)
    out = {
        "kelas_referensi": an.reference_classes(a),
        "peringatan_dini": an.early_warning(snap, p),
        "skenario_margin": an.margin_scenario(a),
        "uji_mundur_p80": pd.DataFrame([an.loo_backtest(a, c, lv) for c in [None, "jenis_pekerjaan", "kelas_ukuran"]
                                        for lv in an.LEVELS]),
    }
    folder = root / "data" / "summary"
    folder.mkdir(parents=True, exist_ok=True)
    for k, df in out.items():
        df.to_csv(folder / f"{k}.csv", index=False, float_format="%.6f")
    return out


def main(root: Path = Path(".")):
    build_data(root)
    db.build_database(root)
    build_summaries(root)
    print("selesai: data/processed, data/status_reports, data/summary, sql/project_controls.db")


if __name__ == "__main__":
    main()
