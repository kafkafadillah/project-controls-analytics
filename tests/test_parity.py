"""Uji konsistensi: parser ProTrack, Python vs SQL vs workbook Excel."""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook

from project_controls import analysis as an, db, protrack as pt

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "excel" / "Analisis_Kinerja_Biaya_Jadwal_Proyek.xlsx"
TOL = 1e-5


@pytest.fixture(scope="module")
def data():
    proyek = pd.read_csv(ROOT / "data" / "processed" / "proyek.csv")
    periode = pd.read_csv(ROOT / "data" / "processed" / "periode_proyek.csv", parse_dates=["tanggal_status"])
    a = an.portfolio(proyek)
    return proyek, periode, a


@pytest.fixture(scope="module")
def wb():
    return load_workbook(XLSX, data_only=True)


def close(x, y, tol=TOL):
    return abs(float(x) - float(y)) <= tol * max(1.0, abs(float(x)))


def test_calendar_working_hours():
    cal = pt.Calendar(nonworking_hours=[h for h in range(24) if h not in (8, 9, 10, 11, 13, 14, 15, 16)],
                      nonworking_days=[5, 6])
    mon = datetime(2024, 1, 1, 8)  # Senin
    assert cal.hours_per_day == 8
    assert cal.working_hours_between(mon, datetime(2024, 1, 1, 17)) == 8
    assert cal.working_hours_between(mon, datetime(2024, 1, 8, 8)) == 40      # satu minggu kerja
    assert cal.end_date(mon, 16) == datetime(2024, 1, 2, 17)                  # dua hari kerja
    assert cal.end_date(datetime(2024, 1, 5, 8), 16) == datetime(2024, 1, 8, 17)  # melewati akhir pekan


def test_reconciliation_and_rules(data):
    proyek, _, a = data
    assert len(proyek) == 231 and proyek.kode_proyek.is_unique
    assert (proyek.jumlah_periode > 0).sum() == 155
    bac_ok = proyek.bac_ringkasan.notna() & ((proyek.bac / proyek.bac_ringkasan - 1).abs() < 1e-3)
    assert bac_ok.sum() == 185
    assert proyek.biaya_sumber_daya_di_anggaran.eq("Tidak").sum() == 21
    assert len(a) == 119 and (a.ac_akhir > 0).all()


def test_sql_matches_python(data, tmp_path):
    _, periode, a = data
    path = db.build_database(ROOT, tmp_path / "t.db")
    q = db.queries(ROOT)
    s = an.summary(a)
    r = db.run(path, q["ringkasan_portofolio"]).iloc[0]
    for k in ["proyek", "di_atas_anggaran", "di_bawah_anggaran", "membengkak_material", "terlambat"]:
        assert close(r[k], s[k]), k
    j = db.run(path, q["kinerja_per_jenis"]).set_index("jenis_pekerjaan")
    g = an.by_group(a, "jenis_pekerjaan")
    for k in ["proyek", "median_rasio_biaya", "p80_rasio_biaya", "porsi_di_atas_anggaran"]:
        assert np.allclose(j.loc[g.index, k].astype(float), g[k].astype(float), rtol=1e-9), k
    ew = an.early_warning(an.milestone_snapshots(an.project_periods(periode, a)))
    e = db.run(path, q["peringatan_dini_50"]).iloc[0]
    m = ew[ew.milestone == 0.5].iloc[0]
    for k in ["proyek", "proyek_membengkak", "proyek_ditandai", "tertangkap", "eac_dalam_5pct", "bac_dalam_5pct"]:
        assert close(e[k], m[k]), k


def test_excel_has_no_error_values(wb):
    bad = [f"{ws.title}!{c.coordinate}" for ws in wb.worksheets for row in ws.iter_rows() for c in row
           if isinstance(c.value, str) and c.value.startswith("#") and c.value.endswith(("!", "?", "A"))]
    assert not bad, bad[:10]


def test_excel_portfolio_matches_python(data, wb):
    _, _, a = data
    K = wb["Kinerja_Portofolio"]
    s = an.summary(a)
    cells = {"proyek": "C7", "di_atas_anggaran": "C8", "di_bawah_anggaran": "C9", "membengkak_material": "C10",
             "terlambat": "C11", "median_rasio_biaya": "C12", "p80_rasio_biaya": "C13", "p90_rasio_biaya": "C14",
             "median_rasio_durasi": "C15"}
    for k, ref in cells.items():
        assert close(s[k], K[ref].value), k
    for top, col in [(19, "jenis_pekerjaan"), (27, "kelas_ukuran")]:
        r = top
        while K[f"B{r}"].value != "Semua proyek":
            grp = a[a[col] == K[f"B{r}"].value]
            assert K[f"C{r}"].value == len(grp)
            assert close(K[f"D{r}"].value, grp.rasio_biaya.median())
            assert close(K[f"E{r}"].value, an.percentile_inc(grp.rasio_biaya, 0.8))
            assert close(K[f"G{r}"].value, grp.rasio_durasi.mean())
            r += 1


def test_excel_per_project_ratios(data, wb):
    _, _, a = data
    D = wb["Data_Proyek"]
    rows = {D[f"B{r}"].value: r for r in range(6, 6 + 231)}
    assert sum(D[f"W{r}"].value == "Ya" for r in rows.values()) == len(a)
    for x in a.itertuples():
        r = rows[x.kode_proyek]
        assert D[f"W{r}"].value == "Ya"
        assert close(D[f"X{r}"].value, x.rasio_biaya), x.kode_proyek
        assert close(D[f"Y{r}"].value, x.rasio_durasi), x.kode_proyek


def test_excel_early_warning_reference_margin(data, wb):
    _, periode, a = data
    ew = an.early_warning(an.milestone_snapshots(an.project_periods(periode, a)))
    W = wb["Peringatan_Dini"]
    for i, m in ew.iterrows():
        r = 7 + i
        for col, k in zip("DEFGHIJK", ["proyek", "eac_dalam_5pct", "bac_dalam_5pct", "proyek_membengkak",
                                       "proyek_ditandai", "tertangkap", "recall", "presisi"]):
            assert close(W[f"{col}{r}"].value, m[k]), (m.milestone, k)
    rc = an.reference_classes(a).set_index("kelas")
    R = wb["Kelas_Referensi"]
    for r in range(6, 14):
        k = R[f"B{r}"].value
        assert R[f"D{r}"].value == rc.loc[k, "proyek"]
        for col, lv in zip("EFG", ["P50", "P80", "P90"]):
            assert close(R[f"{col}{r}"].value, rc.loc[k, lv]), (k, lv)
    ms = an.margin_scenario(a)
    M = wb["Skenario_Margin"]
    for i, m in ms.iterrows():
        assert M[f"C{6 + i}"].value == m.proyek_rugi
        assert close(M[f"E{6 + i}"].value, m.porsi_margin_tergerus_separuh)
        assert close(M[f"F{6 + i}"].value, m.median_margin_realisasi)
