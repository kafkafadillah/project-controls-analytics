// Fungsi: membaca satu file laporan status (CSV, pemisah ";", UTF-8 dengan BOM).
// Nama query: fnBacaLaporan
(isi as binary) as table =>
let
    Sumber = Csv.Document(isi, [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Judul  = Table.PromoteHeaders(Sumber, [PromoteAllScalars = true])
in
    Judul
