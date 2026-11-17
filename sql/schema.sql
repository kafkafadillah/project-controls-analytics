-- Skema database portofolio proyek (SQLite).
-- Tabel diisi dari data/processed/*.csv oleh src/project_controls/db.py.

DROP VIEW  IF EXISTS v_periode;
DROP VIEW  IF EXISTS v_portofolio;
DROP TABLE IF EXISTS aktivitas_periode;
DROP TABLE IF EXISTS periode_proyek;
DROP TABLE IF EXISTS aktivitas;
DROP TABLE IF EXISTS proyek;

CREATE TABLE proyek (
    kode_proyek                    TEXT PRIMARY KEY,
    nama_proyek                    TEXT NOT NULL,
    mata_uang                      TEXT,
    jumlah_aktivitas               INTEGER,
    jumlah_sumber_daya             INTEGER,
    jam_kerja_per_hari             INTEGER,
    mulai_rencana                  TEXT,
    selesai_rencana                TEXT,
    durasi_rencana_hari            REAL,
    bac                            REAL,          -- anggaran biaya (budget at completion)
    jam_kerja_rencana              REAL,
    jumlah_periode                 INTEGER,
    biaya_sumber_daya              REAL,
    biaya_sumber_daya_di_anggaran  TEXT,
    tanggal_status_akhir           TEXT,
    ev_akhir                       REAL,
    ac_akhir                       REAL,
    persen_selesai_akhir           REAL,
    mulai_aktual                   TEXT,
    durasi_aktual_hari             REAL,
    jam_kerja_earned_akhir         REAL,
    jam_kerja_aktual_akhir         REAL,
    sektor_sumber                  TEXT,
    kata_kunci                     TEXT,
    bac_ringkasan                  REAL,
    durasi_rencana_ringkasan       REAL,
    biaya_aktual_ringkasan         REAL,
    durasi_aktual_ringkasan        REAL,
    deviasi_biaya_ringkasan        REAL,
    sektor                         TEXT,
    kelompok_sektor                TEXT,
    status_pemantauan              TEXT,
    catatan_kualitas               TEXT,
    masuk_analisis                 TEXT CHECK (masuk_analisis IN ('Ya', 'Tidak'))
);

CREATE TABLE aktivitas (
    kode_proyek         TEXT NOT NULL REFERENCES proyek (kode_proyek),
    id_aktivitas        INTEGER NOT NULL,
    nama_aktivitas      TEXT,
    paket_pekerjaan     TEXT,
    mulai_rencana       TEXT,
    selesai_rencana     TEXT,
    durasi_rencana_jam  INTEGER,
    biaya_rencana       REAL,
    jam_kerja_rencana   REAL,
    PRIMARY KEY (kode_proyek, id_aktivitas)
);

CREATE TABLE periode_proyek (
    kode_proyek       TEXT NOT NULL REFERENCES proyek (kode_proyek),
    periode           INTEGER NOT NULL,
    tanggal_status    TEXT NOT NULL,
    pv                REAL,     -- planned value
    ev                REAL,     -- earned value
    ac                REAL,     -- actual cost
    jam_kerja_earned  REAL,
    jam_kerja_aktual  REAL,
    PRIMARY KEY (kode_proyek, periode)
);

CREATE TABLE aktivitas_periode (
    kode_proyek        TEXT NOT NULL,
    periode            INTEGER NOT NULL,
    nama_periode       TEXT,
    tanggal_status     TEXT,
    id_aktivitas       INTEGER NOT NULL,
    pv                 REAL,
    ev                 REAL,
    ac                 REAL,
    persen_selesai     REAL,
    mulai_aktual       TEXT,
    durasi_aktual_jam  INTEGER,
    sisa_durasi_jam    INTEGER,
    jam_kerja_rencana  REAL,
    jam_kerja_earned   REAL,
    jam_kerja_aktual   REAL,
    paket_pekerjaan    TEXT,
    biaya_rencana      REAL,
    PRIMARY KEY (kode_proyek, periode, id_aktivitas),
    FOREIGN KEY (kode_proyek, id_aktivitas) REFERENCES aktivitas (kode_proyek, id_aktivitas)
);

CREATE INDEX ix_periode_proyek ON periode_proyek (kode_proyek, periode);

-- Proyek yang dianalisis (konstruksi & engineering, selesai, data biaya lengkap) beserta rasio realisasi.
CREATE VIEW v_portofolio AS
SELECT p.*,
       p.ac_akhir / p.bac                                  AS rasio_biaya,
       p.durasi_aktual_hari / p.durasi_rencana_hari        AS rasio_durasi,
       p.ev_akhir / p.ac_akhir                             AS cpi_akhir,
       CASE WHEN p.bac < 250000  THEN 'Kecil (< 250 rb)'
            WHEN p.bac < 1000000 THEN 'Menengah (250 rb - 1 jt)'
            ELSE 'Besar (> 1 jt)' END                       AS kelas_ukuran,
       CASE p.sektor
            WHEN 'Konstruksi - Perumahan'        THEN 'Perumahan'
            WHEN 'Konstruksi - Sipil'            THEN 'Sipil & infrastruktur'
            WHEN 'Konstruksi - Gedung Komersial' THEN 'Gedung komersial & institusi'
            WHEN 'Konstruksi - Gedung Institusi' THEN 'Gedung komersial & institusi'
            WHEN 'Konstruksi - Industri'         THEN 'Industri & engineering'
            WHEN 'Engineering'                   THEN 'Industri & engineering'
       END                                                 AS jenis_pekerjaan,
       CASE WHEN p.jam_kerja_aktual_akhir > 0
            THEN p.jam_kerja_earned_akhir / p.jam_kerja_aktual_akhir END AS pf_tenaga_kerja
FROM proyek p
WHERE p.masuk_analisis = 'Ya';

-- Periode pemantauan proyek analisis dengan indikator earned value.
CREATE VIEW v_periode AS
SELECT t.kode_proyek, t.periode, t.tanggal_status, t.pv, t.ev, t.ac,
       v.bac, v.ac_akhir, v.rasio_biaya,
       t.ev / v.bac                                          AS progres,
       t.pv / v.bac                                          AS progres_rencana,
       CASE WHEN t.ac > 0 THEN t.ev / t.ac END               AS cpi,
       CASE WHEN t.pv > 0 THEN t.ev / t.pv END               AS spi,
       CASE WHEN t.ac > 0 AND t.ev > 0 THEN v.bac * t.ac / t.ev END AS eac_cpi
FROM periode_proyek t
JOIN v_portofolio v USING (kode_proyek);
