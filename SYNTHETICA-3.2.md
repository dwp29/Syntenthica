# Synthetica 3.2 — eksperimen baseline lama (digantikan)

> **DITARIK SEBAGAI KANDIDAT UPDATE 3.1.** Build di halaman ini kembali ke
> basis 2.0 dan menghapus beberapa fitur/perbaikan 3.1; pengguna mengoreksi
> bahwa itu bukan upgrade yang diminta. Arsip dipertahankan hanya sebagai
> bukti historis, bukan rilis 3.2 yang direkomendasikan. Revisi yang mempertahankan
> 3.1 menggunakan identitas `3.2-r1` agar ABI dan modulnya tidak tertukar.
>
> **JANGAN FLASH.** Kernel baru sudah dikompilasi, tetapi belum diuji boot pada
> perangkat fisik atau ROM Android 17. ZIP di bawah adalah bukti kompilasi,
> **bukan** installer recovery atau boot image lengkap. Tidak ada bukti bahwa
> build ini memperbaiki kegagalan boot pada ROM tertentu.

## Unduh bukti kompilasi

- [Synthetica 3.2 — bukti kompilasi, bukan ZIP flash](https://drive.google.com/file/d/194lsbP7ZAmRRMSYTpdVQyOJrD5IW140c/view?usp=drivesdk)
- [Checksum SHA-256 ZIP](https://drive.google.com/file/d/1spsy_uKGQbhLtef6HJscY9MPQm_NbDhN/view?usp=drivesdk)
- Ukuran ZIP: **16.036.430 byte**. SHA-256:
  `7783dc7c6fa01bcc7843ddfe125c582e19889a5b891125926ed790bd127ebe26`
- SHA-256 `DO-NOT-FLASH-Synthetica-3.2-Image.gz`:
  `cb6c953dba1515b710ff0f3d90086afa572903bd702a735aed53af7e31b6e943`
- Build aktual: [GitHub Actions 42499760357](https://github.com/dwp29/Syntenthica/actions/runs/42499760357),
  source resep pada commit `bb7c4f3adff9866e92de983aed54f33124d7c5f6`.
- Verifikasi ulang arsip, signature dan koreksi metadata:
  [GitHub Actions 42501978944](https://github.com/dwp29/Syntenthica/actions/runs/42501978944).

ZIP berisi image kernel, konfigurasi, `Module.symvers`, `System.map`, enam modul
hasil build yang sama, sertifikat publik modul, checksum dan catatan provenance.
Tidak ada private key, boot image lengkap, DTB, DTBO, `ksud`, atau installer.
Berkas Drive disimpan di folder pribadi; pemeriksaan izin menunjukkan hanya
pemilik yang memiliki akses.

## Pilihan untuk mengurangi variabel berisiko

3.2 adalah **kompilasi ulang baru**, bukan image 2.0 yang diganti namanya.
Release yang tertanam adalah `4.14.357-openela-synthetica-3.2`. Resep kembali
ke source dan konfigurasi tersimpan dari basis 2.0 yang dipin:
`Saamitk/kernel_xiaomi_sm6250-switchoff@c1e6f795b557b7bf92220c91f05a42b456de7a74`.
Kompilasi menggunakan **Ubuntu Clang/LLD 18.1.3**, bukan toolchain Neutron 24
3.1. Keputusan ini mengurangi jumlah perubahan baru yang perlu divalidasi;
tidak membuktikan toolchain atau fitur 3.1 merupakan penyebab gagal boot.

- Nilai konfigurasi yang dihasilkan sama dengan arsip 2.0 kecuali
  `LOCALVERSION`; patch MGLRU/UCLAMP eksperimental 3.1 tidak diikutkan.
- Ini juga berarti patch lain yang ditambahkan setelah basis 2.0, termasuk
  perubahan jalur root 3.0/3.1, **tidak otomatis dipertahankan**. Konfigurasi
  KernelSU/SUSFS dasar tetap ada, tetapi perilaku root harus diuji ulang.
- `IKCONFIG` diperbaiki agar data konfigurasi di image sesuai `.config` build
  sesungguhnya, bukan stock defconfig yang lama.
- Konfigurasi `MODULE_SIG_FORCE=y`, `MODVERSIONS=y`, `SECURITY_SELINUX=y`,
  `DM_VERITY=y` dan KernelSU dasar dipertahankan; status enforcement saat runtime
  belum diuji. Tidak ada bypass tanda tangan modul atau vermagic, penonaktifan
  AVB, maupun force-load modul yang ditambahkan.

## Hasil pemeriksaan

1. Seluruh **12.236** rekaman ekspor dibandingkan dengan `Module.symvers` basis
   2.0: **12.227 ekspor kernel** dan **9 ekspor modul**. Nama, pemilik, jenis
   ekspor dan CRC semuanya cocok; `module_layout=0x08efcbb0`. File
   `Module.symvers` sendiri identik byte-for-byte dengan arsip referensi,
   SHA-256 `07bb866c067a4c2c0567f5eb17f51137ca7da948dd82799077d93deb82278972`.
   Ini bukan pembandingan dengan modul ROM Android 17 yang sebenarnya.
2. Enam modul yang memang dipilih konfigurasi basis dibangun dan ditandatangani
   bersama kernel ini. Tanda tangan, vermagic dan seluruh version record modul
   tersebut diperiksa secara statis terhadap build yang sama. **Belum pernah
   dimuat di perangkat atau diintegrasikan ke ROM.**
3. Identitas Manager `net.ember.labs` dan fingerprint sertifikat yang dipin
   ditemukan di image. Itu belum membuktikan Manager 5.0.1 dikenali atau root
   bekerja saat runtime.
4. Sertifikat modul baru memiliki SHA-256
   `37a423ef945ff4d6234cf2d0ace538c4c2e9aaeaae1f0ba144754c2d0722dba2`;
   sertifikat yang sama tidak ditemukan pada image referensi 2.0. Sertifikat
   penandatangan modul ROM dan keyring runtime belum diperiksa. Nama release
   baru juga mengubah vermagic. Jadi, **CRC yang cocok tidak menjamin modul ROM
   dapat diterima atau dimuat**.

Uji host lokal menjalankan **346 tes, 70 dilewati** karena prasyarat/fixture
opsional tidak tersedia; termasuk pemeriksaan ulang arsip build aktual, enam
signature modulnya, dan koreksi metadata. Pemeriksaan host dan fixture berjalan
tanpa ponsel dan tidak membuktikan AVB, ramdisk, DTB/DTBO, recovery, kamera,
modem, stabilitas atau boot Android 17. Tidak ada file atau partisi di perangkat
yang disentuh.

## Mengapa belum ada ZIP flash

Installer yang lolos fixture belum tentu aman pada recovery, layout boot, dan
ROM lain. Hash DTB referensi lama hanya membatasi satu referensi historis, bukan
persetujuan untuk ROM Android 17. Karena integrasi modul, signature/AVB, dan
boot fisik belum diverifikasi, belum dibuat installer 3.2. Jangan memindahkan
`Image.gz` ini ke ZIP installer lain atau memaksa pemuatan modul sebagai jalan
pintas. Untuk rilis yang dapat diuji, diperlukan verifikasi terhadap perangkat
dan ROM yang tepat, backup boot yang dapat dipulihkan, serta pengujian recovery
terlebih dahulu. Itu tetap tidak menjamin semua perangkat Android 17 aman.

## Pemeriksaan modul offline opsional bagi pengembang

`build-kit/scripts/audit_synthetica32_rom_modules.py` membaca salinan privat
modul `.ko` dan ZIP bukti yang tepat, lalu membandingkan vermagic, CRC impor,
dependensi dan tanda tangan terhadap sertifikat publik build. Tidak ada modul
yang dijalankan atau dipasang. Laporan detail harus baru, berada di luar repo
dan input, dan ditulis privat (`0600`). Modul terkompresi atau symlink dicatat
sebagai dilewati; hasil cocok sekalipun bukan izin flash atau bukti boot.

```sh
python3 build-kit/scripts/audit_synthetica32_rom_modules.py \
  --modules /path/privat/modul-rom \
  --evidence /path/privat/Synthetica-3.2-DO-NOT-FLASH-Bukti-Kompilasi.zip \
  --report /path/privat/laporan-modul-3.2.json
```

## Koreksi teks bukti dan reproduksibilitas

Satu kalimat pada `STATUS.json` transfer CI awal secara keliru menyatakan
sertifikat baru **bukan** penandatangan modul ROM, padahal penandatangan ROM
belum diketahui. ZIP unduhan mengoreksi kalimat menjadi **mungkin tidak cocok**
dan memperbarui `SHA256SUMS.txt`. Hanya dua berkas itu yang berubah; seluruh
image, enam modul, konfigurasi, sertifikat, `System.map` dan provenance
**identik byte-per-byte** dengan transfer CI awal. Tidak ada kompilasi ulang
atau perubahan biner saat koreksi.

Transfer CI asli tetap dapat diidentifikasi oleh Git blob
`1c5903d8e306d2339a1af7272c4b715154098a27` dan SHA-256
`7adfddedb3bacab7304e4b6d8e644451de7730515913e38e3ef54431eeb84895`.
Transfer yang dikoreksi adalah Git blob
`e0af6ff272653fcfd4075667586b55de3e8eba23`; identitas lengkapnya dipin di
`build-kit/ci/synthetica32-build-evidence.json`. Isi setiap berkas terkoreksi
dapat direproduksi dengan `build-kit/scripts/correct_synthetica32_evidence.py`;
representasi ZIP terkompresi dapat berbeda antara versi zlib.
