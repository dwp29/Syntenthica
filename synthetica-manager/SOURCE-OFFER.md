# Source lengkap Synthetica Manager

Dokumen ini adalah penawaran source (source offer) untuk APK `net.ember.labs`
versi 6.0.0 dan seterusnya, sesuai GPL-3.0 pasal 6.

## Di mana source-nya

| Yang dibutuhkan | Lokasi |
| --- | --- |
| Manager (kode APK ini) | `synthetica-manager/` di <https://github.com/dwp29/Syntenthica> |
| Kernel, modul, installer | sisa repository yang sama |
| Basis upstream | <https://github.com/KernelSU-Next/KernelSU-Next> |
| Lisensi penuh | [`LICENSE`](LICENSE), atau <https://www.gnu.org/licenses/gpl-3.0.txt> |

## Yang TIDAK ada di source publik (dan kenapa)

Satu-satunya bagian yang tidak dipublikasikan adalah **kunci penandatanganan**
(`synthetica-2.0.p12`) dan kata sandinya. Kunci itu bukan bagian dari "source
code" dalam pengertian GPL, dan kernel Synthetica memverifikasi tanda tangan APK
ini sebagai syarat root — menerbitkannya berarti siapa pun bisa membuat APK
yang diterima kernel sebagai Manager resmi.

APK tetap dapat dibangun ulang dari source di atas; hanya hasil build tersebut
tidak akan dikenali kernel Synthetica sampai ditandatangani dengan kunci itu.
Build tanpa kunci tetap berfungsi sebagai Manager universal lewat `su` pada
kernel lain (lihat `docs/SYNTHETICA-MANAGER-6.0.0-UNIVERSAL.md`).

## Reproduksi build

Prosedur lengkap ada di `build-kit/scripts/` dan `.github/workflows/`
(repository utama). Ringkasnya:

1. Siapkan JDK 21 + Android SDK.
2. Suntikkan `libksud.so` ABI 64-bit ke `app/src/main/jniLibs/` (tidak masuk git).
3. `./gradlew :app:assembleRelease` — hanya lewat CI resmi untuk rilis.
4. Tandatangani dengan kunci Synthetica (tidak dibagikan).
5. Jalankan `tests/verify_synthetica60_apk.py` untuk memeriksa identitas,
   UAPI v4, dan isi payload.

## Kontak

Pembuat build ini: **Pure_Saturday** — Telegram [@Pure_Saturday](https://t.me/Pure_Saturday).
