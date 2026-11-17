// Query: Laporan_Status
// Menggabungkan semua laporan status di folder data\status_reports (satu file per proyek).
// Laporan memakai format Eropa: desimal koma dan tanggal dd/mm/yyyy, sehingga tipe data diubah dengan locale id-ID.
// Laporan baru cukup disalin ke folder yang sama, lalu Data > Refresh All.
let
    Sumber      = Folder.Files(FolderData & "\status_reports"),
    HanyaCsv    = Table.SelectRows(Sumber, each Text.Lower([Extension]) = ".csv" and not Text.StartsWith([Name], "~")),
    Dibaca      = Table.AddColumn(HanyaCsv, "Isi", each fnBacaLaporan([Content])),
    Ringkas     = Table.SelectColumns(Dibaca, {"Name", "Isi"}),
    Kolom       = {"Kode Proyek", "Nama Proyek", "Mata Uang", "Periode", "Tanggal Status", "Paket Pekerjaan",
                   "Anggaran Paket", "Nilai Rencana (PV)", "Nilai Hasil (EV)", "Biaya Aktual (AC)",
                   "Jam Kerja Rencana", "Jam Kerja Earned", "Jam Kerja Aktual"},
    Digabung    = Table.ExpandTableColumn(Ringkas, "Isi", Kolom),
    TanpaFile   = Table.RemoveColumns(Digabung, {"Name"}),
    Rapi        = Table.TransformColumns(TanpaFile, {{"Kode Proyek", Text.Trim, type text},
                                                     {"Nama Proyek", Text.Trim, type text},
                                                     {"Paket Pekerjaan", Text.Trim, type text}}),
    BarisValid  = Table.SelectRows(Rapi, each [Kode Proyek] <> null and [Kode Proyek] <> ""),
    Tipe        = Table.TransformColumnTypes(BarisValid, {
                      {"Mata Uang", type text}, {"Periode", Int64.Type}, {"Tanggal Status", type date},
                      {"Anggaran Paket", type number}, {"Nilai Rencana (PV)", type number},
                      {"Nilai Hasil (EV)", type number}, {"Biaya Aktual (AC)", type number},
                      {"Jam Kerja Rencana", type number}, {"Jam Kerja Earned", type number},
                      {"Jam Kerja Aktual", type number}}, "id-ID"),
    PaketKosong = Table.ReplaceValue(Tipe, "", "(tanpa grup)", Replacer.ReplaceValue, {"Paket Pekerjaan"}),
    Urut        = Table.Sort(PaketKosong, {{"Kode Proyek", Order.Ascending}, {"Periode", Order.Ascending},
                                           {"Paket Pekerjaan", Order.Ascending}})
in
    Urut
