# Link satu-klik: pulihkan CI Synthetica

Semua URL di bawah sudah diuji (HTTP 200 / redirect sah), bukan tebakan.

---

## Langkah 1 — kosongkan storage (penyebab billing)

GitHub → halaman **Caches & Artifacts** repo:

**<https://github.com/dwp29/Syntenthica/actions/caches>**

Di halaman itu ada dua tab: **Caches** dan **Artifacts**. Pilih **Artifacts**,
lalu hapus yang besar. Saat dokumen ini ditulis:

- total artifact: **189**
- total ukuran: **1,22 GB**
- penyumbang terbesar: `themes501-simulated-ui-emulator-*` (~40–70 MB tiap run)

Ketik `themes501` di kotak filter untuk memunculkannya sekaligus.

---

## Langkah 2 — cek billing

**<https://github.com/settings/billing/summary>**

Lihat tab **Storage** dan **Actions**. Kalau storage turun setelah langkah 1,
build biasanya langsung bisa jalan tanpa menunggu reset bulanan.

---

## Langkah 3 — jalankan build Manager 6.0.0

**<https://github.com/dwp29/Syntenthica/actions/workflows/synthetica60-manager.yml>**

Klik **Run workflow** → pilih branch `arena/96cbd65a-synthentica` → **Run workflow**.

Kalau tombol itu tidak muncul atau run tetap tidak terjadwal, alternatifnya:

**<https://github.com/dwp29/Syntenthica/actions/runs/42658163433>**

Run #1 (commit `e83d3a4`) sukses. Tombol **Re-run all jobs** di kanan atas akan
membangun ulang; hasilnya APK 6.0.0 tanpa perubahan hari ini, tetapi tetap
berguna untuk memastikan pipeline hidup lagi.

---

## Langkah 4 — kirim hasilnya ke agen

Setelah run selesai, kirim salah satu:

- URL halaman run, atau
- angka `SHA256` dari langkah *Verify identity, permissions, daemon...*, atau
- nama artifact `synthetica60-manager-unsigned-<run_id>`

Agen lalu menandatangani dengan kunci `synthetica` (sertifikat
`fe833710…`, 1381 byte / `0x565`), menjalankan `tests/verify_synthetica60_apk.py`,
dan mengunggah APK final ke Google Drive seperti sebelumnya.

---

## Catatan penting

- Workflow di path `synthetica60-manager.yml` sudah dikembalikan ke nama aslinya
  karena GitHub masih mendaftarkan workflow `412328719` di path itu; saat filenya
  sempat di-rename, GitHub menganggapnya rusak (`cannot be rerun`).
- Agen **tidak bisa** menghapus artifact atau memicu run: token yang dipakai
  hanya punya izin `contents`, dan tidak bisa `workflow_dispatch`
  (`403 Resource not accessible by integration`). Karena itu langkah 1–3 harus
  dari akun Anda.
