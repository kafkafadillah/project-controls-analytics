-- Kueri analisis. Setiap kueri diawali baris "-- name: <nama>" agar bisa dipanggil dari Python.

-- name: ringkasan_portofolio
-- Kinerja akhir proyek analisis: berapa yang melampaui anggaran dan jadwal.
SELECT COUNT(*)                                                     AS proyek,
       AVG(CASE WHEN rasio_biaya  > 1.005 THEN 1.0 ELSE 0 END)      AS di_atas_anggaran,
       AVG(CASE WHEN rasio_biaya  < 0.995 THEN 1.0 ELSE 0 END)      AS di_bawah_anggaran,
       AVG(CASE WHEN rasio_biaya  > 1.05  THEN 1.0 ELSE 0 END)      AS membengkak_material,
       AVG(CASE WHEN rasio_durasi > 1.005 THEN 1.0 ELSE 0 END)      AS terlambat
FROM v_portofolio;

-- name: kinerja_per_jenis
-- Rasio biaya akhir/anggaran per jenis pekerjaan; median dan P80 dihitung seperti PERCENTILE.INC di Excel.
WITH urut AS (
    SELECT jenis_pekerjaan, rasio_biaya, rasio_durasi,
           ROW_NUMBER() OVER (PARTITION BY jenis_pekerjaan ORDER BY rasio_biaya) - 1 AS i,
           COUNT(*)     OVER (PARTITION BY jenis_pekerjaan)                          AS n
    FROM v_portofolio
),
pos AS (
    SELECT DISTINCT jenis_pekerjaan, n, q,
           (n - 1) * q                       AS h,
           CAST((n - 1) * q AS INTEGER)      AS lo
    FROM urut, (SELECT 0.5 AS q UNION ALL SELECT 0.8)
),
persentil AS (
    SELECT p.jenis_pekerjaan, p.q,
           MAX(CASE WHEN u.i = p.lo     THEN u.rasio_biaya END)
         + (p.h - p.lo) * (COALESCE(MAX(CASE WHEN u.i = p.lo + 1 THEN u.rasio_biaya END),
                                    MAX(CASE WHEN u.i = p.lo     THEN u.rasio_biaya END))
                         - MAX(CASE WHEN u.i = p.lo THEN u.rasio_biaya END)) AS nilai
    FROM pos p JOIN urut u ON u.jenis_pekerjaan = p.jenis_pekerjaan
    GROUP BY p.jenis_pekerjaan, p.q
)
SELECT u.jenis_pekerjaan,
       COUNT(*)                                                     AS proyek,
       (SELECT nilai FROM persentil s WHERE s.jenis_pekerjaan = u.jenis_pekerjaan AND s.q = 0.5) AS median_rasio_biaya,
       (SELECT nilai FROM persentil s WHERE s.jenis_pekerjaan = u.jenis_pekerjaan AND s.q = 0.8) AS p80_rasio_biaya,
       AVG(CASE WHEN u.rasio_biaya > 1.005 THEN 1.0 ELSE 0 END)     AS porsi_di_atas_anggaran
FROM urut u
GROUP BY u.jenis_pekerjaan
ORDER BY proyek DESC;

-- name: status_terakhir
-- Kondisi setiap proyek pada periode pemantauan terakhir (bahan dashboard status proyek).
WITH terakhir AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY kode_proyek ORDER BY periode DESC) AS rn
    FROM v_periode
)
SELECT t.kode_proyek, p.nama_proyek, p.jenis_pekerjaan, t.periode, t.tanggal_status,
       t.progres, t.cpi, t.spi, t.eac_cpi, t.bac,
       CASE WHEN t.cpi < 0.95 THEN 'Biaya di atas rencana'
            WHEN t.spi < 0.95 THEN 'Jadwal tertinggal'
            ELSE 'Sesuai rencana' END AS status
FROM terakhir t JOIN v_portofolio p USING (kode_proyek)
WHERE t.rn = 1
ORDER BY t.kode_proyek;

-- name: peringatan_dini_50
-- Periode pertama ketika progres mencapai 50%: apakah CPI < 0,95 menandai proyek yang akhirnya membengkak > 5%?
WITH pertama AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY kode_proyek ORDER BY periode) AS rn
    FROM v_periode
    WHERE progres >= 0.5 AND progres < 0.9999 AND cpi IS NOT NULL
)
SELECT COUNT(*)                                                                    AS proyek,
       SUM(CASE WHEN rasio_biaya > 1.05 THEN 1 ELSE 0 END)                         AS proyek_membengkak,
       SUM(CASE WHEN cpi < 0.95 THEN 1 ELSE 0 END)                                 AS proyek_ditandai,
       SUM(CASE WHEN cpi < 0.95 AND rasio_biaya > 1.05 THEN 1 ELSE 0 END)          AS tertangkap,
       AVG(CASE WHEN ABS(eac_cpi / ac_akhir - 1) <= 0.05 THEN 1.0 ELSE 0 END)      AS eac_dalam_5pct,
       AVG(CASE WHEN ABS(bac / ac_akhir - 1) <= 0.05 THEN 1.0 ELSE 0 END)          AS bac_dalam_5pct
FROM pertama
WHERE rn = 1;

-- name: produktivitas
-- Faktor produktivitas jam kerja (earned / aktual) untuk proyek yang mencatat jam kerja.
SELECT kode_proyek, nama_proyek, jenis_pekerjaan, jam_kerja_earned_akhir, jam_kerja_aktual_akhir,
       pf_tenaga_kerja, rasio_biaya, rasio_durasi
FROM v_portofolio
WHERE pf_tenaga_kerja IS NOT NULL
ORDER BY pf_tenaga_kerja;

-- name: rekonsiliasi_ringkasan
-- Proyek yang anggarannya berbeda dengan ringkasan resmi DSLIB (> 0,1%).
SELECT kode_proyek, nama_proyek, bac, bac_ringkasan, bac_ringkasan / bac - 1 AS selisih, catatan_kualitas
FROM proyek
WHERE bac_ringkasan IS NOT NULL AND ABS(bac_ringkasan / bac - 1) >= 0.001
ORDER BY ABS(bac_ringkasan / bac - 1) DESC;
