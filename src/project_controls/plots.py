"""Grafik untuk notebook dan README."""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mt
import numpy as np
import pandas as pd

NAVY, GREEN, RED, GREY, LIGHT = "#2F3368", "#2E9E5B", "#C0392B", "#8C8C8C", "#D9D9D9"
JENIS_COLORS = {"Perumahan": "#2F3368", "Sipil & infrastruktur": "#2E9E5B",
                "Gedung komersial & institusi": "#C77C02", "Industri & engineering": "#C0392B"}
PCT = mt.PercentFormatter(1.0, decimals=0)


def style():
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 150, "savefig.bbox": "tight", "font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#A6A6A6", "axes.titleweight": "bold",
        "axes.titlesize": 11, "axes.titlelocation": "left", "axes.grid": True, "grid.color": "#ECECEC",
        "grid.linewidth": 0.8, "xtick.color": "#595959", "ytick.color": "#595959", "legend.frameon": False,
    })


def funnel(proyek: pd.DataFrame, ax=None):
    ax = ax or plt.subplots(figsize=(8, 2.8))[1]
    steps = [("File proyek di DSLIB", len(proyek)),
             ("Punya laporan pemantauan", int((proyek.jumlah_periode > 0).sum())),
             ("Selesai pada laporan terakhir", int(proyek.status_pemantauan.eq("Selesai").sum())),
             ("Konstruksi & engineering, biaya tercatat", int(proyek.masuk_analisis.eq("Ya").sum()))]
    y = np.arange(len(steps))[::-1]
    ax.barh(y, [s[1] for s in steps], color=[LIGHT, LIGHT, LIGHT, NAVY], height=0.62)
    for yi, (lab, v) in zip(y, steps):
        ax.text(v + 3, yi, f"{v}", va="center", fontsize=9, fontweight="bold")
    ax.set_yticks(y, [s[0] for s in steps]); ax.grid(False); ax.set_xlim(0, 260); ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Dari 231 file proyek ke 119 proyek yang dianalisis")
    return ax


def outcome_scatter(a: pd.DataFrame, ax=None):
    ax = ax or plt.subplots(figsize=(8, 5))[1]
    for j, c in JENIS_COLORS.items():
        g = a[a.jenis_pekerjaan == j]
        ax.scatter(g.rasio_durasi, g.rasio_biaya, s=26, color=c, alpha=0.85, edgecolor="white", linewidth=0.6,
                   label=f"{j} ({len(g)})", zorder=3)
    ax.axhline(1, color=GREY, lw=0.9); ax.axvline(1, color=GREY, lw=0.9)
    ax.set_xlabel("Rasio durasi (aktual / rencana)"); ax.set_ylabel("Rasio biaya (aktual / anggaran)")
    ax.text(0.99, 0.98, "terlambat & di atas anggaran", transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#595959")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Realisasi biaya dan jadwal 119 proyek")
    return ax


def group_bars(g: pd.DataFrame, ax=None):
    """g: hasil analysis.by_group (index = kelas)."""
    ax = ax or plt.subplots(figsize=(8, 3.2))[1]
    g = g.sort_values("porsi_di_atas_anggaran")
    y = np.arange(len(g))
    ax.barh(y + 0.18, g.median_rasio_biaya - 1, height=0.34, color="#9DA3CF", label="Median")
    ax.barh(y - 0.18, g.p80_rasio_biaya - 1, height=0.34, color=NAVY, label="P80")
    for yi, (_, r) in zip(y, g.iterrows()):
        ax.text(max(r.median_rasio_biaya - 1, 0) + 0.002, yi + 0.18, f"{r.median_rasio_biaya - 1:+.1%}", va="center",
                fontsize=7.5, color="#595959")
        ax.text(r.p80_rasio_biaya - 1 + 0.002, yi - 0.18, f"{r.p80_rasio_biaya - 1:+.1%}", va="center", fontsize=8,
                fontweight="bold", color=NAVY)
        ax.text(0.128, yi, f"{r.porsi_di_atas_anggaran:.0%}", va="center", ha="right", fontsize=9, fontweight="bold",
                color=RED if r.porsi_di_atas_anggaran >= 0.5 else "#404040")
    ax.text(0.128, len(g) - 0.45, "proyek di atas\nanggaran", ha="right", va="bottom", fontsize=7.5, color="#595959")
    ax.set_yticks(y, [f"{i} ({int(r.proyek)})" for i, r in g.iterrows()])
    ax.set_xlim(0, 0.13)
    ax.xaxis.set_major_locator(mt.MultipleLocator(0.02))
    ax.xaxis.set_major_formatter(mt.PercentFormatter(1.0, decimals=0)); ax.axvline(0, color=GREY, lw=0.9)
    ax.set_xlabel("Biaya akhir di atas anggaran"); ax.legend(loc="lower center", bbox_to_anchor=(0.45, -0.32), ncols=2)
    ax.set_title("Pembengkakan biaya per jenis pekerjaan")
    return ax


def cpi_by_progress(pp: pd.DataFrame, overrun: float = 0.05, ax=None):
    """Median CPI per pita progres, dipisah antara proyek yang akhirnya membengkak dan tidak."""
    ax = ax or plt.subplots(figsize=(8, 3.6))[1]
    d = pp[(pp.progres < 0.9999) & pp.cpi.notna()].copy()
    d["pita"] = pd.cut(d.progres, np.arange(0, 1.01, 0.1), right=False)
    d["grup"] = np.where(d.rasio_biaya > 1 + overrun, "Akhirnya membengkak > 5%", "Tidak membengkak")
    # satu nilai per proyek per pita (rata-rata), agar proyek dengan banyak periode tidak mendominasi
    d = d.groupby(["grup", "kode_proyek", "pita"], observed=True, as_index=False).cpi.mean()
    for grp, col in [("Tidak membengkak", GREEN), ("Akhirnya membengkak > 5%", RED)]:
        g = d[d.grup == grp].groupby("pita", observed=True).cpi
        mid = [iv.left + 0.05 for iv in g.median().index]
        ax.plot(mid, g.median().values, marker="o", ms=4, color=col, lw=1.8, label=grp)
        ax.fill_between(mid, g.quantile(0.25).values, g.quantile(0.75).values, color=col, alpha=0.12, lw=0)
    ax.axhline(0.95, color=GREY, lw=0.9, ls="--"); ax.text(0.01, 0.952, "batas 0,95", fontsize=7.5, color="#595959")
    ax.axvline(0.5, color=LIGHT, lw=6, zorder=0)
    ax.xaxis.set_major_formatter(PCT); ax.set_xlabel("Progres proyek (EV / BAC)"); ax.set_ylabel("CPI (median, pita = kuartil)")
    ax.legend(loc="lower left"); ax.set_title("CPI proyek yang akhirnya membengkak turun sejak awal pelaksanaan")
    return ax


def early_warning(ew: pd.DataFrame, ax=None):
    ax = ax or plt.subplots(figsize=(8, 3.4))[1]
    x = ew.milestone
    ax.plot(x, ew.eac_dalam_5pct, marker="o", color=NAVY, lw=2, label="EAC = BAC/CPI meleset <= 5%")
    ax.plot(x, ew.bac_dalam_5pct, marker="o", color=GREY, lw=1.6, ls="--", label="Anggaran awal meleset <= 5%")
    ax.plot(x, ew.recall, marker="s", color=GREEN, lw=1.6, label="Proyek membengkak yang tertangkap CPI < 0,95")
    for xi, v in zip(x, ew.eac_dalam_5pct):
        ax.annotate(f"{v:.0%}", (xi, v), textcoords="offset points", xytext=(9, -13), ha="center", fontsize=8, color=NAVY)
    ax.xaxis.set_major_formatter(PCT); ax.yaxis.set_major_formatter(PCT); ax.set_ylim(0.4, 1.0)
    ax.set_xticks(x); ax.set_xlabel("Progres saat dinilai"); ax.set_ylabel("Porsi proyek")
    ax.legend(loc="lower right", fontsize=8); ax.set_title("Mulai progres 50%, perkiraan EAC lebih tepat daripada anggaran awal")
    return ax


def reference_classes(rc: pd.DataFrame, ax=None):
    ax = ax or plt.subplots(figsize=(8, 3.4))[1]
    r = rc.iloc[::-1].reset_index(drop=True)
    y = np.arange(len(r))
    ax.hlines(y, r.P50 - 1, r.P90 - 1, color=LIGHT, lw=6)
    ax.scatter(r.P50 - 1, y, color="#9DA3CF", s=34, label="P50", zorder=3)
    ax.scatter(r.P80 - 1, y, color=NAVY, s=46, label="P80 (kontinjensi yang disarankan)", zorder=3)
    ax.scatter(r.P90 - 1, y, color=RED, s=30, label="P90", zorder=3)
    for yi, v in zip(y, r.P80 - 1):
        ax.text(v, yi + 0.28, f"{v:.1%}", ha="center", fontsize=7.5, color=NAVY)
    ax.set_yticks(y, [f"{k} ({n})" for k, n in zip(r.kelas, r.proyek)])
    ax.xaxis.set_major_formatter(mt.PercentFormatter(1.0, decimals=0)); ax.axvline(0, color=GREY, lw=0.9)
    ax.xaxis.set_major_locator(mt.MultipleLocator(0.05))
    ax.set_xlabel("Kontinjensi terhadap estimasi biaya")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncols=3, fontsize=8)
    ax.set_title("Kontinjensi tender per kelas referensi")
    return ax


def margin(ms: pd.DataFrame, ax=None):
    ax = ax or plt.subplots(figsize=(6.5, 3))[1]
    x = np.arange(len(ms))
    ax.bar(x - 0.18, ms.porsi_rugi, width=0.36, color=RED, label="Merugi")
    ax.bar(x + 0.18, ms.porsi_margin_tergerus_separuh, width=0.36, color="#E8A39B", label="Margin tergerus > separuh")
    for xi, v in zip(x, ms.porsi_rugi):
        ax.text(xi - 0.18, v + 0.008, f"{v:.0%}", ha="center", fontsize=8)
    ax.set_xticks(x, [f"{m:.0%}" for m in ms.margin_rencana]); ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Margin kontrak rencana"); ax.set_ylabel("Porsi proyek"); ax.legend()
    ax.set_title("Proyek yang merugi menurut margin kontrak")
    return ax


def productivity(b: pd.DataFrame, ax=None):
    ax = ax or plt.subplots(figsize=(6.5, 3.6))[1]
    for j, c in JENIS_COLORS.items():
        g = b[b.jenis_pekerjaan == j]
        if len(g):
            ax.scatter(g.pf_tenaga_kerja, g.rasio_durasi, color=c, s=30, edgecolor="white", label=f"{j} ({len(g)})", zorder=3)
    ax.axvline(1, color=GREY, lw=0.9); ax.axhline(1, color=GREY, lw=0.9)
    ax.set_xlabel("PF jam kerja (earned / aktual)"); ax.set_ylabel("Rasio durasi"); ax.legend(fontsize=7.5)
    ax.set_title("Produktivitas jam kerja vs keterlambatan (38 proyek)")
    return ax


def s_curve(g: pd.DataFrame, name: str, bac: float):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(g.tanggal_status, g.pv / bac, color=GREY, lw=1.6, ls="--", label="Rencana (PV)")
    a1.plot(g.tanggal_status, g.ev / bac, color=NAVY, lw=2, label="Hasil (EV)")
    a1.plot(g.tanggal_status, g.ac / bac, color=RED, lw=1.6, label="Biaya aktual (AC)")
    a1.yaxis.set_major_formatter(PCT); a1.set_ylabel("% dari anggaran"); a1.legend(loc="upper left")
    a1.set_title(f"Kurva S dan indeks kinerja: {name}")
    a2.plot(g.tanggal_status, g.cpi, color=RED, lw=1.6, label="CPI")
    a2.plot(g.tanggal_status, g.spi, color=GREEN, lw=1.6, label="SPI")
    a2.axhline(0.95, color=GREY, lw=0.9, ls="--"); a2.set_ylabel("Indeks"); a2.legend(loc="lower left", ncols=2)
    return fig
