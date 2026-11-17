# Panduan dashboard Power BI

Folder ini berisi bahan untuk membangun dashboard di Power BI Desktop: rumus DAX (`measures.dax`), tema warna (`tema_dashboard.json`), dan rancangan halaman di bawah. Data yang dipakai sama dengan workbook Excel.

## 1. Memuat data

| Tabel | Sumber | Catatan |
|---|---|---|
| Proyek | `data/processed/proyek.csv` | Kunci: `kode_proyek` |
| Periode | `data/processed/periode_proyek.csv` | Satu baris per proyek per periode |
| Laporan_Status | folder `data/status_reports` | Pakai query `02_Laporan_Status.pq` (Power BI memakai bahasa M yang sama) |
| Kelas_Referensi | `data/summary/kelas_referensi.csv` | Faktor P50/P80/P90 |
| Peringatan_Dini | `data/summary/peringatan_dini.csv` | Akurasi EAC dan sinyal CPI per milestone |

Relasi (Model view): `Proyek[kode_proyek]` 1 ke banyak `Periode[kode_proyek]` dan `Laporan_Status[Kode Proyek]`.
Tema: View > Themes > Browse for themes > `tema_dashboard.json`.

## 2. Halaman

**Halaman 1 – Portofolio**
- Kartu: `Proyek Dianalisis`, `% Di Atas Anggaran`, `% Terlambat`, `P80 Rasio Biaya`.
- Bar chart horizontal: sumbu `Jenis Pekerjaan`, nilai `Median Rasio Biaya` dan `P80 Rasio Biaya`.
- Scatter: sumbu X `Rasio Durasi`, sumbu Y `Rasio Biaya`, detail `kode_proyek`, legenda `Jenis Pekerjaan`; garis konstan 1,0 di kedua sumbu.
- Slicer: `Jenis Pekerjaan`, `Kelas Ukuran`. Filter halaman: `masuk_analisis = Ya`.

**Halaman 2 – Status proyek** (slicer `kode_proyek`, single select)
- Line chart: sumbu `Periode[tanggal_status]`, nilai `PV`, `EV`, `AC` (kurva S).
- Line chart: `CPI` dan `SPI` dengan garis konstan `Batas CPI` (0,95).
- Kartu: `BAC Proyek`, `EAC (BAC/CPI)`, `CPI Terakhir`, `Status Proyek`.
- Tabel: `Laporan_Status[Paket Pekerjaan]` dengan anggaran paket, EV, AC pada periode terakhir.

**Halaman 3 – Peringatan dini & tender**
- Line chart dari `Peringatan_Dini`: sumbu `milestone`, nilai `eac_dalam_5pct`, `bac_dalam_5pct`, `recall`.
- Tabel `Kelas_Referensi` (kelas, proyek, P50, P80, P90).
- Kalkulator: parameter what-if `Estimasi Biaya`, slicer `Tingkat`, slicer `Kelas_Referensi[kelas]`, kartu `Faktor Biaya`, `Kontinjensi`, `Biaya + Kontinjensi`.

## 3. Cek angka

Setelah dashboard jadi, angka kartu halaman 1 harus sama dengan sheet `Kinerja_Portofolio` di Excel: 119 proyek, 51,3% di atas anggaran, 72,3% terlambat, P80 rasio biaya 1,058.
