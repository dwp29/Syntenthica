# Synthetica Manager 5.0.1 — empat komposisi tema

Manager 5.0.1 mempertahankan paket `net.ember.labs`, menaikkan version code dari 60000 ke **60001**, dan mengubah komposisi layar untuk Pixel Signal, Cyberpunk, iOS Glass, dan Neon. Pilih melalui **Settings → Customization → Design theme**. Tema sekarang memengaruhi hero/status, bentuk kartu, latar, dan dock pada layar Manager; bukan hanya font, warna, atau aplikasi preview terpisah. Pilihan aksen, terang/gelap/AMOLED, intensitas dan gerak tetap tersedia melalui preferensi yang sama.

Versi ini juga memperbaiki ikon aksi atas yang tidak terbaca pada tema Pixel gelap serta dock yang dapat tetap tersembunyi setelah kembali dari halaman tergulir. iOS Glass merupakan desain terinspirasi kaca, bukan produk Apple; ada fallback tanpa blur untuk versi Android yang tidak mendukungnya. APK tidak memasang atau mem-flash kernel secara otomatis. Operasi root, modul, dan tuning yang dipilih pengguna tetap memiliki risiko.

## Artefak yang dipilih

| Atribut | Nilai |
|---|---|
| File | `Synthetica-Manager-5.0.1-MultiTema-SIGNED.apk` |
| SHA-256 APK signed | `d90269abb5ff89f23371f8b56e489f6f57e8708ae752aa5ea5390b7e64473d11` |
| APK unsigned yang ditandatangani | SHA-256 `58604ffb5544ea5e8372e38856047be3bb029decd69169a7b816266390b89b76` |
| Paket / versi | `net.ember.labs` / `5.0.1` (`60001`) |
| Dukungan minimum | Android 8.0 (API 26), arm64 |
| Sertifikat asli, SHA-256 | `fe833710a733f63061691c87ff222e84ca2fa462582aceaf5f577fe799ab4140` |
| Kode build produksi | `e6b6ae6530ab614dd9e3aa879ea7e8607c157157` |

APK release dan checksum disimpan terpisah dari repositori ini. Penandatanganan lokal menggunakan sertifikat Manager asli; salinan sementara key dan backup yang diunduh dihapus setelahnya. Pemeriksaan lokal memverifikasi signature v2/v3, sertifikat, alignment 4-byte dan 16-KiB, isi non-signature identik dengan unsigned yang diuji, izin yang sama dengan Manager 5.0, dan penolakan terhadap salinan APK yang dimodifikasi. Ini **bukan** pengujian runtime atau jaminan bahwa Android menerima pembaruan pada semua perangkat.

## Bukti dan batasan

- [Build unsigned dan fixture 5.0.1](https://github.com/dwp29/Syntenthica/actions/runs/42460246310) berhasil untuk kode produksi di atas. Fixture baseline dan updated yang cocok dicatat dalam `build-kit/ci/synthetica501-ui-fixture-evidence.json`.
- [Uji emulator layar Manager](https://github.com/dwp29/Syntenthica/actions/runs/42467032708) lulus untuk empat tema pada layar yang menggunakan komposisi produksi, mode terang/gelap/AMOLED, restart, gerak dikurangi, navigasi layar kecil, dan preferensi saat **fixture simulasi** diperbarui. [Smoke test empat tema](https://github.com/dwp29/Syntenthica/actions/runs/42462193207) juga lulus. Fixture berisi data simulasi dan bukan pengujian backend root; beberapa jalur yang tidak diaudit masih dapat memanggil shell sehingga fixture hanya boleh dipakai pada layar yang diuji dalam emulator terisolasi.
- Tangkapan layar fixture diberi label **SIMULATED UI / NO ROOT**; nilai status bukan data perangkat nyata.
- Pada layar sangat sempit dengan font 150%, sebagian label dock dapat terpotong. Perbaikan tambahan untuk label besar tidak disertakan karena belum berhasil dibangun dan diuji.
- Belum ada uji instalasi/update APK production signed ini pada ponsel fisik, ROM target, root nyata, modul/WebUI, tuning, boot, atau recovery. Identitas paket dan sertifikat yang cocok serta version code lebih tinggi adalah syarat update, bukan jaminan. Simpan cadangan; jangan langsung mencopot aplikasi lama jika update ditolak karena dapat menghapus data/pengaturan.
- Run CI yang lebih baru [42470600287](https://github.com/dwp29/Syntenthica/actions/runs/42470600287) gagal pada unduhan Gradle 9.2.0 yang timeout, sebelum kompilasi. Ini berbeda dari run build sukses yang menghasilkan APK di atas; kode produksi relevan pada commit restorasi `20cf565` sama dengan build `e6b6ae6`. Jangan menganggap run terbaru tersebut sukses.

## Kode dan pengujian

- Overlay tema: `build-kit/ci/ksun-themes501/`.
- Build produksi dan fixture: `build-kit/scripts/build_manager_501_themes.py` dan `build-kit/scripts/build_manager_501_fixture.py`.
- Runner emulator: `tests/run_themes501_emulator.py`; smoke: `tests/smoke_themes501_emulator.py` dan `tests/smoke_themes501_small_emulator.py`.
- Signer lokal dengan sertifikat yang dipin dan pengujian key sementara: `build-kit/scripts/sign_manager_501_locally.py`, `tests/test_multitheme501_signing*.py`.

Kernel 3.1 yang terpisah masih berlabel TEST. Jangan menghapus data atau menonaktifkan AVB/vbmeta untuk memaksa boot.
