# Power Query: konsolidasi laporan status

Query di folder ini menghasilkan tiga sheet input di workbook Excel: `Laporan_Status`, `Data_Proyek` (kolom biru tua), dan tiga kolom pertama `Data_Periode`.

| File | Nama query | Fungsi |
|---|---|---|
| `00_FolderData.pq` | `FolderData` | Parameter lokasi folder `data` |
| `01_fnBacaLaporan.pq` | `fnBacaLaporan` | Membaca satu file laporan (CSV `;`, UTF-8) |
| `02_Laporan_Status.pq` | `Laporan_Status` | Menggabungkan 155 file di `data/status_reports`, membersihkan teks, dan mengubah tipe data dengan locale `id-ID` (desimal koma, tanggal dd/mm/yyyy) |
| `03_Proyek.pq` | `Proyek` | Master 231 proyek dari `data/processed/proyek.csv`, sel kosong menjadi null sebelum diubah ke angka |
| `04_Kunci_Periode.pq` | `Kunci_Periode` | Daftar unik proyek x periode (referensi ke `Laporan_Status`) |

## Cara memasang di Excel

1. Data > Get Data > Launch Power Query Editor.
2. Home > Manage Parameters > New Parameter: nama `FolderData`, tipe Text, isi dengan path folder `data` di komputer Anda.
3. Untuk setiap file `01`–`04`: Home > New Source > Blank Query, buka Advanced Editor, tempel isi file, lalu ganti nama query sesuai tabel di atas.
4. Close & Load To… > Table, ke sheet yang sesuai. Kolom hitung di sebelah kanan tabel akan ikut memanjang bila baris bertambah.

## Menambah laporan baru

Simpan file laporan proyek baru (format sama, satu file per proyek) ke `data/status_reports`, lalu Data > Refresh All. Validasi di sheet `Validasi` akan menunjukkan apakah total EV/AC di `Data_Periode` masih sama dengan `Laporan_Status`.
