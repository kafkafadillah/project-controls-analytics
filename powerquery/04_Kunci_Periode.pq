// Query: Kunci_Periode
// Daftar unik proyek x periode dari Laporan_Status; menjadi tiga kolom pertama sheet Data_Periode.
let
    Sumber = Laporan_Status,
    Kunci  = Table.Distinct(Table.SelectColumns(Sumber, {"Kode Proyek", "Periode", "Tanggal Status"})),
    Urut   = Table.Sort(Kunci, {{"Kode Proyek", Order.Ascending}, {"Periode", Order.Ascending}})
in
    Urut
