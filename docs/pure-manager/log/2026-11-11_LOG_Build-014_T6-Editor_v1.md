# LOG Build-014 — Tahap 6: Editor teks/kode (0.9.0)

- **Tanggal:** 11 November 2026
- **Versi:** 0.9.0 (versionCode 15)
- **Run hijau:** `43038923337` — SUCCESS, 3m29s
- **Status:** T6 selesai. T7 (gambar/audio) berikutnya; T8 (AI) masih ditahan.

## Yang diminta

Tahap 6 pada rencana: editor kode di dalam aplikasi. Rencana awal memakai
`sora-editor`.

## Keputusan: tidak memakai sora-editor

Dua fakta bertemu, dan keduanya cukup:

1. **Lisensi.** sora-editor berlisensi LGPL-2.1. Itu keputusan lisensi sebelum
   menjadi keputusan dependensi: pustaka LGPL di dalam APK menimbulkan kewajiban
   yang harus dipahami dulu, bukan ditambahkan sambil jalan.
2. **Tidak bisa diverifikasi.** Maven Central, jitpack.io dan dl.google.com
   diblokir dari sandbox ini (`curl` mengembalikan 000). Rilis GitHub sora-editor
   tidak menyertakan AAR — hanya kode sumber. Dependensi yang tidak bisa
   diunduh dan diperiksa di sini hanya akan gagal di CI, tiga menit sekali, tanpa
   cara memeriksanya lebih dulu.

Satu percobaan mengukur akses Maven dari runner CI sempat ditambahkan, lalu
dicabut lagi: setelah editor ditulis sendiri, jawabannya tidak lagi mengubah
apa pun, dan langkah yang hanya mencetak kode HTTP yang tidak terbaca (log run
repo ini mengembalikan EOF) adalah satu menit tambahan di setiap build.

## Yang dibuat

| Berkas | Isi |
|---|---|
| `edit/Text.kt` | `Buffer`, `Edit`, `History`: undo/redo berbatas 200 langkah, pengetikan digabung jadi satu langkah, auto-indent, dedent, indent blok |
| `edit/Syntax.kt` | `Language` (11 bahasa), `highlight()` → daftar `Span`, `sortedSpans()`, `lineColumn()` |
| `edit/Search.kt` | `findIn`, `findAllIn`, `replaceAll`, `nextMatchIndex`, `FindBar` |
| `edit/Brackets.kt` | `autoCloseFor` (tutup otomatis `()[]{}""''`), `deletesPair`, `matchingBracket` |
| `edit/EditIO.kt` | Baca/tulis berkas nyata dan dokumen SAF; deteksi UTF-8 vs Latin-1; batas 8 MB; tolak data biner; tulis lewat berkas sementara + rename |
| `ui/EditorScreen.kt` | Layar editor: `BasicTextField` + `VisualTransformation` berwarna, bilah Simpan/Undo/Redo/Cari, cari-ganti, status baris:kolom |
| `tools/editor_logic_check.py` | Port Python dari algoritme yang sama, dijalankan penjaga Python |
| `test/.../EditorTest.kt` | 56 tes JVM |

Tidak ada dependensi baru. Gradle tidak berubah selain nomor versi dan komentar
alasan yang diperbarui.

## Bug yang ditemukan sebelum CI

Port Python ada karena sandbox ini **tidak punya JDK**: Kotlin tidak bisa
dijalankan di sini, jadi kesalahan aritmetika offset hanya akan muncul sebagai
kegagalan CI. Port itu menjalankan kasus yang sama dan menemukan tujuh kesalahan
nyata sebelum kode pernah menyentuh CI:

1. **Undo yang menempelkan teks baru ke atas dirinya sendiri.** `Edit` hanya
   menyimpan teks yang disisipkan; saat undo, teks yang dihapus sudah tidak ada,
   jadi yang dihitung adalah teks pengganti. Undo tampak tidak melakukan apa-apa.
   → `Edit` sekarang menyimpan `removed`.
2. **Kata menjadi dua langkah undo.** Digabungnya dua ketukan dihitung dari
   "langkah sebelumnya menyisipkan tepat satu karakter", yang berhenti benar
   begitu dua ketukan bergabung. → penanda `typed` pada `Edit`.
3. **Kurung mencocokkan dirinya sendiri.** `matchingBracket` mulai menghitung dari
   karakter itu sendiri, jadi kedalaman langsung nol dan `f(a` dilaporkan
   berpasangan. → pindai mulai dari tetangga.
4. **`find` memakai `lowercase()`.** Panjang string tidak selalu sama setelah
   dihuruf-kecilkan (I bertitik Turki, ß), sehingga offset hasil pencarian bisa
   menunjuk karakter yang salah. → `regionMatches(ignoreCase = true)`.
5. **Indentasi ganjil** (3 spasi) menghapus seluruh indentasi, bukan satu level.
6. **`indentBlock` menggeser offset dengan arah salah** saat seleksi.
7. **Cari mundur membungkus ke indeks yang salah.**

## Bug yang ditemukan CI

Tiga putaran merah, semuanya jujur dan semuanya diperbaiki:

1. **Komentar blok bersarang.** KDoc di `Syntax.kt` memuat dua karakter pembuka
   komentar; Kotlin menyarangkan komentar blok, jadi komentar kedua menelan sisa
   berkas. Kompiler melaporkan 30 galat sintaks, yang pertama 25 baris di bawah
   kesalahan sebenarnya. Penjaga Python sekarang menghitung kedalaman komentar di
   semua berkas, dan sudah diuji dengan memasukkan kembali bug-nya.
2. **`Int` bertemu `Long`.** `const val` tanpa tipe adalah `Long`; setiap
   perbandingan dengan `ByteArray.size`/`File.length()` butuh cast. Dua putaran
   terpisah, karena setiap pemanggil salah dengan caranya sendiri. → konstanta
   diketik `Int`, dan `formatMb` diberi overload `Int`.
3. **`object OffsetMapping` bersarang menutupi nama pustaka**, sehingga
   `OffsetMapping.Identity` tidak resolve.
4. **Lima ekspektasi tes salah tulis**, bukan kodenya: hasil auto-close adalah
   satu string + offset caret (bukan pasangan), dan dua offset akhir komentar/
   kutip dihitung dari titik acuan yang salah.

## Verifikasi

- **135 penjaga Python OK** (118 sebelumnya + 17 kelas `CodeEditor`).
- **191 tes JVM**: `EditorTest` 56 kasus, sisanya suite sebelumnya.
- Dua APK diperiksa: 146 entri zip, dan penanda `EditorScreen`, `Buffer`,
  `SyntaxColour`, `EditIO`, `autoCloseFor`, `matchingBracket`, `findAllIn`,
  `MAX_BYTES` ditemukan di dex.

## Hasil

| Varian | Berkas | Byte | sha256 (16 awal) | Drive |
|---|---|---|---|---|
| FULL | `PureManager-0.9.0-DEBUGKEY.apk` | 19.035.369 | `770ebebdf2533717` | `1kJsaYX3dh76B31nvFVdGwTYha4dgFW14` |
| MINIMAL | `PureManager-0.9.0-minimal-DEBUGKEY.apk` | 19.035.377 | `63420ca58d22d85d` | `1GR3Ho7ABXLxPfhdxMr9fAHIFmtn4aDVF` |

MINIMAL masih 8 byte lebih besar dari FULL, sama seperti 0.8.0 — flavor tidak
memengaruhi ukuran karena kode kedua varian identik dan perbedaannya hanya
`BuildConfig.HAS_MODULES`.

## Keterbatasan yang harus dikatakan

- **Belum ada "Simpan sebagai"**. Tombolnya ada dan menjawab dengan kalimat
  bahwa fitur itu belum ada; Simpan menulis ke berkas yang sama.
- **Belum ada autocomplete, pencarian simbol, atau integrasi git.** Ini editor
  teks dengan penyorotan, bukan IDE.
- **Berkas di atas 8 MB tidak bisa dibuka di editor** (ditolak dengan pesan yang
  menyebut batasnya). Berkas biner juga ditolak.
- **Penyorotan dihentikan pada 200.000 karakter**; di atas itu teks tampil tanpa
  warna, bukan setengah berwarna.
- **Edit dicapai lewat panjang-tekan → "Edit teks"**, bukan ketuk, supaya
  perilaku ketuk yang sudah dipakai dari tahap 1–5 tidak berubah.
- **Belum diuji di HP.** Belum ada yang menjalankan editor ini di perangkat
  sungguhan; itu menunggu owner.

## Pengarsipan

Kedua APK diunggah ke folder `02` Drive. LOG-013 sebelumnya ditolak filter
keamanan Drive; log ini ditulis tanpa contoh jalur sistem berkas, tetapi bila
Drive menolak lagi, isinya tetap ada di repo.
