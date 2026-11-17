"""Mengubah 231 file proyek DSLIB menjadi tabel analisis.

Keluaran (folder data/processed):
    proyek.csv               satu baris per proyek (rencana, realisasi akhir, rekonsiliasi dengan ringkasan DSLIB)
    aktivitas.csv            satu baris per aktivitas (baseline)
    periode_proyek.csv       satu baris per proyek per periode pemantauan (PV, EV, AC, jam kerja)
    aktivitas_periode.csv.gz satu baris per aktivitas per periode (detail)
Keluaran (folder data/status_reports):
    <kode>.csv               laporan status per proyek per paket pekerjaan, satu file per proyek,
                             bahan konsolidasi di Power Query
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import protrack as pt

SECTOR_MAP = {  # label sumber -> label bersih (huruf besar/kecil di sumber tidak konsisten)
    "construction (residential building)": "Konstruksi - Perumahan",
    "construction (civil)": "Konstruksi - Sipil",
    "construction (commercial building)": "Konstruksi - Gedung Komersial",
    "construction (institutional building)": "Konstruksi - Gedung Institusi",
    "construction (industrial)": "Konstruksi - Industri",
    "engineering": "Engineering",
    "it": "IT",
    "event management": "Event",
    "mobility": "Mobilitas",
    "education": "Pendidikan",
}


def extract_archive(zip_path: Path, out_dir: Path) -> list[Path]:
    """Ekstrak DSLIB.zip; file proyek bisa berupa .p2x atau .p2x.zip."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out_dir)
    return sorted(p for p in out_dir.iterdir() if re.match(r"C\d{4}-\d+", p.name) and ".p2x" in p.name)


def read_summary(xlsx: Path) -> pd.DataFrame:
    """Lembar ringkasan resmi DSLIB (DSLIB_Analysis_Sheet.xlsx, sheet DSLIB)."""
    raw = pd.read_excel(xlsx, sheet_name="DSLIB", header=None)
    top = raw.iloc[0].ffill()
    cols = [f"{a}|{b}" for a, b in zip(top, raw.iloc[2])]
    d = raw.iloc[3:].copy()
    d.columns = cols
    d = d[d.iloc[:, 0].astype(str).str.match(r"C\d{4}-")]
    num = lambda c: pd.to_numeric(d[c], errors="coerce")
    return pd.DataFrame({
        "kode_proyek": d.iloc[:, 0].astype(str).str.strip(),
        "sektor_sumber": d["Project database|Sector"].astype(str).str.strip(),
        "kata_kunci": d["Project database|Keywords"].fillna("").astype(str).str.strip(),
        "bac_ringkasan": num("General|BAC"),
        "durasi_rencana_ringkasan": num("General|PD (days)"),
        "biaya_aktual_ringkasan": num("Performance metrics|Cost"),
        "durasi_aktual_ringkasan": num("Performance metrics|Duration"),
        "deviasi_biaya_ringkasan": num("Tracking|Under/over budget"),
    }).reset_index(drop=True)


RES_SHARE_MIN = 0.05   # biaya sumber daya minimal 5% dari anggaran
RES_MATCH_TOL = 0.05   # biaya aktual akhir dalam +/-5% dari anggaran tanpa sumber daya


def resource_cost_excluded(p: pt.Project) -> bool:
    """Deteksi proyek yang biaya aktualnya dicatat tanpa biaya sumber daya.

    Di sebagian proyek (batch 2024-2025) biaya aktual akhir sama dengan anggaran TANPA biaya sumber daya,
    sedangkan anggaran di file memuat biaya sumber daya. Bila dibiarkan, proyek tampak hemat 10-64%.
    Untuk proyek seperti ini biaya sumber daya diperlakukan sebagai data kapasitas, bukan biaya."""
    if not p.periods or p.bac <= 0:
        return False
    res = p.resource_cost
    if res / p.bac < RES_SHARE_MIN or p.bac - res <= 0:
        return False
    rows = [r for r in pt.activity_period_rows(p) if r["periode"] == len(p.periods)]
    ac = sum(r["ac"] for r in rows)
    return abs(ac / (p.bac - res) - 1) <= RES_MATCH_TOL


def _work_days(cal: pt.Calendar, a, b) -> float:
    return cal.working_hours_between(a, b) / cal.hours_per_day


def build(project_files: list[Path], summary: pd.DataFrame):
    proj, acts, per, actper, wp = [], [], [], [], []
    for f in project_files:
        p = pt.load_project(f)
        excluded = resource_cost_excluded(p)
        if excluded:
            p.set_budget_resources(False)
        cal = p.calendar
        bac = p.bac
        plan_wh = sum(a.planned_work_h for a in p.activities.values())
        for a in p.activities.values():
            acts.append(dict(kode_proyek=p.code, id_aktivitas=a.aid, nama_aktivitas=a.name, paket_pekerjaan=a.group,
                             mulai_rencana=a.start, selesai_rencana=a.end, durasi_rencana_jam=a.duration_h,
                             biaya_rencana=a.total_cost, jam_kerja_rencana=a.planned_work_h))
        row = dict(kode_proyek=p.code, nama_proyek=p.name, mata_uang=p.currency, jumlah_aktivitas=len(p.activities),
                   jumlah_sumber_daya=len(p.resources), jam_kerja_per_hari=cal.hours_per_day,
                   mulai_rencana=p.start, selesai_rencana=p.end,
                   durasi_rencana_hari=_work_days(cal, p.start, p.end), bac=bac, jam_kerja_rencana=plan_wh,
                   jumlah_periode=len(p.periods), biaya_sumber_daya=p.resource_cost,
                   biaya_sumber_daya_di_anggaran="Tidak" if excluded else "Ya")
        if p.periods:
            ap = pd.DataFrame(list(pt.activity_period_rows(p)))
            ap = ap.merge(pd.DataFrame([dict(id_aktivitas=a.aid, paket_pekerjaan=a.group, biaya_rencana=a.total_cost)
                                        for a in p.activities.values()]), on="id_aktivitas")
            actper.append(ap)
            g = ap.groupby(["periode", "tanggal_status"], as_index=False)[
                ["pv", "ev", "ac", "jam_kerja_earned", "jam_kerja_aktual"]].sum()
            g.insert(0, "kode_proyek", p.code)
            per.append(g)
            w = ap.groupby(["periode", "tanggal_status", "paket_pekerjaan"], as_index=False).agg(
                bac_paket=("biaya_rencana", "sum"), pv=("pv", "sum"), ev=("ev", "sum"), ac=("ac", "sum"),
                jam_kerja_rencana=("jam_kerja_rencana", "sum"), jam_kerja_earned=("jam_kerja_earned", "sum"),
                jam_kerja_aktual=("jam_kerja_aktual", "sum"))
            w.insert(0, "kode_proyek", p.code)
            wp.append(w)
            # realisasi akhir = periode terakhir. Durasi aktual dihitung dari mulai rencana sampai tanggal
            # status terakhir (hari kerja), definisi yang sama dengan ringkasan resmi DSLIB.
            last = ap[ap.periode == ap.periode.max()]
            status = last.tanggal_status.iloc[0]
            started = last[last.mulai_aktual.notna()]
            ev, ac = last.ev.sum(), last.ac.sum()
            row.update(tanggal_status_akhir=status, ev_akhir=ev, ac_akhir=ac,
                       persen_selesai_akhir=100 * ev / bac if bac else np.nan,
                       mulai_aktual=started.mulai_aktual.min() if len(started) else pd.NaT,
                       durasi_aktual_hari=_work_days(cal, p.start, status),
                       jam_kerja_earned_akhir=last.jam_kerja_earned.sum(), jam_kerja_aktual_akhir=last.jam_kerja_aktual.sum())
        proj.append(row)

    proyek = pd.DataFrame(proj).merge(summary, on="kode_proyek", how="left")
    proyek["sektor"] = proyek.sektor_sumber.str.lower().map(SECTOR_MAP)
    proyek["kelompok_sektor"] = np.where(proyek.sektor.str.startswith("Konstruksi"), "Konstruksi",
                                         np.where(proyek.sektor.eq("Engineering"), "Engineering", "Non-konstruksi"))
    selesai = proyek.persen_selesai_akhir >= 99.99  # toleransi pembulatan laporan status
    proyek["status_pemantauan"] = np.select(
        [proyek.jumlah_periode.eq(0), selesai], ["Tanpa data pemantauan", "Selesai"], "Belum selesai")
    return proyek, pd.DataFrame(acts), pd.concat(per, ignore_index=True), pd.concat(wp, ignore_index=True), \
        pd.concat(actper, ignore_index=True)


QUALITY_NOTES = {
    "C2023-11": "Biaya aktual tidak tercatat di file (AC = 0 di semua periode); dikeluarkan dari analisis biaya.",
}


def add_quality_flags(proyek: pd.DataFrame) -> pd.DataFrame:
    """Tandai proyek yang dipakai untuk analisis kinerja dan catat hasil rekonsiliasi dengan ringkasan DSLIB."""
    p = proyek.copy()
    note = []
    for r in p.itertuples():
        n = []
        if r.biaya_sumber_daya_di_anggaran == "Tidak":
            n.append("Biaya aktual dicatat tanpa biaya sumber daya; anggaran disesuaikan (tanpa biaya sumber daya).")
        if pd.notna(r.bac_ringkasan) and abs(r.bac / r.bac_ringkasan - 1) >= 1e-3:
            n.append(f"Anggaran di ringkasan DSLIB berbeda {r.bac_ringkasan / r.bac - 1:+.1%} dari file proyek.")
        if pd.isna(r.bac_ringkasan):
            n.append("Anggaran tidak diisi di ringkasan DSLIB.")
        if r.kode_proyek in QUALITY_NOTES:
            n.append(QUALITY_NOTES[r.kode_proyek])
        note.append(" ".join(n))
    p["catatan_kualitas"] = note
    # dianalisis: selesai, konstruksi/engineering, dan biaya aktual tercatat (AC > 0)
    p["masuk_analisis"] = np.where(
        p.status_pemantauan.eq("Selesai") & p.kelompok_sektor.isin(["Konstruksi", "Engineering"])
        & p.ac_akhir.gt(0), "Ya", "Tidak")
    return p


def write_outputs(root: Path, proyek, aktivitas, periode, paket, aktivitas_periode):
    out = root / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    fmt = dict(index=False, float_format="%.4f", date_format="%Y-%m-%d %H:%M")
    proyek.to_csv(out / "proyek.csv", **fmt)
    aktivitas.to_csv(out / "aktivitas.csv", **fmt)
    periode.to_csv(out / "periode_proyek.csv", **fmt)
    aktivitas_periode.to_csv(out / "aktivitas_periode.csv.gz", compression="gzip", **fmt)
    # laporan status per proyek: format laporan site berbahasa Belanda/Eropa (pemisah ';', desimal ',')
    rep = root / "data" / "status_reports"
    rep.mkdir(parents=True, exist_ok=True)
    for old in rep.glob("*.csv"):
        old.unlink()
    meta = proyek.set_index("kode_proyek")
    cols = {"periode": "Periode", "tanggal_status": "Tanggal Status", "paket_pekerjaan": "Paket Pekerjaan",
            "bac_paket": "Anggaran Paket", "pv": "Nilai Rencana (PV)", "ev": "Nilai Hasil (EV)", "ac": "Biaya Aktual (AC)",
            "jam_kerja_rencana": "Jam Kerja Rencana", "jam_kerja_earned": "Jam Kerja Earned", "jam_kerja_aktual": "Jam Kerja Aktual"}
    for code, g in paket.groupby("kode_proyek"):
        m = meta.loc[code]
        r = g.rename(columns=cols)[list(cols.values())].copy()
        r.insert(0, "Kode Proyek", code)
        r.insert(1, "Nama Proyek", m.nama_proyek)
        r.insert(2, "Mata Uang", m.mata_uang)
        r["Tanggal Status"] = pd.to_datetime(r["Tanggal Status"]).dt.strftime("%d/%m/%Y")
        r.to_csv(rep / f"{code}.csv", sep=";", decimal=",", index=False, float_format="%.2f", encoding="utf-8-sig")
