UFO-0.1 — paket AnyKernel3
==========================

Isi zip ini adalah kerangka AnyKernel3 (osm0sis) yang dipakai Roll 3.3, dengan:
  - Image.gz dari build UFO-0.1 (Kinesis 4.14.344 + Synthetica 3.2 features)
  - anykernel.sh yang sudah diubah identitasnya menjadi UFO-0.1
  - DTB TIDAK dibawa (DTB milik ROM Anda dipertahankan)
  - ksud disertakan, tapi /data/adb/ksud yang sudah ada tidak ditimpa

Cara flash:
  1. Rekam dulu boot.img asli (paket ini juga menyimpannya ke /sdcard/UFO-diag/)
  2. Flash lewat recovery (TWRP/OrangeFox): Install -> pilih zip
  3. Reboot system

Kalau gagal boot: masuk recovery, flash boot-sebelum-UFO-0.1.img dari
/sdcard/UFO-diag/ — itu boot image Anda sebelum paket ini.

YANG BELUM DIUJI: paket ini belum pernah di-flash siapa pun. Tidak ada bukti boot,
tidak ada angka baterai, tidak ada uji thermal.
