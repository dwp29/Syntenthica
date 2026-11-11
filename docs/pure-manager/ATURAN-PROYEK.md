# Aturan Proyek Pure Manager

Berlaku sejak 2026-11-11. Aturan ini **wajib** dan tidak boleh dilanggar
tanpa persetujuan pemilik proyek.

---

## 1. Aturan arsip — mengikat

### 1.1 Setiap hasil kerja harus diarsipkan di DUA tempat

| Tempat | Isi | Kenapa |
|---|---|---|
| **GitHub** (`arena/96cbd65a-synthentica`) | kode, dokumen, skrip | Tahan reset workspace |
| **Google Drive** `SYNTHETICA/Pure Manager` | APK, dokumen, desain, catatan build | Mudah dibuka di HP |

**Dilarang** menyimpan hasil kerja hanya di `/tmp` atau hanya sebagai berkas
yang belum di-commit. Ini sudah menimpa proyek ini lima kali.

### 1.2 Urutan wajib: GitHub dulu, Drive kedua

```
1. tulis berkas
2. git add + commit
3. git push          ← di sini berkas sudah aman dari reset
4. unggah ke Drive
5. verifikasi Drive (list_files: ukuran cocok)
```

Alasan urutannya: kalau reset terjadi antara langkah 3 dan 5, berkas masih bisa
dipulihkan dari GitHub. Kalau dibalik, berkas di Drive tidak punya padanan di git.

### 1.3 Jangan pernah menimpa berkas di Drive

**Kejadian nyata:** sebuah dokumen 19 KB tertimpa `"PLACEHOLDER"` karena memakai
`update_file_content` dengan isi tidak lengkap.

**Aturan baru:** unggah sebagai berkas **baru** (dengan versi di nama), lalu hapus
yang lama setelah unggahan baru terverifikasi. Jangan pernah menimpa langsung.

### 1.4 Struktur folder Drive

```
SYNTHETICA/Pure Manager/
├── 00-ATURAN-DAN-CARA-KERJA/    aturan, tahapan, log harian
├── 01-RISET-DAN-DESAIN/         riset pasar, tema, mockup, deck
├── 02-BUILD-APK/                APK + checksum + catatan build
├── 03-ARSIP-KODE/               (jika perlu) snapshot kode penting
└── 04-HOLD-BAHASAN-AI-DITAHAN/  bahasan AI — DITAHAN, jangan dibuka
```

### 1.5 Format nama berkas — wajib

```
YYYY-MM-DD_[kategori]_[nama]_v[versi].[ext]
```

Contoh:
- `2026-11-11_DOK_Aturan-Proyek_v1.md`
- `2026-11-11_APK_PureManager-0.1.0-SIGNED.apk`
- `2026-11-11_LOG_Build-001_v1.md`

Tanggal memakai **tanggal kerja**, bukan tanggal sistem sandbox.

---

## 2. Aturan teknis — mengikat

### 2.1 Kode THTIDAK ditulis sebelum desain disetujui
Desain sudah disetujui 2026-10-31 (tema). Integrasi AI **DITAHAN** atas perintah
pemilik proyek — bahasan disimpan, tidak diimplementasikan.

### 2.2 Tidak ada kode di luar aplikasi yang dijanjikan
Setiap fitur yang dilaporkan "selesai" harus punya bukti: lolos build,
lolos verifikasi, dan tercatat di log build.

### 2.3 Kunci tanda tangan
- Satu kunci untuk Full dan Minimal.
- Disimpan di **tiga tempat** sebelum APK pertama dirilis.
- Sidik jari SHA-256 dicatat di dokumen dan di `MANIFEST`.
- **Tidak pernah** di-commit ke git.

### 2.4 Jangan klaim tanpa bukti
Larangan eksplisit:
- Jangan bilang "sudah dites di HP" kalau tidak.
- Jangan bilang "semua fitur masuk" kalau sebagian ditunda.
- Jangan sembunyikan fitur yang ditunda — daftar di §3.

---

## 3. Status fitur — jujur, per 2026-11-11

| Fitur | Status |
|---|---|
| Tema (4 model navigasi) | ✅ desain disetujui |
| Tab kustomisasi | ✅ desain disetujui |
| Full + Minimal | ✅ keputusan dikunci |
| Modul via GitHub Releases | ✅ keputusan dikunci |
| **AI (semua bentuk)** | 🔒 **DITAHAN** — bahasan disimpan |
| PDF/Word/Excel | ⬜ v1.1 |
| Editor kode (sora-editor) | ⬜ v1.2 |
| Terminal | ⬜ v1.2 |
| Root (libsu) | ⬜ v1.1 |
| APK pertama | 🔄 sedang dikerjakan |

---

## 4. Log harian

Setiap sesi kerja menghasilkan satu entri log:
`YYYY-MM-DD_LOG_[ringkas].md` di folder `00-ATURAN-DAN-CARA-KERJA`.
Isinya: apa yang dibuat, berkas apa, hash, apa yang gagal, apa langkah berikutnya.
