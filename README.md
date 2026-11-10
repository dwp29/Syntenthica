# Syntenthica

## Pengembangan Synthetica 4.0

[Eksperimen Linux 6.18](SYNTHETICA-4.0-PENGEMBANGAN.md) sedang dikerjakan.
**Jangan flash:** integrasi SUSFS, Manager/UAPI dan kompatibilitas Joyeuse/ROM
belum lengkap atau divalidasi.

## Synthetica Manager 6.0.0 Universal

APK manager **6.0.0** (`net.ember.labs`, versionCode `70000`) sudah
dikompilasi di CI dan ditandatangani dengan sertifikat Synthetica asli.

- Berkas: `Synthetica-Manager-6.0.0-Universal-SIGNED.apk`, `8.990.470` byte
- SHA-256: `666b24b6d4e7835a5b03b7e5e40f77676820f827d0130aad2d96a120a4dd9cac`
- Tanda tangan: v2 + v3, sertifikat `fe833710…ab4140`
- Build CI: [run `42750759962`](https://github.com/dwp29/Syntenthica/actions/runs/42750759962) (compile + verify lulus)

Rincian, termasuk apa yang **belum** diverifikasi, ada di
[docs/SYNTHETICA-MANAGER-6.0.0-UNIVERSAL.md](docs/SYNTHETICA-MANAGER-6.0.0-UNIVERSAL.md).
Instalasi di perangkat, root `su` sungguhan, pemuatan modul, dan perilaku boot
belum diuji.

## Kernel Synthetica 3.2-r1

Kandidat ini dikompilasi dari basis **3.1** dengan fitur-fiturnya dipertahankan
di konfigurasi dan source. Hasilnya masih berupa [bukti kompilasi](SYNTHETICA-3.2-r1.md), **bukan
installer dan belum boleh dianggap aman untuk di-flash**. Boot Android 17,
modul ROM, AVB dan root belum diverifikasi pada perangkat.

Eksperimen 3.2 sebelumnya yang kembali ke basis 2.0
[ditarik sebagai kandidat update](SYNTHETICA-3.2.md); jangan mencampur kernel
atau modul dari kedua build.
