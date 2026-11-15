# PURE MANAGER — DISCONTINUED

**Status: DIHENTIKAN. Jangan dilanjutkan, jangan dibangun ulang, jangan dipasang.**

APK "Pure Manager" (`net.pure.manager`) tidak lagi dikembangkan, tidak lagi
ditandatangani, dan seluruh arsipnya sudah dihapus dari repo ini maupun dari Drive.

## Kenapa berhenti

Alasan utamanya bukan soal tampilan atau fitur: **Pure Manager adalah aplikasi
penjelajah berkas (file explorer), bukan manager KernelSU.**

Itu membuat satu keputusan sebelumnya salah. Kernel sempat dipatok ke sertifikat
Pure Manager lewat `KSU_NEXT_MANAGER_SIZE` / `KSU_NEXT_MANAGER_HASH`. Memasang
sertifikat sebuah file explorer di kernel tidak membuatnya mampu mengelola izin
root; ia hanya mendapat perlakuan sebagai manager (mis. modul tidak di-umount untuk
appid-nya) dan bisa menjalankan `su`. Kemampuan yang orang harapkan dari "manager"
— daftar aplikasi, izin root per-UID, pasang modul KernelSU — memang tidak ada di
dalamnya.

Kernel sekarang memakai manager KernelSU-Next resmi, tanpa pin ke APK apa pun.

## Apa yang sudah dihapus

- `pure-manager/` — seluruh kode APK
- `docs/pure-manager/` — seluruh dokumen, aturan proyek, dan log build
- `.github/workflows/pure-manager-build.yml` — pipeline build APK
- `docs/2026-11-15_PURE-MANAGER-TAMPILAN-BARU.md`
- `tests/test_pure_manager_sources.py`
- `ci-stage/keystore.b64`, `ci-stage/keystore-password.txt`,
  `ci-stage/expected-signer.txt`
- `google_drive/2026-11-11_KEY-Pure-Manager-PM_KEYSTORE_B64-...txt`
- Arsip Drive: folder `08-PURE-MANAGER-APK-DAN-LOG`,
  `05-KEY-SIGNING-BERKAS-PENTING-Pure-Manager`, beserta seluruh APK, laporan,
  dan log di dalamnya

## Kunci tanda tangan sudah dimusnahkan

Private key Pure Manager (PKCS#12, sertifikat RSA-4096, sidik jari
`A2:F9:42:45:2E:EC:1C:D8:76:3E:6C:F3:3B:99:37:C1:A9:9B:38:49:C6:27:73:A7:3B:F4:44:77:67:43:F2:D8`)
ikut dihapus atas permintaan pemilik proyek.

Akibatnya, dan ini tidak bisa dibatalkan:

- APK yang sudah beredar dengan tanda tangan itu **tidak bisa diperbarui lagi**;
  versi baru harus memakai `applicationId` berbeda.
- Tanda tangan itu **tidak bisa direproduksi**, jadi siapa pun yang punya APK lama
  tidak bisa memverifikasi ulang dari sumber.
- Kernel yang masih memakai sertifikat itu **tidak akan mengenali** APK mana pun
  sebagai manager, karena tidak ada APK yang bisa ditandatangani dengan kunci itu lagi.

Kalau menemukan salah satu APK lama itu terpasang, cabut.

## Kalau nanti butuh manager

Pakai manager KernelSU-Next resmi, atau bangun manager baru dengan nama, paket, dan
kunci yang benar-benar baru. Jangan menghidupkan kembali `net.pure.manager`.
