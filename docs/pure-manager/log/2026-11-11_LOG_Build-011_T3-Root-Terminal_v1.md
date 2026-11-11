# LOG-011 — Pure Manager 0.6.0
## Tahap T3: akses root, terminal, pintasan folder sistem

**Tanggal:** 2026-11-11
**Versi:** 0.5.0 → **0.6.0** (versionCode 12)
**Run hijau:** [43023031877](https://github.com/dwp29/Synthentica/actions/runs/43023031877)
**APK:** `PureManager-0.6.0-DEBUGKEY.apk`, 18.871.529 byte,
sha256 `7ce2692812c9ab638986990836d606d0853f98bf605f3febd704c2b7c3e4f187`
**Di Drive:** ID `16FU999S0teAET5qUMgj0Qzu9dEXL5E9e` (folder `02-BUILD-APK`)
**Log ini di Drive:** ID `10IXj6BJhVwSkG7KvnrHSJpWfrMRlcmUF`

---

## 1. Yang dibangun

| Bagian | Isi |
|---|---|
| `root/Shell.kt` | menjalankan `su` / shell dengan **batas waktu**, argumen terkutip, dan runner yang bisa diganti |
| `root/Terminal.kt` | baris perintah: `cd`, `pwd`, `help`, `clear`, `exit`, riwayat, batas scrollback |
| `ui/TerminalScreen.kt` | layar terminal (monospace, gelap, terpisah dari tema) |
| tab **Modul** | baris "Terminal" sekarang benar-benar membuka terminal |
| `Storage.rootPlaces()` | pintasan `/system`, `/data`, `/data/adb`, `/` di panel Lokasi, **di balik sakelar** |

---

## 2. Keputusan yang perlu Anda tahu

**Tanpa `libsu`.** Rencana awal memakai libsu. Saya tidak memakainya karena
pekerjaan yang benar-benar dilakukan di sini kecil dan stabil (jalankan `su -c`,
baca kode keluar), sedangkan menambah dependensi berarti satu titik gagal baru di
lingkungan build yang jaringan kerjanya hanya lewat git. Hasilnya ±120 baris yang
**bisa diuji di JVM dengan `sh`**, bukan kode yang hanya bisa diuji di HP ber-root
milik Anda. Kalau nanti butuh fitur libsu yang lebih berat (daemon, mount), itu
bisa ditambah tanpa membongkar apa pun.

**Terminal ini bukan emulator terminal.** Tidak ada pty. Artinya: `top`, `vi`,
`nano`, dan program layar-penuh lain **tidak akan tampil benar**. Layarnya
mengatakan itu terus-terpanjang, bukan menyembunyikannya. `ls`, `cat`, `cp`, `mv`,
`grep`, `find`, `chmod`, `mount`, dan perintah baris-perintah biasa bekerja.

**`su` dicari, bukan diminta.** Aplikasi memeriksa keberadaan binary `su` (7 lokasi
umum, termasuk KernelSU) tanpa menjalankan apa pun. Dialog izin root muncul saat
perintah **pertama** dijalankan — saat Anda sedang melihat terminal dan mengerti
kenapa ada dialog. Aplikasi yang memunculkan dialog root saat dibuka biasanya
ditolak.

**Folder sistem di balik sakelar.** `/system` dan `/data` hanya muncul di panel
Lokasi kalau Anda menyalakan "Folder sistem". Alasannya: baris yang ada tapi selalu
gagal dibuka lebih buruk daripada baris yang tidak ada. Tanpa root, aplikasi tetap
100% berfungsi; terminal hanya berjalan sebagai pengguna biasa dan mengatakannya.

---

## 3. Keamanan

| Hal | Cara ditangani |
|---|---|
| Nama berkas berisi spasi / kutip | `Shell.quote()` — kutip tunggal dengan escape `'\''`. Diuji dengan nama `laporan rahasia's.txt`. |
| Perintah menggantung (dialog root tak dijawab) | batas waktu 15–20 detik, proses dimatikan paksa. Diuji dengan `sleep 30` dan anggaran 1 detik. |
| Output raksasa | scrollback dipotong di 500 baris. |
| Perintah berjalan di UI thread | tidak: `withContext(Dispatchers.IO)`. Dijaga tes. |
| Menulis ke berkas sistem | **tidak** ada tombol "mount rw" otomatis. Itu tetap perintah manual di terminal. Saya sengaja tidak membuat satu tombol yang bisa merusak sistem tanpa sadar. |

---

## 4. Bukti

- **96 tes sumber** (`tests/test_pure_manager_sources.py`) — OK.
- **110 tes JVM di CI** (bertambah 24: `ShellTest` 10, `TerminalTest` 14).
- APK diperiksa: zip bersih, 146 entri, string `TerminalScreen`, `root/Shell`,
  `suBinary`, `rootPlaces` ada di dalam `classes*.dex`.
- **Yang belum:** uji nyata di HP ber-root. Saya tidak punya perangkatnya. Yang bisa
  saya buktikan adalah lapisan logikanya berjalan benar dengan `sh` dan bahwa
  aplikasi tidak crash tanpa root. Uji di HP Anda (KernelSU/Magisk) tetap perlu, dan
  itu memang disebut di rencana T3 sebagai bukti yang wajib.

---

## 5. Dua bug nyata selama build ini

**a. `Shell.Result` menutupi `kotlin.Result`.** Run 43021233350 merah:
`One type argument expected for class 'Result'` — di berkas yang tidak menyebut
`Result` dengan sengaja. Penyebabnya: saya mengganti nama kelasnya menjadi `Output`
tapi anotasi tipe kembalian masih `Result`. Penjaga baru mencari **bentuk
deklarasi** yang menutupi tipe stdlib (`Result`, `Pair`, `Triple`, `Lazy`,
`Nothing`), dan sudah diuji dengan menanam kelas palsu lebih dulu.

**b. Tes kutipan membandingkan dialek shell, bukan perilaku.** Run 43022254336
merah di `ShellTest` karena `printf '%s'` mencetak kutip tunggal di runner CI
tapi tidak di sandbox ini. Yang penting bukan bentuk cetakannya, melainkan bahwa
teks yang disisipkan **tidak menjadi perintah kedua**; asersinya sekarang
menghitung baris.

Dua-duanya kelas kesalahan yang sama: hijau di sini, merah di sana. Itu sebabnya
setiap penjaga baru saya uji dengan menanam kerusakan lebih dulu.

---

## 6. Yang belum

| Hal | Status |
|---|---|
| T4 dua varian (Full & Minimal) + modul unduhan | belum |
| T5 PDF/Word/Excel | belum |
| T6 editor kode | belum |
| T7 edit gambar/audio | belum |
| T8 AI | ditahan |
| Kunci rilis dipakai | menunggu 2 variabel GitHub (lihat LOG-010 §5) |
| Arti "reset" | masih belum jelas |
