# Gate integrasi AxSandbox — 3 November 2026

**Belum dipasang.** Kandidat sumber yang dipilih pengguna adalah [AxionAOSP/android_packages_apps_AxSandbox](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/tree/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62), commit `df0f91f826a32bb5e7cd2aff53de80f6b1b99f62`. Pemeriksaan berikut hanya statis, bukan audit keamanan menyeluruh atau uji perangkat.

## Ketergantungan platform

- [`Android.bp`](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/blob/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62/Android.bp) meminta `certificate: "platform"`, `platform_apis`, privileged `system_ext`, serta `AppLocker`, `privapp-permissions-axsandbox`, `ax_sandbox_shared` dan `ax_compose`.
- [`AndroidManifest.xml`](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/blob/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62/AndroidManifest.xml) meminta `android.uid.system` dan permission sensitif. Kode [`AuthenticateActivity`](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/blob/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62/src/com/android/axion/sandbox/AuthenticateActivity.kt) menggunakan `android.app.AxSandboxManager` dan `Context.AX_SANDBOX_SERVICE`; file [`BackupManager`](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/blob/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62/src/com/android/axion/sandbox/io/BackupManager.kt) memanggil API spoofing khusus per aplikasi.
- Kehadiran dan kecocokan service/API ini, AppLocker, SELinux, signature platform, dan izin pada basis diza **belum dibuktikan**. Memasang APK yang hanya di-compile atau ditandatangani kunci lain tidak membuktikan akan diterima sebagai system UID atau bahwa penguncian/spoofing bekerja. Jangan melemahkan verifikasi signature atau permission untuk memaksanya.

## Risiko data yang memerlukan pengujian sebelum dipakai

Pada [`FileVaultManager.kt`](https://github.com/AxionAOSP/android_packages_apps_AxSandbox/blob/df0f91f826a32bb5e7cd2aff53de80f6b1b99f62/src/com/android/axion/sandbox/io/FileVaultManager.kt), `importFile` menulis data terenkripsi, memasukkan metadata, kemudian memanggil `cleanupOriginal`, yang dapat menghapus berkas asli. Kode itu tidak menunjukkan verifikasi baca-kembali penuh/durabilitas sebelum penghapusan. `migrateLegacyIfNeeded` juga menghapus `metadata.json` pada jalur exception. Ini adalah **temuan statis/risiko yang perlu diuji**, bukan bukti telah terjadi kehilangan data atau cacat yang dapat dieksploitasi.

Sebelum pemakaian: pengujian gagal I/O, keystore belum siap, ruang habis, gangguan daya, restore dan rollback dengan **data sintetis**, serta review keamanan/otorisasi antar-user dan provider. Jangan mencoba pada data pengguna atau mengklaim vault/sandbox aman hanya karena menu tampil.

## Lisensi dan status

Sejumlah file sumber memiliki header Apache-2.0, tetapi tidak ditemukan berkas LICENSE/NOTICE tingkat repositori pada tree commit tersebut; hak dan kewajiban seluruh komponen tetap perlu diklarifikasi. Tidak ada modifikasi ke APK, framework, image, atau perangkat dalam pemeriksaan ini. Dukungan sandbox, spoofing, dan keamanan tetap **belum terbukti**.
