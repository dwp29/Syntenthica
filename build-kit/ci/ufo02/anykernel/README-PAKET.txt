UFO-0.2 — paket AnyKernel3
==========================

Isi zip ini adalah kerangka AnyKernel3 (osm0sis) yang dipakai Roll 3.3, dengan:
  - Image.gz dari build UFO-0.2 (Saamitk switchoff 4.14.357 + Synthetica 3.2)
  - anykernel.sh yang sudah diubah identitasnya menjadi UFO-0.2
  - DTB TIDAK dibawa (DTB milik ROM Anda dipertahankan)
  - ksud disertakan, tapi /data/adb/ksud yang sudah ada tidak ditimpa

Cara flash:
  1. Rekam dulu boot.img asli (paket ini juga menyimpannya ke /sdcard/UFO-diag/)
  2. Flash lewat recovery (TWRP/OrangeFox): Install -> pilih zip
  3. Reboot system

Kalau gagal boot: masuk recovery, flash boot-sebelum-UFO-0.2.img dari
/sdcard/UFO-diag/ — itu boot image Anda sebelum paket ini.

YANG BELUM DIUJI: paket ini belum pernah di-flash siapa pun. Tidak ada bukti boot,
tidak ada angka baterai, tidak ada uji thermal.

Bedanya dengan UFO-0.1 (yang berbasis Kinesis 4.14.344):
  - Basis 4.14.357, bukan 344. SuSFS, KernelSU-Next, NoMount sudah ada di pohon
    basis; MGLRU dan UCLAMP ditanam lewat enam patch Synthetica asli.
  - Kernel ini menyimpan sidik jari sertifikat Pure Manager 0.10.0, jadi APK
    manager kita dikenali. Jangan ganti APK dengan build lain tanpa mengganti
    hash-nya di build_ufo02.sh.
