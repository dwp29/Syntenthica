# Tahapan Kerja Pure Manager

Rencana kerja dengan **bukti terukur** per tahap. Tidak ada tahap yang dianggap
selesai tanpa APK yang bisa dipasang.

---

## Ringkasan

| Tahap | Isi | Target | Status |
|---|---|---|---|
| **T1** | Kerangka + 4 tema + tab kustomisasi | APK 0.1.0 | 🔄 mulai |
| **T2** | File manager inti (copy/move/rename/arsip/thumbnail) | APK 0.2.0 | ⬜ |
| **T3** | Root via libsu + terminal | APK 0.3.0 | ⬜ |
| **T4** | Dua varian: Full & Minimal + tab Modul | APK 0.4.0 | ⬜ |
| **T5** | PDF/Word/Excel (modul docx4j) | APK 0.5.0 | ⬜ |
| **T6** | Editor kode (sora-editor) | APK 0.6.0 | ⬜ |
| **T7** | Edit gambar + edit suara | APK 0.7.0 | ⬜ |
| **T8** | AI | 🔒 **DITAHAN** | — |

---

## T1 — Kerangka, tema, tab kustomisasi

**Tujuan:** APK pertama yang bisa dipasang, dengan 4 tema dan tab kustomisasi
berfungsi penuh. Belum ada fitur berat.

**Yang dibuat:**
1. Proyek Gradle Kotlin + Compose, `applicationId net.pure.manager`
2. `minSdk 29` (Android 10), `targetSdk 36`
3. Sistem token: `PureTheme` dengan `ColorScheme`, `Shapes`, `Typography`, `MotionSpec`
4. 4 tema: iOS, Pixel, Windows, Cyberpunk — **model navigasi berbeda**
5. Mode Light / Dark / AMOLED
6. Tab Kustomisasi: aksen, font, kepadatan, radius, animasi
7. Daftar berkas tiruan (belum baca storage) — untuk membuktikan tema bekerja
8. Workflow CI yang menghasilkan APK unsigned
9. Tanda tangan v2 dengan skrip yang sudah diuji
10. `MANIFEST` + checksum + catatan build

**Bukti selesai (semua wajib):**
- [ ] CI hijau, APK dihasilkan
- [ ] APK signed, verifikasi v2 VALID
- [ ] `aapt dump badging` menunjukkan `net.pure.manager`, minSdk 29
- [ ] 4 tema bisa diganti di aplikasi tanpa restart
- [ ] Tab kustomisasi mengubah aksen dan font secara langsung
- [ ] Terpasang dan terbuka di HP pemilik proyek

**Perkiraan:** 3–5 sesi kerja.

---

## T2 — File manager inti

**Yang dibuat:**
1. `FileOps` interface + `SafeFileOps` (MediaStore + SAF)
2. Izin `MANAGE_EXTERNAL_STORAGE` + layar penjelasan
3. Daftar berkas nyata, navigasi folder, dual-pane
4. Copy/move/delete/rename dengan progress + batal
5. Multi-select, sort, bookmark, cari nama
6. Arsip ZIP/TAR baca + tulis
7. Thumbnail gambar/video + cache
8. Recycle bin

**Bukti:** copy 1.000 berkas tidak crash; ZIP 500 MB bisa dibuka tanpa OOM.

---

## T3 — Root

**Yang dibuat:**
1. `libsu` — **`su` polos dulu**, varian khusus belakangan
2. `RootFileOps`
3. Jelajah `/system`, `/data`; mount rw; chmod/chown
4. Terminal emulator (`TermView`)
5. Turun otomatis ke `SafeFileOps` kalau root dicabut

**Bukti:** diuji di **dua perangkat** — satu Magisk, satu KernelSU.

---

## T4 — Dua varian + tab Modul

1. `ModuleManager`: unduh dari GitHub Releases, verifikasi SHA-256 + Ed25519
2. Tab Modul: status, unduh, hapus
3. Dua varian build, kunci sama

**Bukti:** modul diunduh, verifikasi gagal kalau hash diubah (uji negatif).

---

## T5–T8

Lihat `ARSITEKTUR-MODUL-AI-TEMA.md`. T8 (AI) **ditahan**.

---

## Aturan per tahap

1. **Tidak lanjut ke tahap berikutnya** sebelum bukti tahap ini lengkap.
2. Setiap tahap menghasilkan **satu APK** dengan versi naik.
3. Setiap APK diarsipkan ke Drive + git, lengkap dengan checksum.
4. Kalau ada yang gagal, **dicatat di log**, bukan dihapus.
