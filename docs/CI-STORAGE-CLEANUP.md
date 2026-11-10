# Bersihkan artifact GitHub Actions Synthetica (satu klik)

Storage meteran GitHub Actions akun `dwp29` kemungkinan penuh karena
**189 artifact = 1,22 GB** menumpuk di `dwp29/Syntenthica`
(artifact terbesar: `themes501-simulated-ui-emulator-*`, ~70 MB per run).

Tool ini tidak bisa menghapusnya lewat API karena token yang dipakai agen hanya
punya izin `contents`. Dua cara di bawah sama-sama hanya butuh browser.

---

## Cara 1 — klik di browser (paling cepat, tanpa token)

1. Buka: <https://github.com/dwp29/Syntenthica/actions/caches>
2. Di kiri atas halaman ada tab **Artifacts** (sebelah **Caches**). Klik.
3. Hapus yang besar-besar, terutama semua yang namanya berawalan
   `themes501-simulated-ui-emulator-`.
4. Karena daftarnya panjang, pakai pencarian: ketik `themes501`, lalu hapus
   yang muncul.

> Kalau tab **Artifacts** tidak terlihat, buka langsung:
> <https://github.com/dwp29/Syntenthica/actions>
> lalu pilih satu run yang lama → di bagian bawah halaman run ada tombol hapus
> per-artifact.

---

## Cara 2 — satu perintah dengan GitHub CLI (paling cepat kalau punya `gh`)

Tempel di terminal (bukan di browser). Ini menghapus **artifact lebih dari 7
hari** saja, jadi yang baru tetap aman:

```bash
gh auth refresh -s actions:write   # sekali saja, memberi izin hapus artifact
gh api --paginate \
  "repos/dwp29/Syntenthica/actions/artifacts?per_page=100" \
  --jq '.artifacts[] | select(.created_at < (now - 7*86400 | todate)) | .id' \
| while read id; do gh api -X DELETE "repos/dwp29/Syntenthica/actions/artifacts/$id" && echo "deleted $id"; done
```

Untuk menghapus **semua** artifact (termasuk yang baru):

```bash
gh api --paginate "repos/dwp29/Syntenthica/actions/artifacts?per_page=100" \
  --jq '.artifacts[].id' \
| while read id; do gh api -X DELETE "repos/dwp29/Syntenthica/actions/artifacts/$id"; done
```

---

## Setelah dibersihkan

1. Cek status: <https://github.com/settings/billing/summary>
   (tab **Storage** dan **Actions**).
2. Kalau sudah normal, jalankan build:
   <https://github.com/dwp29/Syntenthica/actions/workflows/manager60-build.yml>
   → tombol **Run workflow** → branch `arena/96cbd65a-synthentica` → **Run**.
3. Setelah build selesai, APK unsigned bisa diambil dari halaman run, lalu
   agen menandatangani dengan kunci `synthetica` dan memverifikasinya.

## Kenapa artifact menumpuk

`manager60-build.yml` memakai `retention-days: 14`, dan workflow emulator UI
menyimpan 40–70 MB per run. Bilang saja kalau mau agen menurunkan retensi ke 3
hari (dan menambah langkah hapus otomatis) supaya tidak terulang.
