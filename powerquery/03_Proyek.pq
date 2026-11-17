// Query: Proyek
// Master proyek hasil ekstraksi Python (data\processed\proyek.csv). Sel kosong di CSV diubah menjadi null
// sebelum tipe angka diterapkan, agar tidak muncul Error di kolom angka.
let
    Sumber     = Csv.Document(File.Contents(FolderData & "\processed\proyek.csv"),
                              [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Judul      = Table.PromoteHeaders(Sumber, [PromoteAllScalars = true]),
    Pilih      = Table.SelectColumns(Judul, {"kode_proyek", "nama_proyek", "sektor_sumber", "mata_uang",
                     "jumlah_aktivitas", "mulai_rencana", "selesai_rencana", "durasi_rencana_hari", "bac",
                     "jumlah_periode", "biaya_sumber_daya_di_anggaran", "durasi_aktual_hari", "bac_ringkasan",
                     "catatan_kualitas", "masuk_analisis"}),
    KosongNull = Table.TransformColumns(Pilih, {}, each if _ = "" then null else _),
    Tipe       = Table.TransformColumnTypes(KosongNull, {
                     {"jumlah_aktivitas", Int64.Type}, {"mulai_rencana", type datetime}, {"selesai_rencana", type datetime},
                     {"durasi_rencana_hari", type number}, {"bac", type number}, {"jumlah_periode", Int64.Type},
                     {"durasi_aktual_hari", type number}, {"bac_ringkasan", type number}}, "en-US"),
    Tanggal    = Table.TransformColumns(Tipe, {{"mulai_rencana", DateTime.Date, type date},
                                               {"selesai_rencana", DateTime.Date, type date}}),
    // proyek yang memenuhi kriteria analisis diletakkan di atas (sumber PivotTable di sheet Rekap)
    Urut       = Table.Sort(Tanggal, {{"masuk_analisis", Order.Descending}, {"kode_proyek", Order.Ascending}}),
    TanpaUrut  = Table.RemoveColumns(Urut, {"masuk_analisis"}),
    Nama       = Table.RenameColumns(TanpaUrut, {
                     {"kode_proyek", "Kode Proyek"}, {"nama_proyek", "Nama Proyek"}, {"sektor_sumber", "Sektor (sumber)"},
                     {"mata_uang", "Mata Uang"}, {"jumlah_aktivitas", "Jumlah Aktivitas"}, {"mulai_rencana", "Mulai Rencana"},
                     {"selesai_rencana", "Selesai Rencana"}, {"durasi_rencana_hari", "Durasi Rencana (hari kerja)"},
                     {"bac", "Anggaran (BAC)"}, {"jumlah_periode", "Jumlah Periode"},
                     {"biaya_sumber_daya_di_anggaran", "Biaya Sumber Daya di Anggaran"},
                     {"durasi_aktual_hari", "Durasi Aktual (hari kerja)"}, {"bac_ringkasan", "BAC di Ringkasan DSLIB"},
                     {"catatan_kualitas", "Catatan Kualitas Data"}})
in
    Nama
