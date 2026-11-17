"""Analisis kinerja portofolio proyek: realisasi biaya & jadwal, peringatan dini, produktivitas,
kelas referensi untuk estimasi tender, dan skenario margin.

Semua rasio tidak bergantung pada mata uang, sehingga proyek dengan nilai sangat berbeda bisa dibandingkan.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SIZE_BINS = [0, 250_000, 1_000_000, np.inf]
SIZE_LABELS = ["Kecil (< 250 rb)", "Menengah (250 rb - 1 jt)", "Besar (> 1 jt)"]
WORK_TYPE = {
    "Konstruksi - Perumahan": "Perumahan",
    "Konstruksi - Sipil": "Sipil & infrastruktur",
    "Konstruksi - Gedung Komersial": "Gedung komersial & institusi",
    "Konstruksi - Gedung Institusi": "Gedung komersial & institusi",
    "Konstruksi - Industri": "Industri & engineering",
    "Engineering": "Industri & engineering",
}
LEVELS = (0.5, 0.8, 0.9)


@dataclass(frozen=True)
class Params:
    cpi_warning: float = 0.95      # CPI di bawah ini = sinyal peringatan
    overrun_material: float = 0.05  # pembengkakan biaya > 5% dianggap material
    milestones: tuple = (0.10, 0.25, 0.50, 0.75, 0.90)
    margin: float = 0.10           # asumsi margin kontrak terhadap anggaran biaya (skenario)
    tol_on_budget: float = 0.005   # |rasio - 1| <= 0,5% dianggap sesuai anggaran
    done: float = 0.9999           # progres >= nilai ini dianggap selesai (toleransi pembulatan laporan)


def percentile_inc(x, q):
    """Sama dengan PERCENTILE.INC di Excel (interpolasi linear)."""
    x = np.sort(np.asarray(x, dtype=float))
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return np.nan
    return float(np.percentile(x, q * 100, method="linear"))


def portfolio(proyek: pd.DataFrame) -> pd.DataFrame:
    """Proyek yang masuk analisis beserta rasio realisasi."""
    a = proyek[proyek.masuk_analisis.eq("Ya")].copy()
    a["rasio_biaya"] = a.ac_akhir / a.bac
    a["rasio_durasi"] = a.durasi_aktual_hari / a.durasi_rencana_hari
    a["cpi_akhir"] = a.ev_akhir / a.ac_akhir
    a["kelas_ukuran"] = pd.cut(a.bac, SIZE_BINS, labels=SIZE_LABELS, right=False).astype(str)
    a["jenis_pekerjaan"] = a.sektor.map(WORK_TYPE)
    a["pf_tenaga_kerja"] = np.where(a.jam_kerja_aktual_akhir > 0, a.jam_kerja_earned_akhir / a.jam_kerja_aktual_akhir, np.nan)
    return a.reset_index(drop=True)


def outcome_status(r: pd.Series, p: Params) -> str:
    if r > 1 + p.tol_on_budget:
        return "Di atas anggaran"
    if r < 1 - p.tol_on_budget:
        return "Di bawah anggaran"
    return "Sesuai anggaran"


def summary(a: pd.DataFrame, p: Params = Params()) -> dict:
    rb, rd = a.rasio_biaya, a.rasio_durasi
    return {
        "proyek": len(a),
        "di_atas_anggaran": float((rb > 1 + p.tol_on_budget).mean()),
        "di_bawah_anggaran": float((rb < 1 - p.tol_on_budget).mean()),
        "membengkak_material": float((rb > 1 + p.overrun_material).mean()),
        "terlambat": float((rd > 1 + p.tol_on_budget).mean()),
        "median_rasio_biaya": float(rb.median()),
        "p80_rasio_biaya": percentile_inc(rb, 0.8),
        "p90_rasio_biaya": percentile_inc(rb, 0.9),
        "median_rasio_durasi": float(rd.median()),
        "korelasi_biaya_durasi_spearman": float(a[["rasio_biaya", "rasio_durasi"]].corr("spearman").iloc[0, 1]),
    }


def by_group(a: pd.DataFrame, col: str) -> pd.DataFrame:
    g = a.groupby(col).agg(proyek=("kode_proyek", "size"),
                           median_rasio_biaya=("rasio_biaya", "median"),
                           p80_rasio_biaya=("rasio_biaya", lambda s: percentile_inc(s, 0.8)),
                           median_rasio_durasi=("rasio_durasi", "median"),
                           porsi_di_atas_anggaran=("rasio_biaya", lambda s: (s > 1.005).mean()))
    return g.sort_values("proyek", ascending=False)


def project_periods(periode: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """Periode pemantauan proyek analisis, dengan progres, CPI, SPI dan EAC."""
    p = periode[periode.kode_proyek.isin(a.kode_proyek)].merge(
        a[["kode_proyek", "bac", "ac_akhir", "rasio_biaya"]], on="kode_proyek")
    p = p.sort_values(["kode_proyek", "periode"]).reset_index(drop=True)
    p["progres"] = p.ev / p.bac
    p["progres_rencana"] = p.pv / p.bac
    p["cpi"] = np.where(p.ac > 0, p.ev / p.ac, np.nan)
    p["spi"] = np.where(p.pv > 0, p.ev / p.pv, np.nan)
    p["eac_cpi"] = np.where(p.cpi > 0, p.bac / p.cpi, np.nan)
    return p


def milestone_snapshots(pp: pd.DataFrame, p: Params = Params()) -> pd.DataFrame:
    """Periode pertama ketika progres (EV/BAC) mencapai tiap milestone, sebelum proyek selesai."""
    out = []
    for m in p.milestones:
        q = pp[(pp.progres >= m) & (pp.progres < p.done) & pp.cpi.notna()]
        q = q.groupby("kode_proyek", as_index=False).head(1).copy()
        q.insert(0, "milestone", m)
        out.append(q)
    return pd.concat(out, ignore_index=True)


def early_warning(snap: pd.DataFrame, p: Params = Params()) -> pd.DataFrame:
    rows = []
    for m, q in snap.groupby("milestone"):
        err_eac = q.eac_cpi / q.ac_akhir - 1
        err_bac = q.bac / q.ac_akhir - 1
        over = q.rasio_biaya > 1 + p.overrun_material
        flag = q.cpi < p.cpi_warning
        rows.append(dict(milestone=m, proyek=len(q),
                         eac_dalam_5pct=float((err_eac.abs() <= 0.05).mean()),
                         bac_dalam_5pct=float((err_bac.abs() <= 0.05).mean()),
                         median_galat_eac=float(err_eac.abs().median()),
                         median_galat_bac=float(err_bac.abs().median()),
                         proyek_membengkak=int(over.sum()), proyek_ditandai=int(flag.sum()),
                         tertangkap=int((flag & over).sum()),
                         recall=float((flag & over).sum() / over.sum()) if over.sum() else np.nan,
                         presisi=float((flag & over).sum() / flag.sum()) if flag.sum() else np.nan))
    return pd.DataFrame(rows)


def reference_classes(a: pd.DataFrame, levels=LEVELS) -> pd.DataFrame:
    """Distribusi rasio biaya akhir/anggaran per kelas referensi (dasar kontinjensi tender)."""
    classes = [("Semua proyek", "Semua", a)]
    for col, name in [("jenis_pekerjaan", "Jenis pekerjaan"), ("kelas_ukuran", "Ukuran proyek")]:
        for k, g in a.groupby(col):
            classes.append((name, k, g))
    rows = []
    for dim, k, g in classes:
        r = dict(dimensi=dim, kelas=k, proyek=len(g))
        for lv in levels:
            r[f"P{int(lv * 100)}"] = percentile_inc(g.rasio_biaya, lv)
        rows.append(r)
    return pd.DataFrame(rows)


def loo_backtest(a: pd.DataFrame, col: str | None, level: float, min_n: int = 10) -> dict:
    """Uji mundur leave-one-out: untuk tiap proyek, hitung batas Pxx dari proyek lain di kelas yang sama
    (atau semua proyek bila kelasnya < min_n), lalu cek apakah biaya aktual proyek itu tertutup."""
    hit = []
    for i, r in a.iterrows():
        others = a.drop(index=i)
        if col is not None:
            same = others[others[col] == r[col]]
            others = same if len(same) >= min_n else others
        hit.append(r.rasio_biaya <= percentile_inc(others.rasio_biaya, level))
    return dict(kelas=col or "Semua proyek", level=level, cakupan=float(np.mean(hit)), proyek=len(hit))


def margin_scenario(a: pd.DataFrame, margins=(0.05, 0.08, 0.10, 0.12, 0.15)) -> pd.DataFrame:
    """Nilai kontrak = anggaran biaya x (1 + margin). Margin realisasi = 1 - biaya aktual / nilai kontrak."""
    rows = []
    for m in margins:
        real = 1 - a.rasio_biaya / (1 + m)
        rows.append(dict(margin_rencana=m, median_margin_realisasi=float(real.median()),
                         proyek_rugi=int((real < 0).sum()), porsi_rugi=float((real < 0).mean()),
                         porsi_margin_tergerus_separuh=float((real < m / 2).mean())))
    return pd.DataFrame(rows)


def productivity(a: pd.DataFrame) -> pd.DataFrame:
    """Faktor produktivitas = jam kerja earned / jam kerja aktual (>1 = lebih produktif dari rencana)."""
    b = a[a.pf_tenaga_kerja.notna()].copy()
    b["kelompok_pf"] = pd.cut(b.pf_tenaga_kerja, [0, 0.9, 1.0 - 1e-9, np.inf],
                              labels=["Di bawah 0,90", "0,90 - 0,99", "1,00 ke atas"]).astype(str)
    return b
