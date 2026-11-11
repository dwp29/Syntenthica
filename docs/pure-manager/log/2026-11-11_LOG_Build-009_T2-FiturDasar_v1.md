# Log Build 009 — Pure Manager 0.4.0 · Progres, batal, thumbnail, penyimpanan, ZIP

Tanggal: **2026-11-11**
Tahap: **T2** (menutup "semua yang kamu sebutkan")
Status: **✅ APK siap uji** — run `43005944967` hijau, **65/65 tes JVM lolos**

| | |
|---|---|
| Berkas | `2026-11-11_APK_Pure-Manager-v0.4.0_Progres-Batal-Thumbnail_DebugKey.apk` |
| Ukuran | **18.789.613 byte** |
| SHA256 | `d1bd732a93f0bc0d11fb7c086cbc44abe0d1f2ddb68d5a57ebdc3b778bb230d0` |
| Tanda tangan | v2 ✅ |
| Drive | `1dHbfiLXX0QWng__ohcHS6H1ILn_Sc3D2` |
| GitHub | https://github.com/dwp29/Synthentica/raw/build-output/PureManager-0.4.0-DEBUGKEY.apk |

---

## 1. Lima hal yang diminta, semuanya ada

| Fitur | Perilaku |
|---|---|
| **Progres salin** | persentase, "12 dari 40 berkas", nama berkas yang sedang disalin |
| **Tombol Batal** | benar-benar menghentikan; sisa berkas yang setengah jadi **dihapus** |
| **Thumbnail** | gambar dan video tampil sebagai gambar, bukan lambang |
| **Analisis penyimpanan** | tombol ◧ di toolbar: ukuran tiap folder, terbesar di atas |
| **ZIP** | "Lihat isi arsip" dan "Ekstrak ke sini" dari menu tahan-lama |

Tombol Batal bukan hiasan. Mesin salin memeriksa pembatalan **di antara potongan
512 KB**, jadi berkas video 2 GB berhenti dalam hitungan detik, bukan setelah
selesai. Berkas setengah jadi dihapus karena sisa salinan terbaca sebagai berkas
utuh — itu lebih berbahaya daripada tidak ada berkas sama sekali.

## 2. Tiga bug yang ditemukan tes, bukan oleh mata

Build ini sempat **merah empat kali**. Tiga di antaranya kesalahan saya sendiri,
dan yang keempat menemukan bug nyata:

| Bug | Akibatnya kalau lolos |
|---|---|
| Menyalin folder ke dirinya sendiri | rekursi tanpa henti; disk penuh |
| Batal meninggalkan berkas separuh | berkas rusak yang terlihat utuh |
| Ekstrak ZIP **melewati** entri berbahaya | laporan "berhasil" padahal isinya kurang |

Ketiganya lolos dari saya saat menulis kode. Yang menemukan adalah 65 tes JVM.

## 3. Tiga kegagalan CI yang bukan bug aplikasi

Saya catat apa adanya, karena bagian ini yang paling banyak menghabiskan waktu:

1. Lambda kosong `{}` untuk callback berparameter → **0 tes jalan**, karena kode
   tidak pernah dikompilasi. Kesalahan yang sama juga mengendap di
   `BrowserScreen.kt` sejak 0.3.0 dan belum pernah terkompilasi sekali pun.
2. `'it'` dipakai di dalam lambda yang memberi nama parameternya sendiri.
3. `return@forEach` di dalam `forEachIndexed`.

Yang membuat ketiganya mahal bukan kesalahannya, tetapi **saya tidak bisa membaca
pesan kompilatornya**. Endpoint log GitHub mengembalikan EOF untuk repo ini,
endpoint blob menerima unggahan lalu 404 saat dibaca, dan unduhan artefak diblokir
dari sandbox. Solusinya: kalau build merah, workflow sekarang **mendorong
`tests.log` ke branch `build-output-failure` lewat git** — satu-satunya jalur yang
selalu bekerja. Percobaan pertama langsung menyebut kedua baris yang salah.

## 4. Tes

| Lapis | Jumlah | Catatan |
|---|---|---|
| Tes JVM | **65** (dari 38) | mesin salin 13, ZIP 10, penyimpanan 6, sisanya dari tahap sebelumnya |
| Penjaga sumber Python | **70** | termasuk penjaga bahwa lambda kosong tidak boleh dipakai untuk callback berparameter |

Penjaga sumber itu sendiri pernah salah dua kali di build ini: satu versi menandai
kode yang benar (alarm palsu), satu versi mencocokkan bentuk yang tidak pernah ada
di bug aslinya. Keduanya saya buang dan ganti dengan versi yang saya uji **terhadap
kode rusak** lebih dulu.

## 5. Masih terbuka

| Hal | Status |
|---|---|
| Tema iOS / glass / blur sesuai foto | **belum sesuai** — dikerjakan setelah fitur dasar, sesuai arahan |
| Daftar A–Z yang bisa dilompati | belum ada |
| RAR / 7Z | **tidak diklaim**; hanya ZIP, karena butuh pustaka native yang menambah ukuran APK |
| "Coba dalami reset" | **masih belum jelas** — lihat bagian 6 |

## 6. Soal "reset"

Saya sudah tanya dan jawabannya masih belum bisa saya pakai. Supaya tidak menebak,
saya tulis tiga kemungkinan beserta besar pekerjaannya:

1. **Reset aplikasi** — tombol di Setelan yang menghapus folder pilihan dan
   pengaturan, lalu mulai dari awal. Kecil, bisa di build berikutnya.
2. **Reset tema** — satu tombol mengembalikan tampilan ke bawaan kalau tema
   diutak-atik lalu tidak bisa kembali. Juga kecil.
3. **Riset**, bukan reset — salah tulis. Kalau ini, sebutkan riset tentang apa.

Kalau yang dimaksud (1) atau (2), cukup jawab "reset aplikasi" atau "reset tema",
dan keduanya masuk build setelah tema.

## 7. Cara mencoba

1. Pasang di atas 0.3.x — kunci tangannya sama, jadi langsung menimpa.
2. Coba salin satu folder besar: sekarang ada persentase dan tombol Batal.
3. Buka folder foto: thumbnail muncul di tampilan kisi.
4. Tekan ◧ di toolbar untuk melihat folder mana yang paling besar.
5. Tahan-lama sebuah `.zip` → **Lihat isi arsip** / **Ekstrak ke sini**.

Kalau ada yang aneh, sebutkan langkahnya: layar apa, tombol apa, dan apa yang
diharapkan.
