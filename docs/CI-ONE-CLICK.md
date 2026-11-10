# Link satu-klik: jalankan build Manager 6.0.0

Semua URL di sini sudah diuji (HTTP 200), bukan tebakan.

---

## Status: build sudah sukses

Run **`42750759962`** (`main`, commit `8106db7`) berstatus **success**. Langkah
6 (**Compile**) dan 7 (**Verify**) lulus. Artifact
`synthetica60-manager-unsigned-42750759962` berukuran `7.610.330` byte.

APK final: `Synthetica-Manager-6.0.0-Universal-SIGNED.apk`, `8.990.470` byte,
SHA-256 `666b24b6d4e7835a5b03b7e5e40f77676820f827d0130aad2d96a120a4dd9cac`.

Halaman run: <https://github.com/dwp29/Syntenthica/actions/runs/42750759962>

---

## Akar masalahnya (sudah diperbaiki)

Branch **`main` hanya berisi `README.md`**. GitHub hanya menampilkan tombol
**Run workflow** kalau file `workflow_dispatch` ada di **branch default**. Karena
`main` tidak punya `.github/workflows/` sama sekali, tombol itu tidak pernah
muncul — bukan karena billing, bukan karena workflow rusak.

Billing Anda juga sudah saya baca dari screenshot: `$0` billable,
Compute `$0 / $12.00`, storage `0 GB / 0.5 GB`. Jadi **billing bukan penyebab**.
Repo publik tidak menghitung artifact sebagai storage berbayar.

Perbaikan yang sudah masuk:

| Branch | Isi | Fungsi |
|---|---|---|
| `main` | `.github/workflows/manager60-run.yml` | memunculkan tombol Run workflow |
| `arena/96cbd65a-synthentica` | `synthetica60-manager.yml` | seluruh langkah build sebenarnya |

`manager60-run.yml` **memuat salinan utuh** langkah build, bukan memanggil
workflow lain. Ini disengaja: `uses:` ke reusable workflow lintas-branch membuat
GitHub gagal menjadwalkan run (`startup_failure`, 0 job). Kesamaan langkah
diverifikasi otomatis dengan `js-yaml` (`steps identical: true`), jadi salinan
tidak bisa diam-diam menyimpang.

---

## Jalankan build — satu klik

### 👉 <https://github.com/dwp29/Syntenthica/actions/workflows/manager60-run.yml>

Klik tombol **Run workflow** (kanan atas) → **Run workflow**.

Halaman itu sekarang menampilkan tombolnya; sebelumnya 404.

---

## Kalau masih ingin cara lama

Run #1 dulu sukses, dan tombol **Re-run all jobs** selalu tersedia.

### 👉 <https://github.com/dwp29/Syntenthica/actions/runs/42658163433>

---

## Setelah build selesai (sudah dilakukan)

Alur yang dipakai pada build sukses:

1. artifact `synthetica60-manager-unsigned-42750759962` diunduh;
2. SHA-256-nya dicocokkan dengan `SHA256.txt` di dalam ZIP
   (`7f3333b6…bd5c8`, cocok);
3. ditandatangani dengan kunci `synthetica` (sertifikat `fe833710…`, 1381 byte /
   `0x565`), v2 + v3 aktif;
4. `tests/verify_synthetica60_apk.py` dijalankan dan semua gate lulus;
5. APK final diunggah ke Google Drive beserta berkas `.sha256`.

Isi payload tidak berubah sama sekali saat penandatanganan (642 entri sebelum
dan sesudah).

---

## Batas agen

Token integrasi hanya punya izin `contents`. Ia **tidak** bisa
`workflow_dispatch` (`403 Resource not accessible by integration`), tidak bisa
menghapus artifact, dan tidak bisa menekan tombol di UI. Karena itu langkah
klik di atas harus dari akun Anda.

---

## Riwayat kegagalan (jangan diulang)

| Percobaan | Hasil | Sebab |
|---|---|---|
| `workflow_dispatch` di workflow yang hanya ada di branch arena | tombol tidak muncul | GitHub hanya menampilkan tombol untuk file di branch default |
| `main` memanggil `uses: .../synthetica60-manager.yml@arena/...` | `startup_failure`, **0 job**, `referenced_workflows: []` | GitHub tidak me-resolve reusable workflow lintas-branch dari `main` |
| `main` berisi salinan langkah build utuh | **sukses** (run `42750759962`) | tidak ada `uses:` yang bisa gagal; langkahnya diverifikasi identik |
| `strings_manager50.xml` dengan apostrof mentah `kernel's` | gagal `aapt2` di run `42747877219` | apostrof harus `\'` di resource Android |
| `createRootShellBuilder` dideklarasikan dua kali | gagal Kotlin `unresolved reference: build` di run `42749580793` | pesan error menunjuk pemanggil, bukan deklarasi ganda |

Kedua bug di atas sekarang dijaga test regresi (`test_strings_are_valid_aapt_input`,
`test_no_duplicate_top_level_declarations`), dan penjaganya sudah dibuktikan
gagal saat bug disuntikkan kembali.

Kesimpulan: jangan memakai `uses:` lintas-branch untuk kasus ini, dan jangan
mengubah nama berkas workflow (yang di-rename tidak terdaftar dan tidak bisa
di-rerun).
