# Link satu-klik: jalankan build Manager 6.0.0

Semua URL di sini sudah diuji (HTTP 200), bukan tebakan.

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

`manager60-run.yml` tidak punya langkah build sendiri: ia **memanggil** workflow
asli (`workflow_call`) di branch arena, jadi langkah build tetap di satu tempat
dan tidak bisa berbeda.

---

## Jalankan build — satu klik

### 👉 <https://github.com/dwp29/Syntenthica/actions/workflows/manager60-run.yml>

Klik tombol **Run workflow** (kanan atas) → **Run workflow**.

Halaman itu sekarang menampilkan tombolnya; sebelumnya 404.

---

## Kalau masih ingin cara lama

Run #1 dulu sukses, dan tombol **Re-run all jobs** selalu tersedia:

### 👉 <https://github.com/dwp29/Syntenthica/actions/runs/42658163433>

---

## Setelah build selesai

Kirim salah satu ke agen:

- URL halaman run, atau
- angka `SHA256` dari langkah *Verify identity, permissions, daemon...*, atau
- nama artifact `synthetica60-manager-unsigned-<run_id>`

Agen lalu menandatangani dengan kunci `synthetica` (sertifikat `fe833710…`,
1381 byte / `0x565`), menjalankan `tests/verify_synthetica60_apk.py`, dan
mengunggah APK final ke Google Drive seperti sebelumnya.

---

## Batas agen

Token integrasi hanya punya izin `contents`. Ia **tidak** bisa
`workflow_dispatch` (`403 Resource not accessible by integration`), tidak bisa
menghapus artifact, dan tidak bisa menekan tombol di UI. Karena itu langkah
klik di atas harus dari akun Anda.
