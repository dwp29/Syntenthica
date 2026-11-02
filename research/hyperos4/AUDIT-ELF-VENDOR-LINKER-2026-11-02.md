# Inventaris ELF vendor dan linker runtime

**Tanggal:** 2 November 2026. **Status:** pemeriksaan statis host pada salinan kandidat kedua, bukan uji ABI atau boot perangkat.

## Hasil yang sudah terverifikasi

[Run 41460808839](https://github.com/dwp29/Syntenthica/actions/runs/41460808839) memeriksa header ELF berkas reguler di direktori `vendor/bin` dan subdirektori yang terlihat. Hasilnya:

| Header yang ditemukan | Jumlah | Interpreter yang tertulis |
|---|---:|---|
| ARM 32-bit, ELF `ET_DYN` | 11 | `/system/bin/linker` |
| AArch64 64-bit, ELF `ET_DYN` | 183 | `/system/bin/linker64` |
| ARM 32-bit, ELF `ET_EXEC` | 1 | tidak ada `PT_INTERP` |

Total 225 berkas reguler diperiksa, termasuk 30 non-ELF; tidak ada header ELF yang dikategorikan rusak/tidak didukung. Ada **178 symlink** yang tidak diikuti, sehingga hasil bukan inventaris semua executable vendor atau library. Kategori ELF dan string interpreter tidak membuktikan bahwa file dapat dijalankan.

Pada system yang sama, `/system/bin/linker` dan `/system/bin/linker64` adalah symlink menuju `/apex/com.android.runtime/bin/linker` dan `/apex/com.android.runtime/bin/linker64`. Paket `com.android.runtime.apex` terlihat sebagai file reguler berukuran **12.996.608 byte**. Pada run tersebut paket hanya dihitung dan tidak dibuka; paket pada disk saja tidak membuktikan target symlink tersedia atau APEX aktif.

Run tersebut menyelesaikan **58 tes regresi host** serta kontrol sintetis checkvintf positif/negatif/rusak. Pemeriksaan VINTF tetap menghasilkan exit 65 untuk kedua skenario snapshot parsial; [laporan terpisah](AUDIT-CHECKVINTF-PARSIAL-SELINUX-2026-11-02.md) menjelaskan batasnya. ZIP kandidat dan empat extent tetap identik sebelum/sesudah, identitas 67 XML cocok, dan tidak ada perangkat diakses.

Pada [run 41461656228](https://github.com/dwp29/Syntenthica/actions/runs/41461656228), satu paket runtime APEX itu dibaca sebagai data dan hanya `apex_payload.img` disalin sementara; CRC member ZIP cocok. Payload berformat **EROFS**, yang tidak didukung pembaca filesystem pada run tersebut. SHA-256 paket `021646695ba127260ea9cc96df6c924edfeb86ba783781a9cc276db232443fc4`; SHA-256 payload `9776b642132872ce4931218694c345231ecaac4490ead5d7c2f7c24e17481c17`. Tanda tangan APEX tidak diverifikasi.

Setelah alat host resmi AOSP `fsck.erofs` lulus kontrol sintetis positif/rusak pada [probe 41462548664](https://github.com/dwp29/Syntenthica/actions/runs/41462548664), [run 41463290011](https://github.com/dwp29/Syntenthica/actions/runs/41463290011) memeriksa payload yang sama di chroot read-only, tanpa jaringan/capability, dengan hasil ekstraksi hanya pada tmpfs terbatas yang dibuang setelah audit. Dua kontrol sintetis EROFS dan tiga kontrol checkvintf lulus sebelum kandidat dibaca; **66 tes host** lulus. Di dalam payload terlihat:

| Path dalam runtime APEX | Header statis | SHA-256 |
|---|---|---|
| `/bin/linker` | ARM 32-bit, `ET_DYN`, 1.849.436 byte | `08512f614863b9a2d12829ad8c4ec0041b35ceded2a2e48d9e9652ccd90b29e4` |
| `/bin/linker64` | AArch64 64-bit, `ET_DYN`, 2.473.488 byte | `b6dd216b7a775b8f04c825cada286bfe7ddaeecf2c0c10e617287118965abc00` |

Ini membuktikan kedua file ada **dalam paket yang diperiksa**, bukan bahwa APEX tersebut aktif atau linker dapat berjalan di kernel dan namespace perangkat. Tidak ada binary ROM yang dijalankan. Tanda tangan APEX maupun statement build tool belum diverifikasi.

## Pemeriksaan DT_NEEDED lanjutan

[Run 41466512890](https://github.com/dwp29/Syntenthica/actions/runs/41466512890) mem-parsing `DT_NEEDED` dari 194 executable vendor yang memiliki interpreter yang dikenali; tidak ada kegagalan parser atau nama yang ditolak. Dari pasangan nama dan bitness, 344 memiliki nama serta header ELF dasar yang sesuai pada direktori library langsung terpilih, enam hanya terlihat sebagai symlink yang tidak diikuti, dan 36 tidak terlihat pada direktori tersebut. Ini **bukan** pembuktian ABI cocok ataupun bukti 36 library hilang: APEX, ODM, subdirektori, namespace dan versi simbol belum diselesaikan.

## Batasan

Pemeriksaan ini tidak mengikuti symlink vendor atau menyelesaikan dependency `DT_NEEDED` dalam namespace linker, dan tidak membuktikan ABI library 32/64-bit, versi simbol, kemampuan ARM 32-bit kernel, APEX aktif, kebijakan SELinux, AVB, service HAL, recovery atau boot. Tidak boleh menyimpulkan bahwa dukungan 32-bit ada atau tidak ada hanya dari header ELF dan nama symlink.

Paket, binary dan kernel ROM tidak dieksekusi; image serta perangkat tidak diubah. Fitur serta modul tetap **hold**; tindakan pada perangkat di luar persetujuan awal tetap memerlukan persetujuan spesifik.
